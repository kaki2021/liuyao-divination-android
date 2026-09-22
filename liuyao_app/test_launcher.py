"""Real loopback launch/relaunch tests; browser and paid AI calls stay closed."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from . import launcher
from .instance_lock import InstanceLock
from .runtime_identity import APP_ID, CASTING_METHODS, app_build_id
from .server import Application


@contextmanager
def identity_server(payload=None, *, redirect=None):
    """An unrelated/old local service, independent of production Application."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if redirect:
                self.send_response(302)
                self.send_header('Location', redirect)
                self.end_headers()
                return
            raw = json.dumps(payload).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={'poll_interval': 0.01}, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class DesktopLauncherChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.directory = self.home / 'data'
        self.directory.mkdir()
        self.runtime_path = self.directory / 'runtime.json'
        # Both overrides are necessary: developer machine configuration must not
        # select a real user's case database or inject an existing .env file.
        self.environment = patch.dict(os.environ, {
            'LIUYAO_HOME': str(self.home),
            'LIUYAO_DATA_DIR': str(self.directory),
        })
        self.environment.start()
        self.launches = []

    def tearDown(self):
        try:
            for run in reversed(self.launches):
                run['stop'].set()
                run['thread'].join(timeout=5)
                self.assertFalse(run['thread'].is_alive(), 'launcher did not exit')
                self.assertEqual(run['errors'], [], 'background launcher failed')
        finally:
            self.environment.stop()
            self.temp.cleanup()

    def start_launcher(self, **kwargs):
        run = {'stop': threading.Event(), 'ready': threading.Event(),
               'finished': threading.Event(), 'errors': [], 'record': None,
               'browser': Mock(return_value=True)}

        def ready(record):
            run['record'] = record
            run['ready'].set()

        def worker():
            try:
                launcher.run_desktop(browser_open=run['browser'],
                                     stop_event=run['stop'], ready=ready, **kwargs)
            except BaseException as exc:
                run['errors'].append(exc)
            finally:
                run['finished'].set()
                run['ready'].set()

        run['thread'] = threading.Thread(target=worker, daemon=True)
        self.launches.append(run)
        run['thread'].start()
        self.assertTrue(run['ready'].wait(8), 'launcher never became ready')
        if run['errors']:
            raise run['errors'][0]
        self.assertIsNotNone(run['record'])
        return run

    def write_record(self, url, *, build_id=None, instance_id='a' * 32):
        record = {'url': url, 'build_id': build_id or app_build_id(),
                  'instance_id': instance_id}
        self.runtime_path.write_text(json.dumps(record), encoding='utf-8')
        return record

    def test_occupied_old_service_does_not_choose_old_page(self):
        with identity_server({'old': True}) as (old_url, old_requests):
            # A stale same-directory address must not override the fresh socket.
            self.write_record(old_url, build_id='0' * 64)
            run = self.start_launcher()
            url = run['record']['url']
            self.assertNotEqual(url, old_url)
            run['browser'].assert_called_once_with(url)
            self.assertEqual(old_requests, [], 'new startup contacted old service')
            connection = http.client.HTTPConnection(
                '127.0.0.1', int(url.rsplit(':', 1)[1]), timeout=3)
            try:
                connection.request('GET', '/')
                response = connection.getresponse()
                html = response.read().decode('utf-8')
                self.assertEqual(response.status, 200)
                for method in ('meibu', 'taiji', 'direct'):
                    self.assertIn(f'value="{method}"', html)
                self.assertIn('枚卜丸', html)
                self.assertIn('太极丸', html)
            finally:
                connection.close()

    def test_stop_removes_own_runtime_record_and_releases_data_lock(self):
        run = self.start_launcher()
        self.assertEqual(json.loads(self.runtime_path.read_text()), run['record'])
        self.assertTrue((self.home / '.env').is_file())
        self.assertTrue((self.directory / 'cases.sqlite3').is_file())
        run['stop'].set()
        run['thread'].join(timeout=5)
        self.assertFalse(run['thread'].is_alive())
        self.assertFalse(self.runtime_path.exists())
        lock = InstanceLock(self.directory / 'app.lock')
        lock.close()
        self.assertTrue((self.directory / 'cases.sqlite3').is_file())

    def test_running_same_build_reopens_exact_instance(self):
        run = self.start_launcher()
        browser = Mock(return_value=True)
        launcher.run_desktop(browser_open=browser)
        browser.assert_called_once_with(run['record']['url'])
        self.assertEqual(json.loads(self.runtime_path.read_text()), run['record'])
        self.assertTrue(run['thread'].is_alive())
        identity = launcher.fetch_runtime(run['record']['url'])
        self.assertEqual(identity['instance_id'], run['record']['instance_id'])

    def test_old_build_data_lock_never_opens_or_deletes_old_data(self):
        old_app = Application(self.directory)
        try:
            database_before = (self.directory / 'cases.sqlite3').read_bytes()
            with identity_server({'old': True}) as (old_url, requests):
                record = self.write_record(old_url, build_id='0' * 64)
                browser = Mock(return_value=True)
                with self.assertRaises(launcher.LaunchError) as caught:
                    launcher.run_desktop(browser_open=browser)
                self.assertIn('Ctrl+C', str(caught.exception))
                self.assertIn('案例数据不会被删除', str(caught.exception))
                browser.assert_not_called()
                self.assertEqual(requests, [])
                self.assertEqual(json.loads(self.runtime_path.read_text()), record)
                self.assertEqual((self.directory / 'cases.sqlite3').read_bytes(),
                                 database_before)
        finally:
            old_app.close()

    def test_tampered_runtime_identity_is_not_reopened(self):
        run = self.start_launcher()
        altered = dict(run['record'], instance_id='b' * 32)
        self.runtime_path.write_text(json.dumps(altered), encoding='utf-8')
        browser = Mock(return_value=True)
        with self.assertRaises(launcher.LaunchError):
            launcher.run_desktop(browser_open=browser)
        browser.assert_not_called()
        # Restore the live owner's record, so its normal exit can remove it.
        self.runtime_path.write_text(json.dumps(run['record']), encoding='utf-8')

    def test_missing_runtime_identity_is_not_reopened(self):
        build = app_build_id()
        payload = {'app_id': APP_ID, 'build_id': build,
                   'casting_methods': CASTING_METHODS}
        with identity_server(payload) as (url, _):
            record = self.write_record(url, build_id=build)
            del record['instance_id']
            self.runtime_path.write_text(json.dumps(record), encoding='utf-8')
            browser = Mock(return_value=True)
            self.assertFalse(launcher.reopen_existing(self.runtime_path, build, browser))
            browser.assert_not_called()

    def test_nonlocal_and_ambiguous_addresses_never_open_or_fetch(self):
        values = ['https://127.0.0.1:1234', 'http://example.com:1234',
                  'http://localhost:1234', 'http://127.0.0.1:1234/path',
                  'http://127.0.0.1:1234@evil.example',
                  'http://127.0.0.1:65536', 'http://127.0.0.1:0', None]
        for url in values:
            with self.subTest(url=url):
                self.write_record(url)
                browser = Mock(return_value=True)
                with patch('urllib.request.build_opener') as opener:
                    with self.assertRaises(launcher.LaunchError):
                        launcher.reopen_existing(self.runtime_path, app_build_id(), browser)
                    opener.assert_not_called()
                browser.assert_not_called()

    def test_redirect_is_not_followed(self):
        with identity_server({'unexpected': True}) as (destination, destination_requests):
            with identity_server(redirect=destination + '/target') as (url, requests):
                self.write_record(url)
                browser = Mock(return_value=True)
                self.assertFalse(launcher.reopen_existing(self.runtime_path,
                                                        app_build_id(), browser))
                browser.assert_not_called()
                self.assertEqual(requests, ['/api/runtime'])
                self.assertEqual(destination_requests, [])

    def test_fresh_identity_mismatch_releases_lock_without_opening(self):
        browser = Mock(return_value=True)
        with patch.object(launcher, 'fetch_runtime', return_value={'app_id': 'other'}):
            with self.assertRaises(launcher.LaunchError):
                launcher.run_desktop(browser_open=browser)
        browser.assert_not_called()
        self.assertFalse(self.runtime_path.exists())
        lock = InstanceLock(self.directory / 'app.lock')
        lock.close()


if __name__ == '__main__':
    unittest.main()
