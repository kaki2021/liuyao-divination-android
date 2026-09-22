"""Persistent profiles in the case database. Birth data never enters AI input."""
import datetime as dt
import json
from pathlib import Path
import sqlite3
import uuid
from case_store import ident, encoded, AccessDenied, Conflict
from .birth_calendar import calculate_birth_chart
FIELDS={'birth_date':10,'name':200,'gender':40,'birth_time':80,'birth_place':500,'bazi':500,'occupation':200,'industry':200,'tags':1000,'notes':4000}

PROFILE_DEFAULTS = {
    'version': 'INTEGER NOT NULL DEFAULT 1',
    'is_self': 'INTEGER NOT NULL DEFAULT 0',
    'created_at': "TEXT NOT NULL DEFAULT ''",
    'updated_at': "TEXT NOT NULL DEFAULT ''",
}
FEEDBACK_COLUMNS = ('rules_version', 'match_degree', 'user_notes')
PROFILE_REQUIRED = {'person_id', 'owner_id', 'profile_json'}
LEGACY_PROFILE_COLUMNS = {
    'profile_id', 'owner_id', 'slug', 'display_name', 'details_json',
    'created_at', 'updated_at',
}


def _columns(db, table):
    return {row[1] for row in db.execute(f'PRAGMA table_info({table})')}


def _needs_migration(db):
    if db.execute("PRAGMA user_version").fetchone()[0] > 5:
        raise ValueError("该数据库由更新版本创建，请使用对应版本的软件")
    return (not (set(PROFILE_DEFAULTS) | PROFILE_REQUIRED).issubset(_columns(db, 'person_profiles'))
            or not set(FEEDBACK_COLUMNS).issubset(_columns(db, 'feedback'))
            or not db.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='unique_self_profile'").fetchone()
            or db.execute('PRAGMA user_version').fetchone()[0] != 5)


def _backup_before_migration(db):
    filename = next(row[2] for row in db.execute('PRAGMA database_list') if row[1] == 'main')
    if not filename:  # In-memory test databases have no persistent file to protect.
        return
    source_path = Path(filename).resolve()
    directory = source_path.parent / 'backups'
    directory.mkdir(exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = directory / f'{source_path.stem}-before-profile-migration-{stamp}-{uuid.uuid4().hex[:8]}.sqlite3'
    temporary = destination.with_suffix('.tmp')
    try:
        # A separate read connection can back up WAL data while the migration
        # connection holds BEGIN IMMEDIATE, before any schema changes occur.
        source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
        try:
            target = sqlite3.connect(temporary)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def migrate(db, *, backup_existing=True):
    if not _needs_migration(db):
        return
    db.execute('BEGIN IMMEDIATE')
    try:
        # Recheck after locking: another process may have completed migration.
        if not _needs_migration(db):
            db.execute('COMMIT')
            return
        columns = _columns(db, 'person_profiles')
        archive_empty_legacy = False
        if columns and not PROFILE_REQUIRED.issubset(columns):
            if LEGACY_PROFILE_COLUMNS.issubset(columns):
                if db.execute('SELECT 1 FROM person_profiles LIMIT 1').fetchone():
                    raise ValueError('旧式人物档案表含有记录，需要按原资料格式转换；已停止迁移以保留原数据')
                archive_empty_legacy = True
            else:
                raise ValueError('人物档案表缺少基础字段，已停止迁移以保留原数据：' + ', '.join(sorted(PROFILE_REQUIRED - columns)))
        if backup_existing:
            _backup_before_migration(db)
        if archive_empty_legacy:
            # Keep the exact, confirmed-empty legacy table. Rebuilding the
            # active table also removes its old NOT NULL slug/details columns
            # from the write path; merely adding columns would break inserts.
            archive = 'person_profiles_legacy_' + uuid.uuid4().hex
            db.execute(f'ALTER TABLE person_profiles RENAME TO {archive}')
            index = db.execute("SELECT tbl_name FROM sqlite_master WHERE type='index' AND name='unique_self_profile'").fetchone()
            if index and index[0] == archive:
                db.execute('DROP INDEX unique_self_profile')
        db.execute('''CREATE TABLE IF NOT EXISTS person_profiles (
            person_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, version INTEGER NOT NULL,
            is_self INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, profile_json TEXT NOT NULL)''')
        columns = _columns(db, 'person_profiles')
        for name, definition in PROFILE_DEFAULTS.items():
            if name not in columns:
                db.execute(f'ALTER TABLE person_profiles ADD COLUMN {name} {definition}')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS unique_self_profile ON person_profiles(owner_id) WHERE is_self=1')
        columns = _columns(db, 'feedback')
        for name in FEEDBACK_COLUMNS:
            if name not in columns:
                db.execute(f'ALTER TABLE feedback ADD COLUMN {name} TEXT')
        db.execute('PRAGMA user_version=5')
        db.execute('COMMIT')
    except Exception:
        db.execute('ROLLBACK')
        raise

def decode(row):
    row=dict(row);row['profile']=json.loads(row.pop('profile_json'));row['is_self']=bool(row['is_self'])
    profile=row['profile']
    row['birth_chart']=profile.get('bazi_calculation') or calculate_birth_chart(profile.get('birth_date',''),profile.get('birth_time',''))
    return row

def list_profiles(store,actor):
    return [decode(row) for row in store.db.execute('SELECT * FROM person_profiles WHERE owner_id=? ORDER BY is_self DESC,updated_at DESC',(actor.owner_id,))]

def get_profile(store,actor,person_id):
    row=store.db.execute('SELECT * FROM person_profiles WHERE owner_id=? AND person_id=?',(actor.owner_id,person_id)).fetchone()
    if row is None:raise AccessDenied('person profile unavailable')
    return decode(row)

def save_profile(store,actor,profile,*,person_id=None,expected_version=None,is_self=False,idempotency_key):
    if not isinstance(profile,dict) or set(profile)-set(FIELDS):raise ValueError('档案字段无效')
    if type(is_self) is not bool:raise ValueError('本人标记须为布尔值')
    normalized={}
    for key,limit in FIELDS.items():
        value=profile.get(key,'')
        if not isinstance(value,str) or len(value)>limit:raise ValueError(key+'格式或长度不正确')
        normalized[key]=value.strip()
    if not normalized['name']:raise ValueError('请填写姓名或称呼')
    if normalized['birth_date'] or normalized['birth_time']:
        birth=calculate_birth_chart(normalized['birth_date'],normalized['birth_time'])
        if birth['status']=='error':raise ValueError(birth['message'])
        normalized['birth_date']=birth['birth_date']
        normalized['bazi']=birth['text']
        normalized['bazi_calculation']=birth
    def action():
        now=store.clock();pid=person_id or ident('person');version=1;created=now
        if person_id:
            old=get_profile(store,actor,person_id)
            if type(expected_version) is not int or old['version']!=expected_version:raise Conflict('档案已更新，请重新打开')
            version=old['version']+1;created=old['created_at']
        if is_self:store.db.execute('UPDATE person_profiles SET is_self=0,version=version+1,updated_at=? WHERE owner_id=? AND is_self=1 AND person_id<>?',(now,actor.owner_id,pid))
        if person_id:store.db.execute('UPDATE person_profiles SET version=?,is_self=?,updated_at=?,profile_json=? WHERE owner_id=? AND person_id=?',(version,int(is_self),now,encoded(normalized),actor.owner_id,pid))
        else:store.db.execute('INSERT INTO person_profiles (person_id,owner_id,version,is_self,created_at,updated_at,profile_json) VALUES (?,?,?,?,?,?,?)',(pid,actor.owner_id,version,int(is_self),created,now,encoded(normalized)))
        return get_profile(store,actor,pid)
    return store._write(actor,'save_profile',idempotency_key,dict(person_id=person_id,profile=normalized,expected_version=expected_version,is_self=is_self),action)
