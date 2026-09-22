"""Retained AI interpretation grounded in deterministic charts and core sources.

The model gives a direct, conditional synthesis of the available evidence.
Structure validation does not turn its interpretation into a verified forecast.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from pathlib import Path
from typing import Callable

import base_chart
import branch_relations
from liuyao_app.calendar_context import calculate_calendar
from liuyao_app.basic_analysis import build_basic_analysis
from liuyao_app.person_context import person_evidence
from liuyao_app import buzhai
from liuyao_app.selection_projection import project_selection
from liuyao_app.response_compat import normalize_stage_output, parse_model_json
from liuyao_app.selection_context import build_information_scope, review_selection_notes, current_selection_notes
from liuyao_app.validation_feedback import collect_output_errors, collect_application_errors
from liuyao_app.interpretation_checks import interpretation_errors
from liuyao_app.report_generator import build_user_report, normalize_report, fallback_report
from liuyao_app.rulebook import load_rules
from liuyao_app.comprehensive_analysis import calculate_comprehensive, select_use_lines, analysis_facts
from liuyao_app.report_template import SECTIONS
from copy import deepcopy
from liuyao_app.runtime_contract import runtime_prompt, runtime_output_schema
from case_store import Actor, CaseStore, content_digest, ident
from validate_ai_contract import (
    ContractError, SOURCE_ROLES, canonical, check_schema, load_pack,
    prompt_digest, validate_output,
)

FOUNDATION = Path(__file__).resolve().parents[1] / "software_prep"
DIMENSIONS = ("outcome", "subject_effect", "cost", "support", "obstacle", "adjustment")
HEADINGS = dict(zip(DIMENSIONS, ("目标成败", "自身得失", "代价", "支持条件", "阻碍", "可调整事项")))
STAGES = ("intent", "selection", "interpretation", "report")
REPORT_TIMEOUT_SECONDS = 90
BASE_RULES = (
    "casting.four_states", "chart.palace_elements", "chart.branch_elements",
    "chart.palace_sequence", "chart.branch_assignment", "relation.ordinary_kinship",
    "chart.shi_ying", "chart.shi_body", "chart.gua_body",
)
SELECTION_RULES = ("interpretation.functional_role", "relation.ordinary_kinship",
                   "interpretation.three_self_references", "interpretation.analysis_scale")
SCENARIO_RULES = {
    "interpretation.object_functions": ("车", "土地", "粮", "稻", "麦", "食物"),
    "interpretation.leader_documents": ("领导", "职位", "升职", "合同", "录用", "offer", "调令"),
    "interpretation.producing_wealth": ("基金", "债券", "股票"),
    "interpretation.relationship_roles": ("恋爱", "婚", "配偶", "伴侣", "感情"),
    "interpretation.treatment_roles": ("病", "药", "医生", "治疗", "手术", "健康"),
    "interpretation.judge_role": ("法官", "原告", "被告", "诉讼", "官司"),
    "interpretation.travel_roles": ("出行", "旅行", "出差", "旅游"),
    "interpretation.study_roles": ("学习", "考试", "成绩", "考学", "学业"),
}
INTERPRETATION_RULES = (
    "interpretation.no_intrinsic_omen", "interpretation.single_target",
    "interpretation.gains_before_success", "interpretation.report_uncertainty",
    "interpretation.three_self_references", "interpretation.analysis_scale",
    "interpretation.body_overlap", "relation.ordinary_wuxing",
    "interpretation.target_effects",
)


class StageFailure(Exception):
    def __init__(self, code, message, stage, *, validation_detail=None, attempts=None, suggestion=None):
        self.code, self.message, self.stage = code, message, stage
        self.validation_detail = validation_detail
        self.attempts, self.suggestion = attempts, suggestion
        super().__init__(message)


def _validation_failure(stage, detail, attempts=2):
    """Explain the actual rejected stage without inserting model prose in UI copy."""
    label = {"intent": "理解问题", "selection": "确定取用", "interpretation": "综合解卦", "report": "整理报告"}[stage]
    if "ready selection needs a non-null primary candidate ID" in detail:
        reason = "AI没有明确选定主用神候选，且无法从回复中确定唯一主候选"
    elif "candidate ID does not exist in candidates" in detail:
        reason = "AI填写的主候选编号不在它生成的候选列表中"
    elif "selected_primary_id must reference a primary candidate" in detail:
        reason = "AI把辅助、代价或承载候选填成了主候选"
    elif "nonexistent refs" in detail:
        reason = "AI引用了本次资料中不存在的依据编号"
    elif "binding" in detail or "another run" in detail:
        reason = "AI返回的内容与本次案例记录不匹配"
    elif "JSON" in detail or "output must" in detail:
        reason = "AI回复的格式无法读取"
    elif "RELATION_DIRECTION_MISMATCH" in detail:
        reason = "AI把所引五行关系的生克方向写反，相关判断尚未修正"
    elif "ENGINE_INFERENCE_REQUIRED" in detail:
        reason = "AI把自己的解释标成了程序已验证的结论，但没有对应的验证依据"
    elif "CONTEXT_CONTRADICTION" in detail:
        reason = "AI对已提供资料的描述与本次排盘记录矛盾"
    elif "UNSUPPORTED_SCOPE" in detail:
        reason = "AI从排盘结构推导出的现实判断超出了所引用规则的范围"
    elif "direction" in detail or "conclusion" in detail:
        reason = "AI结论与它列出的依据或成立条件不一致"
    elif "missing" in detail or "wrong type" in detail or "enum mismatch" in detail:
        reason = "AI回复缺少必要字段或字段格式不符合要求"
    else:
        reason = "AI回复中的依据、规则或字段未通过核对"
    message = f"{label}阶段未完成：{reason}，自动修复后仍未通过。问题、卦象和过程已保存。"
    return StageFailure("CONTRACT_INVALID", message, stage,
        validation_detail=detail[:4000], attempts=attempts,
        suggestion="展开“查看AI原始回复”可查看本次生成内容；也可导出诊断用于排查，或在当前案例重新解卦。")


def _catalog():
    value = json.loads((FOUNDATION / "rule_catalog.json").read_text(encoding="utf-8"))
    return value, {r["rule_id"]: r for r in value["rules"]}


def _project_rules(catalog, ids, usage, applicability):
    """The explicit stage allowlist is the approval decision, not catalog order.

    A definition may be approved for functional interpretation without claiming
    its complete inference algorithm is implemented. Display calculations also
    require the catalog's tested implementation status.
    """
    result = []
    for rule_id in dict.fromkeys(ids):
        rule = catalog[rule_id]
        role = SOURCE_ROLES.get(rule["source_id"])
        if rule["status"] != "defined" or role not in ("core", "core_supplement"):
            raise ContractError("unapproved rule in application allowlist: " + rule_id)
        if usage == "display" and rule["implementation_status"] != "tested":
            raise ContractError("display calculation is not tested: " + rule_id)
        result.append({
            "rule_id": rule_id, "source_id": rule["source_id"], "source_role": role,
            "source_locator": rule["source_locator"], "statement": rule["statement"],
            "status": "approved", "usage": usage, "applicability": applicability,
        })
    return result


def _selection_rules(catalog, evidence, topic_context=None):
    text = "\n".join(e["text"] for e in evidence).lower()
    rules = _project_rules(catalog, SELECTION_RULES, "selection",
        "仅用于识别本次对象的功能关系及相应六亲；不支持成败判断或具体爻位筛选。")
    for rule_id, terms in SCENARIO_RULES.items():
        matched = [term for term in terms if term in text]
        if matched:
            rules.extend(_project_rules(catalog, [rule_id], "selection",
                "原问或已知背景出现“" + "、".join(matched) + "”；只在原文所述用途与本案一致时作功能候选，不能由名称直接定取用。"))
    rules.extend(_project_rules(catalog, buzhai.projected_rule_ids(topic_context, 'selection'), 'selection',
        '用户已明确启用卜宅专题；只按所述角色、阶段和实际功能取用，不能凭房屋名称或风水关键词固定用神。'))
    return rules


def calculate_chart(input_data, rules=None):
    """One chart path for initial display, retained analysis and case reopening."""
    calendar = calculate_calendar(input_data)
    day_stem = calendar.get("day_stem") if calendar["status"] == "computed" else None
    chart = base_chart.calculate_base_chart(input_data["lines"], verified_day_stem=day_stem)
    chart["calendar"] = calendar
    if calendar["status"] == "computed":
        chart["not_computed"] = [item for item in chart["not_computed"] if item != "calendar"]
        month_branch = calendar["pillars"]["month"][1]
        month_element = base_chart.BRANCH_ELEMENTS[month_branch]
        for line in chart["main"]["lines"]:
            line["ordinary_month_strength"] = base_chart.ordinary_month_strength(month_element, line["element"])
    pairs = []
    for a, b in itertools.combinations(chart["main"]["lines"], 2):
        relation = branch_relations.classify_pair(a["branch"], b["branch"])
        if relation["relations"]:
            pairs.append({"positions": [a["position"], b["position"]], **relation})
    chart["line_pair_relations"] = pairs
    chart["relation_scope"] = "main_chart_pair_and_category_only"
    chart["basic_analysis"] = build_basic_analysis(chart)
    chart["comprehensive_analysis"] = calculate_comprehensive(chart, rules or load_rules())
    chart["not_computed"] = [x for x in chart["not_computed"] if x not in ('changed_line_relatives','comprehensive_strength')]
    if input_data.get('buzhai'):
        chart['buzhai_analysis'] = buzhai.analyze_buzhai(chart, input_data['buzhai'])
    return chart


def _chart(lines):
    """Compatibility for callers that only possess the six line states."""
    return calculate_chart({"lines": lines})


def _evidence(snapshot, known_at):
    evidence = [{"evidence_id": "USER_QUESTION", "text": snapshot["input"]["question"],
                 "origin": "user_question", "known_at": known_at}]
    people = person_evidence(snapshot["input"], known_at)
    if people is not None:
        evidence.append(people)
    topic = buzhai.context_evidence(snapshot['input'], known_at)
    if topic is not None:
        evidence.append(topic)
    for event in snapshot["context_events"]:
        if event["event_type"] not in ("background", "clarification_answer", "user_correction"):
            continue
        content = event["content"]
        text = next((content[key] for key in ("text", "answer", "background")
                     if isinstance(content.get(key), str) and content[key].strip()), None)
        if text is not None:
            if len(text) > 10000:
                raise StageFailure("CONTEXT_TOO_LONG", "单条背景内容过长，请整理当前问题的相关事实。", "intent")
            evidence.append({"evidence_id": event["event_id"], "text": text,
                "origin": "clarification_answer" if event["event_type"] == "clarification_answer" else "user_background",
                "known_at": event["recorded_at"]})
    if len(evidence) > 40:
        raise StageFailure("CONTEXT_TOO_LONG", "本案背景记录超过当前分析可接收数量，已保留全部记录，请另建聚焦当前问题的案例。", "intent")
    return evidence


def _prior_clarifications(snapshot, pack):
    questions = []
    definition = pack["stages"]["intent"]["input_schema"]["$defs"]["question"]
    for event in snapshot["context_events"]:
        if event["event_type"] != "clarification_question":
            continue
        candidate = {key: event["content"].get(key) for key in ("question_id", "text", "why_needed", "affects")}
        try:
            check_schema(candidate, definition)
        except ContractError:
            continue
        questions.append(candidate)
    return questions[-20:]


def _fact(fact_id, kind, subject, predicate, value, rule=None):
    return dict(fact_id=fact_id, kind=kind, subject=subject, predicate=predicate,
                value=value, source_rule_id=rule)


def _facts(chart, evidence, selection):
    facts = [_fact("CTX_" + str(i), "context", "用户原问" if i == 0 else "用户背景",
                   "已说明", e["text"], None) for i, e in enumerate(evidence)]
    # Context's fact scalar is capped by the pack; long original evidence is
    # preserved at the intent/selection stages and in the frozen case snapshot.
    facts = [f for f in facts if len(f["value"]) <= 4000]
    facts.extend([
        _fact("CHART_NAME", "chart", "主卦", "卦名", chart["main"]["name"], "chart.palace_sequence"),
        _fact("CHART_BITS", "chart", "主卦", "阴阳序列（初爻至上爻，1阳0阴）", canonical(chart["main"]["bits"]), "casting.four_states"),
        _fact("CHART_LOWER_TRIGRAM", "chart", "主卦", "下卦", chart["main"]["lower_trigram"], "chart.branch_assignment"),
        _fact("CHART_UPPER_TRIGRAM", "chart", "主卦", "上卦", chart["main"]["upper_trigram"], "chart.branch_assignment"),
        _fact("CHART_PALACE", "chart", "主卦", "归宫", chart["main"]["palace"], "chart.palace_sequence"),
        _fact("PALACE_ELEMENT", "calculation", "主卦宫", "五行", chart["main"]["palace_element"], "chart.palace_elements"),
        _fact("SHI_POSITION", "calculation", "世爻", "爻位", chart["shi_position"], "chart.shi_ying"),
        _fact("YING_POSITION", "calculation", "应爻", "爻位", chart["ying_position"], "chart.shi_ying"),
        _fact("BODY_POSITION", "calculation", "世身", "爻位", chart["shi_body_position"], "chart.shi_body"),
        _fact("GUA_BODY", "calculation", "卦身", "地支", chart["gua_body_branch"], "chart.gua_body"),
        _fact("MOVING_POSITIONS", "chart", "主卦", "动爻位置", canonical(chart["moving_positions"]), "casting.four_states"),
        _fact("HAS_CHANGED_STRUCTURE", "chart", "本次卦象", "是否有动爻形成独立变卦", chart["changed_structure"] is not None, "casting.four_states"),
    ])
    for line in chart["main"]["lines"]:
        pos = str(line["position"])
        for key, predicate, rule in (("yang", "是否阳爻", "casting.four_states"),
                                     ("branch", "地支", "chart.branch_assignment"),
                                     ("element", "五行", "chart.branch_elements"),
                                     ("relative_code", "普通六亲", "relation.ordinary_kinship"),
                                     ("moving", "是否发动", "casting.four_states")):
            facts.append(_fact("LINE_" + pos + "_" + key.upper(), "chart", "主卦第" + pos + "爻", predicate, line[key], rule))
    changed = chart["changed_structure"]
    if changed is not None:
        facts.extend([
            _fact("CHANGED_CHART_NAME", "chart", "变卦", "卦名", changed["name"], "chart.palace_sequence"),
            _fact("CHANGED_CHART_BITS", "chart", "变卦", "阴阳序列（初爻至上爻，1阳0阴）", canonical(changed["bits"]), "casting.four_states"),
            _fact("CHANGED_LOWER_TRIGRAM", "chart", "变卦", "下卦", changed["lower_trigram"], "chart.branch_assignment"),
            _fact("CHANGED_UPPER_TRIGRAM", "chart", "变卦", "上卦", changed["upper_trigram"], "chart.branch_assignment"),
        ])
        # Every branch belongs to the resulting trigram structure, including
        # unchanged line positions. This does not infer active changed-line roles.
        for position, (bit, branch) in enumerate(zip(changed["bits"], changed["branches"]), 1):
            for suffix, predicate, value, rule in (
                ("YANG", "是否阳爻", bool(bit), "casting.four_states"),
                ("BRANCH", "变卦结构中的地支", branch, "chart.branch_assignment"),
                ("ELEMENT", "地支五行", base_chart.BRANCH_ELEMENTS[branch], "chart.branch_elements"),
            ):
                facts.append(_fact(f"CHANGED_LINE_{position}_{suffix}", "chart", f"变卦第{position}爻", predicate, value, rule))
    for pair in chart["line_pair_relations"]:
        a, b = pair["positions"]
        for relation in pair["relations"]:
            facts.append(_fact(f"PAIR_{a}_{b}_{relation['relation_type']}", "calculation",
                f"主卦第{a}爻与第{b}爻", relation["label"] + "类别", relation["category_label"], relation["rule_ids"][1]))
    # One snapshot drives the UI and AI; the model does not recalculate these
    # relations. Compatibility fallback is for callers with pre-update charts.
    foundation = chart.get("basic_analysis") or build_basic_analysis(chart)
    facts.extend(foundation["facts"])
    facts.extend(analysis_facts(chart))
    calendar = chart.get("calendar", {})
    if calendar.get("status") == "computed":
        for key, name in (("year", "年柱"), ("month", "月柱"), ("day", "日柱"), ("hour", "时柱")):
            facts.append(_fact("CALENDAR_" + key.upper(), "calculation", "实际起卦时间", name,
                               calendar["pillars"][key], None))
        facts.append(_fact("CALENDAR_CONVENTION", "calculation", "四柱", "排盘约定",
                           calendar["convention_label"], None))
        facts.append(_fact("CAST_TIME", "calculation", "本次起卦", "按排盘时区显示的时刻", calendar["cast_time"], None))
        for line in chart["main"]["lines"]:
            pos = line["position"]
            facts.append(_fact(f"LINE_{pos}_SIX_SPIRIT", "calculation", f"主卦第{pos}爻", "按日干定位的六神",
                               line["six_spirit"], "chart.six_spirits"))
            facts.append(_fact(f"LINE_{pos}_MONTH_STRENGTH", "calculation", f"主卦第{pos}爻", "普通五行月令分类（非综合旺衰）",
                               line["ordinary_month_strength"], "relation.ordinary_month_strength"))
    primary = next(c for c in selection["candidates"] if c["candidate_id"] == selection["selected_primary_id"])
    subject_reference = primary.get("subject_reference")
    if subject_reference:
        pos = chart["shi_position"] if subject_reference == "shi" else chart["shi_body_position"]
        facts.append(_fact("SUBJECT_REFERENCE", "selection", "本次所问主体", "主体参照",
                           "世爻" if subject_reference == "shi" else "世身", "interpretation.three_self_references"))
        facts.append(_fact("MATCHING_LINES", "selection", "本次主体参照", "主卦位置", canonical([pos]),
                           "chart.shi_ying" if subject_reference == "shi" else "chart.shi_body"))
        return facts
    facts.append(_fact("FUNCTION_SELECTION", "selection", "本次主目标", "功能六亲候选",
                       primary["six_relative"], primary["rule_refs"][0]))
    matches = [line["position"] for line in chart["main"]["lines"] if line["relative_code"] == primary["six_relative"]]
    facts.append(_fact("MATCHING_LINES", "selection", "本次功能六亲", "主卦同类位置（尚未确定具体用神）", canonical(matches), "relation.ordinary_kinship"))
    return facts


def _gaps(input_data, chart, selection, evidence):
    gaps = [{"gap_id":"GAP_TIMING", "description":"精确应期算法尚未实现，不推造精确日期。", "affects":["timing"], "blocking":False}]
    if chart.get("calendar", {}).get("status") != "computed":
        gaps.append({"gap_id": "GAP_CALENDAR", "description": "实际起卦时间未能用于历法排盘，暂不评价日月强弱与精确应期；仍需根据已有本变卦、世应身位及关系给粗略解读。",
                     "affects": ["outcome", "timing"], "blocking": True})
    primary = next(c for c in selection["candidates"] if c["candidate_id"] == selection["selected_primary_id"])
    if not primary.get("subject_reference"):
        matches = [line["position"] for line in chart["main"]["lines"] if line["relative_code"] == primary["six_relative"]]
        use = chart['comprehensive_analysis'].get('use_selection',{}).get('primary') or {}
        if not use.get('chosen'):
            gaps.append({'gap_id':'GAP_USE_LINE','description':'当前功能六亲在本卦和本宫伏神中均未定位。','affects':['selection','outcome'],'blocking':False})
    if primary.get("subject_reference") == "shi_body" and len(chart["gua_body_positions"]) != 1:
        gaps.append({"gap_id": "GAP_BODY_POSITION", "description": "卦身在本卦缺位或有多个匹配。位身五行关系仅作结构参考，须说明显现程度或候选位置，不能当作唯一有效作用。",
                     "affects": ["subject_effect"], "blocking": True})
    if any(len(e["text"]) > 4000 for e in evidence):
        gaps.append({"gap_id": "GAP_CONTEXT_PROJECTION", "description": "部分较长背景完整保存在原始快照与取用阶段，未压缩成解释阶段的简短事实；不能视为已完成全部背景评估。", "affects": list(DIMENSIONS), "blocking": True})
    if chart["line_pair_relations"]:
        gaps.append({"gap_id": "GAP_RELATION_EFFECT", "description": "形害分类仅为地支结构事实，整体大象、作用对象与有效性未定，不能推断现实人物动机或必然结果。", "affects": list(DIMENSIONS), "blocking": True})
    for index, route in enumerate(selection["route_requests"]):
        if route["missing_information"] or route["topic"] == "true_wuxing_applicability":
            gaps.append({"gap_id": "GAP_ROUTE_" + str(index), "description": "适用范围：" + route["basis"] + "；明确本次采用的条件，不将未知范围当作已经核定。", "affects": list(DIMENSIONS), "blocking": True})
    # A valid functional choice can still have unanswered questions. Carry the
    # complete early note with its independent availability review instead of
    # blocking every later interpretation. Max 20 unresolved + 1 question plus
    # the existing max 9 gaps fits the output contract's 30 uncertainty records.
    from liuyao_app.selection_context import current_selection_notes
    for index, note in enumerate(current_selection_notes(selection, input_data, chart)):
        gaps.append({'gap_id':f'GAP_SELECTION_UNRESOLVED_{index}','description':note,'affects':[*DIMENSIONS,'selection'],'blocking':False})
    for index, question in enumerate(selection["clarifying_questions"]):
        gaps.append({"gap_id": f"GAP_SELECTION_QUESTION_{index}",
                     "description": question["text"] + "；需要核实的原因：" + question["why_needed"],
                     "affects": [*DIMENSIONS, "selection"], "blocking": True})
    return gaps


def _interpretation_rules(catalog, selection_rules, chart):
    rules = [rule for rule in selection_rules if rule["rule_id"] not in INTERPRETATION_RULES and not rule['rule_id'].startswith('buzhai.')]
    rules.extend(_project_rules(catalog, [r for r in BASE_RULES if r not in {x['rule_id'] for x in rules}], "display",
                               "只说明本次已计算的普通主卦、世应、身位与动变结构，不支持预测成败。"))
    rules.extend(_project_rules(catalog, INTERPRETATION_RULES, "interpretation",
                               "可结合本案有方向五行事实及主体尺度给条件性得失、支持和阻碍判断；区分目标实现，不将关系分类当作已判有效的全部作用。"))
    if chart.get("calendar", {}).get("status") == "computed":
        rules.extend(_project_rules(catalog, ["chart.six_spirits", "relation.ordinary_month_strength"], "display",
                                   "仅六神定位与普通月令五类，不以六神名称直接定吉凶，不等于年月日与动变的综合强弱。"))
    relation_ids = {rid for pair in chart["line_pair_relations"] for r in pair["relations"] for rid in r["rule_ids"]}
    if any(f.get("source_rule_id") == "relation.six_combination_pairs"
           for f in chart.get("basic_analysis", {}).get("facts", [])):
        relation_ids.add("relation.six_combination_pairs")
    if relation_ids:
        rules.extend(_project_rules(catalog, sorted(relation_ids), "display", "本次主卦爻对确有该分类，仅展示配对和类别。"))
    if any("three_forms" in rid for rid in relation_ids):
        rules.extend(_project_rules(catalog, ["interpretation.three_forms_context"], "interpretation",
                                   "本次存在互形结构；整体大象未完成，只可说明解释条件与限制。"))
    topic = chart.get('buzhai_analysis', {}).get('context')
    rules.extend(_project_rules(catalog, buzhai.projected_rule_ids(topic, 'interpretation'), 'interpretation',
        '仅本次明确选择的卜宅对象、场所、阶段与方案。结合结构事实作有前提的解释，不代表自动成局或已验证预测。'))
    return rules


def _semantic_guards(stage, output, server_input):
    """Narrow deterministic guards supplement, not replace, semantic review."""
    if stage == "interpretation":
        scope_errors = collect_application_errors(stage, output, server_input)
        if scope_errors:
            issue = scope_errors[0]
            raise ContractError(f"{issue['path']} [{issue['code']}]: {issue['message']}")
        for claim in output["claims"]:
            if claim["kind"] == "engine_supported":
                raise ContractError("this application has no verified outcome inferences")
    if stage == "report":
        plan = server_input["accepted_interpretation"]
        if not plan["claims"] and any(p["qualification"] != "undetermined" for p in output["parts"]):
            raise ContractError("empty interpretation cannot yield a resolved report")


def _stage_call(store, actor, case_id, run_id, stage, server_input, pack,
                provider, model, provider_call, progress, audit_warnings=None):
    audit_warnings = audit_warnings if audit_warnings is not None else []
    input_schema=deepcopy(pack['stages'][stage]['input_schema'])
    if stage=='report': input_schema['properties']['analysis_chart']={'type':'object'}
    check_schema(server_input, input_schema)
    prompt = runtime_prompt(stage, pack, server_input)
    repair_context = None
    last_error = "invalid model JSON"
    deadline = time.monotonic() + REPORT_TIMEOUT_SECONDS if stage == 'report' else None
    for attempt in range(1, 3):
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining < 1:
            raise StageFailure('timeout', '报告整理已达到等待时限，保留已有解卦结论。', stage, attempts=attempt - 1)
        progress({"stage": stage, "attempt": attempt, "phase": "waiting", "analysis_run_id": run_id})
        raw = ""
        metadata = {"provider": provider, "model": model, "stage_input": server_input,
                    "stage_input_digest": content_digest(server_input), "system_prompt_digest": hashlib.sha256(prompt.encode()).hexdigest(),
                    "system_prompt": prompt, "stage_prompt_digest": prompt_digest(pack, stage), "attempt_number": attempt}
        if repair_context is not None:
            metadata["repair_of_attempt"] = attempt - 1
            metadata["repair_validation_error"] = repair_context["validation_error"]
        try:
            options = {"timeout": None}
            if remaining is not None:
                from liuyao_app.providers import _timeout
                options['timeout'] = min(_timeout(None), remaining)
            if repair_context is not None:
                options["repair_context"] = repair_context
            response = provider_call(provider, model, prompt, server_input, **options)
            raw = response["raw_text"]
            if not isinstance(raw, str):
                raise TypeError("provider raw_text must be text")
            metadata.update({key: response[key] for key in ("provider", "model", "response_model", "request_id", "usage", "finish_reason", "elapsed_ms", "request_hash", "http_status", "thinking", "reasoning_effort", "max_tokens") if key in response})
            progress({"stage": stage, "attempt": attempt, "phase": "validating"})
        except Exception as exc:
            code = getattr(exc, "code", "PROVIDER_FAILURE")
            # The provider adapter exposes sanitized error messages; arbitrary
            # injected callables do not have that guarantee.
            message = str(exc) if getattr(exc, "code", None) else "AI调用失败，未自动切换厂商。"
            provider_meta = getattr(exc, "metadata", {})
            if isinstance(provider_meta, dict):
                metadata.update({key: provider_meta[key] for key in ("request_id", "usage", "finish_reason", "response_model", "elapsed_ms", "request_hash", "http_status", "thinking", "reasoning_effort", "max_tokens") if key in provider_meta})
            raw = getattr(exc, "raw_text", None) or ""
            parse_status = "invalid_json" if code == "invalid_json" else ("not_parsed" if raw else "provider_error")
            store.add_ai_event(actor, case_id, run_id, stage=stage, attempt_id=f"{stage}_{attempt}",
                raw_output=raw, parse_status=parse_status, validation_errors=[{"code": str(code), "message": message}],
                model_run_metadata=metadata, idempotency_key=f"{run_id}:{stage}:{attempt}")
            progress({"stage": stage, "attempt": attempt, "phase": "repairing" if code == "invalid_json" and attempt == 1 else "error", "reply_saved": True})
            if code == "invalid_json":
                if attempt == 1:
                    repair_context = {"previous_output": raw, "validation_error": "invalid model JSON: " + message}
                    continue
                raise _validation_failure(stage, "invalid model JSON: " + message, attempt) from exc
            raise StageFailure(str(code), message, stage, attempts=attempt) from exc
        error = None
        validation_errors = []
        parse_status = "parsed"
        try:
            parse_model_json(raw)
        except ValueError:
            parse_status = "invalid_json"
        try:
            normalized, changes = normalize_stage_output(stage, raw, server_input)
            if stage == "selection":
                normalized, projected = project_selection(normalized)
                changes.extend(projected)
            metadata["normalization_changes"] = changes
            if stage == 'report':
                normalized = normalize_report(normalized, server_input)
                validation_errors = []
                if normalized.get('binding') != {k:server_input['meta'][k] for k in ('analysis_run_id','input_snapshot_id')}:
                    validation_errors.append({'code':'BINDING_MISMATCH','path':'$.binding','message':'wrong report binding'})
            else:
                validation_errors = collect_output_errors(stage, normalized, server_input, pack)
            validation_errors.extend(collect_application_errors(stage, normalized, server_input))
            if stage == "interpretation":
                validation_errors.extend(interpretation_errors(normalized, server_input))
            try:
                check_schema(normalized, runtime_output_schema(stage, pack, server_input))
            except (ContractError, KeyError, TypeError, ValueError) as exc:
                if not any(item["message"] == str(exc) for item in validation_errors):
                    validation_errors.append({"code": "APPLICATION_CONTRACT", "path": "$", "message": str(exc)})
            if stage in ('interpretation','report'):
                fatal = [e for e in validation_errors if e['code'].startswith('SCHEMA_') or e['code'] in ('BINDING_MISMATCH','APPLICATION_CONTRACT')]
                warnings = [e for e in validation_errors if e not in fatal]
                if stage=='report' and 'sections' in normalized:
                    if [p['key'] for p in normalized['sections']] != [k for k,h in SECTIONS]:
                        fatal.append({'code':'REPORT_SECTION_ORDER','path':'$.sections','message':'报告分段缺失、重复或顺序不正确'})
                if stage=='report' and isinstance(normalized.get('plain_language'),dict):
                    from liuyao_app.report_generator import TECHNICAL_WORDS
                    plain=normalized['plain_language']
                    if plain.get('direction')!=server_input['accepted_interpretation']['conclusion']['direction']:
                        fatal.append({'code':'PLAIN_DIRECTION','path':'$.plain_language.direction','message':'通俗答案必须保持原推演方向'})
                    if plain.get('source')=='ai' and TECHNICAL_WORDS.search(' '.join([str(plain.get(k,'')) for k in ('answer','reason','watch_for','next_steps','timing')])):
                        fatal.append({'code':'PLAIN_JARGON','path':'$.plain_language','message':'请把六爻术语和实验评分改成普通人能理解的日常语言，专业依据留在sections'})
                metadata['audit_warnings'] = warnings
                audit_warnings.extend(dict(stage=stage,attempt=attempt,**e) for e in warnings)
                validation_errors = fatal
                accepted = normalized if not fatal else None
            else:
                accepted = validate_output(stage, canonical(normalized), server_input, pack) if not validation_errors else None
            if validation_errors:
                repair_issues = validation_errors + metadata.get("audit_warnings",[])
                error = "\n".join(f"{item.get('path', '$')} [{item['code']}]: {item['message']}" for item in repair_issues)
                last_error, accepted = error, None
        except (ContractError, KeyError, TypeError, ValueError) as exc:
            error = str(exc)
            last_error = error
            accepted = None
            validation_errors.append({"code": "CONTRACT_INVALID", "message": error, "path": "$"})
        store.add_ai_event(actor, case_id, run_id, stage=stage, attempt_id=f"{stage}_{attempt}",
            raw_output=raw, parse_status=parse_status,
            validation_errors=validation_errors,
            adopted_output=accepted, model_run_metadata=metadata, idempotency_key=f"{run_id}:{stage}:{attempt}")
        progress({"stage": stage, "attempt": attempt, "phase": "stage_done" if accepted is not None else "repairing" if attempt == 1 else "error", "reply_saved": True,
                  "completed_stage": stage if accepted is not None else None})
        if accepted is not None:
            return accepted
        if attempt == 1:
            # One explicit repair attempt on the same frozen evidence, provider,
            # model and task. No more evidence, fallback or new domain rule.
            repair_context = {"previous_output": raw, "validation_error": error}
    raise _validation_failure(stage, last_error)


def _display(result):
    if result["is_demo"]:
        chart = result["chart"]
        return {"title": "本地排盘演示", "summary": "已按输入生成基础卦盘；本次未调用AI，也未判断真念或成败。",
            "sections": [{"heading": "卦盘", "content": f"主卦：{chart['main']['name']}；归宫：{chart['main']['palace']}，宫五行：{chart['main']['palace_element']}。"},
                         {"heading": "当前范围", "content": "可查看六爻、世应、身位、变卦结构及三形六害类别。成败与应期仍待完整规则。"}]}
    interpretation = result["stage_outputs"].get("interpretation", {})
    if result["status"] == "failed" and not interpretation:
        return {"title": "分析未完成", "summary": result.get("error", {}).get("message", "本次分析未完成，输入和过程已保留。"), "sections": []}
    understood = []
    intent = result["stage_outputs"].get("intent", {})
    if intent.get("status") == "ready":
        selected = next(c for c in intent["candidates"] if c["candidate_id"] == intent["selected_candidate_id"])
        understood.append({"heading": "本次所问", "content": selected["primary_question"]})
    selection = result["stage_outputs"].get("selection", {})
    if selection.get("status") == "ready":
        selected = next(c for c in selection["candidates"] if c["candidate_id"] == selection["selected_primary_id"])
        details = ["关注对象：" + selected["object_role"], "本次作用：" + selected["function"]]
        if selected.get("subject_reference"):
            details.append("分析主体：" + ("世爻，侧重社会身份与角色" if selected["subject_reference"] == "shi" else "世身，侧重个人状态与处境"))
        elif result.get("chart"):
            labels = {"parents": "父母", "siblings": "兄弟", "offspring": "子孙", "wealth": "妻财", "official_ghost": "官鬼"}
            relative = selected["six_relative"]
            matches = [str(line["position"]) for line in result["chart"]["main"]["lines"]
                       if line["relative_code"] == relative]
            details.append("程序按功能关系对应六亲：" + labels[relative])
            details.append("本卦同类位置：" + ("第" + "、".join(matches) + "爻" if matches else "本卦未现"))
        details.extend("待核实的假设：" + assumption for assumption in selected["assumptions"])
        understood.append({"heading": "关注对象的作用", "content": "\n".join(details)})
    if result["clarifying_questions"] and not interpretation:
        return {"title": "需要补充信息", "summary": "补充下列事实后，可以继续分析这一个案例。",
                "sections": understood + [{"heading": "待补充", "content": "\n".join(result["clarifying_questions"])}]}
    if result["status"] == "unresolved":
        return {"title": "取用仍待核对", "summary": "本次问题或适用规则还有未决项，暂未继续作出判断。",
                "sections": understood + [{"heading": "未决事项", "content": "\n".join(result["unresolved"])}]}
    if result.get('user_report'):
        return result['user_report']
    if interpretation.get('conclusion'):
        return fallback_report(interpretation,result.get('chart') or {})
    return {'title':'分析未完成','summary':'本次尚未形成预测。','sections':[]}


def result_from_outcome(run):
    """Project a CaseStore.export_case analysis run back to the UI contract."""
    outcome = run.get("outcome")
    if outcome and isinstance(outcome.get("result", {}).get("report"), dict):
        return outcome["result"]["report"]
    result = {"analysis_run_id": run["analysis_run_id"], "status": run.get("status", "running"),
              "chart": None, "report": None, "display_report": {"title": "正在分析", "summary": "分析进行中。", "sections": []},
              "clarifying_questions": [], "unresolved": [], "stage_outputs": {}, "is_demo": False}
    return result


def run_analysis(db_path, actor: Actor, case_id, provider, model, expected_revision_seq,
                 progress: Callable | None = None, *, provider_call=None):
    """Retain one analysis on a frozen revision; always finish a started run.

    Actor is trusted service identity. Providers and secrets are never obtained
    from case content. A separate local demo path performs no model calls.
    """
    if not isinstance(actor, Actor):
        raise TypeError("Actor must come from the service session")
    if isinstance(expected_revision_seq, bool) or not isinstance(expected_revision_seq, int) or expected_revision_seq < 1:
        raise ValueError("expected_revision_seq is required")
    if not isinstance(provider, str) or not provider or not isinstance(model, str):
        raise ValueError("provider and model must be strings")
    catalog, rule_table = _catalog()
    pack = load_pack()
    source_manifest = [{k: source[k] for k in ("source_id", "sha256")}
                       for source in catalog["sources"] if "sha256" in source]
    source_hash = content_digest(source_manifest)
    rulebook = load_rules(Path(db_path).parent / 'knowledge_base')
    rules_digest = content_digest({'core':catalog,'parameters':rulebook.compiled})
    prompts = {stage: prompt_digest(pack, stage) for stage in STAGES}
    engine = content_digest({"base": base_chart.engine_build(), "relations": branch_relations.engine_build(),
                             "pipeline": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             "response_compat": hashlib.sha256(Path(__file__).with_name("response_compat.py").read_bytes()).hexdigest(),
                             "calendar": hashlib.sha256(Path(__file__).with_name("calendar_context.py").read_bytes()).hexdigest(),
                             "interpretation_evidence": hashlib.sha256(Path(__file__).with_name("interpretation_evidence.py").read_bytes()).hexdigest(),
                             "casting": hashlib.sha256((FOUNDATION / "casting_input.py").read_bytes()).hexdigest(),
                             "input_schema": hashlib.sha256((FOUNDATION / "liuyao_input_schema.json").read_bytes()).hexdigest(),
                             **{name: hashlib.sha256(Path(__file__).with_name(name + ".py").read_bytes()).hexdigest()
                                for name in ("runtime_contract", "selection_context", "validation_feedback", "interpretation_checks", "claim_rule_scope",
                                             "basic_analysis", "person_context", "selection_projection", "rulebook", "comprehensive_analysis",
                                             "day_month_analysis", "change_analysis", "strength_engine", "relation_effect_engine", "report_generator", "report_template", "profile_store", "buzhai")}})
    store = CaseStore(db_path)
    started = None
    terminal = False
    result = {"analysis_run_id": None, "status": "running", "chart": None, "report": None,
              "display_report": {}, "clarifying_questions": [], "unresolved": [], "stage_outputs": {}, "is_demo": provider == "demo"}
    result.update(rules_version=rulebook.version,parameter_version=rulebook.version,engine_build=engine,
                  ai_model={'provider':provider,'model':model},rules_snapshot=rulebook.compiled,
                  audit_report={'warnings':[],'fatal_errors':[],'rules_version':rulebook.version,'model_version':'V5 experimental'})
    projections = []
    def emit(event):
        if progress is not None:
            try:
                progress(event)
            except Exception:
                pass  # A disconnected UI does not abandon the retained run.
    def finish(status, *, error=None):
        nonlocal terminal
        result["status"] = status
        if error:
            result["error"] = error
        audit=result['audit_report']
        audit['unresolved']=result['unresolved']
        audit['selection_note_reviews']=result.get('selection_note_reviews',[])
        interpretation=result['stage_outputs'].get('interpretation',{})
        audit['fact_refs']=sorted({r for c in interpretation.get('claims',[]) for r in c.get('fact_refs',[])})
        audit['rule_refs']=sorted({r for c in interpretation.get('claims',[]) for r in c.get('rule_refs',[])})
        audit['conclusion_conditions']=interpretation.get('conclusion',{}).get('key_conditions',[])
        audit['conclusion_limits']=interpretation.get('conclusion',{}).get('limits',[])
        if error: audit['fatal_errors'].append(error)
        result["display_report"] = _display(result)
        store.finish_analysis(actor, case_id, started["analysis_run_id"], status=status,
            idempotency_key=started["analysis_run_id"] + ":finish", chart_snapshot=result["chart"],
            evidence=[{"source_manifest": source_manifest, "stage_projections": projections}], report=result,
            validation={"structural_contracts": len(result["stage_outputs"]) == 4 and status != "failed" and not result["is_demo"],
                        "validated_stages": list(result["stage_outputs"]), "semantic_review_required": True,
                        "verified_outcome_inferences": False, "stage_prompt_digests": prompts},
            unresolved=result["unresolved"], error=error)
        terminal = True
        emit({"stage": "finished", "analysis_run_id": started["analysis_run_id"], "status": status})
        return result
    try:
        started = store.start_analysis(actor, case_id, source_hash=source_hash, rules_digest=rules_digest,
            prompt_digest=content_digest(prompts), engine_build=engine, idempotency_key=ident("start"),
            expected_revision_seq=expected_revision_seq)
        result["analysis_run_id"] = started["analysis_run_id"]
        emit({"stage": "started", "analysis_run_id": result["analysis_run_id"]})
        exported = store.export_case(actor, case_id)
        frozen = next(r for r in exported["analysis_runs"] if r["analysis_run_id"] == result["analysis_run_id"])
        snapshot = frozen["input_snapshot"]
        result["chart"] = calculate_chart(snapshot["input"], rulebook)
        if provider == "demo":
            result["unresolved"] = ["本地演示未调用AI，未分析真念、取用或成败。"]
            return finish("partial")
        if provider_call is None:
            from liuyao_app.providers import generate_json
            provider_call = generate_json
        revision = next(r for r in exported["revisions"] if r["revision_seq"] == snapshot["revision_seq"])
        evidence = _evidence(snapshot, revision["recorded_at"])
        question = snapshot["input"]["question"]
        meta = {key: started[key] for key in ("case_id", "analysis_run_id", "input_snapshot_id")}
        meta.update(source_hash=source_hash, rules_digest=rules_digest, engine_build=engine)
        def call(stage, **payload):
            server_input = {"meta": {**meta, "prompt_digest": prompts[stage]}, **payload}
            projected_rules = server_input.get("rules", [])
            projections.append({"stage": stage, "input_digest": content_digest(server_input),
                "rules": [{"rule_id": r["rule_id"], "projected_status": r["status"], "usage": r["usage"],
                           "catalog_status": rule_table[r["rule_id"]]["status"],
                           "implementation_status": rule_table[r["rule_id"]]["implementation_status"]} for r in projected_rules]})
            output = _stage_call(store, actor, case_id, result["analysis_run_id"], stage, server_input,
                                 pack, provider, model, provider_call, emit, result["audit_report"]["warnings"])
            result["stage_outputs"][stage] = output
            return output
        def unresolved(output):
            result["clarifying_questions"] = [q["text"] for q in output.get("clarifying_questions", [])]
            result["unresolved"] = output.get("unresolved", []) or result["clarifying_questions"] or ["取用规则仍需核对。"]
            for q in output.get("clarifying_questions", []):
                store.append_context_event(actor, case_id, event_type="clarification_question",
                    content={**q, "analysis_run_id": result["analysis_run_id"]}, idempotency_key=ident("clarify"))
            return finish("unresolved")
        intent = call("intent", question=question, user_evidence=evidence, prior_clarifications=_prior_clarifications(snapshot, pack))
        if intent["status"] != "ready":
            return unresolved(intent)
        selected_intent = next(c for c in intent["candidates"] if c["candidate_id"] == intent["selected_candidate_id"])
        selection_rules = _selection_rules(rule_table, evidence, snapshot['input'].get('buzhai'))
        selection = call("selection", intent=selected_intent, user_evidence=evidence, rules=selection_rules,
                         information_scope=build_information_scope(snapshot["input"], result["chart"]))
        if selection["status"] != "ready":
            return unresolved(selection)
        for q in selection["clarifying_questions"]:
            store.append_context_event(actor, case_id, event_type="clarification_question",
                content={**q, "analysis_run_id": result["analysis_run_id"]}, idempotency_key=ident("clarify"))
        result['chart']['comprehensive_analysis']['use_selection']=select_use_lines(result['chart'],selection,rulebook)
        facts = _facts(result["chart"], evidence, selection)
        facts.extend(buzhai.structural_facts(result['chart']))
        result["selection_note_reviews"] = review_selection_notes(selection, snapshot["input"], result["chart"])
        for review in result['selection_note_reviews']:
            remaining=current_selection_notes({'unresolved':[review['original_text']]},snapshot['input'],result['chart'])
            review['current_text']='；'.join(remaining)
            review['current_status']='resolved' if not remaining else 'active' if review['current_text']==review['original_text'].rstrip('。') else 'partially_resolved'

        gaps = _gaps(snapshot["input"], result["chart"], selection, evidence)
        interpretation = call("interpretation", question=question, selection={**selection, "unresolved": current_selection_notes(selection,snapshot["input"],result["chart"])}, facts=facts,
            rules=_interpretation_rules(rule_table, selection_rules, result["chart"]), inferences=[], unresolved_gaps=gaps)
        result["unresolved"] = [u["impact"] for u in interpretation["uncertainties"]]
        result["clarifying_questions"] = list(dict.fromkeys(
            q["text"] for q in selection["clarifying_questions"] + interpretation["clarifying_questions"]))
        result['user_report']=fallback_report(interpretation,result['chart'])
        result['display_report'] = _display(result)
        emit({'analysis_run_id': result['analysis_run_id'], 'checkpoint': deepcopy(result),
              'report_timeout_seconds': REPORT_TIMEOUT_SECONDS})
        try:
            result["report"] = call("report", question=question, accepted_interpretation=interpretation, unresolved_gaps=gaps,analysis_chart=result['chart'])
            result['user_report']=build_user_report(result['report'])
            result['report_status'] = {'mode':'ai'}
        except StageFailure as exc:
            result['audit_report']['warnings'].append({'stage':'report','code':exc.code,'message':exc.message,'fallback':'已保留原始预测，使用程序排版'})
            result['report_status'] = {'mode':'fallback','code':exc.code,
                'message':'报告整理超时，已保留解卦结论和专业依据。' if exc.code=='timeout' else '报告整理未完成，已保留解卦结论和专业依据。'}
        result['user_report']['model_info']={'rules_version':rulebook.version,'model_version':'V5 experimental','timing':'精确应期未实现','strength':'实验综合强度已启用','calendar':result['chart']['calendar']['status']}
        return finish('completed')
    except Exception as exc:
        if started is None:
            raise  # Ownership/revision conflicts create no phantom running record.
        if terminal:
            raise
        if isinstance(exc, StageFailure):
            error = {"code": exc.code, "message": exc.message, "stage": exc.stage}
            for key in ("validation_detail", "attempts", "suggestion"):
                if getattr(exc, key) is not None:
                    error[key] = getattr(exc, key)
        else:
            error = {"code": "ANALYSIS_FAILURE", "message": "分析过程遇到错误，输入与已有过程已保留。", "type": type(exc).__name__}
        return finish("failed", error=error)
    finally:
        store.close()
