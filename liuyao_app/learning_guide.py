"""Reading guidance derived from the shipped catalog, not invented quotations."""
import json
from pathlib import Path

TOPICS = [
    ('intent.plan_before_cast', '先认真谋划，再卜疑处', '原文称“谋而后卜”。谋事时先说明已有条件、准备采取的做法与未拿准之处，再借卦检查这项计划。若还在诊断问题，先明确待查范围，不编造整改方案；不能把这理解为任何泛问都无需准备。'),
    ('intent.true_concern', '把真正关心的用途说出来', '同样问一辆车，自用、转卖获利、运输经营的关注点不同。写你实际想解决的事；AI 只能整理你表达的关切，不能声称看穿你的隐藏想法。'),
    ('intent.main_question', '本次围绕一个焦点', '同一件事能否办成、对自己有什么得失和代价，可以一起讨论。彼此无关的问题应另行记录，不固定规定一个场景必须起几卦。'),
    ('interpretation.functional_role', '按本次功能取用', '先看对象在这次问题里承担什么作用，再确定六亲和候选爻。不能只看“房子”“钱”等关键词就固定取用。'),
    ('interpretation.gains_before_success', '成事与自身得失分开看', '一件事办成也可能代价过大；过程受益也不代表目标已经实现。读答案时一起看成立条件、主体得失和代价。'),
    ('interpretation.three_self_references', '世、世身与卦身各有尺度', '按问题涉及的主体层次选取参照，保留世、世身和卦身的区别；不能看到哪个分数高就换用哪个。具体采用条件在专业分析中说明。'),
    ('interpretation.target_effects', '强弱要结合所问目标', '较强的爻可能是支持，也可能是阻碍。先确定作用对象，再解释影响；一个高分、一个相生或相克，都不能独立变成最终成败。'),
    ('buzhai.site_then_divination', '卜宅先有具体对象和方案', '先看现场与现实条件，明确谁使用、哪个地点、怎样使用或整改，再提出本次疑问。软件不能替代相地和方案设计。'),
    ('buzhai.workflow', '选房、查问题、验方案分别记录', '择地是独立场景；治风水则按原文依次核对范围、另问具体问题、再问整改方案。不是所有人都起四卦，也不是治理时任选一步就完成全流程。方案判断不利先复查与调整，再记录新的主问；实施后的效果另做反馈。'),
]


def usage_guide():
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'software_prep/rule_catalog.json').read_text())
    rules = {r['rule_id']:r for r in catalog['rules']}
    sources = {s['source_id']:s for s in catalog['sources']}
    review = json.loads((Path(__file__).resolve().parents[1] / 'software_prep/reading_review.json').read_text())
    entries = []
    for key, title, help_text in TOPICS:
        rule = rules[key]
        entries.append({'id':key, 'title':title, 'help':help_text, 'catalog_summary':rule['statement'],
                        'source':sources[rule['source_id']]['title'], 'locator':rule['source_locator'],
                        'limitations':rule.get('limitations',[]), **review['rules'][key]})
    return {'title':'怎样问、怎样起、怎样用',
            'source_note':'已于 2026-09-20 核对《卜筮正术》001、003、010～012 与《卜筮正术补充卜宅》044 的相关正文。以下白话是整理说明；展开可区分原文短引、课次定位和软件采用方式。原理有出处，不等于实验分值已由原书规定或经案例验证。',
            'purpose':'先谋划现实中的做法，再就未拿准之处起卦；用于检查计划、权衡得失和改进做法，保留后续事实反馈。',
            'rules':entries,
            'workflow':[
                {'title':'明确所问','text':'谋事写清具体计划、已知条件与疑点；诊断先写清待查范围和目的。保留本人真实关切，不让 AI 猜来意。'},
                {'title':'记录实际起卦','text':'按器具说明操作，保存本次真实结果及当时的时间。软件只翻译和排盘，不代替实际摸取或摇卦。'},
                {'title':'分层阅读结果','text':'先读直接答案，再看条件与专业依据。程序结构、实验评分、AI 判断和实际发生结果分别辨认。'},
                {'title':'留存后续反馈','text':'记录实际进展。补充事实后可继续分析原卦；重新解卦调用 AI，不会自动再起一卦。新起一卦另建案例。'}]}
