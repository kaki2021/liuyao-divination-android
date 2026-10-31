"""知人本地数据服务。与六爻案例/人物档案隔离，不进行任何远程传输。"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

FIELDS = {
    "name": 120, "city": 120, "industry": 160, "occupation": 160,
    "contact": 400, "notes": 3000, "relationship": 120
}
LIST_FIELDS = ("categories", "skills", "interests", "needs")
CARD_FIELDS = {"name", "city", "industry", "occupation", "contact",
               "skills", "interests", "needs"}
KINDS = {"需求", "动态", "倡议", "活动"}


class ZhirenError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, field, limit, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ZhirenError(field + "格式有误或内容过长")
    value = value.strip()
    if required and not value:
        raise ZhirenError(field + "不能为空")
    return value


def lists(value, field):
    if not isinstance(value, list) or len(value) > 30:
        raise ZhirenError(field + "必须为不超过30项的列表")
    result = []
    for item in value:
        item = text(item, field, 80, required=True)
        if item not in result:
            result.append(item)
    return result


def validate_person(data):
    if not isinstance(data, dict) or set(data) - (set(FIELDS) | set(LIST_FIELDS)):
        raise ZhirenError("人物资料含有不支持的字段")
    result = {k: text(data.get(k, ""), k, maximum, required=(k == "name"))
              for k, maximum in FIELDS.items()}
    result.update({k: lists(data.get(k, []), k) for k in LIST_FIELDS})
    return result


class ZhirenStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS people (
                  person_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                  profile_json TEXT NOT NULL, version INTEGER NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_people_owner ON people(owner_id);
                CREATE TABLE IF NOT EXISTS cards (
                  card_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                  name TEXT NOT NULL, fields_json TEXT NOT NULL,
                  audience TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS posts (
                  post_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                  kind TEXT NOT NULL, content TEXT NOT NULL,
                  recipients_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                  owner_id TEXT NOT NULL, request_key TEXT NOT NULL,
                  response_json TEXT NOT NULL,
                  PRIMARY KEY(owner_id, request_key));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA busy_timeout=10000")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _person(row):
        result = json.loads(row["profile_json"])
        result.update(person_id=row["person_id"], version=row["version"],
                      created_at=row["created_at"], updated_at=row["updated_at"])
        return result

    @staticmethod
    def _previous(db, owner, key):
        row = db.execute("SELECT response_json FROM requests WHERE owner_id=? AND request_key=?",
                         (owner, key)).fetchone()
        return json.loads(row["response_json"]) if row else None

    @staticmethod
    def _remember(db, owner, key, result):
        db.execute("INSERT INTO requests(owner_id,request_key,response_json) VALUES(?,?,?)",
                   (owner, key, json.dumps(result, ensure_ascii=False)))

    def list_people(self, owner):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM people WHERE owner_id=? ORDER BY updated_at DESC",
                              (owner,)).fetchall()
            return [self._person(row) for row in rows]

    def save_person(self, owner, payload, request_key):
        if not isinstance(payload, dict) or set(payload) - {"person", "person_id", "expected_version"}:
            raise ZhirenError("人物请求字段不正确")
        person = validate_person(payload.get("person"))
        person_id = payload.get("person_id")
        expected = payload.get("expected_version")
        if person_id is not None and (not isinstance(person_id, str) or len(person_id) > 64):
            raise ZhirenError("人物编号无效")
        if person_id is not None and (type(expected) is not int or expected < 1):
            raise ZhirenError("更新人物须提供原始版本")
        if person_id is None and expected is not None:
            raise ZhirenError("新增人物不需要版本")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = self._previous(db, owner, request_key)
            if old is not None:
                return old
            timestamp = now()
            if person_id is None:
                person_id = uuid.uuid4().hex
                db.execute("INSERT INTO people VALUES(?,?,?,?,?,?)",
                           (person_id, owner, json.dumps(person, ensure_ascii=False), 1,
                            timestamp, timestamp))
                version = 1
            else:
                cur = db.execute("UPDATE people SET profile_json=?,version=version+1,updated_at=? "
                                 "WHERE owner_id=? AND person_id=? AND version=?",
                                 (json.dumps(person, ensure_ascii=False), timestamp,
                                  owner, person_id, expected))
                if cur.rowcount != 1:
                    raise ZhirenError("人物记录不存在或已被修改，请重新打开")
                version = expected + 1
            result = {**person, "person_id": person_id, "version": version,
                      "updated_at": timestamp}
            self._remember(db, owner, request_key, result)
            return result

    def list_cards(self, owner):
        with self.connect() as db:
            return [dict(card_id=r["card_id"], name=r["name"],
                         fields=json.loads(r["fields_json"]), audience=r["audience"])
                    for r in db.execute("SELECT * FROM cards WHERE owner_id=? ORDER BY created_at",
                                        (owner,))]

    def save_card(self, owner, data, request_key):
        if not isinstance(data, dict) or set(data) != {"name", "fields", "audience"}:
            raise ZhirenError("名片字段不完整")
        name = text(data["name"], "名片名称", 80, True)
        audience = text(data["audience"], "分享对象", 200)
        fields = lists(data["fields"], "展示字段")
        if not fields or set(fields) - CARD_FIELDS:
            raise ZhirenError("名片展示字段无效")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = self._previous(db, owner, request_key)
            if old is not None:
                return old
            result = dict(card_id=uuid.uuid4().hex, name=name,
                          fields=fields, audience=audience)
            db.execute("INSERT INTO cards VALUES(?,?,?,?,?,?)",
                       (result["card_id"], owner, name, json.dumps(fields), audience, now()))
            self._remember(db, owner, request_key, result)
            return result

    def list_posts(self, owner):
        with self.connect() as db:
            return [dict(post_id=r["post_id"], kind=r["kind"], content=r["content"],
                         recipient_ids=json.loads(r["recipients_json"]),
                         delivery_status="not_sent", created_at=r["created_at"])
                    for r in db.execute("SELECT * FROM posts WHERE owner_id=? ORDER BY created_at DESC",
                                        (owner,))]

    def save_post(self, owner, data, request_key):
        if not isinstance(data, dict) or set(data) != {"kind", "content", "recipient_ids"}:
            raise ZhirenError("发布内容字段不完整")
        if data["kind"] not in KINDS:
            raise ZhirenError("请选择需求、动态、倡议或活动")
        content = text(data["content"], "发布内容", 4000, True)
        recipients = data["recipient_ids"]
        if not isinstance(recipients, list) or len(recipients) > 500 or any(
                not isinstance(v, str) or len(v) > 64 for v in recipients):
            raise ZhirenError("通知名单无效")
        recipients = list(dict.fromkeys(recipients))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = self._previous(db, owner, request_key)
            if old is not None:
                return old
            if recipients:
                marks = ",".join("?" for _ in recipients)
                count = db.execute(
                    "SELECT count(*) FROM people WHERE owner_id=? AND person_id IN (" + marks + ")",
                    [owner, *recipients]).fetchone()[0]
                if count != len(recipients):
                    raise ZhirenError("通知名单包含不存在的人物")
            result = dict(post_id=uuid.uuid4().hex, kind=data["kind"],
                          content=content, recipient_ids=recipients,
                          delivery_status="not_sent", created_at=now())
            db.execute("INSERT INTO posts VALUES(?,?,?,?,?,?)",
                       (result["post_id"], owner, result["kind"], content,
                        json.dumps(recipients), result["created_at"]))
            self._remember(db, owner, request_key, result)
            return result
