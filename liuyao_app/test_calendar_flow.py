"""Real HTTP/calendar/storage/demo integration, with no remote model call."""
import copy
import unittest

from . import test_app_flow as app_flow


class CalendarHTTPFlow(unittest.TestCase):
    # Reuse the HTTP harness only; do not inherit/discover its application tests.
    setUp = app_flow.FullAppFlow.setUp
    tearDown = app_flow.FullAppFlow.tearDown
    request = app_flow.FullAppFlow.request
    api = app_flow.FullAppFlow.api
    analyze_demo = app_flow.FullAppFlow.analyze_demo

    @staticmethod
    def supplied(instant="2023-02-24T23:00:00+08:00"):
        return {"question": "明天出行是否顺利？", "actual_cast_time": instant,
                "casting": {"method": "meibu", "results": ["1", "5", "5"]}}

    @staticmethod
    def spirits(chart):
        return [line["six_spirit"] for line in chart["main"]["lines"]]

    def test_save_and_reopen_return_calendar_and_six_spirits(self):
        supplied = self.supplied()
        created = self.api("POST", "/api/cases", {"input": supplied}, 201)
        chart = created["chart"]
        self.assertEqual("computed", chart["calendar"]["status"])
        self.assertEqual({"year": "癸卯", "month": "甲寅", "day": "癸丑", "hour": "甲子"},
                         chart["calendar"]["pillars"])
        self.assertEqual(["玄武", "青龙", "朱雀", "勾陈", "腾蛇", "白虎"], self.spirits(chart))
        self.assertEqual("computed_from_verified_stem", chart["six_spirits_status"])
        reopened = self.api("GET", "/api/cases/" + created["case_id"])
        self.assertEqual(chart, reopened["chart"])
        self.assertEqual(supplied["actual_cast_time"], reopened["case"]["original_input"]["actual_cast_time"])

    def test_demo_freezes_actual_instant_policy_and_calendar(self):
        supplied = self.supplied("2023-02-24T15:00:00Z")
        created = self.api("POST", "/api/cases", {"input": supplied}, 201)
        job = self.analyze_demo(created["case_id"])
        exported = self.api("GET", "/api/cases/" + created["case_id"] + "/export")
        run = exported["analysis_runs"][0]
        frozen = run["outcome"]["result"]["chart_snapshot"]
        self.assertEqual(created["chart"], frozen)
        self.assertEqual(frozen, job["result"]["chart"])
        self.assertEqual(supplied["actual_cast_time"], run["input_snapshot"]["input"]["actual_cast_time"])
        self.assertEqual("2023-02-24T23:00:00+08:00", frozen["calendar"]["cast_time"])
        self.assertTrue(frozen["calendar"]["timezone_converted"])
        self.assertEqual(2, frozen["calendar"]["calculation_policy"]["library_eight_char_sect"])
        self.assertEqual("1.4.8", frozen["calendar"]["calendar_library"]["version"])
        self.assertEqual([], run["ai_events"])

    def test_time_correction_changes_current_chart_but_not_old_analysis(self):
        original = self.supplied()
        created = self.api("POST", "/api/cases", {"input": original}, 201)
        case_id = created["case_id"]
        self.analyze_demo(case_id)
        before = self.api("GET", f"/api/cases/{case_id}/export")
        old_run = copy.deepcopy(before["analysis_runs"][0])
        old_chart = old_run["outcome"]["result"]["chart_snapshot"]
        corrected = self.supplied("2023-02-25T00:30:00+08:00")
        self.api("POST", f"/api/cases/{case_id}/revisions", {
            "input": corrected, "reason": "按实际记录更正为次日凌晨起卦", "expected_revision_seq": 1}, 201)
        detail = self.api("GET", f"/api/cases/{case_id}")
        self.assertFalse(detail["report_is_current"])
        self.assertEqual("甲寅", detail["chart"]["calendar"]["pillars"]["day"])
        self.assertEqual("青龙", self.spirits(detail["chart"])[0])
        self.assertNotEqual(old_chart["calendar"]["pillars"], detail["chart"]["calendar"]["pillars"])
        self.assertNotEqual(self.spirits(old_chart), self.spirits(detail["chart"]))
        self.assertEqual(old_run, detail["case"]["analysis_runs"][0])
        self.assertEqual(old_chart, detail["result"]["chart"])
        self.analyze_demo(case_id, revision=2)
        after = self.api("GET", f"/api/cases/{case_id}/export")
        self.assertEqual(old_run, after["analysis_runs"][0])
        self.assertEqual("癸丑", after["analysis_runs"][0]["outcome"]["result"]["chart_snapshot"]["calendar"]["pillars"]["day"])
        second_chart = after["analysis_runs"][1]["outcome"]["result"]["chart_snapshot"]
        self.assertEqual(detail["chart"], second_chart)
        self.assertEqual("青龙", self.spirits(second_chart)[0])

    def test_missing_time_remains_missing_in_http_and_demo_snapshot(self):
        supplied = self.supplied()
        del supplied["actual_cast_time"]
        created = self.api("POST", "/api/cases", {"input": supplied}, 201)
        self.assertEqual("missing", created["chart"]["calendar"]["status"])
        self.assertEqual([None] * 6, self.spirits(created["chart"]))
        job = self.analyze_demo(created["case_id"])
        frozen = job["result"]["chart"]
        self.assertIsNone(frozen["calendar"]["cast_time"])
        self.assertIsNone(frozen["calendar"]["day_stem"])
        self.assertEqual([None] * 6, self.spirits(frozen))


if __name__ == "__main__":
    unittest.main()
