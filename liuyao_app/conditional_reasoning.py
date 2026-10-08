"""Question-scoped, three-valued condition checks, independent of score weights.

Eligibility is not proof of an effective operation. Unknown conditions remain
unknown, especially whole-chart strength and competing operation priorities.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import base_chart as base
import branch_relations
from .day_month_analysis import element_relation, xun_empty, clash, combine, RELATION_LABELS

MODEL_VERSION = '条件判断 1'
RULES = (
    ('functional_use', '按用途取用', '取用', '按原问中的对象、用途和关切匹配六亲或主体参照。',
     '用途明确后定位；同类多现保留候选，不按实验分选中最高者。', ['interpretation.functional_role']),
    ('target_scope', '围绕本问核对作用', '作用', '先明确本问目标，再列来源对目标的候选关系。',
     '结构关系不等于有效作用；来源状态与目标优先级分别核对。', ['interpretation.target_effects']),
    ('change_empty', '原爻旬空与动爻化空分开', '空破', '原爻支和变支分别与起卦日的旬空比较。',
     '识别为空时记录状态；对目标的影响和解除条件留待有依据的判断，不固定扣分。', []),
    ('form_context', '三形结合整体判断', '形害', '配对存在后，仍需独立判断整体趋势及与目标的关系。',
     '只列形的类别和条件；不凭形标签判吉凶，也不循环证明整体趋势。', ['interpretation.three_forms_context']),
    ('harm_direction', '六害分类型与方向', '形害', '识别恩间或害间，区分来源、目标和涉及的合支。',
     '分别展示方向与结构；不统一扣分，不由配对推定现实人物动机。', ['relation.six_harms_categories']),
    ('residence_empty', '尚未入住的世空例外', '卜宅', '使用者本人、阳宅选房、尚未入住、世爻旬空且世旺。',
     '前提均成立才可讨论不因世空单独否定；世旺未核定时保留未知。', ['buzhai.empty_scope']),
    ('outcome_dimensions', '得失与成败分开', '结论', '区分主体受益或代价和目标能否实现。',
     '世应、身位生克只列结构与条件；两个判断维度分别解释。', ['interpretation.gains_before_success']),
    ('timing_limits', '时间条件与判断范围', '结论', '区分起卦时间、所问期限和后续作用条件。',
     '没有完整应期判据时不生成精确日期；这是系统能力边界。', []),
)

# source, affected branch -> the third branch whose combination is discussed.
# These are interpretive routes from lesson 058, not assertions of actual intent.
HARM_ROUTES = {
    '子未': ('午', '相克关系；来源也受目标克制'), '未子': ('丑', '相克关系'),
    '卯辰': ('酉', '相克关系；涉及来源冲酉时受金克的风险'), '辰卯': ('戌', '相克关系；来源受目标克制'),
    '午丑': ('子', '来源生目标'), '丑午': ('未', '目标生来源'),
    '酉戌': ('卯', '涉及保护目标与目标生来源'), '戌酉': ('辰', '来源生目标'),
    '寅巳': ('申', '来源生目标'), '巳寅': ('亥', '目标生来源'),
    '申亥': ('寅', '来源生目标'), '亥申': ('巳', '涉及保护目标'),
}


def condition(key, label, value, note='', missing_kind=None):
    if value is not None and type(value) is not bool:
        raise ValueError('Condition values must be true, false or unknown')
    return {'id': key, 'label': label, 'status': 'unknown' if value is None else 'satisfied' if value else 'unsatisfied',
            'value': value, 'note': note, 'missing_kind': missing_kind if value is None else None}


def conjunction(checks):
    statuses = {c['status'] for c in checks}
    return 'unsatisfied' if 'unsatisfied' in statuses else 'unknown' if 'unknown' in statuses else 'satisfied'


def rule_guide():
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'software_prep/rule_catalog.json').read_text())
    by_id = {r['rule_id']: r for r in catalog['rules']}
    sources = {s['source_id']: s for s in catalog['sources']}
    entries = []
    for key, name, scene, scope, policy, ids in RULES:
        evidence = [{'title': sources[by_id[i]['source_id']]['title'], 'locator': by_id[i]['source_locator'],
                     'statement': by_id[i]['statement'], 'rule_id': i} for i in ids]
        entries.append({'id': key, 'name': name, 'scene': scene, 'scope': scope, 'policy': policy,
                        'sources': evidence, 'implementation': '已实现结构与条件核对；具体解释仍需条件判断'})
    return {'model_version': MODEL_VERSION, 'version': logic_digest(), 'rules': entries,
            'statuses': {'satisfied': '满足', 'unsatisfied': '不满足', 'unknown': '未知'},
            'note': '每条规则的状态表示适用前提，不表示已发生的作用或事情成败。'}


def logic_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _line_state(line, chart, layer='visible'):
    calendar = chart.get('calendar', {})
    known = calendar.get('status') == 'computed'
    day = calendar['pillars']['day'] if known else None
    month = calendar['pillars']['month'][1] if known else None
    empty = xun_empty(day)['branches'] if known else None
    branch = line['branch']
    moving = bool(line.get('moving'))
    changed_branch = chart['changed_structure']['branches'][line['position']-1] if moving else None
    return {'position': line['position'], 'layer': layer, 'branch': branch, 'element': line['element'],
            'relative': line['relative'], 'relative_code': line['relative_code'], 'moving': moving,
            'month_class': base.ordinary_month_strength(base.BRANCH_ELEMENTS[month], line['element']) if known else None,
            'day_relation': element_relation(base.BRANCH_ELEMENTS[day[1]], line['element']) if known else None,
            'empty': branch in empty if known else None, 'month_break': clash(branch, month) if known else None,
            'day_clash': clash(branch, day[1]) if known else None,
            'day_combine': combine(branch, day[1]) if known else None,
            'changed_branch': changed_branch,
            'changed_empty': changed_branch in empty if moving and known else None,
            'changed_month_break': clash(changed_branch, month) if moving and known else None,
            'return_relation': element_relation(base.BRANCH_ELEMENTS[changed_branch], line['element']) if moving else None,
            'comprehensive_strength': None, 'effective_operation': 'unknown'}


def evaluate_conditions(chart, input_data, selection=None):
    """Read-only, reusable for normal charts, saved snapshots and scenario trials."""
    lines = [_line_state(line, chart) for line in chart['main']['lines']]
    present = {line['relative_code'] for line in lines}
    hidden = []
    for position, branch in enumerate(base.PURE_BRANCHES[chart['main']['palace']], 1):
        element = base.BRANCH_ELEMENTS[branch]
        relative = base.ordinary_relative(chart['main']['palace_element'], element)
        code = base.RELATIVE_CODES[relative]
        if code not in present:
            hidden.append(_line_state({'position': position, 'branch': branch, 'element': element,
                                      'relative': relative, 'relative_code': code, 'moving': False}, chart, 'hidden'))
    selected = next((c for c in (selection or {}).get('candidates', [])
                     if c['candidate_id'] == (selection or {}).get('selected_primary_id')), None)
    matches = []
    if selected:
        reference = selected.get('subject_reference')
        if reference:
            position = chart['shi_position'] if reference == 'shi' else chart['shi_body_position']
            matches = [line for line in lines if line['position'] == position]
        else:
            matches = [line for line in lines if line['relative_code'] == selected['six_relative']]
            if not matches:
                matches = [line for line in hidden if line['relative_code'] == selected['six_relative']]
    checks = []
    def check(key, conditions, result):
        name=next(r[1] for r in RULES if r[0]==key)
        checks.append({'rule_id': key, 'name': name, 'conditions': conditions, 'status': conjunction(conditions), 'result': result})
    check('functional_use', [condition('purpose', '本次用途已明确', bool(selected) if selection else None,
                                       '取用阶段的功能理解属于 AI 候选解释。', 'analysis_pending'),
                             condition('one_line', '具体用神有唯一匹配', True if len(matches) == 1 else None,
                                       '多现候选需有用途及位置依据；不按实验分强选。',
                                       'analysis_pending' if not selected else 'system_criteria')],
          '唯一匹配只完成结构定位；多现保留所有位置。')
    effects = []
    for target in matches:
        for source in lines:
            if target['layer'] == 'visible' and source['position'] == target['position']:
                continue
            activation = True if source['moving'] else None if source['day_clash'] is not False else False
            conditions = [condition('source_active', '来源能作为本问作用来源', activation,
                                    '发动是已知结构；日冲静爻的有效暗动尚无完整判据。', 'system_criteria'),
                          condition('priority', '作用目标及先后条件已核定', None,
                                    '目前保留候选关系，不认为全部生克同时生效。', 'system_criteria')]
            effects.append({'source_position': source['position'], 'target_position': target['position'],
                            'target_layer': target['layer'], 'relation': element_relation(source['element'], target['element']),
                            'relation_label': RELATION_LABELS[element_relation(source['element'], target['element'])],
                            'status': conjunction(conditions), 'conditions': conditions, 'effective': None})
    check('target_scope', [condition('target', '本问目标已有爻位候选', True if matches else None,
                                    missing_kind='analysis_pending' if not selected else 'system_criteria'),
                           condition('priority', '有效作用及优先级已核定', None,
                                     '仅列本问目标相关的候选关系。', 'system_criteria')],
          '作用表分别记录来源和目标；未知项不自动当作有效。')
    moving = [line for line in lines if line['moving']]
    has_change_empty = any(line['changed_empty'] for line in moving) if chart.get('calendar', {}).get('status') == 'computed' else None
    check('change_empty', [condition('changed_empty', '本卦存在动爻化空', has_change_empty,
                                     '先识别变支旬空，原爻旬空另列。', 'user_fact')],
          '化空影响、能否作用及后续时间条件不由固定扣分决定。')
    pairs = chart.get('line_pair_relations', [])
    forms = [pair for pair in pairs if any(r['relation_type'] == 'mutual_form' for r in pair['relations'])]
    harms = [pair for pair in pairs if any(r['relation_type'] == 'mutual_harm' for r in pair['relations'])]
    check('form_context', [condition('pair', '本卦出现三形配对', bool(forms)),
                           condition('whole', '整体趋势有独立判断依据', None,
                                     '三形标签不能先定吉凶再反证整体。', 'system_criteria')], '配对与类别已列；整体解释仍待判断。')
    harm_routes = []
    for pair in harms:
        a, b = pair['positions']
        for source, target in ((lines[a-1], lines[b-1]), (lines[b-1], lines[a-1])):
            third, meaning = HARM_ROUTES[source['branch']+target['branch']]
            category = next(r['category_label'] for r in pair['relations'] if r['relation_type'] == 'mutual_harm')
            harm_routes.append({'source': source['position'], 'target': target['position'], 'category': category,
                                'combination_partner': third, 'route': meaning,
                                'partner_positions': [l['position'] for l in lines if l['branch'] == third],
                                'status': 'structural_only'})
    check('harm_direction', [condition('pair', '本卦出现六害配对', bool(harms)),
                             condition('effective', '具体方向与本问的有效作用已核定', None,
                                       '类别和方向已识别，现实动机与效果仍未知。', 'system_criteria')],
          '分别显示恩间、害间及两个方向，不统一视作负面作用。')
    context = input_data.get('buzhai') or {}
    shi = lines[chart['shi_position']-1]
    def scene_value(key, expected):
        if not context:
            return False  # User did not enable this topic: not applicable, not a missing field.
        actual = context.get(key)
        return None if actual is None or actual == 'unknown' or (key == 'role' and actual == 'other') else actual == expected
    check('residence_empty', [condition('stage', '本次是选房', scene_value('stage', 'site_choice'), missing_kind='user_fact'),
                              condition('kind', '阳宅', scene_value('site_kind', 'yang'), missing_kind='user_fact'),
                              condition('role', '使用者本人起卦', scene_value('role', 'host'), missing_kind='user_fact'),
                              condition('residence', '尚未入住', scene_value('residence', 'not_occupied'), missing_kind='user_fact'),
                              condition('empty', '世爻旬空', shi['empty'], missing_kind='user_fact'),
                              condition('wang', '世爻综合旺衰已核定为旺', None,
                                        '普通月令旺相和实验高分不能代替此判据。', 'system_criteria')],
          '目前仅保留带前提的例外；不宣布旬空解除或自动抵扣分数。')
    check('outcome_dimensions', [condition('purpose', '已明确主问及主体尺度', bool(selected) if selection else None,
                                           missing_kind='analysis_pending')], 'AI 分别解释目标成败与主体得失，并保留各自条件。')
    check('timing_limits', [condition('criteria', '完整精确应期判据可用', None,
                                      '这是系统能力边界，不要求用户补充算法。', 'system_criteria')], '保留时间范围，不生成确定发力或应验日期。')
    return {'model_version': MODEL_VERSION, 'logic_version': logic_digest(), 'lines': lines, 'hidden_spirits': hidden,
            'primary_matches': deepcopy(matches), 'effects': effects, 'checks': checks, 'harm_routes': harm_routes,
            'selection_status': 'unique_match' if len(matches) == 1 else 'multiple_matches' if matches else 'not_located' if selected else 'pending',
            'limits': ['综合旺衰、有效暗动与作用先后尚无完整自动判据。', '结构命中不等于实际作用；具体成败与得失是带条件的 AI 判断。',
                       '完整化空影响与精确应期尚未实现；未知不当作零、假或默认满足。']}


def reasoning_facts(chart):
    analysis = chart.get('conditional_analysis')
    if not analysis:
        return []
    values = [('REASONING_MODEL', '条件判断版本', {'model_version': analysis['model_version'], 'logic_version': analysis['logic_version']}),
              ('PRIMARY_USE_LINE', '功能匹配候选，不按分数取用',
               {'matches': analysis['primary_matches'], 'status': analysis['selection_status'],
                'chosen': analysis['primary_matches'][0] if len(analysis['primary_matches']) == 1 else None}),
              ('REASONING_LIMITS', '条件判断能力边界', analysis['limits'])]
    values.extend((f"CONDITION_{check['rule_id']}", '规则适用前提，不是吉凶结论', check) for check in analysis['checks'])
    values.extend((f'CANDIDATE_EFFECT_{i}', '本问相关的候选结构作用，effective未知', effect) for i, effect in enumerate(analysis['effects']))
    values.extend((f'HARM_DIRECTION_{i}', '六害方向结构，未判现实动机或效果', route) for i, route in enumerate(analysis['harm_routes']))
    for line in analysis['lines']:
        values.append((f"LINE_STATE_{line['position']}", '日月、原爻旬空、动变及化空状态；综合旺衰未知', line))
    if analysis['hidden_spirits']:
        values.append(('HIDDEN_STATES', '伏神结构与日月状态，未核定有效作用', analysis['hidden_spirits']))
    return [{'fact_id': key, 'kind': 'calculation', 'subject': '本次条件判断', 'predicate': predicate,
             'value': json.dumps(value, ensure_ascii=False, separators=(',', ':')), 'source_rule_id': None}
            for key, predicate, value in values]
