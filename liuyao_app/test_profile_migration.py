"""Regression coverage for existing profile tables and startup migration."""
import http.cookiejar
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request

from liuyao_app.profile_store import get_profile, list_profiles, save_profile, migrate
from liuyao_app.server import Application, Server
from case_store import Actor, CaseStore

ROOT = Path(__file__).resolve().parents[1]
PID = 'person_' + 'a' * 32
PROFILE = {'name': '原人物', 'bazi': '仅供记录', 'notes': '原备注'}


def legacy_database(path, *, version=0, minimal=False, wal=False):
    db = sqlite3.connect(path)
    if wal:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA wal_autocheckpoint=0')
    db.executescript((ROOT / 'software_prep/case_store.sql').read_text())
    if minimal:
        db.execute('CREATE TABLE person_profiles (person_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, profile_json TEXT NOT NULL)')
        db.execute('INSERT INTO person_profiles VALUES (?,?,?)', (PID, 'local-user', json.dumps(PROFILE, ensure_ascii=False)))
    else:
        db.execute('''CREATE TABLE person_profiles (
            person_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, version INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, profile_json TEXT NOT NULL,
            legacy_note TEXT)''')
        db.execute('INSERT INTO person_profiles VALUES (?,?,?,?,?,?,?)',
                   (PID, 'local-user', 3, '2026-01-01T12:00:00Z', '2026-02-01T12:00:00Z', json.dumps(PROFILE, ensure_ascii=False), 'keep-extra-field'))
    db.execute("INSERT INTO cases VALUES ('old-case','local-user','old-session','2026-01-01T00:00:00Z','{}')")
    db.execute("INSERT INTO feedback VALUES ('old-feedback','old-case',NULL,NULL,'2026-02-01T00:00:00Z','原反馈','self_reported',NULL,NULL)")
    db.execute(f'PRAGMA user_version={version}')
    db.commit()
    return db


def slug_legacy_database(path):
    """Exact seven-column schema reported from the user's Windows database."""
    db = legacy_database(path)
    db.execute('DROP TABLE person_profiles')
    db.execute('''CREATE TABLE person_profiles (
        profile_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, slug TEXT NOT NULL,
        display_name TEXT NOT NULL, details_json TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    db.execute("INSERT INTO case_revisions VALUES ('old-case',1,'old-revision','2026-01-01','initial','original','{}','{}')")
    db.execute('INSERT INTO analysis_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
               ('old-run', 'old-case', 1, None, '2026-01-01', 'a'*64, '{}', 'b'*64, 'c'*64, 'd'*64, 'old-engine'))
    db.execute('INSERT INTO analysis_outcomes VALUES (?,?,?,?,?)',
               ('old-run', '2026-01-01', 'completed', '{"report":"original prediction"}', 'e'*64))
    db.commit()
    return db


class ProfileMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / 'cases.sqlite3'
        self.actor = Actor('local-user', 'test-session')

    def backups(self):
        return list((self.directory / 'backups').glob('*.sqlite3'))

    def test_missing_self_column_preserves_rows_and_allows_profile_writes(self):
        old = legacy_database(self.path)
        before = old.execute('SELECT * FROM person_profiles').fetchall()
        cases = old.execute('SELECT * FROM cases').fetchall()
        old.close()
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual([tuple(r) for r in store.db.execute('SELECT person_id,owner_id,version,created_at,updated_at,profile_json,legacy_note FROM person_profiles')], before)
        self.assertEqual([tuple(r) for r in store.db.execute('SELECT * FROM cases')], cases)
        self.assertEqual(store.db.execute('SELECT reported_outcome FROM feedback').fetchone()[0], '原反馈')
        original = get_profile(store, self.actor, PID)
        self.assertFalse(original['is_self'])
        self.assertEqual(original['profile'], PROFILE)
        save_profile(store, self.actor, {**PROFILE, 'notes': '新备注'}, person_id=PID, expected_version=3, is_self=True, idempotency_key='edit')
        added = save_profile(store, self.actor, {'name': '新增人物'}, is_self=True, idempotency_key='new')
        self.assertTrue(added['is_self'])
        self.assertEqual(added['profile']['name'], '新增人物')
        self.assertFalse(get_profile(store, self.actor, PID)['is_self'])
        self.assertEqual(get_profile(store, self.actor, PID)['legacy_note'], 'keep-extra-field')
        self.assertEqual(len(self.backups()), 1)
        with sqlite3.connect(self.backups()[0]) as backup:
            self.assertEqual(backup.execute('SELECT * FROM person_profiles').fetchall(), before)
            self.assertNotIn('is_self', {r[1] for r in backup.execute('PRAGMA table_info(person_profiles)')})
            self.assertEqual(backup.execute('PRAGMA quick_check').fetchone()[0], 'ok')
        reopened = CaseStore(self.path)
        reopened.close()
        self.assertEqual(len(self.backups()), 1)

    def test_version_number_does_not_skip_partial_schema_repair(self):
        legacy_database(self.path, version=5).close()
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        self.assertFalse(list_profiles(store, self.actor)[0]['is_self'])
        self.assertTrue({'rules_version', 'match_degree', 'user_notes'} <= {r[1] for r in store.db.execute('PRAGMA table_info(feedback)')})

    def test_minimal_profile_metadata_is_added_without_replacing_content(self):
        legacy_database(self.path, minimal=True).close()
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        original = get_profile(store, self.actor, PID)
        self.assertEqual(original['profile'], PROFILE)
        self.assertEqual(original['version'], 1)
        updated = save_profile(store, self.actor, PROFILE, person_id=PID, expected_version=1, is_self=True, idempotency_key='update')
        self.assertEqual(updated['version'], 2)

    def test_new_database_and_reopening_need_no_backup(self):
        store = CaseStore(self.path)
        store.close()
        store = CaseStore(self.path)
        store.close()
        self.assertEqual(self.backups(), [])

    def test_backup_failure_leaves_schema_and_data_untouched(self):
        legacy_database(self.path).close()
        with patch('liuyao_app.profile_store._backup_before_migration', side_effect=OSError('backup unavailable')):
            with self.assertRaisesRegex(OSError, 'backup unavailable'):
                CaseStore(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertNotIn('is_self', {r[1] for r in db.execute('PRAGMA table_info(person_profiles)')})
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)
            self.assertEqual(json.loads(db.execute('SELECT profile_json FROM person_profiles').fetchone()[0]), PROFILE)

    def test_failed_index_creation_rolls_back_added_columns(self):
        db = legacy_database(self.path, minimal=True)
        db.execute('ALTER TABLE person_profiles ADD COLUMN is_self INTEGER DEFAULT 1')
        db.execute('INSERT INTO person_profiles VALUES (?,?,?,?)', ('person_' + 'b' * 32, 'local-user', '{}', 1))
        db.commit(); db.close()
        with self.assertRaises(sqlite3.IntegrityError):
            CaseStore(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertNotIn('version', {r[1] for r in db.execute('PRAGMA table_info(person_profiles)')})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM person_profiles').fetchone()[0], 2)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)
        self.assertEqual(len(self.backups()), 1)

    def test_backup_includes_committed_wal_records(self):
        old = legacy_database(self.path, wal=True)
        self.addCleanup(old.close)
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        with sqlite3.connect(self.backups()[0]) as backup:
            self.assertEqual(json.loads(backup.execute('SELECT profile_json FROM person_profiles').fetchone()[0]), PROFILE)
            self.assertEqual(backup.execute('SELECT reported_outcome FROM feedback').fetchone()[0], '原反馈')

    def test_application_starts_with_old_database_and_serves_profile_api(self):
        legacy_database(self.path).close()
        self.check_profile_http(PROFILE)

    def test_reported_empty_schema_starts_and_serves_profile_api(self):
        slug_legacy_database(self.path).close()
        self.check_profile_http(None)

    def check_profile_http(self, expected_profile):
        app = Application(self.directory)
        self.addCleanup(app.close)
        server = Server(('127.0.0.1', 0), app)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:' + str(server.server_port)
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        client.open(url, timeout=10).close()
        with client.open(url + '/api/profiles', timeout=10) as response:
            profiles = json.load(response)['profiles']
        if expected_profile is None:
            self.assertEqual(profiles, [])
        else:
            self.assertEqual(profiles[0]['profile'], expected_profile)
        body = json.dumps({'profile': {'name': '通过页面新增'}, 'is_self': True}).encode()
        request = urllib.request.Request(url + '/api/profiles', data=body, headers={
            'Content-Type': 'application/json', 'X-App-Request': '1', 'X-Idempotency-Key': 'http-add', 'Origin': url})
        with client.open(request, timeout=10) as response:
            added = json.load(response)
        self.assertTrue(added['is_self'])
        self.assertEqual(added['profile']['name'], '通过页面新增')

    def test_reported_empty_schema_preserves_history_and_supports_new_writes(self):
        db = slug_legacy_database(self.path)
        tables = ('cases', 'case_revisions', 'analysis_runs', 'analysis_outcomes', 'feedback')
        before = {name: db.execute('SELECT * FROM ' + name).fetchall() for name in tables}
        original_schema = db.execute('PRAGMA table_info(person_profiles)').fetchall()
        db.close()
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        for name, expected in before.items():
            rows = [tuple(row)[:len(expected[0])] for row in store.db.execute('SELECT * FROM ' + name)]
            self.assertEqual(rows, expected, name)
        self.assertEqual(list_profiles(store, self.actor), [])
        archives = [r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'person_profiles_legacy_*'")]
        self.assertEqual(len(archives), 1)
        self.assertEqual([tuple(r) for r in store.db.execute('PRAGMA table_info(' + archives[0] + ')')], original_schema)
        self.assertEqual(store.db.execute('SELECT COUNT(*) FROM ' + archives[0]).fetchone()[0], 0)
        new = save_profile(store, self.actor, {'name': '本人'}, is_self=True, idempotency_key='new')
        updated = save_profile(store, self.actor, {'name': '更新本人'}, person_id=new['person_id'], expected_version=1, is_self=True, idempotency_key='update')
        self.assertEqual(updated['version'], 2)
        self.assertEqual(updated['profile']['name'], '更新本人')
        with sqlite3.connect(self.backups()[0]) as backup:
            self.assertEqual(backup.execute('PRAGMA table_info(person_profiles)').fetchall(), original_schema)
            for name in tables:
                self.assertEqual(backup.execute('SELECT * FROM ' + name).fetchall(), before[name])
        reopened = CaseStore(self.path)
        reopened.close()
        self.assertEqual(len(self.backups()), 1)

    def test_reported_schema_with_records_is_not_treated_as_empty(self):
        db = slug_legacy_database(self.path)
        record = ('profile-original', 'local-user', 'self', '旧人物', '{"unknown":"preserve"}', '2026-01-01', '2026-01-02')
        db.execute('INSERT INTO person_profiles VALUES (?,?,?,?,?,?,?)', record)
        db.commit(); db.close()
        with self.assertRaisesRegex(ValueError, '旧式人物档案表含有记录'):
            CaseStore(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT * FROM person_profiles').fetchall(), [record])
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)

    def test_reported_schema_rebuild_rolls_back_if_feedback_migration_fails(self):
        db = slug_legacy_database(self.path)
        self.addCleanup(db.close)
        original_schema = db.execute('PRAGMA table_info(person_profiles)').fetchall()
        class FailureDuringFeedback:
            def execute(self, sql, *args):
                if sql == 'ALTER TABLE feedback ADD COLUMN match_degree TEXT':
                    raise sqlite3.OperationalError('simulated migration interruption')
                return db.execute(sql, *args)
        with self.assertRaisesRegex(sqlite3.OperationalError, 'simulated'):
            migrate(FailureDuringFeedback())
        self.assertEqual(db.execute('PRAGMA table_info(person_profiles)').fetchall(), original_schema)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name GLOB 'person_profiles_legacy_*'").fetchone()[0], 0)
        self.assertNotIn('rules_version', {r[1] for r in db.execute('PRAGMA table_info(feedback)')})
        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)

    def test_reported_schema_with_partial_fix_rebuilds_self_index(self):
        db = slug_legacy_database(self.path)
        db.execute('ALTER TABLE person_profiles ADD COLUMN version INTEGER DEFAULT 1')
        db.execute('ALTER TABLE person_profiles ADD COLUMN is_self INTEGER DEFAULT 0')
        db.execute('CREATE UNIQUE INDEX unique_self_profile ON person_profiles(owner_id) WHERE is_self=1')
        db.execute('PRAGMA user_version=5')
        db.commit(); db.close()
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual(store.db.execute("SELECT tbl_name FROM sqlite_master WHERE name='unique_self_profile'").fetchone()[0], 'person_profiles')
        save_profile(store, self.actor, {'name': '本人'}, is_self=True, idempotency_key='first')
        save_profile(store, self.actor, {'name': '另一人'}, is_self=True, idempotency_key='second')
        self.assertEqual(sum(p['is_self'] for p in list_profiles(store, self.actor)), 1)


if __name__ == '__main__':
    unittest.main()
