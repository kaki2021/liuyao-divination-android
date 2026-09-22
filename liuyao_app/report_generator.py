"""Canonical report adapter, with a deterministic fallback after report failure."""
from copy import deepcopy
from liuyao_app.report_template import SECTIONS, format_divination_report
LABELS={'generates':'生','controls':'克','same':'同类','drains':'被生（目标生来源）','consumes':'被克（目标克来源）'}

def computed_sections(chart):
    a=chart.get('comprehensive_analysis',{}); lines=a.get('lines',[])
    u=a.get('use_selection',{}).get('primary') or {};target=u.get('chosen')
    chosen=next((l for l in (a.get('hidden_spirits',[]) if target and target['layer']=='hidden' else lines) if target and l['position']==target['position']),None)
    targets=[chosen] if chosen else lines
    dm=[]
    for l in targets:
        d=l['day_month'];s=l['strength'];identity=f"{'伏神' if target and target['layer']=='hidden' else '第'+str(l['position'])+'爻'}{l['relative']}{l['branch']}{l['element']}"
        if d['status']=='computed':
            dm.append(f"{identity}：月令{d['month_class']}，月支{d['month_branch']}与本爻{LABELS[d['month_relation']]}，日支{d['day_branch']}与本爻{LABELS[d['day_relation']]}；综合{s['score']:g}/10（{s['level']}）。")
        else:dm.append(f"{identity}：起卦时间未提供或未能计算日月；当前局部分{s['score']:g}/10。")
    changes=[]
    for l in lines:
        c=l.get('change')
        if c:changes.append(f"第{l['position']}爻{l['relative']}{l['branch']}{l['element']}动，变{c['relative']}{c['changed']}{c['changed_element']}；{'、'.join(c['effects']) or '没有启用规则命中的进退墓绝空标记'}。")
    sy=[]
    if lines:
        s=lines[chart['shi_position']-1];y=lines[chart['ying_position']-1]
        from liuyao_app.day_month_analysis import element_relation
        sy=[f"世为第{s['position']}爻{s['branch']}{s['element']}，{s['strength']['score']:g}/10；应为第{y['position']}爻{y['branch']}{y['element']}，{y['strength']['score']:g}/10。应对世：{LABELS[element_relation(y['element'],s['element'])]}。"]
    rel=[f"第{p['positions'][0]}、{p['positions'][1]}爻：{'、'.join(p['labels'])}" for p in a.get('pair_relations',[])]
    return {'day_month':'\n'.join(dm),'change':'\n'.join(changes) or '本卦六爻安静，无动爻变爻。',
            'shi_ying':'\n'.join(sy),'relations':'；'.join(rel) or '本次未检出启用规则中的合冲形害配对。'}

def legacy_sections(output,chart):
    sections=computed_sections(chart)
    parts={p['dimension']:p['text'] for p in output.get('parts',[]) if isinstance(p,dict) and isinstance(p.get('text'),str) and 'dimension' in p}
    if parts.get('subject_effect'): sections['shi_ying'] += '\n'+parts['subject_effect']
    sections.update(support=parts.get('support','本次未单列支持因素。'),obstacle=parts.get('obstacle','本次未单列阻碍因素。'),advice=parts.get('adjustment','请记录事情进展，便于回看本次判断。'))
    return [{'key':k,'heading':h,'content':sections.get(k,'')} for k,h in SECTIONS]

def normalize_report(output,server_input):
    result=deepcopy(output)
    if 'sections' not in result and isinstance(result.get('parts'),list):
        result['sections']=legacy_sections(result,server_input.get('analysis_chart',{}))
    plain=result.get('plain_language')
    if plain is None and isinstance(result.get('conclusion'),dict):
        result['plain_language']=plain_fallback(result['conclusion'])
    elif isinstance(plain,dict):
        plain['source']='ai'
    # Compatibility-only research fields are preserved in raw AI event, not duplicated in user report.
    return {k:result[k] for k in ('binding','summary','conclusion','sections','plain_language') if k in result}

def build_user_report(report, model_info=None):
    sections={s['key']:s['content'] for s in report['sections']}
    result=format_divination_report(deepcopy(report['conclusion']),sections)
    result['plain_language']=deepcopy(report.get('plain_language') or plain_fallback(report['conclusion']))
    result['model_info']=model_info or {}
    return result

def fallback_report(interpretation,chart):
    sections=computed_sections(chart)
    for key,dimension in [('support','support'),('obstacle','obstacle'),('advice','adjustment')]:
        texts=[c['statement'] for c in interpretation.get('claims',[]) if c['dimension']==dimension]
        if key=='advice':texts.extend(a['text'] for a in interpretation.get('advice',[]))
        sections[key]='\n'.join(texts) or {'support':'本次推演未单列支持因素。','obstacle':'本次推演未单列阻碍因素。','advice':'请结合目前条件推进，并记录实际进展。'}[key]
    result=format_divination_report(deepcopy(interpretation['conclusion']),sections)
    result['plain_language']=plain_fallback(interpretation['conclusion'])
    return result


# Compatibility display for saved reports; original conclusions remain intact.
import re
TECHNICAL_WORDS = re.compile(r'用神|官鬼|妻财|父母爻|兄弟爻|子孙|世爻|应爻|应克世|持世|动爻|变爻|旬空|月令|日辰|生扶|回头生|回头克|实验|综合分|结构性|第[一二三四五六123456]爻|GAP_|claim_refs')


def plain_fallback(conclusion):
    direction=conclusion.get('direction','undetermined')
    answer=conclusion.get('answer','')
    lead=re.split(r'[：:；;。\n]',answer,1)[0].strip()
    lead=re.sub(r'^按本次卦象[，,]?','',lead)
    if not lead or len(lead)>100 or TECHNICAL_WORDS.search(lead):
        lead={'favorable':'这件事偏向能成，但仍有条件需要落实。',
              'unfavorable':'这件事目前偏向难成，需要先解决主要阻碍。',
              'mixed':'有机会，但推进中可能有反复，暂不能判断会顺利办成。',
              'undetermined':'目前还无法给出明确判断。'}.get(direction,'目前还无法给出明确判断。')
    return {'direction':direction,'answer':lead.rstrip('。')+'。','reason':'',
            'watch_for':[],'next_steps':[],'timing':'','source':'compatibility'}


def plain_schema():
    text=lambda n:{'type':'string','maxLength':n}
    items={'type':'array','maxItems':3,'items':text(120)}
    props={'direction':{'type':'string','enum':['favorable','unfavorable','mixed','undetermined']},
           'answer':dict(text(120),minLength=1),'reason':text(320),'watch_for':items,'next_steps':items,'timing':text(160),
           'source':{'type':'string','enum':['ai','compatibility']}}
    return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
