"""Explainable additive experimental scores; never calibrated probabilities."""
def calculate_strength(rules, contributions, *, calendar_available=True):
    raw=rules.value('BASE_SCORE')+sum(item['value'] for item in contributions)
    score=round(max(0,min(10,raw)),3)
    level='偏弱' if score<rules.value('LEVEL_WEAK') else '偏强' if score>rules.value('LEVEL_STRONG') else '中等'
    return {'score':score,'raw_score':round(raw,3),'base':rules.value('BASE_SCORE'),'level':level,
        'contributions':contributions,'status':'experimental','rules_version':rules.version,
        'coverage':'日月、动变与爻间作用' if calendar_available else '仅动变与爻间作用，缺日月',
        'calendar_available':calendar_available}
