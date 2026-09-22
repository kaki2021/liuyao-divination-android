# 六爻软件开发基础

这里是可运行的业务基础和明确的接口资料，配套需求与设计文件在资料包的 documents 目录。本目录提供应用所用的规则、契约与计算模块，Windows本机包另含本机浏览器界面和启动文件。界面接通、模型调用、Windows启动及完整占断各自按实际实现和验证记录确认，不能互相替代。

## Windows本机交付

交付形态为内置Python运行环境的Windows本机包，用户无需另装Python，界面由本机浏览器打开。配置默认保存于 `%LOCALAPPDATA%\Liuyao\.env`，案例等数据保存在该目录的 `data` 下；可用 `LIUYAO_HOME` 指定其他数据根目录。Python运行环境取得、封装与Windows实际启动分别验证，目前不能将开发环境检查写成Windows实机已通过。

## 开发环境运行

使用 Python 3.10 或更新版本。当前代码仅依赖 Python 标准库；本次实际检查运行在 Python 3.12。进入本目录后运行：

```sh
python run_checks.py
python validate_input.py liuyao_input_example.json
python generate_reference_tables.py
python generate_branch_tables.py
```

第一条依次执行基础排盘、输入、案例存储、AI契约、AI事件与存储衔接、三形六害、起卦标准化七组检查。实际数量和结果见对应结果JSON及工作簿；这些检查验证程序行为，不是真实预测成功案例。工作簿另列尚待应用接通后执行的验收场景。

## 文件与职责

| 文件 | 用途 |
|---|---|
| liuyao_input_schema.json | 普通入口：问题、casting或lines、可选实际起卦时间；同给时要求一致 |
| liuyao_input_example*.json | 直接六爻或器具输入及已知／未知时间的格式样例 |
| validate_input.py | 当前入口校验、器具结果一致性检查和四象推导；不是通用JSON Schema实现 |
| casting_input.py | 枚卜三次、太极六次转换为lines，保留原始casting，拒绝冲突输入 |
| base_chart.py | 宫序、纳支、主卦六亲、世应、世身、卦身、动爻和变卦结构 |
| branch_relations.py | 三形追溯及三形、六害配对分类；允许同一对地支返回多种关系 |
| generate_branch_tables.py / branch_reference_tables.json | 从关系模块生成三形六害定义参考表，保留原理来源和模块摘要 |
| hexagram_names.json | 六爻阴阳结构与卦名映射 |
| generate_reference_tables.py | 根据基础程序生成64卦、384爻参考表及内容摘要 |
| reference_tables.json | 已生成的参考表，不作为人工编辑的规则来源 |
| rule_catalog.json | 当前规则的依据、适用范围、待研究问题及实际实现状态 |
| liuyao_ai_prompt_pack.yaml | 四阶段完整提示词、输入输出Schema及示例；内容为YAML兼容的JSON |
| validate_ai_contract.py | AI字段、引用范围、阶段边界和部分受控含义校验 |
| case_store.py / case_store.sql | SQLite案例业务方法、事务、归属检查、追加记录和幂等 |
| case_record_schema.json | 后台案例导出契约，不是用户可写输入 |
| case_record_example.json | 工程样例，不是真实用户案例 |
| case_store_notes.md | 案例接口调用方法、时间语义与接入边界 |
| test_*.py / *_results.json | 可执行检查和本次实际运行结果 |

入口支持三种方式：

- 枚卜丸：casting.method为meibu，results恰好三项字符串，依次下卦、上卦、动爻。circle乾、square坤、1震2兑3坎4艮5离6巽；第三次circle全动、square全静，数字指定单爻动。
- 太极丸：casting.method为taiji，results恰好六项字符串，自初至上每项由三个2或3组成。界面提供222、223、233、333四种组合，分别对应老阴、少阳、少阴、老阳；API兼容同组成排列，只按数量归类并保留原串，不赋予排列空间含义。
- 直接六爻：仅提供lines，不传casting.method=direct。lines为old_yin、young_yang、young_yin、old_yang之一，恰好六项，从下至上。

API可只给casting，由后台生成lines；两者同给必须一致。器具原始casting与标准化lines共同保留，修改原始结果须重算。太极丸组合没有三丸身份和空间顺序，不启用或反推六峜。实际起卦时间缺失保持未知，服务器收到资料的时间另存。

## 开发衔接

本机软件已将三种结果录入页、确定性标准化、CaseStore和calculate_base_chart连通。每份提交建立记录；修改输入追加修订，开始分析固定当时输入和上下文，结束分析追加结果，反馈关联当时报告。AI提供意图理解、取用候选和解释，各次尝试保留原文与校验结果。校验通过不等于自然语言推论正确，正式模型仍需独立评估。

Actor必须由服务器已认证会话构造。本目录的业务方法不独立提供HTTP鉴权；liuyao_app/server.py提供限本机使用的会话边界。输入正文不能自行声明可信用户、校验结果、规则摘要或完成状态。用户删除、权限分级、主动取消与备份恢复界面待实现；应用重启已将中断任务保留为失败，不自动重放模型调用。

历法口径、真五行适用模块、同类用神多现选择、综合旺衰与完整成败判断按规则登记表继续研究，不让AI补成确定算法。变卦结构已计算，变爻六亲尚未在基础模块执行。普通月令函数只返回给定五行的单项旺相休囚死，不代表历法和综合判断已接通。

三形六害模块只识别定义关系，尚未接入整卦作用目标与大象判断。三形的无恩、恃势、无礼是类别，六害的恩间、害间也不是固定吉凶或对现实人物动机的证明。日月相害另一端不明时保留未决，不自动当成日支与月支互害。

来源以《卜筮正术》及《卜筮正术补充》共同作为原理核心，AI规则引用分别使用SRC-BSZS/core及SRC-BSZS-SUPP/core_supplement。其他材料的身份与原文位置见规则总册。主文档用B编号，补充PDF用PDF-P1至PDF-P6。文件内容摘要用于追溯，不是软件发布编号。
