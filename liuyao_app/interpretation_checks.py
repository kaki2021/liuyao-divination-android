"""Limited, deterministic checks for known interpretation failure patterns.

This is not a natural-language proof system or a replacement for review. It
rejects only identifiable contradictions and two narrowly defined scope jumps;
ambiguous actor references are left alone. No response is rewritten here.
"""
from __future__ import annotations

import re


_ELEMENT_PAIR = re.compile(r"[子丑寅卯辰巳午未申酉戌亥][木火土金水]")
_NEGATED = re.compile(
    r"并非|不是|并不|不能|不应|不表示|不代表|不意味着|不等于|不一定|未必|"
    r"无法据此|没有依据|没有证据|尚未确认|若|如果|假如|假设|除非")
_GENERIC_RULES = {
    "interpretation.no_intrinsic_omen", "interpretation.three_self_references",
    "interpretation.analysis_scale", "interpretation.gains_before_success",
    "interpretation.body_overlap", "interpretation.functional_role",
}


def _clauses(text):
    for clause in re.split(r"[。；;！？!?\n，,]", str(text)):
        if clause and not _NEGATED.search(clause):
            yield clause


def _text_fields(item, prefix):
    if not isinstance(item, dict):
        return
    for field in ("statement", "answer", "description", "explanation", "impact"):
        if isinstance(item.get(field), str):
            yield prefix + "." + field, item[field]
    proposition = item.get("proposition")
    if isinstance(proposition, dict) and isinstance(proposition.get("value"), str):
        yield prefix + ".proposition.value", proposition["value"]


def _branch_element(name):
    matches = _ELEMENT_PAIR.findall(name)
    return matches[-1] if matches else None


def _relation_parts(fact):
    source, target = fact.get("source"), fact.get("target")
    if not isinstance(source, str) or not isinstance(target, str):
        parts = re.split(r"\s*(?:→|->)\s*", str(fact.get("subject", "")), maxsplit=1)
        if len(parts) != 2:
            return None
        source, target = parts
    if fact.get("value") not in ("controls", "is_controlled_by", "generates", "is_generated_by"):
        return None
    return source, target, fact["value"]


def _alternatives(values):
    return "(?:" + "|".join(re.escape(x) for x in sorted(set(values), key=len, reverse=True) if x) + ")"


def _aliases(name):
    result = [name]
    pair = _branch_element(name)
    if pair:
        result.append(pair)
    for label in ("日支", "月支", "世身", "卦身"):
        if label in name:
            result.append(label)
    if "日支" in name:
        result.append("日辰")
    if "月支" in name:
        result.append("月令")
    position = re.search(r"第([1-6])爻", name)
    if position:
        pos = position[1]
        result.extend(("第" + pos + "爻", "一二三四五六"[int(pos) - 1] + "爻"))
    return result


def _subject_is_target(claim, fact, target, facts):
    proposition = claim.get("proposition")
    subject = str(proposition.get("subject", "")) if isinstance(proposition, dict) else ""
    if any(alias in subject for alias in _aliases(target)):
        return True
    position = re.search(r"_TO_LINE_([1-6])$", str(fact.get("fact_id", "")))
    if not position:
        return False
    for label, ref in (("世身", "BODY_POSITION"), ("世爻", "SHI_POSITION"), ("应爻", "YING_POSITION")):
        if label in subject and str(facts.get(ref, {}).get("value")) == position[1]:
            return True
    return False


def _direction_error(claim, fact, facts, related):
    parts = _relation_parts(fact)
    if not parts:
        return None
    source, target, relation = parts
    inverse = relation.startswith("is_")
    actual_agent, actual_patient = (target, source) if inverse else (source, target)
    wrong_agent, wrong_patient = actual_patient, actual_agent
    action = "克" if "control" in relation else "生"
    action_pattern = r"克(?:制)?" if action == "克" else r"(?:生(?:扶|助)?|扶助)"
    agent = _alternatives(_aliases(wrong_agent))
    patient = _alternatives(_aliases(wrong_patient))
    # Do not cross punctuation or a second relational verb while matching actors.
    filler = r"[^，,。；;克生受被]{0,14}"
    active = re.compile(agent + filler + action_pattern + filler + patient)
    active_to = re.compile(agent + filler + r"对" + filler + patient + filler + action_pattern)
    passive = re.compile(patient + filler + r"(?:受|被)" + filler + agent + filler + action_pattern)
    a_pair, p_pair = _branch_element(wrong_agent), _branch_element(wrong_patient)
    elemental = re.compile(re.escape(a_pair[-1]) + action + re.escape(p_pair[-1])) if a_pair and p_pair else None
    period = "日" if "日支" in source else "月" if "月支" in source else None
    # Shorthand such as “受日支克制” is checked only with one unambiguous target.
    same_period = [x for x in related if _relation_parts(x) and period and
                   (period + "支") in _relation_parts(x)[0]]
    target_is_unique = len({(_relation_parts(x)[1], x.get("value")) for x in same_period}) == 1
    implicit = bool(inverse and period and target_is_unique and _subject_is_target(claim, fact, target, facts))
    shorthand = re.compile(("(?:日支|日辰)" if period == "日" else "(?:月支|月令)") +
                           r"[^，,。；;克生相受被]{0,8}" + action_pattern) if implicit else None
    for field, text in _text_fields(claim, ""):
        for clause in _clauses(text):
            if active.search(clause) or active_to.search(clause) or passive.search(clause) or (elemental and elemental.search(clause)):
                return field, actual_agent + action + actual_patient
            if shorthand and shorthand.search(clause):
                # “与日支存在源受目标所克” does not assert the target is controlled.
                if re.search(r"(?:受|被).{0,5}" + shorthand.pattern, clause) or field == ".proposition.value":
                    return field, actual_agent + action + actual_patient
    return None


def _only_generic_rules(claim, rules):
    refs = claim.get("rule_refs", [])
    for ref in refs if isinstance(refs, list) else []:
        if not isinstance(ref, str):
            continue
        rule = rules.get(ref)
        if (rule and rule.get("usage") == "interpretation" and
                ref not in _GENERIC_RULES and not ref.startswith(("chart.", "casting.", "relation."))):
            # A specific rule requires separate review of its scope; do not
            # pretend this pattern checker understands every future rule.
            return False
    return True


def interpretation_errors(output, server_input):
    """Return bounded structured feedback; malformed shapes are schema's job."""
    if not isinstance(output, dict) or not isinstance(server_input, dict):
        return []
    fact_items, rule_items = server_input.get("facts"), server_input.get("rules")
    facts = {f["fact_id"]: f for f in (fact_items if isinstance(fact_items, list) else [])
             if isinstance(f, dict) and isinstance(f.get("fact_id"), str)}
    rules = {r["rule_id"]: r for r in (rule_items if isinstance(rule_items, list) else [])
             if isinstance(r, dict) and isinstance(r.get("rule_id"), str)}
    errors, seen = [], set()

    def add(code, message, path):
        if (code, path) not in seen and len(errors) < 40:
            errors.append({"code": code, "message": message, "path": path})
            seen.add((code, path))

    claims = output.get("claims", [])
    for index, claim in enumerate(claims if isinstance(claims, list) else []):
        if not isinstance(claim, dict):
            continue
        path = f"$.claims[{index}]"
        refs = claim.get("fact_refs", [])
        related = [facts[r] for r in refs if isinstance(r, str) and r in facts] if isinstance(refs, list) else []
        for fact in related:
            mismatch = _direction_error(claim, fact, facts, related)
            if mismatch:
                field, correct = mismatch
                add("RELATION_DIRECTION_MISMATCH",
                    f"所引事实 {fact['fact_id']} 的方向是“{correct}”；当前表述将生克双方颠倒。请依据事实重写并复核受其影响的结论，不把结构方向写成已判有效作用。",
                    path + field)
        if _only_generic_rules(claim, rules):
            texts = list(_text_fields(claim, path))
            full = " ".join(text for _, text in texts)
            absent = (any(f.get("fact_id") == "REL_GUA_BODY_PRESENT" and f.get("value") is False for f in related)
                      or bool(re.search(r"卦身.{0,12}(?:未现|未出现|缺位|缺失)", full)))
            moving = bool(re.search(r"世爻.{0,15}(?:唯一动爻|独动)|唯一动爻.{0,10}世", full))
            for field, text in texts:
                for clause in _clauses(text):
                    if absent and re.search(r"(?:缺少|缺乏|没有|缺失).{0,16}(?:核心支点|成形位|现实支撑|现实支点)", clause):
                        add("UNSUPPORTED_SCOPE", "卦身缺位只证明该地支未在本卦出现；所引定位或通用规则没有授权据此断言现实事项缺少核心支点。请删除这一跨越或提供适用的具体依据。", field)
                    if moving and re.search(r"(?:主动权|决定权).{0,12}(?:在|归|掌握)|(?:关键|成败).{0,8}在于.{0,12}(?:主动|推动)|(?:主动权|决定权).{0,10}(?:自己|我方|求测者)", clause):
                        add("UNSUPPORTED_SCOPE", "世爻为唯一动爻只证明变化位置；所引动变或通用规则没有授权据此确定现实主动权属于求测者。请区分盘面事实、条件解释和行动建议。", field)

    has_calendar = any(facts.get(key, {}).get("value") not in (None, "", False)
                       for key in ("CAST_TIME", "CALENDAR_DAY", "CALENDAR_MONTH"))
    if has_calendar:
        fields = []
        for index, claim in enumerate(claims if isinstance(claims, list) else []):
            fields.extend(_text_fields(claim, f"$.claims[{index}]"))
        fields.extend(_text_fields(output.get("conclusion"), "$.conclusion"))
        uncertainties = output.get("uncertainties", [])
        for index, item in enumerate(uncertainties if isinstance(uncertainties, list) else []):
            fields.extend(_text_fields(item, f"$.uncertainties[{index}]"))
        missing = re.compile(
            r"(?:未提供|没有提供|未给出|缺少|缺失|缺乏|没有|缺).{0,8}(?:实际)?起卦(?:的)?(?:日期|时间)|"
            r"起卦(?:的)?(?:日期|时间)(?:、[^，,。；;]{0,20})?(?:仍|尚|还|目前|本次|实际|是|为){0,2}"
            r"(?:未提供|没有提供|未给出|缺失|未知|不明)")
        for field, text in fields:
            # A correction quoting an earlier stage must remain expressible.
            if re.search(r"前阶段|前一阶段|此前|先前|曾说|曾称|曾认为", text) and re.search(r"现已|实际已|已经提供|已提供|已知|已计算|已补充", text):
                continue
            for clause in _clauses(text):
                if missing.search(clause):
                    add("CONTEXT_CONTRADICTION", "本次输入已有实际起卦时间或日月排盘事实，不能断言用户未提供起卦日期；请区分阶段未收到信息与实际缺失，并保留仍真实存在的算法限制。", field)
    return errors
