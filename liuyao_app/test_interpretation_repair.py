"""Anonymous end-to-end regressions for actual interpretation failure shapes.

All replies are synthetic and input-bound. These verify repair, provenance and
limited semantic checks, never a live model or divination accuracy.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from liuyao_app.test_pipeline import BoundProvider
from case_store import Actor, CaseStore
from liuyao_app.pipeline import run_analysis


CAST_TIME = "2026-08-12T09:20:00+08:00"
LINES = ["young_yin", "young_yin", "young_yin", "young_yin", "young_yang", "young_yin"]


class SyntheticReplyProvider(BoundProvider):
    def __init__(self, transform):
        super().__init__("conditional")
        self.transform, self.raw_replies = transform, []

    def __call__(self, provider, model, prompt, inp, **kwargs):
        response = super().__call__(provider, model, prompt, inp, **kwargs)
        stage = self.calls[-1]["stage"]
        attempt = sum(call["stage"] == stage for call in self.calls)
        parsed = json.loads(response["raw_text"])
        self.transform(stage, attempt, parsed, inp)
        # Keep deliberate whitespace so raw preservation is stronger than JSON
        # equivalence and the retry cannot quietly swap in normalized output.
        response["raw_text"] = json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
        response["parsed_json"] = deepcopy(parsed)
        self.raw_replies.append({"stage": stage, "attempt": attempt, "raw_text": response["raw_text"]})
        return response


class InterpretationRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cases.sqlite3"
        self.store = CaseStore(self.path)
        self.actor = Actor("synthetic-owner", "synthetic-session")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_case(self, transform, *, dated=True):
        value = {"question": "我准备出售一批旧书，想问能否成交。", "lines": list(LINES)}
        if dated:
            value["actual_cast_time"] = CAST_TIME
        case_id = self.store.create_case(self.actor, value, idempotency_key="create-case")["case_id"]
        provider = SyntheticReplyProvider(transform)
        result = run_analysis(self.path, self.actor, case_id, "deepseek", "synthetic-model", 1,
                              provider_call=provider)
        exported = self.store.export_case(self.actor, case_id)
        return result, provider, exported["analysis_runs"][-1]

    def test_all_seven_engine_errors_and_false_context_return_in_single_repair(self):
        def transform(stage, attempt, out, inp):
            if stage != "interpretation" or attempt != 1:
                return
            template = deepcopy(out["claims"][0])
            out["claims"] = []
            for index in range(7):
                claim = deepcopy(template)
                claim.update(claim_id=f"ENGINE_{index}", kind="engine_supported",
                             assumptions=[], requires_review=False)
                out["claims"].append(claim)
            out["claims"].append({
                "claim_id": "ALGORITHM_AS_CONTEXT", "dimension": "obstacle", "kind": "real_world_context",
                "statement": "尚未提供完整应期算法。", "direction": "neutral",
                "proposition": {"subject": "本次分析", "predicate": "算法范围", "value": "应期算法未齐备"},
                "fact_refs": ["CHART_NAME"], "rule_refs": [], "inference_refs": [],
                "assumptions": [], "limitations": [], "requires_review": False,
            })
            out["conclusion"]["claim_refs"] = ["ENGINE_0"]
            out["advice"] = [{
                "advice_id": "PREPARE", "text": "按实际交易安排准备物品清单。",
                "basis": "system_interpretation", "claim_refs": ["ENGINE_0"], "fact_refs": [],
                "conditions": ["仅作为可调整事项供核对。"], "requires_review": True,
            }]

        result, provider, run = self.run_case(transform)
        self.assertEqual(result["status"], "completed", result.get("error"))
        self.assertEqual([call["stage"] for call in provider.calls],
                         ["intent", "selection", "interpretation", "interpretation", "report"])
        calls = [call for call in provider.calls if call["stage"] == "interpretation"]
        events = [event["attempt"] for event in run["ai_events"] if event["stage"] == "interpretation"]
        raw = next(reply["raw_text"] for reply in provider.raw_replies
                   if reply["stage"] == "interpretation" and reply["attempt"] == 1)
        self.assertEqual(events[0]["raw_output"], raw)
        self.assertEqual(calls[1]["repair_context"]["previous_output"], raw)
        self.assertEqual(json.loads(raw)["claims"][0]["kind"], "engine_supported")
        self.assertTrue(json.loads(raw)["advice"][0]["requires_review"])
        feedback = calls[1]["repair_context"]["validation_error"]
        for index in range(7):
            self.assertIn(f"$.claims[{index}].inference_refs [ENGINE_INFERENCE_REQUIRED]", feedback)
        self.assertIn("$.claims[7].fact_refs [CONTEXT_FACT_KIND]", feedback)
        self.assertIn("$.claims[7].proposition [CONTEXT_ATOM_MISMATCH]", feedback)
        self.assertEqual(calls[0]["input"], calls[1]["input"])
        self.assertEqual(calls[0]["prompt"], calls[1]["prompt"])
        self.assertEqual({(call["provider"], call["model"]) for call in provider.calls},
                         {("deepseek", "synthetic-model")})
        self.assertEqual(events[0]["model_run_metadata"]["stage_input_digest"],
                         events[1]["model_run_metadata"]["stage_input_digest"])
        self.assertTrue(events[0]["validation_errors"])
        self.assertFalse(events[1]["validation_errors"])
        conclusion = result["stage_outputs"]["interpretation"]["conclusion"]
        self.assertEqual(conclusion["qualification"], "conditional")
        self.assertEqual(result["report"]["conclusion"], conclusion)
        self.assertEqual(result["display_report"]["summary"], conclusion["answer"])
        self.assertTrue(all(claim["kind"] == "ai_hypothesis"
                            for claim in result["stage_outputs"]["interpretation"]["claims"]))

    def test_saved_time_clears_only_date_part_of_early_compound_note(self):
        original = "起卦日期、年龄、完整旺衰算法未提供，限制应期和力度细化。"

        def transform(stage, attempt, out, inp):
            if stage == "selection":
                out["unresolved"] = [original]

        result, provider, run = self.run_case(transform)
        self.assertEqual(result["status"], "completed", result.get("error"))
        selection_input = next(call["input"] for call in provider.calls if call["stage"] == "selection")
        scope = selection_input["information_scope"]
        self.assertTrue(scope["actual_cast_time_provided"])
        self.assertTrue(scope["month_context_available"])
        self.assertTrue(scope["day_context_available"])
        self.assertFalse(scope["chart_values_in_this_stage"])
        review = result["selection_note_reviews"][0]
        self.assertEqual(review["original_text"], original)
        self.assertEqual(review["status"], "partially_clarified")
        self.assertIn(original, review["review_text"])
        self.assertIn("已计算月、日历法信息", review["review_text"])
        interpretation_input = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        gap_table = {gap["gap_id"]: gap for gap in interpretation_input["unresolved_gaps"]}
        self.assertNotIn("GAP_CALENDAR", gap_table)
        self.assertNotIn("GAP_SELECTION_UNRESOLVED_0",gap_table)
        self.assertEqual(result["audit_report"]["selection_note_reviews"][0]["original_text"],original)
        selection_event = next(event["attempt"] for event in run["ai_events"] if event["stage"] == "selection")
        self.assertEqual(json.loads(selection_event["raw_output"])["unresolved"], [original])
        self.assertEqual(result["stage_outputs"]["selection"]["unresolved"], [original])
        self.assertEqual(result["report"]["conclusion"]["qualification"], "conditional")
        self.assertEqual(len(provider.calls), 4)

    def test_no_actual_time_is_missing_in_scope_and_still_allows_coarse_interpretation(self):
        result, provider, run = self.run_case(lambda *args: None, dated=False)
        self.assertEqual(result["status"], "completed", result.get("error"))
        scope = next(call["input"]["information_scope"] for call in provider.calls if call["stage"] == "selection")
        self.assertEqual(scope["calendar_status"], "missing")
        self.assertFalse(scope["actual_cast_time_provided"])
        self.assertFalse(scope["month_context_available"])
        self.assertFalse(scope["day_context_available"])
        interpretation_input = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        self.assertIn("GAP_CALENDAR", {gap["gap_id"] for gap in interpretation_input["unresolved_gaps"]})
        self.assertFalse(any(fact["fact_id"].startswith("CALENDAR_") for fact in interpretation_input["facts"]))
        self.assertEqual(result["display_report"]["conclusion"]["qualification"], "conditional")

    def test_maximum_length_note_and_added_review_fit_downstream_contracts(self):
        prefix = "起卦日期、年龄、综合旺衰算法未提供。"
        original = prefix + "尚需核对背景。" * ((1500 - len(prefix)) // 7)
        original = (original + "待核实" * 500)[:1500]
        self.assertEqual(len(original), 1500)

        def transform(stage, attempt, out, inp):
            if stage == "selection":
                out["unresolved"] = [original]

        result, provider, run = self.run_case(transform)
        self.assertEqual(result["status"], "completed", result.get("error"))
        review = result["selection_note_reviews"][0]
        self.assertEqual(review["original_text"], original)
        self.assertGreater(len(review["review_text"]), 1500)
        self.assertLessEqual(len(review["review_text"]), 2400)
        output_gap = next(gap for gap in result["stage_outputs"]["interpretation"]["uncertainties"]
                          if gap["gap_id"] == "GAP_SELECTION_UNRESOLVED_0")
        self.assertNotIn("起卦日期",output_gap["impact"])
        self.assertNotIn("取用阶段早期",output_gap["impact"])
        self.assertEqual(len(provider.calls), 4)

    def test_reversed_direction_is_audited_without_rewriting_the_prediction(self):
        def transform(stage, attempt, out, inp):
            if stage != "interpretation":
                return
            fact = next(fact for fact in inp["facts"] if fact["fact_id"] == "CAL_DAY_TO_LINE_6")
            self.assertEqual(fact["value"], "is_controlled_by")
            claim = out["claims"][0]
            claim["fact_refs"].append("CAL_DAY_TO_LINE_6")
            claim["statement"] = "日支午火克子水。"

        result, provider, run = self.run_case(transform)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([c['stage'] for c in provider.calls],['intent','selection','interpretation','report'])
        self.assertTrue(any(w['code']=='RELATION_DIRECTION_MISMATCH' for w in result['audit_report']['warnings']))
        events=[e['attempt'] for e in run['ai_events'] if e['stage']=='interpretation']
        self.assertEqual(len(events),1)
        self.assertIn('日支午火克子水。',events[0]['raw_output'])
        self.assertTrue(events[0]['adopted_output'])
        self.assertFalse(events[0]['validation_errors'])
        self.assertTrue(events[0]['model_run_metadata']['audit_warnings'])


if __name__ == "__main__":
    unittest.main()
