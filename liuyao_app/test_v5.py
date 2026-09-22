"""V5 behavioural regressions. Synthetic providers only; no paid API calls."""
import copy
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from liuyao_app.pipeline import calculate_chart,run_analysis
from liuyao_app.rulebook import load_rules,save_rules,compile_rules,RuleBook,read_workbook,export_workbook
from liuyao_app.day_month_analysis import xun_empty,analyze_day_month
from liuyao_app.change_analysis import analyze_change
from liuyao_app.comprehensive_analysis import select_use_lines,analysis_facts
from liuyao_app.report_template import SECTIONS
from liuyao_app.profile_store import save_profile,get_profile,list_profiles
from liuyao_app.selection_context import current_selection_notes
from liuyao_app.test_pipeline import BoundProvider
from case_store import Actor,CaseStore,AccessDenied,Conflict
import base_chart

INPUT={'question':'下个月这个项目能不能签下合同？','casting':{'method':'meibu','results':['1','5','5']},'actual_cast_time':'2026-09-19T12:00:00+08:00'}
LINES=['old_yang','young_yin','young_yin','young_yang','old_yin','young_yang']

class NewReportProvider(BoundProvider):
    def __call__(self,*args,**kwargs):
        response=super().__call__(*args,**kwargs)
        stage=self.calls[-1]['stage'];inp=self.calls[-1]['input'];out=json.loads(response['raw_text'])
        if stage=='interpretation':
            out['conclusion'].update(answer='偏向能签成，但需要先调整合同条件。',direction='favorable',qualification='conditional')
        if stage=='report':
            out={'binding':out['binding'],'summary':inp['accepted_interpretation']['conclusion']['answer'],
                 'conclusion':inp['accepted_interpretation']['conclusion'],
                 'plain_language':{'direction':'favorable','answer':'下个月偏向能签成，但需要先谈妥合同条件。','reason':'推进签约的条件相对有利，文书和资源安排仍需落实。','watch_for':['对方的条款可能让你承受压力。','文书或资金安排可能反复。'],'next_steps':['先核对条款、资质和交付安排。','提前明确可接受的让步范围。'],'timing':'暂时不能确定具体签约日期，请给谈判和准备材料预留时间。','source':'ai'},
                 'sections':[{'key':k,'heading':h,'content':'合成测试报告：'+h} for k,h in SECTIONS]}
        response['raw_text']=json.dumps(out,ensure_ascii=False);return response

class V5Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'cases.sqlite3'
        self.store=CaseStore(self.path);self.actor=Actor('owner','session');self.rules=load_rules()
    def tearDown(self):self.store.close();self.temp.cleanup()
    def create(self,profile=None):
        data={**INPUT}
        if profile:data['person_info']={'subject':'self','profile_id':profile['person_id']}
        return self.store.create_case(self.actor,data,idempotency_key='case')['case_id']
    def run_case(self,case,provider=None):
        return run_analysis(self.path,self.actor,case,'deepseek','synthetic',1,provider_call=provider or NewReportProvider())
    def test_sixty_day_empty_pairs(self):
        stems='甲乙丙丁戊己庚辛壬癸';branches=base_chart.BRANCHES
        expected=['戌亥','申酉','午未','辰巳','寅卯','子丑']
        for i in range(60):self.assertEqual(''.join(xun_empty(stems[i%10]+branches[i%12])['branches']),expected[i//10])
        for invalid in ['甲丑','',None,'甲子日']:
            with self.assertRaises(ValueError):xun_empty(invalid)
    def test_day_clash_is_not_always_hidden_moving(self):
        line={'position':1,'branch':'卯','element':'木','moving':False}
        strong=analyze_day_month(line,{'status':'computed','pillars':{'month':'甲寅','day':'乙酉'}},self.rules)
        self.assertTrue(strong['hidden_moving']);self.assertFalse(strong['day_break'])
        weak=analyze_day_month(line,{'status':'computed','pillars':{'month':'乙酉','day':'乙酉'}},self.rules)
        self.assertTrue(weak['month_break']);self.assertTrue(weak['day_break']);self.assertFalse(weak['hidden_moving'])
        unknown=analyze_day_month(line,{'status':'missing'},self.rules)
        self.assertIsNone(unknown['empty']);self.assertIsNone(unknown['hidden_moving'])
    def test_change_uses_original_palace_and_reverse_direction(self):
        line={'position':1,'branch':'寅','element':'木'}
        c=analyze_change(line,'亥','土',{'status':'missing'},self.rules)
        self.assertEqual(c['relative_code'],'wealth');self.assertEqual(c['relation'],'generates');self.assertIn('回头生',c['effects'])
        self.assertIn('化进',analyze_change(line,'卯','土',{},self.rules)['effects'])
        line={'position':1,'branch':'卯','element':'木'}
        self.assertIn('化退',analyze_change(line,'寅','土',{},self.rules)['effects'])
        self.assertIn('化墓',analyze_change(line,'未','土',{},self.rules)['effects'])
        self.assertIn('化绝',analyze_change(line,'申','土',{},self.rules)['effects'])
    def test_all_4096_states_are_bounded_and_fact_budget_safe(self):
        # Exhaustive coverage for six positions and all four explicit line states.
        max_facts=0
        for states in itertools.product(base_chart.STATES,repeat=6):
            chart=calculate_chart({'lines':list(states),'actual_cast_time':INPUT['actual_cast_time']},self.rules)
            a=chart['comprehensive_analysis'];facts=analysis_facts(chart);max_facts=max(max_facts,len(facts))
            self.assertTrue(all(0<=l['strength']['score']<=10 for l in a['lines']))
            self.assertEqual(sum(l['change'] is not None for l in a['lines']),len(chart['moving_positions']))
            self.assertTrue(all(not isinstance(f['value'],str) or len(f['value'])<=4000 for f in facts))
            for fu in a['hidden_spirits']:
                self.assertNotIn(fu['relative_code'],{l['relative_code'] for l in a['lines']})
                self.assertEqual(fu['flying_branch'],a['lines'][fu['position']-1]['branch'])
        self.assertLess(max_facts,100)
    def test_workbook_roundtrip_and_bad_id_formula_type_rejection(self):
        data=export_workbook(self.rules)
        self.assertEqual(compile_rules(read_workbook(data)),self.rules.compiled)
        rows=copy.deepcopy(self.rules.compiled['rules'])
        for change in ('duplicate','missing','unknown','type','range','required'):
            r=copy.deepcopy(rows)
            if change=='duplicate':r.append(r[0])
            elif change=='missing':r.pop()
            elif change=='unknown':r[0]['id']='NEW_ID'
            elif change=='type':r[0]['value']='1'
            elif change=='range':r[0]['value']=float('nan')
            elif change=='required':next(x for x in r if x['id']=='BASE_SCORE')['enabled']=False
            with self.assertRaises(ValueError,msg=change):compile_rules(r)
        z=zipfile.ZipFile(io.BytesIO(data));out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as w:
            for n in z.namelist():
                raw=z.read(n)
                if n=='xl/worksheets/sheet1.xml':
                    raw=raw.replace(b'</ns0:c>',b'<ns0:f>1+1</ns0:f></ns0:c>',1)
                w.writestr(n,raw)
        with self.assertRaises(ValueError):read_workbook(out.getvalue())
    def test_changed_weight_changes_score_and_preserves_old_prediction(self):
        case=self.create();first=self.run_case(case)
        original=copy.deepcopy(self.store.export_case(self.actor,case)['analysis_runs'][0])
        rows=copy.deepcopy(self.rules.compiled['rules']);next(r for r in rows if r['id']=='BASE_SCORE')['value']=2
        b=save_rules(Path(self.temp.name)/'knowledge_base',rows)
        second=self.run_case(case)
        self.assertNotEqual(first['rules_version'],second['rules_version'])
        self.assertEqual(second['rules_version'],b.version)
        self.assertNotEqual([l['strength']['score'] for l in first['chart']['comprehensive_analysis']['lines']],[l['strength']['score'] for l in second['chart']['comprehensive_analysis']['lines']])
        self.assertEqual(self.store.export_case(self.actor,case)['analysis_runs'][0],original)
        self.store.add_feedback(self.actor,case,reported_outcome='最终签约',analysis_run_id=first['analysis_run_id'],match_degree='matched',user_notes='测试反馈',idempotency_key='feedback')
        fb=self.store.export_case(self.actor,case)['feedback'][0];self.assertEqual(fb['rules_version'],first['rules_version']);self.assertEqual(fb['match_degree'],'matched')
    def test_canonical_report_and_warning_do_not_vanish(self):
        case=self.create();p=NewReportProvider();r=self.run_case(case,p)
        self.assertEqual(r['status'],'completed',r.get('error'))
        self.assertEqual(len(p.calls),4)
        self.assertEqual(r['user_report'],r['display_report'])
        self.assertTrue(r['user_report']['summary'].startswith('偏向能签成'))
        self.assertEqual([s['key'] for s in r['user_report']['sections']],[k for k,h in SECTIONS])
        self.assertTrue(r['audit_report']['warnings']) # Fixture omits claim evidence on purpose.
        self.assertNotIn('待复核的条件解释',json.dumps(r['user_report'],ensure_ascii=False))
    def test_report_failure_retains_prediction_and_audit(self):
        case=self.create();p=NewReportProvider()
        def broken(*args,**kwargs):
            r=p(*args,**kwargs)
            if p.calls[-1]['stage']=='report':r['raw_text']='not JSON'
            return r
        r=self.run_case(case,broken)
        self.assertEqual(r['status'],'completed');self.assertEqual(len(p.calls),5)
        self.assertTrue(r['user_report']['conclusion']['answer'].startswith('偏向能签成'))
        self.assertTrue(any(w['stage']=='report' for w in r['audit_report']['warnings']))
    def test_profile_snapshot_bazi_exclusion_and_ownership(self):
        p=save_profile(self.store,self.actor,{'name':'自己','bazi':'BAZI_PRIVATE_SENTINEL','notes':'PRIVATE_BIRTH_NOTES','birth_time':'1990-01-01T12:00'},is_self=True,idempotency_key='p1')
        case=self.create(p);provider=NewReportProvider();first=self.run_case(case,provider)
        self.assertNotIn('BAZI_PRIVATE_SENTINEL',json.dumps(provider.calls,ensure_ascii=False))
        run=self.store.export_case(self.actor,case)['analysis_runs'][0]
        self.assertEqual(run['input_snapshot']['person_profile_snapshot']['profile']['bazi'],p['profile']['bazi'])
        self.assertNotIn('PRIVATE_BIRTH_NOTES',json.dumps(provider.calls,ensure_ascii=False))
        self.assertNotIn(p['profile']['bazi'],json.dumps(provider.calls,ensure_ascii=False))
        p2=save_profile(self.store,self.actor,{'name':'新称呼','bazi':'REVISED'},person_id=p['person_id'],expected_version=1,is_self=True,idempotency_key='p2')
        self.assertEqual(p2['version'],2)
        self.assertEqual(self.store.export_case(self.actor,case)['analysis_runs'][0],run)
        with self.assertRaises(Conflict):save_profile(self.store,self.actor,{'name':'过期编辑'},person_id=p['person_id'],expected_version=1,idempotency_key='p3')
        with self.assertRaises(AccessDenied):get_profile(self.store,Actor('other','s'),p['person_id'])
        self.assertEqual(list_profiles(self.store,Actor('other','s')),[])
    def test_resolved_note_is_only_in_audit_not_current_ai_context(self):
        c=calculate_chart({'lines':LINES,'actual_cast_time':INPUT['actual_cast_time']})
        selection={'unresolved':['未收到起卦日期，合同期限未提供。']}
        notes=current_selection_notes(selection,{'actual_cast_time':INPUT['actual_cast_time']},c)
        self.assertEqual(notes,['合同期限未提供'])
    def test_v4_database_migrates_without_rewriting_old_records(self):
        import sqlite3
        old_path=Path(self.temp.name)/'v4.sqlite3'
        old=sqlite3.connect(old_path)
        old.executescript((Path(__file__).resolve().parents[1]/'software_prep/case_store.sql').read_text())
        old.execute("INSERT INTO cases VALUES ('old-case','owner','session','2025-01-01T00:00:00Z','{}')")
        old.execute("INSERT INTO feedback VALUES ('old-feedback','old-case',NULL,NULL,'2025-01-01T00:00:00Z','旧反馈','self_reported',NULL,NULL)")
        old.commit();before=old.execute('SELECT * FROM cases').fetchall();old.close()
        migrated=CaseStore(old_path)
        self.assertEqual([tuple(r) for r in migrated.db.execute('SELECT * FROM cases')],before)
        feedback=dict(migrated.db.execute('SELECT * FROM feedback').fetchone())
        self.assertEqual(feedback['reported_outcome'],'旧反馈');self.assertIsNone(feedback['rules_version'])
        self.assertEqual(migrated.db.execute('PRAGMA user_version').fetchone()[0],5)
        migrated.close()

    def test_static_pair_is_not_an_active_effect(self):
        c=calculate_chart({'lines':['young_yang']*6})
        self.assertTrue(c['comprehensive_analysis']['pair_relations'])
        self.assertFalse(any(e['active'] for e in c['comprehensive_analysis']['effects']))
    def test_missing_function_selects_a_hidden_line(self):
        found=False
        for bits in itertools.product(('young_yin','young_yang'),repeat=6):
            c=calculate_chart({'lines':list(bits)});hidden=c['comprehensive_analysis']['hidden_spirits']
            if not hidden:continue
            sel={'candidates':[{'candidate_id':'p','purpose':'primary','six_relative':hidden[0]['relative_code']}],'selected_primary_id':'p'}
            u=select_use_lines(c,sel,self.rules)
            self.assertEqual(u['primary']['chosen']['layer'],'hidden');found=True;break
        self.assertTrue(found)

if __name__=='__main__':unittest.main()
