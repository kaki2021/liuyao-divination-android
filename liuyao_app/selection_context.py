"""Separate a stage's limited visibility from information actually available.

Selection receives availability flags, not calendar values, line positions or
strength.  Its unresolved notes remain immutable early AI opinions.  Review
records retain every original character and append only narrow corrections
that can be established from the saved input and the deterministic chart.
"""
from __future__ import annotations

import re


_CAST_TIME_MENTION = re.compile(r"(?:起卦|摇卦)(?:的)?(?:日期|时间|时刻|年月日|年月日时)")
_CALENDAR_MENTION = re.compile(r"日月|月令|日辰|月建|日建|四柱")
_LOCATION_MENTION = re.compile(r"定位|匹配|落于|多个|唯一|哪.{0,12}爻|具体.{0,12}爻")
_RELATIVE_NAMES = {
    "parents": "父母", "siblings": "兄弟", "offspring": "子孙",
    "wealth": "妻财", "official_ghost": "官鬼",
}
_STEMS = frozenset("甲乙丙丁戊己庚辛壬癸")
_BRANCHES = frozenset("子丑寅卯辰巳午未申酉戌亥")


def _pillar_available(pillar):
    return (isinstance(pillar, str) and len(pillar) == 2
            and pillar[0] in _STEMS and pillar[1] in _BRANCHES)


def build_information_scope(input_data, chart):
    """Project availability only; never infer a cast date from question text.

    ``calendar_status`` is ``computed``, ``missing``, ``error`` or ``unknown``.
    A computed calendar is usable only when it belongs to the supplied casting
    instant. A contradictory or unbound chart is an error, not a new date.
    The two context flags say which facts the later interpretation can receive;
    they are not claims that a complete strength/timing algorithm exists.
    """
    actual_time = input_data.get("actual_cast_time")
    provided = isinstance(actual_time, str) and bool(actual_time.strip())
    calendar = chart.get("calendar") or {}
    status = calendar.get("status", "unknown")
    if status not in ("computed", "missing", "error"):
        status = "unknown"
    if status == "computed" and (
        not provided or calendar.get("source_cast_time") != actual_time
    ):
        status = "error"
    pillars = calendar.get("pillars") or {}
    return {
        "actual_cast_time_provided": provided,
        "calendar_status": status,
        "month_context_available": status == "computed" and _pillar_available(pillars.get("month")),
        "day_context_available": status == "computed" and _pillar_available(pillars.get("day")),
        "chart_values_in_this_stage": False,
    }


def _unique_primary_match(selection, chart, note):
    candidates = selection.get("candidates") or []
    selected_id = selection.get("selected_primary_id")
    primary = next((c for c in candidates if c.get("candidate_id") == selected_id), None)
    if not primary or primary.get("purpose") != "primary" or primary.get("subject_reference"):
        return None
    relative = primary.get("six_relative")
    name = _RELATIVE_NAMES.get(relative)
    if not name or not _LOCATION_MENTION.search(note):
        return None
    # Limit the clarification to the selected functional relation. In particular,
    # a note about an auxiliary 官鬼 cannot be silently resolved by one 父母爻.
    target_terms = (name + "爻", "同类爻", "主功能", "主候选", "主用神", "所取六亲")
    if not any(term in note for term in target_terms):
        return None
    matches = [line.get("position") for line in chart.get("main", {}).get("lines", [])
               if line.get("relative_code") == relative]
    if len(matches) == 1 and type(matches[0]) is int and 1 <= matches[0] <= 6:
        return matches[0]
    return None


def review_selection_notes(selection, input_data, chart):
    """Return immutable-note reviews without turning hypotheses into gaps.

    Result fields: ``index``, ``status`` (``needs_review`` or
    ``partially_clarified``), ``original_text``, ``review_text``.  No original
    note is deleted or rewritten, including mixed date/age/rule statements.
    Partial clarification never means a complete rule or effective use-line
    has been established. Callers should freeze these records beside the raw
    stage output and use review_text, rather than the unqualified original, in
    the interpretation's uncertainty context.
    """
    scope = build_information_scope(input_data, chart)
    reviewed = []
    for index, original in enumerate(selection.get("unresolved", [])):
        clarifications = []
        if _CAST_TIME_MENTION.search(original) or _CALENDAR_MENTION.search(original):
            if scope["actual_cast_time_provided"]:
                if scope["month_context_available"] and scope["day_context_available"]:
                    clarifications.append(
                        "系统已收到实际起卦时间，并已计算月、日历法信息；取用阶段未展示这些具体值，"
                        "不能据此断言用户未提供起卦日期或本案缺少日月信息。"
                    )
                else:
                    clarifications.append(
                        "实际起卦时间字段已填写，但月、日历法信息尚未完整可用；"
                        "应区分已填写但未成功计算与用户未提供。"
                    )
            else:
                clarifications.append(
                    "实际起卦时间字段未填写；不能用原问中的事件日期、录入时间或当前时间替代。"
                )
        position = _unique_primary_match(selection, chart, original)
        if position is not None:
            clarifications.append(
                f"当前所选主功能六亲在本卦的结构匹配只有第{position}爻；"
                "这只确认同类位置，不等于已验证该功能假设或已确定唯一有效用神。"
            )
        review_text = "取用阶段早期AI意见（不是系统已确认的信息缺失）：" + original
        if clarifications:
            review_text += "\n系统复核：" + "".join(clarifications)
            review_text += "原文其余背景、功能假设及规则疑问仍需逐项核对，不能因这一部分已澄清而一并消除。"
        else:
            review_text += "\n尚未独立核实这项意见；请结合本次实际输入和盘面逐项评估，不直接当作已确认缺口。"
        reviewed.append({
            "index": index,
            "status": "partially_clarified" if clarifications else "needs_review",
            "original_text": original,
            "review_text": review_text,
        })
    return reviewed


def current_selection_notes(selection,input_data,chart):
    """Keep current unresolved clauses only; preserve verbatim history in audit."""
    scope=build_information_scope(input_data,chart)
    current=[]
    for note in selection.get('unresolved',[]):
        clauses=re.split(r'[。；;，,\n]+',note)
        remaining=[]
        for clause in clauses:
            if not clause.strip():continue
            if '、' in clause and re.search(r'未提供|缺少|缺失|未收到',clause):
                # Shared suffix: 起卦日期、年龄、合同期限未提供.
                suffix=re.search(r'(未提供|缺少|缺失|未收到).*',clause)
                names=clause[:suffix.start()].split('、') if suffix else []
                keep=[]
                for name in names:
                    if (_CAST_TIME_MENTION.search(name) or _CALENDAR_MENTION.search(name)) and scope['month_context_available'] and scope['day_context_available']:continue
                    if name in ('年龄','出生日期','姓名','背景','完整旺衰算法','综合旺衰算法','综合强弱算法'):continue
                    keep.append(name)
                clause='、'.join(keep)+suffix.group() if keep and suffix else ''
            if not clause:continue
            if re.fullmatch(r'限制应期和力度细化|(?:年龄|姓名|出生日期|背景)(?:未提供|缺失)',clause):continue
            has_real_world=bool(re.search(r'签约日期|合同内容|合同期限|用途|职业|审批|对方|目标期限',clause))
            solved=False
            if not has_real_world:
                if (_CAST_TIME_MENTION.search(clause) or _CALENDAR_MENTION.search(clause)) and scope['month_context_available'] and scope['day_context_available']:solved=True
                if _unique_primary_match(selection,chart,clause) is not None:solved=True
                if any(w in clause for w in ('综合旺衰算法','综合强弱算法','完整旺衰算法','未提供伏神','未自动确定变爻')) and chart.get('comprehensive_analysis'):solved=True
            if not solved:remaining.append(clause.strip())
        if remaining:current.append('；'.join(remaining))
    return current
