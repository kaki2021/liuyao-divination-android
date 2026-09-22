"""SQLite service-data foundation. Trusted Actor must come from the future API session.

No HTTP server, identity provider, AI calls, legal retention policy, or full
divination engine is implemented here. Inputs and outputs are retained as facts;
storing an interpretation does not certify its truth or validate its inference.
"""
from dataclasses import dataclass
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import sqlite3
import uuid
from validate_input import validate_input, valid_timestamp
from casting_input import normalize_casting_input

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def content_digest(value): return hashlib.sha256(encoded(value).encode('utf-8')).hexdigest()
def utc_now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
def ident(prefix): return prefix + '_' + uuid.uuid4().hex
def nonempty(value, name):
    if not isinstance(value, str) or not value.strip(): raise ValueError(name + ' must be non-empty text')

@dataclass(frozen=True)
class Actor:
    owner_id: str
    session_id: str
    def __post_init__(self):
        nonempty(self.owner_id, 'owner_id'); nonempty(self.session_id, 'session_id')

def normalized_profile_id(input_data):
    return (input_data.get('person_info') or {}).get('profile_id')

class AccessDenied(PermissionError): pass
class Conflict(ValueError): pass

class CaseStore:
    def __init__(self, path, *, clock=utc_now):
        self.clock = clock
        backup_existing = str(path) != ':memory:' and Path(path).is_file() and Path(path).stat().st_size > 0
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute('PRAGMA busy_timeout=5000')
            if self.db.execute('PRAGMA user_version').fetchone()[0] > 5:
                raise ValueError('该数据库由更新版本创建，请使用对应版本的软件')
            self.db.executescript(Path(__file__).with_name('case_store.sql').read_text())
            from liuyao_app.profile_store import migrate
            migrate(self.db, backup_existing=backup_existing)
        except Exception:
            self.db.close()
            raise
        # Database guards prevent accidental replacement of historical records.
        # Privileged retention/erasure workflows require a separately designed path.
        for table in ('cases','case_revisions','context_events','analysis_runs','analysis_outcomes','ai_events','feedback','intake_failures'):
            for operation in ('UPDATE','DELETE'):
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only service history'); END")

    def close(self): self.db.close()

    def _owned(self, actor, case_id):
        row = self.db.execute('SELECT * FROM cases WHERE case_id=? AND owner_id=?', (case_id, actor.owner_id)).fetchone()
        if row is None: raise AccessDenied('case not available to this owner')
        return row

    def _run(self, actor, case_id, run_id):
        self._owned(actor, case_id)
        row = self.db.execute('SELECT * FROM analysis_runs WHERE analysis_run_id=? AND case_id=?', (run_id, case_id)).fetchone()
        if row is None: raise AccessDenied('analysis run does not belong to this case')
        return row

    def _write(self, actor, operation, key, payload, action):
        if not isinstance(actor, Actor): raise TypeError('Actor must be supplied by the trusted service')
        nonempty(key, 'idempotency_key')
        if len(key) > 160: raise ValueError('idempotency key too long')
        request_digest = content_digest(payload)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            previous = self.db.execute('SELECT * FROM idempotency WHERE owner_id=? AND operation=? AND idempotency_key=?', (actor.owner_id, operation, key)).fetchone()
            if previous:
                if previous['request_digest'] != request_digest: raise Conflict('idempotency key reused with different content')
                response = json.loads(previous['response_json'])
            else:
                response = action()
                self.db.execute('INSERT INTO idempotency VALUES (?,?,?,?,?)', (actor.owner_id, operation, key, request_digest, encoded(response)))
            self.db.execute('COMMIT')
            return response
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    @staticmethod
    def _time_context(data):
        actual = data.get('actual_cast_time')
        return {'actual_cast_time': actual,
                'precision': 'subsecond' if actual and '.' in actual else ('second' if actual else 'unknown'),
                'provenance': 'user_supplied' if actual else 'unknown'}

    def create_case(self, actor, input_data, *, idempotency_key):
        validation = validate_input(input_data)
        normalized = normalize_casting_input(input_data) if validation['valid'] else None
        def action():
            recorded = self.clock()
            if not validation['valid']:
                failure_id = ident('failure')
                related = {k:input_data[k] for k in ('question','lines','casting','actual_cast_time') if isinstance(input_data,dict) and k in input_data}
                self.db.execute('INSERT INTO intake_failures VALUES (?,?,?,?,?,?)', (failure_id,actor.owner_id,actor.session_id,recorded,encoded(related),encoded(validation['errors'])))
                return {'accepted':False,'failure_id':failure_id,'recorded_at':recorded,'errors':validation['errors']}
            profile_id=normalized_profile_id(normalized)
            if profile_id:
                from liuyao_app.profile_store import get_profile
                get_profile(self,actor,profile_id)
            case_id = ident('case')
            self.db.execute('INSERT INTO cases VALUES (?,?,?,?,?)', (case_id,actor.owner_id,actor.session_id,recorded,encoded(normalized)))
            self.db.execute('INSERT INTO case_revisions VALUES (?,?,?,?,?,?,?,?)', (case_id,1,ident('revision'),recorded,'initial','用户首次提交',encoded(normalized),encoded(self._time_context(normalized))))
            return {'accepted':True,'case_id':case_id,'revision_seq':1,'recorded_at':recorded}
        return self._write(actor,'create_case',idempotency_key,input_data,action)

    def revise_case(self, actor, case_id, input_data, *, reason, expected_revision_seq, idempotency_key):
        validation = validate_input(input_data)
        if not validation['valid']: raise ValueError(encoded(validation['errors']))
        normalized = normalize_casting_input(input_data)
        nonempty(reason,'reason')
        def action():
            self._owned(actor,case_id)
            profile_id=normalized_profile_id(normalized)
            if profile_id:
                from liuyao_app.profile_store import get_profile
                get_profile(self,actor,profile_id)
            current = self.db.execute('SELECT MAX(revision_seq) FROM case_revisions WHERE case_id=?',(case_id,)).fetchone()[0]
            if current != expected_revision_seq: raise Conflict('case was revised; load the current revision first')
            seq = current+1;recorded=self.clock()
            self.db.execute('INSERT INTO case_revisions VALUES (?,?,?,?,?,?,?,?)',(case_id,seq,ident('revision'),recorded,'user_correction',reason,encoded(normalized),encoded(self._time_context(normalized))))
            return {'case_id':case_id,'revision_seq':seq,'recorded_at':recorded}
        return self._write(actor,'revise_case',idempotency_key,{'case_id':case_id,'input':input_data,'reason':reason,'expected_revision_seq':expected_revision_seq},action)

    def append_context_event(self, actor, case_id, *, event_type, content, idempotency_key):
        if event_type not in ('background','clarification_question','clarification_answer','intent_interpretation','user_correction','unresolved_notice','service_failure'):
            raise ValueError('unsupported service context event')
        if not isinstance(content,dict) or not content: raise ValueError('content must be a nonempty service-related object')
        def action():
            self._owned(actor,case_id)
            seq=self.db.execute('SELECT COALESCE(MAX(event_seq),0)+1 FROM context_events WHERE case_id=?',(case_id,)).fetchone()[0]
            event_id=ident('event');recorded=self.clock()
            self.db.execute('INSERT INTO context_events VALUES (?,?,?,?,?,?,?)',(event_id,case_id,seq,event_type,recorded,actor.session_id,encoded(content)))
            return {'event_id':event_id,'event_seq':seq,'recorded_at':recorded}
        return self._write(actor,'context_event',idempotency_key,{'case_id':case_id,'event_type':event_type,'content':content},action)

    def start_analysis(self, actor, case_id, *, source_hash, rules_digest, prompt_digest, engine_build, idempotency_key, expected_revision_seq=None, parent_run_id=None):
        for name,value in (('source_hash',source_hash),('rules_digest',rules_digest),('prompt_digest',prompt_digest)):
            if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value): raise ValueError(name+' must be a SHA256 digest')
        nonempty(engine_build,'engine_build')
        payload=dict(case_id=case_id,source_hash=source_hash,rules_digest=rules_digest,prompt_digest=prompt_digest,engine_build=engine_build,expected_revision_seq=expected_revision_seq,parent_run_id=parent_run_id)
        def action():
            self._owned(actor,case_id)
            if parent_run_id:self._run(actor,case_id,parent_run_id)
            rev=self.db.execute('SELECT * FROM case_revisions WHERE case_id=? ORDER BY revision_seq DESC LIMIT 1',(case_id,)).fetchone()
            if expected_revision_seq is not None and rev['revision_seq']!=expected_revision_seq:raise Conflict('question revision changed')
            events=[self._decode_context(r) for r in self.db.execute('SELECT * FROM context_events WHERE case_id=? ORDER BY event_seq',(case_id,))]
            snapshot={'case_id':case_id,'revision_seq':rev['revision_seq'],'input':json.loads(rev['input_json']),'time_context':json.loads(rev['time_context_json']),'context_events':events}
            profile_id=normalized_profile_id(snapshot['input'])
            if profile_id:
                from liuyao_app.profile_store import get_profile
                snapshot['person_profile_snapshot']=get_profile(self,actor,profile_id)
            snapshot_id=content_digest(snapshot);run_id=ident('analysis');recorded=self.clock()
            self.db.execute('INSERT INTO analysis_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',(run_id,case_id,rev['revision_seq'],parent_run_id,recorded,snapshot_id,encoded(snapshot),source_hash,rules_digest,prompt_digest,engine_build))
            return {'case_id':case_id,'analysis_run_id':run_id,'revision_seq':rev['revision_seq'],'input_snapshot_id':snapshot_id,'analyzed_at':recorded,'status':'running'}
        return self._write(actor,'start_analysis',idempotency_key,payload,action)

    def finish_analysis(self, actor, case_id, analysis_run_id, *, status, idempotency_key, chart_snapshot=None, evidence=None, report=None, validation=None, unresolved=None, error=None):
        if status not in ('completed','partial','unresolved','failed'):raise ValueError('invalid terminal status')
        if status=='completed' and report is None:raise ValueError('completed run requires its retained report')
        if status in ('partial','unresolved') and not unresolved:raise ValueError('partial/unresolved run requires unresolved reasons')
        if status=='failed' and error is None:raise ValueError('failed run requires error details')
        if evidence is not None and not isinstance(evidence,list):raise ValueError('evidence must be a list')
        result={'status':status,'chart_snapshot':chart_snapshot,'evidence':evidence or [],'report':report,'validation':validation or {},'unresolved':unresolved or [],'error':error}
        def action():
            self._run(actor,case_id,analysis_run_id)
            if self.db.execute('SELECT 1 FROM analysis_outcomes WHERE analysis_run_id=?',(analysis_run_id,)).fetchone():raise Conflict('run already finalized; create another run instead of replacing its report')
            recorded=self.clock();digest=content_digest(result)
            self.db.execute('INSERT INTO analysis_outcomes VALUES (?,?,?,?,?)',(analysis_run_id,recorded,status,encoded(result),digest))
            return {'analysis_run_id':analysis_run_id,'status':status,'recorded_at':recorded,'result_digest':digest}
        return self._write(actor,'finish_analysis',idempotency_key,{'case_id':case_id,'analysis_run_id':analysis_run_id,'result':result},action)

    def add_ai_event(self, actor, case_id, analysis_run_id, *, stage, attempt_id, raw_output, parse_status, validation_errors, idempotency_key, adopted_output=None, model_run_metadata=None):
        nonempty(stage,'stage');nonempty(attempt_id,'attempt_id')
        if not isinstance(raw_output,str):raise ValueError('raw_output must be a string, including empty output on provider failure')
        if parse_status not in ('parsed','invalid_json','provider_error','not_parsed'):raise ValueError('invalid parse_status')
        if not isinstance(validation_errors,list):raise ValueError('validation_errors must be a list')
        if adopted_output is not None and (parse_status!='parsed' or validation_errors):raise ValueError('invalid AI output cannot be adopted')
        event={'event_type':'ai_attempt','stage':stage,'attempt_id':attempt_id,'raw_output':raw_output,'parse_status':parse_status,'validation_errors':validation_errors,'adopted_output':adopted_output,'adopted_output_digest':content_digest(adopted_output) if adopted_output is not None else None,'model_run_metadata':model_run_metadata or {}}
        def action():
            self._run(actor,case_id,analysis_run_id)
            if self.db.execute('SELECT 1 FROM analysis_outcomes WHERE analysis_run_id=?',(analysis_run_id,)).fetchone():raise Conflict('cannot attach a new AI attempt to a finalized run')
            if self.db.execute('SELECT 1 FROM ai_events WHERE analysis_run_id=? AND stage=? AND attempt_id=?',(analysis_run_id,stage,attempt_id)).fetchone():raise Conflict('attempt_id already retained')
            event_id=ident('ai');recorded=self.clock()
            self.db.execute('INSERT INTO ai_events VALUES (?,?,?,?,?,?)',(event_id,analysis_run_id,recorded,stage,attempt_id,encoded(event)))
            return {'event_id':event_id,'analysis_run_id':analysis_run_id,'recorded_at':recorded}
        return self._write(actor,'add_ai_event',idempotency_key,{'case_id':case_id,'analysis_run_id':analysis_run_id,'event':event},action)

    def add_feedback(self, actor, case_id, *, reported_outcome, idempotency_key, occurred_at=None, analysis_run_id=None, verification_status='self_reported', verification_method=None, supersedes_feedback_id=None, match_degree=None, user_notes=None):
        nonempty(reported_outcome,'reported_outcome')
        if occurred_at is not None and not valid_timestamp(occurred_at):raise ValueError('invalid actual feedback occurrence time')
        if verification_status not in ('self_reported','externally_supported','disputed','unknown'):raise ValueError('invalid verification status')
        if verification_status=='externally_supported' and not verification_method:raise ValueError('external support requires a recorded verification method')
        if match_degree not in (None,'matched','partly_matched','unmatched','pending'):raise ValueError('匹配程度无效')
        if user_notes is not None and (not isinstance(user_notes,str) or len(user_notes)>4000):raise ValueError('反馈备注过长')
        payload=dict(match_degree=match_degree,user_notes=user_notes,case_id=case_id,analysis_run_id=analysis_run_id,reported_outcome=reported_outcome,occurred_at=occurred_at,verification_status=verification_status,verification_method=verification_method,supersedes_feedback_id=supersedes_feedback_id)
        def action():
            self._owned(actor,case_id)
            if analysis_run_id:self._run(actor,case_id,analysis_run_id)
            if supersedes_feedback_id and not self.db.execute('SELECT 1 FROM feedback WHERE feedback_id=? AND case_id=?',(supersedes_feedback_id,case_id)).fetchone():raise AccessDenied('feedback correction target does not belong to this case')
            feedback_id=ident('feedback');recorded=self.clock()
            rules_version=None
            if analysis_run_id:
                outcome=self.db.execute('SELECT result_json FROM analysis_outcomes WHERE analysis_run_id=?',(analysis_run_id,)).fetchone()
                if outcome:rules_version=(json.loads(outcome[0]).get('report') or {}).get('rules_version')
            self.db.execute('INSERT INTO feedback (feedback_id,case_id,analysis_run_id,occurred_at,recorded_at,reported_outcome,verification_status,verification_method,supersedes_feedback_id,rules_version,match_degree,user_notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(feedback_id,case_id,analysis_run_id,occurred_at,recorded,reported_outcome,verification_status,verification_method,supersedes_feedback_id,rules_version,match_degree,user_notes))
            return {'feedback_id':feedback_id,'recorded_at':recorded,'verification_status':verification_status}
        return self._write(actor,'add_feedback',idempotency_key,payload,action)

    @staticmethod
    def _decode_context(row):
        value=dict(row);value['content']=json.loads(value.pop('content_json'));return value

    def export_case(self, actor, case_id):
        row=self._owned(actor,case_id)
        result=dict(row);result['original_input']=json.loads(result.pop('original_input_json'))
        result['revisions']=[]
        for r in self.db.execute('SELECT * FROM case_revisions WHERE case_id=? ORDER BY revision_seq',(case_id,)):
            r=dict(r);r['input']=json.loads(r.pop('input_json'));r['time_context']=json.loads(r.pop('time_context_json'));result['revisions'].append(r)
        result['context_events']=[self._decode_context(r) for r in self.db.execute('SELECT * FROM context_events WHERE case_id=? ORDER BY event_seq',(case_id,))]
        result['analysis_runs']=[]
        for run in self.db.execute('SELECT * FROM analysis_runs WHERE case_id=? ORDER BY analyzed_at,analysis_run_id',(case_id,)):
            run=dict(run);run['input_snapshot']=json.loads(run.pop('input_snapshot_json'))
            outcome=self.db.execute('SELECT * FROM analysis_outcomes WHERE analysis_run_id=?',(run['analysis_run_id'],)).fetchone()
            if outcome:
                outcome=dict(outcome);outcome['result']=json.loads(outcome.pop('result_json'))
            run['outcome']=outcome;run['status']=outcome['status'] if outcome else 'running'
            run['ai_events']=[]
            for event in self.db.execute('SELECT * FROM ai_events WHERE analysis_run_id=? ORDER BY recorded_at,event_id',(run['analysis_run_id'],)):
                event=dict(event);event['attempt']=json.loads(event.pop('event_json'));run['ai_events'].append(event)
            result['analysis_runs'].append(run)
        result['feedback']=[dict(r) for r in self.db.execute('SELECT * FROM feedback WHERE case_id=? ORDER BY recorded_at,feedback_id',(case_id,))]
        result['usage_policy']={'service_case_archive':True,'public_use':False,'training_use':False}
        return result

    def list_cases(self, actor):
        return [dict(r) for r in self.db.execute('SELECT case_id,session_id,recorded_at FROM cases WHERE owner_id=? ORDER BY recorded_at,case_id',(actor.owner_id,))]

    def export_intake_failures(self, actor):
        result=[]
        for row in self.db.execute('SELECT * FROM intake_failures WHERE owner_id=? ORDER BY recorded_at,failure_id',(actor.owner_id,)):
            row=dict(row);row['related_input']=json.loads(row.pop('related_input_json'));row['errors']=json.loads(row.pop('errors_json'));result.append(row)
        return result
