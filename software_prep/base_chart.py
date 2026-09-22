"""Deterministic base chart under the definitions of 卜筮正术.

No calendar conversion, global true-element switch, use-spirit selection or
outcome prediction is implemented here. Lines are always bottom to top.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
STATES = {
    "old_yin": (0, True), "young_yang": (1, False),
    "young_yin": (0, False), "old_yang": (1, True),
}
TRIGRAMS = {
    "乾": (1, 1, 1), "兑": (1, 1, 0), "离": (1, 0, 1), "震": (1, 0, 0),
    "巽": (0, 1, 1), "坎": (0, 1, 0), "艮": (0, 0, 1), "坤": (0, 0, 0),
}
PALACE_ELEMENTS = {"乾": "土", "坤": "土", "震": "木", "巽": "木", "艮": "金", "兑": "金", "坎": "水", "离": "火"}
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
BRANCH_ELEMENTS = dict(zip(BRANCHES, "水土木木土火火土金金土水"))
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
PURE_BRANCHES = {
    "乾": "子寅辰午申戌", "兑": "巳卯丑亥酉未", "离": "卯丑亥酉未巳", "震": "子寅辰午申戌",
    "巽": "丑亥酉未巳卯", "坎": "寅辰午申戌子", "艮": "辰午申戌子寅", "坤": "未巳卯丑亥酉",
}
PALACE_STAGES = ("本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂")
SHI_POSITIONS = (6, 1, 2, 3, 4, 5, 4, 3)
SPIRITS = ("青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武")
STEM_SPIRIT_START = dict(zip("甲乙丙丁戊己庚辛壬癸", (0, 0, 1, 1, 2, 3, 4, 4, 5, 5)))
TRIGRAM_BY_BITS = {bits: name for name, bits in TRIGRAMS.items()}
RELATIVE_CODES = {"父母": "parents", "兄弟": "siblings", "子孙": "offspring", "妻财": "wealth", "官鬼": "official_ghost"}


def palace_index():
    """Generate eight palaces independently of the auxiliary 64-table."""
    result = {}
    for palace, trigram in TRIGRAMS.items():
        bits = list(trigram + trigram)
        states = [tuple(bits)]
        for i in range(5):
            bits[i] ^= 1
            states.append(tuple(bits))
        bits[3] ^= 1
        states.append(tuple(bits))
        for i in range(3):
            bits[i] ^= 1
        states.append(tuple(bits))
        for stage, value in enumerate(states):
            if value in result:
                raise RuntimeError("Duplicate palace pattern")
            result[value] = (palace, stage)
    return result


PALACE_BY_BITS = palace_index()


def ordinary_relative(palace_element, line_element):
    if palace_element not in GENERATES or line_element not in GENERATES:
        raise ValueError("Unknown five-element label")
    if line_element == palace_element:
        return "兄弟"
    if GENERATES[line_element] == palace_element:
        return "父母"
    if GENERATES[palace_element] == line_element:
        return "子孙"
    if CONTROLS[palace_element] == line_element:
        return "妻财"
    return "官鬼"


def ordinary_month_strength(month_element, line_element):
    """Month-only qualitative label; not a day/month outcome formula."""
    if month_element not in GENERATES or line_element not in GENERATES:
        raise ValueError("Unknown five-element label")
    if month_element == line_element:
        return "旺"
    if GENERATES[month_element] == line_element:
        return "相"
    if GENERATES[line_element] == month_element:
        return "休"
    if CONTROLS[line_element] == month_element:
        return "囚"
    return "死"


def _structure(bits):
    bits = tuple(bits)
    lower = TRIGRAM_BY_BITS[bits[:3]]
    upper = TRIGRAM_BY_BITS[bits[3:]]
    names = json.loads((ROOT / "hexagram_names.json").read_text(encoding="utf-8"))
    name = names["".join(map(str, bits))]
    palace, stage = PALACE_BY_BITS[bits]
    return {
        "name": name, "bits": list(bits), "lower_trigram": lower, "upper_trigram": upper,
        "palace": palace, "palace_stage": PALACE_STAGES[stage],
        "branches": list(PURE_BRANCHES[lower][:3] + PURE_BRANCHES[upper][3:]),
    }


def calculate_base_chart(lines, *, verified_day_stem=None):
    if not isinstance(lines, list) or len(lines) != 6:
        raise ValueError("Six bottom-to-top line states are required")
    if any(not isinstance(x, str) or x not in STATES for x in lines):
        raise ValueError("Each line must be one of the four explicit line states")
    if verified_day_stem is not None and verified_day_stem not in STEM_SPIRIT_START:
        raise ValueError("verified_day_stem must be a valid heavenly stem")
    bits = [STATES[x][0] for x in lines]
    moving = [i + 1 for i, x in enumerate(lines) if STATES[x][1]]
    changed_bits = [value ^ int(i + 1 in moving) for i, value in enumerate(bits)]
    main = _structure(bits)
    palace, stage = PALACE_BY_BITS[tuple(bits)]
    palace_element = PALACE_ELEMENTS[palace]
    shi = SHI_POSITIONS[stage]
    ying = (shi + 2) % 6 + 1
    shi_branch = main["branches"][shi - 1]
    shi_body = BRANCHES.index(shi_branch) % 6 + 1
    gua_body = BRANCHES[((0 if bits[shi - 1] else 6) + shi - 1) % 12]
    line_facts = []
    for i, branch in enumerate(main["branches"]):
        relative = ordinary_relative(palace_element, BRANCH_ELEMENTS[branch])
        fact = {
            "position": i + 1, "state": lines[i], "yang": bool(bits[i]),
            "moving": i + 1 in moving, "branch": branch, "element": BRANCH_ELEMENTS[branch],
            "relative": relative, "relative_code": RELATIVE_CODES[relative],
            "is_shi": i + 1 == shi, "is_ying": i + 1 == ying,
            "is_shi_body": i + 1 == shi_body, "matches_gua_body": branch == gua_body,
            "six_spirit": None,
        }
        if verified_day_stem is not None:
            fact["six_spirit"] = SPIRITS[(STEM_SPIRIT_START[verified_day_stem] + i) % 6]
        line_facts.append(fact)
    main.update({"palace_element": palace_element, "lines": line_facts})
    return {
        "input_lines": list(lines), "main": main,
        "moving_positions": moving,
        "changed_structure": _structure(changed_bits) if moving else None,
        "shi_position": shi, "ying_position": ying, "shi_body_position": shi_body,
        "gua_body_branch": gua_body,
        "gua_body_positions": [x["position"] for x in line_facts if x["matches_gua_body"]],
        "six_spirits_status": "computed_from_verified_stem" if verified_day_stem else "requires_verified_day_stem",
        "calculation_scope": "ordinary_main_chart_and_changed_structure",
        "not_computed": ["calendar", "true_element_application", "changed_line_relatives", "use_spirit_selection", "comprehensive_strength", "outcome", "liujing"],
    }


def engine_build():
    """Content digest, without invented software release numbering."""
    digest = hashlib.sha256()
    for name in ("base_chart.py", "hexagram_names.json"):
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    import sys
    payload = json.load(sys.stdin)
    print(json.dumps(calculate_base_chart(payload["lines"]), ensure_ascii=False, indent=2))
