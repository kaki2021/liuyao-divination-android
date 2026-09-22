"""Directional ordinary-five-element structure for AI interpretation.

The source defines the matrix, not an unconditional effect of every possible
pair. These facts deliberately do not decide strength, activation, use-spirit
selection, benefit, outcome, or changed-line roles. In particular ``same`` means
the two elements match; it does not certify effective assistance.

Core source: 卜筮正术, ordinary matrix (B0918–B0919), 世应/身位
(B1573–B1574, B1602–B1603). Interpretation remains a separate operation.
"""
from __future__ import annotations

import base_chart


MATRIX_RULE = "relation.ordinary_wuxing"


def ordinary_relation(source_element, target_element):
    """Return the relation of SOURCE to TARGET in the ordinary matrix."""
    if (not isinstance(source_element, str) or
            not isinstance(target_element, str) or
            source_element not in base_chart.GENERATES or
            target_element not in base_chart.GENERATES):
        raise ValueError("Source and target must be known Chinese five-element labels")
    if source_element == target_element:
        return "same"
    if base_chart.GENERATES[source_element] == target_element:
        return "generates"
    if base_chart.CONTROLS[source_element] == target_element:
        return "controls"
    if base_chart.GENERATES[target_element] == source_element:
        return "is_generated_by"
    return "is_controlled_by"


def relation_statement(source_name, source_element, target_name, target_element):
    """Name both operands in the actual generating/controlling direction.

    The stored relation remains relative to SOURCE; the sentence instead uses
    active Chinese wording even for ``is_generated_by``/``is_controlled_by``.
    This is only an ordinary-element classification, never an efficacy claim.
    """
    if any(not isinstance(name, str) or not name.strip()
           for name in (source_name, target_name)):
        raise ValueError("Source and target must have nonempty object names")
    relation = ordinary_relation(source_element, target_element)
    if relation == "same":
        return f"{source_name}与{target_name}同属{source_element}"
    if relation == "generates":
        return f"{source_name}生{target_name}"
    if relation == "controls":
        return f"{source_name}克{target_name}"
    if relation == "is_generated_by":
        return f"{target_name}生{source_name}"
    return f"{target_name}克{source_name}"


def _fact(fact_id, subject, predicate, value, rule=MATRIX_RULE):
    # Same scalar fact contract as pipeline._fact, without a circular import.
    return dict(fact_id=fact_id, kind="calculation", subject=subject,
                predicate=predicate, value=value, source_rule_id=rule)


def _relation_fact(fact_id, source_name, source_element, target_name, target_element):
    relation = ordinary_relation(source_element, target_element)
    statement = relation_statement(source_name, source_element, target_name, target_element)
    return _fact(fact_id, source_name + " → " + target_name,
                 "凡五行：" + statement + "；仅结构分类，未判有效作用",
                 relation)


def _line_name(line):
    return f"本卦第{line['position']}爻{line['branch']}{line['element']}"


def _validated_lines(chart):
    lines = chart["main"]["lines"]
    if not isinstance(lines, list) or len(lines) != 6:
        raise ValueError("Six main-chart lines are required")
    indexed = {}
    for line in lines:
        position, branch = line["position"], line["branch"]
        if type(position) is not int or not 1 <= position <= 6 or position in indexed:
            raise ValueError("Main-chart positions must be distinct integers 1 through 6")
        if branch not in base_chart.BRANCH_ELEMENTS or line["element"] != base_chart.BRANCH_ELEMENTS[branch]:
            raise ValueError("Main-chart branch and element do not agree")
        indexed[position] = line
    for key in ("shi_position", "ying_position", "shi_body_position"):
        if type(chart[key]) is not int or chart[key] not in indexed:
            raise ValueError("Chart reference position must be an integer 1 through 6")
    return indexed


def build_relation_facts(chart):
    """Build 34 scalar structure facts, plus 12 with a computed calendar.

    Stable specialist IDs: REL_YING_TO_SHI and REL_GUA_BODY_TO_SHI_BODY.
    Directed line IDs: REL_LINE_<source>_TO_<target> (30, excluding self).
    Calendar IDs: CAL_DAY_TO_LINE_<target>, CAL_MONTH_TO_LINE_<target>.

    Gua-body absence is retained explicitly; its element can be classified even
    when its branch has no matching main-chart line. That does not resolve the
    efficacy of an absent position. No input object is modified.
    """
    lines = _validated_lines(chart)
    body_branch = chart["gua_body_branch"]
    if body_branch not in base_chart.BRANCH_ELEMENTS:
        raise ValueError("Gua-body branch must be a known earthly branch")
    body_element = base_chart.BRANCH_ELEMENTS[body_branch]
    body_positions = [p for p, line in sorted(lines.items()) if line["branch"] == body_branch]
    if sorted(chart["gua_body_positions"]) != body_positions:
        raise ValueError("Gua-body matching positions do not agree with the main chart")
    facts = [_fact(
        "RELATION_EVIDENCE_SCOPE", "本次凡五行关系事实", "计算范围",
        "只分类源相对目标的凡五行结构；不是每一爻对都已发生有效作用。"
        "同五行不自动等于有效生扶；生克分类不自动确定吉凶、旺衰、用神或目标成败。"
        "真五行适用问题另行核定，不由此表替代。")]
    for source_position in range(1, 7):
        source = lines[source_position]
        for target_position in range(1, 7):
            if source_position == target_position:
                continue
            target = lines[target_position]
            facts.append(_relation_fact(
                f"REL_LINE_{source_position}_TO_{target_position}",
                _line_name(source), source["element"],
                _line_name(target), target["element"]))

    shi, ying = lines[chart["shi_position"]], lines[chart["ying_position"]]
    facts.append(_relation_fact("REL_YING_TO_SHI", "应（" + _line_name(ying) + "）",
                                ying["element"], "世（" + _line_name(shi) + "）", shi["element"]))
    body_line = lines[chart["shi_body_position"]]
    match_label = ("本卦第" + "、".join(map(str, body_positions)) + "爻" if body_positions else "本卦未现")
    facts.append(_relation_fact(
        "REL_GUA_BODY_TO_SHI_BODY", f"卦身（位：{body_branch}{body_element}；{match_label}）",
        body_element, "世身（身：" + _line_name(body_line) + "）", body_line["element"]))
    facts.append(_fact("REL_GUA_BODY_PRESENT", "卦身（位）", "地支是否在本卦出现",
                       bool(body_positions), "chart.gua_body"))

    calendar = chart.get("calendar") or {}
    if calendar.get("status") == "computed":
        for period, label in (("day", "日支"), ("month", "月支")):
            pillar = calendar["pillars"][period]
            if not isinstance(pillar, str) or len(pillar) != 2 or pillar[1] not in base_chart.BRANCH_ELEMENTS:
                raise ValueError("Computed calendar must provide a two-character day/month pillar")
            branch = pillar[1]
            element = base_chart.BRANCH_ELEMENTS[branch]
            for position in range(1, 7):
                target = lines[position]
                facts.append(_relation_fact(
                    f"CAL_{period.upper()}_TO_LINE_{position}", f"{label}{branch}{element}",
                    element, _line_name(target), target["element"]))
    return facts
