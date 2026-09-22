"""Checks relation direction and evidence boundaries, not prediction accuracy."""
import copy
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import base_chart
from liuyao_app.interpretation_evidence import (
    build_relation_facts, ordinary_relation, relation_statement,
)


class OrdinaryRelationTests(unittest.TestCase):
    def test_all_twenty_five_directed_relations(self):
        # Explicit expected matrix, rows SOURCE and columns TARGET 木火土金水.
        expected = {
            "木": ("same", "generates", "controls", "is_controlled_by", "is_generated_by"),
            "火": ("is_generated_by", "same", "generates", "controls", "is_controlled_by"),
            "土": ("is_controlled_by", "is_generated_by", "same", "generates", "controls"),
            "金": ("controls", "is_controlled_by", "is_generated_by", "same", "generates"),
            "水": ("generates", "controls", "is_controlled_by", "is_generated_by", "same"),
        }
        for source, results in expected.items():
            for target, relation in zip("木火土金水", results):
                with self.subTest(source=source, target=target):
                    self.assertEqual(ordinary_relation(source, target), relation)

    def test_invalid_elements_are_rejected(self):
        for bad in ("", "火星", "water", None, [], 1):
            for pair in ((bad, "木"), ("木", bad)):
                with self.subTest(pair=pair), self.assertRaises(ValueError):
                    ordinary_relation(*pair)

    def test_all_twenty_five_statements_name_actual_direction(self):
        # Explicit active-direction matrix; do not derive the expectations from
        # the implementation or from ordinary_relation.
        expected = {
            "木": ("同", "正生", "正克", "反克", "反生"),
            "火": ("反生", "同", "正生", "正克", "反克"),
            "土": ("反克", "反生", "同", "正生", "正克"),
            "金": ("正克", "反克", "反生", "同", "正生"),
            "水": ("正生", "正克", "反克", "反生", "同"),
        }
        for source, results in expected.items():
            for target, direction in zip("木火土金水", results):
                a, b = f"日支（{source}）", f"二爻（{target}）"
                statements = {
                    "同": f"{a}与{b}同属{source}",
                    "正生": f"{a}生{b}", "反生": f"{b}生{a}",
                    "正克": f"{a}克{b}", "反克": f"{b}克{a}",
                }
                with self.subTest(source=source, target=target):
                    statement = relation_statement(a, source, b, target)
                    self.assertEqual(statement, statements[direction])
                    reverse = relation_statement(b, target, a, source)
                    # Reversing the query cannot reverse the underlying action.
                    if source != target:
                        self.assertEqual(reverse, statement)
                    else:
                        self.assertEqual(reverse, f"{b}与{a}同属{target}")
                    self.assertNotIn("源", statement)
                    self.assertNotIn("目标", statement)

    def test_statements_reject_missing_names_and_invalid_elements(self):
        for bad in ("", "  ", None, [], 1):
            with self.subTest(name=bad):
                with self.assertRaises(ValueError):
                    relation_statement(bad, "土", "本卦第2爻寅木", "木")
                with self.assertRaises(ValueError):
                    relation_statement("日支未土", "土", bad, "木")
        with self.assertRaises(ValueError):
            relation_statement("日支未土", "坏", "本卦第2爻寅木", "木")


class RelationFactsTests(unittest.TestCase):
    def setUp(self):
        self.qian = base_chart.calculate_base_chart(["young_yang"] * 6)

    def facts(self, chart=None):
        return {f["fact_id"]: f for f in build_relation_facts(chart or self.qian)}

    def test_qian_structure_and_absent_gua_body(self):
        facts = self.facts()
        self.assertEqual(len(facts), 34)
        self.assertEqual(facts["REL_LINE_1_TO_2"]["value"], "generates")
        self.assertEqual(facts["REL_LINE_2_TO_1"]["value"], "is_generated_by")
        self.assertEqual(facts["REL_YING_TO_SHI"]["value"], "same")
        self.assertEqual(facts["REL_YING_TO_SHI"]["subject"], "应（本卦第3爻辰土） → 世（本卦第6爻戌土）")
        self.assertEqual(facts["REL_GUA_BODY_TO_SHI_BODY"]["value"], "controls")
        self.assertEqual(facts["REL_GUA_BODY_TO_SHI_BODY"]["subject"], "卦身（位：巳火；本卦未现） → 世身（身：本卦第5爻申金）")
        self.assertIs(facts["REL_GUA_BODY_PRESENT"]["value"], False)
        for key in ("REL_YING_TO_SHI", "REL_GUA_BODY_TO_SHI_BODY"):
            self.assertEqual(facts[key]["source_rule_id"], "relation.ordinary_wuxing")
            self.assertIn("未判有效作用", facts[key]["predicate"])

    def test_sixty_four_base_charts_have_exactly_thirty_directed_pairs(self):
        for bits in itertools.product((0, 1), repeat=6):
            chart = base_chart.calculate_base_chart(["young_yang" if b else "young_yin" for b in bits])
            with self.subTest(bits=bits):
                facts = self.facts(chart)
                pairs = {key for key in facts if key.startswith("REL_LINE_")}
                self.assertEqual(pairs, {f"REL_LINE_{a}_TO_{b}" for a in range(1, 7) for b in range(1, 7) if a != b})
                self.assertEqual(len(facts), 34)
                self.assertEqual(facts["REL_GUA_BODY_PRESENT"]["value"], bool(chart["gua_body_positions"]))
                for fact in facts.values():
                    self.assertEqual(set(fact), {"fact_id", "kind", "subject", "predicate", "value", "source_rule_id"})
                    self.assertNotIsInstance(fact["value"], (dict, list))

    def test_preserves_input_and_does_not_infer_changed_roles(self):
        chart = base_chart.calculate_base_chart(["old_yang"] * 6)
        before = copy.deepcopy(chart)
        facts = build_relation_facts(chart)
        self.assertEqual(chart, before)
        # Identical main-chart matrix, regardless of motion or changed structure.
        self.assertEqual(facts, build_relation_facts(self.qian))
        self.assertFalse(any("CHANGED" in f["fact_id"] for f in facts))

    def test_computed_calendar_adds_twelve_directed_day_month_relations(self):
        chart = copy.deepcopy(self.qian)
        chart["calendar"] = {"status": "computed", "pillars": {"day": "甲子", "month": "丙寅"}}
        facts = self.facts(chart)
        self.assertEqual(len(facts), 46)
        self.assertEqual(facts["CAL_DAY_TO_LINE_2"]["value"], "generates")  # 子水 -> 寅木
        self.assertEqual(facts["CAL_DAY_TO_LINE_2"]["subject"], "日支子水 → 本卦第2爻寅木")
        self.assertEqual(facts["CAL_MONTH_TO_LINE_3"]["value"], "controls")  # 寅木 -> 辰土
        self.assertEqual(facts["CAL_MONTH_TO_LINE_3"]["subject"], "月支寅木 → 本卦第3爻辰土")
        self.assertFalse(any("STRENGTH" in f for f in facts))

    def test_day_wei_earth_does_not_control_yin_wood_but_month_you_metal_does(self):
        chart = copy.deepcopy(self.qian)
        chart["calendar"] = {"status": "computed", "pillars": {"day": "辛未", "month": "丁酉"}}
        facts = self.facts(chart)
        day, month = facts["CAL_DAY_TO_LINE_2"], facts["CAL_MONTH_TO_LINE_2"]
        self.assertEqual(len(facts), 46)
        self.assertEqual(day["subject"], "日支未土 → 本卦第2爻寅木")
        self.assertEqual(day["value"], "is_controlled_by")
        self.assertEqual(day["predicate"], "凡五行：本卦第2爻寅木克日支未土；仅结构分类，未判有效作用")
        self.assertEqual(month["subject"], "月支酉金 → 本卦第2爻寅木")
        self.assertEqual(month["value"], "controls")
        self.assertEqual(month["predicate"], "凡五行：月支酉金克本卦第2爻寅木；仅结构分类，未判有效作用")
        for fact in (day, month):
            self.assertEqual(fact["source_rule_id"], "relation.ordinary_wuxing")
            self.assertNotIn("旺", fact["predicate"])
            self.assertNotIn("吉", fact["predicate"])

    def test_incomplete_calendar_does_not_invent_day_or_month(self):
        for calendar in (None, {}, {"status": "missing"}, {"status": "unsupported"}):
            chart = copy.deepcopy(self.qian)
            chart["calendar"] = calendar
            with self.subTest(calendar=calendar):
                self.assertEqual(len(build_relation_facts(chart)), 34)
                self.assertFalse(any(f["fact_id"].startswith("CAL_") for f in build_relation_facts(chart)))

    def test_invalid_chart_or_computed_calendar_is_rejected(self):
        for mutate in (
            lambda c: c["main"]["lines"][0].update(element="土"),
            lambda c: c["main"]["lines"][0].update(position=2),
            lambda c: c.update(shi_position=True),
            lambda c: c.update(gua_body_positions=[1]),
            lambda c: c.update(calendar={"status": "computed", "pillars": {"day": "坏", "month": "丙寅"}}),
        ):
            chart = copy.deepcopy(self.qian)
            mutate(chart)
            with self.assertRaises(ValueError):
                build_relation_facts(chart)


if __name__ == "__main__":
    unittest.main()
