"""Use the application's existing services from an AI host, without a server.

The JSON adapter deliberately dispatches through the same route validators and
services as the app. It does not start a listener or rely on a running APK.
"""
from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from .skill_tools import execute as basic_tool
from .server import Application, Handler
from case_store import Actor

OWNER = Actor('local-user', 'skill-host')
MAX_INPUT = 7_000_000


class DirectRequest:
    """In-process version of Handler; route logic and persistence stay shared."""
    dispatch = Handler.dispatch

    def __init__(self, app, method, path, body, idem):
        self.server = SimpleNamespace(app=app)
        self.path, self._body = path, body
        self.headers = {'X-Idempotency-Key': idem}
        self.wfile = io.BytesIO()
        self.status, self.value, self.content_type = None, None, None
        self.mutation = method == 'POST'

    def guard(self, mutation=False):
        pass  # There is no network or cross-origin request in this adapter.

    def actor(self):
        return OWNER

    def body(self):
        return self._body

    def send_json(self, value, status=200, extra=None):
        self.status, self.value = status, value

    def _headers(self, status, kind, length, extra=None):
        self.status, self.content_type = status, kind

    def run(self):
        self.dispatch(self.mutation)
        if self.status is None:
            raise RuntimeError('技能调用没有返回结果。')
        if self.value is None and self.wfile.tell():
            self.value = {'content_type': self.content_type,
                          'base64': base64.b64encode(self.wfile.getvalue()).decode('ascii')}
        return self.status, self.value


def _validate_request(request):
    if not isinstance(request, dict) or request.get('kind') not in ('api', 'tool', 'install_rules'):
        raise ValueError('请选择 api、tool 或 install_rules。')
    if request['kind'] != 'api':
        return
    if set(request) - {'kind', 'method', 'path', 'body', 'idempotency_key'}:
        raise ValueError('请求包含未知字段。')
    method, path = request.get('method'), request.get('path')
    if method not in ('GET', 'POST') or not isinstance(path, str) or len(path) > 2048:
        raise ValueError('请求方法或路径无效。')
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith('/api/'):
        raise ValueError('只接受本项目的相对 API 路径。')
    if '..' in parsed.path.split('/') or '%' in parsed.path or '\\' in parsed.path:
        raise ValueError('请求路径无效。')
    if method == 'POST':
        if not isinstance(request.get('body'), dict):
            raise ValueError('POST 需要 JSON 对象。')
        idem = request.get('idempotency_key')
        if not isinstance(idem, str) or not 1 <= len(idem.strip()) <= 160:
            raise ValueError('POST 需要稳定且唯一的 idempotency_key。')
    elif 'body' in request or 'idempotency_key' in request:
        raise ValueError('GET 不接受请求正文或操作标识。')


def _solar_defaults(path, body):
    """Do not introduce a Beijing-time choice when recording a new cast."""
    body = copy.deepcopy(body)
    route = urlsplit(path).path
    parts = route.strip('/').split('/')
    case_input = route == '/api/cases' or (len(parts) == 4 and parts[:2] == ['api', 'cases'] and parts[3] == 'revisions')
    subject = body.get('input') if case_input else body if route == '/api/calendar' else None
    if isinstance(subject, dict):
        basis = subject.setdefault('time_basis', 'true_solar')
        if basis != 'true_solar':
            raise ValueError('新起卦使用当地真太阳时，请提供实际时刻和经度。')
    return body


def _install_rules(app, request):
    """Decrypt a separately supplied package into a temporary private directory."""
    if set(request) != {'kind', 'path'} or not isinstance(request['path'], str):
        raise ValueError('请提供本机加密规则包路径。')
    package = Path(request['path']).expanduser().resolve(strict=True)
    if not package.is_file() or package.suffix != '.lyrules':
        raise ValueError('请选择 .lyrules 规则包。')
    from .rulebook import rules_installed, read_workbook, save_rules
    if rules_installed(app.rules_directory):
        raise ValueError('已安装规则；为避免覆盖，先检查现有版本。')
    if not (os.environ.get('LIUYAO_RULE_PASSWORD_FILE') or os.environ.get('LIUYAO_RULE_PASSWORD')):
        raise ValueError('请通过环境变量或口令文件提供规则包口令。')
    tool = Path(__file__).resolve().parents[1] / 'tools' / 'rule-package.mjs'
    with tempfile.TemporaryDirectory(prefix='rules-import-', dir=app.directory) as directory:
        out = Path(directory) / 'rules.xlsx'
        try:
            result = subprocess.run(['node', str(tool), 'decrypt', str(package), str(out)],
                                    capture_output=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('无法运行规则包导入工具，请确认已安装 Node.js。') from None
        if result.returncode:
            raise ValueError('规则包或口令无效，请核对后重试。')
        book = save_rules(app.rules_directory, read_workbook(out.read_bytes()))
    return {'installed': True, 'version': book.version, 'rule_count': len(book.rows)}


def _tool(request):
    if set(request) != {'kind', 'name', 'input'} or not isinstance(request['input'], dict):
        raise ValueError('工具请求需要 name 和 input 对象。')
    name, payload = request['name'], request['input']
    if name == 'casting':
        from casting_input import derive_casting_lines
        return {'casting': payload, 'lines': derive_casting_lines(payload)}
    if name == 'random_coin':
        if payload != {'user_requested': True}:
            raise ValueError('仅在用户明确要求时模拟本次掷币。')
        from casting_input import TAIJI_FOUR_STATES
        token = ''.join(str(2 + secrets.randbits(1)) for _ in range(3))
        return {'token': token, 'line': TAIJI_FOUR_STATES[''.join(sorted(token))],
                'note': '本次仅生成一爻；记录六次实际结果后再保存。'}
    if name == 'chart' and payload.get('time_basis', 'true_solar') != 'true_solar':
        raise ValueError('新起卦使用当地真太阳时，请提供实际时刻和经度。')
    return basic_tool(name, payload)


def execute(request, workspace=None):
    _validate_request(request)
    if request['kind'] == 'tool':
        return {'ok': True, 'result': _tool(request)}
    if not workspace:
        raise ValueError('请通过 --workspace 指定私有数据目录。')
    app = Application(Path(workspace).expanduser().resolve())
    try:
        if request['kind'] == 'install_rules':
            return {'ok': True, 'result': _install_rules(app, request)}
        method, path = request['method'], request['path']
        body = _solar_defaults(path, request.get('body', {})) if method == 'POST' else None
        status, result = DirectRequest(app, method, path, body, request.get('idempotency_key')).run()
        if status == 202 and isinstance(result, dict) and result.get('job_id'):
            job_id = result['job_id']
            if urlsplit(path).path.startswith('/api/workbench/'):
                read = lambda: app.workbench.store.job(OWNER.owner_id, job_id)
            else:
                read = lambda: app.get_job(OWNER, job_id)
            while True:
                result = read()
                if result['status'] not in ('queued', 'running'):
                    break
                time.sleep(.1)
        return {'ok': 200 <= status < 300, 'status': status, 'result': result}
    finally:
        app.close()


def main():
    parser = argparse.ArgumentParser(description='六爻与知识库 Skill 的本机 JSON 运行入口')
    parser.add_argument('--workspace', default=os.environ.get('LIUYAO_SKILL_HOME'))
    args = parser.parse_args()
    try:
        raw = sys.stdin.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError('输入过长。')
        request = json.loads(raw or '{}')
        value = execute(request, args.workspace)
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        # No stack trace or model credentials; service errors already use safe messages.
        message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else '输入或本地文件无效，请检查后重试。'
        value = {'ok': False, 'error': message}
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return 0 if value.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
