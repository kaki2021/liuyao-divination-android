"""Persistent conversation orchestration; existing domain engines own their data."""
import json

from case_store import Actor, Conflict, AccessDenied
from .chat_router import MODES, route
from .workbench_store import dumps, digest, ident, now


class DialogueService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store

    def owned(self, db, owner, dialogue_id):
        return self.store.owned(db, 'wb_dialogues', 'dialogue_id', dialogue_id, owner)

    def create(self, owner, title, idem):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError('请填写对话标题。')
        def action(db):
            dialogue_id = ident('dialogue')
            db.execute('INSERT INTO wb_dialogues VALUES (?,?,?,?,?,?)',
                       (dialogue_id, owner, title.strip(), dumps({}), now(), now()))
            return {'dialogue_id': dialogue_id}
        return self.store.request(owner, idem, ['dialogue', title], action)

    def listing(self, owner):
        with self.store.db() as db:
            return [dict(row) for row in db.execute('''SELECT dialogue_id,title,created_at,updated_at,
                (SELECT count(*) FROM wb_dialogue_turns t WHERE t.dialogue_id=d.dialogue_id) turns
                FROM wb_dialogues d WHERE owner=? ORDER BY updated_at DESC''', (owner,))]

    def detail(self, owner, dialogue_id):
        with self.store.db() as db:
            row = self.owned(db, owner, dialogue_id)
            turns = []
            for turn in db.execute('SELECT * FROM wb_dialogue_turns WHERE dialogue_id=? ORDER BY rowid', (dialogue_id,)):
                value = dict(turn)
                value['result'] = json.loads(value.pop('result_json')) if value['result_json'] else None
                turns.append(value)
            active = []
            for job in db.execute('SELECT job_id,payload FROM wb_jobs WHERE owner=? AND kind=\'assistant\' AND status IN (\'queued\',\'running\')', (owner,)):
                if json.loads(job['payload'])['dialogue_id'] == dialogue_id:
                    active.append(job['job_id'])
            return {'dialogue_id': dialogue_id, 'title': row['title'], 'context': json.loads(row['context_json']),
                    'turns': turns, 'active_jobs': active}

    def enqueue(self, owner, dialogue_id, body, idem):
        if not isinstance(body, dict) or set(body) != {'text', 'mode', 'provider', 'model'}:
            raise ValueError('对话请求字段无效。')
        if not isinstance(body['text'], str) or not 1 <= len(body['text'].strip()) <= 4000 or body['mode'] not in MODES:
            raise ValueError('请输入 1 至 4000 字的内容。')
        if not all(isinstance(body[k], str) and len(body[k]) <= 200 for k in ('provider', 'model')):
            raise ValueError('模型选择无效。')
        if not isinstance(idem, str) or not 1 <= len(idem) <= 160:
            raise ValueError('请求标识无效。')
        fingerprint = digest(['dialogue-turn', dialogue_id, body])
        with self.runtime.lock, self.store.db(True) as db:
            old = db.execute('SELECT * FROM wb_jobs WHERE owner=? AND idem=?', (owner, idem)).fetchone()
            if old:
                if old['digest'] != fingerprint:
                    raise Conflict('请求标识已用于另一条消息。')
                return {'job_id': old['job_id']}
            dialogue = self.owned(db, owner, dialogue_id)
            if db.execute('SELECT 1 FROM wb_dialogue_turns WHERE dialogue_id=? AND status IN (\'queued\',\'running\')', (dialogue_id,)).fetchone():
                raise Conflict('请等待当前这条消息处理完成。')
            if len(self.store.pending(owner)) >= 2:
                raise Conflict('已有两个技能任务正在处理，请稍后再发。')
            context = json.loads(dialogue['context_json'])
            routing = route(body['text'].strip(), context, body['mode'])
            turn_id, job_id = ident('message'), ident('wbjob')
            payload = {**body, 'text': body['text'].strip(), 'dialogue_id': dialogue_id, 'turn_id': turn_id,
                       'context': context, 'routing': routing}
            db.execute('INSERT INTO wb_dialogue_turns VALUES (?,?,?,?,?,?,?)',
                       (turn_id, dialogue_id, payload['text'], body['mode'], 'queued', None, now()))
            db.execute('INSERT INTO wb_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (job_id, owner, idem, fingerprint, 'assistant', dumps(payload), 'queued', None, now(), now()))
        self.runtime.app.pool.submit(self.runtime._run, owner, job_id, 'assistant', payload)
        return {'job_id': job_id}

    def execute(self, owner, payload):
        result = dict(payload['routing'])
        action = result['action']
        if action == 'knowledge':
            self.runtime._model(payload)
            history = []
            detail = self.detail(owner, payload['dialogue_id'])
            for turn in detail['turns']:
                previous = turn['result'] or {}
                if turn['status'] == 'completed' and previous.get('action') == 'knowledge' and previous.get('answer'):
                    history.extend([{'role': 'user', 'content': turn['user_text']}, {'role': 'assistant', 'content': previous['answer']}])
            history = history[-16:]
            while len(history) > 2 and sum(len(m['content']) for m in history) > 28000:
                history = history[2:]
            skill = self.store.skill(owner, 'knowledge')
            result.update(self.runtime._knowledge({**payload, 'question': payload['text'], 'history': history,
                'sources': self.store.search(owner, payload['text'], history), 'skill': skill}))
            result['skill_version'] = skill['version']
        elif action == 'followup':
            self.runtime._model(payload)
            app = self.runtime.app
            actor = Actor(owner, 'dialogue-' + payload['dialogue_id'])
            case_id = payload['context']['active_case']
            app.ensure_idle(actor, case_id)
            cases = app.store()
            try:
                case = cases.export_case(actor, case_id)
                selected = payload['context'].get('active_run')
                runs = case.get('analysis_runs', [])
                run = next((r for r in runs if r['analysis_run_id'] == selected), None) if selected else (runs[-1] if runs else None)
                if not run:
                    return {'action': 'case', 'case_id': case_id, 'answer': '这卦已经保存，还没有完成解卦。可以先展开卦盘并开始分析，再围绕结果继续追问。'}
                from .conversation import start_turn, reply
                turn = start_turn(cases, actor, case_id, run['analysis_run_id'], case['revisions'][-1]['revision_seq'],
                                  payload['text'], idempotency_key=payload['turn_id'])['turn_id']
                # Retain the cross-database link before the billed call. Recovery
                # can adopt an already-saved answer if the final acknowledgement is lost.
                with self.store.db(True) as db:
                    db.execute('UPDATE wb_dialogue_turns SET result_json=? WHERE turn_id=?',
                               (dumps({'action':'followup','case_id':case_id,'_case_turn_id':turn}),payload['turn_id']))
                outcome = reply(cases, actor, case_id, turn, payload['provider'], payload['model'],
                                skill_snapshot=self.store.skill(owner, 'liuyao'))
                if outcome['status'] != 'completed':
                    return {'action': 'followup', 'case_id': case_id, 'error': outcome.get('error'),
                            'answer': outcome.get('error', {}).get('message', '回复尚未完成，追问已经保留。')}
                result.update(outcome['conversation'], case_id=case_id, analysis_run_id=run['analysis_run_id'])
            finally:
                cases.close()
        elif action == 'feedback':
            result.update(title=payload['text'][:120], description=payload['text'])
        return result

    def finish(self, db, owner, payload, status, result):
        row = self.owned(db, owner, payload['dialogue_id'])
        context = json.loads(row['context_json'])
        if status == 'completed':
            action = result.get('action')
            if action == 'cast':
                target = result.get('update_target') or payload['turn_id']
                # Updating a card retains the earlier message and its original defaults.
                context.update(last_skill='liuyao', pending_cast={'turn_id': target, 'prefill': result['prefill']})
            elif action in ('followup', 'case'):
                context['last_skill'] = 'liuyao'
            elif action == 'knowledge':
                context['last_skill'] = 'knowledge'
        db.execute('UPDATE wb_dialogue_turns SET status=?,result_json=? WHERE turn_id=?',
                   (status, dumps(result), payload['turn_id']))
        db.execute('UPDATE wb_dialogues SET context_json=?,updated_at=? WHERE dialogue_id=?',
                   (dumps(context), now(), payload['dialogue_id']))

    def profile(self, owner, dialogue_id, profile_id, idem):
        if profile_id is not None:
            if not isinstance(profile_id, str):
                raise ValueError('人物档案标识无效。')
            from .profile_store import get_profile
            cases = self.runtime.app.store()
            try:get_profile(cases, Actor(owner, 'profile-association'), profile_id)
            finally:cases.close()
        def action(db):
            row = self.owned(db, owner, dialogue_id)
            context = json.loads(row['context_json'])
            context['profile_id'] = profile_id
            db.execute('UPDATE wb_dialogues SET context_json=?,updated_at=? WHERE dialogue_id=?', (dumps(context), now(), dialogue_id))
            return {'profile_id': profile_id}
        return self.store.request(owner, idem, ['dialogue-profile', dialogue_id, profile_id], action)

    def link_feedback(self, owner, dialogue_id, body, idem):
        if not isinstance(body,dict) or set(body)!={'turn_id','issue_id'}:
            raise ValueError('反馈关联格式无效。')
        def action(db):
            self.owned(db,owner,dialogue_id)
            self.store.owned(db,'wb_issues','issue_id',body['issue_id'],owner)
            row=db.execute('SELECT result_json FROM wb_dialogue_turns WHERE dialogue_id=? AND turn_id=?',
                           (dialogue_id,body['turn_id'])).fetchone()
            if not row or not row[0]:raise AccessDenied('message unavailable')
            result=json.loads(row[0])
            if result.get('action')!='feedback':raise ValueError('这条消息不是反馈卡片。')
            if result.get('issue_id') not in (None,body['issue_id']):raise Conflict('这张卡片已经提交了另一条反馈。')
            result['issue_id']=body['issue_id']
            db.execute('UPDATE wb_dialogue_turns SET result_json=? WHERE turn_id=?',(dumps(result),body['turn_id']))
            return {'issue_id':body['issue_id']}
        return self.store.request(owner,idem,['dialogue-feedback',dialogue_id,body],action)

    def draft(self, owner, dialogue_id, body, idem):
        if not isinstance(body,dict) or set(body)!={'card_id','fields','solar_input'}:
            raise ValueError('草稿格式无效。')
        if not isinstance(body['card_id'],str) or len(body['card_id'])>100 or not isinstance(body['fields'],dict):
            raise ValueError('草稿标识无效。')
        if len(dumps(body))>50000 or len(body['fields'])>250:
            raise ValueError('草稿过长，请先保存本次卦例。')
        for key,value in body['fields'].items():
            if not isinstance(key,str) or not isinstance(value,dict) or set(value)-{'value','checked'}:
                raise ValueError('草稿字段无效。')
            if not isinstance(value.get('value'),str) or len(value['value'])>5000 or type(value.get('checked',False)) is not bool:
                raise ValueError('草稿内容无效。')
        if body['solar_input'] is not None:
            from validate_input import validate_input
            if not isinstance(body['solar_input'],dict):raise ValueError('草稿地点格式无效。')
            value={'question':'草稿','lines':['young_yang']*6,**body['solar_input']}
            if not validate_input(value)['valid']:
                raise ValueError('草稿地点格式无效。')
        def action(db):
            row=self.owned(db,owner,dialogue_id)
            context=json.loads(row['context_json'])
            turn=db.execute('SELECT result_json FROM wb_dialogue_turns WHERE dialogue_id=? AND turn_id=?',
                            (dialogue_id,body['card_id'])).fetchone()
            if not turn or not turn[0] or json.loads(turn[0]).get('action')!='cast':
                raise AccessDenied('card unavailable')
            drafts=context.setdefault('drafts',{})
            if len(drafts)>=10 and body['card_id'] not in drafts:
                raise ValueError('此对话已有十份起卦草稿，请先保存。')
            drafts[body['card_id']]={k:body[k] for k in ('fields','solar_input')}
            db.execute('UPDATE wb_dialogues SET context_json=? WHERE dialogue_id=?',(dumps(context),dialogue_id))
            return {'saved':True}
        return self.store.request(owner,idem,['dialogue-draft',dialogue_id,body],action)

    def bind_case(self, owner, dialogue_id, body, idem):
        if not isinstance(body, dict) or set(body) - {'turn_id', 'case_id', 'analysis_run_id'} or 'case_id' not in body:
            raise ValueError('案例关联字段无效。')
        cases = self.runtime.app.store()
        try:
            case = cases.export_case(Actor(owner, 'dialogue-bind'), body['case_id'])
        finally:cases.close()
        run_id = body.get('analysis_run_id')
        if run_id is not None and not any(r['analysis_run_id'] == run_id for r in case['analysis_runs']):
            raise AccessDenied('run unavailable')
        def action(db):
            row = self.owned(db, owner, dialogue_id)
            context = json.loads(row['context_json'])
            turn_id = body.get('turn_id')
            if turn_id:
                turn = db.execute('SELECT result_json FROM wb_dialogue_turns WHERE turn_id=? AND dialogue_id=?', (turn_id, dialogue_id)).fetchone()
                if not turn or not turn[0]:raise AccessDenied('turn unavailable')
                result = json.loads(turn[0])
                if result.get('action') not in ('cast','case'):raise ValueError('只能把卦例关联到对应卡片。')
                if result.get('case_id') not in (None, body['case_id']):raise Conflict('卡片已经关联到另一卦。')
                result['case_id'] = body['case_id']
                db.execute('UPDATE wb_dialogue_turns SET result_json=? WHERE turn_id=?', (dumps(result), turn_id))
            else:
                turn_id = ident('message')
                db.execute('INSERT INTO wb_dialogue_turns VALUES (?,?,?,?,?,?,?)',
                           (turn_id, dialogue_id, '查看已保存的卦例', 'liuyao', 'completed',
                            dumps({'action': 'case', 'case_id': body['case_id'], 'answer': case['revisions'][-1]['input']['question']}), now()))
            context.update(active_case=body['case_id'], active_run=run_id, last_skill='liuyao')
            context.pop('pending_cast', None)
            if context.get('drafts'):context['drafts'].pop(turn_id,None)
            db.execute('UPDATE wb_dialogues SET context_json=?,updated_at=? WHERE dialogue_id=?', (dumps(context), now(), dialogue_id))
            return {'case_id': body['case_id'], 'turn_id': turn_id}
        return self.store.request(owner, idem, ['bind-dialogue-case', dialogue_id, body], action)
