"""Calendar facts for an explicitly supplied casting instant.

This adapter's calendar policy is an engineering choice, not an assertion that
the divination source texts specified these civil-time boundaries. It uses only
calendar conversion from the vendored library, never its fortune/timing APIs.
"""
from datetime import datetime, timedelta, timezone
import re

from ._vendor.lunar_python import Solar


BEIJING_STANDARD_TIME = timezone(timedelta(hours=8))
LIBRARY_INFO = {
    "name": "lunar_python", "version": "1.4.8", "license": "MIT",
    "source": "https://github.com/6tail/lunar-python",
    "distribution_sha256": "3aa11cc73c25e70ddf0ba5bdac7398c03acc9491a3aa512a91c9642973b669d6",
    "vendored_path": "liuyao_app/_vendor/lunar_python",
}
CALCULATION_POLICY = {
    "policy_id": "beijing_standard_lichun_jie_midnight_late_zi",
    "authority": "software_calendar_convention",
    "timezone": "UTC+08:00",
    "timezone_label": "北京时间（固定 UTC+08:00）",
    "year_boundary": "lichun_exact_instant",
    "month_boundary": "jie_exact_instant",
    "day_boundary": "00:00:00",
    "late_zi_hour": "23:00–23:59 日柱仍属当天，时柱用次日子时",
    "hour_pillar_day_basis": "next_day_at_23_else_current_day",
    "six_spirits_day_basis": "displayed_day_pillar",
    "library_eight_char_sect": 2,
    "true_solar_time": False,
    "historical_daylight_saving": False,
    "supported_beijing_years": [1900, 2100],
    "solar_term_precision": "library_computed_second",
}
CONVENTION_LABEL = (
    "北京时间；立春交节换年、节令交节换月；日柱零点换日；"
    "23时晚子时时柱按次日子时；标准时，不校正真太阳时。"
)
_ISO_INSTANT = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


def _result(status, original, code, message):
    return {
        "status": status,
        "pillars": {key: None for key in ("year", "month", "day", "hour")},
        "day_stem": None, "day_branch": None, "month_branch": None,
        "source_cast_time": original, "cast_time": None,
        "timezone": "UTC+08:00", "source_utc_offset": None,
        "timezone_converted": None,
        "convention_label": CONVENTION_LABEL,
        "calculation_policy": {**CALCULATION_POLICY, "supported_beijing_years": [1900, 2100]},
        "calendar_library": dict(LIBRARY_INFO),
        "code": code, "message": message,
    }


def calculate_calendar(input_data):
    """Return JSON-ready calendar facts; never substitute entry/current time.

    ``actual_cast_time`` must be a full ISO-8601 instant with timezone/offset.
    All four pillars are computed after conversion to fixed UTC+08:00. The
    original instant, converted instant, dependency and convention are returned
    together so a saved analysis can freeze exactly what its chart used.
    """
    if not isinstance(input_data, dict):
        return _result("error", None, "INVALID_INPUT", "起卦输入格式无效。")
    original = input_data.get("actual_cast_time")
    if original is None or original == "":
        return _result("missing", original, "CAST_TIME_MISSING",
                       "未填写实际起卦时间，四柱和六神暂缺；未用录入或解读时间代替。")
    if not isinstance(original, str) or not _ISO_INSTANT.fullmatch(original):
        return _result("error", original, "CAST_TIME_INVALID",
                       "实际起卦时间须为完整日期时间并包含时区，例如 2026-09-17T18:42:00+08:00。")
    try:
        source_time = datetime.fromisoformat(original.replace("Z", "+00:00"))
        local_time = source_time.astimezone(BEIJING_STANDARD_TIME)
    except (ValueError, OverflowError):
        return _result("error", original, "CAST_TIME_INVALID", "实际起卦日期、时间或时区无效。")
    if not 1900 <= local_time.year <= 2100:
        return _result("error", original, "CAST_TIME_OUT_OF_RANGE",
                       "四柱计算目前支持北京时间 1900 至 2100 年；原始起卦时间仍可保存。")
    try:
        solar = Solar.fromYmdHms(local_time.year, local_time.month, local_time.day,
                                local_time.hour, local_time.minute, local_time.second)
        eight_char = solar.getLunar().getEightChar()
        # Explicitly select midnight day rollover. Upstream intentionally bases
        # the 23:xx hour pillar on the next day's 子 hour in both sects.
        eight_char.setSect(2)
        pillars = {"year": eight_char.getYear(), "month": eight_char.getMonth(),
                   "day": eight_char.getDay(), "hour": eight_char.getTime()}
    except (ValueError, IndexError, ArithmeticError):
        return _result("error", original, "CALENDAR_COMPUTATION_FAILED",
                       "该起卦时间未能生成四柱，请核对时间；卦象仍可保留。")
    result = _result("computed", original, "CALENDAR_COMPUTED", "已按实际起卦时间排出四柱。")
    result.update({
        "pillars": pillars,
        "day_stem": pillars["day"][0], "day_branch": pillars["day"][1],
        "month_branch": pillars["month"][1],
        "cast_time": local_time.isoformat(),
        "source_utc_offset": source_time.strftime("%z")[:3] + ":" + source_time.strftime("%z")[3:],
        "timezone_converted": source_time.utcoffset() != timedelta(hours=8),
    })
    return result
