"""One-way source-to-target effects using frozen local strengths (no recursion)."""
import branch_relations
from liuyao_app.day_month_analysis import element_relation, clash, combine, RELATION_LABELS

def pair_labels(a,b,rules):
    labels=[]
    if clash(a,b):labels.append('六冲')
    if combine(a,b):labels.append('六合')
    for r in branch_relations.classify_pair(a,b)['relations']:
        label='三形' if 'form' in r['relation_type'] else '六害'
        if label not in labels:labels.append(label)
    if rules.enabled('ENABLE_BREAK') and a!=b and any(set((a,b))==set(p) for p in ('子酉','丑辰','寅亥','卯午','巳申','未戌')):labels.append('相破')
    if rules.enabled('ENABLE_HIDDEN_COMBINE') and a!=b and any(set((a,b))==set(p) for p in ('寅丑','午亥','卯申')):labels.append('暗合')
    return labels

def evaluate_relation_effect(source,target,rules):
    relation=element_relation(source['element'],target['element'])
    active=bool(source['moving'] or source['day_month']['hidden_moving'])
    factor=source['local_strength']['score']/10 if active else 0
    if source['day_month']['empty']:factor*=rules.value('SOURCE_EMPTY_FACTOR')
    if source['day_month']['month_break']:factor*=rules.value('SOURCE_BROKEN_FACTOR')
    if not source['moving'] and active:factor*=rules.value('HIDDEN_SOURCE_FACTOR')
    label=f"第{source['position']}爻→第{target['position']}爻"
    contributions=[rules.contribution('MOVE_'+relation.upper(),label+' '+RELATION_LABELS[relation],factor)] if active else []
    labels=pair_labels(source['branch'],target['branch'],rules)
    mapping={'六合':'REL_COMBINE','六冲':'REL_CLASH','三形':'REL_FORM','六害':'REL_HARM','相破':'REL_BREAK','暗合':'REL_HIDDEN_COMBINE'}
    if active:contributions.extend(rules.contribution(mapping[k],label+' '+k,factor) for k in labels)
    return {'source_position':source['position'],'target_position':target['position'],
        'relation':relation,'labels':labels,'active':active,'source_factor':round(factor,6),
        'effect':round(sum(c['value'] for c in contributions),6),'contributions':contributions}
