"""Offline validation for the specific AI pack; not a general JSON Schema engine.
The caller must supply a server-owned projection, never trust a client-built facts array.
Natural-language entailment still needs model/human evaluation.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

PACK_PATH = Path(__file__).with_name('liuyao_ai_prompt_pack.yaml')
class ContractError(ValueError):
    pass

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError('duplicate JSON key: ' + key)
        result[key] = value
    return result

def parse_raw(raw: str) -> Any:
    if not isinstance(raw, str) or len(raw) > 500000:
        raise ContractError('raw output must be text of at most 500000 characters')
    try:
        parsed = json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ContractError('non-finite JSON number: ' + value)))
        def finite(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ContractError('non-finite JSON number')
            if isinstance(value, dict):
                for child in value.values(): finite(child)
            elif isinstance(value, list):
                for child in value: finite(child)
        finite(parsed)
        return parsed
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ContractError('invalid JSON') from exc

def load_pack(path: Path = PACK_PATH):
    return parse_raw(path.read_text(encoding='utf-8'))

def prompt_digest(pack, stage):
    item = pack['stages'][stage]
    return hashlib.sha256(canonical({'system_prompt': pack['system_prompt'], 'prompt': item['prompt'],
        'input_schema': item['input_schema'], 'output_schema': item['output_schema']}).encode()).hexdigest()

def _type(value, name):
    return {'object': isinstance(value, dict), 'array': isinstance(value, list),
            'string': isinstance(value, str), 'number': isinstance(value, (float, int)) and not isinstance(value, bool),
            'boolean': isinstance(value, bool), 'null': value is None}.get(name, False)

def check_schema(value, schema, root=None, path='$'):
    """Supports only the schema keywords used by this package, failing on unknown ones."""
    root = schema if root is None else root
    known = {'$schema', '$defs', '$ref', 'type', 'properties', 'required', 'additionalProperties',
             'items', 'minItems', 'maxItems', 'uniqueItems', 'minLength', 'maxLength', 'enum', 'pattern'}
    unsupported = set(schema) - known
    if unsupported:
        raise ContractError(path + ': unsupported schema keywords ' + str(sorted(unsupported)))
    if '$ref' in schema:
        ref = schema['$ref']
        if not ref.startswith('#/$defs/'):
            raise ContractError(path + ': external schema ref forbidden')
        return check_schema(value, root['$defs'][ref.split('/')[-1]], root, path)
    types = schema.get('type')
    if types and not any(_type(value, t) for t in ([types] if isinstance(types, str) else types)):
        raise ContractError(path + ': wrong type')
    if 'enum' in schema and value not in schema['enum']:
        raise ContractError(path + ': enum mismatch')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        missing = set(schema.get('required', [])) - set(value)
        if missing:
            raise ContractError(path + ': missing ' + str(sorted(missing)))
        if schema.get('additionalProperties') is False and set(value) - set(props):
            raise ContractError(path + ': unexpected fields ' + str(sorted(set(value) - set(props))))
        for key in value:
            if key in props:
                check_schema(value[key], props[key], root, path + '.' + key)
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            raise ContractError(path + ': invalid array length')
        if schema.get('uniqueItems') and len({canonical(v) for v in value}) != len(value):
            raise ContractError(path + ': duplicate items')
        for index, item in enumerate(value):
            check_schema(item, schema.get('items', {}), root, path + '[' + str(index) + ']')
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', float('inf')):
            raise ContractError(path + ': invalid string length')
        if schema.get('minLength', 0) and not value.strip():
            raise ContractError(path + ': blank string')
        if 'pattern' in schema and re.search(schema['pattern'], value) is None:
            raise ContractError(path + ': pattern mismatch')

def _unique(items, key):
    table = {}
    for item in items:
        if item[key] in table:
            raise ContractError('duplicate identifier: ' + item[key])
        table[item[key]] = item
    return table

def _refs(refs, table, label):
    absent = set(refs) - set(table)
    if absent:
        raise ContractError(label + ': nonexistent refs ' + str(sorted(absent)))

def _quote_check(quotes, evidence):
    for quote in quotes:
        source = evidence.get(quote['evidence_id'])
        if source is None or quote['quote'] not in source['text']:
            raise ContractError('user evidence quotation not found')

SOURCE_ROLES = {'SRC-BSZS':'core', 'SRC-BSZS-SUPP':'core_supplement', 'SRC-BUZHAI':'core_supplement', 'SRC-TAIBU':'core_supplement', 'SRC-GSK':'supplementary',
                'SRC-ZYLYBG':'personal_reflection', 'SRC-OUTLINE':'personal_reflection'}

def _source_roles(rules):
    for rule in rules.values():
        if SOURCE_ROLES.get(rule['source_id']) != rule['source_role']:
            raise ContractError('source identity and source role do not match')

def _core_rules(refs, rules):
    _refs(refs, rules, 'rule')
    for rid in refs:
        rule = rules[rid]
        if rule['status'] != 'approved' or rule['source_role'] not in ('core', 'core_supplement'):
            raise ContractError('only approved core or core-supplement rules support current production claims')

def _binding(output, inp):
    expected = {key: inp['meta'][key] for key in ('analysis_run_id', 'input_snapshot_id')}
    if output['binding'] != expected:
        raise ContractError('cross-run or cross-snapshot binding')

def _uncertainties(output, gaps):
    uncertainties = _unique(output['uncertainties'], 'gap_id')
    if not set(gaps).issubset(uncertainties):
        raise ContractError('an unresolved server gap was omitted')
    for gid in uncertainties:
        if gid not in gaps and not gid.startswith('AI_GAP_'):
            raise ContractError('new gap needs AI_GAP_ prefix')

def _has_specific_limit(text):
    """Reject bare implementation-status boilerplate, not a semantic entailment test."""
    normalized = re.sub(r'[\s，。；：、,.!！?？:;]', '', text)
    for fragment in (
        '当前依据不足', '目前依据不足', '资料不足', '信息不足', '缺少信息',
        '缺少完整引擎', '引擎未完成', '引擎尚未完成', '引擎未实现',
        '算法未完成', '算法尚未完成', '规则未完成', '规则尚未完善',
        '暂时无法判断', '目前无法判断', '无法判断', '不能判断',
        '不能解卦', '无法解卦', '需要补充信息', '请补充信息',
        '所以', '因此', '由于', '因为',
    ):
        normalized = normalized.replace(fragment, '')
    return bool(normalized)

def _conclusion(output, claims, rules=None):
    conclusion = output['conclusion']
    _refs(conclusion['claim_refs'], claims, 'conclusion claims')
    cited = [claims[c] for c in conclusion['claim_refs']]
    if not {a for c in cited for a in c['assumptions']}.issubset(conclusion['key_conditions']):
        raise ContractError('conclusion omitted a cited claim assumption')
    if not {limit for c in cited for limit in c['limitations']}.issubset(conclusion['limits']):
        raise ContractError('conclusion omitted a cited claim limitation')
    if conclusion['qualification'] == 'undetermined':
        if conclusion['direction'] != 'undetermined':
            raise ContractError('undetermined conclusion cannot carry a resolved direction')
        if not any(_has_specific_limit(limit) for limit in conclusion['limits']):
            raise ContractError('undetermined conclusion needs a specific substantive limit')
        if not _has_specific_limit(conclusion['answer']):
            raise ContractError('conclusion answer cannot be bare engine-status boilerplate')
        return
    primary = [c for c in cited if c['dimension'] in ('outcome', 'subject_effect')
               and c['kind'] in ('engine_supported', 'ai_hypothesis')]
    if not primary:
        raise ContractError('conditional conclusion needs outcome or subject-effect claims')
    if rules is not None:
        for claim in primary:
            if not any(rules[r]['usage'] == 'interpretation' for r in claim['rule_refs']):
                raise ContractError('overall conclusion requires an applicable interpretation rule')
    directions = {c['direction'] for c in primary} - {'neutral', 'unknown'}
    expected = ('mixed' if 'mixed' in directions or directions == {'favorable', 'unfavorable'}
                else next(iter(directions)) if len(directions) == 1 else None)
    if expected is None or conclusion['direction'] != expected:
        raise ContractError('conclusion direction contradicts or exceeds cited primary claims')

def validate_output(stage: str, raw_output: str, server_input: dict, pack=None) -> dict:
    """Returns validated structured data; does not authorize free-text semantic claims.
    Failures raise ContractError; caller records raw output/error even on failure.
    """
    pack = load_pack() if pack is None else pack
    if stage not in pack['stages']:
        raise ContractError('unknown stage')
    item = pack['stages'][stage]
    check_schema(server_input, item['input_schema'])
    if server_input['meta']['prompt_digest'] != prompt_digest(pack, stage):
        raise ContractError('prompt digest mismatch')
    out = parse_raw(raw_output)
    check_schema(out, item['output_schema'])
    _binding(out, server_input)
    if stage == 'intent':
        evidence = _unique(server_input['user_evidence'], 'evidence_id')
        if not any(e['origin'] == 'user_question' and e['text'] == server_input['question'] for e in evidence.values()):
            raise ContractError('question is missing from original evidence')
        candidates = _unique(out['candidates'], 'candidate_id')
        for candidate in candidates.values():
            _quote_check(candidate['evidence_quotes'], evidence)
        if out['status'] == 'ready':
            if out['selected_candidate_id'] not in candidates or out['clarifying_questions']:
                raise ContractError('ready intent must select a candidate without a blocking question')
        elif out['selected_candidate_id'] is not None or not out['clarifying_questions']:
            raise ContractError('ambiguous intent needs factual clarification without forced selection')
    elif stage == 'selection':
        evidence = _unique(server_input['user_evidence'], 'evidence_id')
        rules = _unique(server_input['rules'], 'rule_id')
        _source_roles(rules)
        candidates = _unique(out['candidates'], 'candidate_id')
        mapping = {'generates_me':'parents', 'same_as_me':'siblings', 'generated_by_me':'offspring',
                   'controlled_by_me':'wealth', 'controls_me':'official_ghost'}
        for candidate in candidates.values():
            _quote_check(candidate['evidence_quotes'], evidence)
            _core_rules(candidate['rule_refs'], rules)
            if any(rules[r]['usage'] != 'selection' for r in candidate['rule_refs']):
                raise ContractError('non-selection rule used for functional candidate')
            if candidate.get('subject_reference') is not None:
                if candidate['relation'] is not None or candidate['six_relative'] is not None:
                    raise ContractError('subject reference is distinct from functional kinship')
                required = {'interpretation.three_self_references', 'interpretation.analysis_scale'}
                if candidate['purpose'] == 'primary' and not required.issubset(candidate['rule_refs']):
                    raise ContractError('primary subject reference requires self-reference and scale rules')
            elif (candidate['relation'] is None or
                  mapping.get(candidate['relation']) != candidate['six_relative']):
                raise ContractError('functional relation/kinship mismatch')
        selected = candidates.get(out['selected_primary_id'])
        if out['status'] == 'ready':
            if out['selected_primary_id'] is None:
                raise ContractError('$.selected_primary_id: ready selection needs a non-null primary candidate ID')
            if selected is None:
                raise ContractError('$.selected_primary_id: candidate ID does not exist in candidates')
            if selected['purpose'] != 'primary':
                index = next(i for i, candidate in enumerate(out['candidates'])
                             if candidate['candidate_id'] == out['selected_primary_id'])
                raise ContractError(f'$.candidates[{index}].purpose: selected_primary_id must reference a primary candidate')
            # Ready means a supported primary candidate exists. Remaining
            # conditions and questions must reach interpretation as disclosed
            # gaps, not prevent every partial reading at this stage.
        elif out['selected_primary_id'] is not None:
            raise ContractError('unresolved selection cannot be frozen as selected')
        if out['status'] == 'needs_clarification' and not out['clarifying_questions']:
            raise ContractError('missing material clarification')
        if out['status'] == 'needs_rule_review' and not out['unresolved']:
            raise ContractError('missing rule gap')
    elif stage == 'interpretation':
        _binding(server_input['selection'], server_input)
        facts = _unique(server_input['facts'], 'fact_id')
        rules = _unique(server_input['rules'], 'rule_id')
        _source_roles(rules)
        inferences = _unique(server_input['inferences'], 'inference_id')
        gaps = _unique(server_input['unresolved_gaps'], 'gap_id')
        claims = _unique(out['claims'], 'claim_id')
        _uncertainties(out, gaps)
        for inference in inferences.values():
            if inference['analysis_run_id'] != server_input['meta']['analysis_run_id']:
                raise ContractError('inference belongs to another run')
            _refs(inference['premise_fact_ids'], facts, 'inference premises')
            _refs([inference['rule_id']], rules, 'inference rule')
        for claim in claims.values():
            _refs(claim['fact_refs'], facts, 'claim facts')
            _refs(claim['inference_refs'], inferences, 'claim inferences')
            if claim['kind'] == 'engine_supported':
                _core_rules(claim['rule_refs'], rules)
                if not claim['inference_refs'] or claim['requires_review'] or claim['assumptions']:
                    raise ContractError('engine claim must contain a verified inference, without new assumptions')
                for iid in claim['inference_refs']:
                    inf = inferences[iid]
                    if inf['status'] != 'verified' or inf['conclusion'] != claim['proposition'] or inf['direction'] != claim['direction']:
                        raise ContractError('inference does not support exact structured conclusion')
                    if not set(inf['premise_fact_ids']).issubset(claim['fact_refs']) or inf['rule_id'] not in claim['rule_refs']:
                        raise ContractError('claim omitted inference premises or rule')
                if any(g['blocking'] and claim['dimension'] in g['affects'] for g in gaps.values()):
                    raise ContractError('blocking gap prevents supported claim in this dimension')
            elif claim['kind'] == 'ai_hypothesis':
                _core_rules(claim['rule_refs'], rules)
                if not claim['rule_refs'] or not claim['requires_review'] or not claim['limitations']:
                    raise ContractError('AI hypothesis needs applicable core rule, review flag and limitations')
                if claim['inference_refs']:
                    raise ContractError('hypothesis uses facts/rules; do not disguise it as an engine inference')
            else:
                if claim['rule_refs'] or claim['inference_refs'] or claim['direction'] != 'neutral':
                    raise ContractError('real-world context cannot masquerade as a divination prediction')
                if any(facts[f]['kind'] != 'context' for f in claim['fact_refs']):
                    raise ContractError('real-world context must use context facts')
                if not any(all(facts[f][key] == claim['proposition'][key] for key in ('subject','predicate','value')) for f in claim['fact_refs']):
                    raise ContractError('context proposition must match observed context')
        _unique(out['advice'], 'advice_id')
        for advice in out['advice']:
            _refs(advice['claim_refs'], claims, 'advice claims')
            _refs(advice['fact_refs'], facts, 'advice facts')
            if not advice['claim_refs'] and not advice['fact_refs']:
                raise ContractError('advice needs a factual or interpretive basis')
            if advice['basis'] == 'system_interpretation' and not advice['claim_refs']:
                raise ContractError('system advice needs claim refs')
            if advice['basis'] == 'real_world_information':
                if not advice['fact_refs'] or any(facts[f]['kind'] != 'context' for f in advice['fact_refs']):
                    raise ContractError('real-world advice needs observed context facts')
                if any(claims[c]['kind'] != 'real_world_context' for c in advice['claim_refs']):
                    raise ContractError('real-world advice cannot disguise chart speculation')
        if any(c['requires_review'] for c in claims.values()) and out['status'] != 'needs_review':
            raise ContractError('review-required claim is not reflected in status')
        if out['status'] == 'supported' and (gaps or out['uncertainties'] or not claims):
            raise ContractError('supported status conflicts with gaps or empty claims')
        _conclusion(out, claims, rules)
    else:
        plan = server_input['accepted_interpretation']
        _binding(plan, server_input)
        claims = _unique(plan['claims'], 'claim_id')
        advice = _unique(plan['advice'], 'advice_id')
        gaps = _unique(server_input['unresolved_gaps'], 'gap_id')
        _uncertainties(out, gaps)
        source_unc = {u['gap_id']: u for u in plan['uncertainties']}
        if out['uncertainties'] != plan['uncertainties']:
            raise ContractError('report must preserve all accepted uncertainty records verbatim')
        if out['clarifying_questions'] != plan['clarifying_questions']:
            raise ContractError('report must preserve accepted clarification questions')
        if out['question_restated'] != server_input['question']:
            raise ContractError('report changed the current question')
        if out['conclusion'] != plan['conclusion']:
            raise ContractError('report must preserve the accepted conclusion verbatim')
        _conclusion(out, claims)
        dimensions = [p['dimension'] for p in out['parts']]
        if set(dimensions) != {'outcome','subject_effect','cost','support','obstacle','adjustment'} or len(set(dimensions)) != 6:
            raise ContractError('report must cover six distinct dimensions')
        for part in out['parts']:
            _refs(part['claim_refs'], claims, 'report claims')
            _refs(part['advice_refs'], advice, 'report advice')
            if any(claims[c]['dimension'] != part['dimension'] for c in part['claim_refs']):
                raise ContractError('report claim belongs to different dimension')
            if part['advice_refs'] and part['dimension'] != 'adjustment':
                raise ContractError('advice only belongs in adjustment dimension')
            if part['qualification'] != 'undetermined' and not part['claim_refs'] and not part['advice_refs']:
                raise ContractError('unsupported report section is presented as resolved')
            referenced = [claims[c] for c in part['claim_refs']]
            if part['qualification'] == 'supported' and any(c['kind'] == 'ai_hypothesis' for c in referenced):
                raise ContractError('conditional hypothesis promoted to supported report')
            if part['qualification'] == 'supported' and any(g['blocking'] and part['dimension'] in g['affects'] for g in gaps.values()):
                raise ContractError('report hid a blocking uncertainty')
    return out

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['intent','selection','interpretation','report'])
    parser.add_argument('server_input')
    parser.add_argument('raw_output')
    args = parser.parse_args()
    try:
        result = validate_output(args.stage, Path(args.raw_output).read_text(), parse_raw(Path(args.server_input).read_text()))
        print(json.dumps({'valid': True, 'validated_output': result}, ensure_ascii=False))
    except ContractError as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
