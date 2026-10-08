"""Built-in, exportable documentation bound to the shipped calculation code."""
import hashlib
import json
from pathlib import Path

from .calendar_context import CALCULATION_POLICY, CONVENTION_LABEL
from .conditional_reasoning import rule_guide
from .rule_explanations import scoring_guide
import base_chart as base

ROOT = Path(__file__).resolve().parents[1]
CODE_PATHS = (
    'software_prep/casting_input.py', 'software_prep/base_chart.py', 'software_prep/branch_relations.py',
    'software_prep/rule_catalog.json', 'liuyao_app/calendar_context.py',
    'liuyao_app/conditional_reasoning.py', 'liuyao_app/calculation_logic.py',
    'liuyao_app/comprehensive_analysis.py', 'liuyao_app/pipeline.py', 'liuyao_app/runtime_contract.py',
    'liuyao_app/rule_explanations.py', 'liuyao_app/strength_engine.py', 'liuyao_app/day_month_analysis.py',
    'liuyao_app/change_analysis.py', 'liuyao_app/relation_effect_engine.py', 'liuyao_app/buzhai.py',
    'liuyao_app/rulebook.py', 'liuyao_app/selection_projection.py', 'liuyao_app/report_generator.py',
    'liuyao_app/series_store.py',
)


def logic_guide(parameter_version=None):
    manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in CODE_PATHS}
    build = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    rules = rule_guide()
    return {'format': 'liuyao-calculation-logic', 'format_version': 1, 'title': '软件计算逻辑',
            'model_version': rules['model_version'], 'logic_version': rules['version'], 'build_digest': build,
            'parameter_version': parameter_version, 'code_manifest': manifest,
            'summary': '按真实输入排盘，按用途定位候选，分别核对爻状态和作用条件，再由 AI 解释目标成败与主体得失。实验评分仅供对照。',
            'steps': [
                {'title': '输入与系列', 'formula': '起卦记录 → 初爻至上爻的六个四象',
                 'detail': '枚卜丸、太极丸或直接六爻由 casting_input.normalize_casting_input 统一。系列共用有来源的背景；新卦保留独立原问、时间与盘面，父卦解释不变成事实。'},
                {'title': '历法', 'formula': CONVENTION_LABEL,
                 'detail': '只读取 actual_cast_time，转换到固定 UTC+08:00；缺失不取当前时间代替。六神用显示日柱天干。人物八字不参与六爻取用或强弱计算。'},
                {'title': '本变卦与六亲', 'formula': '老阴变阳、老阳变阴；少阴少阳不变',
                 'detail': '按八宫卦序归宫；本卦及动爻变支的六亲都以原宫五行为参照。只在发动位置讨论动变；其他变卦纳支不表示对应爻发动。'},
                {'title': '世应与身位', 'formula': '本宫世6，一至五世世1—5，游魂世4，归魂世3；应与世相隔三位',
                 'detail': '世身位置=世支在十二支中的零基序号%6+1。卦身支=（阳世从子、阴世从午起，加世位−1）%12。保留世、应、世身、卦身不同参照，不按分高切换。'},
                {'title': '状态与条件', 'formula': '旬空=日柱所属十日旬未纳入的两支；原爻与变支分别匹配',
                 'detail': '月破与日冲：两支序号差取模12等于6；六合查六对支。月令分类只记录旺相休囚死，不代替综合旺衰。每条规则逐条件为满足、不满足或未知：任一不满足则整条不满足，否则含未知则未知，全满足才标满足；满足仅表示适用前提。'},
                {'title': '取用与相关作用', 'formula': '用途 → 功能六亲或主体参照 → 本卦匹配，缺位再列本宫伏神',
                 'detail': '本问所用的六亲只对应一个爻时可以定位；同类六亲对应多个爻时，分别列出各爻及其采用条件。例如本问取父母爻而卦中有两个父母爻时，需说明各自与所问对象的关系，依据不足则保持未确定。只列来源对本问目标的候选关系；静爻日冲不一律当有效暗动，作用先后未知时不宣布全部同时生效。实验分不用于自动选定某爻。'},
                {'title': '解释与报告', 'formula': '结构事实＋用户资料＋适用原理＋条件缺口 → AI条件解释',
                 'detail': 'AI不得改写盘面或把未知条件填成满足。分别写目标成败与主体得失；key_conditions和limits随结论保存，在专业分析展示。研究审计及原始回复在Log。'}],
            'tables': [
                {'title': '本软件的宫五行', 'headers': ['宫', '五行'], 'rows': [[k, v] for k, v in base.PALACE_ELEMENTS.items()]},
                {'title': '五行与月令分类', 'headers': ['月令与爻的关系', '分类'],
                 'rows': [['同五行', '旺'], ['月令生爻', '相'], ['爻生月令', '休'], ['爻克月令', '囚'], ['月令克爻', '死']]},
                {'title': '缺口怎样处理', 'headers': ['缺口来源', '处理'],
                 'rows': [['用户事实', '只在影响本问时补问现实信息'], ['阶段未展开', '按保存输入与后续阶段核对'],
                          ['系统判据未实现', '显示能力边界，不要求用户补算法'], ['资料冲突或多个候选', '保留条件与分支，不替用户或资料作无据断言']]},
                {'title': '实现范围', 'headers': ['已实现', '仍需条件解释或案例核对'],
                 'rows': [['排盘、日月关系、原爻旬空与变支化空', '完整综合旺衰、化空具体影响与解除条件'],
                          ['形害类别、六害方向、本问候选关系', '有效暗动、作用先后与互斥、整体趋势'],
                          ['世空选房例外的前提核对', '世旺的完整判据，不能用月令或分数替代'],
                          ['原问和版本快照、实际反馈留存', '精确应期、预测准确率和参数校准']]}],
            'calendar_policy': CALCULATION_POLICY, 'rules': rules['rules'], 'legacy_scoring': scoring_guide(),
            'version_note': '本说明随软件保存；代码摘要来自当前安装文件。新分析冻结当时的逻辑摘要与说明，更新软件不改写旧报告。'}


def logic_markdown(guide):
    lines = ['# 软件计算逻辑', '', guide['summary'], '',
             f"判断模型：{guide['model_version']}", f"逻辑版本：{guide['logic_version']}",
             f"计算实现摘要：{guide['build_digest']}", f"实验参数版本：{guide['parameter_version'] or '未安装'}", '', guide['version_note'], '']
    for index, step in enumerate(guide['steps'], 1):
        lines += [f"## {index}. {step['title']}", '', step['formula'], '', step['detail'], '']
    for table in guide['tables']:
        lines += ['## '+table['title'], '', '| '+' | '.join(table['headers'])+' |', '| '+' | '.join(['---']*len(table['headers']))+' |']
        lines += ['| '+' | '.join(row)+' |' for row in table['rows']]
        lines.append('')
    lines += ['## 条件规则', '']
    for rule in guide['rules']:
        lines += ['### '+rule['name'], '']
        for label, value in rule.get('details', [['适用范围', rule['scope']], ['判断原则', rule['policy']]]):
            lines += [label+'：'+value, '']
        lines += ['出处：'+s['title']+'；'+s['locator']+'。'+s['statement'] for s in rule['sources']]
        if not rule['sources']:
            lines.append('本项是软件结构识别或能力边界，不代表原书给出了完整判断算法。')
        lines.append('')
    lines += ['## 实验评分（仅供研究对照）', '', guide['legacy_scoring']['rationale'], '']
    for item in guide['legacy_scoring']['formulas']:
        lines += [item['title']+'：'+item['formula'], '', item['detail'], '']
    lines += ['## 计算代码版本对应', '', '| 文件 | SHA256 |', '| --- | --- |']
    lines += [f'| {path} | {digest} |' for path, digest in guide['code_manifest'].items()]
    return '\n'.join(lines)+'\n'
