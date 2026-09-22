"""Versioned numerical model. Excel is the human-facing editing interface.

Only the compiled file is read by an analysis; each analysis freezes one copy.
The built-in schema (not an imported workbook) owns IDs, types and limits.
"""
from __future__ import annotations

from functools import lru_cache
import argparse
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'knowledge_base'
TEMPLATE = ROOT / 'rules_template.xlsx'
LOCK = threading.RLock()
HEADERS = ['Rule_ID', '类别', '规则名称', '条件说明', '参数值', '单位', '启用', '状态', '来源', '解释', '备注', '数据类型', '最小值', '最大值']
EXPLANATION_HEADERS = ['参数含义','计算公式','修改后的影响','计算示例','初始取值考虑','参数类型','影响位置']
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


class RulesNotInstalled(ValueError):
    """The public build has not received a separately distributed rule pack."""


def rules_installed(directory=None):
    directory = Path(directory) if directory else ROOT
    return (directory / 'compiled_rules.json').is_file()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def schema():
    return json.loads((ROOT / 'rule_schema.json').read_text(encoding='utf-8'))


def validate(rows):
    if not isinstance(rows, list):
        raise ValueError('规则必须为列表')
    definitions = schema()['rules']
    ids = [r.get('id') for r in rows if isinstance(r, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        raise ValueError('Rule_ID 缺失或重复')
    if set(ids) != set(definitions):
        raise ValueError('Rule_ID 被修改、缺失或新增：' + ', '.join(sorted(set(ids) ^ set(definitions))))
    for row in rows:
        spec = definitions[row['id']]
        if set(row) != {'id', 'value', 'enabled', 'source', 'explanation', 'notes'}:
            raise ValueError(row['id'] + ' 字段不完整')
        value = row['value']
        if type(row['enabled']) is not bool:
            raise ValueError(row['id'] + ' 启用必须为是或否')
        if spec.get('required') and not row['enabled']:
            raise ValueError(row['id'] + ' 为必要参数，不能禁用')
        if spec['type'] == 'number':
            if type(value) not in (int, float) or not math.isfinite(value) or not spec['min'] <= value <= spec['max']:
                raise ValueError(row['id'] + ' 数值类型或范围不正确')
        elif spec['type'] == 'branch':
            if not isinstance(value, str) or value not in list('子丑寅卯辰巳午未申酉戌亥'):
                raise ValueError(row['id'] + ' 必须填写一个地支')
        for field in ('source', 'explanation', 'notes'):
            if not isinstance(row[field], str) or len(row[field]) > 2000:
                raise ValueError(row['id'] + ' 说明文本无效')
    values = {r['id']: r['value'] for r in rows}
    if values['LEVEL_WEAK'] >= values['LEVEL_STRONG']:
        raise ValueError('偏弱分界必须小于偏强分界')
    return rows


def compile_rules(rows):
    rows = sorted(copy.deepcopy(validate(rows)), key=lambda r: r['id'])
    for row in rows:
        if type(row['value']) is float and row['value'].is_integer(): row['value']=int(row['value'])
    checksum = digest({'schema': schema(), 'rules': rows})
    return {'schema_version': schema()['schema_version'], 'version': 'v5-exp-' + checksum[:16],
            'digest': checksum, 'rules': rows}


def atomic_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='rules-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


class RuleBook:
    def __init__(self, compiled):
        verified = compile_rules(compiled['rules'])
        if compiled != verified:
            raise ValueError('规则版本或摘要不匹配，请重新导入规则表')
        self.compiled = verified
        self.rows = {row['id']: row for row in verified['rules']}
        self.version, self.digest = verified['version'], verified['digest']

    def enabled(self, key): return self.rows[key]['enabled']
    def value(self, key): return self.rows[key]['value']
    def weight(self, key): return self.value(key) if self.enabled(key) else 0

    def contribution(self, key, detail, factor=1):
        return {'rule_id': key, 'value': round(self.weight(key) * factor, 6),
                'detail': detail, 'status': schema()['rules'][key]['status']}


def load_rules(directory=None):
    directory = Path(directory) if directory else ROOT
    with LOCK:
        path = directory / 'compiled_rules.json'
        if not path.exists():
            builtin_path = ROOT / 'compiled_rules.json'
            if not builtin_path.is_file():
                raise RulesNotInstalled('尚未安装规则包，请先在“规则”页面导入 .lyrules 加密规则包。')
            builtin = json.loads(builtin_path.read_text(encoding='utf-8'))
            save_rules(directory, builtin['rules'])
        return RuleBook(json.loads(path.read_text(encoding='utf-8')))


def save_rules(directory, rows):
    compiled = compile_rules(rows)
    raw = (json.dumps(compiled, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    directory = Path(directory)
    with LOCK:
        atomic_bytes(directory / 'versions' / (compiled['version'] + '.json'), raw)
        atomic_bytes(directory / 'compiled_rules.json', raw)
    return RuleBook(compiled)


def excel_rows(book):
    from .rule_explanations import explain_rule
    definitions = schema()['rules']
    result = []
    for row in book.compiled['rules']:
        s = definitions[row['id']]
        result.append([row['id'], s['category'], s['name'], s['condition'], row['value'], s['unit'],
            '是' if row['enabled'] else '否', s['status'], row['source'], row['explanation'], row['notes'],
            s['type'], s.get('min', ''), s.get('max', '')])
        note=explain_rule(row['id'],row,s)
        result[-1].extend(note[k] for k in ('meaning','formula','increase','example','rationale','kind_label','affects'))
    return result


def _sheet_member(archive):
    workbook = ET.fromstring(archive.read('xl/workbook.xml'))
    selected = next((s for s in workbook.findall('s:sheets/s:sheet', NS) if s.get('name') == 'Rules'), None)
    if selected is None: raise ValueError('找不到 Rules 工作表')
    rid = selected.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
    relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    target = next((r.get('Target') for r in relationships if r.get('Id') == rid), None)
    if not target: raise ValueError('规则工作表引用无效')
    member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
    if '..' in member.split('/'): raise ValueError('规则工作表路径无效')
    return member


def read_workbook(raw):
    if len(raw) > 5_000_000: raise ValueError('规则表超过 5 MB')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist()) > 20_000_000: raise ValueError('解压后规则表过大')
            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                strings = [''.join(t.text or '' for t in si.iter('{'+NS['s']+'}t')) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
            root = ET.fromstring(z.read(_sheet_member(z)))
            grid = {}
            for cell in root.findall('.//s:sheetData/s:row/s:c', NS):
                if cell.find('s:f', NS) is not None: raise ValueError('规则表不接受公式，请填写数值或文字')
                value = cell.find('s:v', NS)
                kind = cell.get('t')
                if kind == 'inlineStr': v = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
                elif kind == 's': v = strings[int(value.text)]
                elif value is None or value.text is None: v = ''
                elif kind in ('str', 'e'): v = value.text
                elif kind == 'b': v = bool(int(value.text))
                else: v = float(value.text)
                grid[cell.get('r')] = v
            headers=[grid.get(f'{chr(65+c)}1', '') for c in range(14)]
            if headers[4]=='Value':headers[4]='参数值'
            if headers != HEADERS:
                raise ValueError('表头被修改，请先导出当前规则表')
            rownums = sorted({int(''.join(filter(str.isdigit, r))) for r in grid})
            expected = schema()['rules']; rows = []
            for n in rownums:
                if n == 1: continue
                vals = [grid.get(f'{chr(65+c)}{n}', '') for c in range(14)]
                if all(v == '' for v in vals): continue
                key = vals[0]
                if key not in expected: raise ValueError(f'第 {n} 行 Rule_ID 无效')
                spec = expected[key]
                frozen = [spec['category'], spec['name'], spec['condition'], spec['unit'], spec['status'], spec['type'], spec.get('min',''), spec.get('max','')]
                if [vals[c] for c in (1,2,3,5,7,11,12,13)] != frozen:
                    raise ValueError(f'第 {n} 行系统字段被修改')
                if vals[6] not in ('是','否'): raise ValueError(f'第 {n} 行启用须填是或否')
                rows.append(dict(id=key, value=vals[4], enabled=vals[6]=='是', source=vals[8], explanation=vals[9], notes=vals[10]))
            return validate(rows)
    except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError) as exc:
        raise ValueError('无法读取规则表，请使用导出的 XLSX 文件') from exc


def export_workbook(book):
    """Fill the authored OOXML template using stdlib; no runtime dependency."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(TEMPLATE) as source, zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as out:
        member = _sheet_member(source)
        root = ET.fromstring(source.read(member))
        data = root.find('s:sheetData', NS)
        template_cells = {c.get('r'): c.attrib.copy() for c in data.findall('s:row/s:c', NS)}
        data.clear()
        dimension = root.find('s:dimension', NS)
        if dimension is None:
            dimension = ET.Element('{'+NS['s']+'}dimension')
            root.insert(1 if root.find('s:sheetPr', NS) is not None else 0, dimension)
        dimension.set('ref', 'A1:U'+str(len(book.rows)+1))
        columns = root.find('s:cols', NS)
        if columns is not None:
            ET.SubElement(columns, '{'+NS['s']+'}col', {'min':'20','max':'21','width':'38','customWidth':'1'})
        for n, values in enumerate([HEADERS+EXPLANATION_HEADERS] + excel_rows(book), 1):
            row = ET.SubElement(data, '{'+NS['s']+'}row', {'r': str(n), 'ht':'104' if n>1 else '32', 'customHeight':'1'})
            for index, value in enumerate(values):
                ref = f'{chr(65+index)}{n}'
                attributes = template_cells.get(ref, template_cells.get(f'S{n}', {'r':ref})).copy(); attributes['r']=ref
                attributes.pop('t', None)
                c = ET.SubElement(row, '{'+NS['s']+'}c', attributes)
                if type(value) in (int,float): ET.SubElement(c,'{'+NS['s']+'}v').text = str(value)
                else:
                    c.set('t','inlineStr'); ET.SubElement(ET.SubElement(c,'{'+NS['s']+'}is'),'{'+NS['s']+'}t').text = str(value)
        for info in source.infolist():
            raw=source.read(info)
            if info.filename==member:raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
            elif info.filename.startswith('xl/tables/') and info.filename.endswith('.xml'):
                table=ET.fromstring(raw)
                if table.get('name')=='RuleParameters':
                    extent='A1:U'+str(len(book.rows)+1)
                    table.set('ref',extent)
                    auto_filter=table.find('s:autoFilter',NS)
                    if auto_filter is not None:auto_filter.set('ref',extent)
                    headers=table.find('s:tableColumns',NS)
                    for index,title in enumerate(EXPLANATION_HEADERS[-2:],20):
                        ET.SubElement(headers,'{'+NS['s']+'}tableColumn',{'id':str(index),'name':title})
                    headers.set('count',str(len(headers)))
                    raw=ET.tostring(table,encoding='utf-8',xml_declaration=True)
            elif info.filename=='xl/workbook.xml':
                wb=ET.fromstring(raw);calc=wb.find('s:calcPr',NS)
                if calc is None:calc=ET.SubElement(wb,'{'+NS['s']+'}calcPr')
                calc.set('fullCalcOnLoad','1');calc.set('forceFullCalc','1');calc.set('calcMode','auto')
                raw=ET.tostring(wb,encoding='utf-8',xml_declaration=True)
            elif info.filename.startswith('xl/worksheets/') and info.filename.endswith('.xml'):
                sheet=ET.fromstring(raw)
                for cell in sheet.findall('.//s:c',NS):
                    if cell.find('s:f',NS) is not None:
                        cached=cell.find('s:v',NS)
                        if cached is not None:cell.remove(cached)
                raw=ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
            out.writestr(info,raw)
    return buffer.getvalue()


def main():
    p=argparse.ArgumentParser(description='六爻实验规则表导入导出')
    p.add_argument('operation', choices=['import','export','check'])
    p.add_argument('file'); p.add_argument('--directory', type=Path)
    args=p.parse_args()
    from liuyao_app.config import data_directory
    directory=args.directory or data_directory()/'knowledge_base'
    if args.operation=='export': atomic_bytes(args.file,export_workbook(load_rules(directory)))
    else:
        rows=read_workbook(Path(args.file).read_bytes())
        book=save_rules(directory,rows) if args.operation=='import' else RuleBook(compile_rules(rows))
        print(book.version)


if __name__=='__main__': main()
