"""Loopback-only HTTP application. This is a personal local workspace, not a public server."""
import base64
import argparse
import ast
import datetime as dt
import hashlib
from functools import lru_cache
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

from .config import ROOT, load_env, data_directory, initialize_configuration, configuration_file
from .instance_lock import InstanceLock
from .runtime_identity import APP_ID, CASTING_METHODS, app_build_id
from case_store import Actor, CaseStore, AccessDenied, Conflict, content_digest
from .pipeline import calculate_chart
from .rulebook import (load_rules, read_workbook, export_workbook, save_rules,
                       RulesNotInstalled, LOCK as RULE_LOCK)
from .profile_store import list_profiles, get_profile, save_profile
from casting_input import normalize_casting_input


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def exact_fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ApiError(400, 'INVALID_FIELDS', '请求字段不完整或包含不支持的字段。')


def text_field(value, limit=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ApiError(400, 'INVALID_TEXT', f'请填写 1 至 {limit} 字的内容。')
    return value


def revision_field(value):
    if type(value) is not int or value < 1:
        raise ApiError(400, 'INVALID_REVISION', '请重新打开案例后再操作。')
    return value


@lru_cache(maxsize=1)
def diagnostic_schema_fields():
    """Only bundled output-schema field names may enter shared diagnostics."""
    names = set()
    def collect(value):
        if isinstance(value, dict):
            names.update(value.get('properties', {}))
            for child in value.values():collect(child)
        elif isinstance(value, list):
            for child in value:collect(child)
    try:
        pack = json.loads((ROOT / 'software_prep' / 'liuyao_ai_prompt_pack.yaml').read_text(encoding='utf-8'))
        for stage in pack['stages'].values():collect(stage['output_schema'])
    except (OSError, ValueError, KeyError, TypeError):
        # An unavailable schema must remove diagnostic detail, never cause a
        # fallback to unrestricted model-generated identifiers.
        return frozenset()
    return frozenset(names)


def diagnostic_error(value):
    """Retain error categories, never model/user supplied free text or values."""
    value = value if isinstance(value, dict) else {}
    code = value.get('code', '')
    code = code if isinstance(code, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', code) else 'VALIDATION_FAILED'
    message = value.get('message', '')
    message = message if isinstance(message, str) else ''
    # Prefixes and categories are fixed literals: dynamic IDs, quotes and model
    # output are deliberately not copied to a file the user may share.
    categories = ('wrong type', 'enum mismatch', 'missing', 'unexpected fields',
        'invalid array length', 'duplicate items', 'invalid string length',
        'blank string', 'pattern mismatch', 'duplicate JSON key', 'invalid JSON', 'invalid model JSON',
        'nonexistent refs', 'cross-run or cross-snapshot binding',
        'source identity and source role do not match',
        'functional relation/kinship mismatch', 'prompt digest mismatch',
        'ready selection needs a primary candidate and no blocking issue',
        'ready selection needs a non-null primary candidate ID',
        'candidate ID does not exist in candidates',
        'selected_primary_id must reference a primary candidate',
        'conclusion omitted a cited claim assumption',
        'conclusion omitted a cited claim limitation',
        'report must preserve the accepted conclusion verbatim',
        'report must preserve all accepted uncertainty records verbatim',
        'conclusion direction contradicts or exceeds cited primary claims',
        'selection/display definitions alone cannot support an interpretive hypothesis',
        'AI hypothesis needs applicable core rule, review flag and limitations')
    category = next((item for item in categories if item in message), None)
    result = {'code': code, 'message': category or '校验或调用未通过；详细原文仅保存在本地。'}
    known = diagnostic_schema_fields()

    def allowed_path(path):
        return (isinstance(path, str)
                and re.fullmatch(r'\$(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]{1,6}\]){0,20}', path)
                and known
                and all(name in known for name in re.findall(r'\.([A-Za-z_][A-Za-z0-9_]*)', path)))

    # Batch feedback supplies a separate path. Apply the same fixed-schema
    # allowlist as legacy message prefixes; never export arbitrary identifiers.
    explicit_path = value.get('path')
    if allowed_path(explicit_path):
        result['field_path'] = explicit_path
    match = re.match(r'^(\$(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]{1,6}\]){0,20}):\s*(.*)$', message)
    if match:
        path, suffix = match.groups()
        if allowed_path(path):
            result.setdefault('field_path', path)
            if result['field_path'] == path and suffix.startswith('missing ') and len(suffix) <= 4096:
                try:missing = ast.literal_eval(suffix[len('missing '):])
                except (ValueError, SyntaxError, RecursionError):missing = None
                if isinstance(missing, list):
                    fields = sorted({field for field in missing if isinstance(field, str) and field in known})
                    if fields:result['missing_fields'] = fields
    return result


def case_diagnostics(case, build_id):
    """An owner-authorized, minimal projection, separate from a full case export."""
    result = {'format': 'liuyao_case_diagnostics', 'app_build_id': build_id,
              'case_id': case['case_id'], 'analysis_runs': []}
    for run in case.get('analysis_runs', []):
        record = {'analysis_run_id': run['analysis_run_id'], 'status': run['status'], 'attempts': []}
        for event in run.get('ai_events', []):
            attempt = event.get('attempt', {})
            metadata = attempt.get('model_run_metadata', {})
            stage = attempt.get('stage')
            number = metadata.get('attempt_number')
            model = metadata.get('model')
            provider = metadata.get('provider')
            finish = metadata.get('finish_reason')
            # These metadata values come from server configuration/provider
            # control fields, not from the model's body or input snapshot.
            record['attempts'].append({
                'stage': stage if stage in ('intent', 'selection', 'use_spirit', 'interpretation', 'report') else 'unknown',
                'attempt_number': number if type(number) is int and 1 <= number <= 10 else None,
                'parse_status': attempt.get('parse_status') if attempt.get('parse_status') in ('parsed', 'invalid_json', 'provider_error', 'not_parsed') else 'unknown',
                'validation_errors': [diagnostic_error(error) for error in attempt.get('validation_errors', [])],
                'model_metadata': {
                    'provider': provider if provider in ('deepseek', 'doubao', 'demo') else 'unknown',
                    'model': model if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}', model) else None,
                    'finish_reason': finish if finish in ('stop', 'length', 'max_tokens', 'content_filter', 'tool_calls', 'function_call', 'end_turn', 'error') else None,
                }})
        result['analysis_runs'].append(record)
    return result


def case_ai_attempts(case, run_id=None):
    """Local, owner-only raw replies; never include prompts or provider secrets."""
    def error_with_path(error):
        projected = {key: error[key] for key in ('code', 'message') if isinstance(error.get(key), str)}
        safe_path = diagnostic_error(error).get('field_path')
        if safe_path is not None:
            projected['path'] = safe_path
        return projected

    runs = case.get('analysis_runs', [])
    if run_id is not None:
        runs = [run for run in runs if run.get('analysis_run_id') == run_id]
        if not runs:
            raise ApiError(404, 'RUN_NOT_FOUND', '没有找到这次分析记录。')
    result = {'case_id': case['case_id'], 'analysis_runs': []}
    for run in runs:
        record = {'analysis_run_id': run['analysis_run_id'], 'attempts': []}
        for event in run.get('ai_events', []):
            attempt = event.get('attempt', {})
            metadata = attempt.get('model_run_metadata', {})
            errors = attempt.get('validation_errors', [])
            record['attempts'].append({
                'stage': attempt.get('stage'),
                'attempt_number': metadata.get('attempt_number'),
                'raw_output': attempt.get('raw_output') if isinstance(attempt.get('raw_output'), str) else '',
                'validation_errors': [
                    error_with_path(error)
                    for error in errors if isinstance(error, dict)],
                'adopted': attempt.get('adopted_output') is not None and not errors,
                'normalization_changes': [change for change in metadata.get('normalization_changes', []) if isinstance(change, str)],
                'http_status': metadata.get('http_status') if type(metadata.get('http_status')) is int and 100 <= metadata['http_status'] <= 599 else None,
                'elapsed_ms': metadata.get('elapsed_ms') if type(metadata.get('elapsed_ms')) is int and metadata['elapsed_ms'] >= 0 else None,
            })
        result['analysis_runs'].append(record)
    return result


class Application:
    def __init__(self, directory, pipeline=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.instance_lock = InstanceLock(self.directory / 'app.lock')
        self.rules_directory = self.directory / 'knowledge_base'
        self.db_path = self.directory / 'cases.sqlite3'
        self.jobs_path = self.directory / 'jobs.sqlite3'
        self.instance_id = uuid.uuid4().hex
        self.build_id = app_build_id()
        self.pipeline = pipeline
        self.sessions = {}
        self.stopping = threading.Event()
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='liuyao-analysis')
        store = self.store()
        store.close()
        with self.jobs_db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, case_id TEXT NOT NULL, idem_key TEXT NOT NULL, request_digest TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(owner_id,idem_key))')
        self.recover()

    def store(self):
        return CaseStore(self.db_path)

    def jobs_db(self):
        db = sqlite3.connect(self.jobs_path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def recover(self):
        # An interrupted invocation is recorded as failed, never replayed with an API charge.
        checkpoints = {}
        with self.jobs_db() as db:
            for row in db.execute('SELECT * FROM jobs'):
                state = json.loads(row['state'])
                if state['status'] in ('queued', 'running'):
                    if state.get('_checkpoint'):
                        checkpoints[state.get('analysis_run_id')] = (row, state)
                        continue
                    state.update(status='failed', stage='interrupted', error={'code':'INTERRUPTED', 'message':'上次分析被中断，已保存输入，可重新分析。'})
                    db.execute('UPDATE jobs SET state=?,updated_at=? WHERE job_id=?', (json.dumps(state, ensure_ascii=False), stamp(), row['job_id']))
        store = self.store()
        try:
            rows = store.db.execute('SELECT r.analysis_run_id,r.case_id,c.owner_id,c.session_id FROM analysis_runs r JOIN cases c USING(case_id) LEFT JOIN analysis_outcomes o USING(analysis_run_id) WHERE o.analysis_run_id IS NULL').fetchall()
            for row in rows:
                saved = checkpoints.pop(row['analysis_run_id'], None)
                actor = Actor(row['owner_id'], row['session_id'])
                if saved and saved[0]['owner_id'] == row['owner_id'] and saved[0]['case_id'] == row['case_id']:
                    job_row, state = saved
                    result = state['_checkpoint']
                    if result.get('analysis_run_id') == row['analysis_run_id'] and result.get('user_report'):
                        result.update(status='completed', report_status={'mode':'fallback','code':'INTERRUPTED','message':'报告整理被中断，已保留此前解卦结论和专业依据。'})
                        result['audit_report']['warnings'].append({'stage':'report', **result['report_status']})
                        store.finish_analysis(actor, row['case_id'], row['analysis_run_id'], status='completed',
                            idempotency_key='recover-'+row['analysis_run_id'], chart_snapshot=result['chart'],
                            report=result, validation={'structural_contracts':False,'validated_stages':list(result['stage_outputs']), 'recovered_interpretation':True},
                            unresolved=result.get('unresolved', []))
                        self.update_job(job_row['job_id'], status='completed', stage='finished', phase='finished', result=result, error=None, _checkpoint=None)
                        continue
                store.finish_analysis(actor, row['case_id'], row['analysis_run_id'], status='failed', idempotency_key='recover-'+row['analysis_run_id'], error={'code':'INTERRUPTED','message':'本地服务中断，原输入和已经产生的分析记录保留。'})
                if saved:self.update_job(saved[0]['job_id'], status='failed', stage='interrupted', _checkpoint=None, error={'code':'INTERRUPTED','message':'本地服务中断，已保存分析记录。'})
            for run_id, (job_row, state) in checkpoints.items():
                case = store.export_case(Actor(job_row['owner_id'], 'recovery'), job_row['case_id'])
                run = next((r for r in case['analysis_runs'] if r['analysis_run_id'] == run_id), None)
                result = run['outcome']['result'].get('report') if run and run.get('outcome') else None
                self.update_job(job_row['job_id'], status=run['status'] if result else 'failed', stage='finished' if result else 'interrupted',
                    result=result, _checkpoint=None, error=result.get('error') if result else {'code':'INTERRUPTED','message':'本地服务中断，已保存分析记录。'})
        finally:
            store.close()

    def session(self, token=None):
        with self.lock:
            if token in self.sessions:
                return token, self.sessions[token]
            token = secrets.token_urlsafe(32)
            actor = Actor('local-user', 'session_'+uuid.uuid4().hex)
            self.sessions[token] = actor
            return token, actor

    def actor(self, token):
        with self.lock:
            actor = self.sessions.get(token)
        if actor is None:
            raise ApiError(401, 'SESSION_REQUIRED', '请刷新页面以恢复本地会话。')
        return actor

    def config(self):
        from .providers import provider_catalog
        providers = provider_catalog()
        providers = [p for p in providers if p['id'] in ('deepseek','doubao')]
        providers.append({'id':'demo','name':'离线演示','models':['local-demo'],'configured':True,'default_model':'local-demo'})
        return {'providers':providers,'default_provider':'deepseek','storage_mode':'local',
                'storage_paths':{'data_directory':str(self.directory.resolve()),
                                 'configuration_file':str(configuration_file().resolve())},
                'capabilities':{'chart':True,'ai_requires_key':True,'calendar':True,'conditional_ai_interpretation':True,'complete_judgment_engine':False,'local_only':True}}

    def active(self, actor, case_id=None):
        with self.jobs_db() as db:
            rows = db.execute('SELECT case_id,state FROM jobs WHERE owner_id=?', (actor.owner_id,)).fetchall()
        return [json.loads(r['state']) for r in rows if (case_id is None or r['case_id']==case_id) and json.loads(r['state'])['status'] in ('queued','running')]

    def ensure_idle(self, actor, case_id):
        if self.active(actor, case_id):
            raise ApiError(409, 'CASE_BUSY', '本案例正在分析，请等待完成后再更正或补充。')

    def enqueue(self, actor, case_id, body, idem_key):
        exact_fields(body, ('provider','model','expected_revision_seq'), ('provider','model','expected_revision_seq'))
        revision_field(body['expected_revision_seq'])
        text_field(body['provider'], 40); text_field(body['model'], 200)
        fingerprint = content_digest({'case_id':case_id, **body})
        with self.lock:
            with self.jobs_db() as db:
                old = db.execute('SELECT * FROM jobs WHERE owner_id=? AND idem_key=?', (actor.owner_id, idem_key)).fetchone()
                if old:
                    if old['request_digest'] != fingerprint:
                        raise Conflict('request key already used')
                    return {'job_id':old['job_id']}
                self.ensure_idle(actor, case_id)
                if len(self.active(actor)) >= 2:
                    raise ApiError(429, 'TOO_MANY_ANALYSES', '已有两项分析正在进行，请稍后再试。')
                store = self.store()
                try:
                    case = store.export_case(actor, case_id)
                    if case['revisions'][-1]['revision_seq'] != body['expected_revision_seq']:
                        raise Conflict('case revision changed')
                finally:
                    store.close()
                provider = next((p for p in self.config()['providers'] if p['id']==body['provider']), None)
                if provider is None or body['model'] not in provider['models']:
                    raise ApiError(400, 'UNKNOWN_MODEL', '请选择后台已配置的厂商和模型。')
                if not provider['configured']:
                    raise ApiError(400, 'PROVIDER_NOT_CONFIGURED', '该厂商尚未配置 API 密钥，案例和排盘已经保留。')
                job_id = 'job_'+uuid.uuid4().hex
                state = {'job_id':job_id, 'case_id':case_id,'status':'queued','stage':'queued','analysis_run_id':None,'result':None,'error':None,
                         'provider':body['provider'],'model':body['model'],'completed_stages':[],'reply_count':0,'attempt':0,'phase':'queued'}
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)', (job_id, actor.owner_id, case_id, idem_key, fingerprint, json.dumps(body), json.dumps(state), stamp(), stamp()))
            self.pool.submit(self._work, job_id, actor, case_id, body)
        return {'job_id':job_id}

    def update_job(self, job_id, **changes):
        with self.lock, self.jobs_db() as db:
            row=db.execute('SELECT state FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            state=json.loads(row['state']);now=stamp()
            if changes.get('stage') in ('intent','selection','interpretation','report'):
                if state.get('stage') != changes['stage']:
                    state['stage_started_at']=now
                state['last_stage']=changes['stage']
            if changes.get('phase') == 'waiting':
                state['request_started_at']=now
            completed=changes.pop('completed_stage',None)
            if completed in ('intent','selection','interpretation','report'):
                state['completed_stages']=list(dict.fromkeys([*state.get('completed_stages',[]),completed]))
            if changes.pop('reply_saved',False):
                state['reply_count']=state.get('reply_count',0)+1
            state.update(changes)
            db.execute('UPDATE jobs SET state=?,updated_at=? WHERE job_id=?',(json.dumps(state,ensure_ascii=False),now,job_id))

    def get_job(self, actor, job_id):
        with self.jobs_db() as db:
            row=db.execute('SELECT state,created_at,updated_at FROM jobs WHERE job_id=? AND owner_id=?',(job_id,actor.owner_id)).fetchone()
        if row is None:
            raise AccessDenied('job unavailable')
        state=json.loads(row['state']);now=dt.datetime.now(dt.timezone.utc)
        checkpoint = state.pop('_checkpoint', None)
        if checkpoint and state['status'] in ('queued','running'):state['preview_report'] = checkpoint.get('user_report')
        def elapsed(start,end):
            try:return max(0,int((dt.datetime.fromisoformat(end)-dt.datetime.fromisoformat(start)).total_seconds()))
            except (TypeError,ValueError):return 0
        state.update(created_at=row['created_at'],updated_at=row['updated_at'],server_time=now.isoformat())
        end=now.isoformat() if state['status'] in ('queued','running') else row['updated_at']
        state['elapsed_seconds']=elapsed(row['created_at'],end)
        state['request_elapsed_seconds']=elapsed(state.get('request_started_at',row['updated_at']),end)
        return state

    def _work(self, job_id, actor, case_id, body):
        try:
            from .pipeline import run_analysis
            self.update_job(job_id,status='running',stage='starting')
            def progress(value):
                if isinstance(value,str): value={'stage':value}
                safe={k:v for k,v in value.items() if k in ('stage','analysis_run_id')}
                if type(value.get('attempt')) is int and 1 <= value['attempt'] <= 2:safe['attempt']=value['attempt']
                if value.get('phase') in ('waiting','validating','stage_done','repairing','error'):safe['phase']=value['phase']
                if value.get('completed_stage') in ('intent','selection','interpretation','report'):safe['completed_stage']=value['completed_stage']
                if value.get('reply_saved') is True:safe['reply_saved']=True
                if isinstance(value.get('checkpoint'), dict):
                    checkpoint = value['checkpoint']
                    if checkpoint.get('analysis_run_id') == value.get('analysis_run_id') and isinstance(checkpoint.get('user_report'), dict):
                        safe['_checkpoint'] = {k:v for k,v in checkpoint.items() if k in (
                            'analysis_run_id','status','chart','user_report','display_report','is_demo','unresolved','clarifying_questions',
                            'rules_version','parameter_version','engine_build','ai_model','rules_snapshot','audit_report','stage_outputs','selection_note_reviews')}
                if type(value.get('report_timeout_seconds')) is int:safe['report_timeout_seconds']=value['report_timeout_seconds']
                self.update_job(job_id,**safe)
            extra = {}
            if self.pipeline is None:
                from .providers import generate_json, ProviderError
                def provider_call(*args, **kwargs):
                    if self.stopping.is_set():
                        raise ProviderError('service_stopping','软件正在关闭，本次分析已停止，记录已经保留。')
                    return generate_json(*args, **kwargs)
                extra['provider_call'] = provider_call
            result=(self.pipeline or run_analysis)(self.db_path, actor, case_id, body['provider'], body['model'], body['expected_revision_seq'], progress=progress, **extra)
            self.update_job(job_id,status=result['status'],stage='finished',phase='finished',result=result,analysis_run_id=result.get('analysis_run_id'),error=result.get('error'),_checkpoint=None)
        except Exception:
            # Pipeline retains detailed safe failures. Never send tracebacks, environment or provider keys to clients.
            current = self.get_job(actor, job_id)
            if current.get('analysis_run_id'):
                store = self.store()
                try:
                    exists = store.db.execute('SELECT 1 FROM analysis_outcomes WHERE analysis_run_id=?', (current['analysis_run_id'],)).fetchone()
                    if not exists:
                        store.finish_analysis(actor, case_id, current['analysis_run_id'], status='failed', idempotency_key='job-failed-'+job_id, error={'code':'ANALYSIS_FAILED','message':'分析意外中断，输入与已有尝试保留。'})
                finally:
                    store.close()
            self.update_job(job_id,status='failed',stage='failed',error={'code':'ANALYSIS_FAILED','message':'分析未完成，已保留案例，请打开记录后重试。'})

    def case_detail(self, actor, case_id):
        store=self.store()
        try:
            case=store.export_case(actor,case_id)
        finally:store.close()
        current=case['revisions'][-1]
        runs=case['analysis_runs']
        latest=runs[-1] if runs else None
        active=self.active(actor,case_id)
        user_types={'background','clarification_answer','user_correction'}
        current_context=[e['event_id'] for e in case['context_events'] if e['event_type'] in user_types]
        analyzed_context=[e['event_id'] for e in latest['input_snapshot']['context_events'] if e['event_type'] in user_types] if latest else []
        return {'case':case,'chart':calculate_chart(current['input'],load_rules(self.rules_directory)),
                'result':latest['outcome']['result'].get('report') if latest and latest['outcome'] else None,
                'report_is_current':bool(latest and latest['outcome'] and latest['outcome']['result'].get('report') and latest['revision_seq']==current['revision_seq'] and analyzed_context==current_context),
                'active_job_id':active[0]['job_id'] if active else None}

    def list_cases(self, actor):
        store=self.store()
        try:
            rows=store.db.execute('''SELECT c.case_id,c.recorded_at,r.revision_seq,r.input_json,
                (SELECT COALESCE(o.status,'running') FROM analysis_runs a LEFT JOIN analysis_outcomes o USING(analysis_run_id) WHERE a.case_id=c.case_id ORDER BY a.analyzed_at DESC LIMIT 1) status
                FROM cases c JOIN case_revisions r ON r.case_id=c.case_id
                WHERE c.owner_id=? AND r.revision_seq=(SELECT MAX(revision_seq) FROM case_revisions WHERE case_id=c.case_id)
                ORDER BY c.recorded_at DESC''',(actor.owner_id,)).fetchall()
            return [{'case_id':r['case_id'],'question':json.loads(r['input_json'])['question'],'recorded_at':r['recorded_at'],'revision_seq':r['revision_seq'],'status':r['status'] or 'saved'} for r in rows]
        finally:store.close()

    def close(self):
        self.stopping.set()
        self.pool.shutdown(wait=True)
        self.instance_lock.close()


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, address, app):
        if address[0] not in ('127.0.0.1','localhost'):
            raise ValueError('This local app must bind to loopback.')
        super().__init__(address, Handler)
        self.app=app


class Handler(BaseHTTPRequestHandler):
    server_version='LiuyaoLocal'
    def log_message(self, fmt, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def _headers(self, status, kind, length, extra=None):
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(length))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers()

    def send_json(self, value, status=200, extra=None):
        raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        self._headers(status,'application/json; charset=utf-8',len(raw),extra)
        self.wfile.write(raw)

    def guard(self, mutation=False):
        port=self.server.server_port
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:
            raise ApiError(403,'INVALID_HOST','仅允许本机访问。')
        origin=self.headers.get('Origin')
        if origin is not None and origin not in {'http://'+h for h in allowed}:
            raise ApiError(403,'INVALID_ORIGIN','请求来源不受支持。')
        if self.headers.get('Sec-Fetch-Site')=='cross-site':
            raise ApiError(403,'CROSS_SITE','不接受跨站请求。')
        if mutation and self.headers.get('X-App-Request')!='1':
            raise ApiError(403,'REQUEST_HEADER_REQUIRED','请从软件页面提交操作。')

    def actor(self):
        jar=cookies.SimpleCookie()
        try:jar.load(self.headers.get('Cookie',''))
        except cookies.CookieError:pass
        token=jar['liuyao_session'].value if 'liuyao_session' in jar else None
        return self.server.app.actor(token)

    def body(self):
        if self.headers.get('Transfer-Encoding'):
            raise ApiError(400,'INVALID_BODY','不支持此请求格式。')
        if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
            raise ApiError(415,'JSON_REQUIRED','请求须为 JSON。')
        try:size=int(self.headers.get('Content-Length','0'))
        except ValueError:raise ApiError(400,'INVALID_LENGTH','请求长度无效。')
        limit = 7_000_000 if urlsplit(self.path).path=='/api/rules/import' else 65536
        if size<1 or size>limit:
            raise ApiError(413,'BODY_LIMIT','请求内容过大或为空。')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('duplicate key')
                result[key]=value
            return result
        def invalid(value):raise ValueError('non-JSON number')
        try:return json.loads(self.rfile.read(size).decode('utf-8'),object_pairs_hook=unique,parse_constant=invalid)
        except (ValueError,UnicodeDecodeError,RecursionError):raise ApiError(400,'INVALID_JSON','请求内容不是有效的 JSON。')

    def dispatch(self, mutation=False):
        try:
            self.guard(mutation)
            path=urlsplit(self.path).path
            if not mutation and path in ('/','/index.html','/app.js','/styles.css','/static/app.js','/static/styles.css','/chart-display.js','/static/chart-display.js','/v5-features.js','/static/v5-features.js','/static/report-views.js','/static/buzhai.js','/static/mobile.js','/static/mobile.css','/static/compat.js','/static/phone-chart.js','/static/analysis-status.js','/static/guidance.js','/favicon.ico'):
                if path=='/favicon.ico':
                    self._headers(204,'image/x-icon',0);return
                name='index.html' if path in ('/','/index.html') else path.rsplit('/',1)[-1]
                target=Path(__file__).parent/'static'/name
                raw=target.read_bytes()
                extra={}
                if name=='index.html':
                    token,_=self.server.app.session()
                    extra['Set-Cookie']=f'liuyao_session={token}; HttpOnly; SameSite=Strict; Path=/'
                self._headers(200,(mimetypes.guess_type(name)[0] or 'application/octet-stream')+'; charset=utf-8',len(raw),extra)
                self.wfile.write(raw);return
            if not mutation and path == '/api/runtime':
                app=self.server.app
                self.send_json({'app_id':APP_ID, 'instance_id':app.instance_id, 'build_id':app.build_id, 'casting_methods':CASTING_METHODS})
                return
            actor=self.actor()
            app=self.server.app
            parts=path.strip('/').split('/')
            if not mutation:
                if path=='/api/config':self.send_json(app.config());return
                if path=='/api/cases':self.send_json({'cases':app.list_cases(actor)});return
                if path=='/api/profiles':
                    store=app.store()
                    try: profiles=list_profiles(store,actor)
                    finally: store.close()
                    self.send_json({'profiles':profiles});return
                if path=='/api/rules/guide':
                    from .rule_explanations import rule_guide
                    self.send_json(rule_guide(load_rules(app.rules_directory)));return
                if path=='/api/usage-guide':
                    from .learning_guide import usage_guide
                    self.send_json(usage_guide());return
                if path in ('/api/principles', '/api/principles/export'):
                    from .buzhai import principle_guide
                    guide = principle_guide()
                    if path.endswith('/export'):
                        raw = json.dumps(guide, ensure_ascii=False, indent=2).encode('utf-8')
                        self._headers(200, 'application/json; charset=utf-8', len(raw), {'Content-Disposition':'attachment; filename="buzhai-principles.json"'})
                        self.wfile.write(raw)
                    else:
                        self.send_json(guide)
                    return
                if path=='/api/rules':
                    try:book=load_rules(app.rules_directory)
                    except RulesNotInstalled:
                        self.send_json({'installed':False,'status':'not_installed','rule_count':0});return
                    self.send_json({'installed':True,'version':book.version,'digest':book.digest,'rule_count':len(book.rows),'status':'experimental'});return
                if path=='/api/rules/export':
                    raw=export_workbook(load_rules(app.rules_directory))
                    self._headers(200,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',len(raw),{'Content-Disposition':'attachment; filename="rules.xlsx"'})
                    self.wfile.write(raw);return
                if len(parts)==3 and parts[:2]==['api','jobs']:
                    self.send_json(app.get_job(actor,parts[2]));return
                if len(parts) in (3,4) and parts[:2]==['api','cases']:
                    if len(parts)==4 and parts[3]=='ai-attempts':
                        query=parse_qs(urlsplit(self.path).query,keep_blank_values=True)
                        if set(query)-{'run_id'} or ('run_id' in query and (len(query['run_id'])!=1 or not query['run_id'][0])):
                            raise ApiError(400,'INVALID_QUERY','分析记录参数无效。')
                        store=app.store()
                        try:attempts=case_ai_attempts(store.export_case(actor,parts[2]),query.get('run_id',[None])[0])
                        finally:store.close()
                        self.send_json(attempts);return
                    if len(parts)==4 and parts[3]=='diagnostics':
                        store=app.store()
                        try:diagnostics=case_diagnostics(store.export_case(actor,parts[2]),app.build_id)
                        finally:store.close()
                        self.send_json(diagnostics,extra={'Content-Disposition':'attachment; filename="case_diagnostics.json"'});return
                    result=app.case_detail(actor,parts[2])
                    if len(parts)==3:self.send_json(result);return
                    if parts[3]=='export':
                        self.send_json(result['case'],extra={'Content-Disposition':f'attachment; filename="{parts[2]}.json"'});return
            else:
                body=self.body()
                idem=self.headers.get('X-Idempotency-Key')
                text_field(idem,160)
                if path=='/api/profiles/bazi':
                    exact_fields(body,('birth_date','birth_time'))
                    from .birth_calendar import calculate_birth_chart
                    result=calculate_birth_chart(body.get('birth_date',''),body.get('birth_time',''))
                    self.send_json(result,422 if result['status']=='error' else 200);return
                if path=='/api/profiles':
                    exact_fields(body,('profile','person_id','expected_version','is_self'),('profile',))
                    store=app.store()
                    try: result=save_profile(store,actor,body['profile'],person_id=body.get('person_id'),expected_version=body.get('expected_version'),is_self=body.get('is_self',False),idempotency_key=idem)
                    finally: store.close()
                    self.send_json(result,201);return
                if path=='/api/rules/preview':
                    exact_fields(body,('rule_id','value','enabled','expected_version','input'),('rule_id','value','enabled','expected_version'))
                    from .rule_explanations import preview_rule
                    book=load_rules(app.rules_directory)
                    if book.version!=body['expected_version']:raise Conflict('规则已更新，请重新打开规则库')
                    if body.get('input'):
                        from validate_input import validate_input
                        if not validate_input(body['input'])['valid']:raise ValueError('试算输入不完整，请先保存一个有效卦盘')
                    self.send_json(preview_rule(book,body['rule_id'],body['value'],body['enabled'],body.get('input')));return
                if path=='/api/rules/import':
                    exact_fields(body,('xlsx_base64','expected_version'),('xlsx_base64','expected_version'))
                    with RULE_LOCK:
                        try:current=load_rules(app.rules_directory)
                        except RulesNotInstalled:current=None
                        if current is not None and current.version!=body['expected_version']:
                            raise Conflict('规则已更新，请重新导出')
                        if current is None and body['expected_version'] not in (None,''):
                            raise Conflict('规则安装状态已变化，请重新打开规则页')
                        try:
                            rows=read_workbook(base64.b64decode(body['xlsx_base64'],validate=True))
                            book=save_rules(app.rules_directory,rows)
                        except ValueError as exc:raise ApiError(422,'INVALID_RULEBOOK',str(exc))
                    self.send_json({'version':book.version,'rule_count':len(book.rows)});return
                if path=='/api/cases':
                    exact_fields(body,('input',),('input',))
                    # Check before writing so attempts made before first rule
                    # installation cannot leave duplicate case records.
                    book=load_rules(app.rules_directory)
                    store=app.store()
                    try:result=store.create_case(actor,body['input'],idempotency_key=idem)
                    finally:store.close()
                    if not result['accepted']:
                        self.send_json({'error':{'code':'INVALID_INPUT','message':'请检查问题及所选起卦方式的记录。','details':result['errors']},'failure_id':result['failure_id']},422);return
                    result['chart']=calculate_chart(normalize_casting_input(body['input']),book)
                    self.send_json(result,201);return
                if len(parts)==4 and parts[:2]==['api','cases']:
                    case_id,action=parts[2:]
                    if action=='analyze':
                        load_rules(app.rules_directory)
                        self.send_json(app.enqueue(actor,case_id,body,idem),202);return
                    # Serialize edit/context with analyze enqueue to avoid a snapshot race.
                    with app.lock:
                        if action in ('context','revisions'):app.ensure_idle(actor,case_id)
                        store=app.store()
                        try:
                            if action=='context':
                                exact_fields(body,('text',),('text',))
                                result=store.append_context_event(actor,case_id,event_type='background',content={'text':text_field(body['text'])},idempotency_key=idem)
                            elif action=='revisions':
                                exact_fields(body,('input','reason','expected_revision_seq'),('input','reason','expected_revision_seq'))
                                result=store.revise_case(actor,case_id,body['input'],reason=text_field(body['reason'],1000),expected_revision_seq=revision_field(body['expected_revision_seq']),idempotency_key=idem)
                            elif action=='feedback':
                                exact_fields(body,('text','analysis_run_id','occurred_at','match_degree','user_notes'),('text',))
                                if body.get('analysis_run_id') is not None:text_field(body['analysis_run_id'],160)
                                result=store.add_feedback(actor,case_id,reported_outcome=text_field(body['text']),analysis_run_id=body.get('analysis_run_id'),occurred_at=body.get('occurred_at'),match_degree=body.get('match_degree'),user_notes=body.get('user_notes'),idempotency_key=idem)
                            else:raise ApiError(404,'NOT_FOUND','没有此操作。')
                        finally:store.close()
                    self.send_json(result,201);return
            raise ApiError(404,'NOT_FOUND','找不到此记录或页面。')
        except ApiError as e:self.send_json({'error':{'code':e.code,'message':e.message}},e.status)
        except AccessDenied:self.send_json({'error':{'code':'NOT_FOUND','message':'找不到此记录。'}},404)
        except Conflict:self.send_json({'error':{'code':'CONFLICT','message':'记录已变化或操作重复，请刷新后重试。'}},409)
        except RulesNotInstalled as e:self.send_json({'error':{'code':'RULES_NOT_INSTALLED','message':str(e)}},409)
        except (ValueError,TypeError,KeyError):self.send_json({'error':{'code':'INVALID_REQUEST','message':'请求内容无效，请检查后重试。'}},400)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception:self.send_json({'error':{'code':'INTERNAL_ERROR','message':'本地服务暂时无法完成操作，已保存的案例不会丢失。'}},500)

    def do_GET(self):self.dispatch()
    def do_POST(self):self.dispatch(True)
    def do_OPTIONS(self):self.send_json({'error':{'code':'NOT_ALLOWED','message':'不接受跨站请求。'}},405)


def main():
    config_path = initialize_configuration()
    load_env(config_path)
    parser=argparse.ArgumentParser(description='六爻占问本地软件')
    parser.add_argument('--port',type=int,default=8877)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--open',action='store_true',help='启动后打开本机浏览器')
    args=parser.parse_args()
    app=Application(args.data_dir or data_directory())
    server=Server(('127.0.0.1',args.port),app)
    print(f'六爻占问已启动：http://127.0.0.1:{server.server_port}',flush=True)
    print('仅供本机浏览器使用。按 Ctrl+C 停止。API 密钥只从后台环境读取。',flush=True)
    print(f'模型配置：{config_path}', flush=True)
    print(f'案例数据：{app.directory}', flush=True)
    if args.open:
        import webbrowser
        threading.Timer(0.5, lambda:webbrowser.open(f'http://127.0.0.1:{server.server_port}')).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        app.close()

if __name__=='__main__':main()
