"""Local V0.9 people-memory state; Zhiren's canonical people table remains authoritative for cross-Skill IDs.

The editable UI snapshot is kept in the same SQLite file, with revision conflict
protection. Core search/profile records are updated in the SAME transaction.
This is a local, owner-scoped MVP, not a network social feed.
"""
import copy
import json
import sqlite3
from .zhiren_store import ZhirenStore, ZhirenError, validate_person, now

MAX_PEOPLE = 2000
MAX_POSTS = 3000
MAX_STATE_BYTES = 6_500_000

def _list(value, limit=30, max_chars=80):
    if not isinstance(value, list) or len(value)>limit:
        raise ZhirenError('人物列表字段格式无效')
    return [x.strip()[:max_chars] for x in value if isinstance(x,str) and x.strip()][:limit]

def _canonical(p):
    name=(p.get('name') or p.get('nickname') or '').strip()
    if not name:raise ZhirenError('请填写姓名或昵称')
    return validate_person({
        'name':name[:120],
        'city':str(p.get('city') or '')[:120],
        'industry':str(p.get('industry') or '')[:160],
        'occupation':str(p.get('role') or p.get('occupation') or '')[:160],
        'contact':str(p.get('wechat') or p.get('contact') or '')[:400],
        'notes':str(p.get('bio') or p.get('notes') or '')[:3000],
        'relationship':str(p.get('relationship') or '')[:120],
        'categories':_list(p.get('groups') or p.get('categories') or []),
        'skills':_list(p.get('skills') or []),
        'interests':_list(p.get('interests') or []),
        'needs':_list(p.get('needs') or []),
    })

def _as_v09(p):
    return {
        'id':p['person_id'], 'name':p.get('name',''), 'nickname':'',
        'city':p.get('city',''), 'industry':p.get('industry',''),
        'role':p.get('occupation',''), 'wechat':p.get('contact',''),
        'bio':p.get('notes',''), 'metAt':'', 'photo':None,
        'groups':list(p.get('categories') or []), 'skills':list(p.get('skills') or []),
        'interests':list(p.get('interests') or []),
        'needs':list(p.get('needs') or []), 'birthday':'',
    }

class ZhirenV09Data:
    def __init__(self, file_path):
        self.z=ZhirenStore(file_path)
        with self.z.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS ui_v09_state (
              owner_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
              snapshot_json TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS ui_v09_requests (
              owner_id TEXT NOT NULL, request_key TEXT NOT NULL, revision INTEGER NOT NULL,
              PRIMARY KEY(owner_id,request_key))''')

    def load(self,owner):
        with self.z.connect() as db:
            row=db.execute('SELECT revision,snapshot_json FROM ui_v09_state WHERE owner_id=?',(owner,)).fetchone()
            people_rows=db.execute('SELECT * FROM people WHERE owner_id=? ORDER BY updated_at DESC',(owner,)).fetchall()
            if row:
                state=json.loads(row['snapshot_json'])
                known={p.get('id') for p in state['people']}
                new=[_as_v09(self.z._person(p)) for p in people_rows if p['person_id'] not in known]
                if new:
                    state['people'].extend(new)
                    # Imported people are included in the next save with their stable ID.
                return {'revision':row['revision'],'state':state}
            # No fake/demo contacts on a real device.
            people=[_as_v09(self.z._person(p)) for p in people_rows]
            posts=[{'id':p['post_id'],'author':'me','text':p['content'],'type':p['kind'],
                'date':p['created_at'],'audience':'all','people':[],
                'invitation':{'selected':json.loads(p['recipients_json']),'omitted':[],'recommended':[],'simulated':True},
                'replies':[]} for p in db.execute('SELECT * FROM posts WHERE owner_id=?',(owner,))]
            cards=[{'id':p['card_id'],'title':p['name'],'description':p['audience'],
                'fields':['role' if x=='occupation' else 'wechat' if x=='contact' else x
                          for x in json.loads(p['fields_json'])],'groups':[],'persons':[]}
                    for p in db.execute('SELECT * FROM cards WHERE owner_id=?',(owner,))]
            categories=sorted({g for p in people for g in p['groups']})
            return {'revision':0,'state':{'version':9,'people':people,'posts':posts,
                'categories':categories,'cards':cards,'inbox':[],'events':[],
                'outbox':[],'history':[],'reports':{},'self':{}}}

    def save(self,owner,body,request_key):
        if not isinstance(body,dict) or set(body)!={'revision','state'}:
            raise ZhirenError('资料保存请求格式错误')
        revision=body['revision']
        state=body['state']
        if type(revision) is not int or revision<0:
            raise ZhirenError('本地资料版本无效')
        if not isinstance(state,dict) or not all(isinstance(state.get(x),list) for x in
                ('people','posts','cards','categories','inbox','events','outbox','history')):
            raise ZhirenError('本地资料缺少必要字段')
        if not isinstance(state.get('reports'),dict) or not isinstance(state.get('self'),dict):
            raise ZhirenError('档案数据结构无效')
        if len(state['people'])>MAX_PEOPLE or len(state['posts'])>MAX_POSTS:
            raise ZhirenError('资料数量超过当前版本限制')
        raw=json.dumps(state,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        if len(raw.encode('utf8'))>MAX_STATE_BYTES:
            raise ZhirenError('照片或附件过大，请先缩小或导出备份')
        ids=set()
        canon={}
        for p in state['people']:
            if not isinstance(p,dict):raise ZhirenError('人物记录格式错误')
            pid=p.get('id')
            if not isinstance(pid,str) or not 1<=len(pid)<=64 or pid in ids:
                raise ZhirenError('人物编号重复或无效')
            ids.add(pid)
            canon[pid]=_canonical(p)
        for c in state['categories']:
            if not isinstance(c,str) or len(c)>80:raise ZhirenError('分类名称无效')
        with self.z.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            request=db.execute('SELECT revision FROM ui_v09_requests WHERE owner_id=? AND request_key=?',
                               (owner,request_key)).fetchone()
            if request:return {'revision':request['revision'],'saved':True}
            row=db.execute('SELECT revision FROM ui_v09_state WHERE owner_id=?',(owner,)).fetchone()
            current=row['revision'] if row else 0
            if current!=revision:
                raise ZhirenError('人物档案已在另一窗口更新，请刷新后重新操作')
            stamp=now()
            existing={r['person_id']:r for r in db.execute('SELECT * FROM people WHERE owner_id=?',(owner,))}
            for pid,item in canon.items():
                normalized=json.dumps(item,ensure_ascii=False)
                if pid in existing:
                    old=existing[pid]
                    if json.loads(old['profile_json'])!=item:
                        db.execute('UPDATE people SET profile_json=?,version=?,updated_at=? WHERE owner_id=? AND person_id=?',
                            (normalized,old['version']+1,stamp,owner,pid))
                else:
                    db.execute('INSERT INTO people VALUES(?,?,?,?,?,?)',
                               (pid,owner,normalized,1,stamp,stamp))
            # Absent rows are retained for referential integrity of old divination cases.
            updated=current+1
            db.execute('INSERT INTO ui_v09_state VALUES(?,?,?,?) ON CONFLICT(owner_id) DO UPDATE SET '
                       'revision=excluded.revision,snapshot_json=excluded.snapshot_json,updated_at=excluded.updated_at',
                       (owner,updated,raw,stamp))
            db.execute('INSERT INTO ui_v09_requests VALUES(?,?,?)',(owner,request_key,updated))
            return {'revision':updated,'saved':True}

    def for_search(self,owner):
        people=self.z.list_people(owner)
        state=self.load(owner)['state']
        enriched={p['id']:p for p in state['people'] if isinstance(p,dict) and isinstance(p.get('id'),str)}
        for p in people:
            raw=enriched.get(p['person_id'],{})
            # These details stay on-device; no private notes/contacts are sent to cloud models.
            p.update(nickname=raw.get('nickname',''),role=raw.get('role',''),
                     bio=raw.get('bio',''),metAt=raw.get('metAt',''))
        return people
