"""Inspect actual adapter requests using synthetic replies; no external API calls."""
import copy, json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from liuyao_app.providers import generate_json, TransportResponse
from liuyao_app.test_v5 import NewReportProvider, INPUT
from liuyao_app.pipeline import run_analysis
from liuyao_app.test_buzhai import TOPIC
from casting_input import normalize_casting_input
from case_store import CaseStore, Actor

example = {**INPUT, 'casting': {'method': 'meibu', 'results': ['1', '5', '4']}}
lines = normalize_casting_input(example)['lines']
tokens = {'young_yang': '322', 'young_yin': '323', 'old_yang': '333', 'old_yin': '222'}
base = {k: v for k, v in example.items() if k != 'casting'}
inputs = {
    'meibu': example,
    'taiji': {**base, 'casting': {'method': 'taiji', 'results': [tokens[x] for x in lines]}},
    'direct': {**base, 'lines': lines},
    'buzhai': {**example, 'buzhai': TOPIC},
}
forbidden_text = ['枚卜丸', '太极丸', '《周易古筮考》', '《周易六爻八卦》', '《六爻取用神实战纲要》', '课外补充', '个人感悟']
forbidden_keys = {'casting', 'casting_method', 'raw_casting', 'original_input', 'meibu', 'taiji'}
def keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys(v)

requests = []
charts = []
for case_name, data in inputs.items():
    provider = NewReportProvider()
    def call(provider_id, model, prompt, payload, **kwargs):
        synthetic = provider(provider_id, model, prompt, payload, **kwargs)
        stage = provider.calls[-1]['stage']
        def transport(url, headers, body, timeout):
            assert url == 'https://api.deepseek.com/chat/completions'
            assert 0 < timeout <= 90 if stage == 'report' else timeout == 600
            controls = {k: body.get(k) for k in ('model', 'thinking', 'reasoning_effort', 'max_tokens')}
            assert controls == {'model': 'deepseek-v4-pro', 'thinking': {'type': 'enabled'}, 'reasoning_effort': 'max', 'max_tokens': 131072}
            messages = body['messages']
            assert [x['role'] for x in messages] == ['system', 'user']
            system, user = [x['content'] for x in messages]
            sent = json.loads(user)
            assert not any(x in system + user for x in forbidden_text)
            assert not (set(keys(sent)) & forbidden_keys)
            assert ('本次用户明确启用卜宅专题' in system) == (case_name == 'buzhai')
            if stage == 'intent':
                assert '谋事应先认真考虑现实条件' in system
                assert '诊断前先编造整改方案' in system
                assert '简短问题可直接ready' not in system
            if stage != 'selection':
                assert sent['question'] == data['question']
            if stage in ('intent', 'selection'):
                assert any(x['text'] == data['question'] for x in sent['user_evidence'])
            if stage in ('selection', 'interpretation'):
                assert sent['rules'] and all(r['status'] == 'approved' and r['statement'] and r['applicability'] for r in sent['rules'])
            if stage == 'report':
                chart = sent['analysis_chart']
                assert chart['input_lines'] == lines and chart['moving_positions'] == [4]
                assert chart['main']['name'] == '火雷噬嗑' and chart['changed_structure']['name'] == '山雷颐'
                if case_name != 'buzhai':
                    charts.append(copy.deepcopy(chart))
            requests.append({'case': case_name, 'stage': stage, **controls, 'system_characters': len(system), 'input_characters': len(user), 'input_keys': list(sent), 'rule_count': len(sent.get('rules', []))})
            return TransportResponse(200, {}, json.dumps({'model': model, 'choices': [{'message': {'content': synthetic['raw_text'], 'reasoning_content': 'private-synthetic-reasoning'}, 'finish_reason': 'stop'}]}).encode())
        return generate_json(provider_id, model, prompt, payload, transport=transport, **kwargs)
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'offline-test-placeholder'}, clear=True):
        path = Path(directory) / 'cases.sqlite3'
        db = CaseStore(path)
        actor = Actor('test-owner', 'session')
        try:
            cid = db.create_case(actor, data, idempotency_key='new')['case_id']
            result = run_analysis(path, actor, cid, 'deepseek', 'deepseek-v4-pro', 1, provider_call=call)
            assert result['status'] == 'completed', result.get('error')
            exported = db.export_case(actor, cid)
            assert exported['original_input'] == normalize_casting_input(data)
            events = exported['analysis_runs'][0]['ai_events']
            assert len(events) == 4
            assert all(e['attempt']['model_run_metadata']['reasoning_effort'] == 'max' for e in events)
            assert 'private-synthetic-reasoning' not in json.dumps(exported)
        finally:
            db.close()
assert len(requests) == 16
assert charts[0] == charts[1] == charts[2]
report = {'status': 'passed', 'live_api_calls': 0, 'checks': ['三种起卦输入发送相同规范卦盘', '原始器具记录仅本地保留', '用户问题原文保留', 'system 无器具或书目介绍', '规则为提取的适用逻辑', '卜宅按需启用', '四阶段 Pro max', '案例保留实际请求审计'], 'requests': requests}
output = Path(os.environ.get('LIUYAO_TEST_OUTPUT', 'test-results')); output.mkdir(parents=True, exist_ok=True)
(output / 'request_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False))
