"""Isolated browser-test server with public placeholder rules and no live models."""
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from liuyao_app.server import Application, Server
from liuyao_app.rulebook import save_rules
from liuyao_app.test_rule_installation import public_placeholder_rows
from liuyao_app.test_conversation import INPUT, saved_analysis
from liuyao_app import conversation
from case_store import Actor


def answer(provider,model,prompt,context,**options):
    messages=options['conversation_history']
    return {'parsed_json':{'answer':'<b>测试回复</b>：'+messages[-1]['content']+'；已接续 '+str(len(messages))+' 条消息。',
                          'requires_reanalysis':'待遇已确认' in messages[-1]['content']}}


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as directory:
        app=Application(directory)
        save_rules(app.rules_directory,public_placeholder_rows())
        app.config=lambda:{'providers':[{'id':'deepseek','name':'测试模型','models':['test-model'],
            'default_model':'test-model','configured':True}],'default_provider':'deepseek','storage_mode':'local'}
        conversation.generate_json=answer
        store=app.store();actor=Actor('local-user','browser-fixture')
        case=store.create_case(actor,INPUT,idempotency_key='case')['case_id'];saved_analysis(store,actor,case);store.close()
        server=Server(('127.0.0.1',0),app)
        print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'case_id':case}),flush=True)
        try:server.serve_forever(poll_interval=.05)
        finally:server.server_close();app.close()
