"""Integration smoke: stage validator + case event retention, without model calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from case_store import Actor, CaseStore, content_digest
from validate_ai_contract import PACK_PATH, ContractError, load_pack, prompt_digest, validate_output

results=[]
def check(test_id,title,value):
    results.append({'test_id':test_id,'title':title,'status':'passed' if value else 'failed',
                    'runner':'software_prep/test_ai_store_integration.py',
                    'evidence_file':'software_prep/ai_store_integration_results.json'})

pack=load_pack()
example=deepcopy(pack['stages']['intent']['valid_example'])
with TemporaryDirectory() as tmp:
    store=CaseStore(Path(tmp)/'cases.sqlite3')
    actor=Actor('OWNER','SESSION')
    case=store.create_case(actor,{'question':example['input']['question'],
        'lines':['young_yang','young_yin','old_yang','old_yin','young_yang','young_yin']},idempotency_key='create')
    pack_digest=hashlib.sha256(PACK_PATH.read_bytes()).hexdigest()
    run=store.start_analysis(actor,case['case_id'],source_hash='a'*64,rules_digest='b'*64,
        prompt_digest=pack_digest,engine_build='offline_fixture',idempotency_key='start')
    for key in ('case_id','analysis_run_id','input_snapshot_id'):
        example['input']['meta'][key]=run[key]
    example['input']['meta']['prompt_digest']=prompt_digest(pack,'intent')
    example['output']['binding']={k:run[k] for k in ('analysis_run_id','input_snapshot_id')}
    metadata={'stage_prompt_digest':prompt_digest(pack,'intent'),
              'input_projection_digest':content_digest(example['input']), 'model_id':'no_model_offline_fixture'}
    bad_raw='{"binding":'
    try:
        validate_output('intent',bad_raw,example['input'],pack)
        error=None
    except ContractError as exc:
        error=str(exc)
    store.add_ai_event(actor,case['case_id'],run['analysis_run_id'],stage='intent',attempt_id='attempt_1',
        raw_output=bad_raw,parse_status='invalid_json',validation_errors=[error],model_run_metadata=metadata,
        idempotency_key='attempt1')
    raw=json.dumps(example['output'],ensure_ascii=False)
    adopted=validate_output('intent',raw,example['input'],pack)
    store.add_ai_event(actor,case['case_id'],run['analysis_run_id'],stage='intent',attempt_id='attempt_2',
        raw_output=raw,parse_status='parsed',validation_errors=[],adopted_output=adopted,
        model_run_metadata=metadata,idempotency_key='attempt2')
    exported=store.export_case(actor,case['case_id'])
    saved=exported['analysis_runs'][0]
    attempts=[e['attempt'] for e in saved['ai_events']]
    check('AI-STORE-001','失败原始输出与校验错误保留，未被成功重试覆盖',
          len(attempts)==2 and attempts[0]['raw_output']==bad_raw and attempts[0]['validation_errors']==[error])
    check('AI-STORE-002','通过结构引用校验的采用内容保持运行绑定',
          attempts[1]['adopted_output']==adopted and adopted['binding']['analysis_run_id']==run['analysis_run_id'])
    check('AI-STORE-003','原始输出与采用内容分开保存，摘要由存储生成',
          attempts[1]['raw_output']==raw and attempts[1]['adopted_output_digest']==content_digest(adopted)
          and attempts[0]['adopted_output'] is None)
    check('AI-STORE-004','分析整包摘要与阶段模板摘要均可追溯',
          saved['prompt_digest']==pack_digest and attempts[1]['model_run_metadata']['stage_prompt_digest']==prompt_digest(pack,'intent'))
    check('AI-STORE-005','输入缺日期仍留案例，不把录入时间补为实际起卦时间',
          'actual_cast_time' not in saved['input_snapshot']['input'] and saved['input_snapshot']['time_context'].get('actual_cast_time') is None)
    store.close()
result={'test_suite':'ai_case_store_integration','scope':'本地validator与SQLite事件联通；没有调用真实AI',
        'total':len(results),'passed':sum(r['status']=='passed' for r in results),'failed':sum(r['status']=='failed' for r in results),'tests':results}
Path(__file__).with_name('ai_store_integration_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('total','passed','failed')},ensure_ascii=False))
if result['failed']:raise SystemExit(1)
