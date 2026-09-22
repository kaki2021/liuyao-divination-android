"""Pinned upstream fixtures plus the adapter's timezone/boundary contract."""
import copy
import unittest

from .calendar_context import calculate_calendar
from ._vendor.lunar_python import Solar
from software_prep.base_chart import calculate_base_chart


def calendar(value):
    return calculate_calendar({"actual_cast_time": value})


class CalendarContextTests(unittest.TestCase):
    def test_upstream_four_pillar_fixtures(self):
        # https://github.com/6tail/lunar-python/blob/master/test/EightCharTest.py
        # getYear/getMonth/getDay/getTime fixtures: test_gan_zhi, test7, test10,
        # and forward checks of the dates in test15/test16/test17/test18.
        fixtures = [
            ("2005-12-23T08:37:00+08:00", ["乙酉", "戊子", "辛巳", "壬辰"]),
            ("2022-08-28T01:50:00+08:00", ["壬寅", "戊申", "癸丑", "癸丑"]),
            ("1988-02-15T23:30:00+08:00", ["戊辰", "甲寅", "庚子", "戊子"]),
            ("1901-01-01T12:00:00+08:00", ["庚子", "戊子", "己卯", "庚午"]),
            ("1960-12-17T12:00:00+08:00", ["庚子", "戊子", "己卯", "庚午"]),
            ("2023-02-24T23:00:00+08:00", ["癸卯", "甲寅", "癸丑", "甲子"]),
            ("1900-01-29T16:00:00+08:00", ["己亥", "丁丑", "壬寅", "戊申"]),
            ("1959-12-17T16:00:00+08:00", ["己亥", "丙子", "癸酉", "庚申"]),
        ]
        for instant, expected in fixtures:
            with self.subTest(instant=instant):
                result = calendar(instant)
                self.assertEqual("computed", result["status"])
                self.assertEqual(expected, list(result["pillars"].values()))
                self.assertEqual(expected[2][0], result["day_stem"])

    def test_no_time_is_not_substituted_by_entry_time(self):
        for absent in ({}, {"actual_cast_time": None}, {"actual_cast_time": ""},
                       {"created_at": "2026-09-17T18:42:00+08:00"}):
            result = calculate_calendar(absent)
            self.assertEqual("missing", result["status"])
            self.assertIsNone(result["cast_time"])
            self.assertIsNone(result["day_stem"])
            self.assertTrue(all(value is None for value in result["pillars"].values()))

    def test_malformed_input_never_invents_pillars(self):
        for value in ["2026-09-17", "2026-09-17T12:00:00", "2026-02-30T10:00:00Z",
                      "2026-09-17T10:00:00+00:99", "2026-09-17T25:00:00Z", [], 42]:
            with self.subTest(value=value):
                result = calendar(value)
                self.assertEqual("error", result["status"])
                self.assertIsNone(result["day_stem"])
        self.assertEqual("error", calculate_calendar(None)["status"])

    def test_equal_instants_convert_to_same_beijing_chart(self):
        values = ["2005-12-23T08:37:00+08:00", "2005-12-23T00:37:00Z",
                  "2005-12-22T19:37:00-05:00", "2005-12-23T04:37:00+04:00"]
        results = [calendar(value) for value in values]
        for value, result in zip(values, results):
            self.assertEqual(results[0]["pillars"], result["pillars"])
            self.assertEqual("2005-12-23T08:37:00+08:00", result["cast_time"])
            self.assertEqual(value, result["source_cast_time"])
        self.assertFalse(results[0]["timezone_converted"])
        self.assertTrue(results[1]["timezone_converted"])
        self.assertEqual("-05:00", results[2]["source_utc_offset"])

    def test_utc_rollover_uses_converted_calendar_day(self):
        before = calendar("1988-02-15T15:59:59Z")
        after = calendar("1988-02-15T16:00:00Z")
        self.assertEqual("庚子", before["pillars"]["day"])
        self.assertEqual("辛丑", after["pillars"]["day"])

    def test_late_zi_keeps_day_but_hour_uses_next_day(self):
        before = calendar("1988-02-15T22:59:59+08:00")
        late = calendar("1988-02-15T23:00:00+08:00")
        late_end = calendar("1988-02-15T23:59:59+08:00")
        next_day = calendar("1988-02-16T00:00:00+08:00")
        self.assertEqual(["庚子", "庚子", "庚子", "辛丑"],
                         [item["pillars"]["day"] for item in (before, late, late_end, next_day)])
        self.assertEqual(["丁亥", "戊子", "戊子", "戊子"],
                         [item["pillars"]["hour"] for item in (before, late, late_end, next_day)])

    def test_six_spirits_follow_displayed_day_not_late_zi_hour_day(self):
        # 2023-02-24 is 癸丑; at 23:00 time becomes 甲子 but the spirits must
        # still start with 癸-day 玄武, not next-day 甲-day 青龙.
        instant = calendar("2023-02-24T23:00:00+08:00")
        chart = calculate_base_chart(["young_yang"] * 6, verified_day_stem=instant["day_stem"])
        self.assertEqual("癸", instant["day_stem"])
        self.assertEqual(["玄武", "青龙", "朱雀", "勾陈", "腾蛇", "白虎"],
                         [line["six_spirit"] for line in chart["main"]["lines"]])
        tomorrow = calendar("2023-02-25T00:00:00+08:00")
        next_chart = calculate_base_chart(["young_yang"] * 6, verified_day_stem=tomorrow["day_stem"])
        self.assertEqual("青龙", next_chart["main"]["lines"][0]["six_spirit"])

    def test_upstream_exact_month_fixture(self):
        # Upstream LunarTest.test28/29: 寒露日零点尚未交节，月支仍酉。
        self.assertEqual("乙酉", calendar("1990-10-08T00:00:00+08:00")["pillars"]["month"])
        self.assertEqual("丙戌", calendar("1990-10-09T00:00:00+08:00")["pillars"]["month"])

    def test_upstream_term_second_boundary(self):
        # Upstream JieQiTest.test7 pins 白露 to this second.
        term = Solar.fromYmdHms(2012, 9, 10, 12, 0, 0).getLunar().getJieQiTable()["白露"]
        self.assertEqual("2012-09-07 13:29:01", term.toYmdHms())
        before = calendar("2012-09-07T13:29:00+08:00")
        after = calendar("2012-09-07T13:29:01+08:00")
        self.assertEqual("戊申", before["pillars"]["month"])
        self.assertEqual("己酉", after["pillars"]["month"])

    def test_lichun_changes_year_and_month_at_same_second(self):
        # Boundary supplied by the pinned library. 2024-02-04 date also agrees
        # with Hong Kong Observatory's 2024 calendar, not Lunar New Year's Day.
        before = calendar("2024-02-04T16:27:06+08:00")
        after = calendar("2024-02-04T16:27:07+08:00")
        self.assertEqual(["癸卯", "乙丑"], [before["pillars"]["year"], before["pillars"]["month"]])
        self.assertEqual(["甲辰", "丙寅"], [after["pillars"]["year"], after["pillars"]["month"]])
        self.assertEqual(before["pillars"]["day"], after["pillars"]["day"])

    def test_supported_range_is_checked_after_conversion(self):
        for instant in ["1899-12-31T23:59:59+08:00", "2101-01-01T00:00:00+08:00"]:
            self.assertEqual("CAST_TIME_OUT_OF_RANGE", calendar(instant)["code"])
        for instant in ["1899-12-31T16:00:00Z", "2100-12-31T23:59:59+08:00"]:
            self.assertEqual("computed", calendar(instant)["status"])

    def test_fractional_input_and_policy_are_frozen_without_mutating_input(self):
        supplied = {"actual_cast_time": "2026-09-17T10:42:00.125Z", "question": "明天是否顺利"}
        original = copy.deepcopy(supplied)
        result = calculate_calendar(supplied)
        self.assertEqual(original, supplied)
        self.assertEqual("2026-09-17T18:42:00.125000+08:00", result["cast_time"])
        self.assertEqual("software_calendar_convention", result["calculation_policy"]["authority"])
        self.assertEqual(2, result["calculation_policy"]["library_eight_char_sect"])
        self.assertEqual("1.4.8", result["calendar_library"]["version"])
        result["calculation_policy"]["supported_beijing_years"][0] = 1
        self.assertEqual([1900, 2100], calculate_calendar(supplied)["calculation_policy"]["supported_beijing_years"])


if __name__ == "__main__":
    unittest.main()
