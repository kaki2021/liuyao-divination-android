"""Calendar structures and configurable experimental day effects."""
import base_chart as base
STEMS = '甲乙丙丁戊己庚辛壬癸'
COMBINATIONS = ('子丑','寅亥','卯戌','辰酉','巳申','午未')
RELATION_LABELS={'same':'同类','generates':'生扶','controls':'克制','drains':'本爻生来源而泄气','consumes':'本爻克来源而耗气'}
MONTH_KEYS = dict(zip('旺相休囚死', ('WANG','XIANG','XIU','QIU','SI')))

def element_relation(source, target):
    if source == target: return 'same'
    if base.GENERATES[source] == target: return 'generates'
    if base.CONTROLS[source] == target: return 'controls'
    if base.GENERATES[target] == source: return 'drains'
    return 'consumes'

def clash(a, b): return (base.BRANCHES.index(a) - base.BRANCHES.index(b)) % 12 == 6
def combine(a, b): return a != b and any(set((a,b)) == set(p) for p in COMBINATIONS)

def xun_empty(day_pillar):
    if not isinstance(day_pillar,str) or len(day_pillar)!=2: raise ValueError('日柱格式错误')
    cycle = [STEMS[i%10]+base.BRANCHES[i%12] for i in range(60)]
    if day_pillar not in cycle: raise ValueError('日柱不在六十甲子中')
    start = cycle.index(day_pillar)//10*10
    return {'xun':cycle[start], 'branches':[base.BRANCHES[(start+10)%12],base.BRANCHES[(start+11)%12]]}

def analyze_day_month(line, calendar, rules):
    result = {'position':line['position'], 'status':'missing', 'month_branch':None, 'day_branch':None,
        'month_class':None, 'month_relation':None, 'day_relation':None, 'empty':None,
        'month_break':None, 'day_clash':None, 'day_combine':None, 'hidden_moving':None, 'day_break':None, 'contributions':[]}
    if calendar.get('status')!='computed': return result
    pillars=calendar['pillars']; month=pillars['month'][1]; day=pillars['day'][1]; branch=line['branch']
    mc=base.ordinary_month_strength(base.BRANCH_ELEMENTS[month],line['element'])
    dr=element_relation(base.BRANCH_ELEMENTS[day],line['element']); empty=xun_empty(pillars['day'])
    is_empty=branch in empty['branches']; broken=clash(month,branch); hit=clash(day,branch)
    hidden=not line['moving'] and hit and mc in '旺相' and not is_empty and not broken and rules.enabled('HIDDEN_MOVE')
    day_break=not line['moving'] and hit and mc not in '旺相' and rules.enabled('DAY_BREAK')
    result.update(status='computed',month_branch=month,day_branch=day,month_class=mc,
        month_relation=element_relation(base.BRANCH_ELEMENTS[month],line['element']),day_relation=dr,
        empty=is_empty,xun=empty,month_break=broken,day_clash=hit,day_combine=combine(day,branch),
        hidden_moving=hidden,day_break=day_break)
    mods=result['contributions']
    mods.append(rules.contribution('MONTH_'+MONTH_KEYS[mc], '月令'+mc))
    mods.append(rules.contribution('DAY_'+dr.upper(), '日辰对本爻：'+RELATION_LABELS[dr]))
    for key,flag,label in [('EMPTY',is_empty,'旬空'),('MONTH_BREAK',broken,'月破'),('DAY_CLASH',hit,'日冲'),
                           ('DAY_COMBINE',result['day_combine'],'日合'),('HIDDEN_MOVE',hidden,'实验暗动'),('DAY_BREAK',day_break,'实验日破')]:
        if flag: mods.append(rules.contribution(key,label))
    return result
