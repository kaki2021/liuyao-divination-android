"""Bundled skill descriptions and bounded, versioned presentation preferences.

Skill files are data. Loading a skill never executes downloaded Python or shell.
Domain tools remain explicit application-owned entry points.
"""
import json
from pathlib import Path

ROOT = Path(__file__).with_name('skills')
SKILL_IDS = ('liuyao', 'knowledge')
DEFAULT_PREFERENCES = {'detail': 'balanced', 'layout': 'paragraphs',
                       'tone': 'plain', 'clarify_first': True}
OPTIONS = {'detail': ('concise', 'balanced', 'detailed'),
           'layout': ('paragraphs', 'steps'), 'tone': ('plain', 'beginner')}


def skill_info(skill_id):
    if skill_id not in SKILL_IDS:
        raise ValueError('没有这个技能。')
    value = json.loads((ROOT / skill_id / 'manifest.json').read_text(encoding='utf-8'))
    return {**value, 'instructions': (ROOT / skill_id / 'SKILL.md').read_text(encoding='utf-8')}


def validate_preferences(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_PREFERENCES):
        raise ValueError('技能偏好字段不完整。')
    for key, choices in OPTIONS.items():
        if not isinstance(value[key], str) or value[key] not in choices:
            raise ValueError('技能偏好选项无效。')
    if type(value['clarify_first']) is not bool:
        raise ValueError('澄清偏好无效。')
    return dict(value)


def preference_prompt(snapshot):
    """Only closed enums become instructions; model/issue free text never does."""
    if not snapshot:
        return ''
    p = validate_preferences(snapshot['preferences'])
    detail = {'concise': '简洁回答，先给结论，保留必要条件。',
              'balanced': '先回答所问，再说明必要依据。',
              'detailed': '充分解释依据、条件和推导步骤。'}[p['detail']]
    layout = '需要列举时按步骤组织。' if p['layout'] == 'steps' else '优先用连贯段落表达。'
    tone = '面向新手，解释专业术语。' if p['tone'] == 'beginner' else '使用朴素、准确的中文。'
    clarify = '资料不足时明确缺口，并提出具体澄清问题。' if p['clarify_first'] else '先回答资料能支持的部分，再说明缺口。'
    return ('\n表达偏好（仅影响措辞和组织，不改变原始事实、规则、计算、引用、JSON结构和判断边界）：'
            + detail + layout + tone + clarify)
