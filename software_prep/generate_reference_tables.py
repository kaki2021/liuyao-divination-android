"""Generate reference tables from the core constants and deterministic module."""
from pathlib import Path
import json
import hashlib
from base_chart import (
    PALACE_BY_BITS, PALACE_ELEMENTS, BRANCH_ELEMENTS, BRANCHES,
    calculate_base_chart, ordinary_relative, ordinary_month_strength, engine_build,
)

ROOT = Path(__file__).resolve().parent
generated = {
    "basis": "卜筮正术明确常量与算法；卦名映射来自已核对的辅助表",
    "generator_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "engine_build": engine_build(),
    "palace_elements": PALACE_ELEMENTS,
    "branch_elements": BRANCH_ELEMENTS,
    "ordinary_kinship": {base: {e: ordinary_relative(base, e) for e in "木火土金水"} for base in "木火土金水"},
    "ordinary_month_labels": {month: {e: ordinary_month_strength(month, e) for e in "木火土金水"} for month in "木火土金水"},
    "shi_body_positions": {branch: i % 6 + 1 for i, branch in enumerate(BRANCHES)},
    "gua_body_branches": {kind: {str(pos): BRANCHES[(start + pos - 1) % 12] for pos in range(1, 7)} for kind, start in [("yang_shi", 0), ("yin_shi", 6)]},
    "hexagrams": [calculate_base_chart(["young_yang" if b else "young_yin" for b in bits]) for bits in PALACE_BY_BITS],
    "limits": ["Generated tables are implementation references, not empirical prediction evidence", "No complete time/calendar or outcome algorithm"],
}
(ROOT / "reference_tables.json").write_text(json.dumps(generated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"hexagrams": len(generated["hexagrams"]), "lines": sum(len(h["main"]["lines"]) for h in generated["hexagrams"])}, ensure_ascii=False))
