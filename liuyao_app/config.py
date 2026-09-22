"""Resource paths and a literal .env loader; writable data stays outside the app."""
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def application_home():
    override = os.environ.get('LIUYAO_HOME')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local')))
        return (base / 'Liuyao').resolve()
    return ROOT

def configuration_file():
    return application_home() / '.env'

def initialize_configuration():
    """Create an empty example once, without replacing a user's credentials."""
    home = application_home()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = configuration_file()
    example = ROOT / '.env.example'
    if example.is_file():
        try:
            with target.open('x', encoding='utf-8') as stream:
                stream.write(example.read_text(encoding='utf-8-sig'))
        except FileExistsError:
            pass
    upgrade_deepseek_defaults(target)
    return target


def upgrade_deepseek_defaults(path):
    """Once, upgrade the shipped Flash preset; retain keys and custom endpoints.

    Custom model allowlists and subsequent deliberate selections stay intact.
    Original bytes are backed up before atomically replacing a legacy preset.
    """
    path = Path(path)
    if not path.is_file():
        return False
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    marker = '# LIUYAO_DEFAULTS: deepseek-pro-max'
    if marker in text:
        return False
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key.strip() in values:
            return False  # Ambiguous user configuration is not rewritten.
        values[key.strip()] = value
    legacy = {'deepseek-flash', 'deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner'}
    allowed = [x.strip() for x in values.get('DEEPSEEK_MODELS', '').split(',') if x.strip()]
    old_preset = (values.get('DEEPSEEK_MODEL') in legacy
                  or (values.get('DEEPSEEK_MODEL') == 'deepseek-v4-pro' and not values.get('DEEPSEEK_REASONING_EFFORT')))
    if not old_preset or any(x not in legacy | {'deepseek-v4-pro'} for x in allowed):
        return False
    changes = {'DEEPSEEK_MODEL': 'deepseek-v4-pro',
               'DEEPSEEK_MODELS': ','.join(dict.fromkeys(['deepseek-v4-pro'] + (allowed or ['deepseek-flash']))),
               'DEEPSEEK_REASONING_EFFORT': 'max', 'DEEPSEEK_THINKING': 'enabled'}
    if values.get('DEEPSEEK_MAX_TOKENS', '') in ('', '8192', '32768'):
        changes['DEEPSEEK_MAX_TOKENS'] = '131072'
    if values.get('AI_TIMEOUT_SECONDS', '') in ('', '90', '120'):
        changes['AI_TIMEOUT_SECONDS'] = '600'
    lines=[];remaining=dict(changes)
    for line in text.splitlines():
        key=line.split('=', 1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else ''
        if key in changes:
            lines.append(key+'='+changes[key]);remaining.pop(key,None)
        else:
            lines.append(line)
    lines.extend(key+'='+value for key,value in remaining.items())
    lines.append(marker)
    backup = path.with_name('.env.before-deepseek-pro-max')
    try:
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.env-pro-max-', delete=False) as stream:
            temporary=Path(stream.name)
            stream.write('\n'.join(lines)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True

def load_env(path=None):
    path = Path(path) if path is not None else configuration_file()
    if not path.is_file():
        return
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'.env 第 {number} 行缺少等号')
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if not key or not key.replace('_', '').isalnum() or not key[0].isalpha():
            raise ValueError(f'.env 第 {number} 行变量名无效')
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)

def data_directory():
    path = Path(os.environ.get('LIUYAO_DATA_DIR', str(application_home() / 'data'))).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path
