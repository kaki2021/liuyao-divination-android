"""Run the current minimal input checks against validate_input, without archived tools."""
import copy
import json
from pathlib import Path
from validate_input import validate_input, derive_six_lines

ROOT=Path(__file__).parent
base=json.loads((ROOT/'liuyao_input_example.json').read_text())
timed=json.loads((ROOT/'liuyao_input_example_known_time.json').read_text())
results=[]

def check(title,value,expected):
    actual=validate_input(value)
    test_id='INPUT-'+str(len(results)+1).zfill(2)
    results.append({'test_id':test_id,'title':title,'status':'passed' if actual['valid']==expected else 'failed',
                    'expected_valid':expected,'actual_valid':actual['valid'],
                    'evidence':'test_input.py:'+test_id,'error_codes':[e['code'] for e in actual['errors']]})

check('问题与六项四象即可接受',base,True)
check('已知实际起卦时间可选附加',timed,True)
x=copy.deepcopy(base);x['actual_cast_time']=None;check('实际时间未知可显式null',x,True)
x=copy.deepcopy(base);x['lines']=['young_yang']*6;check('六爻全同合法，不误判重复',x,True)
x=copy.deepcopy(base);x['lines']=x['lines'][:5];check('五项四象应拒绝',x,False)
x=copy.deepcopy(base);x['lines'].append('old_yang');check('七项四象应拒绝',x,False)
x=copy.deepcopy(base);x['lines']='乾为天';check('卦名不能代替六项四象',x,False)
x=copy.deepcopy(base);x['lines']=['yang','yin']*3;check('仅阴阳不能保存动静',x,False)
x=copy.deepcopy(base);x['lines'][2]=True;check('布尔值不是四象枚举',x,False)
x=copy.deepcopy(base);x['question']='  \n ';check('空白问题应拒绝',x,False)
x=copy.deepcopy(base);x['age_years']=35;check('年龄不成为通用入口字段',x,False)
x=copy.deepcopy(base);x['raw_values']=[[2,2,3]]*6;check('入口不接收三丸原始值',x,False)
x=copy.deepcopy(base);x['casting_method']='taiji_balls';check('起卦方法不成为输入字段',x,False)
x=copy.deepcopy(base);x['recorded_at']='2026-09-17T12:00:00Z';check('登记时间由服务器生成',x,False)
x=copy.deepcopy(base);x['engine_context']={'mode':'ordinary'};check('引擎配置不能从客户端注入',x,False)
x=copy.deepcopy(base);x['actual_cast_time']='2026-02-30T12:00:00Z';check('不存在的实际日期应拒绝',x,False)
x=copy.deepcopy(base);x['actual_cast_time']='2026-09-17T12:00:00';check('完整时刻缺时区不默猜',x,False)
x=copy.deepcopy(base);x['actual_cast_time']='2026-09-17T12:00:00-00:00';check('未知时间偏移不能冒充已知时刻',x,False)

derived=derive_six_lines(base)
okay=(derived['base_bits']==[1,0,1,0,1,0] and derived['moving_line_numbers']==[3,4]
      and derived['changed_bits']==[1,0,0,1,1,0] and derived['actual_cast_time'] is None
      and derived['time_context_status']=='unknown')
results.append({'test_id':'INPUT-19','title':'第三四爻动变正确，未知时间仍为null',
                'status':'passed' if okay else 'failed','evidence':'test_input.py:INPUT-19'})
report={'scope':'Current input validation and four-state conversion; no model or prediction validation',
        'tests_run':len(results),'passed':sum(r['status']=='passed' for r in results),
        'failed':sum(r['status']=='failed' for r in results),'tests':results}
(ROOT/'input_test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('tests_run','passed','failed')},ensure_ascii=False))
raise SystemExit(0 if report['failed']==0 else 1)
