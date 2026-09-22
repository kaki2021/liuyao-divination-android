"""Human explanations derived from the actual scoring pipeline."""
from copy import deepcopy
from .rulebook import schema, load_rules, RuleBook, compile_rules

KINDS = {
    'base': ('共同起点', '先给每一个爻相同的起算值，随后分别计算。'),
    'points': ('条件加减分', '命中条件时，直接增减对应爻的分数。'),
    'effect': ('爻间作用权重', '乘来源爻强度和状态系数，再增减目标爻的分数。'),
    'factor': ('来源衰减乘数', '缩放来源对外的作用，不直接给它自己加减分。'),
    'threshold': ('强弱标签分界', '只改变偏弱、中等、偏强标签，不改变分数。'),
    'ranking': ('取用候选排序', '只改变同类候选的优先次序，不改变爻强度。'),
    'summary_factor': ('辅助摘要乘数', '只影响辅助功能对主目标的作用摘要，不重复计分。'),
    'switch': ('结构识别开关', '决定是否识别该结构；数值 1 不表示加一分。'),
    'branch': ('地支对照约定', '决定哪些变支算化墓或化绝，命中后使用另外的分值参数。'),
}
SCORE_INTRO = [
    {'title':'到底给谁打分？', 'text':'本卦有六个爻，程序分别计算六份相对强度。每个爻都从同一个基础值开始；伏神另算。没有把六爻加起来形成整卦总分，也没有把分数当作签约、赚钱等事情的成功率。'},
    {'title':'为什么初始是 5 分？', 'text':'程序选用 0～10 的量尺，把 5 放在中间，给加分和扣分预留空间。这是设计者选定的计算起点，尚无案例校准证明 5 比 4 或 6 更准确；它不是原典给每个爻评出的分数。'},
    {'title':'分数怎样进入解卦？', 'text':'第一轮算各爻自身状态；第二轮按动爻的第一轮强度计算它对其他爻的作用。最后的分数用于强弱标签、同类取用候选排序，并连同具体结构交给 AI。强的爻可能帮助目标，也可能阻碍目标，须结合本问角色判断。'},
    {'title':'什么时候需要修改？', 'text':'正常起卦和解读不要求调参。没有明确的模型修正假设和案例依据时，保留默认值即可。研究调整时先写下要纠正的现象，只改一项，用多例实际反馈比较；单个例子分数更好看不足以证明参数更准确。'},
]

FORMULAS = [
    {'title':'先算每个爻自身的分数','formula':'局部分 = 限定到 0–10（基础分 + 月令 + 日辰 + 空破 + 发动与动变）','detail':'同一条件每命中一次，加入对应分值；没有命中的项不加入。缺少起卦日期时不计日月项。'},
    {'title':'再算动爻对其他爻的作用','formula':'来源系数 = 来源局部分 ÷ 10 × 旬空系数 × 月破系数 × 暗动系数','detail':'未旬空、未月破、真正发动时相应乘数为 1；只有实验暗动来源才乘暗动系数。普通静爻的来源系数为 0。'},
    {'title':'计算每一项外来作用','formula':'作用分 = 生克权重 × 来源系数；关系修正也乘同一来源系数','detail':'例如来源局部分 6 分、动爻生扶权重 1，实际加 0.6 分；来源又旬空且系数 0.5，就只加 0.3 分。'},
    {'title':'合成最终强度','formula':'原始合计 = 基础分 + 自身全部加减项 + 外来作用；最终分 = 限定到 0–10（原始合计）','detail':'最终合计使用自身未截断的加减项；传给其他爻的作用只使用局部分，不反复循环放大。原始合计仍可查看。'},
    {'title':'判断强弱与候选排序','formula':'低于偏弱分界为偏弱；高于偏强分界为偏强；两端之间（含边界）为中等','detail':'取用排序分另算：综合分 + 发动排序加分 + 持世排序加分。它只用于同类候选排序，不再加到爻强度。'},
    {'title':'伏神与辅助候选','formula':'伏神分 = 限定到 0–10（基础分 + 日月空破 + 飞生伏/飞克伏）；辅助作用 = 方向 × 辅助强度÷10 × 辅助权重 × 主用权重','detail':'辅助作用仅单列摘要，未重复加入爻强度。三合、半合是结构识别，不自动加分或认定成化。'},
]
RATIONALE = '这些数字是软件初始的相对权重，没有来自原典的固定数值，也尚未用足量实际案例拟合。初始设计以 5 分为起点，0.5 表示较小调整，1 表示中等调整，2 表示较大调整；这套量尺用于比较同一模型中的强弱，不能换算成成功率。'


def explain_rule(key, row, definition):
    value=row['value'];unit=definition['unit'];name=definition['name']
    result={'id':key,'name':name,'category':definition['category'],'condition':definition['condition'],
            'value':value,'enabled':row['enabled'],'unit':unit,'type':definition['type'],
            'min':definition.get('min'),'max':definition.get('max'),'required':definition.get('required',False),
            'meaning':'','formula':'','increase':'','example':'','kind':'points'}
    if unit in ('开关','启用配对'):
        result.update(kind='switch',meaning='这是识别开关，请修改“启用”列。Value 中的 1 是占位标记，本身不参与加减分。',
                      formula='启用为“是”时识别；为“否”时不识别',increase='此项请调整启用状态，不靠增大 Value 调节力度。',
                      example='化进配对启用后，命中才计 ADVANCE 分；三合/半合仅展示结构，不直接加分。' if key.startswith('PROGRESS_') else '把启用改为“否”，对应结构将不再识别。')
    elif definition['type']=='branch':
        weight='CHANGE_TOMB' if key.startswith('TOMB_') else 'CHANGE_EXTINCT'
        result.update(kind='branch',meaning='指定判定化墓或化绝时对照的地支，不是强度分值。',formula=f'变爻地支等于本值时，应用 {weight} 的分值',
                      increase='没有调大或调小；更换地支会改变哪些卦命中。',example=f'当前设为“{value}”：命中后才应用相关的化墓或化绝分。不同门派约定可在这里明确选择。')
    elif key=='BASE_SCORE':
        result.update(kind='base',meaning=f'本卦的六个爻分别从 {value:g} 分开始计算，每一个爻都用这个起点；伏神也另从这个值计算。不是整卦只有 {value:g} 分，也不是已经判断六爻实际一样强。',formula='每爻原始合计 = 本值 + 该爻自身各项贡献 + 其他来源对该爻的作用；最终分限制在 0～10',increase='调大使每爻原始起点提高，也可能增加动爻对其他爻的作用。增加不保证每爻最终都等量增加：扣分来源变强、0～10边界都可能改变结果。',example=f'只演示单爻自身计算：{value:g}（起点）+2（月令旺）+1.5（日辰生）−1.5（旬空示例扣分）={value+2:g}；实际命中及分值以下方本卦账单为准。')
    elif key.startswith('LEVEL_'):
        result.update(kind='threshold',meaning='强弱标签的分界线，本身不增加或减少任何分数。',formula='分数 > 本值：偏强' if key=='LEVEL_STRONG' else '分数 < 本值：偏弱',increase='提高偏强分界会更难被标为偏强。' if key=='LEVEL_STRONG' else '提高偏弱分界会让更多爻被标为偏弱。',example=f'当前分界 {value:g}；恰好等于分界仍为中等。偏弱分界必须低于偏强分界。')
    elif key.startswith('SELECT_'):
        result.update(kind='ranking',meaning='只在同类用神有多个候选时增加排序分，不改变爻本身的综合分。',formula='候选排序分 = 综合分 + 命中的排序加分',increase='调大后更优先选择具有这项特征的候选。',example=f'候选综合分 6，命中本项当前加 {value:g}，排序分为 {6+value:g}；综合分仍为 6。')
    elif key in ('MAIN_FACTOR','AUXILIARY_FACTOR'):
        result.update(kind='summary_factor',meaning='辅助候选对主用的作用摘要乘数。当前只用于辅助作用摘要，不重复计入爻强度。',formula='摘要作用 = 生/克方向 × 辅助综合分÷10 × AUXILIARY_FACTOR × MAIN_FACTOR',increase='调大放大摘要作用的绝对值，生扶更正、克制更负。',example='辅助分 6、辅助权重 0.5、主用权重 1：生扶摘要为 +0.3，克制为 -0.3。')
    elif unit=='倍':
        result.update(kind='factor',meaning='乘在作用量上的比例。0.5 表示保留一半，1 表示原量，2 表示两倍。',formula='来源系数 = 来源局部分÷10 × 命中的各项乘数',increase='调大使该状态下来源的作用更强；减小使作用减弱。多个状态同时命中时连乘。',example=f'来源分 6、生扶权重 1，只命中本状态时：1 × 6÷10 × {value:g} = {0.6*value:g} 分。')
    elif key.startswith(('MOVE_','REL_')):
        result.update(kind='effect',meaning='来源满 10 分且无衰减时的作用权重。实际加减分还要乘来源系数。',formula='实际作用分 = 本值 × 来源系数',increase='数值调大使目标得分更高；负数从 -1 改到 -0.5 是减轻扣分，从 -1 改到 -2 是加重扣分。',example=f'来源局部分 6、无衰减：{value:g} × 6÷10 = {value*0.6:g} 分。普通静爻不主动计此项。')
    else:
        result.update(meaning='条件命中时，直接加到对应爻的分数上。正数加分，负数扣分，0 不计分。',formula='本项贡献 = 命中时本值，否则 0；停用时为 0',increase='数值调大使命中者分数更高；若是负数，绝对值变大则扣分更重。',example=f'只看这一项，从 5 分开始：5 + ({value:g}) = {5+value:g} 分。换成 0.5 / 1 / 2 时，分别为 5.5 / 6 / 7 分。')
    if key.startswith('MONTH_') and key!='MONTH_BREAK':
        result['rationale']='月令初始权重按旺、相、休、囚、死拉开相对强弱：+2、+1.5、-0.5、-1、-2。这是可校准的设计选择，不是古籍给出的计分公式。'
    elif value==0 and result['kind']=='effect':
        result['rationale']='初始设为 0，是为了先记录关系、避免单凭标签重复加扣分；确认有案例支持后再试调。'
    else:
        result['rationale']='初始取值用于表达相对影响大小，尚未经过充分案例校准。先一次改一项，观察命中条件和分数变化，再用实际反馈检验。'
    if key=='BASE_SCORE': result['rationale']=SCORE_INTRO[1]['text']
    if result['kind']=='switch': result['rationale']='这是程序识别选项，没有“1 分”的含义。是否启用，应根据所采用的结构约定决定；不会因数值写成 2 就识别得更强。'
    result['kind_label'],result['affects']=KINDS[result['kind']]
    if result['kind']=='summary_factor':
        result['increase']='各乘数均为正时，调大本值会放大摘要绝对值；设为 0 不产生摘要作用；设为负数会反转摘要方向。取值范围虽允许负数，不代表已有原理支持这种反转。'
        result['condition']='已经选定主用与辅助功能候选时，计算辅助候选对主目标的作用摘要'
    result['source_type']='软件实验参数／可调约定'
    result['source_note']='本项属于程序模型设定。相关原理的定性含义与这个数值的有效性需要分别判断；尚无经验证的最优值或成功率换算。'
    result['tuning_note']='保留默认即可使用。下面可查看计算明细，再自愿试改；试算不会保存或改写历史案例。'
    return result


def rule_guide(book):
    definitions=schema()['rules']
    return {'version':book.version,'rationale':RATIONALE,'formulas':FORMULAS,'intro':SCORE_INTRO,
            'kinds':[{'id':k,'name':v[0],'meaning':v[1]} for k,v in KINDS.items()],
            'rules':[explain_rule(row['id'],row,definitions[row['id']]) for row in book.compiled['rules']]}


def preview_rule(book, key, value, enabled, input_data=None):
    if key not in book.rows:raise ValueError('未知规则编号')
    rows=deepcopy(book.compiled['rules'])
    row=next(row for row in rows if row['id']==key);row.update(value=value,enabled=enabled)
    changed=RuleBook(compile_rules(rows))
    from .pipeline import calculate_chart
    demo={'lines':['young_yang','young_yin','young_yin','young_yang','old_yin','young_yang'],'actual_cast_time':'2026-09-18T12:00:00+08:00'}
    supplied=bool(input_data)
    actual=input_data if supplied else demo
    chart=calculate_chart(actual,book)
    before=chart['comprehensive_analysis']
    after=calculate_chart(actual,changed)['comprehensive_analysis']
    def present(line):
        s=line['strength'];return {'position':line['position'],'name':line['relative']+line['branch']+line['element'],
                                  'score':s['score'],'raw_score':s['raw_score'],'level':s['level']}
    return {'saved':False,'example':'当前显示卦盘，按当前规则重新试算（历史报告未改）' if supplied else '固定演示卦（2026-09-18 12:00，不是你的案例）',
            'chart_name':chart['main']['name'], 'rule_kind':explain_rule(key,row,schema()['rules'][key])['kind'],
            'before_trace':score_trace(before,book),'after_trace':score_trace(after,changed),
            'before_structures':{'pairs':before['pair_relations'],'groups':before['combination_groups'],'changes':[{'position':l['position'],'effects':l['change']['effects'] if l['change'] else []} for l in before['lines']]},
            'after_structures':{'pairs':after['pair_relations'],'groups':after['combination_groups'],'changes':[{'position':l['position'],'effects':l['change']['effects'] if l['change'] else []} for l in after['lines']]},
            'before':[present(l) for l in before['lines']],'after':[present(l) for l in after['lines']],
            'before_hidden':before['hidden_spirits'],'after_hidden':after['hidden_spirits'],
            'note':'此处比较爻分数、强弱标签和伏神。取用排序、辅助摘要及结构识别参数可能不改变分数；可对照上方公式理解其作用。没有保存参数，也没有改写历史预测。'}


def score_trace(analysis, book):
    """Project actual engine contributions; never recreate a competing formula."""
    definitions=schema()['rules']
    result=[]
    for line in analysis['lines']:
        own=line['local_strength']; strength=line['strength']
        local=[dict(c,name=definitions[c['rule_id']]['name'],enabled=book.enabled(c['rule_id']),parameter=book.value(c['rule_id'])) for c in own['contributions']]
        incoming=[]
        for effect in analysis['effects']:
            if effect['target_position']!=line['position'] or not effect['active']:continue
            source=analysis['lines'][effect['source_position']-1]
            dm=source['day_month']
            multipliers=[{'name':'来源局部分÷10','value':source['local_strength']['score']/10}]
            for condition,key in ((dm['empty'],'SOURCE_EMPTY_FACTOR'),(dm['month_break'],'SOURCE_BROKEN_FACTOR'),(not source['moving'],'HIDDEN_SOURCE_FACTOR')):
                if condition:multipliers.append({'name':definitions[key]['name'],'value':book.value(key)})
            for contribution in effect['contributions']:
                incoming.append(dict(contribution,name=definitions[contribution['rule_id']]['name'],
                    enabled=book.enabled(contribution['rule_id']),parameter=book.value(contribution['rule_id']),
                    source=source['position'],multipliers=multipliers))
        result.append({'position':line['position'],'name':line['relative']+line['branch']+line['element'],
            'base':strength['base'],'local_items':local,'incoming_items':incoming,
            'local_raw':own['raw_score'],'local_score':own['score'],'raw_score':strength['raw_score'],
            'score':strength['score'],'level':strength['level'],'weak':book.value('LEVEL_WEAK'),'strong':book.value('LEVEL_STRONG'),
            'coverage':strength['coverage'],'calendar_available':strength['calendar_available']})
    return result
