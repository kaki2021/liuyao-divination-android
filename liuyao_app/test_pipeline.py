"""Integration checks with a deliberately synthetic, input-bound provider.

These test retention and application contracts, never prediction accuracy or a
real model response. No example TEST_* rule enters the production projection.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from case_store import Actor, CaseStore, Conflict
from liuyao_app.pipeline import DIMENSIONS, result_from_outcome, run_analysis


class BoundProvider:
    """Build each reply from THIS request; no frozen binding or catalog fixture."""
    def __init__(self, mode="valid"):
        self.mode, self.calls = mode, []

    def __call__(self, provider, model, prompt, inp, timeout=60, repair_context=None):
        stage = ("report" if "accepted_interpretation" in inp else
                 "interpretation" if "facts" in inp else
                 "selection" if "intent" in inp else "intent")
        self.calls.append({"stage": stage, "input": copy.deepcopy(inp), "prompt": prompt,
                           "provider": provider, "model": model, "repair_context": copy.deepcopy(repair_context)})
        binding = {k: inp["meta"][k] for k in ("analysis_run_id", "input_snapshot_id")}
        question = inp.get("question", inp.get("intent", {}).get("primary_question", ""))
        quote = inp.get("user_evidence", [{"text": ""}])[0]["text"][:30]
        questions = [{"question_id": "Q_USE", "text": "你想问成交，还是购买后自用？", "why_needed": "用途会影响功能取用。", "affects": "object_function"}]
        if stage == "intent":
            out = {"binding": binding, "status": "ready", "candidates": [{
                "candidate_id": "INTENT_CURRENT", "primary_question": question,
                "actor": "我", "object": "原问中提出的事项", "action": None,
                "desired_outcome": "了解原问中的事项", "time_scope": None,
                "facets": [], "evidence_quotes": [{"evidence_id": "USER_QUESTION", "quote": quote}]}],
                "selected_candidate_id": "INTENT_CURRENT", "clarifying_questions": [], "independent_questions": []}
            if self.mode == "clarify":
                out.update(status="needs_clarification", selected_candidate_id=None, clarifying_questions=questions)
        elif stage == "selection":
            usable = next(r["rule_id"] for r in inp["rules"] if r["rule_id"] == "interpretation.functional_role")
            out = {"binding": binding, "status": "ready", "candidates": [{
                "candidate_id": "FUNCTION_CURRENT", "object_role": "本次交易的商品", "function": "取得交易收益",
                "relation": "controlled_by_me", "six_relative": "wealth", "purpose": "primary",
                "rule_refs": [usable], "evidence_quotes": [{"evidence_id": "USER_QUESTION", "quote": quote}], "assumptions": []}],
                "selected_primary_id": "FUNCTION_CURRENT", "clarifying_questions": [], "route_requests": [], "unresolved": []}
            if self.mode == "self_condition":
                out["candidates"][0].update(
                    object_role="明日个人整体处境", function="了解日常事务中自己的处境",
                    relation=None, six_relative=None, subject_reference="shi",
                    rule_refs=["interpretation.three_self_references", "interpretation.analysis_scale"],
                    assumptions=["按一般事务中的主体处境作粗略解释，不假定特定出行、交易或健康事件。"])
            if self.mode == "unknown_rule":
                out["candidates"][0]["rule_refs"] = ["fabricated.rule"]
            if self.mode == "selection_clarify":
                out.update(status="needs_clarification", selected_primary_id=None, clarifying_questions=questions)
            if self.mode == "rule_gap":
                out.update(status="needs_rule_review", selected_primary_id=None, candidates=[], unresolved=["本次功能定义尚未明确。"])
        elif stage == "interpretation":
            out = {"binding": binding, "status": "partial", "claims": [], "advice": [],
                   "uncertainties": [{"gap_id": g["gap_id"], "impact": g["description"], "next_step": "research_rule"} for g in inp["unresolved_gaps"]],
                   "clarifying_questions": [],
                   "conclusion": {
                       "answer": "当前可说明目标取用与本变卦结构；成交能否落实还取决于财爻与主体之间的作用是否有效，本次未作有效性判定。",
                       "direction": "undetermined", "qualification": "undetermined", "claim_refs": [],
                       "key_conditions": [], "limits": ["本次未判断财爻与主体之间的作用是否有效。"]}}
            if self.mode in ("conditional", "self_condition", "changed_report_conclusion"):
                self._conditional_interpretation(out, inp)
            if self.mode == "bad_fact":
                out["claims"] = [{"claim_id": "C_BAD", "dimension": "outcome", "kind": "real_world_context", "statement": "复述背景。",
                    "direction": "neutral", "proposition": {"subject": "用户原问", "predicate": "已说明", "value": question},
                    "fact_refs": ["NONEXISTENT"], "rule_refs": [], "inference_refs": [], "assumptions": [], "limitations": [], "requires_review": False}]
        else:
            plan = inp["accepted_interpretation"]
            out = {"binding": binding, "question_restated": question, "summary": "当前综合算法未完整实现，不能确定成败。",
                "parts": [{"dimension": d, "text": "当前依据不足。", "claim_refs": [], "advice_refs": [], "qualification": "undetermined"} for d in DIMENSIONS],
                "conclusion": copy.deepcopy(plan["conclusion"]),
                "uncertainties": plan["uncertainties"], "clarifying_questions": plan["clarifying_questions"], "feedback_invitation": "可在事情有进展后记录实际发生的结果及更正。"}
            for part in out["parts"]:
                claims = [c for c in plan["claims"] if c["dimension"] == part["dimension"]]
                if claims:
                    part.update(text="\n".join(c["statement"] for c in claims),
                                claim_refs=[c["claim_id"] for c in claims], qualification="conditional")
            if self.mode == "changed_report_conclusion":
                out["conclusion"]["answer"] = "模型在报告阶段另行改写的结论。"
            if self.mode == "bad_report_prose":
                out["summary"] = "无依据的新预测绝对成功"
                out["parts"][0]["text"] = "无依据的新预测绝对成功"
        if self.mode == "bad_binding":
            out["binding"]["analysis_run_id"] = "unrelated"
        raw = json.dumps(out, ensure_ascii=False)
        if self.mode == "malformed" or self.mode == "repair" and len(self.calls) == 1:
            raw = "this is not JSON"
        return {"raw_text": raw, "parsed_json": out, "provider": provider, "model": model,
                "request_id": "synthetic_" + str(len(self.calls)), "usage": {"total_tokens": 1}, "finish_reason": "stop"}

    def _conditional_interpretation(self, out, inp):
        """Synthetic contract fixture, not a generic divination implementation.

        Its direction is bound to a provided, directed subject relation, with an
        explicit efficacy assumption. The tests exercise evidence retention and
        output qualification, not the truth of any predicted real-world outcome.
        """
        facts = {fact["fact_id"]: fact for fact in inp["facts"]}
        relation = facts["REL_YING_TO_SHI"]
        # Fixtures deliberately choose either a generating or controlling pair;
        # do not invent a net benefit from an unrelated structural category.
        if relation["value"] not in ("generates", "controls"):
            raise AssertionError("conditional fixture needs a generating/controlling subject pair")
        direction = "favorable" if relation["value"] == "generates" else "unfavorable"
        tendency = "偏向得到支持" if direction == "favorable" else "需留意自身受损"
        assumptions = ["按一般事务的世应尺度分析，且应对世的结构作用在本案条件下能够体现。"]
        limits = ["单独世应生克只用于主体得失方向，不证明主目标最终成败，也不确定精确应期。"]
        statement = f"就当前提供的盘面，若世应作用在本案能够体现，主体{tendency}。"
        refs = ["REL_YING_TO_SHI", "SHI_POSITION", "YING_POSITION"]
        backgrounds = [fact for fact in inp["facts"] if fact["kind"] == "context" and fact["subject"] == "用户背景"]
        if backgrounds:
            fact = backgrounds[-1]
            refs.append(fact["fact_id"])
            assumptions.append("把本次补充作为当前背景核对：" + fact["value"])
        out.update(status="needs_review", claims=[{
            "claim_id": "C_SUBJECT_EFFECT", "dimension": "subject_effect", "kind": "ai_hypothesis",
            "statement": statement, "direction": direction,
            "proposition": {"subject": "本次主问中的主体", "predicate": "条件性得失方向", "value": tendency},
            "fact_refs": refs, "rule_refs": ["relation.ordinary_wuxing", "interpretation.gains_before_success"],
            "inference_refs": [], "assumptions": assumptions, "limitations": limits, "requires_review": True}])
        scope = "就明日个人整体处境作粗略解释" if self.mode == "self_condition" else "就本次所问中的主体处境"
        out["conclusion"] = {"answer": f"{scope}，{tendency}；这仍取决于世应作用是否实际体现，具体目标结果尚不能据此保证。",
            "direction": direction, "qualification": "conditional", "claim_refs": ["C_SUBJECT_EFFECT"],
            "key_conditions": list(assumptions), "limits": list(limits)}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cases.sqlite3"
        self.actor = Actor("local-owner", "test-session")
        self.store = CaseStore(self.path)
        self.input = {"question": "我准备卖掉余粮，想问能否成交。", "lines": ["young_yang", "old_yin", "young_yang", "young_yin", "young_yang", "young_yin"]}
        self.case = self.store.create_case(self.actor, self.input, idempotency_key="new")["case_id"]

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_model(self, mode="valid", **kwargs):
        provider = BoundProvider(mode)
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake-model", 1, provider_call=provider, **kwargs)
        return result, provider

    def latest(self):
        return self.store.export_case(self.actor, self.case)["analysis_runs"][-1]

    def test_four_stages_use_current_binding_and_real_rules(self):
        result, provider = self.run_model()
        self.assertEqual(result["status"], "completed")
        self.assertEqual([c["stage"] for c in provider.calls], ["intent", "selection", "interpretation", "report"])
        self.assertFalse(result["is_demo"])
        for call in provider.calls:
            self.assertEqual(call["input"]["meta"]["analysis_run_id"], result["analysis_run_id"])
            self.assertFalse(any(r["rule_id"].startswith("TEST_") for r in call["input"].get("rules", [])))
        self.assertEqual(set(provider.calls[0]["input"]), {"meta", "question", "user_evidence", "prior_clarifications"})
        self.assertEqual(provider.calls[2]["input"]["inferences"], [])
        self.assertTrue(provider.calls[2]["input"]["unresolved_gaps"])
        self.assertEqual(result_from_outcome(self.latest()), result)
        self.assertEqual(len(self.latest()["ai_events"]), 4)
        self.assertTrue(self.latest()["outcome"]["result"]["evidence"][0]["source_manifest"])

    def test_local_demo_calls_no_model(self):
        def forbidden(*args, **kwargs):
            self.fail("demo must not call AI")
        result = run_analysis(self.path, self.actor, self.case, "demo", "", 1, provider_call=forbidden)
        self.assertTrue(result["is_demo"])
        self.assertEqual(result["stage_outputs"], {})
        self.assertEqual(self.latest()["ai_events"], [])
        self.assertEqual(self.latest()["status"], "partial")
        self.assertTrue(result["chart"]["main"]["lines"])

    def test_source_example_projects_both_charts_with_verified_branch_facts(self):
        source_input = {"question": self.input["question"],
                        "casting": {"method": "meibu", "results": ["5", "2", "4"]}}
        self.case = self.store.create_case(self.actor, source_input, idempotency_key="source-example")["case_id"]
        result, provider = self.run_model()
        self.assertEqual(result["status"], "completed")
        projected = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        facts = {f["fact_id"]: f for f in projected["facts"]}
        self.assertEqual(facts["CHART_NAME"]["value"], "泽火革")
        self.assertEqual(facts["CHANGED_CHART_NAME"]["value"], "水火既济")
        self.assertEqual(json.loads(facts["CHART_BITS"]["value"]), [1, 0, 1, 1, 1, 0])
        self.assertEqual(json.loads(facts["CHANGED_CHART_BITS"]["value"]), [1, 0, 1, 0, 1, 0])
        self.assertEqual(json.loads(facts["MOVING_POSITIONS"]["value"]), [4])
        self.assertIs(facts["HAS_CHANGED_STRUCTURE"]["value"], True)
        self.assertEqual(facts["CHANGED_LOWER_TRIGRAM"]["value"], "离")
        self.assertEqual(facts["CHANGED_UPPER_TRIGRAM"]["value"], "坎")
        # Source: 离内卯丑亥，坎外申戌子. The fifth/sixth branches also change
        # with the upper trigram, while only the fourth line is moving.
        branches = "卯丑亥申戌子"
        elements = "木土水金土水"
        for position, (branch, element) in enumerate(zip(branches, elements), 1):
            self.assertEqual(facts[f"CHANGED_LINE_{position}_BRANCH"]["value"], branch)
            self.assertEqual(facts[f"CHANGED_LINE_{position}_ELEMENT"]["value"], element)
            self.assertEqual(facts[f"CHANGED_LINE_{position}_BRANCH"]["source_rule_id"], "chart.branch_assignment")
        allowed = {rule["rule_id"] for rule in projected["rules"]}
        self.assertTrue(all(f["source_rule_id"] in allowed for f in projected["facts"] if f["kind"] == "chart"))
        self.assertFalse(any("RELATIVE" in fid or "SHI" in fid or "YING" in fid for fid in facts if fid.startswith("CHANGED_")))
        self.assertNotIn("GAP_CHANGED_ROLE", {g["gap_id"] for g in projected["unresolved_gaps"]})
        self.assertEqual(self.latest()["outcome"]["result"]["chart_snapshot"], result["chart"])

    def test_static_chart_does_not_project_an_independent_changed_chart(self):
        static_input = {"question": self.input["question"],
                        "casting": {"method": "meibu", "results": ["5", "2", "square"]}}
        self.case = self.store.create_case(self.actor, static_input, idempotency_key="static-example")["case_id"]
        result, provider = self.run_model()
        self.assertEqual(result["status"], "completed")
        projected = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        facts = {f["fact_id"]: f for f in projected["facts"]}
        self.assertEqual(facts["CHART_NAME"]["value"], "泽火革")
        self.assertIs(facts["HAS_CHANGED_STRUCTURE"]["value"], False)
        self.assertEqual(json.loads(facts["MOVING_POSITIONS"]["value"]), [])
        self.assertFalse(any(fid.startswith("CHANGED_") for fid in facts))
        self.assertIsNone(result["chart"]["changed_structure"])
        self.assertNotIn("GAP_CHANGED_ROLE", {g["gap_id"] for g in projected["unresolved_gaps"]})

    def test_chart_revision_preserves_previous_changed_chart_and_projected_facts(self):
        first, first_provider = self.run_model()
        original_run = copy.deepcopy(self.latest())
        self.assertIsNotNone(first["chart"]["changed_structure"])
        revised = {"question": self.input["question"], "lines": ["young_yang"] * 6}
        self.store.revise_case(self.actor, self.case, revised, reason="更正为实际静卦", expected_revision_seq=1, idempotency_key="chart-revision")
        second_provider = BoundProvider()
        second = run_analysis(self.path, self.actor, self.case, "deepseek", "fake-model", 2, provider_call=second_provider)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["chart"]["main"]["name"], "乾为天")
        self.assertIsNone(second["chart"]["changed_structure"])
        runs = self.store.export_case(self.actor, self.case)["analysis_runs"]
        self.assertEqual(runs[0], original_run)
        old_attempt = next(event["attempt"] for event in runs[0]["ai_events"] if event["attempt"]["model_run_metadata"]["stage_input"].get("facts") is not None)
        originally_projected = next(call["input"]["facts"] for call in first_provider.calls if call["stage"] == "interpretation")
        self.assertEqual(old_attempt["model_run_metadata"]["stage_input"]["facts"], originally_projected)
        self.assertEqual(runs[0]["outcome"]["result"]["chart_snapshot"], first["chart"])
        self.assertEqual(runs[1]["outcome"]["result"]["chart_snapshot"], second["chart"])

    def test_intent_clarification_stops_without_guessing(self):
        result, provider = self.run_model("clarify")
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(result["clarifying_questions"])
        self.assertEqual(self.latest()["status"], "unresolved")
        self.assertEqual(self.store.export_case(self.actor, self.case)["context_events"][-1]["event_type"], "clarification_question")

    def test_selection_clarification_and_rule_gap_stop(self):
        for mode in ("selection_clarify", "rule_gap"):
            with self.subTest(mode=mode):
                result, provider = self.run_model(mode)
                self.assertEqual(result["status"], "unresolved")
                self.assertEqual(len(provider.calls), 2)
                self.assertEqual(self.latest()["status"], "unresolved")

    def test_ready_selection_with_questions_and_gaps_reaches_conditional_report(self):
        self.make_subject_relation_case()
        provider = BoundProvider("conditional")
        issue = "尚不清楚交货期限；先按本次已说明的交易目标作有限解读。"
        question = {"question_id": "Q_DELIVERY", "text": "约定什么时候交货？",
                    "why_needed": "用于进一步细化时间范围，不改变本次交易用途。", "affects": "time_scope"}
        def with_notes(*args, **kwargs):
            response = provider(*args, **kwargs)
            if provider.calls[-1]["stage"] == "selection":
                out = json.loads(response["raw_text"])
                out.update(unresolved=[issue], clarifying_questions=[question], selected_primary_id=None)
                response["raw_text"] = json.dumps(out, ensure_ascii=False)
            return response
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=with_notes)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(provider.calls), 4)
        selection = result["stage_outputs"]["selection"]
        self.assertEqual(selection["unresolved"], [issue])
        self.assertEqual(selection["clarifying_questions"], [question])
        self.assertEqual(selection["selected_primary_id"], selection["candidates"][0]["candidate_id"])
        projection = provider.calls[2]["input"]
        gap = next(g for g in projection["unresolved_gaps"] if g["gap_id"] == "GAP_SELECTION_UNRESOLVED_0")
        self.assertIn("尚不清楚交货期限", gap["description"])
        self.assertNotIn("取用阶段早期",gap["description"])
        self.assertFalse(gap["blocking"])
        self.assertTrue(result["audit_report"]["unresolved"])
        self.assertIn(question["text"], result["clarifying_questions"])
        self.assertEqual(result["display_report"]["conclusion"]["qualification"], "conditional")
        stored = self.latest()
        self.assertIsNone(json.loads(stored["ai_events"][1]["attempt"]["raw_output"])["selected_primary_id"])
        self.assertTrue(stored["ai_events"][1]["attempt"]["model_run_metadata"]["normalization_changes"])
        self.assertEqual(self.store.export_case(self.actor, self.case)["context_events"][-1]["content"]["question_id"], "Q_DELIVERY")

    def test_missing_or_non_primary_selection_fails_with_precise_detail(self):
        for mode in ("no_primary", "wrong_id", "supporting_id"):
            with self.subTest(mode=mode):
                provider = BoundProvider()
                def invalid_selection(*args, **kwargs):
                    response = provider(*args, **kwargs)
                    if provider.calls[-1]["stage"] == "selection":
                        out = json.loads(response["raw_text"])
                        if mode == "wrong_id":
                            out["selected_primary_id"] = "UNKNOWN"
                        else:
                            out["candidates"][0]["purpose"] = "supporting"
                            if mode == "no_primary": out["selected_primary_id"] = None
                        response["raw_text"] = json.dumps(out, ensure_ascii=False)
                    return response
                result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=invalid_selection)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error"]["stage"], "selection")
                self.assertIn("$.candidates[0].purpose:" if mode == "supporting_id" else "$.selected_primary_id:", result["error"]["validation_detail"])
                self.assertNotIn("and no blocking issue", result["error"]["validation_detail"])
                self.assertNotIn("interpretation", result["stage_outputs"])

    def test_bad_json_is_retained_and_retried_once(self):
        result, provider = self.run_model("malformed")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(provider.calls), 2)
        attempts = self.latest()["ai_events"]
        self.assertEqual([x["attempt"]["parse_status"] for x in attempts], ["invalid_json", "invalid_json"])
        self.assertTrue(all(x["attempt"]["adopted_output"] is None for x in attempts))
        self.assertEqual(provider.calls[0]["input"], provider.calls[1]["input"])
        self.assertEqual(provider.calls[1]["repair_context"]["previous_output"], "this is not JSON")
        self.assertEqual(result["error"]["stage"], "intent")
        self.assertEqual(result["error"]["attempts"], 2)
        self.assertIn("JSON", result["error"]["validation_detail"])
        self.assertIn("理解问题", result["error"]["message"])

    def test_repaired_json_preserves_both_attempts(self):
        result, provider = self.run_model("repair")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(provider.calls), 5)
        self.assertEqual(len(self.latest()["ai_events"]), 5)
        self.assertIsNone(self.latest()["ai_events"][0]["attempt"]["adopted_output"])
        self.assertIsNotNone(self.latest()["ai_events"][1]["attempt"]["adopted_output"])
        self.assertIsNone(provider.calls[0]["repair_context"])
        self.assertEqual(provider.calls[1]["repair_context"]["previous_output"], "this is not JSON")
        self.assertIn("JSON", provider.calls[1]["repair_context"]["validation_error"])
        self.assertEqual(provider.calls[0]["prompt"], provider.calls[1]["prompt"])
        self.assertEqual(provider.calls[0]["input"], provider.calls[1]["input"])
        self.assertIsNone(provider.calls[2]["repair_context"])

    def test_unknown_rule_is_never_adopted(self):
        result, provider = self.run_model("unknown_rule")
        self.assertEqual(result["status"], "failed")
        self.assertEqual([x["stage"] for x in provider.calls], ["intent", "selection", "selection"])
        self.assertNotIn("selection", result["stage_outputs"])
        self.assertEqual(result["error"]["stage"], "selection")
        self.assertIn("不存在", result["error"]["message"])
        self.assertIn("nonexistent refs", result["error"]["validation_detail"])
        retry = provider.calls[-1]["repair_context"]
        self.assertIn("fabricated.rule", retry["previous_output"])
        self.assertIn("nonexistent refs", retry["validation_error"])

    def test_repair_context_is_required_to_recover_a_conditional_conclusion(self):
        self.make_subject_relation_case()
        valid = BoundProvider("conditional")
        calls = []
        def repairable(provider, model, prompt, inp, **options):
            calls.append(copy.deepcopy(options))
            if len(calls) == 1:
                return {"raw_text": "broken first answer"}
            if len(calls) == 2:
                self.assertEqual(options["repair_context"]["previous_output"], "broken first answer")
                self.assertIn("JSON", options["repair_context"]["validation_error"])
            else:
                self.assertNotIn("repair_context", options)
            return valid(provider, model, prompt, inp, **options)
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=repairable)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(calls), 5)
        self.assertEqual(result["display_report"]["conclusion"]["qualification"], "conditional")
        self.assertEqual(self.latest()["ai_events"][1]["attempt"]["model_run_metadata"]["repair_of_attempt"], 1)

    def test_safe_compatibility_completes_all_stages_without_retries(self):
        self.make_subject_relation_case()
        valid = BoundProvider("conditional")
        originals = []
        def compatible(*args, **kwargs):
            response = valid(*args, **kwargs)
            out = json.loads(response["raw_text"])
            out.pop("binding")
            out.pop("clarifying_questions")
            stage = valid.calls[-1]["stage"]
            for key in {"intent": ["independent_questions"], "selection": ["route_requests", "unresolved"], "interpretation": ["advice"], "report": []}[stage]:
                out.pop(key)
            if stage == "selection":
                out["candidates"][0].pop("assumptions")
            if stage == "interpretation":
                out["claims"][0]["requires_review"] = False
                out["status"] = "partial"
                out["conclusion"]["key_conditions"] = ["模型对成立条件的另一个概括。"]
                out["conclusion"]["limits"] = ["模型对局限的另一个概括。"]
            if stage == "report":
                out.pop("conclusion")
                out.pop("uncertainties")
                out["question_restated"] = "模型改写了问题"
            response["raw_text"] = "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```"
            originals.append(response["raw_text"])
            return response
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=compatible)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(valid.calls), 4)
        interpretation = result["stage_outputs"]["interpretation"]
        conclusion = result["display_report"]["conclusion"]
        self.assertEqual(conclusion["qualification"], "conditional")
        for assumption in interpretation["claims"][0]["assumptions"]:
            self.assertIn(assumption, conclusion["key_conditions"])
        for limit in interpretation["claims"][0]["limitations"]:
            self.assertIn(limit, conclusion["limits"])
        events = self.latest()["ai_events"]
        self.assertEqual([e["attempt"]["raw_output"] for e in events], originals)
        self.assertTrue(all(e["attempt"]["model_run_metadata"]["normalization_changes"] for e in events))

    def test_report_only_failure_keeps_already_accepted_conclusion(self):
        self.make_subject_relation_case()
        valid = BoundProvider("conditional")
        def broken_report(*args, **kwargs):
            response = valid(*args, **kwargs)
            if valid.calls[-1]["stage"] == "report":
                response["raw_text"] = "not JSON"
            return response
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=broken_report)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(any(w["stage"]=="report" for w in result["audit_report"]["warnings"]))
        self.assertEqual(len(valid.calls), 5)
        self.assertEqual(result["display_report"]["conclusion"], result["stage_outputs"]["interpretation"]["conclusion"])

    def test_bad_reference_is_audited_but_cross_case_binding_is_fatal(self):
        result,provider=self.run_model('bad_fact')
        self.assertEqual(result['status'],'completed')
        self.assertTrue(any(w['code']=='UNKNOWN_REFERENCE' for w in result['audit_report']['warnings']))
        self.assertEqual(len(provider.calls),4)
        result,provider=self.run_model('bad_binding')
        self.assertEqual(result['status'],'failed')
        self.assertEqual(self.latest()['status'],'failed')

    def test_provider_failure_has_terminal_record(self):
        class SyntheticProviderError(Exception):
            code = "NOT_CONFIGURED"
        def missing(*args, **kwargs):
            raise SyntheticProviderError("未配置API密钥。")
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=missing)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "NOT_CONFIGURED")
        self.assertEqual(len(self.latest()["ai_events"]), 1)
        self.assertEqual(self.latest()["ai_events"][0]["attempt"]["parse_status"], "provider_error")

    def test_provider_invalid_json_retains_raw_and_can_repair_once(self):
        class InvalidJson(Exception):
            code = "invalid_json"
            raw_text = "{malformed original model text"
            metadata = {"request_id": "failed-request", "usage": {"total_tokens": 9}}
        valid = BoundProvider()
        calls = []
        def repairable(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise InvalidJson("模型输出JSON格式错误。")
            return valid(*args, **kwargs)
        result = run_analysis(self.path, self.actor, self.case, "deepseek", "fake", 1, provider_call=repairable)
        self.assertEqual(result["status"], "completed")
        self.assertIsNone(calls[0]["timeout"])
        event = self.latest()["ai_events"][0]["attempt"]
        self.assertEqual(event["raw_output"], InvalidJson.raw_text)
        self.assertEqual(event["parse_status"], "invalid_json")
        self.assertEqual(event["model_run_metadata"]["request_id"], "failed-request")
        self.assertEqual(calls[1]["repair_context"]["previous_output"], InvalidJson.raw_text)

    def test_prior_clarification_is_given_with_user_answer(self):
        first, _ = self.run_model("clarify")
        self.store.append_context_event(self.actor, self.case, event_type="clarification_answer", content={"text": "我要出售，不是自用。"}, idempotency_key="answer")
        result, provider = self.run_model()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(provider.calls[0]["input"]["prior_clarifications"][0]["text"], first["clarifying_questions"][0])
        self.assertIn("我要出售", json.dumps(provider.calls[0]["input"]["user_evidence"], ensure_ascii=False))

    def test_stale_revision_starts_no_run(self):
        revised = {**self.input, "question": "我准备出售另一批余粮，能否成交？"}
        self.store.revise_case(self.actor, self.case, revised, reason="澄清目标", expected_revision_seq=1, idempotency_key="revision")
        with self.assertRaises(Conflict):
            self.run_model()
        self.assertEqual(self.store.export_case(self.actor, self.case)["analysis_runs"], [])

    def test_feedback_is_not_model_input_and_snapshots_are_immutable(self):
        self.store.append_context_event(self.actor, self.case, event_type="background", content={"text": "卖的是去年剩余粮食。"}, idempotency_key="bg")
        first, provider = self.run_model()
        original_run = copy.deepcopy(self.latest())
        self.store.add_feedback(self.actor, self.case, reported_outcome="后来意外全部成交，反馈专用标记", idempotency_key="feedback", analysis_run_id=first["analysis_run_id"])
        second, provider = self.run_model()
        self.assertNotEqual(first["analysis_run_id"], second["analysis_run_id"])
        self.assertNotIn("反馈专用标记", json.dumps(provider.calls, ensure_ascii=False))
        self.assertIn("去年剩余粮食", json.dumps(provider.calls[0]["input"], ensure_ascii=False))
        runs = self.store.export_case(self.actor, self.case)["analysis_runs"]
        self.assertEqual(runs[0], original_run)

    def test_unreferenced_report_prose_cannot_become_display_prediction(self):
        result, _ = self.run_model("bad_report_prose")
        self.assertEqual(result["status"], "completed")
        self.assertIn("无依据的新预测", result["report"]["summary"])
        self.assertNotIn("无依据的新预测", json.dumps(result["display_report"], ensure_ascii=False))

    def test_progress_failure_does_not_abandon_analysis(self):
        def broken(event):
            raise RuntimeError("UI disconnected")
        result, _ = self.run_model(progress=broken)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.latest()["status"], "completed")

    def make_subject_relation_case(self, question="我准备卖掉余粮，想问能否成交。"):
        # 水地比: 应为水、世为木. This known structural relation exercises a
        # conditional synthesis; it is not a labeled prediction success case.
        self.input = {"question": question,
                      "lines": ["young_yin", "young_yin", "young_yin",
                                "young_yin", "young_yang", "young_yin"]}
        self.case = self.store.create_case(self.actor, self.input, idempotency_key="subject-case")["case_id"]

    def test_conditional_conclusion_is_returned_saved_and_reopened_unchanged(self):
        self.make_subject_relation_case()
        result, provider = self.run_model("conditional")
        self.assertEqual(result["status"], "completed")
        self.assertEqual([call["stage"] for call in provider.calls], ["intent", "selection", "interpretation", "report"])
        conclusion = result["stage_outputs"]["interpretation"]["conclusion"]
        self.assertEqual(conclusion["qualification"], "conditional")
        self.assertEqual(conclusion["direction"], "favorable")
        self.assertEqual(result["report"]["conclusion"], conclusion)
        self.assertEqual(result["display_report"]["conclusion"], conclusion)
        self.assertEqual(result["display_report"]["summary"], conclusion["answer"])
        self.assertIn("偏向得到支持", result["display_report"]["summary"])
        self.assertTrue(conclusion["limits"])
        self.assertTrue(result["stage_outputs"]["interpretation"]["claims"][0]["requires_review"])
        # Reopen the persisted case through a separate store, rather than
        # checking the same in-memory result object against itself.
        reopened = CaseStore(self.path)
        try:
            run = reopened.export_case(self.actor, self.case)["analysis_runs"][-1]
            self.assertEqual(result_from_outcome(run), result)
            self.assertEqual(run["outcome"]["result"]["chart_snapshot"], result["chart"])
        finally:
            reopened.close()

    def test_sparse_undated_question_still_retains_conditional_interpretation(self):
        self.make_subject_relation_case()
        result, provider = self.run_model("conditional")
        self.assertEqual(result["status"], "completed")
        projection = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        self.assertIn("GAP_CALENDAR", {g["gap_id"] for g in projection["unresolved_gaps"]})
        self.assertNotEqual(result["chart"]["calendar"]["status"], "computed")
        self.assertFalse(any(f["fact_id"].startswith("CALENDAR_") for f in projection["facts"]))
        self.assertEqual(result["display_report"]["conclusion"]["qualification"], "conditional")
        self.assertTrue(any("偏向得到支持" in section["content"] for section in result["display_report"]["sections"]))
        self.assertTrue(result["unresolved"])

    def test_personal_general_question_uses_subject_not_siblings(self):
        self.make_subject_relation_case("明天是否顺利？")
        result, provider = self.run_model("self_condition")
        self.assertEqual(result["status"], "completed")
        primary = result["stage_outputs"]["selection"]["candidates"][0]
        self.assertEqual(primary["subject_reference"], "shi")
        self.assertIsNone(primary["relation"])
        self.assertIsNone(primary["six_relative"])
        projection = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        facts = {f["fact_id"]: f for f in projection["facts"]}
        self.assertEqual(facts["SUBJECT_REFERENCE"]["value"], "世爻")
        self.assertEqual(json.loads(facts["MATCHING_LINES"]["value"]), [result["chart"]["shi_position"]])
        self.assertNotIn("FUNCTION_SELECTION", facts)
        self.assertNotIn("GAP_USE_LINE", {g["gap_id"] for g in projection["unresolved_gaps"]})
        self.assertIn("明日个人整体处境", result["display_report"]["summary"])
        self.assertEqual(result["display_report"]["conclusion"]["qualification"], "conditional")

    def test_supplement_reanalysis_keeps_old_conclusion_and_frozen_evidence(self):
        self.make_subject_relation_case()
        first, _ = self.run_model("conditional")
        frozen = copy.deepcopy(self.latest())
        supplement = "对方已确认样品，仍待约定提货时间。"
        self.store.append_context_event(self.actor, self.case, event_type="background",
            content={"text": supplement}, idempotency_key="supplement-current-fact")
        second, provider = self.run_model("conditional")
        self.assertEqual(second["status"], "completed")
        self.assertNotEqual(first["analysis_run_id"], second["analysis_run_id"])
        self.assertIn(supplement, json.dumps(provider.calls[0]["input"]["user_evidence"], ensure_ascii=False))
        projection = next(call["input"] for call in provider.calls if call["stage"] == "interpretation")
        background = next(f for f in projection["facts"] if f["kind"] == "context" and f["value"] == supplement)
        claim = second["stage_outputs"]["interpretation"]["claims"][0]
        self.assertIn(background["fact_id"], claim["fact_refs"])
        self.assertIn(supplement, json.dumps(second["display_report"]["conclusion"], ensure_ascii=False))
        runs = self.store.export_case(self.actor, self.case)["analysis_runs"]
        self.assertEqual(runs[0], frozen)
        self.assertEqual(result_from_outcome(runs[0])["display_report"]["conclusion"], first["display_report"]["conclusion"])
        self.assertNotIn(supplement, json.dumps(runs[0], ensure_ascii=False))

    def test_report_cannot_replace_the_accepted_conditional_conclusion(self):
        self.make_subject_relation_case()
        result, provider = self.run_model("changed_report_conclusion")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(provider.calls), 4)
        # Report copies server-owned fields mechanically. It cannot replace the
        # already validated interpretation with an invented second conclusion.
        self.assertEqual(result["report"]["conclusion"], result["stage_outputs"]["interpretation"]["conclusion"])
        event = self.latest()["ai_events"][-1]["attempt"]
        self.assertIn("另行改写", event["raw_output"])
        self.assertTrue(event["model_run_metadata"]["normalization_changes"])
        self.assertEqual(result["display_report"]["conclusion"], result["stage_outputs"]["interpretation"]["conclusion"])
        self.assertNotIn("另行改写", json.dumps(result["display_report"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
