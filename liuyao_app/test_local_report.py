"""Regression checks: a completed interpretation needs no further AI request."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from .test_pipeline import BoundProvider
from .pipeline import run_analysis, result_from_outcome
from .report_generator import local_report
from . import test_server as http_fixture
from case_store import Actor, CaseStore


class LocalReportChecks(unittest.TestCase):
    def test_default_report_finishes_with_exactly_three_calls_and_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.sqlite3'
            store = CaseStore(path)
            actor = Actor('owner', 'session')
            try:
                cid = store.create_case(actor, {'question': '当前事项能否推进？',
                    'lines': ['young_yang', 'old_yin', 'young_yang', 'young_yin', 'young_yang', 'young_yin']},
                    idempotency_key='case')['case_id']
                provider = BoundProvider()
                events = []
                def no_formatting_request(*args, **kwargs):
                    if 'accepted_interpretation' in args[3]:
                        raise AssertionError('The report must not make a fourth model request')
                    return provider(*args, **kwargs)
                result = run_analysis(path, actor, cid, 'deepseek', 'synthetic', 1,
                                      provider_call=no_formatting_request, progress=events.append)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual([c['stage'] for c in provider.calls], ['intent', 'selection', 'interpretation'])
                self.assertEqual(result['report_status']['mode'], 'local')
                self.assertEqual(result['user_report']['conclusion'], result['stage_outputs']['interpretation']['conclusion'])
                self.assertTrue(any(e.get('completed_stage') == 'report' for e in events))
                retained = store.export_case(actor, cid)['analysis_runs'][-1]
                self.assertEqual(len(retained['ai_events']), 3)
                self.assertEqual(result_from_outcome(retained), result)
            finally:
                store.close()

    def test_full_answer_conditions_uncertainties_and_qualifications_survive(self):
        plan = {'binding': {'analysis_run_id': 'run', 'input_snapshot_id': 'snapshot'},
            'conclusion': {'answer': '有机会推进；必须先取得确认，不能据此保证最终结果。',
                'direction': 'mixed', 'qualification': 'conditional', 'claim_refs': ['C1'],
                'key_conditions': ['条件一', '条件二', '条件三', '条件四'], 'limits': ['尚不能确定时间']},
            'claims': [{'claim_id': 'C1', 'dimension': 'support', 'statement': '支持因素需要核实。',
                        'assumptions': ['支持能够落实'], 'limitations': ['不能保证结果']}],
            'uncertainties': [{'gap_id': 'GAP_X', 'impact': '答复时间未知'}],
            'advice': [{'text': '先确认对方的答复。'}]}
        original = copy.deepcopy(plan)
        result = local_report(plan, {})
        self.assertEqual(result['conclusion'], plan['conclusion'])
        self.assertEqual(result['plain_language']['answer'], plan['conclusion']['answer'])
        self.assertIn('条件四', result['plain_language']['watch_for'])
        self.assertIn('答复时间未知', result['plain_language']['watch_for'])
        self.assertEqual(result['uncertainties'], plan['uncertainties'])
        self.assertEqual(result['accepted_claims'], plan['claims'])
        support = next(s for s in result['sections'] if s['key'] == 'support')['content']
        self.assertEqual(support.count('支持因素需要核实。'), 1)
        self.assertIn('支持能够落实', support)
        self.assertIn('不能保证结果', support)
        self.assertEqual(plan, original)


class UserGuideHTTPChecks(unittest.TestCase):
    setUp = http_fixture.HTTPChecks.setUp
    tearDown = http_fixture.HTTPChecks.tearDown
    request = http_fixture.HTTPChecks.request
    fake_pipeline = http_fixture.HTTPChecks.fake_pipeline

    def test_guide_is_downloadable_and_requires_session(self):
        status, headers, data = self.request('GET', '/api/help/export')
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers['Content-Type'])
        self.assertIn('attachment', headers['Content-Disposition'])
        text = data.decode()
        for label in ('新人使用说明', '枚卜丸', '太极丸', '报告整理超时', '导出案例'):
            self.assertIn(label, text)
        # Navigation is bundled for offline use; no remote script/image asset is needed.
        self.assertIn('<script id="guide-script">', text)
        self.assertNotRegex(text, r'<script[^>]+src=')
        self.assertNotRegex(text, r'<(?:img|link)[^>]+(?:src|href)=["\']https?://')
        for label in ('开始使用', '起卦图解', '查看结果', '常见问题'):
            self.assertIn(label, text)
        status, _, _ = self.request('GET', '/api/help/export', cookie=False)
        self.assertEqual(status, 401)


if __name__ == '__main__':
    unittest.main()
