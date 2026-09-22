"""Run the existing check suites without external dependencies."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = (
    "test_base_chart.py", "test_input.py", "test_case_store.py",
    "test_ai_contract.py", "test_conclusion_contract.py", "test_ai_store_integration.py",
    "test_branch_relations.py", "test_casting_input.py", "test_person_info.py",
)

if __name__ == "__main__":
    failed = []
    for script in SCRIPTS:
        print(script, flush=True)
        result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT,env={**os.environ,"PYTHONPATH":str(ROOT.parent)})
        if result.returncode:
            failed.append(script)
    if failed:
        print("Failed: " + ", ".join(failed), file=sys.stderr)
        raise SystemExit(1)
    print(f"All {len(SCRIPTS)} check suites passed.")
