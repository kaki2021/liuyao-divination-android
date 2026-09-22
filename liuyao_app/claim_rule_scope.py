"""Bounded rule capabilities for explanations of the selected functional role.

Selection rules explain selected roles. Outcome interpretation requires
separate interpretation rules and traceable evidence. This check preserves
model references while allowing rule-backed forecasts. It is not a general
semantic approval engine.
"""
from __future__ import annotations

import json
import re


_HELP = (
    "这段只有取用或展示依据。仅说明本次主目标的功能归属时，须使用 support、neutral，"
    "引用 FUNCTION_SELECTION、MATCHING_LINES 和本次主候选实际使用的取用规则，"
    "爻位引用只能对应这些匹配爻。若不符合，可删除这段重复说明，同时调整建议及结论的"
    "claim_refs；真正的趋势或得失解释须引用实际适用的 interpretation 规则。"
    "不要附加无关规则来通过检查。"
)
_FORECAST_HELP = (
    "取用说明只能解释对象与六亲、候选爻的对应。趋势判断需要实际作用、强弱或解释规则支持。"
)
_LINE_FACT = re.compile(r"LINE_([1-6])_(BRANCH|ELEMENT|RELATIVE_CODE)$")
_PIVOT = re.compile(r"[。；;！？!?\n，,]|但是|然而|不过|可是|但|因此|所以|故而|可见")
_NEGATED = re.compile(
    r"不表示|不代表|不意味着|不等于|不是|并非|并不|不能|不可|不应|不会|"
    r"不保证|无法保证|没有依据|没有证据|无法判|不能判|尚未判|未必|不一定|"
    r"不确定|尚不能|尚不知|无法断|不构成|不是成败|不是结果"
)
_OUTCOME = (
    r"签成|签下|签订成功|签署成功|签约成功|签约失败|成功|失败|成事|不成|"
    r"达成|落地|顺利|获利|盈利|赚钱|得财|破财|受损|受益|损失|有利|不利|"
    r"有益|有害|吃亏|获益|亏损|吉利|大吉|大凶|凶险|遭拒|拒签"
)
_PREDICTION = re.compile(
    rf"(?:一定|必然|必定|肯定|必会|必能|势必|必将|保证|确保|确定|注定|"
    rf"大概率|有望|会|将|能够|能|可以|可)(?:[^。；;！？!?\n]{{0,18}})(?:{_OUTCOME})|"
    rf"(?:预示|预言|证明|说明|意味着|代表|导致|带来|使得|判断为|结论是|断为|"
    rf"结果为)(?:[^。；;！？!?\n]{{0,16}})(?:{_OUTCOME})|"
    rf"(?:下月|下个月|明日|明天|本月|近期|届时)(?:[^。；;！？!?\n]{{0,12}})(?:{_OUTCOME})|"
    rf"(?:签约|合同|项目|交易|主体|自身|求测者|对方|本卦|此卦)(?:[^。；;！？!?\n]{{0,5}})"
    rf"(?:必成|必败|已成|已败|主吉|主凶|吉利|大吉|大凶|受损|受益|获利|亏损)|"
    r"(?:成功率|签成概率|签约概率)\s*(?:为|是|达到|[:：])?\s*\d+(?:\.\d+)?\s*%"
)


def _list(value):
    return value if isinstance(value, list) else []


def _table(value, key):
    return {item[key]: item for item in _list(value)
            if isinstance(item, dict) and isinstance(item.get(key), str)}


def _strings(value):
    return value if isinstance(value, list) and all(isinstance(x, str) for x in value) else []


def _fields(item, path, advice=False):
    keys = ("text",) if advice else ("statement",)
    for key in keys:
        if isinstance(item.get(key), str):
            yield path + "." + key, item[key]
    if not advice and isinstance(item.get("proposition"), dict):
        for key in ("subject", "predicate", "value"):
            value = item["proposition"].get(key)
            if isinstance(value, str):
                yield path + ".proposition." + key, value
    for key in (("conditions",) if advice else ("assumptions", "limitations")):
        for index, value in enumerate(_strings(item.get(key))):
            yield f"{path}.{key}[{index}]", value


def _has_forecast(text):
    """Recognize a finite set of affirmative scope jumps, not all predictions."""
    for clause in _PIVOT.split(text):
        # A boilerplate disclaimer does not authorize an affirmative sentence
        # immediately following it, even if the model omitted punctuation.
        clause = re.sub(r"(?:这|此|仅)?(?:不是|并非)(?:成败结论|成败判断|预测|预言)", "", clause)
        # Question descriptions do not assert their possible answers. Keep
        # following affirmative clauses independent via punctuation/pivots.
        if re.search(r"(?:问|询问|关心|关切|关注|想知道|想了解).{0,35}(?:能否|是否|会不会)", clause):
            continue
        # Do not let a double negative disguise an affirmative guarantee.
        double_negative = re.search(r"不是不能|并非不能|不能不|不会不|不可能不", clause)
        if _NEGATED.search(clause) and not double_negative:
            continue
        if _PREDICTION.search(clause):
            return True
    return False


def _selection_explanation(claim, server_input, rules, facts):
    """Admit only neutral support explanations tied to the selected candidate."""
    if (claim.get("dimension") != "support" or claim.get("direction") != "neutral"
            or claim.get("requires_review") is not True or claim.get("inference_refs") != []):
        return False
    selection = server_input.get("selection")
    if not isinstance(selection, dict) or selection.get("status") != "ready":
        return False
    candidates = _table(selection.get("candidates"), "candidate_id")
    primary = candidates.get(selection.get("selected_primary_id"))
    if not primary or primary.get("purpose") != "primary" or primary.get("subject_reference"):
        return False
    relative = primary.get("six_relative")
    if relative not in ("parents", "siblings", "offspring", "wealth", "official_ghost"):
        return False
    refs = _strings(claim.get("rule_refs"))
    primary_refs = set(_strings(primary.get("rule_refs")))
    if not refs or any(ref not in rules for ref in refs):
        return False
    cited = [rules[ref] for ref in refs]
    if any(rule.get("status") != "approved" or rule.get("source_role") not in ("core", "core_supplement")
           or rule.get("usage") not in ("selection", "display") for rule in cited):
        return False
    if not any(ref in primary_refs and rules[ref].get("usage") == "selection" for ref in refs):
        return False
    fact_refs = _strings(claim.get("fact_refs"))
    cited_fact_sources = {facts[ref].get("source_rule_id") for ref in fact_refs if ref in facts}
    # A different candidate's selection rule is not a license to reinterpret
    # the primary target. The rule used to compute a cited relative or match is
    # also relevant even when the candidate itself cited only functional rules.
    if any(rules[ref].get("usage") == "selection" and ref not in primary_refs
           and ref not in cited_fact_sources for ref in refs):
        return False
    if not {"FUNCTION_SELECTION", "MATCHING_LINES"}.issubset(fact_refs):
        return False
    function = facts.get("FUNCTION_SELECTION", {})
    matching = facts.get("MATCHING_LINES", {})
    if (function.get("kind") != "selection" or function.get("value") != relative
            or function.get("source_rule_id") not in primary_refs or matching.get("kind") != "selection"):
        return False
    try:
        positions = json.loads(matching.get("value", ""))
    except (TypeError, ValueError):
        return False
    if (not isinstance(positions, list) or any(type(p) is not int or not 1 <= p <= 6 for p in positions)
            or len(set(positions)) != len(positions)):
        return False
    # Verify the complete matching set rather than trusting a declared match.
    relative_facts = [facts.get(f"LINE_{pos}_RELATIVE_CODE", {}) for pos in range(1, 7)]
    if any(fact.get("kind") != "chart" or not isinstance(fact.get("value"), str) for fact in relative_facts):
        return False
    expected = [pos for pos, fact in enumerate(relative_facts, 1) if fact["value"] == relative]
    if sorted(positions) != expected:
        return False
    for ref in fact_refs:
        fact = facts.get(ref)
        if not fact:
            return False
        if ref in ("FUNCTION_SELECTION", "MATCHING_LINES", "CHART_PALACE", "PALACE_ELEMENT"):
            continue
        if fact.get("kind") == "context":
            continue
        line = _LINE_FACT.fullmatch(ref)
        if not line or int(line[1]) not in positions or fact.get("kind") != "chart":
            return False
    return True


def claim_rule_errors(output, server_input):
    """Return all bounded rule-scope issues without rewriting any model data."""
    if not isinstance(output, dict) or not isinstance(server_input, dict):
        return []
    rules = _table(server_input.get("rules"), "rule_id")
    facts = _table(server_input.get("facts"), "fact_id")
    errors = []
    explanation_ids = set()
    for index, claim in enumerate(_list(output.get("claims"))):
        if not isinstance(claim, dict) or claim.get("kind") != "ai_hypothesis":
            continue
        path = f"$.claims[{index}]"
        cited = [rules[ref] for ref in _strings(claim.get("rule_refs")) if ref in rules]
        if any(rule.get("usage") == "interpretation" for rule in cited):
            continue  # Core source status and unknown references stay strict.
        if not _selection_explanation(claim, server_input, rules, facts):
            errors.append({"code": "HYPOTHESIS_INTERPRETATION_RULE_REQUIRED", "path": path + ".rule_refs", "message": _HELP})
            continue
        if isinstance(claim.get("claim_id"), str):
            explanation_ids.add(claim["claim_id"])
        for field, text in _fields(claim, path):
            if _has_forecast(text):
                errors.append({'code':'SELECTION_EXPLANATION_SCOPE_EXCEEDED','path':field,'message':_FORECAST_HELP})
                break
    for index, advice in enumerate(_list(output.get("advice"))):
        if not isinstance(advice, dict) or advice.get("basis") != "system_interpretation":
            continue
        refs = set(_strings(advice.get("claim_refs")))
        if not refs or not refs.issubset(explanation_ids):
            continue
        for field, text in _fields(advice, f'$.advice[{index}]', advice=True):
            if _has_forecast(text):
                errors.append({'code':'SELECTION_ADVICE_SCOPE_EXCEEDED','path':field,'message':_FORECAST_HELP})
                break
    return errors
