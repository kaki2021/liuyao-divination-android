"""Anonymous semantic regression fixtures, never a user's case or account."""
import copy
import unittest

from liuyao_app.interpretation_checks import interpretation_errors


def fact(fact_id, value, subject=""):
    return {"fact_id": fact_id, "value": value, "subject": subject}


class InterpretationChecksTests(unittest.TestCase):
    def fixture(self, statement, value="", subject="世身第2爻寅木"):
        inp = {"facts": [
            fact("CAL_DAY_TO_LINE_2", "is_controlled_by", "日支未土 → 本卦第2爻寅木"),
            fact("BODY_POSITION", 2), fact("CALENDAR_DAY", "辛未"),
        ], "rules": []}
        out = {"claims": [{"statement": statement, "proposition": {"subject": subject, "value": value},
                           "fact_refs": ["CAL_DAY_TO_LINE_2", "BODY_POSITION"],
                           "rule_refs": ["relation.ordinary_wuxing"]}]}
        return inp, out

    def errors(self, statement, value="", subject="世身第2爻寅木"):
        inp, out = self.fixture(statement, value, subject)
        return interpretation_errors(out, inp)

    def test_inverted_day_and_personal_subject_are_reported(self):
        errors = self.errors("从个人尺度看，个人自身状态受日支方向性克制。", "日支方向性克制，个人状态偏弱")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "RELATION_DIRECTION_MISMATCH")
        self.assertIn("寅木克日支未土", errors[0]["message"])
        self.assertIn("statement", errors[0]["path"])

    def test_proposition_alone_is_checked(self):
        self.assertTrue(self.errors("世身落于二爻。", "日支方向性克制，个人状态偏弱"))

    def test_shorthand_does_not_reverse_passive_or_ambiguous_statements(self):
        for value in ("日支未土被寅木克制", "与日支未土相克", "日支未土受寅木克制"):
            with self.subTest(value=value):
                self.assertEqual(self.errors("世身落于二爻。", value), [])

    def test_explicit_elemental_direction_is_checked(self):
        for text in ("未土克寅木。", "日支对寅木有克制作用。", "土克木。", "寅木受未土克制。"):
            with self.subTest(text=text):
                self.assertTrue(self.errors(text))

    def test_correct_direction_and_source_relative_description_pass(self):
        for text in ("寅木克未土。", "木克土。", "日支未土受世身寅木克制。",
                     "与日支未土存在源受目标所克的方向关系。", "建议关注个人状态并主动准备。"):
            with self.subTest(text=text):
                self.assertEqual(self.errors(text), [])

    def test_negative_and_conditional_direction_phrases_are_not_flagged(self):
        for text in ("不是未土克寅木。", "不能把寅木克未土说成未土克寅木。", "并非土克木。",
                     "世身不一定受日支克制。", "如果日支克制世身，仍需要另行判断。"):
            with self.subTest(text=text):
                self.assertEqual(self.errors(text), [])

    def test_month_direction_and_generating_direction(self):
        inp, out = self.fixture("本卦第2爻寅木克月支酉金。")
        inp["facts"][0] = fact("CAL_MONTH_TO_LINE_2", "controls", "月支酉金 → 本卦第2爻寅木")
        out["claims"][0]["fact_refs"] = ["CAL_MONTH_TO_LINE_2"]
        self.assertEqual(interpretation_errors(out, inp)[0]["code"], "RELATION_DIRECTION_MISMATCH")
        inp["facts"][0] = fact("CAL_MONTH_TO_LINE_2", "generates", "月支酉金 → 本卦第2爻子水")
        out["claims"][0]["statement"] = "子水生酉金。"
        self.assertTrue(interpretation_errors(out, inp))
        out["claims"][0]["statement"] = "酉金生子水。"
        self.assertEqual(interpretation_errors(out, inp), [])

    def test_explicit_source_target_fields_supported(self):
        inp, out = self.fixture("未土克寅木。")
        inp["facts"][0].update(subject="方向", source="日支未土", target="二爻寅木")
        self.assertTrue(interpretation_errors(out, inp))

    def test_ambiguous_implicit_target_is_left_for_review(self):
        inp, out = self.fixture("个人受日支克制。")
        inp["facts"].append(fact("CAL_DAY_TO_LINE_3", "controls", "日支未土 → 本卦第3爻子水"))
        out["claims"][0]["fact_refs"].append("CAL_DAY_TO_LINE_3")
        self.assertEqual(interpretation_errors(out, inp), [])

    def test_unrelated_uncited_fact_does_not_block(self):
        inp, out = self.fixture("土克木。")
        out["claims"][0]["fact_refs"] = []
        self.assertEqual(interpretation_errors(out, inp), [])

    def test_guabody_absence_does_not_authorize_missing_real_world_support(self):
        inp, out = self.fixture("卦身未出现，可提示当前事项缺少核心支点。")
        inp["facts"].append(fact("REL_GUA_BODY_PRESENT", False))
        out["claims"][0]["fact_refs"] = ["REL_GUA_BODY_PRESENT"]
        out["claims"][0]["rule_refs"] = ["chart.gua_body"]
        self.assertEqual(interpretation_errors(out, inp)[0]["code"], "UNSUPPORTED_SCOPE")
        out["claims"][0]["statement"] = "卦身未出现，但不能说现实事项缺少核心支点。"
        self.assertEqual(interpretation_errors(out, inp), [])

    def test_specific_interpretation_rule_defers_scope_to_review(self):
        inp, out = self.fixture("卦身未出现，可提示现实事项缺少核心支点。")
        out["claims"][0]["rule_refs"] = ["interpretation.specific_case_rule"]
        inp["rules"].append({"rule_id": "interpretation.specific_case_rule", "usage": "interpretation"})
        self.assertEqual(interpretation_errors(out, inp), [])

    def test_sole_moving_shi_does_not_assign_real_world_control(self):
        inp, out = self.fixture("世爻是唯一动爻，表示主动权在我方。")
        out["claims"][0]["rule_refs"] = ["casting.four_states", "interpretation.no_intrinsic_omen"]
        self.assertEqual(interpretation_errors(out, inp)[0]["code"], "UNSUPPORTED_SCOPE")
        out["claims"][0]["statement"] = "世爻是唯一动爻，这提示事情进展的关键在于求测者一方主动推动。"
        self.assertTrue(interpretation_errors(out, inp))

    def test_moving_fact_advice_and_negative_statement_remain_allowed(self):
        for text in ("世爻是唯一动爻，建议我方主动准备。", "世爻是唯一动爻，不代表主动权在我方。",
                     "若世爻独动可代表主动权在我方，尚需核实适用条件。"):
            with self.subTest(text=text):
                self.assertEqual(self.errors(text), [])

    def test_missing_cast_date_contradiction_with_calendar(self):
        for text in ("用户未提供起卦日期。", "缺少实际起卦时间。", "起卦日期未知。"):
            with self.subTest(text=text):
                errors = self.errors(text)
                self.assertEqual(errors[0]["code"], "CONTEXT_CONTRADICTION")

    def test_date_correction_and_algorithm_gaps_remain_allowed(self):
        for text in ("前阶段曾说用户未提供起卦日期，当前已经提供，应以排盘为准。",
                     "并非没有提供起卦日期。", "当前缺少完整应期算法。", "起卦日期已知，实际结果尚不明。",
                     "起卦日期已知但地点未知。", "起卦日期准确但时区未知。"):
            with self.subTest(text=text):
                self.assertEqual(self.errors(text), [])

    def test_real_missing_date_allowed_without_computed_calendar(self):
        inp, out = self.fixture("起卦日期未提供。")
        inp["facts"] = []
        self.assertEqual(interpretation_errors(out, inp), [])

    def test_conclusion_and_uncertainty_context_are_checked(self):
        inp, out = self.fixture("当前可作有限分析。")
        out["conclusion"] = {"answer": "起卦日期不明，具体时间待定。"}
        out["uncertainties"] = [{"impact": "起卦日期、年龄、旺衰等局部缺口未提供。"}]
        errors = interpretation_errors(out, inp)
        self.assertEqual(len(errors), 2)
        self.assertEqual({e["code"] for e in errors}, {"CONTEXT_CONTRADICTION"})

    def test_checks_do_not_mutate_and_are_bounded(self):
        inp, out = self.fixture("未土克寅木。用户未提供起卦日期。")
        original = copy.deepcopy((inp, out))
        interpretation_errors(out, inp)
        self.assertEqual((inp, out), original)
        out["claims"] *= 100
        self.assertLessEqual(len(interpretation_errors(out, inp)), 40)

    def test_invalid_top_level_shapes_belong_to_schema(self):
        for out, inp in ((None, {}), ({}, None), ([], {}), ({"claims": None}, {})):
            self.assertEqual(interpretation_errors(out, inp), [])
        inp, out = self.fixture("可作有限判断")
        out["claims"][0].update(proposition=[], rule_refs=[{}])
        self.assertEqual(interpretation_errors(out, inp), [])
        self.assertEqual(interpretation_errors(out, {"facts": None, "rules": None}), [])


if __name__ == "__main__":
    unittest.main()
