"""V5 analysis: factual structures and experimental scores stay distinguishable."""
from copy import deepcopy
from itertools import combinations, product
import json
import base_chart as base
from liuyao_app.day_month_analysis import analyze_day_month, element_relation, clash, combine, RELATION_LABELS
from liuyao_app.change_analysis import analyze_change
from liuyao_app.strength_engine import calculate_strength
from liuyao_app.relation_effect_engine import evaluate_relation_effect, pair_labels
TRIPLES=(('申子辰','水'),('亥卯未','木'),('寅午戌','火'),('巳酉丑','金'))

def calculate_comprehensive(chart,rules):
    calendar=chart.get('calendar',{}); available=calendar.get('status')=='computed'
    lines=deepcopy(chart['main']['lines']); palace=chart['main']['palace_element']
    for line in lines:
        dm=analyze_day_month(line,calendar,rules);line['day_month']=dm
        contributions=list(dm['contributions']);line['change']=None
        if line['moving']:
            contributions.append(rules.contribution('MOVING','本爻发动'))
            line['change']=analyze_change(line,chart['changed_structure']['branches'][line['position']-1],palace,calendar,rules)
            contributions.extend(line['change']['contributions'])
        line['local_strength']=calculate_strength(rules,contributions,calendar_available=available)
    effects=[]
    for target in lines:
        incoming=[evaluate_relation_effect(source,target,rules) for source in lines if source['position']!=target['position']]
        effects.extend(incoming)
        contributions=list(target['local_strength']['contributions'])
        contributions.extend(c for effect in incoming for c in effect['contributions'])
        target['strength']=calculate_strength(rules,contributions,calendar_available=available)
    present={line['relative_code'] for line in lines};hidden=[]
    for position,branch in enumerate(base.PURE_BRANCHES[chart['main']['palace']],1):
        element=base.BRANCH_ELEMENTS[branch];relative=base.ordinary_relative(palace,element);code=base.RELATIVE_CODES[relative]
        if code in present:continue
        fly=lines[position-1]
        fu={'position':position,'branch':branch,'element':element,'relative':relative,'relative_code':code,'moving':False}
        dm=analyze_day_month(fu,calendar,rules)
        dm['hidden_moving']=False
        dm['contributions']=[c for c in dm['contributions'] if c['rule_id']!='HIDDEN_MOVE']
        relation=element_relation(fly['element'],element);contributions=list(dm['contributions'])
        if relation in ('generates','controls'):contributions.append(rules.contribution('FLY_'+relation.upper(),'飞神对伏神：'+RELATION_LABELS[relation]))
        fu.update(flying_position=position,flying_branch=fly['branch'],flying_relative=fly['relative'],
            flying_to_hidden=relation,day_month=dm,strength=calculate_strength(rules,contributions,calendar_available=available),status='experimental')
        hidden.append(fu)
    pairs=[{'positions':[a['position'],b['position']],'branches':[a['branch'],b['branch']],'labels':pair_labels(a['branch'],b['branch'],rules)} for a,b in combinations(lines,2)]
    pairs=[p for p in pairs if p['labels']]
    groups=[]
    for branches,element in TRIPLES:
        options=[[l['position'] for l in lines if l['branch']==b] for b in branches]
        if all(options) and rules.enabled('ENABLE_TRIPLE_COMBINE'):
            groups.extend({'type':'三合','positions':list(ps),'branches':list(branches),'nominal_element':element,'transformed':False} for ps in product(*options))
        if rules.enabled('ENABLE_HALF_COMBINE'):
            for a,b in combinations(lines,2):
                if a['branch']!=b['branch'] and {a['branch'],b['branch']}.issubset(branches) and branches[1] in (a['branch'],b['branch']):
                    groups.append({'type':'半合','positions':[a['position'],b['position']],'branches':[a['branch'],b['branch']],'nominal_element':element,'transformed':False})
    return {'model_version':'V5 experimental','rules_version':rules.version,'rules_digest':rules.digest,
        'lines':lines,'hidden_spirits':hidden,'pair_relations':pairs,'combination_groups':groups,'effects':effects,
        'six_clash_hexagram':all(clash(lines[i]['branch'],lines[i+3]['branch']) for i in range(3)),
        'six_combine_hexagram':all(combine(lines[i]['branch'],lines[i+3]['branch']) for i in range(3)),
        'method':'先日月动变得局部分，再以来源局部分计算作用；最后合计并截断至0–10。不循环传播。',
        'timing_implemented':False}

def select_use_lines(chart,selection,rules):
    analysis=chart['comprehensive_analysis'];lines=analysis['lines'];hidden=analysis['hidden_spirits']
    choices=[]
    for candidate in selection['candidates']:
        reference=candidate.get('subject_reference')
        if reference:
            matches=[lines[(chart['shi_position'] if reference=='shi' else chart['shi_body_position'])-1]];layer='visible'
        else:
            matches=[l for l in lines if l['relative_code']==candidate['six_relative']];layer='visible'
            if not matches: matches=[l for l in hidden if l['relative_code']==candidate['six_relative']];layer='hidden'
        ranked=[]
        for line in matches:
            rank=line['strength']['score']
            if line['moving']:rank+=rules.weight('SELECT_MOVING')
            if line.get('is_shi'):rank+=rules.weight('SELECT_SHI')
            ranked.append({'position':line['position'],'branch':line['branch'],'element':line['element'],'relative':line['relative'],
                'layer':layer,'rank_score':round(rank,3),'strength':line['strength']['score']})
        ranked.sort(key=lambda x:(-x['rank_score'],x['position']))
        tied=[r for r in ranked if r['rank_score']==ranked[0]['rank_score']] if ranked else []
        choices.append({'candidate_id':candidate['candidate_id'],'purpose':candidate['purpose'],'matches':ranked,
            'chosen':ranked[0] if ranked else None,'tied_positions':[r['position'] for r in tied] if len(tied)>1 else [],
            'selection_method':'同类候选按实验强度+发动/持世加分排序；并列取较低爻位并保留并列信息',
            'status':'experimental' if len(ranked)>1 or layer=='hidden' else 'structural_match'})
    main=next((x for x in choices if x['candidate_id']==selection['selected_primary_id']),None)
    target=main['chosen'] if main else None
    roles={'原神':[],'忌神':[],'仇神':[],'同类':[]}
    if target:
        enemy=next(e for e in base.CONTROLS if base.CONTROLS[e]==target['element'])
        for line in lines:
            if target['layer']=='visible' and line['position']==target['position']:continue
            e=line['element']
            role='原神' if base.GENERATES[e]==target['element'] else '忌神' if e==enemy else '仇神' if base.GENERATES[e]==enemy else '同类' if e==target['element'] else None
            if role:roles[role].append(line['position'])
    auxiliary=[]
    if target:
        for item in choices:
            if item is main or not item['chosen']:continue
            ch=item['chosen'];relation=element_relation(ch['element'],target['element'])
            sign=1 if relation=='generates' else -1 if relation=='controls' else 0
            auxiliary.append({'candidate_id':item['candidate_id'],'relation_to_main':relation,
                'weighted_effect':round(sign*ch['strength']/10*rules.weight('AUXILIARY_FACTOR')*rules.weight('MAIN_FACTOR'),3),
                'note':'功能候选作用摘要，未重复加入爻强度'})
    return {'primary':main,'candidates':choices,'roles':roles,'auxiliary_effects':auxiliary,'rules_version':rules.version}

def analysis_facts(chart):
    a=chart['comprehensive_analysis'];facts=[]
    def add(key,subject,predicate,value):
        if not isinstance(value,(str,int,float,bool)):value=json.dumps(value,ensure_ascii=False,separators=(',',':'))
        facts.append({'fact_id':key,'kind':'calculation','subject':subject,'predicate':predicate,'value':value,'source_rule_id':None})
    add('MODEL_RULES_VERSION','综合模型','实验参数版本',a['rules_version'])
    for l in a['lines']:
        p=l['position'];s=f'主卦第{p}爻';dm={k:v for k,v in l['day_month'].items() if k!='contributions'}
        add(f'COMPOSITE_{p}',s,'实验综合强度', {k:l['strength'][k] for k in ('score','raw_score','level','coverage')})
        add(f'DAY_MONTH_{p}',s,'日月空破状态',dm)
        for name,mods in [('LOCAL',l['local_strength']['contributions']),('INTERACTION',[c for c in l['strength']['contributions'] if c not in l['local_strength']['contributions']])]:
            add(f'SCORE_{p}_{name}',s,'实验记分明细',[{'rule_id':c['rule_id'],'value':c['value'],'detail':c['detail']} for c in mods])
        if l['change']:add(f'CHANGE_{p}',s,'动变结构',{k:v for k,v in l['change'].items() if k!='contributions'})
    for i,fu in enumerate(a['hidden_spirits']):
        add(f'HIDDEN_{i}',f"第{fu['position']}爻下伏神",'伏飞与日月', {k:v for k,v in fu.items() if k not in ('strength','day_month')} | {'day_month':{k:v for k,v in fu['day_month'].items() if k!='contributions'},'score':fu['strength']['score']})
    add('COMPOSITE_PAIRS','本卦','合冲形害等配对',a['pair_relations'])
    add('COMPOSITE_GROUPS','本卦','三合半合结构，不自动判成化',a['combination_groups'])
    for i,effect in enumerate(e for e in a['effects'] if e['active']):
        add(f'ACTIVE_EFFECT_{i}','动静爻作用','来源对目标的实验作用',{k:v for k,v in effect.items() if k!='contributions'})
    if 'use_selection' in a:
        u=a['use_selection'];add('PRIMARY_USE_LINE','主用神','实验取用及候选',u['primary'])
        add('USE_ROLES','主用神','原神忌神仇神位置',u['roles'])
        add('AUXILIARY_EFFECTS','辅助用神','对主用作用摘要',u['auxiliary_effects'])
    return facts
