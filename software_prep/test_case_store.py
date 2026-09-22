"""Meaningful checks of service-case accumulation. No model calls or outcome accuracy claims."""
from pathlib import Path
import copy
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from case_store import Actor,CaseStore,AccessDenied,Conflict
from validate_input import validate_input,derive_six_lines

ROOT=Path(__file__).parent
BASE={'question':'这辆车能否满足日常出行需要？','lines':['young_yang','young_yin','old_yang','old_yin','young_yang','young_yin']}
HASHES={'source_hash':'a'*64,'rules_digest':'b'*64,'prompt_digest':'c'*64,'engine_build':'test-fixture-only'}

class Clock:
    def __init__(self):self.value=dt.datetime(2026,9,17,12,0,tzinfo=dt.timezone.utc)
    def __call__(self):
        self.value+=dt.timedelta(seconds=1)
        return self.value.isoformat().replace('+00:00','Z')

class CaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=CaseStore(Path(self.tmp.name)/'cases.sqlite',clock=Clock())
        self.actor=Actor('owner-test-A','session-test-A');self.other=Actor('owner-test-B','session-test-B')
        self.case=self.store.create_case(self.actor,BASE,idempotency_key='create')['case_id']
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def run_start(self,key='run',case_id=None,**extra):return self.store.start_analysis(self.actor,case_id or self.case,**HASHES,idempotency_key=key,**extra)
    def export(self):return self.store.export_case(self.actor,self.case)

    def test_01_minimal_entry_and_line_transform(self):
        """CASE-01 两字段入口可创建，第三四爻动变正确"""
        self.assertTrue(validate_input(BASE)['valid'])
        self.assertEqual(derive_six_lines(BASE)['changed_bits'],[1,0,0,1,1,0])
        self.assertEqual(derive_six_lines(BASE)['moving_line_numbers'],[3,4])
        self.assertEqual(self.export()['original_input'],BASE)
    def test_02_unknown_cast_time_not_recorded_time(self):
        """CASE-02 录入时间来自服务器，实际时间未知保持空"""
        record=self.export();context=record['revisions'][0]['time_context']
        self.assertIsNone(context['actual_cast_time']);self.assertEqual(context['precision'],'unknown')
        self.assertEqual(context['provenance'],'unknown');self.assertEqual(record['recorded_at'],'2026-09-17T12:00:01Z')
    def test_03_known_time_provenance(self):
        """CASE-03 已知起卦时间与录入时间分别保存"""
        value={**BASE,'actual_cast_time':'2026-08-01T09:30:15+08:00'}
        case=self.store.create_case(self.actor,value,idempotency_key='known')['case_id']
        record=self.store.export_case(self.actor,case);context=record['revisions'][0]['time_context']
        self.assertEqual(context['actual_cast_time'],value['actual_cast_time']);self.assertNotEqual(context['actual_cast_time'],record['recorded_at'])
        self.assertEqual(context['provenance'],'user_supplied')
    def test_04_intake_failure_auto_retained_without_unrelated_values(self):
        """CASE-04 无效请求也留服务错误，剔除额外字段值"""
        bad={**BASE,'lines':BASE['lines'][:5],'unrelated_secret':'do-not-store-this-value'}
        result=self.store.create_case(self.actor,bad,idempotency_key='bad')
        self.assertFalse(result['accepted'])
        failures=self.store.export_intake_failures(self.actor)
        self.assertEqual(len(failures),1);self.assertNotIn('do-not-store-this-value',json.dumps(failures))
        self.assertEqual(self.store.export_intake_failures(self.other),[])
    def test_05_input_rejects_metadata_and_missing_movement(self):
        """CASE-05 卦名和仅阴阳不可代替四象，客户端不写元数据"""
        for mutation in ({'lines':'乾为天'},{'lines':['yang']*6},{'recorded_at':'2026-09-17T12:00:00Z'},{'owner_id':'intruder'},{'raw_values':[[2,2,3]]*6}):
            with self.subTest(mutation=mutation):self.assertFalse(validate_input({**BASE,**mutation})['valid'])
    def test_06_create_idempotency_and_conflict(self):
        """CASE-06 相同幂等键重试不重复，不同内容冲突"""
        repeated=self.store.create_case(self.actor,BASE,idempotency_key='create')
        self.assertEqual(repeated['case_id'],self.case);self.assertEqual(len(self.store.list_cases(self.actor)),1)
        with self.assertRaises(Conflict):self.store.create_case(self.actor,{**BASE,'question':'别的问题'},idempotency_key='create')
    def test_07_owner_boundary(self):
        """CASE-07 不同owner不能读、改或追加他人案例"""
        with self.assertRaises(AccessDenied):self.store.export_case(self.other,self.case)
        with self.assertRaises(AccessDenied):self.store.revise_case(self.other,self.case,BASE,reason='修正',expected_revision_seq=1,idempotency_key='unauthorized')
        with self.assertRaises(AccessDenied):self.store.add_feedback(self.other,self.case,reported_outcome='外来反馈',idempotency_key='bad-fb')
        self.assertEqual(self.store.list_cases(self.other),[])
    def test_08_question_correction_preserves_original_and_run_snapshot(self):
        """CASE-08 改题追加revision，原问题和旧运行快照不变"""
        run=self.run_start();changed={**BASE,'question':'这辆车作为待出售资产值不值得继续持有？'}
        self.store.revise_case(self.actor,self.case,changed,reason='关注点改为资产持有',expected_revision_seq=1,idempotency_key='revise')
        record=self.export();self.assertEqual(len(record['revisions']),2)
        self.assertEqual(record['original_input']['question'],BASE['question'])
        self.assertEqual(record['analysis_runs'][0]['input_snapshot']['input']['question'],BASE['question'])
        self.assertEqual(record['analysis_runs'][0]['input_snapshot_id'],run['input_snapshot_id'])
        with self.assertRaises(Conflict):self.store.revise_case(self.actor,self.case,BASE,reason='旧客户端提交',expected_revision_seq=1,idempotency_key='stale-revise')
    def test_09_context_snapshot_not_retroactively_changed(self):
        """CASE-09 澄清和背景追加后仅新运行取得新事实"""
        first=self.run_start('first')
        self.store.append_context_event(self.actor,self.case,event_type='clarification_answer',content={'text':'我关心通勤使用','source':'user'},idempotency_key='clarify')
        second=self.run_start('second',parent_run_id=first['analysis_run_id'])
        runs=self.export()['analysis_runs'];by_id={r['analysis_run_id']:r for r in runs}
        self.assertEqual(by_id[first['analysis_run_id']]['input_snapshot']['context_events'],[])
        self.assertEqual(len(by_id[second['analysis_run_id']]['input_snapshot']['context_events']),1)
        self.assertNotEqual(first['input_snapshot_id'],second['input_snapshot_id'])
    def test_10_ai_failures_and_adopted_output_retained(self):
        """CASE-10 无效AI输出与有效采纳输出均累计保留"""
        run=self.run_start()['analysis_run_id']
        self.store.add_ai_event(self.actor,self.case,run,stage='interpretation',attempt_id='try1',raw_output='not json',parse_status='invalid_json',validation_errors=['invalid json'],idempotency_key='ai1')
        self.store.add_ai_event(self.actor,self.case,run,stage='interpretation',attempt_id='try2',raw_output='{"status":"unresolved"}',parse_status='parsed',validation_errors=[],adopted_output={'status':'unresolved'},model_run_metadata={'model_id':'engineering-test'},idempotency_key='ai2')
        events=self.export()['analysis_runs'][0]['ai_events'];self.assertEqual(len(events),2)
        self.assertEqual(events[0]['attempt']['raw_output'],'not json');self.assertTrue(events[1]['attempt']['adopted_output_digest'])
        with self.assertRaises(ValueError):self.store.add_ai_event(self.actor,self.case,run,stage='report',attempt_id='bad',raw_output='bad',parse_status='invalid_json',validation_errors=['bad'],adopted_output={'x':1},idempotency_key='ai-bad')
    def test_11_partial_unresolved_failed_are_terminal_records(self):
        """CASE-11 部分、未决、失败均生成终态记录而非遗漏"""
        for status in ('partial','unresolved','failed'):
            run=self.run_start(status)['analysis_run_id']
            self.store.finish_analysis(self.actor,self.case,run,status=status,unresolved=['缺适用规则'] if status!='failed' else [],error={'code':'PROVIDER_UNAVAILABLE'} if status=='failed' else None,idempotency_key='finish-'+status)
        self.assertEqual({r['status'] for r in self.export()['analysis_runs']},{'partial','unresolved','failed'})
    def test_12_report_snapshot_and_feedback_do_not_overwrite(self):
        """CASE-12 结果反馈追加，原报告及当时依据不被覆盖"""
        run=self.run_start()['analysis_run_id'];report={'text':'工程样例：当前资料只能说明已录入动爻。'}
        self.store.finish_analysis(self.actor,self.case,run,status='completed',report=report,chart_snapshot={'base_bits':[1,0,1,0,1,0]},evidence=[{'rule_id':'casting.four_states'}],validation={'scope':'storage fixture'},idempotency_key='finish')
        original=copy.deepcopy(self.export()['analysis_runs'][0])
        self.store.add_feedback(self.actor,self.case,analysis_run_id=run,reported_outcome='用户自述结果另有变化',occurred_at='2026-09-18T09:00:00+08:00',idempotency_key='feedback')
        self.assertEqual(self.export()['analysis_runs'][0],original)
        with self.assertRaises(Conflict):self.store.finish_analysis(self.actor,self.case,run,status='completed',report={'text':'改写'},idempotency_key='overwrite')
    def test_13_feedback_corrections_and_verification(self):
        """CASE-13 反馈更正保留旧记录，发生时间与核实程度分别保存"""
        first=self.store.add_feedback(self.actor,self.case,reported_outcome='我说错了时间',occurred_at=None,idempotency_key='f1')['feedback_id']
        self.store.add_feedback(self.actor,self.case,reported_outcome='经查凭证发生在此前一天',occurred_at='2026-09-10T09:00:00+08:00',verification_status='externally_supported',verification_method='服务人员核对用户提供的凭证；工程测试桩',supersedes_feedback_id=first,idempotency_key='f2')
        feedback=self.export()['feedback'];self.assertEqual(len(feedback),2);self.assertEqual(feedback[1]['supersedes_feedback_id'],first)
        self.assertIsNone(feedback[0]['occurred_at']);self.assertNotEqual(feedback[1]['occurred_at'],feedback[1]['recorded_at'])
        self.assertEqual(feedback[0]['verification_status'],'self_reported')
    def test_14_no_feedback_is_not_failure_or_success(self):
        """CASE-14 无反馈不会产生结果标签或准确率"""
        run=self.run_start()['analysis_run_id'];self.store.finish_analysis(self.actor,self.case,run,status='unresolved',unresolved=['等待资料'],idempotency_key='finish')
        record=self.export();self.assertEqual(record['feedback'],[]);self.assertEqual(record['analysis_runs'][0]['status'],'unresolved')
        self.assertNotIn('prediction_success',record);self.assertNotIn('accuracy',record)
    def test_15_cross_case_run_and_feedback_references_rejected(self):
        """CASE-15 同一owner也不能把运行或反馈跨案例错接"""
        other_case=self.store.create_case(self.actor,BASE,idempotency_key='second-case')['case_id'];run=self.run_start(case_id=other_case)['analysis_run_id']
        fb=self.store.add_feedback(self.actor,other_case,reported_outcome='另案结果',idempotency_key='other-feedback')['feedback_id']
        with self.assertRaises(AccessDenied):self.store.finish_analysis(self.actor,self.case,run,status='failed',error={'code':'x'},idempotency_key='cross-run')
        with self.assertRaises(AccessDenied):self.store.add_feedback(self.actor,self.case,reported_outcome='错接',supersedes_feedback_id=fb,idempotency_key='cross-feedback')
    def test_16_sql_history_update_and_delete_blocked(self):
        """CASE-16 基础数据库阻止意外覆盖和直接删除历史"""
        with self.assertRaises(sqlite3.IntegrityError):self.store.db.execute('UPDATE case_revisions SET reason=? WHERE case_id=?',('覆盖',self.case))
        with self.assertRaises(sqlite3.IntegrityError):self.store.db.execute('DELETE FROM cases WHERE case_id=?',(self.case,))
    def test_17_failed_write_rolls_back(self):
        """CASE-17 越权写入失败后事务回滚，不污染正常重试"""
        with self.assertRaises(AccessDenied):self.store.append_context_event(self.other,self.case,event_type='background',content={'text':'越权'},idempotency_key='blocked')
        own=self.store.create_case(self.other,BASE,idempotency_key='other-create')['case_id']
        self.store.append_context_event(self.other,own,event_type='background',content={'text':'自己的事实'},idempotency_key='blocked')
        self.assertEqual(self.export()['context_events'],[])
    def test_18_private_service_archive_not_training_or_public(self):
        """CASE-18 服务记录自动积累但公开和训练用途默认关闭"""
        self.assertEqual(self.export()['usage_policy'],{'service_case_archive':True,'public_use':False,'training_use':False})
    def test_19_digests_and_expected_revision_required_context(self):
        """CASE-19 溯源摘要保留，过期revision不生成新解读"""
        with self.assertRaises(ValueError):self.store.start_analysis(self.actor,self.case,**{**HASHES,'rules_digest':'not-a-hash'},idempotency_key='bad-hash')
        with self.assertRaises(Conflict):self.run_start(expected_revision_seq=5)
        run=self.run_start('good');record=self.export()['analysis_runs'][0]
        for key,value in HASHES.items():self.assertEqual(record[key],value)
        self.assertEqual(run['analysis_run_id'],record['analysis_run_id'])
    def test_20_feedback_retry_is_idempotent(self):
        """CASE-20 重复回传同一反馈不会重复计案例数据"""
        kwargs={'reported_outcome':'尚未发生，继续等待','idempotency_key':'retry-feedback'}
        a=self.store.add_feedback(self.actor,self.case,**kwargs);b=self.store.add_feedback(self.actor,self.case,**kwargs)
        self.assertEqual(a,b);self.assertEqual(len(self.export()['feedback']),1)
    def test_21_partial_date_remains_date_fact(self):
        """CASE-21 只知日期作为相关事实保存，不伪造午夜"""
        self.store.append_context_event(self.actor,self.case,event_type='background',content={'fact':'actual_cast_date','value':'2026-09-10','precision':'day','provenance':'user_reported'},idempotency_key='date-only')
        record=self.export();self.assertIsNone(record['revisions'][0]['time_context']['actual_cast_time'])
        self.assertEqual(record['context_events'][0]['content']['precision'],'day')

class JsonResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.rows=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.rows.append({'test_id':test._testMethodName,'title':test.shortDescription(),'status':'passed','evidence':'test_case_store.py:'+test._testMethodName})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.rows.append({'test_id':test._testMethodName,'title':test.shortDescription(),'status':'failed','evidence':self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err);self.rows.append({'test_id':test._testMethodName,'title':test.shortDescription(),'status':'error','evidence':self._exc_info_to_string(err,test)})

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2,resultclass=JsonResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(CaseTests))
    report={'scope':'SQLite service accumulation and minimal input checks; no app/API/auth-provider/model/outcome-accuracy validation','tests_run':result.testsRun,'passed':sum(x['status']=='passed' for x in result.rows),'failed':len(result.failures)+len(result.errors),'tests':result.rows}
    (ROOT/'case_store_test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with tempfile.TemporaryDirectory() as td:
        store=CaseStore(Path(td)/'example.sqlite',clock=Clock());actor=Actor('engineering-example-owner','engineering-example-session')
        case=store.create_case(actor,BASE,idempotency_key='example')['case_id']
        run=store.start_analysis(actor,case,**HASHES,idempotency_key='example-run')['analysis_run_id']
        store.finish_analysis(actor,case,run,status='unresolved',unresolved=['工程示例，没有执行完整领域判断'],idempotency_key='example-finish')
        (ROOT/'case_record_example.json').write_text(json.dumps(store.export_case(actor,case),ensure_ascii=False,indent=2)+'\n');store.close()
    raise SystemExit(0 if result.wasSuccessful() else 1)
