"""Desktop entry: start this installation on its own port, verify, then open it."""
import json
import os
from pathlib import Path
import re
import sys
import threading
import urllib.request
import webbrowser

from .config import ROOT, initialize_configuration, load_env, data_directory
from .runtime_identity import APP_ID, CASTING_METHODS, app_build_id
from .server import Application, Server

class LaunchError(RuntimeError):
    pass


def validate_ui_files():
    html = (ROOT / 'liuyao_app/static/index.html').read_text(encoding='utf-8')
    for method in CASTING_METHODS:
        if f'value="{method}"' not in html:
            raise LaunchError('程序文件不完整：起卦方式入口缺失。请完整解压新的软件包后再启动。')
    for filename in ('app.js', 'styles.css'):
        if not (ROOT / 'liuyao_app/static' / filename).is_file():
            raise LaunchError('程序文件不完整。请完整解压软件包，保留 runtime 和 liuyao_app 文件夹。')


def fetch_runtime(url):
    """Never follow redirects or system proxies when identifying a local instance."""
    if not isinstance(url, str) or not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}', url):
        raise LaunchError('本机程序地址无效。')
    if int(url.rsplit(':', 1)[1]) > 65535:
        raise LaunchError('本机程序端口无效。')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(url + '/api/runtime', timeout=3) as response:
        raw = response.read(8193)
        if len(raw) > 8192:
            raise LaunchError('本机程序信息过大。')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise LaunchError('本机程序信息格式不正确。')
    return value


def matches_instance(value, instance_id, build_id):
    return (isinstance(value, dict) and isinstance(instance_id, str)
            and re.fullmatch(r'[a-f0-9]{32}', instance_id) is not None
            and isinstance(build_id, str) and re.fullmatch(r'[a-f0-9]{64}', build_id) is not None
            and value.get('app_id') == APP_ID and value.get('instance_id') == instance_id
            and value.get('build_id') == build_id and value.get('casting_methods') == CASTING_METHODS)


def reopen_existing(path, build_id, browser_open=webbrowser.open):
    """Reuse only a positively identified running instance of this exact build."""
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('build_id') != build_id:
            return False
        value = fetch_runtime(record.get('url'))
        if not matches_instance(value, record.get('instance_id'), build_id):
            return False
        if not browser_open(record['url']):
            raise LaunchError('浏览器未能自动打开。请复制本机地址打开：' + record['url'])
        print('已打开正在运行的六爻占问：' + record['url'], flush=True)
        return True
    except LaunchError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        return False


def write_runtime(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def run_desktop(*, browser_open=webbrowser.open, stop_event=None, ready=None):
    validate_ui_files()
    config_path = initialize_configuration()
    load_env(config_path)
    directory = data_directory()
    state_path = directory / 'runtime.json'
    build_id = app_build_id()
    app = None
    server = None
    thread = None
    try:
        try:
            app = Application(directory)
        except RuntimeError as exc:
            if '数据目录已被另一个' not in str(exc):
                raise
            if reopen_existing(state_path, build_id, browser_open):
                return
            raise LaunchError('同一案例目录仍被旧程序使用。请回到旧程序的启动窗口按 Ctrl+C 关闭，再双击“六爻占问.exe”。只关闭浏览器不会停止旧程序；案例数据不会被删除。') from None
        # Port 0 requests a free port from the OS. A service at 8877 stays untouched.
        server = Server(('127.0.0.1', 0), app)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.1}, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        identity = fetch_runtime(url)
        if not matches_instance(identity, app.instance_id, build_id):
            raise LaunchError('本机程序检查不一致，已停止打开页面。请重新完整解压软件包。')
        record = {'url': url, 'instance_id': app.instance_id, 'build_id': build_id}
        write_runtime(state_path, record)
        print('六爻占问已启动：' + url, flush=True)
        print('本页支持：枚卜丸、太极丸、直接六爻。', flush=True)
        print(f'模型配置：{config_path}\n案例数据：{directory}', flush=True)
        print('请保留此窗口，退出时按 Ctrl+C。关闭浏览器不会停止程序。', flush=True)
        if not browser_open(url):
            print('浏览器未能自动打开，请复制上面的本机地址手动打开。', flush=True)
        if ready:
            ready(record)
        (stop_event or threading.Event()).wait()
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(timeout=5)
        if app:
            try:
                if state_path.is_file() and json.loads(state_path.read_text(encoding='utf-8')).get('instance_id') == app.instance_id:
                    state_path.unlink()
            except (OSError, ValueError, TypeError, AttributeError):
                pass
            app.close()


def main():
    try:
        run_desktop()
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, LaunchError) else '软件启动失败，请保留运行窗口中的错误信息。\n' + str(exc)
        print(message, file=sys.stderr, flush=True)
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, '六爻占问启动提示', 0x10)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
