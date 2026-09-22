"""Generate branch references from branch_relations; do not maintain a second table."""
from itertools import combinations
from pathlib import Path
import json

from branch_relations import BRANCHES, SOURCE_ID, SOURCE_SHA256, classify_pair, form_origin, engine_build

ROOT = Path(__file__).resolve().parent


def generate_tables():
    forms, harms = [], []
    for left, right in combinations(BRANCHES, 2):
        for relation in classify_pair(left, right)["relations"]:
            (forms if relation["relation_type"] == "mutual_form" else harms).append(relation)
    return {
        "purpose": "Generated definition references; no predictive interpretation",
        "source": {"source_id": SOURCE_ID, "sha256": SOURCE_SHA256},
        "module_sha256": engine_build(),
        "branch_order": list(BRANCHES),
        "form_origins": [form_origin(branch) for branch in BRANCHES],
        "mutual_form_pairs": forms,
        "mutual_harm_pairs": harms,
    }


if __name__ == "__main__":
    tables = generate_tables()
    path = ROOT / "branch_reference_tables.json"
    path.write_text(json.dumps(tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file": path.name, "form_origins": len(tables["form_origins"]),
                      "mutual_form_pairs": len(tables["mutual_form_pairs"]),
                      "mutual_harm_pairs": len(tables["mutual_harm_pairs"])}, ensure_ascii=False))
