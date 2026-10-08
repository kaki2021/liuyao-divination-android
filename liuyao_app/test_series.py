"""Series persistence and HTTP behavior; isolated storage, no model or rule pack."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
try:
    import jsonschema
except ImportError:
    jsonschema = None

from case_store import Actor, CaseStore, AccessDenied, Conflict, encoded, content_digest
from . import series_store
from . import test_server as http_fixture

INPUT = {'question':'今年适合换工作吗？','lines':['young_yang','young_yin','old_yang','old_yin','young_yang','young_yin']}
HASHES = dict(source_hash='a'*64,rules_digest='b'*64,prompt_digest='c'*64,engine_build='series-fixture')


class SeriesStoreChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'cases.sqlite'
        self.store = CaseStore(self.path)
        self.actor = Actor('owner-a','session-a')
        self.other = Actor('owner-b','session-b')
        self.root = self.create('root')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self,key,parent=None,**extra):
        return self.store.create_case(self.actor,{**INPUT,'question':key},idempotency_key=key,parent_case_id=parent,**extra)['case_id']

    def start(self,case_id,key):
        return self.store.start_analysis(self.actor,case_id,**HASHES,idempotency_key=key)['analysis_run_id']

    def finish(self,case_id,key,answer='有条件可行'):
        run = self.start(case_id,key)
        self.store.finish_analysis(self.actor,case_id,run,status='completed',idempotency_key=key+'-finish',
            report={'stage_outputs':{'interpretation':{'conclusion':{'answer':answer,'key_conditions':['收到正式录用通知'],
                'limits':['前卦的条件判断'],'direction':'favorable'},'uncertainties':[{'impact':'薪资待确认'}]}}})
        return run

    def event(self,case_id,text,key,event_type='background'):
        return self.store.append_context_event(self.actor,case_id,event_type=event_type,content={'text':text},idempotency_key=key)

    def snapshot(self,case_id,run_id):
        return next(r for r in self.store.export_case(self.actor,case_id)['analysis_runs'] if r['analysis_run_id']==run_id)['input_snapshot']

    def test_tree_groups_branches_and_nested_questions(self):
        a=self.create('A公司是否适合？',self.root)
        b=self.create('B公司是否适合？',self.root)
        c=self.create('A公司的薪资如何？',a)
        unrelated=self.create('独立问题')
        data=series_store.detail(self.store,self.actor,self.root)
        self.assertEqual(data['case_count'],4)
        parents={n['case_id']:n['parent_case_id'] for n in data['nodes']}
        self.assertEqual(parents,{self.root:None,a:self.root,b:self.root,c:a})
        self.assertEqual(len(series_store.list_series(self.store,self.actor)),2)
        self.assertEqual(series_store.relation(self.store,self.actor,unrelated)['series_id'],unrelated)

    def test_shared_user_context_has_provenance_and_excludes_other_ai_events(self):
        child=self.create('细问',self.root)
        separate=self.create('独立')
        root_event=self.event(self.root,'正在等正式通知','root-event')
        child_event=self.event(child,'待遇尚未商定','child-event','clarification_answer')
        self.event(self.root,'模型提问不应共享','ai-event','clarification_question')
        self.event(separate,'无关背景','separate-event')
        run=self.start(child,'child-run')
        snapshot=self.snapshot(child,run)
        self.assertEqual({e['event_id'] for e in snapshot['context_events']},{root_event['event_id'],child_event['event_id']})
        self.assertEqual({e['case_id'] for e in snapshot['context_events']},{self.root,child})
        self.assertEqual(snapshot['series_context']['context_sources'][0]['question'],'root')
        # The root sees the child's supplement, but each case export stays local.
        self.assertEqual(len(series_store.detail(self.store,self.actor,self.root)['shared_context_events']),2)
        self.assertEqual(len(self.store.export_case(self.actor,child)['context_events']),1)
        self.store.revise_case(self.actor,child,{**INPUT,'question':'细问','person_info':{'subject':'self','background':'招聘方还未确认薪资'}},
            reason='补充人物背景',expected_revision_seq=1,idempotency_key='person-context')
        from .pipeline import _evidence
        root_run=self.start(self.root,'root-person-run')
        evidence=_evidence(self.snapshot(self.root,root_run),'2026-09-17T12:00:00Z')
        self.assertIn('招聘方还未确认薪资',json.dumps(evidence,ensure_ascii=False))
        self.assertNotIn('模型提问不应共享',json.dumps(evidence,ensure_ascii=False))

    def test_an_analysis_freezes_shared_background_during_sibling_writes(self):
        child=self.create('细问',self.root)
        old=self.start(child,'before')
        saved=copy.deepcopy(self.snapshot(child,old))
        self.event(self.root,'新的进展','after-event')
        self.assertEqual(self.snapshot(child,old),saved)
        new=self.start(child,'after')
        self.assertEqual(len(self.snapshot(child,new)['context_events']),1)
        self.assertEqual(saved['input'],{**INPUT,'question':'细问'})

    def test_parent_analysis_is_selected_and_frozen_with_conditions_and_limits(self):
        first=self.finish(self.root,'parent-one','等待通知后可行')
        child=self.create('细问',self.root,parent_revision_seq=1,parent_analysis_run_id=first)
        self.finish(self.root,'parent-two','后来改变判断')
        run=self.start(child,'child-analysis')
        snapshot=self.snapshot(child,run)
        reference=snapshot['series_context']['ancestors'][0]['analysis_reference']
        self.assertEqual(reference['analysis_run_id'],first)
        self.assertEqual(reference['conclusion']['answer'],'等待通知后可行')
        self.assertEqual(reference['conclusion']['limits'],['前卦的条件判断'])
        self.assertEqual(snapshot['context_events'],[])
        from .pipeline import _evidence
        evidence=_evidence(snapshot,'2026-09-17T12:00:00Z')
        self.assertNotIn('等待通知后可行',json.dumps(evidence,ensure_ascii=False))
        prompt=series_store.prompt_reference(snapshot['series_context'])
        self.assertIn('不属于本次facts',prompt)
        self.assertIn('等待通知后可行',prompt)

    def test_nested_parent_lineage_uses_original_revision(self):
        child=self.create('细问',self.root,parent_revision_seq=1)
        self.store.revise_case(self.actor,self.root,{**INPUT,'question':'后来改了总问'},reason='修正',expected_revision_seq=1,idempotency_key='revision')
        grandchild=self.create('进一步细问',child)
        run=self.start(grandchild,'grandchild')
        refs=self.snapshot(grandchild,run)['series_context']['ancestors']
        self.assertEqual([r['question'] for r in refs],['root','细问'])
        self.assertEqual([r['revision_seq'] for r in refs],[1,1])

    def test_rejects_stale_parent_and_cross_case_analysis_atomically(self):
        independent=self.create('独立')
        foreign_run=self.finish(independent,'foreign-run')
        with self.assertRaises(AccessDenied):self.create('错接',self.root,parent_analysis_run_id=foreign_run)
        with self.assertRaises(Conflict):self.create('过期',self.root,parent_revision_seq=7)
        pending=self.start(self.root,'pending')
        with self.assertRaises(Conflict):self.create('未完成',self.root,parent_analysis_run_id=pending)
        self.assertEqual(len(self.store.list_cases(self.actor)),2)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM case_series').fetchone()[0],2)

    def test_owner_cannot_read_or_join_another_series(self):
        with self.assertRaises(AccessDenied):series_store.detail(self.store,self.other,self.root)
        with self.assertRaises(AccessDenied):series_store.effective_context(self.store,self.other,self.root)
        with self.assertRaises(AccessDenied):self.store.create_case(self.other,INPUT,parent_case_id=self.root,idempotency_key='unauthorized')
        self.assertEqual(series_store.list_series(self.store,self.other),[])
        self.assertEqual(self.store.list_cases(self.other),[])

    def test_child_retry_does_not_duplicate_and_reparenting_conflicts(self):
        a=self.create('细问',self.root,parent_revision_seq=1)
        b=self.create('细问',self.root,parent_revision_seq=1)
        self.assertEqual(a,b)
        other=self.create('独立')
        with self.assertRaises(Conflict):self.create('细问',other,parent_revision_seq=1)
        with self.assertRaises(sqlite3.IntegrityError):self.store.db.execute('UPDATE case_series SET parent_case_id=? WHERE case_id=?',(other,a))
        with self.assertRaises(sqlite3.IntegrityError):self.store.db.execute('DELETE FROM case_series WHERE case_id=?',(a,))

    def test_reopen_keeps_links_and_old_cases_migrate_idempotently(self):
        child=self.create('细问',self.root)
        self.store.close();self.store=CaseStore(self.path)
        self.assertEqual(series_store.relation(self.store,self.actor,child)['parent_case_id'],self.root)
        legacy=Path(self.temp.name)/'legacy.sqlite'
        db=sqlite3.connect(legacy)
        db.executescript(Path('software_prep/case_store.sql').read_text().split('-- A series')[0])
        stamp='2026-09-17T12:00:00Z'
        db.execute('INSERT INTO cases VALUES (?,?,?,?,?)',('legacy',self.actor.owner_id,self.actor.session_id,stamp,encoded(INPUT)))
        db.execute('INSERT INTO case_revisions VALUES (?,?,?,?,?,?,?,?)',('legacy',1,'rev',stamp,'initial','原案例',encoded(INPUT),encoded(CaseStore._time_context(INPUT))))
        db.commit();db.close()
        for _ in range(2):
            migrated=CaseStore(legacy)
            try:
                self.assertEqual(series_store.detail(migrated,self.actor,'legacy')['case_count'],1)
                self.assertEqual(migrated.export_case(self.actor,'legacy')['original_input'],INPUT)
            finally:migrated.close()

    @unittest.skipIf(jsonschema is None,'jsonschema is optional and unavailable')
    def test_new_snapshots_and_legacy_exports_validate_against_case_schema(self):
        child=self.create('细问',self.root)
        self.start(child,'analysis')
        schema=json.loads(Path('software_prep/case_record_schema.json').read_text())
        exported=self.store.export_case(self.actor,child)
        jsonschema.validate(exported,schema)
        del exported['analysis_runs'][0]['input_snapshot']['series_context']
        jsonschema.validate(exported,schema)


class SeriesHTTPChecks(unittest.TestCase):
    # Reuse the offline HTTP fixture, without inheriting its rule-pack tests.
    request=http_fixture.HTTPChecks.request
    fake_pipeline=http_fixture.HTTPChecks.fake_pipeline
    create=http_fixture.HTTPChecks.create

    def setUp(self):
        self.rules=patch('liuyao_app.server.load_rules',return_value=object())
        self.chart=patch('liuyao_app.server.calculate_chart',side_effect=lambda value,_:{'question':value['question']})
        self.rules.start();self.chart.start()
        http_fixture.HTTPChecks.setUp(self)

    def tearDown(self):
        http_fixture.HTTPChecks.tearDown(self)
        self.chart.stop();self.rules.stop()

    def child(self,parent,**extra):
        status,_,result=self.request('POST','/api/cases',{'input':{**INPUT,'question':'细问'},'parent_case_id':parent,**extra})
        self.assertEqual(status,201,result)
        return result['case_id']

    def analyze(self,case_id):
        status,_,result=self.request('POST',f'/api/cases/{case_id}/analyze',{'provider':'deepseek','model':'test-model','expected_revision_seq':1})
        self.assertEqual(status,202,result)
        for _ in range(100):
            _,_,job=self.request('GET','/api/jobs/'+result['job_id'])
            if job['status'] not in ('queued','running'):break
            time.sleep(.01)
        self.assertEqual(job['status'],'completed',job)

    def test_series_routes_export_tree_and_keep_unrelated_cases_separate(self):
        root=self.create();child=self.child(root,parent_revision_seq=1);self.child(child)
        self.create()
        status,_,listing=self.request('GET','/api/series')
        self.assertEqual(status,200);self.assertEqual(len(listing['series']),2)
        status,_,data=self.request('GET',f'/api/series/{root}')
        self.assertEqual(status,200);self.assertEqual(data['case_count'],3)
        status,headers,export=self.request('GET',f'/api/series/{root}/export')
        self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition'])
        self.assertEqual(export['format'],'liuyao-series-v1');self.assertEqual(len(export['cases']),3)
        _,_,detail=self.request('GET',f'/api/cases/{child}')
        self.assertEqual(detail['series']['series_id'],root)
        self.assertEqual(self.request('GET',f'/api/series/{child}')[0],404)

    def test_sibling_context_marks_saved_report_stale_without_rewriting_it(self):
        root=self.create();child=self.child(root)
        self.analyze(child)
        _,_,before=self.request('GET',f'/api/cases/{child}')
        self.assertTrue(before['report_is_current'])
        self.assertEqual(self.request('POST',f'/api/cases/{root}/context',{'text':'新进展'})[0],201)
        _,_,after=self.request('GET',f'/api/cases/{child}')
        self.assertFalse(after['report_is_current'])
        self.assertEqual(after['case']['analysis_runs'],before['case']['analysis_runs'])
        self.analyze(child)
        _,_,current=self.request('GET',f'/api/cases/{child}')
        self.assertTrue(current['report_is_current'])
        self.assertEqual(current['case']['analysis_runs'][-1]['input_snapshot']['context_events'][0]['case_id'],root)

    def test_forged_parent_reference_fails_without_an_orphan_child(self):
        root=self.create()
        for extra,expected in (({'parent_revision_seq':99},409),({'parent_analysis_run_id':'does-not-exist'},404)):
            status,_,_=self.request('POST','/api/cases',{'input':INPUT,'parent_case_id':root,**extra})
            self.assertEqual(status,expected)
        self.assertEqual(self.request('POST','/api/cases',{'input':INPUT,'parent_case_id':'not-owned'})[0],404)
        _,_,listing=self.request('GET','/api/cases')
        self.assertEqual(len(listing['cases']),1)

    def test_shared_person_changes_mark_another_nodes_report_stale(self):
        root=self.create();child=self.child(root)
        self.analyze(child)
        self.assertEqual(self.request('POST',f'/api/cases/{root}/revisions',{
            'input':{**INPUT,'person_info':{'subject':'self','background':'正在申请新岗位'}},
            'expected_revision_seq':1,'reason':'补充共同背景'})[0],201)
        _,_,data=self.request('GET',f'/api/cases/{child}')
        self.assertFalse(data['report_is_current'])
        self.assertEqual(data['series']['shared_person_context']['person_info']['background'],'正在申请新岗位')

    def test_child_http_retry_preserves_a_single_link(self):
        root=self.create()
        data={'input':INPUT,'parent_case_id':root,'parent_revision_seq':1}
        headers={'X-Idempotency-Key':'same-child-request'}
        first=self.request('POST','/api/cases',data,headers=headers)
        second=self.request('POST','/api/cases',data,headers=headers)
        self.assertEqual(first[0],201);self.assertEqual(second[0],201)
        self.assertEqual(first[2]['case_id'],second[2]['case_id'])
        _,_,series=self.request('GET',f'/api/series/{root}')
        self.assertEqual(series['case_count'],2)

    def test_legacy_report_is_current_until_new_series_background_is_added(self):
        root=self.create();self.analyze(root)
        _,_,before=self.request('GET',f'/api/cases/{root}')
        record=before['case'];run=record['analysis_runs'][-1]
        snapshot=copy.deepcopy(run['input_snapshot']);del snapshot['series_context']
        actor=Actor(record['owner_id'],record['session_id'])
        store=self.app.store()
        try:
            store.db.execute('INSERT INTO analysis_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                ('legacy-run',root,1,None,store.clock(),content_digest(snapshot),encoded(snapshot),
                 run['source_hash'],run['rules_digest'],run['prompt_digest'],run['engine_build']))
            store.finish_analysis(actor,root,'legacy-run',status='completed',report=run['outcome']['result']['report'],idempotency_key='legacy-finish')
        finally:store.close()
        self.assertTrue(self.request('GET',f'/api/cases/{root}')[2]['report_is_current'])
        status,_,_=self.request('POST','/api/cases',{'parent_case_id':root,'input':{**INPUT,
            'person_info':{'subject':'self','background':'本次新增系列背景'}}})
        self.assertEqual(status,201)
        after=self.request('GET',f'/api/cases/{root}')[2]
        self.assertFalse(after['report_is_current'])
        self.assertEqual(after['case']['analysis_runs'][-1]['input_snapshot'],snapshot)


class SeriesPipelineChecks(unittest.TestCase):
    def test_series_reference_reaches_the_provider_as_audited_prompt_material(self):
        from . import pipeline
        store=Mock();received={}
        context={'series_id':'series','ancestors':[{'question':'总问','analysis_reference':{
            'conclusion':{'answer':'仅供参考的前卦判断','limits':['尚缺条件']}}}]}
        pack={'stages':{'intent':{'input_schema':{'type':'object','properties':{'question':{'type':'string'}},
             'required':['question'],'additionalProperties':False}}}}
        def provider(provider,model,prompt,payload,**options):
            received.update(prompt=prompt,payload=copy.deepcopy(payload))
            raise ValueError('offline provider fixture')
        with patch.object(pipeline,'runtime_prompt',return_value='base system instructions'),patch.object(pipeline,'prompt_digest',return_value='a'*64):
            with self.assertRaises(pipeline.StageFailure):
                pipeline._stage_call(store,Actor('owner','session'),'child','run','intent',{'question':'细问'},
                    pack,'fixture','model',provider,lambda _:None,series_context=context)
        self.assertEqual(received['payload'],{'question':'细问'})
        self.assertIn('仅供参考的前卦判断',received['prompt'])
        self.assertIn('不能替代本卦取用和推演',received['prompt'])
        metadata=store.add_ai_event.call_args.kwargs['model_run_metadata']
        self.assertEqual(metadata['series_context_digest'],pipeline.content_digest(context))
        self.assertEqual(metadata['system_prompt'],received['prompt'])


if __name__=='__main__':unittest.main()
