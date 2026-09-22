"""Validate the core-based implementation against the supplied auxiliary table."""
from pathlib import Path
import json
from base_chart import calculate_base_chart, ordinary_month_strength, ordinary_relative

ROOT = Path(__file__).resolve().parent
results = []


def check(test_id, title, fn):
    try:
        fn()
        results.append({"test_id": test_id, "title": title, "status": "passed"})
    except Exception as exc:
        results.append({"test_id": test_id, "title": title, "status": "failed", "error": repr(exc)})


def same(actual, expected):
    if actual != expected:
        raise AssertionError({"actual": actual, "expected": expected})


def golden(record):
    states = ["young_yang" if l["yin_yang"] else "young_yin" for l in record["lines"]]
    chart = calculate_base_chart(states)
    same(chart["main"]["name"], record["name"])
    same(chart["main"]["palace"], record["palace"])
    same(chart["main"]["palace_element"], record["palace_element"])
    same(len(chart["main"]["lines"]), 6)
    same(chart["changed_structure"], None)
    for line, wanted in zip(chart["main"]["lines"], record["lines"]):
        for key in ("branch", "element", "relative"):
            same(line[key], wanted[key])
        same(line["position"], wanted["line_index"])
        same(line["is_shi"], wanted["position"] == "世")
        same(line["is_ying"], wanted["position"] == "应")


def reject(value):
    try:
        calculate_base_chart(value)
    except ValueError:
        return
    raise AssertionError("Invalid line input accepted")


def qian_bodies():
    chart = calculate_base_chart(["young_yang"] * 6)
    same((chart["shi_position"], chart["ying_position"], chart["shi_body_position"]), (6, 3, 5))
    same(chart["gua_body_branch"], "巳")
    same(chart["gua_body_positions"], [])
    same(chart["six_spirits_status"], "requires_verified_day_stem")


def kun_bodies():
    chart = calculate_base_chart(["young_yin"] * 6)
    same(chart["shi_body_position"], 4)
    same(chart["gua_body_branch"], "亥")
    same(chart["gua_body_positions"], [5])


def ge_change():
    # Core source example B0430–B0432: 离下兑上，四爻动 -> 既济.
    chart = calculate_base_chart(["young_yang", "young_yin", "young_yang", "old_yang", "young_yang", "young_yin"])
    same(chart["main"]["name"], "泽火革")
    same(chart["moving_positions"], [4])
    same(chart["changed_structure"]["name"], "水火既济")
    same(chart["changed_structure"]["bits"], [1, 0, 1, 0, 1, 0])


def all_moving():
    chart = calculate_base_chart(["old_yin"] * 6)
    same(chart["main"]["name"], "坤为地")
    same(chart["changed_structure"]["name"], "乾为天")
    same(chart["moving_positions"], [1, 2, 3, 4, 5, 6])


def spirits():
    chart = calculate_base_chart(["young_yang"] * 6, verified_day_stem="庚")
    same([l["six_spirit"] for l in chart["main"]["lines"]], ["白虎", "玄武", "青龙", "朱雀", "勾陈", "腾蛇"])


def month_example():
    same({e: ordinary_month_strength("火", e) for e in "火土木水金"}, {"火": "旺", "土": "相", "木": "休", "水": "囚", "金": "死"})


def custom_palace_relatives():
    same([ordinary_relative("金", e) for e in "木水土金火"], ["妻财", "子孙", "父母", "兄弟", "官鬼"])


data = json.loads((ROOT / "fixtures/auxiliary_64_table.json").read_text())
for i, record in enumerate(data["records"], 1):
    check(f"CHART-{i:03}", f"辅助表交叉核对 {record['name']}", lambda r=record: golden(r))
for i, value in enumerate([None, [], ["young_yang"] * 5, ["young_yang"] * 7, [1] * 6, ["yang"] * 6], 1):
    check(f"CHART-INPUT-{i:02}", "拒绝不完整或缺动静枚举的输入", lambda v=value: reject(v))
for test_id, title, fn in [
    ("CHART-QIAN-BODY", "乾卦身位及不现位置", qian_bodies),
    ("CHART-KUN-BODY", "阴世卦身计数", kun_bodies),
    ("CHART-CORE-CHANGE", "核心革之既济实例", ge_change),
    ("CHART-ALL-MOVING", "老阴全动形成乾", all_moving),
    ("CHART-SPIRITS", "核定日干的六神循环", spirits),
    ("CHART-MONTH", "核心火月旺相休囚死实例", month_example),
    ("CHART-GEN-METAL", "艮金参照六亲", custom_palace_relatives),
]:
    check(test_id, title, fn)
summary = {
    "scope": "main base chart, supplied auxiliary crosscheck, selected explicit core examples",
    "total": len(results), "passed": sum(r["status"] == "passed" for r in results),
    "failed": sum(r["status"] == "failed" for r in results), "results": results,
    "source_fixture_sha256": data["source_sha256"],
    "limits": ["No predictive outcome test", "No calendar integration", "No changed-line relative calculation"],
}
(ROOT / "base_chart_test_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("total", "passed", "failed")}, ensure_ascii=False))
if summary["failed"]:
    print(json.dumps([r for r in results if r["status"] == "failed"], ensure_ascii=False, indent=2))
    raise SystemExit(1)
