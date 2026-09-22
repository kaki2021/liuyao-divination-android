"""Compatibility tests preserve strict evidence validation after normalisation."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
from validate_ai_contract import ContractError, canonical, load_pack, prompt_digest, validate_output
from liuyao_app.response_compat import normalize_stage_output, parse_model_json


class ModelJSONTests(unittest.TestCase):
    def test_accepts_one_object_with_only_fence_bom_and_whitespace(self):
        for raw in ('{"answer":"好"}', ' \ufeff {"answer":"好"}\n',
                    '```json\n{"answer":"好"}\n```',
                    '\ufeff\n```\r\n{"answer":"好"}\r\n```\n'):
            with self.subTest(raw=raw):
                self.assertEqual(parse_model_json(raw), {"answer": "好"})

    def test_strict_failures_are_not_extracted_or_coerced(self):
        failures = (
            '{"a":1,"a":2}', '{"a":{"b":1,"b":2}}',
            '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
            '{"a":[1e999]}', '{} {}', '说明\n{}', '{}\n说明',
            '```json\n{}\n```\n第二段', '```json\n{}\n```\n```json\n{}\n```',
            '```json\n```json\n{}\n```\n```', '```python\n{}\n```',
            '[]', 'null', '"{}"', '{"a":1,}', '\ufeff\ufeff{}',
        )
        for raw in failures:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_model_json(raw)

    def test_type_size_and_depth_limits(self):
        for raw in (None, {}, ' ' * 500001, '{"a":' + '[' * 2000 + '0' + ']' * 2000 + '}'):
            with self.subTest(type=type(raw)), self.assertRaises(ValueError):
                parse_model_json(raw)


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack()

    def fixture(self, stage):
        fixture = copy.deepcopy(self.pack["stages"][stage]["valid_example"])
        fixture["input"]["meta"]["prompt_digest"] = prompt_digest(self.pack, stage)
        return fixture["input"], fixture["output"]

    def validate(self, stage, output, inp):
        return validate_output(stage, canonical(output), inp, self.pack)

    def normalized(self, stage, output, inp):
        return normalize_stage_output(stage, json.dumps(output, ensure_ascii=False), inp)

    def hypothesis(self):
        inp, out = self.fixture("interpretation")
        inp["rules"][0]["usage"] = "interpretation"
        fact = inp["facts"][0]
        out["claims"] = [{
            "claim_id": "CLAIM_TEST", "dimension": "subject_effect", "kind": "ai_hypothesis",
            "statement": "在明确假设下，主体倾向获得支持（纯接口测试）。",
            "direction": "favorable", "proposition": {"subject": "主体", "predicate": "测试方向", "value": "支持"},
            "fact_refs": [fact["fact_id"]], "rule_refs": [inp["rules"][0]["rule_id"]],
            "inference_refs": [], "assumptions": ["须先确认盘面结构作用在本案实际体现。"],
            "limitations": ["结构倾向不能保证目标实现。"], "requires_review": True,
        }]
        out["status"] = "needs_review"
        out["conclusion"] = {
            "answer": "假设结构作用能够实际体现，主体倾向获得支持；不保证成交。",
            "direction": "favorable", "qualification": "conditional", "claim_refs": ["CLAIM_TEST"],
            "key_conditions": [], "limits": [],
        }
        return inp, out

    def test_valid_examples_unchanged(self):
        for stage in self.pack["stages"]:
            with self.subTest(stage=stage):
                inp, out = self.fixture(stage)
                result, changes = self.normalized(stage, out, inp)
                self.assertEqual(result, out)
                self.assertEqual(changes, [])
                self.validate(stage, result, inp)

    def test_redundant_advice_flag_and_reference_duplicates_are_audited(self):
        inp, out = self.hypothesis()
        out["claims"][0]["fact_refs"] *= 2
        out["advice"] = [{"advice_id": "A_TEST", "text": "先核对当前背景。", "basis": "system_interpretation",
                         "claim_refs": ["CLAIM_TEST", "CLAIM_TEST"], "fact_refs": [],
                         "conditions": [], "requires_review": True}]
        before = copy.deepcopy(out)
        result, changes = self.normalized("interpretation", out, inp)
        self.assertEqual(out, before)
        self.assertNotIn("requires_review", result["advice"][0])
        self.assertEqual(result["advice"][0]["claim_refs"], ["CLAIM_TEST"])
        self.assertEqual(len(result["claims"][0]["fact_refs"]), 1)
        self.assertTrue(any("redundant metadata" in x for x in changes))
        self.assertTrue(any("repeated identical" in x for x in changes))
        self.validate("interpretation", result, inp)

    def test_extra_advice_fields_or_malformed_flags_remain_errors(self):
        for key, value in (("requires_review", "yes"), ("unsupported", True)):
            inp, out = self.hypothesis()
            out["advice"] = [{"advice_id": "A_TEST", "text": "先核对背景。", "basis": "system_interpretation",
                             "claim_refs": ["CLAIM_TEST"], "fact_refs": [], "conditions": [], key: value}]
            result, _ = self.normalized("interpretation", out, inp)
            self.assertEqual(result["advice"][0][key], value)
            with self.assertRaises(ContractError):
                self.validate("interpretation", result, inp)

    def test_unsupported_engine_claim_is_never_reclassified(self):
        inp, out = self.hypothesis()
        out["claims"][0]["kind"] = "engine_supported"
        inp["inferences"] = []
        result, _ = self.normalized("interpretation", out, inp)
        self.assertEqual(result["claims"][0]["kind"], "engine_supported")
        self.assertEqual(result["claims"][0]["statement"], out["claims"][0]["statement"])
        with self.assertRaises(ContractError):
            self.validate("interpretation", result, inp)

    def test_missing_binding_and_optional_empty_arrays(self):
        fields = {
            "intent": ("independent_questions", "clarifying_questions"),
            "selection": ("route_requests", "unresolved", "clarifying_questions"),
            "interpretation": ("advice", "clarifying_questions"),
        }
        for stage, arrays in fields.items():
            with self.subTest(stage=stage):
                inp, out = self.fixture(stage)
                expected = copy.deepcopy(out)
                del out["binding"]
                for field in arrays:
                    del out[field]
                if stage == "selection":
                    del out["candidates"][0]["assumptions"]
                result, changes = self.normalized(stage, out, inp)
                self.assertEqual(result, expected)
                self.assertTrue(changes)
                self.validate(stage, result, inp)

    def test_fence_is_compatible_but_raw_audit_remains_untouched(self):
        inp, out = self.fixture("intent")
        raw = '\ufeff```json\n' + json.dumps(out) + '\n```'
        snapshot = raw[:]
        result, changes = normalize_stage_output("intent", raw, inp)
        self.validate("intent", result, inp)
        self.assertEqual(raw, snapshot)
        self.assertTrue(any("fence" in change for change in changes))

    def test_only_sole_declared_primary_can_fill_an_omitted_reference(self):
        inp, out = self.fixture("selection")
        original_id = out["candidates"][0]["candidate_id"]
        out["selected_primary_id"] = None
        result, changes = self.normalized("selection", out, inp)
        self.assertEqual(result["selected_primary_id"], original_id)
        self.assertIsNone(out["selected_primary_id"])
        self.assertTrue(changes)
        self.validate("selection", result, inp)

    def test_ambiguous_missing_wrong_or_deliberately_unselected_primary_is_not_guessed(self):
        for mode in ("two_primaries", "no_primary", "wrong_id", "needs_clarification"):
            with self.subTest(mode=mode):
                inp, out = self.fixture("selection")
                out["selected_primary_id"] = None
                if mode == "two_primaries":
                    second = copy.deepcopy(out["candidates"][0]); second["candidate_id"] = "SECOND"
                    out["candidates"].append(second)
                elif mode == "no_primary":
                    out["candidates"][0]["purpose"] = "supporting"
                elif mode == "wrong_id":
                    out["selected_primary_id"] = "UNKNOWN"
                else:
                    out["status"] = "needs_clarification"
                result, _ = self.normalized("selection", out, inp)
                self.assertEqual(result["selected_primary_id"], out["selected_primary_id"])

    def test_explicit_wrong_binding_is_never_overwritten(self):
        for wrong in ({"analysis_run_id": "OTHER", "input_snapshot_id": "SNAPSHOT_DEMO"},
                      {"analysis_run_id": None}, None, []):
            with self.subTest(binding=wrong):
                inp, out = self.fixture("intent")
                out["binding"] = copy.deepcopy(wrong)
                result, changes = self.normalized("intent", out, inp)
                if isinstance(wrong, dict):
                    for key, value in wrong.items():
                        self.assertEqual(result["binding"][key], value)
                else:
                    self.assertEqual(result["binding"], wrong)
                with self.assertRaises(ContractError):
                    self.validate("intent", result, inp)

    def test_partial_binding_receives_only_missing_identifier(self):
        inp, out = self.fixture("intent")
        del out["binding"]["input_snapshot_id"]
        result, changes = self.normalized("intent", out, inp)
        self.validate("intent", result, inp)
        self.assertEqual(result["binding"]["input_snapshot_id"], inp["meta"]["input_snapshot_id"])

    def test_conditions_are_exact_union_without_changing_judgment(self):
        inp, out = self.hypothesis()
        out["claims"][0]["requires_review"] = False
        out["status"] = "supported"
        out["conclusion"]["key_conditions"] = ["作用能实际发生时。"]
        out["conclusion"]["limits"] = ["不能保证成交。"]
        before = copy.deepcopy(out)
        result, changes = self.normalized("interpretation", out, inp)
        self.validate("interpretation", result, inp)
        self.assertTrue(result["claims"][0]["requires_review"])
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["claims"][0]["kind"], "ai_hypothesis")
        self.assertEqual(result["conclusion"]["key_conditions"], ["作用能实际发生时。", "须先确认盘面结构作用在本案实际体现。"])
        self.assertEqual(result["conclusion"]["limits"], ["不能保证成交。", "结构倾向不能保证目标实现。"])
        for field in ("answer", "direction", "qualification", "claim_refs"):
            self.assertEqual(result["conclusion"][field], before["conclusion"][field])
        self.assertTrue(changes)
        again, more_changes = normalize_stage_output("interpretation", result, inp)
        self.assertEqual(again, result)
        self.assertEqual(more_changes, [])

    def test_unknown_fact_rule_or_claim_ref_still_rejected(self):
        for target in ("fact_refs", "rule_refs", "claim_refs"):
            with self.subTest(target=target):
                inp, out = self.hypothesis()
                container = out["conclusion"] if target == "claim_refs" else out["claims"][0]
                container[target] = ["NONEXISTENT"]
                result, _ = self.normalized("interpretation", out, inp)
                self.assertEqual((result["conclusion"] if target == "claim_refs" else result["claims"][0])[target], ["NONEXISTENT"])
                with self.assertRaises(ContractError):
                    self.validate("interpretation", result, inp)

    def test_missing_required_evidence_and_judgments_still_rejected(self):
        for field in ("claims", "conclusion", "uncertainties"):
            with self.subTest(field=field):
                inp, out = self.hypothesis()
                del out[field]
                result, _ = self.normalized("interpretation", out, inp)
                self.assertNotIn(field, result)
                with self.assertRaises(ContractError):
                    self.validate("interpretation", result, inp)
        for field in ("fact_refs", "rule_refs", "limitations", "assumptions"):
            with self.subTest(claim_field=field):
                inp, out = self.hypothesis()
                del out["claims"][0][field]
                result, _ = self.normalized("interpretation", out, inp)
                self.assertNotIn(field, result["claims"][0])
                with self.assertRaises(ContractError):
                    self.validate("interpretation", result, inp)
        for field in ("status", "candidates", "selected_candidate_id"):
            with self.subTest(intent_field=field):
                inp, out = self.fixture("intent")
                del out[field]
                result, _ = self.normalized("intent", out, inp)
                self.assertNotIn(field, result)
                with self.assertRaises(ContractError):
                    self.validate("intent", result, inp)

    def test_engine_claim_not_downgraded_to_hide_missing_inference(self):
        inp, out = self.hypothesis()
        out["claims"][0].update(kind="engine_supported", requires_review=False, assumptions=[])
        result, _ = self.normalized("interpretation", out, inp)
        self.assertEqual(result["claims"][0]["kind"], "engine_supported")
        self.assertEqual(result["claims"][0]["inference_refs"], [])
        with self.assertRaises(ContractError):
            self.validate("interpretation", result, inp)

    def test_normalizer_never_changes_contradictory_direction(self):
        inp, out = self.hypothesis()
        out["conclusion"]["direction"] = "unfavorable"
        result, _ = self.normalized("interpretation", out, inp)
        self.assertEqual(result["conclusion"]["direction"], "unfavorable")
        with self.assertRaises(ContractError):
            self.validate("interpretation", result, inp)

    def test_report_fixed_fields_copied_from_accepted_plan(self):
        inp, out = self.fixture("report")
        out.update(question_restated="改写的问题", conclusion={"answer": "改写结论"}, uncertainties=[], clarifying_questions=[])
        expected_prose = copy.deepcopy({key: out[key] for key in ("parts", "summary", "feedback_invitation")})
        inp["accepted_interpretation"]["clarifying_questions"] = [{
            "question_id": "Q_FOLLOWUP", "text": "买方是否已经确认交易条件？",
            "why_needed": "核对当前实际进展。", "affects": "intent"}]
        result, changes = self.normalized("report", out, inp)
        self.validate("report", result, inp)
        self.assertEqual(result["question_restated"], inp["question"])
        for field in ("conclusion", "uncertainties", "clarifying_questions"):
            self.assertEqual(result[field], inp["accepted_interpretation"][field])
        for field, text in expected_prose.items():
            self.assertEqual(result[field], text)
        self.assertTrue(changes)

    def test_report_missing_prose_not_fabricated(self):
        for field in ("parts", "summary"):
            inp, out = self.fixture("report")
            del out[field]
            result, _ = self.normalized("report", out, inp)
            self.assertNotIn(field, result)
            with self.assertRaises(ContractError):
                self.validate("report", result, inp)

    def test_explicit_wrong_optional_types_not_coerced(self):
        inp, out = self.fixture("intent")
        out["clarifying_questions"] = None
        result, _ = self.normalized("intent", out, inp)
        self.assertIsNone(result["clarifying_questions"])
        with self.assertRaises(ContractError):
            self.validate("intent", result, inp)

    def test_raw_dict_and_server_inputs_immutable_including_nested_arrays(self):
        for stage in ("interpretation", "report"):
            inp, out = self.hypothesis() if stage == "interpretation" else self.fixture(stage)
            if stage == "report":
                del out["conclusion"]
            before_inp, before_out = copy.deepcopy(inp), copy.deepcopy(out)
            result, _ = normalize_stage_output(stage, out, inp)
            self.assertEqual(inp, before_inp)
            self.assertEqual(out, before_out)
            result["conclusion"]["limits"].append("mutate only returned object")
            self.assertEqual(inp, before_inp)
            self.assertEqual(out, before_out)


if __name__ == "__main__":
    unittest.main()
