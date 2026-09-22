"""Conclusion and subject-reference contracts; synthetic cases, no predictive claim."""
from copy import deepcopy
import json
import unittest

try:
    from .validate_ai_contract import ContractError, load_pack, validate_output, check_schema
except ImportError:
    from validate_ai_contract import ContractError, load_pack, validate_output, check_schema

PACK = load_pack()


def fixture(stage):
    return deepcopy(PACK['stages'][stage]['valid_example'])


def conditional_fixture():
    pair = fixture('interpretation')
    inp, out = pair['input'], pair['output']
    inp['rules'] = [{
        'rule_id': 'TEST_ORDINARY_GENERATION', 'source_id': 'SRC-BSZS', 'source_role': 'core',
        'source_locator': '凡五行生克（合成合同样例，不作为真实占例）',
        'statement': '凡五行中火生土。', 'status': 'approved', 'usage': 'interpretation',
        'applicability': '只说明普通五行的生助方向，不能单独证明完整成败。',
    }]
    inp['facts'] = [
        {'fact_id': 'FACT_SHI', 'kind': 'chart', 'subject': '世爻', 'predicate': 'element',
         'value': 'earth', 'source_rule_id': 'TEST_ORDINARY_GENERATION'},
        {'fact_id': 'FACT_MOVING', 'kind': 'chart', 'subject': '动爻', 'predicate': 'element',
         'value': 'fire', 'source_rule_id': 'TEST_ORDINARY_GENERATION'},
    ]
    out['status'] = 'needs_review'
    out['claims'] = [{
        'claim_id': 'CLAIM_SELF', 'dimension': 'subject_effect', 'kind': 'ai_hypothesis',
        'statement': '仅从已给出的生克方向看，火对土的生助提供主体受支持的条件解释。',
        'direction': 'favorable',
        'proposition': {'subject': '世爻主体', 'predicate': '条件性作用方向', 'value': '生助'},
        'fact_refs': ['FACT_SHI', 'FACT_MOVING'], 'rule_refs': ['TEST_ORDINARY_GENERATION'],
        'inference_refs': [], 'assumptions': ['将本问按凡五行下的一般个人处境理解。'],
        'limitations': ['未裁定日月强弱，因此不把生助方向等同于实际作用强度。'],
        'requires_review': True,
    }]
    out['conclusion'] = {
        'answer': '就个人受支持的方向看偏顺；实际作用仍受强弱条件限制，不能据此保证具体事项成功。',
        'direction': 'favorable', 'qualification': 'conditional', 'claim_refs': ['CLAIM_SELF'],
        'key_conditions': list(out['claims'][0]['assumptions']),
        'limits': list(out['claims'][0]['limitations']),
    }
    return pair


def subject_fixture():
    pair = fixture('selection')
    inp, out = pair['input'], pair['output']
    base = inp['rules'][0]
    for rule_id in ('interpretation.three_self_references', 'interpretation.analysis_scale'):
        rule = deepcopy(base)
        rule.update(rule_id=rule_id, statement='区分宫五行参照、世爻与世身；按问题尺度选择主体参照。')
        inp['rules'].append(rule)
    candidate = out['candidates'][0]
    candidate.update(subject_reference='shi', relation=None, six_relative=None,
                     rule_refs=['interpretation.three_self_references', 'interpretation.analysis_scale'])
    return pair


def report_fixture():
    pair = fixture('report')
    interpretation = conditional_fixture()['output']
    pair['input']['accepted_interpretation'] = interpretation
    pair['output']['conclusion'] = deepcopy(interpretation['conclusion'])
    pair['output']['parts'][1].update(
        text=interpretation['claims'][0]['statement'], claim_refs=['CLAIM_SELF'], qualification='conditional')
    return pair


class ConclusionContractTests(unittest.TestCase):
    def validate(self, stage, pair):
        return validate_output(stage, json.dumps(pair['output'], ensure_ascii=False), pair['input'], PACK)

    def reject(self, stage, pair):
        with self.assertRaises(ContractError):
            self.validate(stage, pair)

    def test_missing_conclusion_rejected(self):
        for stage in ('interpretation', 'report'):
            with self.subTest(stage=stage):
                pair = fixture(stage)
                del pair['output']['conclusion']
                self.reject(stage, pair)

    def test_report_input_must_also_have_conclusion(self):
        pair = fixture('report')
        del pair['input']['accepted_interpretation']['conclusion']
        self.reject('report', pair)

    def test_conditional_supported_by_subject_effect_despite_local_gaps(self):
        self.validate('interpretation', conditional_fixture())

    def test_conditional_outcome_allowed(self):
        pair = conditional_fixture()
        pair['output']['claims'][0]['dimension'] = 'outcome'
        self.validate('interpretation', pair)

    def test_support_only_cannot_be_promoted_to_overall_success(self):
        pair = conditional_fixture()
        pair['output']['claims'][0]['dimension'] = 'support'
        self.reject('interpretation', pair)

    def test_context_only_cannot_be_promoted_to_success(self):
        pair = conditional_fixture()
        fact = pair['input']['facts'][0]
        fact['kind'] = 'context'
        claim = pair['output']['claims'][0]
        claim.update(kind='real_world_context', direction='neutral', rule_refs=[], fact_refs=[fact['fact_id']],
                     proposition={key: fact[key] for key in ('subject', 'predicate', 'value')})
        self.reject('interpretation', pair)

    def test_selection_rule_cannot_support_outcome_alone(self):
        pair = conditional_fixture()
        pair['input']['rules'][0]['usage'] = 'selection'
        self.reject('interpretation', pair)

    def test_opposite_direction_rejected(self):
        pair = conditional_fixture()
        pair['output']['conclusion']['direction'] = 'unfavorable'
        self.reject('interpretation', pair)

    def test_neutral_primary_claim_cannot_support_favorable_answer(self):
        pair = conditional_fixture()
        pair['output']['claims'][0]['direction'] = 'neutral'
        self.reject('interpretation', pair)

    def test_unknown_primary_claim_cannot_support_favorable_answer(self):
        pair = conditional_fixture()
        pair['output']['claims'][0]['direction'] = 'unknown'
        self.reject('interpretation', pair)

    def test_opposing_primary_claims_require_mixed_direction(self):
        pair = conditional_fixture()
        second = deepcopy(pair['output']['claims'][0])
        second.update(claim_id='CLAIM_OBSTACLE', direction='unfavorable')
        pair['output']['claims'].append(second)
        pair['output']['conclusion']['claim_refs'].append(second['claim_id'])
        self.reject('interpretation', pair)
        pair['output']['conclusion']['direction'] = 'mixed'
        self.validate('interpretation', pair)

    def test_mixed_primary_claim_preserves_mixed_direction(self):
        pair = conditional_fixture()
        pair['output']['claims'][0]['direction'] = 'mixed'
        pair['output']['conclusion']['direction'] = 'mixed'
        self.validate('interpretation', pair)

    def test_empty_claim_refs_rejected_for_conditional(self):
        pair = conditional_fixture()
        pair['output']['conclusion']['claim_refs'] = []
        self.reject('interpretation', pair)

    def test_unknown_claim_ref_rejected(self):
        pair = conditional_fixture()
        pair['output']['conclusion']['claim_refs'] = ['NONEXISTENT']
        self.reject('interpretation', pair)

    def test_all_assumptions_must_reach_conclusion(self):
        pair = conditional_fixture()
        pair['output']['conclusion']['key_conditions'] = []
        self.reject('interpretation', pair)

    def test_all_claim_limits_must_reach_conclusion(self):
        pair = conditional_fixture()
        pair['output']['conclusion']['limits'] = ['一般说明，省略了实际假设。']
        self.reject('interpretation', pair)

    def test_conclusion_limits_may_not_be_empty(self):
        pair = conditional_fixture()
        pair['output']['conclusion']['limits'] = []
        self.reject('interpretation', pair)

    def test_undetermined_requires_undetermined_direction(self):
        pair = fixture('interpretation')
        pair['output']['conclusion']['direction'] = 'favorable'
        self.reject('interpretation', pair)

    def test_specific_undetermined_limit_is_valid(self):
        self.validate('interpretation', fixture('interpretation'))

    def test_engine_unfinished_alone_is_not_a_conclusion(self):
        pair = fixture('interpretation')
        pair['output']['conclusion'].update(answer='引擎未完成，无法解卦。', limits=['引擎未完成。'])
        self.reject('interpretation', pair)

    def test_generic_answer_does_not_hide_behind_specific_limit(self):
        pair = fixture('interpretation')
        pair['output']['conclusion']['answer'] = '当前依据不足，无法判断。'
        self.reject('interpretation', pair)

    def test_report_preserves_conditional_conclusion(self):
        self.validate('report', report_fixture())

    def test_report_cannot_rewrite_any_conclusion_field(self):
        for field, replacement in (
            ('answer', '事情必成。'), ('direction', 'unfavorable'), ('qualification', 'undetermined'),
            ('claim_refs', []), ('key_conditions', []), ('limits', ['改写成其他限制。']),
        ):
            with self.subTest(field=field):
                pair = report_fixture()
                pair['output']['conclusion'][field] = replacement
                self.reject('report', pair)

    def test_self_subject_does_not_require_siblings(self):
        self.validate('selection', subject_fixture())

    def test_body_subject_is_a_distinct_valid_reference(self):
        pair = subject_fixture()
        pair['output']['candidates'][0]['subject_reference'] = 'shi_body'
        self.validate('selection', pair)

    def test_self_subject_cannot_be_labeled_siblings(self):
        pair = subject_fixture()
        pair['output']['candidates'][0].update(relation='same_as_me', six_relative='siblings')
        self.reject('selection', pair)

    def test_self_subject_requires_both_scale_and_reference_rules(self):
        for removed in ('interpretation.three_self_references', 'interpretation.analysis_scale'):
            with self.subTest(removed=removed):
                pair = subject_fixture()
                pair['output']['candidates'][0]['rule_refs'].remove(removed)
                self.reject('selection', pair)

    def test_null_relation_without_subject_reference_rejected(self):
        pair = subject_fixture()
        del pair['output']['candidates'][0]['subject_reference']
        self.reject('selection', pair)

    def test_regular_function_can_explicitly_leave_subject_reference_null(self):
        pair = fixture('selection')
        pair['output']['candidates'][0]['subject_reference'] = None
        self.validate('selection', pair)

    def test_interpretation_nested_selection_schema_accepts_subject_reference(self):
        pair = fixture('interpretation')
        pair['input']['selection'] = subject_fixture()['output']
        check_schema(pair['input'], PACK['stages']['interpretation']['input_schema'])

    def test_clarification_is_limited_to_one_necessary_question(self):
        pair = fixture('intent')
        pair['output'].update(status='needs_clarification', selected_candidate_id=None)
        question = {'question_id': 'Q1', 'text': '两个所指对象中，你问哪一个？',
                    'why_needed': '指代有两个互斥对象。', 'affects': 'intent'}
        pair['output']['clarifying_questions'] = [question]
        self.validate('intent', pair)
        pair['output']['clarifying_questions'].append(dict(question, question_id='Q2'))
        self.reject('intent', pair)


if __name__ == '__main__':
    unittest.main()
