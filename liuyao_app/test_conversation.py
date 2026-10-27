"""Conversation storage, ownership, single-call requests and restart behavior; offline."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from case_store import Actor, CaseStore, AccessDenied, Conflict
from . import conversation
from .pipeline import calculate_chart
from .providers import ProviderError, generate_json, TransportResponse, DEFAULT_DEEPSEEK_MODEL
from .server import Application
from . import test_server as http_fixture

INPUT={'question':'这份工作是否合适？','lines':['young_yang']*6,
       'actual_cast_time':'2026-10-24T12:00:00+08:00','time_basis':'true_solar',
       'cast_location':{'longitude':104.06,'source':'manual'}}


def saved_analysis(store,actor,case_id,key='initial'):
    run=store.start_analysis(actor,case_id,source_hash='1'*64,rules_digest='2'*64,prompt_digest='3'*64,
        engine_build='test',idempotency_key=key)['analysis_run_id']
    chart=calculate_chart(INPUT,include_experimental=False)
    report={'stage_outputs':{'interpretation':{'conclusion':{'answer':'需先确认待遇','limits':['待遇未知']}}},
            'user_report':{'conclusion':{'answer':'需先确认待遇'}},'status':'completed'}
    store.finish_analysis(actor,case_id,run,status='completed',chart_snapshot=chart,report=report,idempotency_key=key+'-finish')
    return run


class ConversationChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'cases.sqlite'
        self.store=CaseStore(self.path);self.actor=Actor('owner','session')
        self.case=self.store.create_case(self.actor,copy.deepcopy(INPUT),idempotency_key='case')['case_id']
        self.run=saved_analysis(self.store,self.actor,self.case)

    def tearDown(self):self.store.close();self.temp.cleanup()

    def turn(self,text='刚才的条件指什么？',key='turn',run=None):
        return conversation.start_turn(self.store,self.actor,self.case,run or self.run,1,text,idempotency_key=key)['turn_id']

    def test_dialogue_uses_saved_chart_and_previous_roles_without_reanalysis(self):
        turn=self.turn()
        calls=[]
        def provider(*args,**kwargs):
            calls.append((args,kwargs))
            return {'parsed_json':{'answer':'待遇尚未确认，需要先明确。','requires_reanalysis':False}}
        before=self.store.export_case(self.actor,self.case)['analysis_runs']
        conversation.reply(self.store,self.actor,self.case,turn,'deepseek','test',provider_call=provider)
        second=self.turn('现在待遇已确认，会有什么变化？','second')
        conversation.reply(self.store,self.actor,self.case,second,'deepseek','test',provider_call=provider)
        self.assertEqual(len(calls),2)
        history=calls[1][1]['conversation_history']
        self.assertEqual([m['role'] for m in history],['user','assistant','user'])
        self.assertEqual(history[1]['content'],'待遇尚未确认，需要先明确。')
        self.assertEqual(calls[0][0][3]['saved_chart']['calendar']['time_basis'],'true_solar')
        self.assertEqual(self.store.export_case(self.actor,self.case)['analysis_runs'],before)
        texts=[e['content']['text'] for e in self.store.export_case(self.actor,self.case)['context_events']]
        self.assertNotIn(history[1]['content'],texts)
        self.assertIn(history[2]['content'],texts)

    def test_reopen_and_export_preserve_dialogue_but_do_not_expose_prompts(self):
        turn=self.turn();conversation.reply(self.store,self.actor,self.case,turn,'demo','local-demo')
        self.store.close();self.store=CaseStore(self.path)
        exported=self.store.export_case(self.actor,self.case)
        self.assertEqual(exported['conversation_turns'][0]['status'],'completed')
        self.assertNotIn('context_json',exported['conversation_turns'][0])
        try:import jsonschema
        except ImportError:return
        schema=json.loads((Path(__file__).parents[1]/'software_prep/case_record_schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(exported)

    def test_idempotency_and_history_are_bound_to_selected_analysis(self):
        first=self.turn();self.assertEqual(self.turn(),first)
        with self.assertRaises(Conflict):self.turn('不同内容')
        conversation.reply(self.store,self.actor,self.case,first,'demo','local-demo')
        other=saved_analysis(self.store,self.actor,self.case,'other')
        second=self.turn('新分析的问题','second',other)
        row=self.store.db.execute('SELECT context_json FROM conversation_turns WHERE turn_id=?',(second,)).fetchone()
        self.assertEqual(len(json.loads(row[0])['history']),1)

    def test_ownership_revision_and_run_case_are_validated(self):
        with self.assertRaises(AccessDenied):conversation.list_turns(self.store,Actor('other','s'),self.case)
        other=self.store.create_case(self.actor,{**INPUT,'question':'另一卦'},idempotency_key='other')['case_id']
        with self.assertRaises(AccessDenied):conversation.start_turn(self.store,self.actor,other,self.run,1,'问',idempotency_key='x')
        self.store.revise_case(self.actor,self.case,{**INPUT,'question':'改问别人'},reason='改问',expected_revision_seq=1,idempotency_key='rev')
        with self.assertRaises(Conflict):self.turn()

    def test_provider_failure_is_saved_and_not_retried_automatically(self):
        turn=self.turn();calls=[]
        def provider(*args,**kwargs):calls.append(1);raise ProviderError('timeout','请求超时')
        result=conversation.reply(self.store,self.actor,self.case,turn,'deepseek','test',provider_call=provider)
        self.assertEqual(result['status'],'failed');self.assertEqual(len(calls),1)
        self.assertEqual(conversation.list_turns(self.store,self.actor,self.case)[0]['result']['error']['code'],'timeout')

    def test_invalid_reply_is_not_adopted(self):
        turn=self.turn()
        result=conversation.reply(self.store,self.actor,self.case,turn,'deepseek','test',
            provider_call=lambda *a,**k:{'parsed_json':{'answer':'','requires_reanalysis':'yes'}})
        self.assertEqual(result['status'],'failed')

    def test_user_followup_is_in_next_full_analysis_snapshot(self):
        self.turn('补充：待遇已确认')
        new=saved_analysis(self.store,self.actor,self.case,'new')
        snapshot=next(r for r in self.store.export_case(self.actor,self.case)['analysis_runs'] if r['analysis_run_id']==new)['input_snapshot']
        self.assertIn('补充：待遇已确认',[e['content']['text'] for e in snapshot['context_events']])


class ConversationHTTPChecks(unittest.TestCase):
    request=http_fixture.HTTPChecks.request
    wait_job=http_fixture.HTTPChecks.wait_job
    fake_pipeline=http_fixture.HTTPChecks.fake_pipeline

    def setUp(self):
        http_fixture.HTTPChecks.setUp(self)
        store=self.app.store()
        self.actor=self.app.actor(self.cookie.split('=',1)[1])
        self.case=store.create_case(self.actor,INPUT,idempotency_key='case')['case_id']
        self.run=saved_analysis(store,self.actor,self.case);store.close()

    def tearDown(self):http_fixture.HTTPChecks.tearDown(self)

    def test_http_turn_is_one_job_and_one_provider_call_even_after_lost_ack(self):
        body={'provider':'deepseek','model':'test-model','text':'刚才的条件？',
              'analysis_run_id':self.run,'expected_revision_seq':1}
        calls=[]
        def provider(*a,**k):calls.append(1);return {'parsed_json':{'answer':'先确认待遇。','requires_reanalysis':False}}
        with patch('liuyao_app.conversation.generate_json',side_effect=provider):
            path='/api/cases/'+self.case+'/conversation'
            status,_,job=self.request('POST',path,body,headers={'X-Idempotency-Key':'same-ack'})
            self.assertEqual(status,202,job)
            self.assertEqual(self.wait_job(job['job_id'])['kind'],'conversation')
            self.assertEqual(self.request('POST',path,body,headers={'X-Idempotency-Key':'same-ack'})[2],job)
        self.assertEqual(len(calls),1);self.assertEqual(self.calls,[])
        store=self.app.store()
        try:self.assertEqual(store.db.execute('SELECT count(*) FROM analysis_runs').fetchone()[0],1)
        finally:store.close()

    def test_calendar_preview_and_location_validation_need_no_rules_or_model(self):
        data={k:INPUT[k] for k in ('actual_cast_time','time_basis','cast_location')}
        status,_,value=self.request('POST','/api/calendar',data)
        self.assertEqual(status,200,value);self.assertEqual(value['time_basis'],'true_solar')
        self.assertEqual(self.request('POST','/api/calendar',{**data,'cast_location':{'longitude':181}})[0],400)
        self.assertEqual(self.request('GET','/static/solar-time.js')[0],200)
        self.assertEqual(self.calls,[])

    def test_restart_marks_pending_turn_failed_without_replay(self):
        store=self.app.store()
        turn=conversation.start_turn(store,self.actor,self.case,self.run,1,'等待中的追问',idempotency_key='pending')['turn_id']
        store.close();self.app.recover()
        store=self.app.store()
        record=next(t for t in conversation.list_turns(store,self.actor,self.case) if t['turn_id']==turn)
        store.close();self.assertEqual(record['status'],'failed');self.assertEqual(record['result']['error']['code'],'INTERRUPTED')

    def test_restart_recovers_saved_answer_when_job_acknowledgement_was_lost(self):
        body={'provider':'deepseek','model':'test-model','text':'追问',
              'analysis_run_id':self.run,'expected_revision_seq':1}
        with patch('liuyao_app.conversation.generate_json',return_value={'parsed_json':{'answer':'已保存的回答','requires_reanalysis':False}}):
            _,_,job=self.request('POST','/api/cases/'+self.case+'/conversation',body)
            self.wait_job(job['job_id'])
        self.app.update_job(job['job_id'],status='running',result=None)
        self.app.recover()
        restored=self.app.get_job(self.actor,job['job_id'])
        self.assertEqual(restored['status'],'completed')
        self.assertEqual(restored['result']['conversation']['answer'],'已保存的回答')


class ConversationTransportChecks(unittest.TestCase):
    def test_provider_receives_explicit_user_assistant_history_in_order(self):
        history=[{'role':'user','content':'上个问题'},{'role':'assistant','content':'上一条回答'},{'role':'user','content':'本轮追问'}]
        calls=[]
        def transport(url,headers,body,timeout):
            calls.append(body)
            return TransportResponse(200,{},json.dumps({'choices':[{'message':{'content':'{"answer":"回复","requires_reanalysis":false}'},'finish_reason':'stop'}]}).encode())
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test-key'},clear=True):
            generate_json('deepseek',DEFAULT_DEEPSEEK_MODEL,'JSON',{'saved_chart':{}},conversation_history=history,transport=transport)
        self.assertEqual(calls[0]['messages'][2:],history)
        with self.assertRaises(ProviderError):
            generate_json('mock','offline-json','JSON',{},conversation_history=[{'role':'system','content':'bad'}])


if __name__=='__main__':unittest.main()
