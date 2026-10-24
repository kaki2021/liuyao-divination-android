"""Calendar facts for an explicitly supplied casting instant.

This adapter's calendar policy is an engineering choice, not an assertion that
the divination source texts specified these civil-time boundaries. It uses only
calendar conversion from the vendored library, never its fortune/timing APIs.
"""
from datetime import datetime, timedelta, timezone
import re

from ._vendor.lunar_python import Solar
from .solar_time import solar_clock


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
        "time_basis": "beijing_standard",
        "convention_label": CONVENTION_LABEL,
        "calculation_policy": {**CALCULATION_POLICY, "supported_beijing_years": [1900, 2100]},
        "calendar_library": dict(LIBRARY_INFO),
        "code": code, "message": message,
    }


def calculate_calendar(input_data):
    """Return JSON-ready calendar facts; never substitute entry/current time.

    ``actual_cast_time`` must be a full ISO-8601 instant with timezone/offset.
    Legacy inputs use fixed UTC+08:00. With true_solar selected, day/hour use
    the local apparent clock while year/month retain actual term boundaries. The
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
        solar_details = None
        basis = input_data.get('time_basis', 'beijing_standard')
        if basis not in ('beijing_standard', 'true_solar'):
            return _result('error', original, 'TIME_BASIS_INVALID', '请选择北京时间或当地真太阳时。')
        if basis == 'true_solar':
            location = input_data.get('cast_location')
            longitude = location.get('longitude') if isinstance(location, dict) else None
            if type(longitude) not in (int, float) or not -180 <= longitude <= 180:
                return _result('error', original, 'CAST_LOCATION_REQUIRED', '真太阳时需要起卦地点的经度，请定位或手动填写。')
            clock, equation = solar_clock(source_time, longitude)
            if not 1900 <= clock.year <= 2100:
                return _result('error', original, 'CAST_TIME_OUT_OF_RANGE', '换算后的真太阳时超出支持年份。')
            solar_char = Solar.fromYmdHms(clock.year, clock.month, clock.day, clock.hour,
                                         clock.minute, clock.second).getLunar().getEightChar()
            solar_char.setSect(2)
            # Terms are physical instants in the library's Beijing chronology.
            # Only day/hour use the apparent clock; never shift a term boundary.
            pillars.update(day=solar_char.getDay(), hour=solar_char.getTime())
            solar_details = {'clock': clock.isoformat(timespec='seconds'), 'longitude': longitude,
                             'longitude_correction_minutes': round(4 * (longitude - 120), 6),
                             'equation_of_time_minutes': round(equation, 6),
                             'total_correction_minutes': round(4 * (longitude - 120) + equation, 6),
                             'algorithm': 'NOAA_Meeus_Julian_century_v1'}
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
    if solar_details:
        label = ('当地真太阳时；立春与节令交接按实际时刻；日柱按当地太阳时零点换日；'
                 '23时晚子时时柱按次日子时；经度修正加均时差。')
        result.update(time_basis='true_solar', timezone=None, cast_time=solar_details['clock'],
                      beijing_cast_time=local_time.isoformat(), solar_time=solar_details,
                      cast_location=dict(input_data['cast_location']), convention_label=label,
                      message='已按起卦地点换算真太阳时，日柱与时柱采用当地太阳时。')
        result['calculation_policy'].update(policy_id='local_apparent_lichun_jie_midnight_late_zi_v1',
            timezone=None, timezone_label='当地真太阳时', true_solar_time=True,
            day_hour_basis='local_apparent_solar_time', term_boundary_basis='actual_instant_beijing_library',
            solar_time_algorithm=solar_details['algorithm'])
    return result
