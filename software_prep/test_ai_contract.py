"""Meaningful positive/adversarial checks for the local AI contract. No live model."""
from copy import deepcopy
import json
from pathlib import Path
from validate_ai_contract import ContractError, load_pack, validate_output, prompt_digest, parse_raw
PACK = load_pack()
RESULTS = []

def trial(test_id, title, stage, change=None, accept=False, raw=None, expected_error=None):
    fixture = deepcopy(PACK['stages'][stage]['valid_example'])
    if change:
        change(fixture['input'], fixture['output'])
    try:
        validate_output(stage, raw if raw is not None else json.dumps(fixture['output'], ensure_ascii=False), fixture['input'], PACK)
        actual = True
        error = None
    except ContractError as exc:
        actual = False
        error = str(exc)
    error_matches = expected_error is None or error == expected_error
    RESULTS.append({'test_id':test_id, 'title':title, 'expected':'accepted' if accept else 'rejected',
                    'status':'passed' if actual == accept and error_matches else 'failed', 'evidence_file':'software_prep/ai_contract_test_results.json',
                    'runner':'software_prep/test_ai_contract.py','observed_error':error})

def supported(inp, out):
    inp['unresolved_gaps']=[]
    inp['rules'][0]['usage']='interpretation'
    fact=inp['facts'][0]
    atom={k:fact[k] for k in ('subject','predicate','value')}
    inp['inferences']=[{'inference_id':'INF_USE','analysis_run_id':'RUN_DEMO','rule_id':inp['rules'][0]['rule_id'],
        'premise_fact_ids':[fact['fact_id']],'target':'待售粮食','conclusion':atom,'direction':'neutral',
        'scope':'仅确定本次交易财货的功能归属，不说明成交结果。','status':'verified'}]
    out.update(status='supported', uncertainties=[], claims=[{'claim_id':'CLAIM_USE','dimension':'support','kind':'engine_supported',
        'statement':'本次待售粮食按交易财货功能归妻财；此项本身不说明能否成交。','direction':'neutral','proposition':deepcopy(atom),
        'fact_refs':[fact['fact_id']],'rule_refs':[inp['rules'][0]['rule_id']],'inference_refs':['INF_USE'],
        'assumptions':[],'limitations':['该结构说明不能作为成交预测。'],'requires_review':False}])

def hypothesis(inp,out):
    supported(inp,out)
    inp['inferences']=[]
    out['status']='needs_review'
    c=out['claims'][0]
    c.update(kind='ai_hypothesis',inference_refs=[],requires_review=True,assumptions=['只讨论已说明的交易用途。'])

def context(inp,out):
    supported(inp,out)
    inp['inferences']=[]
    inp['facts'][0]['kind']='context'
    c=out['claims'][0]
    c.update(kind='real_world_context',rule_refs=[],inference_refs=[])

def both(first, second):
    return lambda i,o:(first(i,o),second(i,o))

for index, stage in enumerate(PACK['stages'],1):
    trial('AI-%03d'%index,'完整正例：'+stage,stage,accept=True)
trial('AI-005','意图步骤拒绝偷传六爻盘面','intent',lambda i,o:i.update(chart={'lines':[1]*6}))
trial('AI-006','功能选择拒绝偷传旺衰结论','selection',lambda i,o:i.update(outcome='吉'))
trial('AI-007','拒绝跨分析run输出','intent',lambda i,o:o['binding'].update(analysis_run_id='OTHER_RUN'))
trial('AI-008','拒绝提示词digest不匹配','intent',lambda i,o:i['meta'].update(prompt_digest='c'*64))
trial('AI-009','拒绝伪造用户引文','intent',lambda i,o:o['candidates'][0]['evidence_quotes'][0].update(quote='用户希望稳赚百分百'))
trial('AI-010','明确问题不需例行确认','intent',accept=True)
trial('AI-011','明确状态不容阻断式追问','intent',lambda i,o:o['clarifying_questions'].append({'question_id':'Q','text':'你确认吗？','why_needed':'例行确认','affects':'intent'}))
trial('AI-012','拒绝引文缺失却强选真念','intent',lambda i,o:o['candidates'][0].update(evidence_quotes=[]))
trial('AI-013','拒绝固定六亲与功能方向矛盾','selection',lambda i,o:o['candidates'][0].update(six_relative='parents'))
trial('AI-014','拒绝补充文献覆盖核心','selection',lambda i,o:i['rules'][0].update(source_id='SRC-GSK'))
trial('AI-015','拒绝个人纲要升级生产依据','selection',lambda i,o:i['rules'][0].update(source_id='SRC-OUTLINE'))
trial('AI-016','拒绝未决规则支撑自动选择','selection',lambda i,o:i['rules'][0].update(status='unresolved'))
trial('AI-017','拒绝虚构用神候选引用','selection',lambda i,o:o.update(selected_primary_id='INVENTED'))
trial('AI-018','无旺衰输入保留部分结果而不编成交','interpretation',accept=True)
trial('AI-019','拒绝漏掉服务器未决事项','interpretation',lambda i,o:o.update(uncertainties=[]))
trial('AI-020','拒绝JSON中重复键','intent',raw='{"binding":{},"binding":{}}')
trial('AI-021','拒绝JSON非有限数','intent',raw='{"invalid":NaN}')
trial('AI-022','拒绝代码围栏包装','intent',raw='```json\n{}\n```')
trial('AI-023','验证原子结论可核对的引擎事实','interpretation',supported,accept=True)
trial('AI-024','编号真实但结论方向相反仍拒绝','interpretation',both(supported,lambda i,o:o['claims'][0].update(direction='favorable')))
trial('AI-025','编号真实但对象被替换仍拒绝','interpretation',both(supported,lambda i,o:o['claims'][0]['proposition'].update(subject='配偶')))
trial('AI-026','拒绝缺少推理前提','interpretation',both(supported,lambda i,o:o['claims'][0].update(fact_refs=['OTHER_FACT'])))
trial('AI-027','拒绝跨run推理事实','interpretation',both(supported,lambda i,o:i['inferences'][0].update(analysis_run_id='OTHER_RUN')))
trial('AI-028','候选推理不能伪装核验事实','interpretation',both(supported,lambda i,o:i['inferences'][0].update(status='candidate')))
trial('AI-029','AI条件解释保留复核与局限','interpretation',hypothesis,accept=True)
trial('AI-030','拒绝AI假设取消复核标记','interpretation',both(hypothesis,lambda i,o:o['claims'][0].update(requires_review=False)))
trial('AI-031','拒绝AI假设省略适用局限','interpretation',both(hypothesis,lambda i,o:o['claims'][0].update(limitations=[])))
trial('AI-032','拒绝用supported掩盖AI假设','interpretation',both(hypothesis,lambda i,o:o.update(status='supported')))
trial('AI-033','现实背景可以原样引用','interpretation',context,accept=True)
trial('AI-034','现实背景不可改造成吉凶预测','interpretation',both(context,lambda i,o:o['claims'][0].update(direction='favorable')))
trial('AI-035','拒绝报告省略未决项','report',lambda i,o:o.update(uncertainties=[]))
trial('AI-036','拒绝报告修改主问','report',lambda i,o:o.update(question_restated='我能否发财？'))
trial('AI-037','拒绝报告无证据却宣称已有支持','report',lambda i,o:o['parts'][0].update(qualification='supported'))
trial('AI-038','拒绝用重复维度掩盖遗漏代价','report',lambda i,o:o['parts'][2].update(dimension='outcome'))
trial('AI-039','拒绝不存在的报告证据','report',lambda i,o:o['parts'][0].update(claim_refs=['FAKE_CLAIM']))
trial('AI-040','拒绝改写待研究事项为其他问题','report',lambda i,o:o['uncertainties'][0].update(impact='不存在任何缺口'))
trial('AI-041','拒绝输出偷写chart字段','interpretation',lambda i,o:o.update(chart={'palace':'乾金'}))
trial('AI-042','提示词原文变化使digest失效','intent',lambda i,o:i['meta'].update(prompt_digest='0'*64))
trial('AI-043','拒绝无证据行动建议','interpretation',lambda i,o:o['advice'].append({'advice_id':'ADV','text':'立即出售','basis':'system_interpretation','claim_refs':[],'fact_refs':[],'conditions':[]}))
trial('AI-044','阻断缺口不能靠已核验局部事实绕过','interpretation',both(supported,lambda i,o:(i['unresolved_gaps'].append({'gap_id':'GAP','description':'该维度未完整','affects':['support'],'blocking':True}),o['uncertainties'].append({'gap_id':'GAP','impact':'不能确认','next_step':'research_rule'}),o.update(status='partial'))))
trial('AI-045','拒绝JSON数字溢出为无限值','intent',raw='{"invalid":1e999}')
trial('AI-046','现实建议不能以盘面判断冒充现实依据','interpretation',both(supported,lambda i,o:o['advice'].append({'advice_id':'ADV','text':'出售粮食','basis':'real_world_information','claim_refs':['CLAIM_USE'],'fact_refs':[],'conditions':[]})))

def form_supported(inp,out):
    supported(inp,out)
    rule=inp['rules'][0]
    rule.update(rule_id='TEST_THREE_FORMS',source_id='SRC-BSZS-SUPP',source_role='core_supplement',
        source_locator='PDF第3页（合成接口样例）',statement='寅巳互形，按相生关系归无恩之形。',
        applicability='仅确定此对子关系与分类，不独立判吉凶。')
    fact=inp['facts'][0]
    fact.update(fact_id='FACT_FORM',kind='chart',subject='寅巳',predicate='mutual_form_category',value='wuen',source_rule_id=rule['rule_id'])
    atom={k:fact[k] for k in ('subject','predicate','value')}
    inf=inp['inferences'][0]
    inf.update(inference_id='INF_FORM',rule_id=rule['rule_id'],premise_fact_ids=[fact['fact_id']],
        target='寅巳',conclusion=atom,scope='仅为互形分类，成败须依本案大象。')
    out['claims'][0].update(claim_id='CLAIM_FORM',statement='寅巳具有无恩之形关系；这一分类本身不决定吉凶。',
        proposition=deepcopy(atom),fact_refs=[fact['fact_id']],rule_refs=[rule['rule_id']],inference_refs=[inf['inference_id']])

def form_and_harm(inp,out):
    form_supported(inp,out)
    rule=deepcopy(inp['rules'][0])
    rule.update(rule_id='TEST_SIX_HARMS',source_locator='PDF第4至5页（合成接口样例）',
        statement='寅巳互害，归恩间；可与其互形关系并存。',applicability='仅确定互害分类，恩间不表示效果必好。')
    inp['rules'].append(rule)
    fact={'fact_id':'FACT_HARM','kind':'chart','subject':'寅巳','predicate':'mutual_harm_category','value':'enjian','source_rule_id':rule['rule_id']}
    inp['facts'].append(fact)
    inf=deepcopy(inp['inferences'][0])
    inf.update(inference_id='INF_HARM',rule_id=rule['rule_id'],premise_fact_ids=[fact['fact_id']],
        conclusion={k:fact[k] for k in ('subject','predicate','value')},scope='仅为互害分类，不预设吉凶和现实人的动机。')
    inp['inferences'].append(inf)
    claim=deepcopy(out['claims'][0])
    claim.update(claim_id='CLAIM_HARM',statement='寅巳同时具有恩间互害关系，不能据类别认定结果好或现实对方恶意。',
        proposition=deepcopy(inf['conclusion']),fact_refs=[fact['fact_id']],rule_refs=[rule['rule_id']],inference_refs=[inf['inference_id']])
    out['claims'].append(claim)

trial('AI-047','核心补充的获准关系分类规则可用','interpretation',form_supported,accept=True)
trial('AI-048','核心补充未决条目不能自动获准','interpretation',both(form_supported,lambda i,o:i['rules'][0].update(status='unresolved')))
trial('AI-049','拒绝来源ID与核心补充身份不一致','interpretation',both(form_supported,lambda i,o:i['rules'][0].update(source_id='SRC-GSK')))
trial('AI-050','课外补充正确登记身份后仍不能冒充核心依据','interpretation',both(form_supported,lambda i,o:i['rules'][0].update(source_id='SRC-GSK',source_role='supplementary')))
trial('AI-051','同对子互形与互害事实及判断允许并存','interpretation',form_and_harm,accept=True)
trial('AI-052','中性互形分类推理不能被改成凶结论','interpretation',both(form_supported,lambda i,o:o['claims'][0].update(direction='unfavorable')))
trial('AI-053','恩间分类推理不能被改成吉结论','interpretation',both(form_and_harm,lambda i,o:o['claims'][1].update(direction='favorable')))
trial('AI-054','输出不能偷偷增添全局反向五行开关','interpretation',both(form_supported,lambda i,o:o.update(reverse_all_wuxing=True)))

def selection_conditions(inp, out):
    out['unresolved'] = ['未提供实际起卦日期，日月强弱的细节仍待核对。']

def selection_detail_question(inp, out):
    out['clarifying_questions'] = [{'question_id':'Q_DETAIL', 'text':'预计在哪一天完成交易？',
        'why_needed':'细化时间范围，不改变以交易财货为主功能的取用。', 'affects':'time_scope'}]

trial('AI-055','主候选有效时保留未决条件继续取用','selection',selection_conditions,accept=True)
trial('AI-056','主候选有效时保留细化问题继续取用','selection',selection_detail_question,accept=True)
trial('AI-057','取用同时保留条件和细化问题','selection',both(selection_conditions,selection_detail_question),accept=True)
trial('AI-058','空主候选编号给出明确字段错误','selection',lambda i,o:o.update(selected_primary_id=None),
    expected_error='$.selected_primary_id: ready selection needs a non-null primary candidate ID')
trial('AI-059','不存在的主候选编号给出明确字段错误','selection',lambda i,o:o.update(selected_primary_id='INVENTED'),
    expected_error='$.selected_primary_id: candidate ID does not exist in candidates')
trial('AI-060','辅助候选不能冒充主候选且定位purpose字段','selection',lambda i,o:o['candidates'][0].update(purpose='supporting'),
    expected_error='$.candidates[0].purpose: selected_primary_id must reference a primary candidate')
trial('AI-061','缺失主候选编号仍拒绝','selection',lambda i,o:o.pop('selected_primary_id'),
    expected_error="$: missing ['selected_primary_id']")
trial('AI-062','保留条件不能绕过未知规则校验','selection',both(selection_conditions,lambda i,o:o['candidates'][0].update(rule_refs=['INVENTED_RULE'])))
trial('AI-063','保留条件不能绕过六亲映射校验','selection',both(selection_conditions,lambda i,o:o['candidates'][0].update(six_relative='parents')))
trial('AI-064','主功能根本未定不能冻结一个主候选','selection',both(selection_detail_question,lambda i,o:o.update(status='needs_clarification')))

def selection_gap(inp, out):
    gap={'gap_id':'GAP_SELECTION_UNRESOLVED_0',
         'description':'交易时间尚未细化，不能给出精确应期。', 'affects':['timing'], 'blocking':True}
    inp['unresolved_gaps'].append(gap)
    out['uncertainties'].append({'gap_id':gap['gap_id'], 'impact':gap['description'], 'next_step':'ask_user'})

trial('AI-065','解释阶段保留取用未决事项','interpretation',selection_gap,accept=True)
trial('AI-066','解释阶段不得遗漏传入的取用未决事项','interpretation',
    both(selection_gap,lambda i,o:o['uncertainties'].pop()),expected_error='an unresolved server gap was omitted')

result={'test_suite':'ai_contract_offline','scope':'局部结构、引用和原子结论校验；未调用真实AI；未验证预测效果或所有自然语言语义',
        'total':len(RESULTS),'passed':sum(r['status']=='passed' for r in RESULTS),'failed':sum(r['status']=='failed' for r in RESULTS),'tests':RESULTS}
Path(__file__).with_name('ai_contract_test_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ('total','passed','failed')},ensure_ascii=False))
if result['failed']:
    print(json.dumps([r for r in RESULTS if r['status']=='failed'],ensure_ascii=False,indent=2))
    raise SystemExit(1)
