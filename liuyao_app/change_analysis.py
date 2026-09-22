"""Changed kinship uses the ORIGINAL palace; structural labels are not omens."""
import base_chart as base
from liuyao_app.day_month_analysis import element_relation, xun_empty, clash
from liuyao_app.rulebook import schema
ELEMENT_KEYS=dict(zip('木火土金水',('WOOD','FIRE','EARTH','METAL','WATER')))

def analyze_change(line, changed_branch, palace_element, calendar, rules):
    element=base.BRANCH_ELEMENTS[changed_branch]
    relation=element_relation(element,line['element'])
    relative=base.ordinary_relative(palace_element,element)
    effects=[]; contributions=[]
    def effect(label,key):
        if rules.enabled(key):
            effects.append(label);contributions.append(rules.contribution(key,label))
    if relation=='generates': effect('回头生','RETURN_GENERATE')
    elif relation=='controls': effect('回头克','RETURN_CONTROL')
    for key, spec in schema()['rules'].items():
        if key.startswith('PROGRESS_') and rules.enabled(key):
            a,b=spec['pair']
            if (line['branch'],changed_branch)==(a,b): effect('化进','ADVANCE')
            elif (line['branch'],changed_branch)==(b,a): effect('化退','RETREAT')
    e=ELEMENT_KEYS[line['element']]
    for prefix,label,weight in [('TOMB_','化墓','CHANGE_TOMB'),('EXTINCT_','化绝','CHANGE_EXTINCT')]:
        if rules.enabled(prefix+e) and changed_branch==rules.value(prefix+e): effect(label,weight)
    changed_empty=None; changed_break=None
    if calendar.get('status')=='computed':
        changed_empty=changed_branch in xun_empty(calendar['pillars']['day'])['branches']
        changed_break=clash(changed_branch,calendar['pillars']['month'][1])
        if changed_empty:effect('化空','CHANGE_EMPTY')
        if changed_break:effect('化月破','CHANGE_MONTH_BREAK')
    return {'position':line['position'],'original':line['branch'],'original_element':line['element'],
        'changed':changed_branch,'changed_element':element,'relative':relative,'relative_code':base.RELATIVE_CODES[relative],
        'reference_palace_element':palace_element,'relation':relation,'effects':effects,
        'changed_empty':changed_empty,'changed_month_break':changed_break,'contributions':contributions,'status':'experimental'}
