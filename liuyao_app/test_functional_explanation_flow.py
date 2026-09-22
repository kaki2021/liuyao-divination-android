"""Anonymous regressions for functional explanations in the full report flow.

The replies below are deliberately constructed from each test request. They
exercise acceptance and history retention, not model quality or predictions.
Uploaded questions, identifiers and model replies are never bundled here.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from case_store import Actor, CaseStore
from liuyao_app.pipeline import run_analysis
from liuyao_app.test_pipeline import BoundProvider


class FunctionalExplanationProvider(BoundProvider):
    """Add a neutral functional explanation beside a separately grounded trend."""

    def __init__(self, *, include_kinship=True, unsupported_outcome=False):
        super().__init__("conditional")
        self.include_kinship = include_kinship
        self.unsupported_outcome = unsupported_outcome

    def __call__(self, *args, **kwargs):
        response = super().__call__(*args, **kwargs)
        call = self.calls[-1]
        inp = call["input"]
        out = response["parsed_json"]
        if call["stage"] == "selection":
            out["candidates"][0].update(
                object_role="本次所问的凭证", function="文书凭证功能",
                relation="generates_me", six_relative="parents",
                rule_refs=["interpretation.functional_role", "interpretation.leader_documents"],
            )
        if call["stage"] == "interpretation":
            rules = ["interpretation.functional_role", "interpretation.leader_documents"]
            if self.include_kinship:
                rules.append("relation.ordinary_kinship")
            claim = {
                "claim_id": "C_FUNCTION_EXPLANATION", "dimension": "support",
                "kind": "ai_hypothesis", "direction": "neutral",
                "statement": "按本次文书凭证功能，可取父母类作为候选；本卦同类位置为初爻。这里只说明功能归属。",
                "proposition": {"subject": "本次文书目标", "predicate": "功能候选", "value": "父母类"},
                "fact_refs": ["CTX_0", "FUNCTION_SELECTION", "MATCHING_LINES", "LINE_1_RELATIVE_CODE"],
                "rule_refs": rules, "inference_refs": [],
                "assumptions": ["按原问中的文书凭证功能理解目标。"],
                "limitations": ["功能归属本身不证明主目标成败。"], "requires_review": True,
            }
            if self.unsupported_outcome:
                claim.update(dimension="outcome", direction="favorable",
                             statement="由文书对应父母类，预测这次目标能够落实。")
                claim["proposition"] = {"subject": "本次文书目标", "predicate": "结果", "value": "能够落实"}
            out["claims"].insert(0, claim)
            out["advice"].append({
                "advice_id": "A_PREPARE_DOCUMENT", "text": "可整理现有凭证资料，核对所问目标。",
                "basis": "system_interpretation", "claim_refs": [claim["claim_id"]],
                "fact_refs": ["FUNCTION_SELECTION"], "conditions": ["原问确实关注文书凭证。"],
            })
        response["raw_text"] = json.dumps(out, ensure_ascii=False)
        return response


class FunctionalExplanationFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cases.sqlite3"
        self.actor = Actor("anonymous-test-owner", "anonymous-test-session")
        self.store = CaseStore(self.path)
        self.case = self.store.create_case(self.actor, {
            "question": "这份合同能否办好？",
            "casting": {"method": "meibu", "results": ["1", "5", "5"]},
        }, idempotency_key="anonymous-case")["case_id"]

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_model(self, **options):
        provider = FunctionalExplanationProvider(**options)
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "synthetic-model", 1,
                              provider_call=provider)
        return result, provider

    def test_functional_explanation_reaches_report_without_a_repair_call(self):
        for include_kinship in (True, False):
            with self.subTest(include_kinship=include_kinship):
                result, provider = self.run_model(include_kinship=include_kinship)
                self.assertEqual(result["status"], "completed", result.get("error"))
                self.assertEqual([call["stage"] for call in provider.calls],
                                 ["intent", "selection", "interpretation", "report"])
                self.assertTrue(all(call["repair_context"] is None for call in provider.calls))
                accepted = result["stage_outputs"]["interpretation"]
                claim = accepted["claims"][0]
                self.assertEqual(claim["claim_id"], "C_FUNCTION_EXPLANATION")
                self.assertEqual(claim["direction"], "neutral")
                self.assertEqual(claim["kind"], "ai_hypothesis")
                self.assertTrue(claim["requires_review"])
                self.assertEqual(provider.calls[-1]["input"]["accepted_interpretation"], accepted)
                support = next(part for part in result["report"]["sections"] if part["key"] == "support")
                self.assertIn("功能归属", support["content"])
                self.assertTrue(result["display_report"])
                self.assertEqual(result["report"]["conclusion"], accepted["conclusion"])

    def test_function_rule_alone_prediction_is_retained_with_audit_warning(self):
        result,provider=self.run_model(unsupported_outcome=True)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([c['stage'] for c in provider.calls],['intent','selection','interpretation','report'])
        self.assertTrue(result['audit_report']['warnings'])
        self.assertIn('report',result['stage_outputs'])

    def test_rerun_adds_history_and_attempt_count_belongs_to_its_stage(self):
        first, _ = self.run_model()
        before = copy.deepcopy(self.store.export_case(self.actor, self.case)["analysis_runs"][0])
        second, _ = self.run_model()
        self.assertEqual(first["status"], "completed", first.get("error"))
        self.assertEqual(second["status"], "completed", second.get("error"))
        self.assertNotEqual(first["analysis_run_id"], second["analysis_run_id"])
        runs = self.store.export_case(self.actor, self.case)["analysis_runs"]
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0], before)
        for run in runs:
            self.assertEqual(len(run["ai_events"]), 4)
            self.assertEqual([event["attempt"]["model_run_metadata"]["attempt_number"]
                              for event in run["ai_events"]], [1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
