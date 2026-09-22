"""Explicit source fixtures and counterexamples; no external dependencies.

These checks validate definition lookup, not predictive outcomes. Expected
tables below were transcribed from the supplied PDF independently of module
constants; the origin mapping was also independently visually checked.
"""
from pathlib import Path
import hashlib
import json

from branch_relations import classify_pair, form_origin, engine_build

ROOT = Path(__file__).resolve().parent
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ORIGINS = dict(zip(BRANCHES, "卯戌巳子未寅酉辰亥午丑申"))
FORM_EXPECTED = {
    "子卯": "无恩之形", "寅巳": "无恩之形", "申亥": "无恩之形",
    "午酉": "恃势之形", "丑戌": "无礼之形", "辰未": "无礼之形",
}
HARM_EXPECTED = {
    "子未": "害间", "卯辰": "害间", "午丑": "恩间",
    "寅巳": "恩间", "申亥": "恩间", "酉戌": "恩间",
}
SOURCE_HASH = "4a25d9f65057b16e6208d1fbe021eb4b93fc899712e56ea1030949c1524180af"
results = []


def same(actual, expected):
    if actual != expected:
        raise AssertionError({"actual": actual, "expected": expected})


def check(test_id, title, fn):
    record = {"test_id": test_id, "title": title,
              "evidence": f"test_branch_relations.py:{test_id}"}
    try:
        fn()
        record["status"] = "passed"
    except Exception as exc:
        record.update(status="failed", error=repr(exc))
    results.append(record)


def origin_case(branch):
    fact = form_origin(branch)
    same(fact["origin_branch"], ORIGINS[branch])
    same(fact["branch_polarity"], "yang" if branch in "子寅辰午申戌" else "yin")
    same(fact["count_direction_from_origin"], "forward" if branch in "子寅辰午申戌" else "reverse")
    same((fact["inclusive_count"], fact["moves"]), (10, 9))
    same(len(fact["count_path"]), 10)
    same((fact["count_path"][0], fact["count_path"][-1]), (ORIGINS[branch], branch))
    same(fact["source"]["pdf_pages"], [2] if branch in "子寅辰午申戌" else [3])
    same(form_origin(fact["origin_branch"])["origin_branch"], branch)


def relation_case(pair, relation_type, expected):
    for left, right in (pair, pair[::-1]):
        relations = classify_pair(left, right)["relations"]
        wanted = [item for item in relations if item["relation_type"] == relation_type]
        same(len(wanted), 1)
        same(wanted[0]["category_label"], expected)
        same(wanted[0]["symmetric"], True)
        same(wanted[0]["pair"], sorted(pair, key=BRANCHES.index))
    same(classify_pair(*pair)["relations"], classify_pair(*pair[::-1])["relations"])


def full_matrix():
    # This excludes every unlisted pair, including self-form claims and other
    # systems' 寅申、巳申、丑未 groupings. Two relations may share the same pair.
    for left in BRANCHES:
        for right in BRANCHES:
            expected = set()
            for table, kind in ((FORM_EXPECTED, "mutual_form"), (HARM_EXPECTED, "mutual_harm")):
                for pair, category in table.items():
                    if frozenset((left, right)) == frozenset(pair):
                        expected.add((kind, category))
            actual = classify_pair(left, right)["relations"]
            same({(r["relation_type"], r["category_label"]) for r in actual}, expected)
            same(len(actual), len(expected))


def inclusive_paths():
    same(form_origin("子")["count_path"], list("卯辰巳午未申酉戌亥子"))
    same(form_origin("丑")["count_path"], list("戌酉申未午巳辰卯寅丑"))
    same(form_origin("卯")["count_path"], list("子亥戌酉申未午巳辰卯"))


def concurrent_relations():
    for pair in ("寅巳", "申亥"):
        same({r["category_label"] for r in classify_pair(*pair)["relations"]}, {"无恩之形", "恩间"})


def reject_invalid():
    for bad in (None, True, 1, "", "子子", " 子", "子 ", "Zi", "甲", [], {}):
        for operation in (lambda: form_origin(bad), lambda: classify_pair(bad, "子"),
                          lambda: classify_pair("子", bad)):
            try:
                operation()
            except ValueError:
                continue
            raise AssertionError(f"Invalid branch accepted: {bad!r}")


def source_and_semantics():
    expected_codes = {"无恩之形": "wuen", "恃势之形": "shishi", "无礼之形": "wuli", "害间": "haijian", "恩间": "enjian"}
    for pair in list(FORM_EXPECTED) + list(HARM_EXPECTED):
        output = classify_pair(*pair)
        same(set(output), {"left_branch", "right_branch", "relations", "lookup_scope", "not_computed"})
        for fact in output["relations"]:
            form = fact["relation_type"] == "mutual_form"
            prefix, page = ("three_forms", 3) if form else ("six_harms", 4)
            same(fact["rule_ids"], [f"relation.{prefix}_pairs", f"relation.{prefix}_categories"])
            same(fact["source"], {"source_id": "SRC-BSZS-SUPP", "source_sha256": SOURCE_HASH,
                                  "pdf_pages": [page], "anchors": [f"PDF-P{page}"]})
            same(fact["fact_type"], "relation_definition")
            same(fact["semantic_scope"], "pair_and_category_only")
            same(fact["category_code"], expected_codes[fact["category_label"]])
        same(set(output["not_computed"]), {"auspiciousness", "personal_motive", "achievement",
              "benefit_or_loss", "combination_breaking_direction", "day_month_application"})


def isolated_outputs():
    first = classify_pair("寅", "巳")
    first["relations"][0]["pair"].append("子")
    first["relations"][0]["source"]["pdf_pages"].append(6)
    first["not_computed"].clear()
    second = classify_pair("寅", "巳")
    same(second["relations"][0]["pair"], ["寅", "巳"])
    same(second["relations"][0]["source"]["pdf_pages"], [3])
    same(len(second["not_computed"]), 6)
    same(json.loads(json.dumps(second, ensure_ascii=False)), second)


def build_digest():
    same(engine_build(), hashlib.sha256((ROOT / "branch_relations.py").read_bytes()).hexdigest())


def main():
    for branch in BRANCHES:
        check(f"BR-ORIGIN-{branch}", f"{branch}的十位形来源与阴阳计数", lambda b=branch: origin_case(b))
    for pair, category in FORM_EXPECTED.items():
        check(f"BR-FORM-{pair}", f"{pair}双向互形分类：{category}", lambda p=pair, c=category: relation_case(p, "mutual_form", c))
    for pair, category in HARM_EXPECTED.items():
        check(f"BR-HARM-{pair}", f"{pair}双向互害分类：{category}", lambda p=pair, c=category: relation_case(p, "mutual_harm", c))
    for test_id, title, fn in (
        ("BR-MATRIX", "全部144个有序地支对精确匹配，无增补自形或其他体系配对", full_matrix),
        ("BR-COUNT", "含首尾共十位，阳顺阴逆求来源时正确逆解", inclusive_paths),
        ("BR-OVERLAP", "寅巳与申亥的互形和互害同时保留", concurrent_relations),
        ("BR-INVALID", "两个配对参数和来源参数均拒绝无效地支", reject_invalid),
        ("BR-SOURCE", "来源页码规则标识正确，输出限定义无个案结论", source_and_semantics),
        ("BR-ISOLATION", "返回值可JSON保存且修改一次结果不污染后续查表", isolated_outputs),
        ("BR-DIGEST", "模块摘要与实际实现文件一致", build_digest),
    ):
        check(test_id, title, fn)
    summary = {
        "scope": "Deterministic mutual-form and mutual-harm pairs/categories and inclusive origin tracing only",
        "tests_run": len(results), "passed": sum(r["status"] == "passed" for r in results),
        "failed": sum(r["status"] == "failed" for r in results), "tests": results,
        "source_id": "SRC-BSZS-SUPP", "source_sha256": SOURCE_HASH,
        "engine_build": engine_build(),
        "limits": ["No predictive outcome verification", "No inferred personal motive",
                   "No day/month applicability or combination-breaking direction",
                   "No global reverse five-element arithmetic", "No chart/store/AI integration"],
    }
    (ROOT / "branch_relation_test_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("tests_run", "passed", "failed")}, ensure_ascii=False))
    if summary["failed"]:
        print(json.dumps([r for r in results if r["status"] == "failed"], ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
