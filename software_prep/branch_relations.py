"""Definition-only branch relations from 卜筮正术补充.pdf, PDF pages 2–5.

The six mutual-form pairs and six mutual-harm pairs are independent sets.
This module does not decide auspiciousness, motives, achievement, applicable
day/month subjects, or the direction of breaking a combination. It does not
change ordinary five-element arithmetic. No casting input or chart is changed.
"""
from pathlib import Path
import hashlib
import json

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
SOURCE_ID = "SRC-BSZS-SUPP"
SOURCE_SHA256 = "4a25d9f65057b16e6208d1fbe021eb4b93fc899712e56ea1030949c1524180af"
FORM_PAIRS = {
    frozenset("子卯"): ("wuen", "无恩之形"),
    frozenset("寅巳"): ("wuen", "无恩之形"),
    frozenset("申亥"): ("wuen", "无恩之形"),
    frozenset("午酉"): ("shishi", "恃势之形"),
    frozenset("丑戌"): ("wuli", "无礼之形"),
    frozenset("辰未"): ("wuli", "无礼之形"),
}
HARM_PAIRS = {
    frozenset("子未"): ("haijian", "害间"),
    frozenset("卯辰"): ("haijian", "害间"),
    frozenset("午丑"): ("enjian", "恩间"),
    frozenset("寅巳"): ("enjian", "恩间"),
    frozenset("申亥"): ("enjian", "恩间"),
    frozenset("酉戌"): ("enjian", "恩间"),
}
NOT_COMPUTED = (
    "auspiciousness", "personal_motive", "achievement", "benefit_or_loss",
    "combination_breaking_direction", "day_month_application",
)


def _require_branch(value):
    if not isinstance(value, str) or len(value) != 1 or value not in BRANCHES:
        raise ValueError("A single exact earthly-branch label is required")
    return BRANCHES.index(value)


def _source(pages):
    return {
        "source_id": SOURCE_ID,
        "source_sha256": SOURCE_SHA256,
        "pdf_pages": list(pages),
        "anchors": [f"PDF-P{page}" for page in pages],
    }


def form_origin(branch):
    """Return the source position whose inclusive tenth position is branch.

    子寅辰午申戌 count forward from the origin; the other six count backward.
    The origin is count 1 and the given branch is count 10: nine moves, not ten.
    To FIND the origin we reverse those nine moves. The returned count_path is
    explicitly origin-to-branch; it is not a forecast or a duration in years.
    """
    index = _require_branch(branch)
    yang = index % 2 == 0
    step = 1 if yang else -1
    origin_index = (index - 9 * step) % 12
    path = [BRANCHES[(origin_index + n * step) % 12] for n in range(10)]
    return {
        "fact_type": "form_origin_definition",
        "branch": branch,
        "branch_polarity": "yang" if yang else "yin",
        "origin_branch": path[0],
        "count_direction_from_origin": "forward" if yang else "reverse",
        "inclusive_count": 10,
        "moves": 9,
        "count_path": path,
        "rule_id": "relation.three_forms_pairs",
        "source": _source([2] if yang else [3]),
        "semantic_scope": "origin_position_only",
    }


def classify_pair(left_branch, right_branch):
    """Return all defined relations for an unordered pair, with PDF anchors.

    Empty relations means no matching definition in THESE TWO tables; it does
    not mean that the branches lack every other relationship. Relation order
    is stable for serialization but carries no priority or mutual exclusion.
    """
    _require_branch(left_branch)
    _require_branch(right_branch)
    pair = frozenset((left_branch, right_branch))
    canonical_pair = sorted(pair, key=BRANCHES.index)
    relations = []
    for table, relation_type, label, rule_prefix, pages in (
        (FORM_PAIRS, "mutual_form", "互形", "three_forms", [3]),
        (HARM_PAIRS, "mutual_harm", "互害", "six_harms", [4]),
    ):
        category = table.get(pair)
        if category is None:
            continue
        relations.append({
            "fact_type": "relation_definition",
            "relation_type": relation_type,
            "label": label,
            "pair": list(canonical_pair),
            "symmetric": True,
            "category_code": category[0],
            "category_label": category[1],
            "rule_ids": [f"relation.{rule_prefix}_pairs", f"relation.{rule_prefix}_categories"],
            "source": _source(pages),
            "semantic_scope": "pair_and_category_only",
        })
    return {
        "left_branch": left_branch,
        "right_branch": right_branch,
        "relations": relations,
        "lookup_scope": ["three_forms", "six_harms"],
        "not_computed": list(NOT_COMPUTED),
    }


def engine_build():
    """Digest of this independent module, for callers' implementation records."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


if __name__ == "__main__":
    import sys
    payload = json.load(sys.stdin)
    print(json.dumps(classify_pair(payload["left_branch"], payload["right_branch"]),
                     ensure_ascii=False, indent=2))
