"""Identify the local code/UI actually serving a browser, without release numbers."""
import hashlib
from pathlib import Path

APP_ID = 'liuyao-local-workbench'
CASTING_METHODS = ['meibu', 'taiji', 'direct']

def app_build_id():
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    paths = list(root.glob('*.py')) + list((root / 'static').glob('*'))
    foundation = root.parent / 'software_prep'
    paths.extend(foundation / name for name in (
        'base_chart.py', 'branch_relations.py', 'casting_input.py',
        'liuyao_ai_prompt_pack.yaml', 'validate_ai_contract.py', 'rule_catalog.json'))
    for path in sorted(paths):
        if path.is_file():
            digest.update(str(path.relative_to(root.parent)).encode('utf-8'))
            digest.update(path.read_bytes())
    return digest.hexdigest()
