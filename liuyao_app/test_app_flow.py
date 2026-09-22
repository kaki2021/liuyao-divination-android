"""Whole local app smoke, with the real demo pipeline and no provider stubs."""
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid

from .server import Application, Server

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    Draft202012Validator = FormatChecker = None


class ResourceLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[]
    def handle_starttag(self, tag, attrs):
        fields=dict(attrs)
        if tag=='script' and fields.get('src'):self.links.append(fields['src'])
        if tag=='link' and fields.get('rel')=='stylesheet':self.links.append(fields['href'])


class FullAppFlow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=Application(self.temp.name)
        self.server=Server(('127.0.0.1',0),self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        self.thread.start();self.cookie=''
        status,raw,headers=self.request('GET','/')
        self.assertEqual(status,200)
        self.cookie=headers['Set-Cookie'].split(';')[0]
        self.html=raw.decode()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.app.close()
        self.thread.join();self.temp.cleanup()

    def request(self, method, path, data=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Cookie':self.cookie,'X-App-Request':'1','X-Idempotency-Key':uuid.uuid4().hex}
        body=None
        if data is not None:
            body=json.dumps(data,ensure_ascii=False).encode();headers['Content-Type']='application/json'
        c.request(method,path,body,headers)
        r=c.getresponse();out=(r.status,r.read(),dict(r.getheaders()));c.close();return out

    def api(self, method, path, data=None, expected=200):
        status,raw,_=self.request(method,path,data)
        self.assertEqual(status,expected,raw)
        return json.loads(raw)

    def analyze_demo(self, case_id, revision=1):
        queued = self.api('POST', f'/api/cases/{case_id}/analyze',
            {'provider': 'demo', 'model': 'local-demo', 'expected_revision_seq': revision}, 202)
        for _ in range(150):
            job = self.api('GET', '/api/jobs/' + queued['job_id'])
            if job['status'] not in ('queued', 'running'):
                break
            time.sleep(0.02)
        self.assertEqual(job['status'], 'partial', job)
        self.assertTrue(job['result']['is_demo'])
        return job

    def assert_input_retained(self, case_id, submitted, expected_lines):
        normalized = {**submitted, 'lines': expected_lines}
        detail = self.api('GET', f'/api/cases/{case_id}')
        exported = self.api('GET', f'/api/cases/{case_id}/export')
        self.assertEqual(exported['original_input'], normalized)
        self.assertEqual(exported['revisions'][0]['input'], normalized)
        self.assertEqual(exported['analysis_runs'][0]['input_snapshot']['input'], normalized)
        self.assertEqual(exported['analysis_runs'][0]['ai_events'], [])
        self.assertEqual(detail['chart']['input_lines'], expected_lines)
        self.assertTrue(detail['report_is_current'])
        return exported

    def test_frontend_resources_and_provider_settings(self):
        parser=ResourceLinks();parser.feed(self.html)
        self.assertEqual(set(parser.links), {'/static/styles.css', '/static/chart-display.js', '/static/v5-features.js', '/static/report-views.js', '/static/buzhai.js','/static/mobile.js','/static/mobile.css', '/static/compat.js', '/static/phone-chart.js','/static/analysis-status.js', '/static/guidance.js', '/static/app.js'})
        self.assertLess(parser.links.index('/static/chart-display.js'), parser.links.index('/static/app.js'))
        for path in parser.links:
            status,raw,headers=self.request('GET',path)
            self.assertEqual(status,200);self.assertGreater(len(raw),1000)
        config=self.api('GET','/api/config')
        self.assertEqual(config['default_provider'],'deepseek')
        self.assertEqual({p['id'] for p in config['providers']},{'deepseek','doubao','demo'})
        self.assertNotIn('api_key',json.dumps(config).lower())

    def test_real_demo_revision_and_feedback(self):
        original={'question':'我想了解这个合作项目的条件。','lines':['old_yin','young_yang','young_yin','old_yang','young_yang','young_yin']}
        case=self.api('POST','/api/cases',{'input':original},201)
        case_id=case['case_id']
        queued=self.api('POST',f'/api/cases/{case_id}/analyze',{'provider':'demo','model':'local-demo','expected_revision_seq':1},202)
        for _ in range(100):
            job=self.api('GET','/api/jobs/'+queued['job_id'])
            if job['status'] not in ('queued','running'):break
            time.sleep(0.02)
        self.assertEqual(job['status'],'partial')
        self.assertTrue(job['result']['is_demo'])
        self.assertIn('未调用AI',job['result']['display_report']['summary'])
        detail=self.api('GET',f'/api/cases/{case_id}')
        self.assertTrue(detail['report_is_current'])
        self.assertEqual(detail['result']['analysis_run_id'],job['analysis_run_id'])
        self.assertEqual(detail['case']['analysis_runs'][0]['ai_events'],[])
        updated={**original,'question':'更正：我想了解这个合作项目的执行条件。'}
        self.api('POST',f'/api/cases/{case_id}/revisions',{'input':updated,'reason':'补充说明关注点','expected_revision_seq':1},201)
        self.api('POST',f'/api/cases/{case_id}/feedback',{'text':'对方已经发来资料，尚未确定。','analysis_run_id':job['analysis_run_id']},201)
        detail=self.api('GET',f'/api/cases/{case_id}')
        self.assertFalse(detail['report_is_current'])
        self.assertEqual(detail['case']['original_input'],original)
        exported=self.api('GET',f'/api/cases/{case_id}/export')
        self.assertEqual(len(exported['revisions']),2)
        self.assertEqual(len(exported['feedback']),1)
        self.assertEqual(exported['analysis_runs'][0]['input_snapshot']['input'],original)

    def test_real_demo_meibu_all_moving_static_and_one_moving(self):
        fixtures = [
            ('circle', ['old_yang'] * 3 + ['old_yin'] * 3, [1, 2, 3, 4, 5, 6]),
            ('square', ['young_yang'] * 3 + ['young_yin'] * 3, []),
            ('6', ['young_yang'] * 3 + ['young_yin', 'young_yin', 'old_yin'], [6]),
        ]
        for third, lines, moving in fixtures:
            with self.subTest(third=third):
                submitted = {'question': '我想了解这个合作项目的条件。',
                    'casting': {'method': 'meibu', 'results': ['circle', 'square', third]}}
                created = self.api('POST', '/api/cases', {'input': submitted}, 201)
                self.assertEqual(created['chart']['moving_positions'], moving)
                job = self.analyze_demo(created['case_id'])
                exported = self.assert_input_retained(created['case_id'], submitted, lines)
                self.assertEqual(exported['analysis_runs'][0]['analysis_run_id'], job['analysis_run_id'])

    def test_real_demo_taiji_preserves_unsorted_tokens(self):
        submitted = {'question': '这件事的执行条件是什么？',
            'casting': {'method': 'taiji', 'results': ['322', '232', '332', '323', '222', '333']}}
        lines = ['young_yang', 'young_yang', 'young_yin', 'young_yin', 'old_yin', 'old_yang']
        created = self.api('POST', '/api/cases', {'input': submitted}, 201)
        self.analyze_demo(created['case_id'])
        exported = self.assert_input_retained(created['case_id'], submitted, lines)
        self.assertEqual(exported['original_input']['casting']['results'], ['322', '232', '332', '323', '222', '333'])

    def test_change_input_modes_retains_each_analysis_and_original(self):
        taiji = {'question': '我想了解这个合作项目的条件。',
            'casting': {'method': 'taiji', 'results': ['222', '322', '332', '333', '232', '323']}}
        first_lines = ['old_yin', 'young_yang', 'young_yin', 'old_yang', 'young_yang', 'young_yin']
        created = self.api('POST', '/api/cases', {'input': taiji}, 201)
        case_id = created['case_id']
        self.analyze_demo(case_id)
        first_export = self.api('GET', f'/api/cases/{case_id}/export')
        meibu = {'question': '更正录入方式并保留枚卜记录。',
            'casting': {'method': 'meibu', 'results': ['1', '2', '3']}}
        second_lines = ['young_yang', 'young_yin', 'old_yin', 'young_yang', 'young_yang', 'young_yin']
        self.api('POST', f'/api/cases/{case_id}/revisions',
            {'input': meibu, 'reason': '修正为实际枚卜记录', 'expected_revision_seq': 1}, 201)
        after_correction = self.api('GET', f'/api/cases/{case_id}')
        self.assertFalse(after_correction['report_is_current'])
        self.assertEqual(after_correction['case']['analysis_runs'], first_export['analysis_runs'])
        self.analyze_demo(case_id, 2)
        direct = {'question': '再次更正，仅提供四象。', 'lines': ['young_yin'] * 6}
        self.api('POST', f'/api/cases/{case_id}/revisions',
            {'input': direct, 'reason': '按四象更正', 'expected_revision_seq': 2}, 201)
        self.analyze_demo(case_id, 3)
        exported = self.api('GET', f'/api/cases/{case_id}/export')
        expected = [{**taiji, 'lines': first_lines}, {**meibu, 'lines': second_lines}, direct]
        self.assertEqual(exported['original_input'], expected[0])
        self.assertEqual([r['input'] for r in exported['revisions']], expected)
        self.assertEqual([r['input_snapshot']['input'] for r in exported['analysis_runs']], expected)
        self.assertEqual(exported['analysis_runs'][0], first_export['analysis_runs'][0])
        self.assertNotIn('casting', exported['revisions'][2]['input'])
        self.assertEqual([r['revision_seq'] for r in exported['analysis_runs']], [1, 2, 3])

    @unittest.skipIf(Draft202012Validator is None, 'optional jsonschema dependency is unavailable')
    def test_actual_export_matches_case_record_json_schema(self):
        schema_path = Path(__file__).resolve().parents[1] / 'software_prep' / 'case_record_schema.json'
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        fixtures = [
            {'question': '四象契约', 'lines': ['young_yang'] * 6},
            {'question': '枚卜契约', 'casting': {'method': 'meibu', 'results': ['circle', 'square', '1']}},
            {'question': '太极契约', 'casting': {'method': 'taiji', 'results': ['322', '232', '332', '323', '222', '333']}},
        ]
        for submitted in fixtures:
            with self.subTest(submitted=submitted):
                created = self.api('POST', '/api/cases', {'input': submitted}, 201)
                self.analyze_demo(created['case_id'])
                exported = self.api('GET', '/api/cases/' + created['case_id'] + '/export')
                errors = [f'{list(error.absolute_path)}: {error.message}' for error in validator.iter_errors(exported)]
                self.assertEqual(errors, [])

if __name__=='__main__':unittest.main()
