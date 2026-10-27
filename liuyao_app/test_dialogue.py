"""Conversation routing, editable defaults and cross-skill state; no paid calls."""
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from case_store import Actor, AccessDenied, Conflict
from .chat_router import route, casting_defaults
from .server import Application
from .test_conversation import INPUT, saved_analysis
from .test_rule_installation import public_placeholder_rows
from .rulebook import save_rules


class RoutingChecks(unittest.TestCase):
    def test_explicit_cast_opens_card_with_current_solar_defaults(self):
        r=route('我想起一卦，问明年能否买房。',{})
        self.assertEqual(r['action'],'cast');self.assertEqual(r['prefill']['time_policy'],'current')
        self.assertNotIn('lines',r['prefill']);self.assertNotIn('cast_location',r['prefill'])

    def test_ambiguous_work_question_is_clarified(self):
        r=route('这份工作适不适合我？',{})
        self.assertEqual(r['action'],'clarify');self.assertEqual(len(r['choices']),2)

    def test_questions_about_casting_do_not_request_a_new_cast(self):
        self.assertEqual(route('起卦是什么意思？',{})['action'],'chat')
        self.assertEqual(route('怎么又重新起卦了？',{'active_case':'case_1','last_skill':'liuyao'})['action'],'feedback')

    def test_housing_fields_are_derived_from_actual_user_statements(self):
        v=casting_defaults('我想起一卦，选A房，给我们一家三口长期自住，尚未入住，我本人起卦。')
        b=v['buzhai']
        self.assertEqual((b['site'],b['role'],b['residence'],b['site_kind']),('A房','host','not_occupied','yang'))
        self.assertIn('一家三口',b['beneficiary']);self.assertEqual(b['proposal'],'长期自住')

    def test_unknown_casting_role_and_residence_remain_unknown(self):
        b=casting_defaults('我想卜宅，看看A房适不适合。')['buzhai']
        self.assertEqual(b['role'],'other');self.assertEqual(b['residence'],'unknown')
        self.assertEqual(b['beneficiary'],'')
        self.assertEqual(casting_defaults('我没亲自起卦，问A房自住。')['buzhai']['role'],'other')

    def test_multiple_properties_are_not_silently_reduced_to_first_one(self):
        self.assertEqual(casting_defaults('想卜宅比较A房和B房。')['buzhai']['site'],'')

    def test_later_corrections_take_precedence_and_keep_original_question(self):
        first=casting_defaults('我想起一卦选A房自住，尚未入住，我本人起卦。')
        later=casting_defaults('不是本人，是朋友代起卦。我们已经入住了。',first)
        self.assertEqual(later['question'],first['question'])
        self.assertEqual(later['buzhai']['role'],'other');self.assertEqual(later['buzhai']['residence'],'occupied')

    def test_house_target_is_not_invented_from_casting_gps(self):
        b=casting_defaults('我人在成都，想卜宅看看选房。')['buzhai']
        self.assertEqual(b['site'],'');self.assertNotIn('cast_location',b)

    def test_ordinary_work_cast_has_no_housing_fields(self):
        self.assertIsNone(casting_defaults('我想起一卦，问这份工作。')['buzhai'])

    def test_historical_cast_does_not_default_to_current_time_or_gps(self):
        self.assertEqual(casting_defaults('补录昨晚摇的卦')['time_policy'],'historical')
        self.assertEqual(casting_defaults('起卦时间不知道')['time_policy'],'unknown')
        self.assertEqual(route('补录昨天起的卦，问工作。',{})['prefill']['time_policy'],'historical')

    def test_negative_cast_request_does_not_start_cast(self):
        self.assertEqual(route('不要起卦，解释一下资料',{})['action'],'knowledge')

    def test_followup_preserves_saved_case_and_can_switch_to_knowledge(self):
        c={'active_case':'case_1','last_skill':'liuyao'}
        self.assertEqual(route('这对我有什么影响？',c)['action'],'followup')
        self.assertEqual(route('根据知识库解释一下这个概念',c)['action'],'knowledge')
        self.assertEqual(route('回到刚才的卦，继续说',dict(c,last_skill='knowledge'))['action'],'followup')
        self.assertEqual(route('卜宅里的世爻是什么意思？',c)['action'],'followup')
        self.assertEqual(route('再起一卦问工作',c)['action'],'cast')

    def test_pending_card_accepts_conversation_supplements(self):
        first=casting_defaults('我想起一卦选A房')
        c={'pending_cast':{'turn_id':'t','prefill':first},'last_skill':'liuyao'}
        r=route('我们一家三口，还没入住。',c)
        self.assertEqual(r['update_target'],'t');self.assertEqual(r['prefill']['buzhai']['residence'],'not_occupied')

    def test_housing_stage_and_yin_target_are_scoped(self):
        self.assertEqual(casting_defaults('我想卜宅，验证整改方案')['buzhai']['stage'],'remedy_check')
        self.assertEqual(casting_defaults('想起一卦问祖坟安葬')['buzhai']['site_kind'],'yin')


class DialogueChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(self.temp.name)
        self.app.config=lambda:{'providers':[{'id':'deepseek','models':['test-model'],'configured':True},
                                             {'id':'demo','models':['local-demo'],'configured':True}]}
        self.runtime=self.app.workbench;self.service=self.runtime.dialogues;self.owner='owner'
        self.dialogue=self.service.create(self.owner,'一个连续会话','create')['dialogue_id']
        self.seq=0

    def tearDown(self):self.app.close();self.temp.cleanup()

    def wait(self,job):
        for _ in range(500):
            result=self.runtime.store.job(self.owner,job)
            if result['status'] not in ('queued','running'):return result
            time.sleep(.01)
        self.fail('task did not finish')

    def send(self,text,mode='auto',idem=None,provider='demo',model='local-demo'):
        self.seq+=1
        body={'text':text,'mode':mode,'provider':provider,'model':model}
        return self.service.enqueue(self.owner,self.dialogue,body,idem or 'send-'+str(self.seq))['job_id']

    def test_cast_is_offline_and_idempotent_after_lost_ack(self):
        with patch('liuyao_app.workbench.generate_json') as call:
            job=self.send('我想起一卦问工作。',idem='same');r=self.wait(job)
            self.assertEqual(self.send('我想起一卦问工作。',idem='same'),job)
        self.assertEqual(call.call_count,0);self.assertEqual(r['result']['action'],'cast')
        self.assertEqual(len(self.service.detail(self.owner,self.dialogue)['turns']),1)
        with self.assertRaises(Conflict):self.send('不同内容',idem='same')

    def test_conversation_prefills_are_retained_across_restart(self):
        self.wait(self.send('我想卜宅选A房。'));self.wait(self.send('尚未入住，给我们一家三口长期自住。'))
        self.app.close();self.app=Application(self.temp.name);self.runtime=self.app.workbench;self.service=self.runtime.dialogues
        detail=self.service.detail(self.owner,self.dialogue)
        self.assertEqual(len(detail['turns']),2)
        self.assertEqual(detail['context']['pending_cast']['prefill']['buzhai']['residence'],'not_occupied')

    def test_draft_preserves_user_edits_separately_from_inferred_defaults(self):
        self.wait(self.send('我想卜宅选A房。'))
        original=self.service.detail(self.owner,self.dialogue)['turns'][0]
        body={'card_id':original['turn_id'],'fields':{'buzhai-site':{'value':'用户手填的B房','checked':False}},'solar_input':{'time_basis':'true_solar'}}
        self.service.draft(self.owner,self.dialogue,body,'draft')
        self.wait(self.send('给我们一家三口住。'))
        detail=self.service.detail(self.owner,self.dialogue)
        self.assertEqual(detail['context']['drafts'][original['turn_id']]['fields']['buzhai-site']['value'],'用户手填的B房')

    def test_binding_saved_case_selects_followup_without_new_analysis(self):
        save_rules(self.app.rules_directory,public_placeholder_rows())
        cases=self.app.store();actor=Actor(self.owner,'test')
        case=cases.create_case(actor,INPUT,idempotency_key='case')['case_id'];run=saved_analysis(cases,actor,case);cases.close()
        self.service.bind_case(self.owner,self.dialogue,{'case_id':case,'analysis_run_id':run},'bind')
        def response(*args,**kwargs):
            return {'parsed_json':{'answer':'沿用当前卦盘解释。','requires_reanalysis':False}}
        with patch('liuyao_app.conversation.generate_json',side_effect=response) as call:
            result=self.wait(self.send('现在如何理解？',provider='deepseek',model='test-model'))
        self.assertEqual(result['result']['action'],'followup');self.assertEqual(call.call_count,1)
        cases=self.app.store()
        try:self.assertEqual(len(cases.export_case(actor,case)['analysis_runs']),1)
        finally:cases.close()

    def test_knowledge_and_cast_can_coexist_in_one_dialogue(self):
        self.wait(self.send('我想起一卦问工作。'))
        self.runtime.store.add_document(self.owner,{'title':'五行','text':'水表示系统的储备。木表示探察。'},'document')
        answer=self.wait(self.send('根据知识库解释水。'))
        self.assertEqual(answer['result']['action'],'knowledge');self.assertTrue(answer['result']['citations'])
        detail=self.service.detail(self.owner,self.dialogue)
        self.assertIn('pending_cast',detail['context'])
        self.assertEqual(detail['context']['last_skill'],'knowledge')

    def test_owner_cannot_read_or_bind_another_owners_records(self):
        with self.assertRaises(AccessDenied):self.service.detail('other',self.dialogue)
        with self.assertRaises(AccessDenied):self.service.enqueue('other',self.dialogue,{'text':'起一卦','mode':'auto','provider':'demo','model':'local-demo'},'other')
        self.assertEqual(self.service.listing('other'),[])

    def test_feedback_is_linked_to_the_message_and_survives_reopen(self):
        self.wait(self.send('回答太长，希望简洁一点'))
        turn=self.service.detail(self.owner,self.dialogue)['turns'][0]
        issue=self.runtime.store.create_issue(self.owner,{'skill_id':'liuyao','title':'回答太长','description':'请简洁'},'issue')['issue_id']
        self.service.link_feedback(self.owner,self.dialogue,{'turn_id':turn['turn_id'],'issue_id':issue},'link')
        self.assertEqual(self.service.detail(self.owner,self.dialogue)['turns'][0]['result']['issue_id'],issue)

    def test_interrupted_conversation_is_not_automatically_replayed(self):
        with patch.object(self.app.pool,'submit'):
            job=self.send('我想起一卦问工作。')
        self.runtime.store.recover()
        self.assertEqual(self.runtime.store.job(self.owner,job)['status'],'failed')
        self.assertEqual(self.service.detail(self.owner,self.dialogue)['turns'][0]['status'],'failed')

    def test_completed_case_answer_wins_after_cross_database_ack_loss(self):
        save_rules(self.app.rules_directory,public_placeholder_rows())
        cases=self.app.store();actor=Actor(self.owner,'test')
        case=cases.create_case(actor,INPUT,idempotency_key='case')['case_id'];run=saved_analysis(cases,actor,case);cases.close()
        self.service.bind_case(self.owner,self.dialogue,{'case_id':case,'analysis_run_id':run},'bind')
        with patch.object(self.app.pool,'submit'):
            job=self.send('继续解释一下',provider='deepseek',model='test-model')
        with self.runtime.store.db() as db:
            payload=json.loads(db.execute('SELECT payload FROM wb_jobs WHERE job_id=?',(job,)).fetchone()[0])
        with patch('liuyao_app.conversation.generate_json',return_value={'parsed_json':{'answer':'已经保存的回复。','requires_reanalysis':False}}) as call:
            self.service.execute(self.owner,payload)
            self.runtime.store.recover()
        result=self.runtime.store.job(self.owner,job)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['result']['answer'],'已经保存的回复。')
        self.assertEqual(call.call_count,1)


if __name__=='__main__':unittest.main()
