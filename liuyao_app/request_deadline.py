"""Bound elapsed network time, even while the peer keeps sending data."""
import http.client
import socket
import threading
import urllib.request

SLOTS = threading.BoundedSemaphore(4)


def within_deadline(operation, seconds, cancel=lambda: None):
    if not SLOTS.acquire(blocking=False):
        from .providers import ProviderError
        raise ProviderError('transport_busy', '仍有网络请求正在退出，请稍后重试。', retryable=True)
    done = threading.Event()
    outcome = {}
    def work():
        try: outcome['value'] = operation()
        except Exception as exc: outcome['error'] = exc
        finally:
            SLOTS.release()
            done.set()
    try: threading.Thread(target=work, name='ai-request', daemon=True).start()
    except Exception:
        SLOTS.release()
        raise
    if not done.wait(seconds):
        cancel()
        raise TimeoutError('AI request elapsed deadline reached')
    if 'error' in outcome: raise outcome['error']
    return outcome['value']


class RequestControl:
    def __init__(self):
        self.lock = threading.Lock()
        self.cancelled = False
        self.connections = []
        self.responses = []

    def check(self):
        if self.cancelled: raise TimeoutError('AI request cancelled')

    def connection_type(self, base):
        control = self
        class Connection(base):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                with control.lock:
                    control.connections.append(self)
                    control.check()
            def connect(self):
                super().connect()
                if control.cancelled:
                    self.close()
                    control.check()
            def getresponse(self):
                response = super().getresponse()
                with control.lock:
                    control.responses.append(response)
                    if control.cancelled:
                        response.close()
                        control.check()
                return response
        return Connection

    def handlers(self):
        http_type = self.connection_type(http.client.HTTPConnection)
        https_type = self.connection_type(http.client.HTTPSConnection)
        class HTTPHandler(urllib.request.HTTPHandler):
            def http_open(self, req): return self.do_open(http_type, req)
        class HTTPSHandler(urllib.request.HTTPSHandler):
            def https_open(self, req): return self.do_open(https_type, req)
        return HTTPHandler(), HTTPSHandler()

    def cancel(self):
        with self.lock:
            self.cancelled = True
            sockets = [c.sock for c in self.connections]
            sockets.extend(getattr(getattr(r.fp,'raw',None),'_sock',None) for r in self.responses)
        for sock in sockets:
            if sock is not None:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
