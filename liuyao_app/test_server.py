"""HTTP integration checks for the personal loopback application; no paid API calls."""
import copy
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

from .server import Application, Server, case_ai_attempts, diagnostic_error
from case_store import Actor, CaseStore


INPUT = {'question': '这辆车还能满足日常出行需要吗？',
         'lines': ['young_yang', 'young_yin', 'old_yang', 'old_yin', 'young_yang', 'young_yin']}


def fake_catalog(self):
    return {'providers': [
        {'id': 'deepseek', 'models': ['test-model'], 'configured': True},
        {'id': 'doubao', 'models': ['other-model'], 'configured': False}],
        'default_provider': 'deepseek'}


class DiagnosticFieldChecks(unittest.TestCase):
    def test_known_output_schema_path_and_missing_fields_are_retained(self):
        missing = diagnostic_error({'code':'CONTRACT_INVALID', 'message':"$.claims[0]: missing ['limitations', 'assumptions']"})
        self.assertEqual(missing['field_path'], '$.claims[0]')
        self.assertEqual(missing['missing_fields'], ['assumptions', 'limitations'])
        enum = diagnostic_error({'code':'CONTRACT_INVALID', 'message':'$.conclusion.direction: enum mismatch'})
        self.assertEqual(enum['field_path'], '$.conclusion.direction')
        self.assertNotIn('missing_fields', enum)
        root = diagnostic_error({'code':'CONTRACT_INVALID', 'message':"$: missing ['binding']"})
        self.assertEqual(root['field_path'], '$')
        self.assertEqual(root['missing_fields'], ['binding'])

    def test_dynamic_field_names_values_and_invalid_paths_are_removed(self):
        for text in ("$.private_secret: missing ['assumptions']", "$.claims[secret]: enum mismatch", "$.claims['私密问题']: missing ['binding']"):
            with self.subTest(text=text):
                result = diagnostic_error({'code':'CONTRACT_INVALID', 'message':text})
                self.assertNotIn('field_path', result)
                self.assertNotIn('missing_fields', result)
                self.assertNotIn('private_secret', json.dumps(result))
                self.assertNotIn('私密问题', json.dumps(result, ensure_ascii=False))
        result = diagnostic_error({'code':'CONTRACT_INVALID', 'message':"$.claims[1]: missing ['assumptions', 'sk-private-key', '私密问题', 'fabricated_field']"})
        self.assertEqual(result['field_path'], '$.claims[1]')
        self.assertEqual(result['missing_fields'], ['assumptions'])
        for secret in ('sk-private-key', '私密问题', 'fabricated_field'):
            self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))

    def test_batch_explicit_path_is_retained_without_model_text(self):
        result = diagnostic_error({'code':'ENGINE_INFERENCE_REQUIRED',
            'message':'untrusted model text with dynamic ID PRIVATE_CASE_123',
            'path':'$.claims[3].inference_refs'})
        self.assertEqual(result['field_path'], '$.claims[3].inference_refs')
        self.assertEqual(result['code'], 'ENGINE_INFERENCE_REQUIRED')
        self.assertNotIn('PRIVATE_CASE_123', json.dumps(result))
        self.assertNotIn('untrusted model text', json.dumps(result))

    def test_explicit_path_uses_same_strict_schema_allowlist_as_legacy(self):
        for path in ('$.fake_field', '$.claims[私密姓名].inference_refs',
                     '$.claims[3].private_secret', '$.claims[1000000].inference_refs',
                     '$.claims[3].inference_refs\nPRIVATE_CASE_123',
                     "$.claims['sk-private-key']", None, [], 123):
            with self.subTest(path=path):
                result = diagnostic_error({'code':'CONTRACT_INVALID', 'message':'untrusted text', 'path':path})
                self.assertNotIn('field_path', result)
                self.assertNotIn('missing_fields', result)
                for private in ('fake_field', '私密姓名', 'private_secret', 'PRIVATE_CASE_123', 'sk-private-key'):
                    self.assertNotIn(private, json.dumps(result, ensure_ascii=False))

    def test_explicit_valid_path_has_priority_but_keeps_legacy_missing_fields_consistent(self):
        result = diagnostic_error({'code':'CONTRACT_INVALID', 'path':'$.claims[3].inference_refs',
                                   'message':"$.claims[0]: missing ['limitations']"})
        self.assertEqual(result['field_path'], '$.claims[3].inference_refs')
        self.assertNotIn('missing_fields', result)
        legacy = diagnostic_error({'code':'CONTRACT_INVALID', 'path':'$.fabricated_field',
                                   'message':"$.claims[0]: missing ['limitations']"})
        self.assertEqual(legacy['field_path'], '$.claims[0]')
        self.assertEqual(legacy['missing_fields'], ['limitations'])

    def test_owner_raw_attempt_projection_retains_only_validated_path(self):
        case = {'case_id':'CASE_TEST', 'analysis_runs':[{'analysis_run_id':'RUN_TEST', 'ai_events':[
            {'attempt': {'stage':'interpretation', 'raw_output':'local-only reply',
                'validation_errors':[
                    {'code':'ENGINE_INFERENCE_REQUIRED', 'message':'specific repair guidance',
                     'path':'$.claims[3].inference_refs'},
                    {'code':'CONTRACT_INVALID', 'message':'legacy error', 'path':'$.private_secret'}],
                'model_run_metadata':{'attempt_number':2, 'system_prompt':'never expose'}}}]}]}
        result = case_ai_attempts(case)
        errors = result['analysis_runs'][0]['attempts'][0]['validation_errors']
        self.assertEqual(errors[0]['path'], '$.claims[3].inference_refs')
        self.assertEqual(errors[0]['message'], 'specific repair guidance')
        self.assertNotIn('path', errors[1])
        self.assertNotIn('private_secret', json.dumps(result))
        self.assertNotIn('never expose', json.dumps(result))


class HTTPChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.release = threading.Event()
        self.release.set()
        self.entered = threading.Event()
        self.catalog_patch = patch.object(Application, 'config', fake_catalog)
        self.catalog_patch.start()
        # Server imports the pipeline inside its worker. Keep that import offline,
        # even if the production pipeline is being built in parallel.
        self.pipeline_patch = patch.dict(sys.modules, {'liuyao_app.pipeline': types.SimpleNamespace(run_analysis=self.fake_pipeline)})
        self.pipeline_patch.start()
        self.app = Application(self.temp.name, pipeline=self.fake_pipeline)
        self.server = Server(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.cookie = None
        status, headers, _ = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.cookie = headers['Set-Cookie'].split(';')[0]

    def tearDown(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.app.close()
        self.pipeline_patch.stop()
        self.catalog_patch.stop()
        self.temp.cleanup()

    def fake_pipeline(self, db_path, actor, case_id, provider, model, revision, progress):
        self.calls.append((case_id, provider, model, revision))
        store = CaseStore(db_path)
        try:
            started = store.start_analysis(actor, case_id, source_hash='1' * 64,
                rules_digest='2' * 64, prompt_digest='3' * 64, engine_build='http-fixture',
                expected_revision_seq=revision, idempotency_key='start-' + str(len(self.calls)))
            progress({'stage': 'fixture', 'analysis_run_id': started['analysis_run_id'], 'secret': 'never-expose'})
            self.entered.set()
            if not self.release.wait(10):
                raise RuntimeError('test worker was not released')
            report = {'summary': 'HTTP fixture report', 'question': INPUT['question']}
            store.finish_analysis(actor, case_id, started['analysis_run_id'], status='completed',
                idempotency_key='finish-' + started['analysis_run_id'], report=report)
            return {'status': 'completed', 'analysis_run_id': started['analysis_run_id'], 'report': report}
        finally:
            store.close()

    def request(self, method, path, value=None, *, raw=None, headers=None, cookie=True):
        data = json.dumps(value, ensure_ascii=False).encode() if value is not None else raw
        supplied = {'Host': '127.0.0.1:' + str(self.server.server_port)}
        if cookie and self.cookie:
            supplied['Cookie'] = self.cookie
        if method == 'POST':
            supplied.update({'Content-Type': 'application/json', 'X-App-Request': '1',
                             'X-Idempotency-Key': 'request-' + str(time.monotonic_ns())})
        if headers:
            for key, val in headers.items():
                if val is None:
                    supplied.pop(key, None)
                else:
                    supplied[key] = val
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, path, data, headers=supplied)
            response = connection.getresponse()
            response_headers = dict(response.getheaders())
            payload = response.read()
            if response_headers.get('Content-Type', '').startswith('application/json'):
                payload = json.loads(payload)
            return response.status, response_headers, payload
        finally:
            connection.close()

    def create(self, **kwargs):
        status, _, result = self.request('POST', '/api/cases', {'input': copy.deepcopy(INPUT)}, **kwargs)
        self.assertEqual(status, 201, result)
        return result['case_id']

    def analyze(self, case_id, *, key=None, revision=1):
        headers = {'X-Idempotency-Key': key} if key else None
        return self.request('POST', '/api/cases/' + case_id + '/analyze',
            {'provider': 'deepseek', 'model': 'test-model', 'expected_revision_seq': revision}, headers=headers)

    def wait_job(self, job_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status, _, result = self.request('GET', '/api/jobs/' + job_id)
            self.assertEqual(status, 200, result)
            if result['status'] not in ('queued', 'running'):
                return result
            threading.Event().wait(.01)
        self.fail('job did not finish')

    def test_cookie_and_security_headers(self):
        status, headers, _ = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_session_required_and_untrusted_cookie(self):
        for headers, cookie in [({}, False), ({'Cookie': 'liuyao_session=forged'}, True)]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('GET', '/api/cases', headers=headers, cookie=cookie)[0], 401)

    def test_host_origin_and_fetch_site(self):
        for headers in [{'Host': 'evil.example'}, {'Host': '127.0.0.1:1'},
                        {'Origin': 'https://evil.example'}, {'Origin': 'null'},
                        {'Sec-Fetch-Site': 'cross-site'}]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('GET', '/api/config', headers=headers)[0], 403)
        self.assertEqual(self.request('GET', '/api/config', headers={
            'Origin': 'http://127.0.0.1:' + str(self.server.server_port)})[0], 200)

    def test_mutation_requires_header_and_idempotency_key(self):
        for headers, expected in [({'X-App-Request': None}, 403),
                                  ({'X-Idempotency-Key': None}, 400),
                                  ({'X-Idempotency-Key': 'x' * 161}, 400)]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request('POST', '/api/cases', {'input': INPUT}, headers=headers)[0], expected)

    def test_cors_preflight_not_allowed(self):
        status, headers, _ = self.request('OPTIONS', '/api/cases')
        self.assertEqual(status, 405)
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_only_loopback_binding(self):
        with self.assertRaises(ValueError):
            Server(('0.0.0.0', 0), self.app)

    def test_second_instance_cannot_recover_active_workspace(self):
        with self.assertRaises(RuntimeError):
            Application(self.temp.name, pipeline=self.fake_pipeline)

    def test_strict_json_encoding_and_duplicate_keys(self):
        for raw in [b'{', b'\xff', b'{"input": {}, "input": {}}',
                    b'{"input":{"question":"x","question":"y"}}', b'{"input": NaN}']:
            with self.subTest(raw=raw):
                status, _, payload = self.request('POST', '/api/cases', raw=raw)
                self.assertEqual(status, 400, payload)
                self.assertEqual(payload['error']['code'], 'INVALID_JSON')

    def test_json_content_type_and_body_size(self):
        self.assertEqual(self.request('POST', '/api/cases', raw=b'{}', headers={'Content-Type': 'text/plain'})[0], 415)
        for raw in [b'', b' ' * 65537]:
            self.assertEqual(self.request('POST', '/api/cases', raw=raw)[0], 413)
        self.assertEqual(self.request('POST', '/api/cases', raw=b'{}', headers={'Transfer-Encoding': 'chunked'})[0], 400)
        self.assertEqual(self.request('POST', '/api/cases', raw=b'{}', headers={'Content-Length': '-1'})[0], 413)
        self.assertEqual(self.request('POST', '/api/cases', raw=b'{}', headers={'Content-Length': 'invalid'})[0], 400)

    def test_excessive_json_nesting_is_client_error(self):
        raw = b'{"input":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}'
        status, _, payload = self.request('POST', '/api/cases', raw=raw)
        self.assertIn(status, (400, 422), payload)

    def test_client_cannot_supply_owner_or_service_fields(self):
        for field in ('owner_id', 'session_id', 'source_hash', 'report', 'recorded_at'):
            with self.subTest(field=field):
                self.assertEqual(self.request('POST', '/api/cases', {'input': INPUT, field: 'evil'})[0], 400)
                data = copy.deepcopy(INPUT); data[field] = 'evil'
                self.assertEqual(self.request('POST', '/api/cases', {'input': data})[0], 422)
        self.assertEqual(self.request('GET', '/api/cases')[2]['cases'], [])

    def test_invalid_inputs_are_retained_as_intake_failures(self):
        status, _, payload = self.request('POST', '/api/cases', {'input': {'question': '', 'lines': []}})
        self.assertEqual(status, 422)
        self.assertTrue(payload['failure_id'])
        store = self.app.store()
        try:
            failures = store.export_intake_failures(Actor('local-user', 'test-reader'))
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]['failure_id'], payload['failure_id'])
        finally:
            store.close()

    def test_create_list_export_and_no_synthetic_cast_time(self):
        case_id = self.create()
        self.assertEqual(self.request('GET', '/api/cases')[2]['cases'][0]['case_id'], case_id)
        status, headers, exported = self.request('GET', '/api/cases/' + case_id + '/export')
        self.assertEqual(status, 200)
        self.assertIn('attachment;', headers['Content-Disposition'])
        self.assertEqual(exported['owner_id'], 'local-user')
        self.assertEqual(exported['original_input'], INPUT)
        self.assertIsNone(exported['revisions'][0]['time_context']['actual_cast_time'])
        self.assertFalse(exported['usage_policy']['training_use'])

    def test_diagnostics_export_is_minimal_and_excludes_private_content(self):
        case_id = self.create()
        actor = Actor('local-user', 'diagnostics-test')
        private_background = '私密背景：与某个人的未公开约定'
        raw_output = '模型原始正文与敏感回答'
        prompt = '不可分享的完整系统提示词'
        key = 'offline-test-key'
        store = self.app.store()
        try:
            store.append_context_event(actor, case_id, event_type='background', content={'text':private_background}, idempotency_key='diagnostic-background')
            run = store.start_analysis(actor, case_id, source_hash='1'*64, rules_digest='2'*64,
                prompt_digest='3'*64, engine_build='diagnostic-fixture', expected_revision_seq=1, idempotency_key='diagnostic-run')
            run_id = run['analysis_run_id']
            store.add_ai_event(actor, case_id, run_id, stage='interpretation', attempt_id='interpretation_2',
                raw_output=raw_output, parse_status='parsed',
                validation_errors=[{'code':'CONTRACT_INVALID', 'message':"claims: nonexistent refs ['" + INPUT['question'] + "', '" + private_background + "']"}],
                model_run_metadata={'provider':'deepseek','model':'deepseek-chat','attempt_number':2,'finish_reason':'stop',
                    'system_prompt':prompt,'stage_input':{'question':INPUT['question'],'background':private_background},'api_key':key},
                idempotency_key='diagnostic-attempt')
            store.finish_analysis(actor, case_id, run_id, status='failed', error={'code':'CONTRACT_INVALID','message':raw_output}, idempotency_key='diagnostic-finish')
        finally:
            store.close()
        status, headers, payload = self.request('GET', '/api/cases/' + case_id + '/diagnostics')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Disposition'], 'attachment; filename="case_diagnostics.json"')
        self.assertEqual(payload['format'], 'liuyao_case_diagnostics')
        self.assertEqual(payload['analysis_runs'][0]['analysis_run_id'], run_id)
        self.assertEqual(payload['analysis_runs'][0]['status'], 'failed')
        attempt = payload['analysis_runs'][0]['attempts'][0]
        self.assertEqual(attempt['stage'], 'interpretation')
        self.assertEqual(attempt['attempt_number'], 2)
        self.assertEqual(attempt['parse_status'], 'parsed')
        self.assertEqual(attempt['model_metadata'], {'provider':'deepseek','model':'deepseek-chat','finish_reason':'stop'})
        self.assertEqual(attempt['validation_errors'][0]['message'], 'nonexistent refs')
        encoded = json.dumps(payload, ensure_ascii=False)
        for private in (INPUT['question'], private_background, raw_output, prompt, key,
                        'raw_output', 'stage_input', 'system_prompt', 'api_key', 'owner_id', 'session_id'):
            self.assertNotIn(private, encoded)

    def test_diagnostics_owner_and_session_are_enforced(self):
        case_id = self.create()
        path = '/api/cases/' + case_id + '/diagnostics'
        self.assertEqual(self.request('GET', path, cookie=False)[0], 401)
        self.app.sessions['different-owner-token'] = Actor('another-user', 'foreign-session')
        self.assertEqual(self.request('GET', path, headers={'Cookie':'liuyao_session=different-owner-token'})[0], 404)
        self.assertEqual(self.request('GET', '/api/cases/missing/diagnostics')[0], 404)
        self.assertEqual(self.request('GET', path, headers={'Origin':'https://evil.example'})[0], 403)

    def test_raw_ai_replies_show_only_selected_run_and_allowed_fields(self):
        case_id = self.create()
        actor = Actor('local-user', 'raw-reply-test')
        store = self.app.store()
        run_ids = []
        try:
            for number in (1, 2):
                run = store.start_analysis(actor, case_id, source_hash='1'*64, rules_digest='2'*64,
                    prompt_digest='3'*64, engine_build='raw-fixture', expected_revision_seq=1, idempotency_key=f'raw-run-{number}')
                run_id = run['analysis_run_id']; run_ids.append(run_id)
                errors = [{'code':'CONTRACT_INVALID','message':'ready selection needs a primary candidate and no blocking issue'}] if number == 1 else []
                store.add_ai_event(actor, case_id, run_id, stage='selection', attempt_id=f'selection_{number}',
                    raw_output=f'<script>private-reply-{number}</script>', parse_status='parsed', validation_errors=errors,
                    adopted_output={'accepted':True} if number == 2 else None,
                    model_run_metadata={'attempt_number':number,'normalization_changes':['status changed'] if number == 2 else [],
                        'stage_input':{'question':'private-input'},'system_prompt':'private-prompt','api_key':'sk-test-secret'},
                    idempotency_key=f'raw-attempt-{number}')
                store.finish_analysis(actor, case_id, run_id, status='failed' if errors else 'completed',
                    error=errors[0] if errors else None, report={'summary':'accepted fixture'} if not errors else None,
                    idempotency_key=f'raw-finish-{number}')
        finally:
            store.close()
        path = f'/api/cases/{case_id}/ai-attempts'
        status, _, result = self.request('GET', path+'?run_id='+run_ids[0])
        self.assertEqual(status, 200)
        self.assertEqual([run['analysis_run_id'] for run in result['analysis_runs']], run_ids[:1])
        attempt = result['analysis_runs'][0]['attempts'][0]
        self.assertEqual(attempt['raw_output'], '<script>private-reply-1</script>')
        self.assertEqual(attempt['validation_errors'][0]['message'], 'ready selection needs a primary candidate and no blocking issue')
        self.assertFalse(attempt['adopted'])
        self.assertEqual(set(attempt), {'stage','attempt_number','raw_output','validation_errors','adopted','normalization_changes','http_status','elapsed_ms'})
        encoded = json.dumps(result)
        for secret in ('private-input','private-prompt','sk-test-secret','stage_input','system_prompt','api_key','owner_id','session_id'):
            self.assertNotIn(secret, encoded)
        all_runs = self.request('GET', path)[2]['analysis_runs']
        self.assertEqual(len(all_runs), 2)
        self.assertTrue(all_runs[1]['attempts'][0]['adopted'])
        self.assertEqual(all_runs[1]['attempts'][0]['normalization_changes'], ['status changed'])
        self.assertEqual(self.request('GET', path+'?run_id=other-case-run')[0], 404)
        self.assertEqual(self.request('GET', path+'?run_id=')[0], 400)
        self.assertEqual(self.request('GET', path+'?run_id=a&run_id=b')[0], 400)
        self.assertEqual(self.request('GET', path+'?unrecognized=1')[0], 400)

    def test_raw_ai_replies_require_owner_and_session(self):
        case_id = self.create()
        path = f'/api/cases/{case_id}/ai-attempts'
        self.assertEqual(self.request('GET', path, cookie=False)[0], 401)
        self.app.sessions['another-raw-owner'] = Actor('another-user', 'foreign-session')
        self.assertEqual(self.request('GET', path, headers={'Cookie':'liuyao_session=another-raw-owner'})[0], 404)
        self.assertEqual(self.request('GET', path, headers={'Origin':'https://evil.example'})[0], 403)
        self.assertEqual(self.request('GET', '/api/cases/missing/ai-attempts')[0], 404)

    def test_config_displays_real_storage_paths_without_configuration_contents(self):
        self.catalog_patch.stop()
        override = Path(self.temp.name) / 'custom-home'
        override.mkdir()
        (override / '.env').write_text('DEEPSEEK_API_KEY=offline-test-key\n')
        with patch.dict(os.environ, {'LIUYAO_HOME':str(override)}):
            status, _, result = self.request('GET', '/api/config')
        self.assertEqual(status, 200)
        self.assertEqual(result['storage_paths'], {'data_directory':str(Path(self.temp.name).resolve()),
            'configuration_file':str((override / '.env').resolve())})
        self.assertNotIn('offline-test-key', json.dumps(result))
        self.assertEqual(self.request('GET', '/api/config', cookie=False)[0], 401)

    def test_casting_only_meibu_three_movement_routes(self):
        fixtures = [
            ('circle', ['old_yang'] * 3 + ['old_yin'] * 3, [1, 2, 3, 4, 5, 6]),
            ('square', ['young_yang'] * 3 + ['young_yin'] * 3, []),
            ('4', ['young_yang'] * 3 + ['old_yin', 'young_yin', 'young_yin'], [4]),
        ]
        for third, lines, moving in fixtures:
            with self.subTest(third=third):
                submitted = {'question': '枚卜输入路径检查', 'casting': {
                    'method': 'meibu', 'results': ['circle', 'square', third]}}
                status, _, created = self.request('POST', '/api/cases', {'input': submitted})
                self.assertEqual(status, 201, created)
                self.assertEqual(created['chart']['input_lines'], lines)
                self.assertEqual(created['chart']['moving_positions'], moving)
                exported = self.request('GET', '/api/cases/' + created['case_id'] + '/export')[2]
                expected = {**submitted, 'lines': lines}
                self.assertEqual(exported['original_input'], expected)
                self.assertEqual(exported['revisions'][0]['input'], expected)

    def test_taiji_permutations_retained_in_export_and_snapshot(self):
        submitted = {'question': '太极排列保留检查', 'actual_cast_time': '2026-09-17T18:42:00+08:00',
                     'casting': {'method': 'taiji', 'results': ['322', '232', '332', '323', '222', '333']}}
        lines = ['young_yang', 'young_yang', 'young_yin', 'young_yin', 'old_yin', 'old_yang']
        status, _, created = self.request('POST', '/api/cases', {'input': submitted})
        self.assertEqual(status, 201, created)
        self.assertEqual(created['chart']['input_lines'], lines)
        self.assertEqual(created['chart']['moving_positions'], [5, 6])
        self.wait_job(self.analyze(created['case_id'])[2]['job_id'])
        exported = self.request('GET', '/api/cases/' + created['case_id'] + '/export')[2]
        expected = {**submitted, 'lines': lines}
        self.assertEqual(exported['original_input'], expected)
        self.assertEqual(exported['revisions'][0]['input'], expected)
        self.assertEqual(exported['analysis_runs'][0]['input_snapshot']['input'], expected)
        self.assertNotIn('spatial_order', exported['original_input']['casting'])

    def test_matching_casting_and_lines_accepted_but_conflict_is_retained(self):
        matching = {'question': '核对两个输入', 'casting': {
            'method': 'meibu', 'results': ['circle', 'square', 'square']},
            'lines': ['young_yang'] * 3 + ['young_yin'] * 3}
        self.assertEqual(self.request('POST', '/api/cases', {'input': matching})[0], 201)
        conflicting = copy.deepcopy(matching)
        conflicting['lines'][0] = 'old_yang'
        status, _, result = self.request('POST', '/api/cases', {'input': conflicting})
        self.assertEqual(status, 422, result)
        self.assertIn('CASTING_LINES_MISMATCH', [e['code'] for e in result['error']['details']])
        self.assertEqual(len(self.request('GET', '/api/cases')[2]['cases']), 1)
        store = self.app.store()
        try:
            failure = store.export_intake_failures(Actor('local-user', 'test-reader'))[0]
            self.assertEqual(failure['failure_id'], result['failure_id'])
            self.assertEqual(failure['related_input'], conflicting)
        finally:
            store.close()

    def test_malformed_casting_does_not_create_case(self):
        fixtures = [
            {'method': 'meibu', 'results': ['circle', 'square']},
            {'method': 'meibu', 'results': ['circle', 'square', 1]},
            {'method': 'taiji', 'results': ['222'] * 5},
            {'method': 'taiji', 'results': ['222'] * 5 + ['234']},
            {'method': 'taiji', 'results': ['222'] * 6, 'spatial_order': [1, 2, 3]},
            {'method': 'direct', 'results': ['222'] * 6},
        ]
        for casting in fixtures:
            with self.subTest(casting=casting):
                status, _, payload = self.request('POST', '/api/cases', {
                    'input': {'question': '无效起卦格式', 'casting': casting}})
                self.assertEqual(status, 422, payload)
        self.assertEqual(self.request('GET', '/api/cases')[2]['cases'], [])

    def test_raw_casting_idempotency_does_not_erase_permutation_changes(self):
        submitted = {'question': '重复提交检查', 'casting': {'method': 'taiji', 'results': ['322'] * 6}}
        headers = {'X-Idempotency-Key': 'raw-casting-retry'}
        first = self.request('POST', '/api/cases', {'input': submitted}, headers=headers)
        second = self.request('POST', '/api/cases', {'input': submitted}, headers=headers)
        self.assertEqual(first[0], 201)
        self.assertEqual(first[2]['case_id'], second[2]['case_id'])
        changed = copy.deepcopy(submitted)
        changed['casting']['results'][0] = '232'
        self.assertEqual(self.request('POST', '/api/cases', {'input': changed}, headers=headers)[0], 409)
        exported = self.request('GET', '/api/cases/' + first[2]['case_id'] + '/export')[2]
        self.assertEqual(exported['original_input']['casting']['results'][0], '322')

    def test_create_idempotency_and_changed_payload_conflict(self):
        headers = {'X-Idempotency-Key': 'create-twice'}
        case_id = self.create(headers=headers)
        self.assertEqual(case_id, self.create(headers=headers))
        changed = copy.deepcopy(INPUT); changed['question'] = '另一个问题'
        self.assertEqual(self.request('POST', '/api/cases', {'input': changed}, headers=headers)[0], 409)
        self.assertEqual(len(self.request('GET', '/api/cases')[2]['cases']), 1)

    def test_missing_records_and_static_allowlist(self):
        for path in ['/api/cases/missing', '/api/jobs/missing', '/.env', '/server.py', '/../server.py']:
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)

    def test_same_local_workspace_across_fresh_sessions(self):
        case_id = self.create()
        _, headers, _ = self.request('GET', '/')
        fresh_cookie = headers['Set-Cookie'].split(';')[0]
        self.assertNotEqual(fresh_cookie, self.cookie)
        self.assertEqual(self.request('GET', '/api/cases/' + case_id, headers={'Cookie': fresh_cookie})[0], 200)

    def test_analysis_idempotency_and_progress_field_allowlist(self):
        case_id = self.create()
        self.release.clear()
        first = self.analyze(case_id, key='same-analysis')
        self.assertEqual(first[0], 202)
        self.assertTrue(self.entered.wait(3))
        second = self.analyze(case_id, key='same-analysis')
        self.assertEqual(first[2], second[2])
        state = self.request('GET', '/api/jobs/' + first[2]['job_id'])[2]
        self.assertNotIn('secret', state)
        self.assertEqual(len(self.calls), 1)
        self.release.set()
        self.assertEqual(self.wait_job(first[2]['job_id'])['status'], 'completed')
        self.assertEqual(self.analyze(case_id, key='same-analysis')[2], first[2])
        self.assertEqual(len(self.calls), 1)

    def test_job_key_cannot_be_reused_for_different_request(self):
        first, second = self.create(), self.create()
        job = self.analyze(first, key='job-key')[2]['job_id']
        self.wait_job(job)
        self.assertEqual(self.analyze(second, key='job-key')[0], 409)

    def test_analysis_blocks_revision_context_and_duplicate_job(self):
        case_id = self.create()
        self.release.clear()
        job = self.analyze(case_id)[2]['job_id']
        self.assertTrue(self.entered.wait(3))
        self.assertEqual(self.analyze(case_id)[0], 409)
        self.assertEqual(self.request('POST', '/api/cases/' + case_id + '/context', {'text': '补充'})[0], 409)
        self.assertEqual(self.request('POST', '/api/cases/' + case_id + '/revisions',
            {'input': INPUT, 'reason': '更正', 'expected_revision_seq': 1})[0], 409)
        self.assertEqual(self.request('GET', '/api/cases/' + case_id)[2]['active_job_id'], job)
        self.release.set()
        self.wait_job(job)

    def test_concurrent_job_limit(self):
        cases = [self.create() for _ in range(3)]
        self.release.clear()
        for case_id in cases[:2]:
            self.assertEqual(self.analyze(case_id)[0], 202)
        self.assertEqual(self.analyze(cases[2])[0], 429)

    def test_revision_precondition_and_provider_model_allowlist(self):
        case_id = self.create()
        self.assertEqual(self.analyze(case_id, revision=2)[0], 409)
        for provider, model, code in [('unknown', 'test-model', 'UNKNOWN_MODEL'),
                                     ('deepseek', 'arbitrary-model', 'UNKNOWN_MODEL'),
                                     ('doubao', 'other-model', 'PROVIDER_NOT_CONFIGURED')]:
            with self.subTest(provider=provider, model=model):
                status, _, payload = self.request('POST', '/api/cases/' + case_id + '/analyze',
                    {'provider': provider, 'model': model, 'expected_revision_seq': 1})
                self.assertEqual(status, 400)
                self.assertEqual(payload['error']['code'], code)
        self.assertEqual(self.calls, [])

    def test_revision_and_feedback_preserve_old_report(self):
        case_id = self.create()
        finished = self.wait_job(self.analyze(case_id)[2]['job_id'])
        before = self.request('GET', '/api/cases/' + case_id)[2]
        self.assertTrue(before['report_is_current'])
        changed = copy.deepcopy(INPUT); changed['question'] = '更正后的问题'
        body = {'input': changed, 'reason': '澄清目标', 'expected_revision_seq': 1}
        status, _, _ = self.request('POST', '/api/cases/' + case_id + '/revisions', body)
        self.assertEqual(status, 201)
        self.assertEqual(self.request('POST', '/api/cases/' + case_id + '/revisions', body)[0], 409)
        feedback = {'text': '事情后来有了变化', 'analysis_run_id': finished['analysis_run_id'], 'occurred_at': '2026-09-17T12:00:00+08:00'}
        self.assertEqual(self.request('POST', '/api/cases/' + case_id + '/feedback', feedback)[0], 201)
        after = self.request('GET', '/api/cases/' + case_id)[2]
        self.assertEqual(len(after['case']['revisions']), 2)
        self.assertEqual(after['case']['original_input'], INPUT)
        self.assertEqual(after['result'], before['result'])
        self.assertEqual(after['case']['analysis_runs'][0], before['case']['analysis_runs'][0])
        self.assertFalse(after['report_is_current'])
        self.assertEqual(len(after['case']['feedback']), 1)
        self.assertEqual(after['case']['feedback'][0]['verification_status'], 'self_reported')

    def test_context_changes_stale_report_and_is_retained(self):
        case_id = self.create()
        self.wait_job(self.analyze(case_id)[2]['job_id'])
        headers = {'X-Idempotency-Key': 'context-once'}
        for _ in range(2):
            self.assertEqual(self.request('POST', '/api/cases/' + case_id + '/context', {'text': '真实关切是出行'}, headers=headers)[0], 201)
        detail = self.request('GET', '/api/cases/' + case_id)[2]
        self.assertFalse(detail['report_is_current'])
        self.assertEqual(len(detail['case']['context_events']), 1)
        self.assertEqual(detail['case']['analysis_runs'][0]['input_snapshot']['context_events'], [])

    def test_feedback_cannot_claim_external_verification_or_cross_case_run(self):
        first, second = self.create(), self.create()
        finished = self.wait_job(self.analyze(first)[2]['job_id'])
        self.assertEqual(self.request('POST', '/api/cases/' + second + '/feedback',
            {'text': '反馈', 'analysis_run_id': finished['analysis_run_id']})[0], 404)
        self.assertEqual(self.request('POST', '/api/cases/' + first + '/feedback',
            {'text': '反馈', 'verification_status': 'externally_supported'})[0], 400)
        self.assertEqual(self.request('POST', '/api/cases/' + first + '/feedback',
            {'text': '反馈', 'occurred_at': 'not-a-timestamp'})[0], 400)

    def test_feedback_analysis_id_rejects_nontext_values(self):
        case_id = self.create()
        for value in [[], {}, 42, True, ['analysis_forged'], '', '   ']:
            with self.subTest(value=value):
                status, _, payload = self.request('POST', '/api/cases/' + case_id + '/feedback',
                    {'text': '反馈', 'analysis_run_id': value})
                self.assertEqual(status, 400, payload)

    def test_no_report_is_not_marked_current(self):
        case_id = self.create()
        self.release.clear()
        job = self.analyze(case_id)[2]['job_id']
        self.assertTrue(self.entered.wait(3))
        detail = self.request('GET', '/api/cases/' + case_id)[2]
        self.assertIsNone(detail['result'])
        self.assertFalse(detail['report_is_current'])
        self.release.set()
        self.wait_job(job)

    def test_pipeline_exception_not_exposed_to_client(self):
        def failing(*args, **kwargs):
            raise RuntimeError('secret-provider-key')
        self.app.pipeline = failing
        case_id = self.create()
        result = self.wait_job(self.analyze(case_id)[2]['job_id'])
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('secret-provider-key', json.dumps(result))

    def test_worker_failure_finalizes_already_started_analysis(self):
        def interrupted(db_path, actor, case_id, provider, model, revision, progress):
            store = CaseStore(db_path)
            try:
                started = store.start_analysis(actor, case_id, source_hash='1' * 64,
                    rules_digest='2' * 64, prompt_digest='3' * 64, engine_build='http-fixture',
                    expected_revision_seq=revision, idempotency_key='fail-started-run')
                progress({'analysis_run_id': started['analysis_run_id'], 'stage': 'fixture'})
            finally:
                store.close()
            raise RuntimeError('private-runtime-details')
        self.app.pipeline = interrupted
        case_id = self.create()
        result = self.wait_job(self.analyze(case_id)[2]['job_id'])
        self.assertEqual(result['status'], 'failed')
        detail = self.request('GET', '/api/cases/' + case_id)[2]
        self.assertEqual(detail['case']['analysis_runs'][0]['status'], 'failed')
        self.assertIsNone(detail['active_job_id'])
        self.assertNotIn('private-runtime-details', json.dumps(detail))

    def test_restart_marks_interrupted_job_and_run_failed_without_replay(self):
        case_id = self.create()
        actor = Actor('local-user', 'recovery-test')
        store = self.app.store()
        try:
            started = store.start_analysis(actor, case_id, source_hash='1' * 64,
                rules_digest='2' * 64, prompt_digest='3' * 64, engine_build='fixture',
                expected_revision_seq=1, idempotency_key='interrupted-run')
        finally:
            store.close()
        state = {'job_id': 'job_interrupted', 'case_id': case_id, 'status': 'running',
                 'stage': 'provider', 'analysis_run_id': started['analysis_run_id'], 'result': None, 'error': None}
        with self.app.jobs_db() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)',
                ('job_interrupted', actor.owner_id, case_id, 'interrupted-key', 'digest', '{}', json.dumps(state), 'old', 'old'))
        # Close this instance before opening another; production directory locking
        # deliberately forbids two services operating the same data directory.
        self.app.close()
        restarted = Application(self.temp.name, pipeline=self.fake_pipeline)
        try:
            job = restarted.get_job(actor, 'job_interrupted')
            self.assertEqual(job['status'], 'failed')
            self.assertEqual(job['error']['code'], 'INTERRUPTED')
            retained = restarted.case_detail(actor, case_id)['case']['analysis_runs'][0]
            self.assertEqual(retained['status'], 'failed')
            self.assertEqual(retained['outcome']['result']['error']['code'], 'INTERRUPTED')
            self.assertEqual(self.calls, [])
            restarted.recover()
            self.assertEqual(restarted.case_detail(actor, case_id)['case']['analysis_runs'][0], retained)
        finally:
            restarted.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
