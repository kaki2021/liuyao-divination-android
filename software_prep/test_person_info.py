"""Optional casting-person context: validation, immutable revisions and no rule switch."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from base_chart import calculate_base_chart
from case_store import Actor, CaseStore, Conflict
from casting_input import normalize_casting_input
from validate_input import validate_input

ROOT = Path(__file__).parent
BASE = {
    'question': '这次出行是否顺利？',
    'lines': ['young_yang', 'young_yin', 'old_yang', 'old_yin', 'young_yang', 'young_yin'],
    'actual_cast_time': '2020-08-01T09:30:15+08:00',
}
HASHES = {'source_hash': 'a' * 64, 'rules_digest': 'b' * 64,
          'prompt_digest': 'c' * 64, 'engine_build': 'person-info-test'}


class PersonInfoValidationTests(unittest.TestCase):
    def check_valid(self, profile):
        result = validate_input({**BASE, 'person_info': profile})
        self.assertTrue(result['valid'], result['errors'])

    def test_old_inputs_remain_valid_and_unchanged(self):
        self.assertTrue(validate_input(BASE)['valid'])
        self.assertEqual(normalize_casting_input(BASE), BASE)

    def test_empty_or_partially_known_profile_is_optional(self):
        for profile in ({}, {'subject': 'unspecified'}, {'background': '第一次参加这个项目'},
                        {'relationship': '同事'}, {'subject_age': 10}, {'querent_age': 30}):
            with self.subTest(profile=profile):
                self.check_valid(profile)
                self.assertEqual(normalize_casting_input({**BASE, 'person_info': profile})['person_info'], profile)

    def test_self_uses_only_querent_age(self):
        self.check_valid({'subject': 'self', 'querent_age': 12})
        for subject_age in (12, 99):
            result = validate_input({**BASE, 'person_info': {
                'subject': 'self', 'querent_age': 12, 'subject_age': subject_age}})
            self.assertFalse(result['valid'])
            self.assertIn('SELF_AGE_CONFLICT', [e['code'] for e in result['errors']])

    def test_other_person_keeps_both_ages_distinct(self):
        profile = {'subject': 'other', 'querent_age': 36, 'subject_age': 8,
                   'relationship': '女儿', 'background': '她要第一次独自参加活动'}
        self.check_valid(profile)
        normalized = normalize_casting_input({**BASE, 'person_info': profile})
        self.assertEqual(normalized['person_info'], profile)
        normalized['person_info']['querent_age'] = 40
        self.assertEqual(profile['querent_age'], 36)

    def test_age_boundaries_include_zero_and_150(self):
        for age in (0, 11, 12, 13, 150):
            with self.subTest(age=age):
                self.check_valid({'subject': 'other', 'querent_age': age, 'subject_age': age})

    def test_age_rejects_booleans_floats_strings_and_out_of_range(self):
        for field in ('querent_age', 'subject_age'):
            for value in (True, False, 1.0, 1.5, '12', None, -1, 151, {}, []):
                with self.subTest(field=field, value=value):
                    errors = validate_input({**BASE, 'person_info': {field: value}})['errors']
                    self.assertIn('INVALID_PERSON_AGE', [e['code'] for e in errors])

    def test_non_object_and_unknown_fields_rejected(self):
        for value in (None, '', [], 1, True):
            with self.subTest(value=value):
                self.assertFalse(validate_input({**BASE, 'person_info': value})['valid'])
        result = validate_input({**BASE, 'person_info': {'full_name': '不收集', 'dob': '2000-01-01'}})
        self.assertEqual({e['path'] for e in result['errors']},
                         {'$/person_info/full_name', '$/person_info/dob'})

    def test_subject_is_explicit_enum_without_truthy_coercion(self):
        for value in ('child', True, None, [], {}, 0):
            with self.subTest(value=value):
                self.assertFalse(validate_input({**BASE, 'person_info': {'subject': value}})['valid'])

    def test_text_fields_are_bounded_and_nonblank_if_supplied(self):
        for field, maximum in (('relationship', 200), ('background', 2000)):
            self.check_valid({field: '字' * maximum})
            for value in ('', ' \n ', '字' * (maximum + 1), None, 12, {}):
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.assertFalse(validate_input({**BASE, 'person_info': {field: value}})['valid'])

    def test_casting_methods_preserve_profile_without_spatial_data(self):
        for casting in ({'method': 'meibu', 'results': ['1', '5', '3']},
                        {'method': 'taiji', 'results': ['222', '223', '233', '333', '232', '323']}):
            value = {k: v for k, v in BASE.items() if k != 'lines'}
            value.update(casting=casting, person_info={'subject': 'self', 'querent_age': 25})
            self.assertTrue(validate_input(value)['valid'])
            normalized = normalize_casting_input(value)
            self.assertEqual(normalized['person_info'], value['person_info'])
            self.assertEqual(len(normalized['lines']), 6)

    def test_profile_does_not_change_deterministic_chart_or_wuxing(self):
        baseline = calculate_base_chart(normalize_casting_input(BASE)['lines'])
        for age in (0, 11, 12, 13, 150):
            value = {**BASE, 'person_info': {'subject': 'other', 'subject_age': age,
                                           'querent_age': 45, 'background': '测试背景'}}
            with self.subTest(age=age):
                self.assertEqual(calculate_base_chart(normalize_casting_input(value)['lines']), baseline)

    def test_input_and_export_schemas_share_profile_contract(self):
        input_schema = json.loads((ROOT / 'liuyao_input_schema.json').read_text())
        record_schema = json.loads((ROOT / 'case_record_schema.json').read_text())
        self.assertNotIn('person_info', input_schema['required'])
        profile_schema = input_schema['properties']['person_info']
        self.assertEqual(profile_schema, record_schema['$defs']['UserInput']['properties']['person_info'])
        self.assertFalse(profile_schema['additionalProperties'])
        self.assertEqual(profile_schema.get('required', []), [])


class PersonInfoHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'cases.sqlite')
        self.actor = Actor('profile-owner', 'profile-session')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def start(self, case_id, key, **extra):
        return self.store.start_analysis(self.actor, case_id, **HASHES, idempotency_key=key, **extra)

    def test_age_stays_at_cast_even_when_recorded_years_later(self):
        value = {**BASE, 'person_info': {'subject': 'self', 'querent_age': 8}}
        case_id = self.store.create_case(self.actor, value, idempotency_key='create')['case_id']
        self.start(case_id, 'first')
        record = self.store.export_case(self.actor, case_id)
        self.assertEqual(record['original_input']['person_info']['querent_age'], 8)
        self.assertEqual(record['analysis_runs'][0]['input_snapshot']['input']['person_info']['querent_age'], 8)
        self.assertEqual(record['revisions'][0]['time_context']['actual_cast_time'], BASE['actual_cast_time'])

    def test_corrected_profile_only_affects_new_analysis_snapshot(self):
        profile = {'subject': 'other', 'querent_age': 36, 'subject_age': 8, 'relationship': '女儿'}
        value = {**BASE, 'person_info': profile}
        case_id = self.store.create_case(self.actor, value, idempotency_key='create')['case_id']
        first = self.start(case_id, 'first')
        initial_run = copy.deepcopy(self.store.export_case(self.actor, case_id)['analysis_runs'][0])
        corrected = copy.deepcopy(value)
        corrected['person_info'].update(subject_age=9, background='将首次独自参加活动')
        self.store.revise_case(self.actor, case_id, corrected, reason='补充所问对象的年龄和活动背景',
                               expected_revision_seq=1, idempotency_key='correct')
        second = self.start(case_id, 'second', parent_run_id=first['analysis_run_id'])
        record = self.store.export_case(self.actor, case_id)
        by_id = {r['analysis_run_id']: r for r in record['analysis_runs']}
        self.assertEqual(by_id[first['analysis_run_id']], initial_run)
        self.assertEqual(record['original_input']['person_info'], profile)
        self.assertEqual(record['revisions'][0]['input']['person_info'], profile)
        self.assertEqual(by_id[second['analysis_run_id']]['input_snapshot']['input']['person_info'], corrected['person_info'])
        self.assertNotEqual(first['input_snapshot_id'], second['input_snapshot_id'])

    def test_legacy_case_can_add_and_remove_optional_context_without_rewriting_history(self):
        case_id = self.store.create_case(self.actor, BASE, idempotency_key='create')['case_id']
        self.start(case_id, 'without-profile')
        with_profile = {**BASE, 'person_info': {'subject': 'self', 'background': '这次以项目经理身份出行'}}
        self.store.revise_case(self.actor, case_id, with_profile, reason='补充任务角色',
                               expected_revision_seq=1, idempotency_key='add')
        self.start(case_id, 'with-profile')
        self.store.revise_case(self.actor, case_id, BASE, reason='新解读不使用补充背景',
                               expected_revision_seq=2, idempotency_key='remove')
        self.start(case_id, 'removed-profile')
        record = self.store.export_case(self.actor, case_id)
        self.assertNotIn('person_info', record['original_input'])
        runs_by_revision = {r['revision_seq']: r['input_snapshot']['input'] for r in record['analysis_runs']}
        self.assertNotIn('person_info', runs_by_revision[1])
        self.assertEqual(runs_by_revision[2]['person_info'], with_profile['person_info'])
        self.assertNotIn('person_info', runs_by_revision[3])

    def test_profile_changes_are_included_in_idempotency_conflict_detection(self):
        original = {**BASE, 'person_info': {'subject': 'self', 'querent_age': 30}}
        first = self.store.create_case(self.actor, original, idempotency_key='same')
        self.assertEqual(self.store.create_case(self.actor, original, idempotency_key='same'), first)
        changed = {**BASE, 'person_info': {'subject': 'self', 'querent_age': 31}}
        with self.assertRaises(Conflict):
            self.store.create_case(self.actor, changed, idempotency_key='same')


if __name__ == '__main__':
    unittest.main()
