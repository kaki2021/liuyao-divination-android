"""Foundation checks verify explicit structures, not divination accuracy."""
import copy
import itertools
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import base_chart
import branch_relations
from liuyao_app.basic_analysis import build_basic_analysis, SIX_COMBINATIONS
from liuyao_app.interpretation_evidence import build_relation_facts


def chart_for(bits, moving=()):
    return base_chart.calculate_base_chart([
        ("old_yang" if bit else "old_yin") if position in moving
        else ("young_yang" if bit else "young_yin")
        for position, bit in enumerate(bits, 1)])


def sections(result):
    return {section["id"]: {item["id"]: item for item in section["items"]}
            for section in result["sections"]}


class BasicAnalysisTests(unittest.TestCase):
    def test_sixty_four_charts_static_and_each_motion_keep_unique_bounded_scalar_facts(self):
        seen_stages = set()
        for bits in itertools.product((0, 1), repeat=6):
            for moving in ((), (1,), (2,), (3,), (4,), (5,), (6,), (1, 2, 3, 4, 5, 6)):
                with self.subTest(bits=bits, moving=moving):
                    chart = chart_for(bits, moving)
                    before = copy.deepcopy(chart)
                    result = build_basic_analysis(chart)
                    facts = result["facts"]
                    ids = [fact["fact_id"] for fact in facts]
                    self.assertEqual(chart, before)
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertLessEqual(len(facts), 63)
                    self.assertEqual(len([key for key in ids if key.startswith("REL_LINE_")]), 30)
                    self.assertNotIn("SHI_POSITION", ids)
                    self.assertNotIn("GUA_BODY", ids)
                    self.assertEqual("CHANGED_CHART_PALACE_STAGE" in ids, bool(moving))
                    for fact in facts:
                        self.assertEqual(set(fact), {"fact_id", "kind", "subject", "predicate", "value", "source_rule_id"})
                        self.assertNotIsInstance(fact["value"], (dict, list))
                    ui = sections(result)
                    self.assertEqual(len([i for i in ui["line_relations"] if i.startswith("line_pair_")]), 15)
                    stage = next(f for f in facts if f["fact_id"] == "CHART_PALACE_STAGE")["value"]
                    self.assertIn("卦序为" + stage, ui["overview"]["palace"]["text"])
                    seen_stages.add(stage)
        self.assertEqual(seen_stages, {"本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"})

    def test_qian_absent_body_and_actual_direction_are_not_truncated(self):
        result = build_basic_analysis(chart_for([1] * 6))
        ui = sections(result)
        self.assertIn("乾宫，宫五行为土", ui["overview"]["palace"]["text"])
        self.assertIn("静卦", ui["overview"]["dynamics"]["text"])
        self.assertIn("本卦未见对应地支", ui["references"]["body_positions"]["text"])
        self.assertEqual(ui["references"]["body_relation"]["text"],
                         "卦身（位：巳火；本卦未现）克世身（身：本卦第5爻申金）。")
        self.assertEqual(ui["line_relations"]["line_pair_2_5"]["text"], "本卦第5爻申金克本卦第2爻寅木。")

    def test_calendar_values_match_ui_and_ai_without_reversing_soil_and_wood(self):
        chart = chart_for([1] * 6)
        chart["calendar"] = {"status": "computed", "pillars": {"month": "丁酉", "day": "辛未"}}
        result = build_basic_analysis(chart)
        ui = sections(result)
        facts = {f["fact_id"]: f for f in result["facts"]}
        self.assertEqual(facts["CAL_DAY_TO_LINE_2"]["value"], "is_controlled_by")
        self.assertEqual(facts["CAL_MONTH_TO_LINE_2"]["value"], "controls")
        self.assertEqual(ui["calendar"]["calendar_line_2"]["text"],
                         "第2爻寅木：月令分类为死；月支酉金克本卦第2爻寅木；本卦第2爻寅木克日支未土。")
        self.assertIn("不表示人物死亡", ui["calendar"]["calendar_scope"]["text"])
        self.assertEqual(len([f for f in facts if f.startswith("CAL_")]), 12)

    def test_all_sixty_four_dated_charts_preserve_all_directional_facts(self):
        for bits in itertools.product((0, 1), repeat=6):
            chart = chart_for(bits, (2,))
            chart["calendar"] = {"status": "computed", "pillars": {"month": "丙寅", "day": "甲子"}}
            with self.subTest(bits=bits):
                foundation = build_basic_analysis(chart)
                original = build_relation_facts(chart)
                self.assertEqual(foundation["facts"][:len(original)], original)
                self.assertLessEqual(len(foundation["facts"]), 63)

    def test_missing_historical_calendar_is_not_invented(self):
        for calendar in (None, {}, {"status": "missing"}, {"status": "unsupported"}):
            chart = chart_for([0] * 6)
            chart["calendar"] = calendar
            with self.subTest(calendar=calendar):
                result = build_basic_analysis(chart)
                self.assertFalse(any(f["fact_id"].startswith("CAL_") for f in result["facts"]))
                self.assertEqual(set(sections(result)["calendar"]), {"calendar_unavailable"})

    def test_calendar_category_disagreement_is_rejected(self):
        chart = chart_for([1] * 6)
        chart["calendar"] = {"status": "computed", "pillars": {"month": "丁酉", "day": "辛未"}}
        chart["main"]["lines"][1]["ordinary_month_strength"] = "旺"
        with self.assertRaisesRegex(ValueError, "Recorded month category"):
            build_basic_analysis(chart)

    def test_six_combination_table_exact_and_all_other_pairs_absent(self):
        # Explicit pairs from core B1278–B1279, including 午未土 rather than 火.
        expected = {"子丑": "土", "寅亥": "木", "卯戌": "火", "辰酉": "金", "巳申": "水", "午未": "土"}
        self.assertEqual(len(SIX_COMBINATIONS), 6)
        for left in "子丑寅卯辰巳午未申酉戌亥":
            for right in "子丑寅卯辰巳午未申酉戌亥":
                label = left + right
                self.assertEqual(SIX_COMBINATIONS.get(frozenset(label)), expected.get(label, expected.get(label[::-1])))

    def test_concrete_combination_fixtures_retain_nominal_element_and_original_branches(self):
        fixtures = [
            ([0, 0, 0, 0, 0, 1], "PAIR_3_4_SIX_COMBINATION", "火"),  # 卯戌
            ([0, 0, 0, 0, 1, 0], "PAIR_2_4_SIX_COMBINATION", "水"),  # 巳申
            ([0, 0, 0, 1, 0, 0], "PAIR_1_4_SIX_COMBINATION", "土"),  # 午未
            ([0, 0, 1, 0, 0, 0], "PAIR_1_6_SIX_COMBINATION", "金"),  # 辰酉
            ([0, 1, 0, 0, 0, 0], "PAIR_1_5_SIX_COMBINATION", "木"),  # 寅亥
        ]
        for bits, fact_id, element in fixtures:
            chart = chart_for(bits)
            before = copy.deepcopy(chart)
            result = build_basic_analysis(chart)
            fact = next(f for f in result["facts"] if f["fact_id"] == fact_id)
            self.assertEqual(fact["value"], element)
            self.assertEqual(fact["predicate"], "六合名义化行（未判成化）")
            self.assertEqual(chart, before)
        no_match = build_basic_analysis(chart_for([0, 0, 1, 0, 0, 0]))
        # 地山谦四爻丑、五爻亥 are not a combination pair.
        self.assertNotIn("PAIR_4_5_SIX_COMBINATION", [f["fact_id"] for f in no_match["facts"]])

    def test_no_false_combinations_and_all_six_pairs_found_across_64_charts(self):
        expected = {frozenset(pair): value for pair, value in (
            ("子丑", "土"), ("寅亥", "木"), ("卯戌", "火"), ("辰酉", "金"), ("巳申", "水"), ("午未", "土"))}
        found = set()
        for bits in itertools.product((0, 1), repeat=6):
            chart = chart_for(bits)
            actual = {f["fact_id"]: f["value"] for f in build_basic_analysis(chart)["facts"]
                      if f["fact_id"].endswith("_SIX_COMBINATION")}
            required = {}
            for a, b in itertools.combinations(chart["main"]["lines"], 2):
                pair = frozenset((a["branch"], b["branch"]))
                if pair in expected:
                    required[f"PAIR_{a['position']}_{b['position']}_SIX_COMBINATION"] = expected[pair]
                    found.add(pair)
            self.assertEqual(actual, required)
        self.assertEqual(found, set(expected))

    def test_form_and_harm_overlap_is_preserved_and_chart_pairs_reused(self):
        # 山地剥: second line 巳 and sixth line 寅 carry both labels.
        chart = chart_for([0, 0, 0, 0, 0, 1])
        pairs = []
        for left, right in itertools.combinations(chart["main"]["lines"], 2):
            classified = branch_relations.classify_pair(left["branch"], right["branch"])
            if classified["relations"]:
                pairs.append({"positions": [left["position"], right["position"]], **classified})
        raw = build_basic_analysis(chart)
        chart["line_pair_relations"] = pairs
        reused = build_basic_analysis(chart)
        self.assertEqual(raw, reused)
        matching = [item["text"] for item in sections(raw)["branch_relations"].values()
                    if "互形（无恩之形）" in item["text"] and "互害（恩间）" in item["text"]]
        self.assertTrue(matching)

    def test_all_rule_references_exist_in_core_catalog(self):
        catalog = json.loads((Path(__file__).resolve().parents[1] / "software_prep" / "rule_catalog.json").read_text())
        rules = {r["rule_id"] for r in catalog["rules"]}
        for bits in itertools.product((0, 1), repeat=6):
            result = build_basic_analysis(chart_for(bits))
            for section in result["sections"]:
                for item in section["items"]:
                    self.assertLessEqual(set(item["rule_ids"]), rules)
            self.assertLessEqual({f["source_rule_id"] for f in result["facts"]}, rules)


if __name__ == "__main__":
    unittest.main()
