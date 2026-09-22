"""Run the unchanged desktop domain on Android, with a private local HTTP gate."""
import json
import os
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

_app = _server = None
_lock = threading.RLock()


def start(resource_root, data_home, token, credentials='{}'):
    global _app, _server
    with _lock:
        if _server:
            return 'http://127.0.0.1:' + str(_server.server_port)
        sys.path.insert(0, str(resource_root))
        os.environ['LIUYAO_HOME'] = str(data_home)
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        sys.dont_write_bytecode = True
        from liuyao_app.config import initialize_configuration, load_env, data_directory
        initialize_configuration(); load_env()
        _configure(credentials)
        from liuyao_app.server import Application, Server, Handler, ApiError

        class NativeHandler(Handler):
            def guard(self, mutation=False):
                super().guard(mutation)
                if urlsplit(self.path).path in ('/', '/index.html'):
                    import secrets
                    if not secrets.compare_digest(self.headers.get('X-Liuyao-Bootstrap',''),token):
                        raise ApiError(403, 'NATIVE_ONLY', '请从应用打开。')
                else:
                    self.actor()  # Static assets and runtime info also require the private session.

        _app = Application(data_directory())
        _server = Server(('127.0.0.1', 0), _app)
        _server.RequestHandlerClass = NativeHandler
        threading.Thread(target=_server.serve_forever, daemon=True).start()
        return 'http://127.0.0.1:' + str(_server.server_port)


def _configure(raw):
    values = json.loads(str(raw))
    allowed = {'DEEPSEEK_API_KEY','DOUBAO_API_KEY','DOUBAO_MODEL','DOUBAO_MODELS'}
    if not isinstance(values, dict) or set(values)-allowed:
        raise ValueError('不支持的模型配置')
    for key in allowed:
        value=values.get(key,'')
        if not isinstance(value,str) or len(value)>2000 or '\n' in value or '\r' in value:
            raise ValueError('模型配置格式不正确')
    for key in allowed:
        os.environ[key]=values.get(key,'')


def configure(raw):
    with _lock:
        if _app and active():
            return False
        _configure(raw)
        return True


def active():
    if not _app:
        return False
    from case_store import Actor
    return bool(_app.active(Actor('local-user','android-service')))


def stop():
    global _app, _server
    if _server:
        _server.shutdown();_server.server_close()
    if _app:
        _app.close()
    _app=_server=None
