"""Read-only, deterministic foundation shared by the screen and AI inputs.

The five-element matrix is the ordinary branch matrix. The six combination
pairs are explicit in 卜筮正术 B1066 and B1278–B1279; their nominal element
does not establish effective transformation. Form/harm labels retain the
independent definitions of 卜筮正术补充 PDF pages 2–5.

This module never selects a use spirit, applies a global age-based matrix
switch, scores comprehensive strength, or generates a forecast.
"""
from __future__ import annotations

import itertools

import base_chart
import branch_relations
from liuyao_app.interpretation_evidence import build_relation_facts


COMBINATION_RULE = "relation.six_combination_pairs"
SIX_COMBINATIONS = {
    frozenset("子丑"): "土", frozenset("寅亥"): "木",
    frozenset("卯戌"): "火", frozenset("辰酉"): "金",
    frozenset("巳申"): "水", frozenset("午未"): "土",
}


def _fact(fact_id, subject, predicate, value, rule):
    return dict(fact_id=fact_id, kind="calculation", subject=subject,
                predicate=predicate, value=value, source_rule_id=rule)


def _item(item_id, text, *rules):
    return {"id": item_id, "text": text, "rule_ids": list(dict.fromkeys(rules))}


def _section(section_id, title, items):
    return {"id": section_id, "title": title, "items": items}


def _line_name(line):
    return f"第{line['position']}爻{line['branch']}{line['element']}"


def _relation_text(fact):
    # The relation direction and its wording come from the same fact delivered
    # to AI. Keep the common scope explanation once at section level in the UI.
    return fact["predicate"].removeprefix("凡五行：").removesuffix("；仅结构分类，未判有效作用")


def _pair_labels(chart, lines):
    """Use the chart's already-classified pairs; support bare base charts too."""
    pairs = chart.get("line_pair_relations")
    if pairs is None:
        pairs = []
        for left, right in itertools.combinations(lines, 2):
            result = branch_relations.classify_pair(left["branch"], right["branch"])
            if result["relations"]:
                pairs.append({"positions": [left["position"], right["position"]], **result})
    return {tuple(pair["positions"]): pair["relations"] for pair in pairs}


def build_basic_analysis(chart):
    """Return deterministic display sections and additional scalar AI facts.

    ``facts`` owns the existing REL_* / CAL_*_TO_LINE_* directional facts,
    CHART_PALACE_STAGE, optional CHANGED_CHART_PALACE_STAGE, and matched
    PAIR_<a>_<b>_SIX_COMBINATION nominal elements. It does not repeat the
    pipeline's chart positions, calendar pillars, month categories or form/harm
    facts. UI sections summarize those existing chart values without changing
    the chart. There are at most 63 facts (including a computed calendar).
    """
    facts = build_relation_facts(chart)  # validates main positions and elements
    by_id = {fact["fact_id"]: fact for fact in facts}
    main = chart["main"]
    lines = sorted(main["lines"], key=lambda line: line["position"])
    indexed = {line["position"]: line for line in lines}
    stage = main["palace_stage"]
    if stage not in base_chart.PALACE_STAGES:
        raise ValueError("Unknown main-chart palace stage")
    facts.append(_fact("CHART_PALACE_STAGE", "主卦", "八宫卦序位置", stage,
                       "chart.palace_sequence"))
    overview = [
        _item("palace", f"{main['name']}归{main['palace']}宫，宫五行为{main['palace_element']}，"
              f"卦序为{stage}。", "chart.palace_sequence", "chart.palace_elements"),
        _item("kinship_basis", f"本卦六亲以{main['palace']}宫{main['palace_element']}为参照，"
              "按各爻地支五行的生、克、同类关系生成。", "relation.ordinary_kinship"),
    ]
    moving = chart["moving_positions"]
    changed = chart["changed_structure"]
    if moving:
        if changed is None:
            raise ValueError("Moving lines require a changed-chart structure")
        changed_stage = changed["palace_stage"]
        if changed_stage not in base_chart.PALACE_STAGES:
            raise ValueError("Unknown changed-chart palace stage")
        facts.append(_fact("CHANGED_CHART_PALACE_STAGE", "变卦", "八宫卦序位置",
                           changed_stage, "chart.palace_sequence"))
        overview.append(_item("dynamics", "第" + "、".join(map(str, moving)) +
                              f"爻发动；变卦为{changed['name']}，归{changed['palace']}宫，"
                              f"卦序为{changed_stage}。", "casting.four_states", "chart.palace_sequence"))
    else:
        overview.append(_item("dynamics", "静卦，六爻均不发动，没有独立变卦。", "casting.four_states"))

    shi, ying = indexed[chart["shi_position"]], indexed[chart["ying_position"]]
    body = indexed[chart["shi_body_position"]]
    matches = chart["gua_body_positions"]
    gua_body = chart["gua_body_branch"]
    presence = ("在本卦第" + "、".join(map(str, matches)) + "爻出现" if matches else "本卦未见对应地支")
    references = [
        _item("shi_ying", f"世爻为{_line_name(shi)}，应爻为{_line_name(ying)}；"
              + _relation_text(by_id["REL_YING_TO_SHI"]) + "。",
              "chart.shi_ying", "relation.ordinary_wuxing"),
        _item("body_positions", f"世身在{_line_name(body)}；卦身为{gua_body}"
              f"{base_chart.BRANCH_ELEMENTS[gua_body]}，{presence}。",
              "chart.shi_body", "chart.gua_body"),
        _item("body_relation", _relation_text(by_id["REL_GUA_BODY_TO_SHI_BODY"]) + "。",
              "relation.ordinary_wuxing"),
    ]

    calendar = chart.get("calendar") or {}
    calendar_items = []
    if calendar.get("status") == "computed":
        month_element = base_chart.BRANCH_ELEMENTS[calendar["pillars"]["month"][1]]
        for line in lines:
            pos = line["position"]
            category = base_chart.ordinary_month_strength(month_element, line["element"])
            recorded = line.get("ordinary_month_strength", category)
            if recorded != category:
                raise ValueError("Recorded month category disagrees with the computed calendar")
            day_fact = by_id[f"CAL_DAY_TO_LINE_{pos}"]
            month_fact = by_id[f"CAL_MONTH_TO_LINE_{pos}"]
            calendar_items.append(_item(f"calendar_line_{pos}",
                f"{_line_name(line)}：月令分类为{category}；"
                + _relation_text(month_fact) + "；" + _relation_text(day_fact) + "。",
                "relation.ordinary_month_strength", "relation.ordinary_wuxing"))
        calendar_items.append(_item("calendar_scope", "旺、相、休、囚、死是单一月令分类；"
            "其中“死”不表示人物死亡，也不直接确定事情成败。",
            "relation.ordinary_month_strength"))
    else:
        calendar_items.append(_item("calendar_unavailable", "该记录尚无可用于排盘的起卦时间，"
            "未生成日月关系；已有卦象关系仍可查看。"))

    pair_items = [_item("ordinary_scope", "以下列出本卦各爻之间的凡五行结构关系，"
        "生克方向由程序确定；是否产生实际作用及对本次目标的影响由综合解读说明。",
        "relation.ordinary_wuxing")]
    branch_items = []
    classified = _pair_labels(chart, lines)
    for left, right in itertools.combinations(lines, 2):
        a, b = left["position"], right["position"]
        relation_fact = by_id[f"REL_LINE_{a}_TO_{b}"]
        pair_items.append(_item(f"line_pair_{a}_{b}", _relation_text(relation_fact) + "。",
                                "relation.ordinary_wuxing"))
        labels, rules = [], []
        nominal_element = SIX_COMBINATIONS.get(frozenset((left["branch"], right["branch"])))
        if nominal_element is not None:
            labels.append(f"六合，名义化行为{nominal_element}")
            rules.append(COMBINATION_RULE)
            facts.append(_fact(f"PAIR_{a}_{b}_SIX_COMBINATION",
                f"主卦第{a}爻{left['branch']}与第{b}爻{right['branch']}",
                "六合名义化行（未判成化）", nominal_element, COMBINATION_RULE))
        for relation in classified.get((a, b), []):
            labels.append(f"{relation['label']}（{relation['category_label']}）")
            rules.extend(relation["rule_ids"])
        if labels:
            branch_items.append(_item(f"branch_pair_{a}_{b}",
                _line_name(left) + "与" + _line_name(right) + "：" + "；".join(labels) + "。", *rules))
    if not branch_items:
        branch_items.append(_item("no_branch_pairs", "本卦各爻地支未匹配到六合、互形或互害配对。",
            COMBINATION_RULE, "relation.three_forms_pairs", "relation.six_harms_pairs"))
    branch_items.append(_item("branch_scope", "此处仅列配对和类别；六合不改写原地支五行，"
        "不据此认定已经成化。互形、互害也不单独判吉凶。", COMBINATION_RULE,
        "relation.three_forms_pairs", "relation.six_harms_pairs"))

    return {"sections": [
        _section("overview", "归宫与动变", overview),
        _section("references", "世应与身位", references),
        _section("calendar", "日月与各爻", calendar_items),
        _section("line_relations", "本卦爻间关系", pair_items),
        _section("branch_relations", "六合、互形与互害", branch_items),
    ], "facts": facts}
