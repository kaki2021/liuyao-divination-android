"""Educational explanations stay tied to real calculations and source status."""
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch
import http.server
from .learning_guide import usage_guide
from .rule_explanations import rule_guide, preview_rule, score_trace, KINDS
from .rulebook import load_rules, RuleBook, compile_rules, export_workbook, read_workbook
from .pipeline import calculate_chart, run_analysis
from .test_v5 import INPUT, LINES, NewReportProvider
CHART_INPUT = {**INPUT, "lines": LINES}
from .providers import _http_transport, ProviderError
from .server import Application
from case_store import CaseStore, Actor

class GuidanceTests(unittest.TestCase):
    def test_checked_sources_keep_quotes_separate_from_software_guidance(self):
        g=usage_guide()
        self.assertEqual(len(g['rules']),9)
        self.assertIn('已于 2026-09-20 核对',g['source_note'])
        self.assertTrue(all(x['locator'] and x['quote'] and x['review_note'] and x['source_url'] and x['evidence_status']=='source_checked_summary' for x in g['rules']))
        self.assertIn('谋而后卜',g['rules'][0]['help'])
        self.assertIn('另问具体问题',g['rules'][-1]['help'])

    def test_all_parameters_have_operational_types(self):
        guide=rule_guide(load_rules())
        self.assertEqual({r['kind'] for r in guide['rules']},set(KINDS))
        self.assertEqual(len(guide['rules']),70)
        self.assertTrue(all(r['kind_label'] and r['affects'] and r['source_type'] for r in guide['rules']))
        base=next(r for r in guide['rules'] if r['id']=='BASE_SCORE')
        self.assertEqual(base['kind'],'base')
        self.assertIn('六个爻分别',base['meaning'])

    def test_ledger_reconciles_actual_engine_including_caps_and_missing_time(self):
        book=load_rules()
        for base in (0,5,10):
            rows=copy.deepcopy(book.compiled['rules']);next(r for r in rows if r['id']=='BASE_SCORE')['value']=base
            changed=RuleBook(compile_rules(rows))
            for inp in (CHART_INPUT, {'lines':['old_yang','young_yin','old_yin','young_yang','old_yin','young_yang'],'question':'账单核对'}):
                a=calculate_chart(inp,changed)['comprehensive_analysis']
                traces=score_trace(a,changed)
                for l,t in zip(a['lines'],traces):
                    own=sum(c['value'] for c in t['local_items']);inc=sum(c['value'] for c in t['incoming_items'])
                    self.assertEqual(round(base+own,3),t['local_raw'])
                    self.assertEqual(round(base+sum(c['value'] for c in t['local_items']+t['incoming_items']),3),t['raw_score'])
                    self.assertEqual(t['score'],l['strength']['score'])
                    for c in t['incoming_items']:
                        amount=c['parameter'] if c['enabled'] else 0
                        for m in c['multipliers']:amount*=m['value']
                        self.assertEqual(round(amount,6),c['value'])

    def test_disabled_parameters_and_non_scoring_switch_are_visible(self):
        book=load_rules();before=copy.deepcopy(book.compiled)
        trial=preview_rule(book,'MOVING',9,False,CHART_INPUT)
        moving=[c for t in trial['after_trace'] for c in t['local_items'] if c['rule_id']=='MOVING']
        self.assertTrue(moving)
        self.assertTrue(all(not c['enabled'] and c['value']==0 for c in moving))
        self.assertFalse(trial['saved']);self.assertEqual(book.compiled,before)
        switch=preview_rule(book,'ENABLE_TRIPLE_COMBINE',1,False,CHART_INPUT)
        self.assertEqual(switch['rule_kind'],'switch')
        self.assertIn('changes',switch['after_structures'])

    def test_export_includes_types_without_changing_numeric_rules(self):
        book=load_rules();raw=export_workbook(book)
        self.assertEqual(compile_rules(read_workbook(raw)),book.compiled)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            sheet=z.read('xl/worksheets/sheet1.xml').decode()
            self.assertIn('参数类型',sheet);self.assertIn('影响位置',sheet)
            self.assertIn('A1:U71',sheet)
            table=z.read('xl/tables/table1.xml').decode()
            self.assertIn('A1:U71',table);self.assertIn('count="21"',table)

    def test_report_checkpoint_and_90_second_budget_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cases.sqlite3';store=CaseStore(path);actor=Actor('local-user','s')
            try:
                case=store.create_case(actor,INPUT,idempotency_key='c')['case_id'];fixture=NewReportProvider();events=[];timeouts=[]
                def call(*args,**kwargs):
                    if 'accepted_interpretation' in args[3]:
                        self.assertTrue(any('checkpoint' in e for e in events));timeouts.append(kwargs['timeout'])
                        raise ProviderError('timeout','合成超时')
                    return fixture(*args,**kwargs)
                result=run_analysis(path,actor,case,'deepseek','deepseek-flash',1,progress=events.append,provider_call=call)
                self.assertTrue(89<timeouts[0]<=90)
                self.assertEqual(result['status'],'completed');self.assertEqual(result['report_status']['code'],'timeout')
                self.assertEqual(result['user_report']['conclusion'],result['stage_outputs']['interpretation']['conclusion'])
            finally:store.close()

    def test_interrupted_report_recovers_saved_interpretation_without_new_call(self):
        class PowerLoss(BaseException):pass
        captured=[]
        def interrupted_pipeline(*args,**kwargs):
            fixture=NewReportProvider();progress=kwargs.pop('progress')
            def record(event):
                progress(event)
                if isinstance(event,dict) and event.get('checkpoint'):
                    captured.append(event['checkpoint'])
                    raise PowerLoss()
            return run_analysis(*args,progress=record,provider_call=fixture,**kwargs)
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,pipeline=interrupted_pipeline);actor=Actor('local-user','s')
            store=app.store()
            try:case=store.create_case(actor,INPUT,idempotency_key='c')['case_id']
            finally:store.close()
            config={'providers':[{'id':'deepseek','models':['deepseek-flash'],'configured':True}]}
            with patch.object(app,'config',return_value=config):
                job_id=app.enqueue(actor,case,{'provider':'deepseek','model':'deepseek-flash','expected_revision_seq':1},'run')['job_id']
            app.pool.shutdown(wait=True)
            job=app.get_job(actor,job_id)
            self.assertEqual(job['status'],'running');self.assertIn('preview_report',job);self.assertNotIn('_checkpoint',job)
            expected=copy.deepcopy(captured[0]['user_report']['conclusion'])
            app.close()
            recovered=Application(directory)
            try:
                job=recovered.get_job(actor,job_id)
                self.assertEqual(job['status'],'completed')
                self.assertEqual(job['result']['report_status']['code'],'INTERRUPTED')
                self.assertEqual(job['result']['user_report']['conclusion'],expected)
                self.assertEqual(len(captured),1)
                store=recovered.store()
                try:
                    runs=store.export_case(actor,case)['analysis_runs']
                    self.assertEqual(len(runs),1);self.assertEqual(runs[0]['status'],'completed')
                finally:store.close()
            finally:recovered.close()

    def test_slow_http_keepalive_has_elapsed_deadline(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.send_response(200);self.end_headers()
                try:
                    for _ in range(30):self.wfile.write(b'\n');self.wfile.flush();time.sleep(.03)
                except (BrokenPipeError,ConnectionResetError):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=lambda:server.serve_forever(poll_interval=.03),daemon=True);t.start()
        try:
            started=time.monotonic()
            with self.assertRaises(TimeoutError):_http_transport('http://127.0.0.1:'+str(server.server_port),{},{},.18)
            self.assertLess(time.monotonic()-started,.7)
        finally:server.shutdown();server.server_close();t.join()

if __name__=='__main__':unittest.main()
