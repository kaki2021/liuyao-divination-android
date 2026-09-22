"""Create the current input and service case record contracts using the standard library."""
from pathlib import Path
import json

ROOT=Path(__file__).parent
def obj(props,required=None,description=None):
    value={'type':'object','properties':props,'required':list(props) if required is None else list(required),'additionalProperties':False}
    if description:value['description']=description
    return value
def ref(name):return {'$ref':'#/$defs/'+name}
def array(items):return {'type':'array','items':items}
def null_or(schema):return {'anyOf':[schema,{'type':'null'}]}
S={'type':'string','minLength':1}
D={'type':'string','format':'date-time'}
H={'type':'string','pattern':'^[a-f0-9]{64}$'}
OPAQUE={'type':'object','additionalProperties':True,'description':'原样保留的相关服务载荷；排盘或AI字段应先由对应模块契约验证，存储不证明其内容正确。'}
# The client input schema is maintained with the casting normalizer.
# Persisted cases always contain normalized lines, and may also retain raw casting.
input_schema=json.loads((ROOT/'liuyao_input_schema.json').read_text())
user={k:v for k,v in input_schema.items() if k not in ('$schema','$id','title')}
user['required']=['question','lines']
example={'question':'这辆车目前还能满足我的日常出行需要吗？','lines':['young_yang','young_yin','old_yang','old_yin','young_yang','young_yin']}
(ROOT/'liuyao_input_example.json').write_text(json.dumps(example,ensure_ascii=False,indent=2)+'\n')
known={**example,'actual_cast_time':'2026-09-17T18:30:00+08:00'}
(ROOT/'liuyao_input_example_known_time.json').write_text(json.dumps(known,ensure_ascii=False,indent=2)+'\n')
time_context=obj({'actual_cast_time':null_or(D),'precision':{'enum':['second','subsecond','unknown']},'provenance':{'enum':['user_supplied','unknown']}})
context_event=obj({'event_id':S,'case_id':S,'event_seq':{'type':'integer','minimum':1},'event_type':{'enum':['background','clarification_question','clarification_answer','intent_interpretation','user_correction','unresolved_notice','service_failure']},'recorded_at':D,'session_id':S,'content':OPAQUE})
revision=obj({'case_id':S,'revision_seq':{'type':'integer','minimum':1},'revision_id':S,'recorded_at':D,'kind':{'enum':['initial','user_correction']},'reason':S,'input':ref('UserInput'),'time_context':time_context})
snapshot=obj({'case_id':S,'revision_seq':{'type':'integer','minimum':1},'input':ref('UserInput'),'time_context':time_context,'context_events':array(ref('ContextEvent'))})
attempt=obj({'event_type':{'const':'ai_attempt'},'stage':S,'attempt_id':S,'raw_output':{'type':'string'},'parse_status':{'enum':['parsed','invalid_json','provider_error','not_parsed']},'validation_errors':array(ref('JsonValue')),'adopted_output':ref('JsonValue'),'adopted_output_digest':null_or(H),'model_run_metadata':OPAQUE})
ai_event=obj({'event_id':S,'analysis_run_id':S,'recorded_at':D,'stage':S,'attempt_id':S,'attempt':attempt})
result=obj({'status':{'enum':['completed','partial','unresolved','failed']},'chart_snapshot':ref('JsonValue'),'evidence':array(ref('JsonValue')),'report':ref('JsonValue'),'validation':OPAQUE,'unresolved':array(ref('JsonValue')),'error':ref('JsonValue')})
outcome=obj({'analysis_run_id':S,'recorded_at':D,'status':{'enum':['completed','partial','unresolved','failed']},'result':result,'result_digest':H})
run=obj({'analysis_run_id':S,'case_id':S,'revision_seq':{'type':'integer','minimum':1},'parent_run_id':null_or(S),'analyzed_at':D,'input_snapshot_id':H,'input_snapshot':snapshot,'source_hash':H,'rules_digest':H,'prompt_digest':H,'engine_build':S,'outcome':null_or(outcome),'status':{'enum':['running','completed','partial','unresolved','failed']},'ai_events':array(ai_event)})
feedback=obj({'feedback_id':S,'case_id':S,'analysis_run_id':null_or(S),'occurred_at':null_or(D),'recorded_at':D,'reported_outcome':S,'verification_status':{'enum':['self_reported','externally_supported','disputed','unknown']},'verification_method':null_or(S),'supersedes_feedback_id':null_or(S)})
case=obj({'case_id':S,'owner_id':S,'session_id':S,'recorded_at':D,'original_input':ref('UserInput'),'revisions':array(revision),'context_events':array(ref('ContextEvent')),'analysis_runs':array(run),'feedback':array(feedback),'usage_policy':obj({'service_case_archive':{'const':True},'public_use':{'const':False},'training_use':{'const':False}})})
case_schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:liuyao:service-case-record','title':'六爻服务案例记录契约',
             'description':'仅供可信服务端导出，不是客户端写入入口；允许保存失败与未决结果，不将无反馈解释为成败。',**case,
             '$defs':{'UserInput':user,'ContextEvent':context_event,
                      'JsonValue':{'oneOf':[{'type':'null'},{'type':'string'},{'type':'number'},{'type':'boolean'},{'type':'array','items':ref('JsonValue')},{'type':'object','additionalProperties':ref('JsonValue')}]}}}
(ROOT/'case_record_schema.json').write_text(json.dumps(case_schema,ensure_ascii=False,indent=2)+'\n')
print('Created input examples and normalized case_record_schema.json')
