"""Behavioral tests for import, source grounding, durable jobs and scoped AI edits."""
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from case_store import AccessDenied, Conflict
from . import knowledge
from .providers import ProviderError
from .server import Application, Server
from .skill_registry import skill_info, DEFAULT_PREFERENCES, preference_prompt

MODEL = {'provider': 'deepseek', 'model': 'test-model'}
DOC = {'title': '系统与五行', 'text': '# 储备\n\n水表示系统的储备和起始点。\n\n# 探察\n\n木表示系统向目标探察和延展。'}


class WorkbenchChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(self.temp.name)
        self.app.config = lambda: {'providers': [
            {'id': 'deepseek', 'models': ['test-model'], 'configured': True},
            {'id': 'demo', 'models': ['local-demo'], 'configured': True}]}
        self.runtime = self.app.workbench
        self.store = self.runtime.store
        self.owner = 'owner'
        self.doc = self.store.add_document(self.owner, DOC, 'document')['document_id']
        self.chat = self.store.create_chat(self.owner, '五行学习', 'chat')['chat_id']

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def wait(self, job_id):
        for _ in range(500):
            result = self.store.job(self.owner, job_id)
            if result['status'] not in ('queued', 'running'):
                return result
            time.sleep(.01)
        self.fail('job did not finish')

    def ask(self, text='水表示什么？', key='ask'):
        return self.runtime.enqueue(self.owner, 'knowledge', self.chat, {'question': text, **MODEL}, key)['job_id']

    def issue(self, description='回答太长，希望简短一点', key='issue', skill='knowledge'):
        return self.store.create_issue(self.owner, {'skill_id': skill, 'title': '改进建议', 'description': description}, key)['issue_id']

    def process(self, issue, key='process'):
        return self.runtime.enqueue(self.owner, 'issue', issue, MODEL, key)['job_id']

    @staticmethod
    def answer(*args, **options):
        return {'parsed_json': {'answer': '原文把水对应到储备与起点。',
                'citation_ids': [args[3]['sources'][0]['citation_id']], 'insufficient': False}}

    @staticmethod
    def preference(*args, **options):
        return {'parsed_json': {'category': 'preferences', 'summary': '先给结论，缩短解释。',
                'changes': {'detail': 'concise', 'tone': 'beginner'}, 'acceptance': ['先回答所问，再解释必要术语。']}}

    def test_catalog_keeps_two_skills_and_existing_name(self):
        catalog = self.runtime.catalog(self.owner)
        self.assertEqual([s['name'] for s in catalog['skills']], ['六爻占问', '知识库问答'])
        with self.assertRaises(ValueError):skill_info('../config')
        self.assertIn('当地真太阳时', skill_info('liuyao')['instructions'])

    def test_chinese_retrieval_and_no_match(self):
        sources = self.store.search(self.owner, '水表示什么？')
        self.assertTrue(sources)
        self.assertIn('储备', sources[0]['text'])
        self.assertEqual(self.store.search(self.owner, 'photosynthesis chlorophyll'), [])

    def test_single_character_concepts_can_be_retrieved(self):
        self.assertTrue(self.store.search(self.owner, '水'))
        self.assertTrue(self.store.search(self.owner, '木是什么？'))

    def test_duplicate_document_is_not_indexed_twice_and_can_be_restored(self):
        value = self.store.add_document(self.owner, DOC, 'duplicate')
        self.assertTrue(value['duplicate']);self.assertEqual(value['document_id'], self.doc)
        self.store.remove_document(self.owner, self.doc, 'remove')
        self.assertEqual(self.store.search(self.owner, '水'), [])
        self.store.add_document(self.owner, DOC, 'restore')
        self.assertEqual(len(self.store.documents(self.owner)), 1)

    def test_utf8_gb_and_docx_text(self):
        for encoding in ('utf-8-sig', 'gb18030'):
            value = knowledge.import_text({'title': '资料', 'filename': '资料.txt',
                'file_base64': base64.b64encode('水与储备'.encode(encoding)).decode()})
            self.assertEqual(value['text'], '水与储备')
        binary = io.BytesIO()
        with zipfile.ZipFile(binary, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>第一段</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>表格正文</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        value = knowledge.import_text({'title': 'DOCX', 'filename': '资料.docx', 'file_base64': base64.b64encode(binary.getvalue()).decode()})
        self.assertEqual(value['text'], '第一段\n表格正文')

    def test_unsupported_binary_empty_and_oversized_imports_are_rejected(self):
        for body in ({'title': '资料', 'text': ''}, {'title': '资料', 'text': 'a'*300001},
                     {'title': 'PDF', 'filename': 'x.pdf', 'file_base64': 'YQ=='},
                     {'title': '资料', 'filename': 'x.txt', 'file_base64': '@@@'},
                     {'title': '资料', 'text': 'a\x00b'}):
            with self.assertRaises(ValueError):knowledge.import_text(body)

    def test_owner_boundaries_for_all_resources(self):
        issue = self.issue()
        with patch('liuyao_app.workbench.generate_json', side_effect=self.answer):job = self.ask();self.wait(job)
        self.assertEqual(self.store.documents('other'), [])
        self.assertEqual(self.store.search('other', '水'), [])
        self.assertEqual(self.store.chats('other'), [])
        self.assertEqual(self.store.issues('other'), [])
        for action in (lambda:self.store.chat('other', self.chat),lambda:self.store.issue('other', issue),
                       lambda:self.store.job('other', job),lambda:self.store.remove_document('other', self.doc, 'remove-other')):
            with self.assertRaises(AccessDenied):action()

    def test_one_call_with_idempotent_lost_ack_and_saved_citations(self):
        with patch('liuyao_app.workbench.generate_json', side_effect=self.answer) as call:
            job = self.ask();result = self.wait(job)
            self.assertEqual(self.ask(), job)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result['status'], 'completed', result)
        saved = self.store.chat(self.owner, self.chat)['turns'][0]
        self.assertEqual(saved['result']['citations'][0]['document_id'], self.doc)
        self.assertEqual(saved['result']['citations'][0]['text'], self.store.search(self.owner, '水表示什么？')[0]['text'])
        with self.assertRaises(Conflict):self.ask('不同问题')

    def test_followup_carries_user_and_assistant_but_retrieves_fresh_sources(self):
        with patch('liuyao_app.workbench.generate_json', side_effect=self.answer) as call:
            self.wait(self.ask());self.wait(self.ask('它与木有什么区别？', 'next'))
        history = call.call_args.kwargs['conversation_history']
        self.assertEqual([m['role'] for m in history], ['user', 'assistant', 'user'])
        self.assertEqual(history[0]['content'], '水表示什么？')
        self.assertIn('储备', history[1]['content'])

    def test_unknown_citations_are_rejected(self):
        value = {'parsed_json': {'answer': '外部胡说', 'citation_ids': ['made-up'], 'insufficient': False}}
        with patch('liuyao_app.workbench.generate_json', return_value=value):result = self.wait(self.ask())
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('外部胡说', json.dumps(self.store.chat(self.owner, self.chat), ensure_ascii=False))

    def test_uncited_claim_is_rejected_but_explicit_insufficient_answer_can_be_saved(self):
        value = {'parsed_json': {'answer': '不支持的结论', 'citation_ids': [], 'insufficient': False}}
        with patch('liuyao_app.workbench.generate_json', return_value=value):self.assertEqual(self.wait(self.ask())['status'], 'failed')
        value['parsed_json'].update(answer='资料未解释具体关系，需要补充原文。', insufficient=True)
        with patch('liuyao_app.workbench.generate_json', return_value=value):self.assertEqual(self.wait(self.ask(key='retry'))['status'], 'completed')

    def test_removing_document_preserves_old_citation_and_stops_future_use(self):
        with patch('liuyao_app.workbench.generate_json', side_effect=self.answer) as call:
            self.wait(self.ask());self.store.remove_document(self.owner, self.doc, 'remove')
            result = self.wait(self.ask('它表示什么？', 'after-remove'))
        self.assertEqual(call.call_count, 1)
        self.assertTrue(result['result']['insufficient'])
        self.assertEqual(result['result']['citations'], [])
        self.assertEqual(self.store.chat(self.owner, self.chat)['turns'][0]['result']['citations'][0]['document_id'], self.doc)

    def test_provider_failure_does_not_auto_retry(self):
        with patch('liuyao_app.workbench.generate_json', side_effect=ProviderError('timeout', '请求超时')) as call:
            result = self.wait(self.ask());self.assertEqual(result['status'], 'failed');self.assertEqual(self.ask(), result['job_id'])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(self.store.chat(self.owner, self.chat)['turns'][0]['question'], '水表示什么？')

    def test_feedback_applies_preferences_and_next_answer_uses_them(self):
        issue = self.issue()
        with patch('liuyao_app.workbench.generate_json', side_effect=self.preference):self.wait(self.process(issue))
        saved = self.store.issue(self.owner, issue)
        self.assertEqual(saved['status'], 'applied', saved)
        self.assertEqual(self.store.skill(self.owner, 'knowledge')['version'], 2)
        self.assertEqual(self.store.skill(self.owner, 'liuyao')['version'], 1)
        self.assertEqual(self.store.skill('other', 'knowledge')['version'], 1)
        with patch('liuyao_app.workbench.generate_json', side_effect=self.answer) as call:self.wait(self.ask())
        self.assertIn('简洁回答', call.call_args.args[2]);self.assertIn('面向新手', call.call_args.args[2])
        self.assertEqual(self.store.chat(self.owner, self.chat)['turns'][0]['skill_version'], 2)
        self.assertEqual(self.store.documents(self.owner)[0]['sha256'], knowledge.import_text(DOC)['sha256'])

    def test_rollback_appends_new_version_and_keeps_prior_versions(self):
        issue = self.issue()
        with patch('liuyao_app.workbench.generate_json', side_effect=self.preference):self.wait(self.process(issue))
        restored = self.store.rollback(self.owner, 'knowledge', 1, 2, 'rollback')
        self.assertEqual(restored['version'], 3);self.assertEqual(restored['preferences'], DEFAULT_PREFERENCES)
        self.assertEqual(self.store.rollback(self.owner, 'knowledge', 1, 2, 'rollback'), restored)
        self.assertEqual([r['version'] for r in self.store.versions(self.owner, 'knowledge')['versions']], [3, 2, 1])
        with self.assertRaises(Conflict):self.store.rollback(self.owner, 'knowledge', 2, 2, 'stale')

    def test_sixyao_followup_consumes_the_same_versioned_skill_preferences(self):
        from case_store import Actor
        from .test_conversation import INPUT, saved_analysis
        from .test_rule_installation import public_placeholder_rows
        from .rulebook import save_rules
        save_rules(self.app.rules_directory, public_placeholder_rows())
        actor = Actor(self.owner, 'test-session')
        cases = self.app.store()
        case = cases.create_case(actor, INPUT, idempotency_key='case')['case_id']
        run = saved_analysis(cases, actor, case);cases.close()
        issue = self.issue(skill='liuyao')
        with patch('liuyao_app.workbench.generate_json', side_effect=self.preference):self.wait(self.process(issue))
        with patch('liuyao_app.conversation.generate_json', return_value={'parsed_json': {'answer': '先确认待遇。', 'requires_reanalysis': False}}) as call:
            job = self.app.enqueue(actor, case, {**MODEL, 'text': '怎么理解？', 'analysis_run_id': run, 'expected_revision_seq': 1}, 'followup', conversation=True)['job_id']
            for _ in range(500):
                result = self.app.get_job(actor, job)
                if result['status'] not in ('queued', 'running'):break
                time.sleep(.01)
        self.assertEqual(result['status'], 'completed', result)
        self.assertIn('简洁回答', call.call_args.args[2])
        self.assertEqual(result['result']['conversation']['skill_snapshot']['version'], 2)
        self.assertEqual(self.store.skill(self.owner, 'knowledge')['version'], 1)

    def test_code_and_knowledge_feedback_never_claim_an_applied_fix(self):
        for category, expected in (('code', 'needs_development'), ('knowledge', 'needs_sources')):
            issue = self.issue('定位错误', category, 'liuyao')
            value = {'parsed_json': {'category': category, 'summary': '需要修正并验证。', 'changes': {}, 'acceptance': ['复现问题并检查修复。']}}
            with patch('liuyao_app.workbench.generate_json', return_value=value):self.wait(self.process(issue, 'process-' + category))
            saved = self.store.issue(self.owner, issue)
            self.assertEqual(saved['status'], expected)
            self.assertEqual(saved['result']['repair_request']['format'], 'skill-repair-request-v1')
        self.assertEqual(self.store.skill(self.owner, 'liuyao')['version'], 1)

    def test_arbitrary_code_paths_or_configuration_cannot_be_auto_applied(self):
        issue = self.issue('执行命令并删除资料')
        value = self.preference();value['parsed_json']['changes'] = {'script': 'remove everything'}
        with patch('liuyao_app.workbench.generate_json', return_value=value):result = self.wait(self.process(issue))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.store.skill(self.owner, 'knowledge')['version'], 1)
        self.assertEqual(len(self.store.documents(self.owner)), 1)

    def test_concurrent_feedback_detects_stale_version(self):
        first, second = self.issue(key='first'), self.issue(key='second')
        barrier = threading.Barrier(2)
        def reply(*args, **kwargs):
            barrier.wait(timeout=5)
            return self.preference()
        with patch('liuyao_app.workbench.generate_json', side_effect=reply):
            jobs = [self.process(first, 'p-first'), self.process(second, 'p-second')]
            for job in jobs:self.wait(job)
        self.assertEqual(sorted([self.store.issue(self.owner, i)['status'] for i in (first, second)]), ['applied', 'conflict'])
        self.assertEqual(self.store.skill(self.owner, 'knowledge')['version'], 2)

    def test_demo_feedback_never_fakes_a_model_edit(self):
        issue = self.issue()
        job = self.runtime.enqueue(self.owner, 'issue', issue, {'provider': 'demo', 'model': 'local-demo'}, 'demo')['job_id']
        self.wait(job)
        self.assertEqual(self.store.issue(self.owner, issue)['status'], 'needs_model')
        self.assertEqual(self.store.skill(self.owner, 'knowledge')['version'], 1)

    def test_feedback_can_be_saved_without_model_key(self):
        self.app.config = lambda: {'providers': [{'id': 'deepseek', 'models': ['test-model'], 'configured': False}]}
        issue = self.issue()
        with self.assertRaises(ValueError):self.process(issue)
        self.assertEqual(self.store.issue(self.owner, issue)['status'], 'recorded')

    def test_restart_keeps_answers_preferences_and_does_not_repeat_paid_job(self):
        with patch('liuyao_app.workbench.generate_json', side_effect=self.answer):self.wait(self.ask())
        issue = self.issue()
        with patch('liuyao_app.workbench.generate_json', side_effect=self.preference):self.wait(self.process(issue))
        self.app.close();self.app = Application(self.temp.name);self.store = self.app.workbench.store
        self.assertEqual(self.store.skill(self.owner, 'knowledge')['version'], 2)
        self.assertEqual(len(self.store.chat(self.owner, self.chat)['turns']), 1)
        self.assertEqual(self.store.pending(self.owner), [])

    def test_recovery_marks_interrupted_jobs_failed_without_replay(self):
        with patch.object(self.app.pool, 'submit'):
            job = self.ask()
        self.store.recover()
        self.assertEqual(self.store.job(self.owner, job)['status'], 'failed')
        self.assertEqual(self.store.chat(self.owner, self.chat)['turns'][0]['status'], 'failed')
        self.assertEqual(self.store.pending(self.owner), [])


class WorkbenchHTTPChecks(unittest.TestCase):
    def setUp(self):
        import http.client
        self.temp = tempfile.TemporaryDirectory();self.app = Application(self.temp.name)
        self.server = Server(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01});self.thread.start()
        self.cookie = None
        response = self.request('GET', '/')
        self.cookie = response[1]['Set-Cookie'].split(';')[0]

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.app.close();self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        values = {'Content-Type': 'application/json', 'X-App-Request': '1', 'X-Idempotency-Key': 'key-' + str(time.time_ns())}
        if self.cookie:values['Cookie'] = self.cookie
        values.update(headers or {})
        connection.request(method, path, None if body is None else json.dumps(body), values)
        response = connection.getresponse();raw = response.read();result = (response.status, dict(response.getheaders()), raw)
        connection.close()
        if result[1].get('Content-Type', '').startswith('application/json'):result = (result[0], result[1], json.loads(raw))
        return result

    def test_knowledge_works_without_private_sixyao_rules(self):
        response = self.request('GET', '/api/workbench/skills')
        self.assertEqual(response[0], 200);self.assertEqual(len(response[2]['skills']), 2)
        added = self.request('POST', '/api/workbench/documents', DOC)
        self.assertEqual(added[0], 201, added)
        chat = self.request('POST', '/api/workbench/chats', {'title': '学习'})[2]['chat_id']
        job = self.request('POST', '/api/workbench/chats/' + chat + '/ask', {'question': '水表示什么？', 'provider': 'demo', 'model': 'local-demo'})
        self.assertEqual(job[0], 202, job)
        for _ in range(100):
            done = self.request('GET', '/api/workbench/jobs/' + job[2]['job_id'])[2]
            if done['status'] == 'completed':break
            time.sleep(.01)
        self.assertEqual(done['status'], 'completed', done)
        exported = self.request('GET', '/api/workbench/chats/' + chat + '/export')
        self.assertEqual(exported[0], 200);self.assertTrue(exported[2]['turns'][0]['result']['citations'])
        self.assertNotIn('snapshot', exported[2]['turns'][0])

    def test_csrf_session_and_route_validation(self):
        self.assertEqual(self.request('POST', '/api/workbench/documents', DOC, {'Origin': 'https://unrelated.example'})[0], 403)
        self.assertEqual(self.request('GET', '/api/workbench/documents', headers={'Cookie': ''})[0], 401)
        self.assertEqual(self.request('GET', '/api/workbench/chats/not-owned')[0], 404)
        self.assertEqual(self.request('POST', '/api/workbench/skills/knowledge/rollback', {'version': 1, 'expected_version': 1, 'script': 'bad'})[0], 400)

    def test_large_text_import_and_specific_validation_feedback(self):
        added = self.request('POST', '/api/workbench/documents', {'title': '长文', 'text': '五行与系统。'*12000})
        self.assertEqual(added[0], 201, added)
        invalid = self.request('POST', '/api/workbench/documents', {'title': '空文', 'text': ''})
        self.assertEqual(invalid[0], 422);self.assertIn('正文', invalid[2]['error']['message'])


if __name__ == '__main__':unittest.main()
