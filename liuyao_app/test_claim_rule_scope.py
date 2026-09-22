"""Anonymous scope regressions; no uploaded question or account is embedded."""
import copy
import unittest

from liuyao_app.claim_rule_scope import claim_rule_errors


def fixture():
    def rule(identifier, usage):
        return {"rule_id": identifier, "status": "approved", "source_role": "core", "usage": usage}

    def fact(identifier, value, kind="chart", rule=None):
        return {"fact_id": identifier, "value": value, "kind": kind, "source_rule_id": rule}

    inp = {"selection": {"status": "ready", "selected_primary_id": "target", "candidates": [
        {"candidate_id": "target", "purpose": "primary", "six_relative": "parents",
         "rule_refs": ["test.functional", "test.documents"]}]},
        "rules": [rule("test.functional", "selection"), rule("test.documents", "selection"),
                  rule("test.kinship", "display"), rule("test.other_selection", "selection"),
                  rule("test.effects", "interpretation")],
        "facts": [fact("FUNCTION_SELECTION", "parents", "selection", "test.functional"),
                  fact("MATCHING_LINES", "[1]", "selection", "test.kinship"),
                  fact("CTX_0", "询问某文件的处理", "context"),
                  fact("CHART_PALACE", "示例宫"), fact("PALACE_ELEMENT", "土", "calculation"),
                  fact("LINE_1_BRANCH", "子"), fact("LINE_1_ELEMENT", "水"),
                  fact("LINE_2_BRANCH", "寅"), fact("CAL_DAY_TO_LINE_1", "controls", "calculation")]
        + [fact(f"LINE_{i}_RELATIVE_CODE", "parents" if i == 1 else "wealth") for i in range(1, 7)]}
    claim = {"claim_id": "role", "kind": "ai_hypothesis", "dimension": "support", "direction": "neutral",
             "statement": "所问文件按功能可取父母类，匹配初爻子水；这只是功能对应，不表示成功或失败。",
             "proposition": {"subject": "所问文件", "predicate": "功能六亲候选", "value": "父母类，初爻子水"},
             "fact_refs": ["CTX_0", "FUNCTION_SELECTION", "MATCHING_LINES", "LINE_1_BRANCH", "LINE_1_RELATIVE_CODE"],
             "rule_refs": ["test.functional", "test.documents", "test.kinship"], "inference_refs": [],
             "assumptions": ["关注的是文件本身"], "limitations": ["功能对应不等于实际结果"], "requires_review": True}
    out = {"claims": [claim], "advice": [{"advice_id": "prepare", "basis": "system_interpretation",
            "text": "可主动准备相关文件，核对文本版本与确认事项；不构成一定成功的预测。",
            "claim_refs": ["role"], "fact_refs": ["CTX_0"], "conditions": ["以文件办理为主要目标"]}]}
    return inp, out


class ClaimRuleScopeTests(unittest.TestCase):
    def test_bound_neutral_function_explanation_and_preparation_pass_unchanged(self):
        inp, out = fixture()
        before = copy.deepcopy((inp, out))
        self.assertEqual(claim_rule_errors(out, inp), [])
        self.assertEqual((inp, out), before)

    def test_actual_pattern_with_only_primary_selection_rules_passes(self):
        inp, out = fixture()
        out["claims"][0]["rule_refs"] = ["test.functional", "test.documents"]
        out["claims"][0]["fact_refs"] += ["CHART_PALACE", "PALACE_ELEMENT"]
        self.assertEqual(claim_rule_errors(out, inp), [])

    def test_referenced_matching_definition_can_have_selection_usage(self):
        inp, out = fixture()
        inp["rules"][2]["usage"] = "selection"
        self.assertEqual(claim_rule_errors(out, inp), [])

    def test_non_neutral_or_predictive_dimensions_still_require_interpretation(self):
        for field, values in (("direction", ("favorable", "unfavorable", "mixed", "unknown")),
                              ("dimension", ("outcome", "subject_effect", "cost", "timing", "obstacle"))):
            for value in values:
                with self.subTest(field=field, value=value):
                    inp, out = fixture()
                    out["claims"][0][field] = value
                    self.assertEqual(claim_rule_errors(out, inp)[0]["code"], "HYPOTHESIS_INTERPRETATION_RULE_REQUIRED")

    def test_original_interpretation_capability_remains(self):
        inp, out = fixture()
        out["claims"][0].update(dimension="subject_effect", direction="unfavorable", rule_refs=["test.effects"])
        self.assertEqual(claim_rule_errors(out, inp), [])

    def test_each_required_binding_is_enforced(self):
        mutations = [
            lambda i, o: o["claims"][0]["fact_refs"].remove("FUNCTION_SELECTION"),
            lambda i, o: o["claims"][0]["fact_refs"].remove("MATCHING_LINES"),
            lambda i, o: i["selection"].update(selected_primary_id="other"),
            lambda i, o: i["selection"]["candidates"][0].update(six_relative="wealth"),
            lambda i, o: i["selection"]["candidates"][0].update(purpose="supporting"),
            lambda i, o: i["selection"]["candidates"][0].update(subject_reference="shi"),
            lambda i, o: o["claims"][0].update(rule_refs=["test.other_selection", "test.kinship"]),
            lambda i, o: o["claims"][0].update(rule_refs=["test.kinship"]),
            lambda i, o: o["claims"][0]["rule_refs"].append("missing_rule"),
            lambda i, o: o["claims"][0]["rule_refs"].append("test.other_selection"),
            lambda i, o: o["claims"][0].update(requires_review=False),
            lambda i, o: o["claims"][0].update(inference_refs=["invented"]),
            lambda i, o: i["rules"][0].update(source_role="auxiliary"),
            lambda i, o: i["facts"][0].update(source_rule_id="test.other_selection"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                inp, out = fixture()
                mutation(inp, out)
                self.assertTrue(claim_rule_errors(out, inp))

    def test_matching_positions_use_complete_six_line_facts(self):
        for value in ("[2]", "[1, 2]", "[1, 1]", "[true]", "[0]", "{}", "not json"):
            with self.subTest(value=value):
                inp, out = fixture()
                inp["facts"][1]["value"] = value
                self.assertTrue(claim_rule_errors(out, inp))
        inp, out = fixture()
        inp["facts"] = [f for f in inp["facts"] if f["fact_id"] != "LINE_6_RELATIVE_CODE"]
        self.assertTrue(claim_rule_errors(out, inp))

    def test_nonmatching_and_forecast_facts_not_smuggled_into_mapping(self):
        for ref in ("LINE_2_BRANCH", "CAL_DAY_TO_LINE_1", "UNKNOWN"):
            with self.subTest(ref=ref):
                inp, out = fixture()
                out["claims"][0]["fact_refs"].append(ref)
                self.assertTrue(claim_rule_errors(out, inp))

    def test_affirmative_forecasts_rejected_despite_neutral_label(self):
        statements = ["合同一定签成。", "项目会成功。", "此卦主吉。", "由此可见主体受损。",
                      "这说明自身会受益。", "下个月签成。", "成功率为90%。",
                      "不是不能成功。", "不表示失败，但合同一定签成。", "并非成败结论，然而项目必然成功。",
                      "如果准备好文件合同一定签成。", "不是预测合同一定成功。"]
        for statement in statements:
            with self.subTest(statement=statement):
                inp, out = fixture()
                out["claims"][0]["statement"] = statement
                errors = claim_rule_errors(out, inp)
                self.assertEqual(errors[0]["code"], "SELECTION_EXPLANATION_SCOPE_EXCEEDED")

    def test_negations_questions_and_preparation_are_not_predictions(self):
        statements = ["不表示成功或失败。", "不是成败结论。", "本次问的是能否签成。",
                      "用户关心下个月是否能签成。", "不能据此判断合同必然失败。",
                      "父母类只表示功能候选，并不意味着一定成功。", "需要准备文件以供双方核对。",
                      "这不等于签约已成功或失败。", "签成与否需要更多依据。"]
        for statement in statements:
            with self.subTest(statement=statement):
                inp, out = fixture()
                out["claims"][0]["statement"] = statement
                self.assertEqual(claim_rule_errors(out, inp), [])

    def test_proposition_assumptions_and_advice_cannot_hide_guarantees(self):
        for field in ("proposition", "assumptions", "advice", "conditions"):
            with self.subTest(field=field):
                inp, out = fixture()
                if field == "proposition": out["claims"][0][field]["value"] = "合同必然签成"
                elif field == "assumptions": out["claims"][0][field] = ["主体一定受益"]
                elif field == "advice": out["advice"][0]["text"] = "按此准备即可确保合同成功。"
                else: out["advice"][0][field] = ["只要准备文件，合同一定签成"]
                errors = claim_rule_errors(out, inp)
                self.assertTrue(errors)
                self.assertIn("SCOPE_EXCEEDED", errors[0]["code"])

    def test_different_claim_scopes_checked_in_one_pass(self):
        inp, out = fixture()
        bad = copy.deepcopy(out["claims"][0])
        bad.update(claim_id="bad", direction="favorable")
        out["claims"].append(bad)
        out["advice"][0]["text"] = "这一定能成功。"
        self.assertEqual([x["code"] for x in claim_rule_errors(out, inp)],
                         ["HYPOTHESIS_INTERPRETATION_RULE_REQUIRED", "SELECTION_ADVICE_SCOPE_EXCEEDED"])

    def test_non_hypothesis_and_malformed_containers_do_not_crash(self):
        self.assertEqual(claim_rule_errors(None, {}), [])
        self.assertEqual(claim_rule_errors({"claims": [None, {}, {"kind": "real_world_context"}]}, {}), [])
        inp, out = fixture()
        out["claims"][0]["rule_refs"] = [None, {}]
        self.assertTrue(claim_rule_errors(out, inp))


if __name__ == "__main__":
    unittest.main()
