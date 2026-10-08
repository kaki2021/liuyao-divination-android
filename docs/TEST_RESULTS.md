# 测试与验证结果

复核日期：2026-10-08。

## 界面状态与公开功能复核（2026-10-08）

修复重新起卦后规则试算仍引用上一卦输入、排盘和说明快照的问题；忙碌或取消离开时保留原案例反馈。实验参数版本改变后重新读取计算说明，过期请求的结果或错误不能覆盖新版本；历史分析的说明快照保持原样。旧记录的空报告或仅含模型信息的报告不再遮挡可读备用报告，反馈继续对应明确关联的那次分析。规则筛选无结果时，刷新案例或卦盘不会恢复无关的旧详情。

本轮 213 项 Python 回归检查中，212 项通过，1 项因缺少可选 `jsonschema` 跳过；包含 119 项条件判断、系列、记录和规则安装检查，以及 94 项基础结构、历法、配置、解释一致性、出生资料和起卦输入检查。所有检查使用公开测试数据或占位参数。

```bash
node android/tests/ui_state.cjs
node android/tests/condition_model.cjs
node android/tests/rules_model.cjs
node android/tests/series_model.cjs
```

Node 状态检查直接执行生产函数，覆盖接受／取消／忙碌时重新起卦、参数版本变更与相同版本复用、过期请求成功和失败的竞态、隐藏页面的缓存失效；源码和 Chrome 58 编译版均通过。报告回退、历史反馈关联、参数和系列模型检查通过。这些是状态及模型检查，不代替浏览器交互验收。

13 个脚本的语法和编译摘要核对通过。Android 资源包重新生成，共 753 个文件、800498 字节；126 个非时区资源逐项对应源码或编译文件，ZIP CRC、私有规则排除及 SHA256 通过，摘要为 `1948aac2ab5788ec46af7b0fe2b21f254a53710b30a73429b217c65342231fa9`。README 的 7 张图片存在且可解码，示意图和早期运行截图的标注保持明确。

本轮未调用真实收费模型，未运行浏览器布局、截图、APK 编译或手机实机检查。完整综合旺衰、有效暗动、作用先后、化空影响与精确应期仍属于明确保留未知的系统判据缺口。

## 规则说明可读性复核（2026-10-08）

普通规则页去掉通用的开发实现状态行；旬空条目改为“识别方法／含义区别”，按用途取用的说明改为同类爻有多个时逐一列出并说明取舍依据。计算逻辑文档补充两个父母爻的说明示例，开发实现范围与版本追溯仍集中在计算逻辑内；版本变更记录留在项目文档，不进入普通规则正文。本次仅调整说明与展示，判断行为保持原样。

14 项条件判断检查全部通过；源码与编译版 Node 条件模型检查通过。13 个脚本重新编译，753 个文件的 Android 资源包重新生成，共 800054 字节，SHA256 为 `5535c07e2af2e0c138b3a4de98ad1bf19820168d9474adf76fcd4107e3ce4ac6`；CRC、资源对应、摘要与私有规则排除核对通过。浏览器交互及 APK 真机检查未在本轮运行。

## 条件判断与内置计算逻辑复核（2026-10-08）

本次把默认解释改为独立状态与三值条件核对：多现取用保留候选，不按实验分强选；原爻旬空与化空分开，候选关系不自动视作有效作用。规则页增加判断规则、只读情景试算、反馈对照，以及离线可读、可导出的七步计算逻辑。新分析冻结说明与代码摘要，历史记录不回填。

```bash
PYTHONPATH=software_prep:. python -m unittest liuyao_app.test_conditional_reasoning -q
node android/tests/condition_model.cjs
node android/tests/rules_model.cjs
node android/tests/series_model.cjs
```

新增 14 项 Python 检查全部通过，覆盖全部 4096 种六爻组合的条件投影边界、原空与化空、多现取用、缺日期、未明确身份、世空选房例外、方向性六害、实验分不影响条件、说明与实际源码摘要、四阶段模型输入和历史快照、真实 HTTP 静态资源及说明导出、无私有规则的只读试算与严格输入校验。沿用下方列出的 105 项回归检查：104 项通过，1 项因缺少可选 `jsonschema` 跳过；合计 119 项中 118 项通过、1 项跳过。

Node 检查源码和 Chrome 58 编译版本的筛选、三值合取、试算变化、空破标签及反馈绑定历史分析；保留参数和系列行为检查通过。反馈自评不等于已验证准确率。修复本地 HTTP 静态资源白名单漏掉规则脚本、样式和系列脚本的问题，实际页面引用资源均返回 200。

`npm --prefix android run build:web` 编译 13 个脚本；`python android/prepare.py` 生成 753 个文件、799826 字节的公开 Android 资源包，SHA256 为 `07730ed718174c02abc835e2da741ef012d345ff332a14eed09326b0b8aeadea`。CRC、源码／编译资源逐项一致和私有规则排除检查通过。

本轮使用公开占位参数、临时案例库和合成模型；没有调用真实收费模型，也未运行浏览器布局、点击、截图或 APK 真机验收。完整综合旺衰、有效暗动、作用先后、化空影响及精确应期仍明确标为系统未实现判据。下方旧计分设计和构建摘要为历史记录。

## 规则工作台增量复核（2026-10-08）

规则页合并为「参数调校／使用原理／规则包」。强度、乘数、分界、候选排序和结构识别共用参数表与单项试算；列表只显示「参数／当前值」，保留类型筛选。使用流程、评分机制、通用及卜宅原理集中用表格阅读，原文和适用边界保留折叠入口。试算不写入规则，持久修改继续采用 XLSX 导出／导入。补充说明化空的单项权重固定、其他条件与最终强度可变，未改计分算法。

```bash
node android/tests/rules_model.cjs
node android/tests/series_model.cjs
PYTHONPATH=software_prep:. python -m unittest liuyao_app.test_guidance.GuidanceTests.test_public_principles_include_scoring_without_installed_rules liuyao_app.test_guidance.GuidanceTests.test_checked_sources_keep_quotes_separate_from_software_guidance liuyao_app.test_guidance.GuidanceTests.test_parameter_preview_is_read_only_and_traces_match_the_engine liuyao_app.test_series software_prep.test_case_store liuyao_app.test_response_compat liuyao_app.test_runtime_contract liuyao_app.test_selection_context liuyao_app.test_selection_projection liuyao_app.test_rule_installation
```

105 项 Python 检查中 104 项通过，1 项因可选 `jsonschema` 缺失跳过。新增检查使用公开占位规则验证试算与实际计算贡献一致，参数库和输入不被修改；未安装私有规则也能读取评分机制、出处与使用流程。实际 HTTP 入口的使用／卜宅原理读取、HTML ID 唯一性和资源引用检查通过。

生产参数模块的筛选、分页边界、数值／地支校验、必要项与识别开关检查通过；源码及 Chrome 58 编译版本的纯参数行为一致。前端及两份浏览器回归脚本语法检查通过。浏览器脚本已适配合并后的栏目、计算表、恢复当前值与规则包管理，本轮未运行浏览器布局、点击、截图或 APK 真机检查；预览图片为布局示意、示例数据。

`npm --prefix android run build:web` 通过，12 个脚本编译至 Chrome 58；`python android/prepare.py` 通过，公开资源包 750 个文件、780248 字节。ZIP CRC、资源与源码／编译脚本一致、未混入私有规则及 SHA256 检查通过；SHA256 为 `a7cc7d0149cf18c721f8b92830da48436a6cfa78d287741b3dec4ebe91d38857`。

## 系列档案增量复核（2026-10-08）

档案按系列归组，支持在选中卦下再起一卦及继续交流。旧案例成为独立系列起点；用户背景和补充在系列内共享并保留来源。分析冻结当时的共享上下文和所选父卦参考，父卦 AI 判断不进入本次用户事实；共享背景更新后，旧报告显示为历史分析。

```bash
PYTHONPATH=software_prep:. python -m unittest liuyao_app.test_series software_prep.test_case_store liuyao_app.test_response_compat liuyao_app.test_runtime_contract liuyao_app.test_selection_context liuyao_app.test_selection_projection liuyao_app.test_rule_installation
node android/tests/series_model.cjs
```

Python 共 102 项：101 项通过，1 项因缺少可选 `jsonschema` 跳过。系列用例覆盖迁移重开、父子及多层分支、独立系列隔离、用户补充及人物背景共享与出处、不可回写的旧快照、所选父卦的条件和边界、跨 owner / 跨案例引用拒绝、幂等重试、新旧报告在共享背景变更后的状态、整系列导出及实际模型请求中的系列参考与审计摘要。Node 使用实际前端系列模块，验证新卦不会继承旧卦象、起卦时间、原时点年龄和专题输入；追问文字与人物标识保留，背景继续作为带来源的系列资料共用，父卦来自所选分析，树状分支顺序正确且长链遍历不依赖递归。

前端及浏览器检查脚本语法检查通过。浏览器布局与点击回归、截图和 APK 实机验收未在本轮运行；当前环境无法启动受限的浏览器，也缺少 Android 编译环境。下方完整规则和旧构建结果是先前复核记录，不代表本次系列功能已完成这些验收。

`npm --prefix android run build:web` 与 `python android/prepare.py` 通过：11 个脚本编译至 Chrome 58 语法目标，公开 Android 资源包 748 个文件、776367 字节；SHA256 为 `7563457dd75f40f0fb1eb9c067018c86ec120ad1faa31d4968f5cd8745ca7121`。

## 本次公开源码复核

### 公开模式与完整规则模式

公开仓库不附真实规则，首先单独运行首次安装状态测试：

```bash
python -m unittest liuyao_app.test_rule_installation
```

结果：4 项全部通过。覆盖无规则启动、空白模板拒绝导入、私有数据目录安装及安装后重新加载。

维护者随后仅在测试期间临时放入真实编译规则，运行完整套件并在退出时移出公开目录：

```bash
LIUYAO_TEST_WITH_PRIVATE_RULES=1 python -m unittest discover -s . -p "test_*.py"
```

完整套件发现 340 项：337 项通过、3 项跳过、无失败。其中 2 项是只适用于“公开目录无规则”的状态测试，已在上一条命令中单独通过；另 1 项因可选依赖条件跳过。合并两个模式后，共有 339 项通过、1 项条件性跳过。覆盖排盘、历法、配置迁移、案例流程、人物档案、规则解释、AI 响应校验、状态恢复和本地服务等模块。

### 基础规则与数据契约

命令：

```bash
python software_prep/run_checks.py
```

结果：9 组检查全部通过，包括基础卦盘、输入契约、案例存储、AI 输出契约、结论结构、分支关系、枚卜丸 / 太极丸输入与人物信息。

### 公开配置检查

- `.env.example` 中无真实密钥。
- Android 签名只从环境变量读取。
- 仓库不包含 Keystore、签名密码、`local.properties`、案例数据库、APK 或 AAB。
- 仓库与 Android payload 均不包含真实 `rules.xlsx`、`compiled_rules.json`、历史规则版本或表格检查记录。
- `rules_template.xlsx` 只包含公开表头、样式和空白试算页，不能作为正式规则导入。
- `.lyrules` 已完成 Node 加密 / 解密回验和 Web Crypto 解密回验；错误口令会被 AES-GCM 完整性校验拒绝，解密文件与原表 SHA-256 一致。
- 从无规则的 Android payload 启动后，`/api/rules` 正确返回未安装状态；导入外部规则表后变为已安装并加载 70 项规则。
- 本地服务仅绑定 `127.0.0.1`，WebView 启动和后续请求使用随机凭据。
- `npm ci && npm run build:web` 通过，共生成并核对 10 个兼容脚本。
- `python android/prepare.py` 在未展开时区目录的公开结构中通过，共打包 746 个文件；生成的 payload SHA-256 为 `3769c678f20542c45accfecbdcdb65ae639e3b9714cf686394fa693365205ddb`。

## 源码包附带的历史构建记录

原始源码包记录显示，独立安装版本曾完成 release 构建、APK 签名验证、ZIP CRC、启动入口、Python 入口、ARM64 / x86_64 原生库和 16 KB 对齐检查。记录对应应用 ID `cn.guanxiang.liuyao.study`、版本名 `1.0`、内部版本号 `6`。

这些记录不替代当前提交的重新签名与真机测试；公开仓库不包含原签名材料或已签名 APK。

本次运行环境没有 Android SDK，且无法访问 Gradle 分发站，因此没有在此环境重新执行 `assembleDebug` / `assembleRelease`。首次在完整 Android 开发环境构建时仍应重新运行 Gradle、Lint 和真机检查。

## 未覆盖范围

- 未调用真实收费模型；AI 流程测试使用合成提供方。
- 未完成 Android 实体手机的安装、通知、省电策略和长期后台运行验收。
- 浏览器中的原生桥接使用测试替身，不能证明所有厂商 WebView 行为一致。
- 软件行为测试不证明占断准确率。
