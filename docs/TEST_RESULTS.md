# 测试与验证结果

复核日期：2026-09-22。

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
