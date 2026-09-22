"""Anonymous contract regressions; no uploaded user cases are embedded here."""
import copy
import unittest

from liuyao_app.validation_feedback import MAX_ERRORS, collect_application_errors, collect_output_errors
from validate_ai_contract import ContractError, canonical, load_pack, prompt_digest, validate_output


class ValidationFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack()

    def fixture(self, stage="interpretation"):
        fixture = copy.deepcopy(self.pack["stages"][stage]["valid_example"])
        fixture["input"]["meta"]["prompt_digest"] = prompt_digest(self.pack, stage)
        return fixture["input"], fixture["output"]

    def collect(self, inp, out, stage="interpretation"):
        return collect_output_errors(stage, out, inp, self.pack)

    def claim(self, identifier="CLAIM_TEST", kind="engine_supported"):
        return {
            "claim_id": identifier, "dimension": "support", "kind": kind,
            "statement": "匿名接口测试：存在一项待核对的支持条件。",
            "direction": "neutral",
            "proposition": {"subject": "匿名对象", "predicate": "测试条件", "value": "待核对"},
            "fact_refs": ["FACT_FUNCTION"], "rule_refs": ["TEST_FUNCTION_GRAIN_TRADE"],
            "inference_refs": [], "assumptions": [], "limitations": [], "requires_review": False,
        }

    def advice(self, identifier="ADVICE_TEST"):
        return {
            "advice_id": identifier, "text": "核对实际条件。", "basis": "system_interpretation",
            "claim_refs": ["CLAIM_TEST"], "fact_refs": [], "conditions": [],
        }

    def assert_issue(self, issues, code, path):
        self.assertTrue(any(issue["code"] == code and issue["path"] == path for issue in issues),
                        (code, path, issues))

    def test_valid_fixtures_have_no_errors(self):
        for stage in self.pack["stages"]:
            with self.subTest(stage=stage):
                inp, out = self.fixture(stage)
                self.assertEqual(self.collect(inp, out, stage), [])

    def test_collects_real_failure_patterns_in_one_pass_without_mutation(self):
        inp, out = self.fixture()
        # Seven model-generated claims falsely purport to have engine proof.
        out["claims"] = [self.claim("CLAIM_" + str(index)) for index in range(7)]
        context = self.claim("CLAIM_CONTEXT", "real_world_context")
        context.update(rule_refs=[], direction="neutral")
        context["proposition"] = {"subject": "程序", "predicate": "能力限制", "value": "缺少算法"}
        out["claims"].append(context)
        out["claims"].append(copy.deepcopy(context))
        out["advice"] = [self.advice("ADVICE_" + str(index)) for index in range(4)]
        for advice in out["advice"]:
            advice.update(claim_refs=["CLAIM_0"], requires_review=True)
        out["uncertainties"] = []
        before = copy.deepcopy((inp, out, self.pack))
        issues = self.collect(inp, out)
        for index in range(4):
            self.assert_issue(issues, "SCHEMA_EXTRA_FIELD", f"$.advice[{index}].requires_review")
        for index in range(7):
            self.assert_issue(issues, "ENGINE_INFERENCE_REQUIRED", f"$.claims[{index}].inference_refs")
        self.assert_issue(issues, "CONTEXT_FACT_KIND", "$.claims[7].fact_refs")
        self.assert_issue(issues, "CONTEXT_ATOM_MISMATCH", "$.claims[7].proposition")
        self.assert_issue(issues, "DUPLICATE_IDENTIFIER", "$.claims[8].claim_id")
        self.assert_issue(issues, "UNRESOLVED_GAP_OMITTED", "$.uncertainties")
        self.assertEqual((inp, out, self.pack), before)
        self.assertLessEqual(len(issues), MAX_ERRORS)
        with self.assertRaises(ContractError):
            validate_output("interpretation", canonical(out), inp, self.pack)

    def test_unknown_refs_review_limits_and_each_advice_checked(self):
        inp, out = self.fixture()
        c = self.claim(kind="ai_hypothesis")
        c.update(fact_refs=["NO_FACT"], rule_refs=["NO_RULE"], inference_refs=["NO_INFERENCE"])
        out["claims"] = [c]
        out["advice"] = [self.advice(), self.advice("ADVICE_SECOND")]
        out["advice"][0]["claim_refs"] = ["NO_CLAIM"]
        out["advice"][1].update(basis="real_world_information", fact_refs=["FACT_FUNCTION"])
        issues = self.collect(inp, out)
        for path in ("$.claims[0].fact_refs", "$.claims[0].rule_refs", "$.claims[0].inference_refs",
                     "$.advice[0].claim_refs"):
            self.assert_issue(issues, "UNKNOWN_REFERENCE", path)
        self.assert_issue(issues, "HYPOTHESIS_REVIEW_REQUIRED", "$.claims[0].requires_review")
        self.assert_issue(issues, "HYPOTHESIS_LIMIT_REQUIRED", "$.claims[0].limitations")
        self.assert_issue(issues, "HYPOTHESIS_ENGINE_REFS", "$.claims[0].inference_refs")
        self.assert_issue(issues, "ADVICE_CONTEXT_REQUIRED", "$.advice[1].fact_refs")
        self.assert_issue(issues, "ADVICE_CONTEXT_CLAIM_KIND", "$.advice[1].claim_refs")

    def test_unverified_inference_and_wrong_structured_conclusion_both_reported(self):
        inp, out = self.fixture()
        inp["unresolved_gaps"] = []
        out["uncertainties"] = []
        c = self.claim()
        c["inference_refs"] = ["INFERENCE_TEST"]
        out["claims"] = [c]
        inp["inferences"] = [{
            "inference_id": "INFERENCE_TEST", "analysis_run_id": inp["meta"]["analysis_run_id"],
            "premise_fact_ids": ["FACT_FUNCTION"], "rule_id": "TEST_FUNCTION_GRAIN_TRADE",
            "status": "unverified", "direction": "unfavorable", "conclusion": c["proposition"],
        }]
        issues = self.collect(inp, out)
        self.assert_issue(issues, "ENGINE_INFERENCE_UNVERIFIED", "$.claims[0].inference_refs")
        self.assert_issue(issues, "ENGINE_CONCLUSION_MISMATCH", "$.claims[0].proposition")

    def test_context_claim_can_match_only_observed_atom(self):
        inp, out = self.fixture()
        fact = {"fact_id": "FACT_CONTEXT", "kind": "context", "subject": "匿名对象",
                "predicate": "已确认条件", "value": "存在", "source_rule_id": None}
        inp["facts"].append(fact)
        c = self.claim(kind="real_world_context")
        c.update(rule_refs=[], fact_refs=[fact["fact_id"]],
                 proposition={key: fact[key] for key in ("subject", "predicate", "value")})
        out["claims"] = [c]
        self.assertEqual(self.collect(inp, out), [])
        c["proposition"]["value"] = "不存在"
        issues = self.collect(inp, out)
        self.assert_issue(issues, "CONTEXT_ATOM_MISMATCH", "$.claims[0].proposition")

    def test_schema_checks_siblings_after_wrong_type_missing_and_extra_fields(self):
        inp, out = self.fixture()
        out["claims"] = [self.claim(), self.claim("CLAIM_SECOND")]
        out["claims"][0]["fact_refs"] = "FACT_FUNCTION"
        del out["claims"][0]["statement"]
        out["claims"][1]["direction"] = "not_an_enum"
        out["extra"] = "unexpected"
        issues = self.collect(inp, out)
        self.assert_issue(issues, "SCHEMA_EXTRA_FIELD", "$.extra")
        self.assert_issue(issues, "SCHEMA_REQUIRED", "$.claims[0].statement")
        self.assert_issue(issues, "SCHEMA_TYPE", "$.claims[0].fact_refs")
        self.assert_issue(issues, "SCHEMA_CONSTRAINT", "$.claims[1].direction")
        self.assert_issue(issues, "ENGINE_INFERENCE_REQUIRED", "$.claims[1].inference_refs")

    def test_report_checks_multiple_parts_and_fixed_fields(self):
        inp, out = self.fixture("report")
        out["question_restated"] = "意外改写"
        out["conclusion"] = {"answer": "意外改写"}
        for part in out["parts"][:2]:
            part["claim_refs"] = ["MISSING_CLAIM"]
        issues = self.collect(inp, out, "report")
        self.assert_issue(issues, "QUESTION_CHANGED", "$.question_restated")
        self.assert_issue(issues, "ACCEPTED_FIELD_CHANGED", "$.conclusion")
        self.assert_issue(issues, "UNKNOWN_REFERENCE", "$.parts[0].claim_refs")
        self.assert_issue(issues, "UNKNOWN_REFERENCE", "$.parts[1].claim_refs")

    def test_output_error_collection_is_bounded_and_non_object_safe(self):
        inp, out = self.fixture()
        for index in range(100):
            out["unexpected_" + str(index)] = True
        issues = self.collect(inp, out)
        self.assertEqual(len(issues), MAX_ERRORS)
        self.assertEqual(len({(e["code"], e["path"], e["message"]) for e in issues}), MAX_ERRORS)
        self.assert_issue(self.collect(inp, None), "SCHEMA_TYPE", "$")
        self.assertEqual(collect_output_errors("unknown", {}, {}, self.pack)[0]["code"], "UNKNOWN_STAGE")

    def test_application_collects_every_hypothesis_without_interpretation_rule(self):
        inp, out = self.fixture()
        inp["rules"].append(dict(inp["rules"][0], rule_id="TEST_DISPLAY", usage="display"))
        out["claims"] = [self.claim("CLAIM_A", "ai_hypothesis"), self.claim("CLAIM_B", "ai_hypothesis")]
        out["claims"][1]["rule_refs"] = ["TEST_DISPLAY"]
        before = copy.deepcopy((inp, out))
        issues = collect_application_errors("interpretation", out, inp)
        self.assertEqual(len(issues), 2)
        for index in range(2):
            self.assert_issue(issues, "HYPOTHESIS_INTERPRETATION_RULE_REQUIRED", f"$.claims[{index}].rule_refs")
        self.assertEqual((inp, out), before)
        inp["rules"][0]["usage"] = "interpretation"
        issues = collect_application_errors("interpretation", out, inp)
        self.assertEqual(len(issues), 1)
        self.assert_issue(issues, "HYPOTHESIS_INTERPRETATION_RULE_REQUIRED", "$.claims[1].rule_refs")

    def test_missing_inference_guidance_does_not_suggest_renaming_kind(self):
        inp, out = self.fixture()
        out["claims"] = [self.claim()]
        issue = next(item for item in self.collect(inp, out) if item["code"] == "ENGINE_INFERENCE_REQUIRED")
        self.assertIn("remove redundant factual claims", issue["message"])
        self.assertIn("Do not merely rename its kind", issue["message"])
        self.assertIn("genuinely support", issue["message"])
        self.assertEqual(collect_application_errors("interpretation", out, inp), [])
        out["claims"][0]["inference_refs"] = ["INFERENCE_TEST"]
        issues = collect_application_errors("interpretation", out, inp)
        self.assert_issue(issues, "APPLICATION_ENGINE_CLAIM_UNAVAILABLE", "$.claims[0].kind")


if __name__ == "__main__":
    unittest.main()
