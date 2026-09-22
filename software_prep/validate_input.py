"""Standard-library validator for the current client casting contract.

This is not a general JSON Schema interpreter and does not validate divination
outcomes. Direct four-state input and explicit meibu/taiji records are supported.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from casting_input import CastingInputError, derive_casting_lines

STATES = {
    'old_yin': {'label': '老阴', 'yang': 0, 'moving': True},
    'young_yang': {'label': '少阳', 'yang': 1, 'moving': False},
    'young_yin': {'label': '少阴', 'yang': 0, 'moving': False},
    'old_yang': {'label': '老阳', 'yang': 1, 'moving': True},
}
TIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')
PERSON_INFO_FIELDS = {'subject', 'querent_age', 'subject_age', 'relationship', 'background', 'profile_id'}

def problem(path, code, message):
    return {'path': path, 'code': code, 'message': message}

def valid_timestamp(value):
    if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
        return False
    if value.endswith('-00:00'):
        return False  # RFC3339 unknown local offset is not a known absolute cast instant.
    if value[-6:-5] in ('+', '-'):
        if int(value[-5:-3]) > 23 or int(value[-2:]) > 59:
            return False
    try:
        instant = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return instant.utcoffset() is not None
    except (ValueError, OverflowError):
        return False

def validate_person_info(value):
    """Optional user context; ages are completed years at casting, never inferred.

    This records context only. It does not select a five-element algorithm or
    establish which age boundary the source material intends.
    """
    path = '$/person_info'
    if not isinstance(value, dict):
        return [problem(path, 'INVALID_PERSON_INFO', '人物信息须为对象；不填写时可省略')]
    errors = []
    for key in value.keys() - PERSON_INFO_FIELDS:
        errors.append(problem(path + '/' + key, 'UNEXPECTED_FIELD', '人物信息不接收此字段'))
    if 'profile_id' in value and (not isinstance(value['profile_id'],str) or not re.fullmatch(r'person_[a-f0-9]{32}',value['profile_id'])):
        errors.append(problem(path+'/profile_id','INVALID_PROFILE_ID','人物档案编号无效'))
    if 'subject' in value and value['subject'] not in ('self', 'other', 'unspecified'):
        errors.append(problem(path + '/subject', 'INVALID_PERSON_SUBJECT', '所问对象须为自己、他人或未指定'))
    for key in ('querent_age', 'subject_age'):
        if key in value and (type(value[key]) is not int or not 0 <= value[key] <= 150):
            errors.append(problem(path + '/' + key, 'INVALID_PERSON_AGE', '年龄须为起卦时的周岁整数（0至150）；未知请不填'))
    for key, limit in (('relationship', 200), ('background', 2000)):
        if key in value and (not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > limit):
            errors.append(problem(path + '/' + key, 'INVALID_PERSON_TEXT', f'该项须为1至{limit}字的非空文本；不填写时请省略'))
    if value.get('subject') == 'self' and 'subject_age' in value:
        errors.append(problem(path + '/subject_age', 'SELF_AGE_CONFLICT', '问自己时仅填写卜筮人年龄，不另填所问对象年龄'))
    return errors

def validate_buzhai(value):
    path = '$/buzhai'
    if not isinstance(value, dict):
        return [problem(path, 'INVALID_BUZHAI', '卜宅资料须为对象；普通问题请省略')]
    enums = {'stage': ('site_choice', 'scope_check', 'diagnosis', 'remedy_check'),
             'site_kind': ('yang', 'yin'), 'role': ('host', 'consultant', 'other'),
             'residence': ('not_occupied', 'occupied', 'unknown')}
    lengths = {'beneficiary': 80, 'site': 120, 'proposal': 800}
    errors = []
    for key in value.keys() - (enums.keys() | lengths.keys() | {'previous_case_id'}):
        errors.append(problem(path+'/'+key, 'UNEXPECTED_FIELD', '卜宅资料不接收此字段'))
    for key, options in enums.items():
        if value.get(key) not in options:
            errors.append(problem(path+'/'+key, 'INVALID_BUZHAI_CHOICE', '请选择有效的卜宅阶段、场所、起卦身份及入住状态'))
    for key, limit in lengths.items():
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > limit:
            errors.append(problem(path+'/'+key, 'INVALID_BUZHAI_TEXT', f'启用卜宅专题后，该项须为1至{limit}字的非空文本'))
    if 'previous_case_id' in value and (not isinstance(value['previous_case_id'], str) or not re.fullmatch(r'case_[a-f0-9]{32}', value['previous_case_id'])):
        errors.append(problem(path+'/previous_case_id', 'INVALID_CASE_REFERENCE', '前序案例编号格式错误；没有请留空'))
    return errors

def validate_input(value):
    errors = []
    if not isinstance(value, dict):
        return {'valid': False, 'errors': [problem('$', 'OBJECT_REQUIRED', '输入必须是对象')]}
    allowed = {'question', 'lines', 'actual_cast_time', 'casting', 'person_info', 'buzhai'}
    for key in value.keys() - allowed:
        errors.append(problem('$/' + key, 'UNEXPECTED_FIELD', '当前客户端入口不接收此字段'))
    question = value.get('question')
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        errors.append(problem('$/question', 'INVALID_QUESTION', '问题须为1至2000字的非空文本'))
    derived_lines = None
    if 'casting' in value:
        try:
            derived_lines = derive_casting_lines(value['casting'])
        except CastingInputError as exc:
            errors.extend(exc.errors)
    lines = value.get('lines', derived_lines)
    if 'lines' not in value and 'casting' in value and derived_lines is None:
        pass  # The malformed casting already has a precise validation error.
    elif not isinstance(lines, list) or len(lines) != 6:
        errors.append(problem('$/lines', 'SIX_LINES_REQUIRED', '须按初爻到上爻顺序提供六项四象结果'))
    else:
        for index, line in enumerate(lines):
            if not isinstance(line, str) or line not in STATES:
                errors.append(problem('$/lines/' + str(index), 'INVALID_FOUR_STATE', '必须明确老阴、少阳、少阴或老阳；卦名或仅阴阳不能代替'))
    if 'lines' in value and derived_lines is not None and value['lines'] != derived_lines:
        errors.append(problem('$/lines', 'CASTING_LINES_MISMATCH', '六爻结果与所记录的起卦结果不一致，请核对原始记录。'))
    actual_time = value.get('actual_cast_time')
    if actual_time is not None and not valid_timestamp(actual_time):
        errors.append(problem('$/actual_cast_time', 'INVALID_ACTUAL_CAST_TIME', '已知起卦时刻须为有效且含明确时区偏移的RFC3339时间；未知请留空或null'))
    if 'person_info' in value:
        errors.extend(validate_person_info(value['person_info']))
    if 'buzhai' in value:
        errors.extend(validate_buzhai(value['buzhai']))
    return {'valid': not errors, 'errors': errors}

def derive_six_lines(value):
    from casting_input import normalize_casting_input
    value = normalize_casting_input(value)
    base = [STATES[line]['yang'] for line in value['lines']]
    moving = [STATES[line]['moving'] for line in value['lines']]
    return {
        'line_order': 'bottom_to_top',
        'base_bits': base,
        'moving_line_numbers': [i + 1 for i, is_moving in enumerate(moving) if is_moving],
        'changed_bits': [1 - bit if is_moving else bit for bit, is_moving in zip(base, moving)],
        'actual_cast_time': value.get('actual_cast_time'),
        'time_context_status': 'known' if value.get('actual_cast_time') else 'unknown',
    }

def read_json(path):
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate JSON key: ' + key)
            value[key] = item
        return value
    def invalid_number(value):
        raise ValueError('Non-JSON number: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_number)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_json')
    args = parser.parse_args()
    try:
        data = read_json(args.input_json)
        result = validate_input(data)
        if result['valid']:
            result['server_derived'] = derive_six_lines(data)
    except (ValueError, OSError) as exc:
        result = {'valid': False, 'errors': [problem('$', 'INVALID_JSON_FILE', str(exc))]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['valid'] else 1)

if __name__ == '__main__':
    main()
