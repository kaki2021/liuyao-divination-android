"""Anonymous regressions for visibility, mixed notes and calendar availability."""
from copy import deepcopy
import unittest

from liuyao_app.selection_context import build_information_scope, review_selection_notes


TIME = "2026-08-12T09:20:00+08:00"


def inputs():
    return {"question": "下个月是否能签下合同？", "actual_cast_time": TIME}


def chart():
    return {
        "calendar": {"status": "computed", "source_cast_time": TIME,
                     "pillars": {"year": "丙午", "month": "丙申", "day": "戊午", "hour": "丁巳"}},
        "main": {"lines": [{"position": 1, "relative_code": "parents"},
                           {"position": 2, "relative_code": "siblings"}]},
    }


def selection(*notes):
    return {
        "candidates": [{"candidate_id": "main", "purpose": "primary", "six_relative": "parents"}],
        "selected_primary_id": "main", "unresolved": list(notes),
    }


class SelectionContextTests(unittest.TestCase):
    def test_scope_exposes_only_availability_not_values_or_strength(self):
        scope = build_information_scope(inputs(), chart())
        self.assertEqual(scope, {
            "actual_cast_time_provided": True, "calendar_status": "computed",
            "month_context_available": True, "day_context_available": True,
            "chart_values_in_this_stage": False,
        })
        self.assertNotIn(TIME, str(scope))
        self.assertNotIn("丙申", str(scope))
        self.assertNotIn("parents", str(scope))

    def test_missing_actual_time_never_uses_event_date_or_recorded_time(self):
        data = {"question": "8月12日是否签约？", "recorded_at": TIME, "event_time": TIME}
        current = {"calendar": {"status": "missing"}}
        scope = build_information_scope(data, current)
        self.assertFalse(scope["actual_cast_time_provided"])
        self.assertFalse(scope["month_context_available"])
        note = review_selection_notes(selection("起卦日期未提供。"), data, current)[0]
        self.assertIn("实际起卦时间字段未填写", note["review_text"])

    def test_provided_but_uncomputed_date_is_not_absence(self):
        current = {"calendar": {"status": "error", "source_cast_time": TIME}}
        row = review_selection_notes(selection("没有起卦时间。"), inputs(), current)[0]
        self.assertIn("已填写", row["review_text"])
        self.assertIn("未完整可用", row["review_text"])
        self.assertNotIn("并已计算", row["review_text"])

    def test_computed_calendar_bound_to_another_time_is_not_used(self):
        current = chart()
        current["calendar"]["source_cast_time"] = "2025-01-01T00:00:00Z"
        scope = build_information_scope(inputs(), current)
        self.assertEqual(scope["calendar_status"], "error")
        self.assertFalse(scope["month_context_available"])
        self.assertFalse(scope["day_context_available"])

    def test_no_synthetic_time_from_unbound_computed_calendar(self):
        scope = build_information_scope({}, chart())
        self.assertFalse(scope["actual_cast_time_provided"])
        self.assertEqual(scope["calendar_status"], "error")
        self.assertFalse(scope["day_context_available"])

    def test_month_and_day_availability_separate(self):
        current = chart()
        current["calendar"]["pillars"]["day"] = None
        scope = build_information_scope(inputs(), current)
        self.assertTrue(scope["month_context_available"])
        self.assertFalse(scope["day_context_available"])

    def test_compound_note_keeps_age_and_rules_and_marks_partial(self):
        original = "起卦日期、年龄与综合旺衰算法没有提供，暂不能确定精确应期。"
        row = review_selection_notes(selection(original), inputs(), chart())[0]
        self.assertEqual(row["original_text"], original)
        self.assertIn(original, row["review_text"])
        self.assertIn("已计算月、日历法信息", row["review_text"])
        self.assertIn("原文其余背景、功能假设及规则疑问仍需逐项核对", row["review_text"])
        self.assertEqual(row["status"], "partially_clarified")

    def test_event_date_not_reclassified_as_cast_date(self):
        original = "签约日期未明确，审批时间仍需确认。"
        row = review_selection_notes(selection(original), inputs(), chart())[0]
        self.assertEqual(row["status"], "needs_review")
        self.assertNotIn("系统复核", row["review_text"])
        self.assertIn(original, row["review_text"])

    def test_vague_strength_note_not_treated_as_missing_calendar(self):
        row = review_selection_notes(selection("综合旺衰算法未核定。"), inputs(), chart())[0]
        self.assertEqual(row["status"], "needs_review")
        self.assertNotIn("已计算", row["review_text"])

    def test_unique_relative_clarifies_position_without_validating_use_line(self):
        row = review_selection_notes(selection("主功能已选，但父母爻的具体匹配位置待排盘。"), inputs(), chart())[0]
        self.assertEqual(row["status"], "partially_clarified")
        self.assertIn("结构匹配只有第1爻", row["review_text"])
        self.assertIn("不等于已验证该功能假设或已确定唯一有效用神", row["review_text"])

    def test_multiple_or_absent_relative_not_silently_resolved(self):
        for lines in ([], [{"position": 1, "relative_code": "parents"},
                           {"position": 2, "relative_code": "parents"}]):
            with self.subTest(lines=lines):
                current = chart()
                current["main"]["lines"] = lines
                row = review_selection_notes(selection("父母爻定位待确认。"), inputs(), current)[0]
                self.assertEqual(row["status"], "needs_review")

    def test_subject_reference_not_treated_as_kinship_candidate(self):
        chosen = selection("主用神爻位待确认。")
        chosen["candidates"][0]["subject_reference"] = "shi"
        row = review_selection_notes(chosen, inputs(), chart())[0]
        self.assertEqual(row["status"], "needs_review")

    def test_auxiliary_kinship_note_not_resolved_by_main_match(self):
        row = review_selection_notes(selection("官鬼爻有多个位置，需要匹配。"), inputs(), chart())[0]
        self.assertEqual(row["status"], "needs_review")
        self.assertNotIn("结构匹配", row["review_text"])

    def test_unknown_functional_background_is_retained_as_unverified_note(self):
        original = "审批方的立场和职责未明确，可能影响辅助功能的取舍。"
        row = review_selection_notes(selection(original), inputs(), chart())[0]
        self.assertEqual(row["status"], "needs_review")
        self.assertIn("不是系统已确认的信息缺失", row["review_text"])
        self.assertIn(original, row["review_text"])

    def test_inputs_and_history_not_modified(self):
        data, current = inputs(), chart()
        chosen = selection("起卦日期未提供，父母爻匹配尚待核对。", "年龄未提供。")
        originals = deepcopy((chosen, data, current))
        rows = review_selection_notes(chosen, data, current)
        self.assertEqual((chosen, data, current), originals)
        self.assertEqual([r["index"] for r in rows], [0, 1])
        self.assertEqual([r["original_text"] for r in rows], chosen["unresolved"])


if __name__ == "__main__":
    unittest.main()
