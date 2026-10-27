"""Phone-like conversation fixture with deterministic model replies and real APIs."""
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from liuyao_app.server import Application,Server
from case_store import Actor
from liuyao_app import workbench,conversation
from liuyao_app.rulebook import save_rules
from liuyao_app.test_rule_installation import public_placeholder_rows
from liuyao_app.test_conversation import INPUT,saved_analysis
from liuyao_app.profile_store import save_profile
from liuyao_app.pipeline import calculate_chart


def answer(provider,model,prompt,payload,**options):
    if prompt==workbench.ISSUE_PROMPT:
        return {'parsed_json':{'category':'preferences','summary':'已建议缩短回答。','changes':{'detail':'concise'},'acceptance':['先回答所问。']}}
    if 'sources' in payload:
        return {'parsed_json':{'answer':'根据原文回答，已接续 '+str(len(options.get('conversation_history',[])))+' 条消息。',
            'citation_ids':[payload['sources'][0]['citation_id']],'insufficient':False}}
    return {'parsed_json':{'answer':'继续沿用当前卦盘，已接续 '+str(len(options.get('conversation_history',[])))+' 条消息。','requires_reanalysis':False}}


def pipeline(db_path,actor,case_id,provider,model,revision,progress=None):
    from case_store import CaseStore
    store=CaseStore(db_path)
    try:
        run=store.start_analysis(actor,case_id,source_hash='1'*64,rules_digest='2'*64,prompt_digest='3'*64,
            engine_build='fixture',idempotency_key='analysis-'+str(revision),expected_revision_seq=revision)['analysis_run_id']
        case=store.export_case(actor,case_id);chart=calculate_chart(case['revisions'][-1]['input'],include_experimental=False)
        report={'analysis_run_id':run,'status':'completed','stage_outputs':{'interpretation':{'conclusion':{'answer':'需要结合居住目标核对。','limits':['测试回复']}}},
            'user_report':{'conclusion':{'answer':'需要结合居住目标核对。'}},'chart':chart,'is_demo':False}
        store.finish_analysis(actor,case_id,run,status='completed',chart_snapshot=chart,report=report,idempotency_key='finish-'+run)
        return report
    finally:store.close()


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as directory:
        app=Application(directory,pipeline=pipeline);save_rules(app.rules_directory,public_placeholder_rows())
        app.config=lambda:{'providers':[{'id':'deepseek','name':'测试模型','models':['test-model'],'default_model':'test-model','configured':True}],
                           'default_provider':'deepseek','storage_mode':'local'}
        workbench.generate_json=answer;conversation.generate_json=answer
        store=app.store();actor=Actor('local-user','fixture')
        case=store.create_case(actor,INPUT,idempotency_key='legacy')['case_id'];saved_analysis(store,actor,case)
        profile=save_profile(store,actor,{'name':'测试本人'},is_self=True,idempotency_key='self')['person_id'];store.close()
        server=Server(('127.0.0.1',0),app)
        print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'legacy_case':case,'profile_id':profile}),flush=True)
        try:server.serve_forever(poll_interval=.02)
        finally:server.server_close();app.close()
