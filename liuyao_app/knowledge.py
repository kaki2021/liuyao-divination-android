"""Small local document library: bounded imports and Chinese lexical retrieval."""
import base64
from collections import Counter
import hashlib
import io
import math
from pathlib import PurePath
import re
import unicodedata
from xml.etree import ElementTree
import zipfile

MAX_TEXT = 300_000
STOP = {'什么', '怎么', '如何', '这个', '那个', '可以', '一下', '是否', '为什', '么是', '是什', '的含', '含义', '解释', '请问'}
STOP_CHARS = set('的了是在和与及或为么什怎样何吗呢请问这那一个我们你他们')


def import_text(body):
    if not isinstance(body, dict) or set(body) - {'title', 'text', 'file_base64', 'filename'}:
        raise ValueError('资料格式无效。')
    title = body.get('title') or body.get('filename')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
        raise ValueError('请填写 1 至 200 字的资料标题。')
    if ('text' in body) == ('file_base64' in body):
        raise ValueError('请选择粘贴文字或导入一个文件。')
    if 'text' in body:
        content = body['text']
        filename = None
    else:
        filename = body.get('filename')
        if not isinstance(filename, str) or len(filename) > 250:
            raise ValueError('文件名无效。')
        extension = PurePath(filename).suffix.lower()
        if extension not in ('.txt', '.md', '.markdown', '.docx'):
            raise ValueError('支持 TXT、Markdown 和 DOCX；PDF、扫描件请先转为文字。')
        encoded = body.get('file_base64')
        if not isinstance(encoded, str) or len(encoded) > 5_600_000:
            raise ValueError('单个文件请控制在 4 MB 以内。')
        try:
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 4_000_000:
                raise ValueError('单个文件请控制在 4 MB 以内。')
            if extension == '.docx':
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    info = archive.getinfo('word/document.xml')
                    if info.file_size > 4_000_000 or info.flag_bits & 1:
                        raise ValueError('文档正文过大或已加密。')
                    xml = archive.read(info)
                if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                    raise ValueError('不支持这个文档结构。')
                root = ElementTree.fromstring(xml)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                content = '\n'.join(''.join(p.itertext()) if not p.findall('.//w:t', ns) else
                                    ''.join(t.text or '' for t in p.findall('.//w:t', ns))
                                    for p in root.findall('.//w:p', ns))
            else:
                try:
                    content = raw.decode('utf-8-sig')
                except UnicodeDecodeError:
                    content = raw.decode('gb18030')
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, UnicodeError, RuntimeError) as exc:
            raise ValueError('无法读取文档，请导出为 UTF-8 的 TXT 或 Markdown 后重试。') from exc
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= MAX_TEXT:
        raise ValueError('资料正文需为 1 至 300000 字。')
    content = content.replace('\r\n', '\n').replace('\r', '\n').strip()
    if any(ord(c) < 32 and c not in '\n\t' for c in content):
        raise ValueError('资料包含非文本内容。')
    return {'title': title.strip(), 'text': content, 'filename': filename,
            'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()}


def chunks(text):
    """Preserve readable paragraph boundaries; long blocks retain overlap."""
    buffer = ''
    for paragraph in re.split(r'\n\s*\n', text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if buffer and len(buffer) + len(paragraph) + 2 > 1000:
            yield buffer
            buffer = ''
        while len(paragraph) > 1000:
            yield paragraph[:1000]
            paragraph = paragraph[840:]
        buffer = (buffer + '\n\n' + paragraph).strip()
    if buffer:
        yield buffer


def terms(text):
    text = unicodedata.normalize('NFKC', text).lower()
    result = re.findall(r'[a-z0-9_]{2,40}', text)
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        result.extend(c for c in run if c not in STOP_CHARS)
        if len(run) > 1:
            result.extend(run[i:i+2] for i in range(len(run)-1) if run[i:i+2] not in STOP)
    return Counter(result)


def retrieve(rows, question, history=(), limit=6):
    query = terms(question)
    # A follow-up such as “它和魂有什么区别” needs the earlier subject as well.
    if history and re.search(r'它|这个|那个|上述|刚才|继续|两者', question):
        for message in history[-4:]:
            if message['role'] == 'user':
                query.update(terms(message['content']))
    if not query or not rows:
        return []
    counts = [terms(r['text']) for r in rows]
    n = len(rows)
    average = sum(sum(c.values()) for c in counts) / n or 1
    df = Counter(t for c in counts for t in query if t in c)
    ranked = []
    for row, count in zip(rows, counts):
        score = 0
        title_terms = terms(row['title'])
        length = sum(count.values())
        for token in query:
            frequency = count.get(token, 0)
            if not frequency:
                continue
            idf = math.log(1 + (n - df[token] + .5) / (df[token] + .5))
            weight = .15 if len(token) == 1 else 1
            score += weight * idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * length / average))
            if token in title_terms:
                score += weight * idf * .4
        if score > 0:
            ranked.append((score, row))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['document_id'], pair[1]['sequence']))
    return [{key: row[key] for key in ('citation_id', 'document_id', 'title', 'version', 'sequence', 'text', 'sha256')}
            for _, row in ranked[:limit]]
