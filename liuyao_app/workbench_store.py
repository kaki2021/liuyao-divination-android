"""Owner-scoped local skill state. Model outcomes and job acknowledgements commit together."""
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from case_store import AccessDenied, Conflict
from . import knowledge
from .skill_registry import DEFAULT_PREFERENCES, SKILL_IDS, validate_preferences


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ident(prefix):
    return prefix + '_' + uuid.uuid4().hex


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(dumps(value).encode('utf-8')).hexdigest()


class WorkbenchStore:
    def __init__(self, path):
        self.path = Path(path)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS wb_documents (
                    document_id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    content TEXT NOT NULL, sha256 TEXT NOT NULL, filename TEXT, active INTEGER NOT NULL,
                    created_at TEXT NOT NULL, UNIQUE(owner,sha256));
                CREATE TABLE IF NOT EXISTS wb_chunks (
                    citation_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    content TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS wb_chats (
                    chat_id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS wb_turns (
                    turn_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, question TEXT NOT NULL,
                    snapshot TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS wb_skill_versions (
                    owner TEXT NOT NULL, skill_id TEXT NOT NULL, version INTEGER NOT NULL,
                    preferences TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(owner,skill_id,version));
                CREATE TABLE IF NOT EXISTS wb_skill_active (
                    owner TEXT NOT NULL, skill_id TEXT NOT NULL, version INTEGER NOT NULL,
                    PRIMARY KEY(owner,skill_id));
                CREATE TABLE IF NOT EXISTS wb_issues (
                    issue_id TEXT PRIMARY KEY, owner TEXT NOT NULL, skill_id TEXT NOT NULL,
                    title TEXT NOT NULL, description TEXT NOT NULL, snapshot TEXT NOT NULL,
                    status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS wb_jobs (
                    job_id TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL,
                    digest TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(owner,idem));
                CREATE TABLE IF NOT EXISTS wb_requests (
                    owner TEXT NOT NULL, idem TEXT NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(owner,idem));
                CREATE INDEX IF NOT EXISTS wb_turn_chat ON wb_turns(chat_id,created_at);
                CREATE INDEX IF NOT EXISTS wb_job_owner ON wb_jobs(owner,status);
            ''')

    @contextmanager
    def db(self, write=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def owned(self, db, table, key, value, owner):
        if (table, key) not in (('wb_chats', 'chat_id'), ('wb_documents', 'document_id'),
                               ('wb_issues', 'issue_id'), ('wb_jobs', 'job_id')):
            raise ValueError('invalid table')
        row = db.execute(f'SELECT * FROM {table} WHERE {key}=? AND owner=?', (value, owner)).fetchone()
        if row is None:
            raise AccessDenied('record unavailable')
        return row

    def request(self, owner, idem, value, action):
        if not isinstance(idem, str) or not 1 <= len(idem) <= 160:
            raise ValueError('请求标识无效。')
        fingerprint = digest(value)
        with self.db(True) as db:
            old = db.execute('SELECT * FROM wb_requests WHERE owner=? AND idem=?', (owner, idem)).fetchone()
            if old:
                if old['digest'] != fingerprint:
                    raise Conflict('request key reused')
                return json.loads(old['result'])
            result = action(db)
            db.execute('INSERT INTO wb_requests VALUES (?,?,?,?)', (owner, idem, fingerprint, dumps(result)))
            return result

    def _skill(self, db, owner, skill_id):
        if skill_id not in SKILL_IDS:
            raise ValueError('没有这个技能。')
        row = db.execute('''SELECT v.* FROM wb_skill_active a JOIN wb_skill_versions v
                            USING(owner,skill_id,version) WHERE a.owner=? AND a.skill_id=?''',
                         (owner, skill_id)).fetchone()
        return {'skill_id': skill_id, 'version': row['version'] if row else 1,
                'preferences': json.loads(row['preferences']) if row else dict(DEFAULT_PREFERENCES)}

    def skill(self, owner, skill_id):
        with self.db() as db:
            return self._skill(db, owner, skill_id)

    def versions(self, owner, skill_id):
        active = self.skill(owner, skill_id)
        with self.db() as db:
            rows = db.execute('SELECT * FROM wb_skill_versions WHERE owner=? AND skill_id=? ORDER BY version DESC',
                              (owner, skill_id)).fetchall()
        revisions = [{'version': r['version'], 'preferences': json.loads(r['preferences']),
                      'reason': r['reason'], 'created_at': r['created_at']} for r in rows]
        if not any(r['version'] == 1 for r in revisions):
            revisions.append({'version': 1, 'preferences': dict(DEFAULT_PREFERENCES),
                              'reason': '内置初始版本', 'created_at': None})
        return {'active': active, 'versions': revisions}

    def _revise(self, db, owner, skill_id, preferences, expected, reason):
        validate_preferences(preferences)
        if self._skill(db, owner, skill_id)['version'] != expected:
            raise Conflict('技能已更新，请重新处理反馈。')
        db.execute('INSERT OR IGNORE INTO wb_skill_versions VALUES (?,?,?,?,?,?)',
                   (owner, skill_id, 1, dumps(DEFAULT_PREFERENCES), '内置初始版本', now()))
        version = db.execute('SELECT COALESCE(MAX(version),1)+1 FROM wb_skill_versions WHERE owner=? AND skill_id=?',
                             (owner, skill_id)).fetchone()[0]
        db.execute('INSERT INTO wb_skill_versions VALUES (?,?,?,?,?,?)',
                   (owner, skill_id, version, dumps(preferences), reason, now()))
        db.execute('INSERT OR REPLACE INTO wb_skill_active VALUES (?,?,?)', (owner, skill_id, version))
        return {'skill_id': skill_id, 'version': version, 'preferences': preferences}

    def rollback(self, owner, skill_id, target, expected, idem):
        if type(target) is not int or type(expected) is not int:
            raise ValueError('版本号无效。')
        def action(db):
            if target == 1:
                preferences = dict(DEFAULT_PREFERENCES)
            else:
                row = db.execute('SELECT preferences FROM wb_skill_versions WHERE owner=? AND skill_id=? AND version=?',
                                 (owner, skill_id, target)).fetchone()
                if row is None:
                    raise ValueError('没有找到这个技能版本。')
                preferences = json.loads(row[0])
            return self._revise(db, owner, skill_id, preferences, expected, '恢复版本 ' + str(target))
        return self.request(owner, idem, ['rollback', skill_id, target, expected], action)

    def documents(self, owner):
        with self.db() as db:
            rows = db.execute('''SELECT document_id,title,sha256,filename,created_at,length(content) characters,
                (SELECT count(*) FROM wb_chunks c WHERE c.document_id=d.document_id) chunks
                FROM wb_documents d WHERE owner=? AND active=1 ORDER BY created_at DESC''', (owner,)).fetchall()
        return [dict(r, version=1) for r in rows]

    def add_document(self, owner, body, idem):
        document = knowledge.import_text(body)
        fragments = list(knowledge.chunks(document['text']))
        def action(db):
            old = db.execute('SELECT document_id FROM wb_documents WHERE owner=? AND sha256=?',
                             (owner, document['sha256'])).fetchone()
            if old:
                db.execute('UPDATE wb_documents SET active=1 WHERE document_id=?', (old[0],))
                return {'document_id': old[0], 'duplicate': True}
            count, size = db.execute('SELECT count(*),COALESCE(sum(length(content)),0) FROM wb_documents WHERE owner=?', (owner,)).fetchone()
            if count >= 200 or size + len(document['text']) > 10_000_000:
                raise ValueError('资料库已达到本机容量上限，请整理后重试。')
            document_id = ident('doc')
            db.execute('INSERT INTO wb_documents VALUES (?,?,?,?,?,?,?,?)',
                       (document_id, owner, document['title'], document['text'], document['sha256'], document['filename'], 1, now()))
            db.executemany('INSERT INTO wb_chunks VALUES (?,?,?,?)',
                           [(f'{document_id}:v1:{i}', document_id, i, text) for i, text in enumerate(fragments, 1)])
            return {'document_id': document_id, 'duplicate': False, 'chunks': len(fragments)}
        return self.request(owner, idem, ['document', document], action)

    def remove_document(self, owner, document_id, idem):
        def action(db):
            self.owned(db, 'wb_documents', 'document_id', document_id, owner)
            db.execute('UPDATE wb_documents SET active=0 WHERE document_id=?', (document_id,))
            return {'document_id': document_id, 'removed': True}
        return self.request(owner, idem, ['remove-document', document_id], action)

    def search(self, owner, question, history=()):
        with self.db() as db:
            rows = [dict(r, version=1) for r in db.execute('''SELECT c.citation_id,c.document_id,c.sequence,
                c.content text,d.title,d.sha256 FROM wb_chunks c JOIN wb_documents d USING(document_id)
                WHERE d.owner=? AND d.active=1''', (owner,))]
        return knowledge.retrieve(rows, question, history)

    def create_chat(self, owner, title, idem):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError('请填写对话标题。')
        def action(db):
            chat_id = ident('chat')
            db.execute('INSERT INTO wb_chats VALUES (?,?,?,?)', (chat_id, owner, title.strip(), now()))
            return {'chat_id': chat_id}
        return self.request(owner, idem, ['chat', title], action)

    def chats(self, owner):
        with self.db() as db:
            return [dict(r) for r in db.execute('''SELECT c.*,
                (SELECT count(*) FROM wb_turns t WHERE t.chat_id=c.chat_id) turns
                FROM wb_chats c WHERE owner=? ORDER BY created_at DESC''', (owner,))]

    def chat(self, owner, chat_id):
        with self.db() as db:
            row = self.owned(db, 'wb_chats', 'chat_id', chat_id, owner)
            turns = [dict(r) for r in db.execute('SELECT * FROM wb_turns WHERE chat_id=? ORDER BY rowid', (chat_id,))]
        for turn in turns:
            turn['result'] = json.loads(turn['result']) if turn['result'] else None
            snapshot = json.loads(turn.pop('snapshot'))
            turn['skill_version'] = snapshot['skill']['version']
        return {**dict(row), 'turns': turns}

    def issues(self, owner):
        with self.db() as db:
            rows = db.execute('SELECT * FROM wb_issues WHERE owner=? ORDER BY created_at DESC', (owner,)).fetchall()
        return [self.issue_view(r) for r in rows]

    @staticmethod
    def issue_view(row):
        result = dict(row)
        result.pop('owner', None)
        result['snapshot'] = json.loads(result['snapshot'])
        result['result'] = json.loads(result['result']) if result['result'] else None
        return result

    def issue(self, owner, issue_id):
        with self.db() as db:
            result = self.issue_view(self.owned(db, 'wb_issues', 'issue_id', issue_id, owner))
            attempts = []
            for row in db.execute('SELECT * FROM wb_jobs WHERE owner=? AND kind=\'issue\' ORDER BY rowid', (owner,)):
                payload = json.loads(row['payload'])
                if payload['issue_id'] == issue_id:
                    attempts.append({'job_id': row['job_id'], 'status': row['status'], 'created_at': row['created_at'],
                                     'skill_version': payload['skill']['version'],
                                     'result': json.loads(row['result']) if row['result'] else None})
            result['attempts'] = attempts
            return result

    def create_issue(self, owner, body, idem):
        if not isinstance(body, dict) or set(body) != {'skill_id', 'title', 'description'}:
            raise ValueError('反馈字段无效。')
        for key, limit in (('title', 200), ('description', 8000)):
            if not isinstance(body[key], str) or not 1 <= len(body[key].strip()) <= limit:
                raise ValueError('请填写问题标题和具体描述。')
        def action(db):
            skill = self._skill(db, owner, body['skill_id'])
            issue_id = ident('issue')
            db.execute('INSERT INTO wb_issues VALUES (?,?,?,?,?,?,?,?,?)',
                       (issue_id, owner, body['skill_id'], body['title'].strip(), body['description'].strip(),
                        dumps({'skill': skill}), 'recorded', None, now()))
            return {'issue_id': issue_id}
        return self.request(owner, idem, ['issue', body], action)

    def job(self, owner, job_id):
        with self.db() as db:
            row = self.owned(db, 'wb_jobs', 'job_id', job_id, owner)
        return {k: row[k] for k in ('job_id', 'kind', 'status', 'created_at', 'updated_at')} | {
            'result': json.loads(row['result']) if row['result'] else None}

    def pending(self, owner):
        with self.db() as db:
            rows = db.execute('SELECT job_id,kind,status,payload FROM wb_jobs WHERE owner=? AND status IN (\'queued\',\'running\')', (owner,)).fetchall()
        return [{'job_id': r['job_id'], 'kind': r['kind'], 'status': r['status'],
                 'chat_id': json.loads(r['payload']).get('chat_id')} for r in rows]

    def recover(self):
        error = dumps({'error': {'code': 'INTERRUPTED', 'message': '上次任务被中断，输入已保留；不会自动重复调用模型。'}})
        with self.db(True) as db:
            for row in db.execute('SELECT * FROM wb_jobs WHERE status IN (\'queued\',\'running\')').fetchall():
                payload = json.loads(row['payload'])
                if row['kind'] == 'knowledge':
                    db.execute('UPDATE wb_turns SET status=\'failed\',result=? WHERE turn_id=?', (error, payload['turn_id']))
                else:
                    db.execute('UPDATE wb_issues SET status=\'failed\',result=? WHERE issue_id=?', (error, payload['issue_id']))
                db.execute('UPDATE wb_jobs SET status=\'failed\',result=?,updated_at=? WHERE job_id=?', (error, now(), row['job_id']))
