"""Birth calculation, report consistency and non-writing rule trials."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from .birth_calendar import calculate_birth_chart
from .calendar_context import calculate_calendar
from .profile_store import save_profile
from .rulebook import load_rules,export_workbook,read_workbook,compile_rules,RuleBook
from .rule_explanations import rule_guide,preview_rule
from .report_generator import plain_fallback
from .test_v5 import NewReportProvider,INPUT
from .pipeline import run_analysis
from case_store import CaseStore,Actor

class BirthTests(unittest.TestCase):
    def test_partial_full_and_calendar_boundary(self):
        partial=calculate_birth_chart('1990-01-01')
        full=calculate_birth_chart('1990-01-01','1990-01-01T12:00:00')
        expected=calculate_calendar({'actual_cast_time':'1990-01-01T12:00:00+08:00'})['pillars']
        self.assertEqual(full['pillars'],expected)
        self.assertIsNone(partial['pillars']['hour'])
        self.assertEqual(partial['pillars']['day'],expected['day'])
        boundary=calculate_birth_chart('2026-02-04')
        self.assertIsNone(boundary['pillars']['year'])
        self.assertIsNone(boundary['pillars']['month'])
        self.assertTrue(boundary['alternatives'])
        late=calculate_birth_chart('1990-01-01','1990-01-01T23:30:00')
        self.assertEqual(late['pillars']['day'],expected['day'])
    def test_invalid_input_is_not_silently_accepted(self):
        for args in [('2026-02-30',''),('1899-01-01',''),('1990-01-01','garbage'),('1990-01-01','1990-01-02T12:00'),(3,False)]:
            self.assertEqual(calculate_birth_chart(*args)['status'],'error',args)
    def test_save_recomputes_and_unknown_hour_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            db=CaseStore(Path(directory)/'cases.sqlite3');a=Actor('a','s')
            try:
                p=save_profile(db,a,{'name':'本人','birth_date':'1990-01-01','bazi':'stale'},idempotency_key='one')
                self.assertIn('时柱待补',p['profile']['bazi'])
                p2=save_profile(db,a,{'name':'本人','birth_date':'1990-01-02'},person_id=p['person_id'],expected_version=1,idempotency_key='two')
                self.assertNotEqual(p['profile']['bazi'],p2['profile']['bazi'])
                self.assertEqual(p2['birth_chart']['status'],'partial')
            finally:db.close()

class RuleGuideTests(unittest.TestCase):
    def test_guide_covers_all_and_preview_never_changes_book(self):
        book=load_rules();old=copy.deepcopy(book.compiled);guide=rule_guide(book)
        self.assertEqual(len(guide['rules']),len(book.rows))
        for r in guide['rules']:
            for k in ('meaning','formula','increase','example','rationale'):self.assertTrue(r[k],r['id'])
        trial=preview_rule(book,'BASE_SCORE',2,True)
        self.assertFalse(trial['saved']);self.assertNotEqual(trial['before'],trial['after']);self.assertEqual(book.compiled,old)
        with self.assertRaises(ValueError):preview_rule(book,'LEVEL_WEAK',9,True)
    def test_export_keeps_annotations_examples_and_no_stale_caches(self):
        book=load_rules();raw=export_workbook(book)
        self.assertEqual(compile_rules(read_workbook(raw)),book.compiled)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertIn('试算',z.read('xl/workbook.xml').decode())
            self.assertIn('fullCalcOnLoad="1"',z.read('xl/workbook.xml').decode())
            self.assertIn('参数含义',z.read('xl/worksheets/sheet1.xml').decode())
            import xml.etree.ElementTree as ET
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            sheet=ET.fromstring(z.read('xl/worksheets/sheet3.xml'))
            formulas=[c for c in sheet.findall('.//s:c',ns) if c.find('s:f',ns) is not None]
            self.assertGreater(len(formulas),5)
            self.assertTrue(all(c.find('s:v',ns) is None for c in formulas))

class PlainReportTests(unittest.TestCase):
    def run_report(self,modifier=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cases.sqlite3';db=CaseStore(path);a=Actor('owner','session')
            try:
                cid=db.create_case(a,INPUT,idempotency_key='case')['case_id'];p=NewReportProvider()
                def provider(*args,**kwargs):
                    r=p(*args,**kwargs)
                    if modifier and p.calls[-1]['stage']=='report':
                        v=json.loads(r['raw_text']);modifier(v);r['raw_text']=json.dumps(v,ensure_ascii=False)
                    return r
                return run_analysis(path,a,cid,'deepseek','synthetic',1,provider_call=provider)
            finally:db.close()
    def test_new_report_contains_plain_answer_and_full_professional_parts(self):
        r=self.run_report();self.assertEqual(r['status'],'completed')
        self.assertEqual(r['user_report']['plain_language']['source'],'ai')
        self.assertEqual(len(r['user_report']['sections']),7)
    def test_wrong_direction_or_jargon_falls_back_without_losing_conclusion(self):
        for change in [lambda v:v['plain_language'].update(direction='unfavorable'),lambda v:v['plain_language'].update(reason='用神官鬼得日辰生扶')]:
            r=self.run_report(change)
            self.assertEqual(r['user_report']['plain_language']['source'],'compatibility')
            self.assertEqual(r['user_report']['conclusion']['direction'],'favorable')
            self.assertTrue(r['audit_report']['warnings'])
    def test_legacy_report_gets_safe_plain_fallback(self):
        r=self.run_report(lambda v:v.pop('plain_language'))
        self.assertEqual(r['user_report']['plain_language']['source'],'compatibility')
        p=plain_fallback({'direction':'favorable','answer':'主用官鬼得月令支持，可成。'})
        self.assertNotIn('官鬼',p['answer'])
