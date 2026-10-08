"""Condition reasoning, frozen documentation and real HTTP entry regressions."""
import copy
import hashlib
import http.client
import itertools
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
import uuid
from html.parser import HTMLParser

from .conditional_reasoning import condition, conjunction, evaluate_conditions, rule_guide
from .calculation_logic import logic_guide, logic_markdown, ROOT
from .pipeline import calculate_chart, run_analysis
from .comprehensive_analysis import select_use_lines, analysis_facts
from .rulebook import RuleBook, compile_rules, save_rules
from .test_rule_installation import public_placeholder_rows
from .test_pipeline import BoundProvider
from .test_v5 import INPUT
from .server import Application, Server
from case_store import Actor, CaseStore
import base_chart as base

DATA={'question':'这套房屋适合本人居住吗？','lines':['young_yang']*6,'actual_cast_time':'2026-09-18T12:00:00+08:00'}


class ConditionalReasoningTests(unittest.TestCase):
    def book(self, base_score=5):
        rows=public_placeholder_rows();next(r for r in rows if r['id']=='BASE_SCORE')['value']=base_score
        return RuleBook(compile_rules(rows))

    def test_unknown_never_becomes_false_or_satisfied(self):
        for values,expected in [([True,True],'satisfied'),([True,None],'unknown'),([False,None],'unsatisfied'),([None,None],'unknown')]:
            self.assertEqual(conjunction([condition(str(i),'前提',v) for i,v in enumerate(values)]),expected)
        for value in [0,1,'true',{},[]]:
            with self.assertRaises(ValueError):condition('x','前提',value)

    def test_missing_calendar_is_preserved_and_static_has_no_change_empty(self):
        chart=calculate_chart({'lines':['young_yang']*6},include_experimental=False)
        for line in chart['conditional_analysis']['lines']:
            self.assertIsNone(line['empty']);self.assertIsNone(line['changed_empty'])
            self.assertFalse(line['moving']);self.assertIsNone(line['comprehensive_strength'])
        self.assertNotIn('comprehensive_analysis',chart)
        self.assertEqual(next(c for c in chart['conditional_analysis']['checks'] if c['rule_id']=='change_empty')['status'],'unknown')

    def test_changed_empty_and_original_empty_are_independent(self):
        chart=calculate_chart({'lines':['old_yang']*6},include_experimental=False)
        chart['calendar']={'status':'computed','pillars':{'month':'甲子','day':'甲子'}}
        a=evaluate_conditions(chart,{'lines':['old_yang']*6})
        self.assertTrue(any(l['empty']!=l['changed_empty'] for l in a['lines']))
        for l in a['lines']:
            self.assertEqual(l['empty'],l['branch'] in ('戌','亥'))
            self.assertEqual(l['changed_empty'],l['changed_branch'] in ('戌','亥'))

    def test_scores_do_not_change_conditions_or_force_multiple_use(self):
        data={'lines':['young_yang']*6,'actual_cast_time':DATA['actual_cast_time']}
        before=calculate_chart(data,self.book(1));after=calculate_chart(data,self.book(9))
        self.assertEqual(before['conditional_analysis'],after['conditional_analysis'])
        code=next(code for code in {l['relative_code'] for l in before['main']['lines']}
                  if sum(l['relative_code']==code for l in before['main']['lines'])>1)
        sel={'candidates':[{'candidate_id':'p','purpose':'primary','six_relative':code}],'selected_primary_id':'p'}
        for chart in (before,after):
            selected=select_use_lines(chart,sel,self.book())['primary']
            self.assertGreater(len(selected['matches']),1);self.assertIsNone(selected['chosen'])
            analysis=evaluate_conditions(chart,data,sel)
            self.assertEqual(analysis['selection_status'],'multiple_matches')
            self.assertTrue(all(e['effective'] is None for e in analysis['effects']))

    def test_only_question_targets_receive_candidate_operations(self):
        chart=calculate_chart({'lines':['old_yang']*6},include_experimental=False)
        sel={'candidates':[{'candidate_id':'p','purpose':'primary','subject_reference':'shi'}],'selected_primary_id':'p'}
        a=evaluate_conditions(chart,{},sel)
        self.assertEqual({e['target_position'] for e in a['effects']},{chart['shi_position']})
        self.assertEqual(len(a['effects']),5)
        self.assertTrue(all(e['status']=='unknown' and e['effective'] is None for e in a['effects']))

    def test_residence_exception_keeps_wang_unknown_even_with_month_wang(self):
        data=copy.deepcopy(DATA);data['buzhai']={'stage':'site_choice','site_kind':'yang','role':'host','residence':'not_occupied'}
        chart=calculate_chart(data,include_experimental=False)
        shi=chart['main']['lines'][chart['shi_position']-1]
        # Force the calendar observations for this scoped unit test, not a user casting.
        day=next(stem+branch for i,(stem,branch) in enumerate(zip(('甲乙丙丁戊己庚辛壬癸'*6),base.BRANCHES*5))
                 if shi['branch'] in __import__('liuyao_app.day_month_analysis',fromlist=['xun_empty']).xun_empty(stem+branch)['branches'])
        chart['calendar']={'status':'computed','pillars':{'day':day,'month':'甲'+shi['branch']}}
        a=evaluate_conditions(chart,data);c=next(c for c in a['checks'] if c['rule_id']=='residence_empty')
        self.assertEqual(c['status'],'unknown');self.assertTrue(all(x['value'] is True for x in c['conditions'][:-1]))
        self.assertEqual(c['conditions'][-1]['missing_kind'],'system_criteria')
        occupied=copy.deepcopy(data);occupied['buzhai']['residence']='occupied'
        self.assertEqual(next(c for c in evaluate_conditions(chart,occupied)['checks'] if c['rule_id']=='residence_empty')['status'],'unsatisfied')

    def test_unspecified_role_is_unknown_not_false(self):
        data=copy.deepcopy(DATA)
        data['buzhai']={'stage':'site_choice','site_kind':'yang','role':'other','residence':'not_occupied'}
        check=next(c for c in evaluate_conditions(calculate_chart(data,include_experimental=False),data)['checks'] if c['rule_id']=='residence_empty')
        role=next(c for c in check['conditions'] if c['id']=='role')
        self.assertEqual(role['status'],'unknown')
        self.assertEqual(role['missing_kind'],'user_fact')

    def test_preview_engine_is_read_only_and_has_directional_harm_routes(self):
        chart=calculate_chart(DATA,include_experimental=False);saved=copy.deepcopy(chart);data=copy.deepcopy(DATA)
        a=evaluate_conditions(chart,data)
        self.assertEqual(chart,saved);self.assertEqual(data,DATA)
        for route in a['harm_routes']:
            self.assertEqual(route['status'],'structural_only')
            self.assertIn(route['combination_partner'],base.BRANCHES)
        self.assertTrue(any(c['status']=='unsatisfied' for c in a['checks']))

    def test_all_4096_structures_have_scalar_bounded_fact_values(self):
        for states in itertools.product(base.STATES,repeat=6):
            c=calculate_chart({'lines':list(states)},include_experimental=False)
            facts=analysis_facts(c)
            self.assertEqual(len(c['conditional_analysis']['lines']),6)
            self.assertLess(len(facts),100)
            self.assertTrue(all(len(str(f['value']))<=4000 for f in facts))
            self.assertFalse(any(f['fact_id'].startswith(('SCORE_','COMPOSITE_','ACTIVE_EFFECT_')) for f in facts))

    def test_documentation_hashes_the_installed_sources_and_is_self_contained(self):
        g=logic_guide();self.assertIsNone(g['parameter_version']);self.assertEqual(len(g['rules']),8)
        for name,digest in g['code_manifest'].items():self.assertEqual(digest,hashlib.sha256((ROOT/name).read_bytes()).hexdigest())
        text=logic_markdown(g)
        for needed in ['世身位置','旬空','多现保留','满足、不满足或未知','作用先后','实验评分','SHA256']:self.assertIn(needed,text)

    def test_live_model_uses_conditions_and_freezes_logic_with_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);save_rules(root/'knowledge_base',public_placeholder_rows())
            store=CaseStore(root/'cases.sqlite3');actor=Actor('owner','session')
            case=store.create_case(actor,INPUT,idempotency_key='create')['case_id'];provider=BoundProvider()
            result=run_analysis(root/'cases.sqlite3',actor,case,'deepseek','synthetic',1,provider_call=provider)
            self.assertEqual(result['status'],'completed',result.get('error'))
            interpretation=next(c['input'] for c in provider.calls if c['stage']=='interpretation')
            self.assertTrue(any(f['fact_id'].startswith('LINE_STATE_') for f in interpretation['facts']))
            self.assertFalse(any(f['fact_id'].startswith(('SCORE_','COMPOSITE_','ACTIVE_EFFECT_')) for f in interpretation['facts']))
            report=next(c['input'] for c in provider.calls if c['stage']=='report')
            self.assertNotIn('comprehensive_analysis',report['analysis_chart'])
            frozen=store.export_case(actor,case)['analysis_runs'][0]['outcome']['result']['report']
            self.assertEqual(frozen['logic_snapshot'],result['logic_snapshot']);store.close()


class ConditionalHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(self.temp.name)
        self.server=Server(('127.0.0.1',0),self.app);self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.cookie='';status,headers,self.html=self.request('GET','/')
        self.assertEqual(status,200);self.cookie=headers['Set-Cookie'].split(';')[0]

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.app.close();self.temp.cleanup()

    def request(self,method,path,data=None):
        headers={'Host':f'127.0.0.1:{self.server.server_port}','Cookie':self.cookie}
        raw=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
        if method=='POST':headers.update({'Content-Type':'application/json','X-App-Request':'1','X-Idempotency-Key':uuid.uuid4().hex})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            conn.request(method,path,raw,headers);response=conn.getresponse();body=response.read();headers=dict(response.getheaders())
            if headers.get('Content-Type','').startswith('application/json'):body=json.loads(body)
            return response.status,headers,body
        finally:conn.close()

    def test_all_page_resources_are_served_without_private_rules(self):
        html=self.html.decode();paths=re.findall(r'(?:src|href)="(/static/[^"]+)"',html)
        self.assertIn('/static/condition-rules.js',paths)
        for path in paths:self.assertEqual(self.request('GET',path)[0],200,path)
        self.assertEqual(self.request('GET','/api/condition-rules')[0],200)
        status,_,logic=self.request('GET','/api/calculation-logic');self.assertEqual(status,200);self.assertIsNone(logic['parameter_version'])
        status,headers,raw=self.request('GET','/api/calculation-logic/export')
        self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition']);self.assertIn('软件计算逻辑',raw.decode())

    def test_scenario_preview_does_not_install_save_or_call_ai(self):
        version=rule_guide()['version'];before=list(Path(self.temp.name).rglob('*'))
        status,_,body=self.request('POST','/api/condition-rules/preview',{'expected_version':version,'context':{'enabled':True,'residence':'not_occupied'}})
        self.assertEqual(status,200,body);self.assertFalse(body['saved']);self.assertTrue(body['is_demo'])
        self.assertEqual(len(body['before']['lines']),6);self.assertEqual(body['before']['lines'],body['after']['lines'])
        self.assertEqual(list(Path(self.temp.name).rglob('*')),before)
        store=self.app.store();self.assertEqual(store.db.execute('SELECT COUNT(*) FROM cases').fetchone()[0],0);store.close()

    def test_unknown_scene_and_stale_logic_are_rejected(self):
        for context in [{'stage':'unexpected'},{'role':[]},{'enabled':1},{'shi_wang':True}]:
            status,_,body=self.request('POST','/api/condition-rules/preview',{'expected_version':rule_guide()['version'],'context':context})
            self.assertIn(status,(400,422),body)
        self.assertEqual(self.request('POST','/api/condition-rules/preview',{'expected_version':'stale'})[0],409)


if __name__=='__main__':unittest.main()
