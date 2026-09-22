"""Casting conversion, input integrity and retention checks; no AI prediction.

The exhaustive meibu test checks all 8 x 8 x 8 ordered draws against independent
trigram bit patterns, including the special all-static/all-moving third draws.
"""
import copy
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from base_chart import calculate_base_chart
from case_store import Actor, CaseStore
from casting_input import CastingInputError, derive_casting_lines, normalize_casting_input
from validate_input import derive_six_lines, validate_input


class CastingInputTests(unittest.TestCase):
    question = "这次出售余粮能否成交？"

    def payload(self, method, results, **extra):
        return {"question": self.question, "casting": {"method": method, "results": results}, **extra}

    def test_all_512_meibu_draws(self):
        # These are the source's three-line pictures, written bottom to top.
        expected_patterns = {"circle": "111", "square": "000", "1": "100", "2": "110", "3": "010", "4": "001", "5": "101", "6": "011"}
        checked = 0
        for lower, upper, third in itertools.product(expected_patterns, repeat=3):
            with self.subTest(draws=(lower, upper, third)):
                data = self.payload("meibu", [lower, upper, third])
                normalized = normalize_casting_input(data)
                derived = derive_six_lines(normalized)
                expected_bits = [int(bit) for bit in expected_patterns[lower] + expected_patterns[upper]]
                moves = [1, 2, 3, 4, 5, 6] if third == "circle" else [] if third == "square" else [int(third)]
                self.assertEqual(derived["base_bits"], expected_bits)
                self.assertEqual(derived["moving_line_numbers"], moves)
                self.assertEqual(derived["changed_bits"], [1 - b if p in moves else b for p, b in enumerate(expected_bits, start=1)])
                self.assertEqual(normalized["casting"], data["casting"])
                self.assertTrue(validate_input(data)["valid"])
                checked += 1
        self.assertEqual(checked, 512)

    def test_primary_source_meibu_example(self):
        # Core B0430–B0432: 5, 2, 4 -> 革 with fourth line moving -> 既济.
        normalized = normalize_casting_input(self.payload("meibu", ["5", "2", "4"]))
        self.assertEqual(normalized["lines"], ["young_yang", "young_yin", "young_yang", "old_yang", "young_yang", "young_yin"])
        chart = calculate_base_chart(normalized["lines"])
        self.assertEqual(chart["main"]["lower_trigram"], "离")
        self.assertEqual(chart["main"]["upper_trigram"], "兑")
        self.assertEqual(chart["moving_positions"], [4])
        self.assertEqual(chart["changed_structure"]["lower_trigram"], "离")
        self.assertEqual(chart["changed_structure"]["upper_trigram"], "坎")

    def test_circle_and_square_third_draws(self):
        moving = normalize_casting_input(self.payload("meibu", ["square", "circle", "circle"]))
        static = normalize_casting_input(self.payload("meibu", ["square", "circle", "square"]))
        self.assertEqual(moving["lines"], ["old_yin"] * 3 + ["old_yang"] * 3)
        self.assertEqual(static["lines"], ["young_yin"] * 3 + ["young_yang"] * 3)

    def test_every_taiji_permutation_at_every_line(self):
        expected = {"222": "old_yin", "223": "young_yang", "232": "young_yang", "322": "young_yang", "233": "young_yin", "323": "young_yin", "332": "young_yin", "333": "old_yang"}
        for token, state in expected.items():
            for position in range(6):
                with self.subTest(token=token, position=position + 1):
                    results = ["223"] * 6
                    results[position] = token
                    normalized = normalize_casting_input(self.payload("taiji", results))
                    expected_lines = ["young_yang"] * 6
                    expected_lines[position] = state
                    self.assertEqual(normalized["lines"], expected_lines)
                    self.assertEqual(normalized["casting"]["results"], results)

    def test_taiji_six_throws_keep_bottom_to_top_order(self):
        results = ["222", "223", "233", "333", "322", "332"]
        normalized = normalize_casting_input(self.payload("taiji", results))
        self.assertEqual(normalized["lines"], ["old_yin", "young_yang", "young_yin", "old_yang", "young_yang", "young_yin"])
        self.assertEqual(derive_six_lines(normalized)["moving_line_numbers"], [1, 4])
        self.assertNotEqual(normalized["lines"], normalize_casting_input(self.payload("taiji", list(reversed(results))))["lines"])

    def test_equivalent_meibu_taiji_and_direct_inputs(self):
        meibu = normalize_casting_input(self.payload("meibu", ["5", "2", "4"]))
        taiji = normalize_casting_input(self.payload("taiji", ["223", "233", "223", "333", "223", "233"]))
        direct = {"question": self.question, "lines": meibu["lines"]}
        self.assertEqual(meibu["lines"], taiji["lines"])
        self.assertEqual(derive_six_lines(meibu), derive_six_lines(taiji))
        self.assertEqual(derive_six_lines(meibu), derive_six_lines(direct))
        self.assertEqual(normalize_casting_input(direct), direct)
        self.assertNotIn("casting", normalize_casting_input(direct))

    def test_matching_both_forms_are_accepted_but_mismatch_is_rejected(self):
        data = normalize_casting_input(self.payload("meibu", ["5", "2", "4"]))
        self.assertTrue(validate_input(data)["valid"])
        self.assertEqual(normalize_casting_input(data), data)
        data["lines"][3] = "young_yang"
        self.assertFalse(validate_input(data)["valid"])
        self.assertIn("CASTING_LINES_MISMATCH", [e["code"] for e in validate_input(data)["errors"]])
        with self.assertRaises(CastingInputError):
            normalize_casting_input(data)

    def test_normalization_is_idempotent_and_does_not_mutate_input(self):
        raw = self.payload("taiji", ["332", "232", "222", "333", "323", "322"], actual_cast_time="2026-09-17T18:30:00+08:00")
        before = copy.deepcopy(raw)
        normalized = normalize_casting_input(raw)
        self.assertEqual(raw, before)
        self.assertEqual(normalize_casting_input(normalized), normalized)
        self.assertIsNot(normalized["casting"], raw["casting"])
        self.assertIsNot(normalized["casting"]["results"], raw["casting"]["results"])
        self.assertEqual(normalized["actual_cast_time"], raw["actual_cast_time"])

    def test_invalid_shapes_and_tokens_cannot_fall_back_to_lines(self):
        invalid = [None, [], {"method": "direct", "results": []}, {"method": [], "results": []},
            {"method": "meibu", "results": ["1", "2"]}, {"method": "meibu", "results": ["1", "2", "3", "4"]},
            {"method": "meibu", "results": [1, "2", "3"]}, {"method": "meibu", "results": ["1", "2", "0"]},
            {"method": "meibu", "results": ["圆", "方", "3"]}, {"method": "meibu", "results": ["Circle", "2", "3"]},
            {"method": "taiji", "results": ["223"] * 5}, {"method": "taiji", "results": ["223"] * 7},
            {"method": "taiji", "results": [223] * 6}, {"method": "taiji", "results": ["7"] * 6},
            {"method": "taiji", "results": ["224"] * 6}, {"method": "taiji", "results": ["22 3"] * 6},
            {"method": "taiji", "results": ["２２３"] * 6}, {"method": "taiji", "results": [[2, 2, 3]] * 6},
            {"method": "taiji", "results": ["223"] * 6, "spatial_order": [1, 2, 3]},
            {"method": "meibu", "results": ["1", "2", "3"], "liujing": []}]
        for casting in invalid:
            with self.subTest(casting=casting):
                data = {"question": self.question, "casting": casting, "lines": ["young_yang"] * 6}
                self.assertFalse(validate_input(data)["valid"])
                with self.assertRaises(CastingInputError):
                    normalize_casting_input(data)

    def test_full_form_validation_is_not_bypassed(self):
        invalid = [self.payload("meibu", ["1", "2", "3"], actual_cast_time="2026-02-30T10:00:00Z"),
                   {"casting": {"method": "meibu", "results": ["1", "2", "3"]}},
                   {"question": " ", "casting": {"method": "taiji", "results": ["223"] * 6}},
                   self.payload("meibu", ["1", "2", "3"], owner_id="injected-owner"),
                   {"question": self.question}]
        for data in invalid:
            with self.subTest(data=data):
                self.assertFalse(validate_input(data)["valid"])
                with self.assertRaises(CastingInputError):
                    normalize_casting_input(data)

    def test_casting_original_and_derived_values_survive_store_revisions(self):
        actor = Actor("casting-user", "test-session")
        first = normalize_casting_input(self.payload("taiji", ["332", "232", "222", "333", "323", "322"]))
        second = normalize_casting_input(self.payload("meibu", ["5", "2", "4"]))
        with tempfile.TemporaryDirectory() as directory:
            store = CaseStore(Path(directory) / "cases.db")
            try:
                case_id = store.create_case(actor, first, idempotency_key="create")["case_id"]
                store.revise_case(actor, case_id, second, reason="更正实际起卦记录", expected_revision_seq=1, idempotency_key="revise")
                exported = store.export_case(actor, case_id)
                self.assertEqual(exported["original_input"], first)
                self.assertEqual(exported["revisions"][0]["input"], first)
                self.assertEqual(exported["revisions"][1]["input"], second)
                self.assertEqual(exported["original_input"]["casting"]["results"][0], "332")
            finally:
                store.close()

    def test_schema_accepts_new_and_legacy_shapes(self):
        # The schema's role is shape validation; computed agreement is checked
        # by the service normalizer (the preceding mismatch regression).
        schema = json.loads(Path(__file__).with_name("liuyao_input_schema.json").read_text())
        self.assertEqual(schema["required"], ["question"])
        self.assertEqual(schema["anyOf"], [{"required": ["lines"]}, {"required": ["casting"]}])
        variants = schema["properties"]["casting"]["oneOf"]
        self.assertEqual([v["properties"]["method"]["const"] for v in variants], ["meibu", "taiji"])
        self.assertTrue(all(v["additionalProperties"] is False for v in variants))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CastingInputTests)
    cases = list(suite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failed = set()
    for case, _ in result.failures + result.errors:
        failed.add(getattr(case, "test_case", case).id())
    titles = {
        "test_all_512_meibu_draws": "枚卜全部512种有序组合的卦象与动变",
        "test_casting_original_and_derived_values_survive_store_revisions": "原始起卦和派生六爻跨原记录与修订保留",
        "test_circle_and_square_third_draws": "第三次圆全动、方全静",
        "test_equivalent_meibu_taiji_and_direct_inputs": "枚卜、太极、直接六爻等价输入一致",
        "test_every_taiji_permutation_at_every_line": "八种太极排列在六个爻位的48种定位",
        "test_full_form_validation_is_not_bypassed": "新入口不能绕过问题时间和字段校验",
        "test_invalid_shapes_and_tokens_cannot_fall_back_to_lines": "无效起卦不能依靠附带六爻静默回退",
        "test_matching_both_forms_are_accepted_but_mismatch_is_rejected": "原始起卦与附带六爻必须一致",
        "test_normalization_is_idempotent_and_does_not_mutate_input": "归一化幂等且不修改原始排列和实际时间",
        "test_primary_source_meibu_example": "核心5、2、4例下离上兑四爻动",
        "test_schema_accepts_new_and_legacy_shapes": "新旧输入契约所需字段及封闭结构",
        "test_taiji_six_throws_keep_bottom_to_top_order": "太极六次先后顺序对应初爻至上爻",
    }
    tests = [{"test_id": "CAST-" + str(index).zfill(3),
              "title": titles[case._testMethodName],
              "status": "failed" if case.id() in failed else "passed",
              "evidence": "test_casting_input.py:" + case._testMethodName}
             for index, case in enumerate(cases, start=1)]
    report = {"scope": "Casting conversion, strict input agreement and raw-data retention; no AI or prediction accuracy validation.",
              "rule_ids": ["casting.meibu_conversion", "casting.taiji_conversion"],
              "coverage": {"meibu_ordered_draw_combinations": 512, "taiji_permutation_position_combinations": 48},
              "tests_run": len(tests), "passed": len(tests) - len(failed), "failed": len(failed), "tests": tests}
    Path(__file__).with_name("casting_input_test_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
