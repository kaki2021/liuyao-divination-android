"""Create the APK's complete local payload, without build output or user data."""
from pathlib import Path
import hashlib, zipfile, json

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / 'app/src/main/assets'
ASSETS.mkdir(parents=True, exist_ok=True)
PRIVATE_RULE_NAMES = {'compiled_rules.json', 'rules.xlsx', 'rules.xlsx.inspect.ndjson'}

def public_source(path):
    relative = path.relative_to(ROOT)
    if relative.parts[:1] == ('knowledge_base',):
        if path.name in PRIVATE_RULE_NAMES or relative.parts[1:2] == ('versions',):
            return False
    return True

paths = []
for name in ('liuyao_app', 'software_prep', 'knowledge_base'):
    for path in (ROOT / name).rglob('*'):
        if path.is_file() and public_source(path) and '__pycache__' not in path.parts and path.suffix != '.pyc' and not path.name.startswith('test_'):
            paths.append(path)
paths.append(ROOT / '.env.example')
web = Path(__file__).resolve().parent / 'web'
manifest = json.loads((web / 'manifest.json').read_text())
scripts = sorted((ROOT / 'liuyao_app/static').glob('*.js'))
assert set(manifest['files']) == {p.name for p in scripts}, 'Run npm ci && npm run build:web in android/'
for path in scripts:
    hashes = manifest['files'][path.name]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes['source'], 'Web source changed: run npm run build:web'
    assert hashlib.sha256((web / path.name).read_bytes()).hexdigest() == hashes['output'], 'Compiled script corrupted: run npm run build:web'
output = ASSETS / 'content.zip'
payload = {}
for path in paths:
    payload[path.relative_to(ROOT).as_posix()] = (web / path.name).read_bytes() if path in scripts else path.read_bytes()

# The public repository keeps the vendored timezone database inside the
# deterministic payload archive instead of expanding hundreds of binary files.
# A private/full source bundle may still provide ROOT/tzdata; otherwise reuse
# those entries from the previously verified payload before replacing it.
timezone_root = ROOT / 'tzdata'
if timezone_root.is_dir():
    for path in timezone_root.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
elif output.is_file():
    with zipfile.ZipFile(output) as existing:
        for name in existing.namelist():
            if name.startswith('tzdata/') and not name.endswith('/'):
                payload[name] = existing.read(name)
else:
    raise FileNotFoundError('Missing timezone data: restore the verified content.zip or provide ROOT/tzdata')

assert 'tzdata/zoneinfo/Asia/Shanghai' in payload, 'Missing bundled timezone data'
assert not any(name == 'knowledge_base/compiled_rules.json' or
               name == 'knowledge_base/rules.xlsx' or
               name == 'knowledge_base/rules.xlsx.inspect.ndjson' or
               name.startswith('knowledge_base/versions/') for name in payload), 'Private rules entered public payload'
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in sorted(payload):
        info=zipfile.ZipInfo(name, date_time=(2026,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,payload[name])
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    assert 'liuyao_app/_vendor/lunar_python/util/HolidayUtil.py' in z.namelist()
digest=hashlib.sha256(output.read_bytes()).hexdigest()
(ASSETS / 'content.sha256').write_text(digest+'\n')
print(json.dumps({'payload_bytes':output.stat().st_size,'files':len(payload),'sha256':digest}))
