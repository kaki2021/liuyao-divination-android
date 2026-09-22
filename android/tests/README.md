# 手机界面回归检查

在 android 目录准备好 content.zip 后，安装 Playwright（`npm install --no-save --package-lock=false playwright`），运行 `npx playwright install chromium`，然后运行 `node tests/buttons_browser.cjs`。也可通过 CHROMIUM_PATH 指定现有 Chromium，通过 PYTHON 指定 Python 3 命令。

检查运行 APK 中的实际资源包和安卓本地 HTTP 入口，使用隔离的临时数据库，不读取真实案例，不调用付费模型。输出位于 test-results，可通过 LIUYAO_TEST_OUTPUT 修改。

53 项检查刻意移除旧 WebView 不具备的方法，并模拟 flex 间距无效，验证设置、保存、分析、档案、规则、反馈、分页及逐爻卡片。Linux 测试机需具备中文字体，以便校验实际中文字宽和截图。原生桥接使用测试替身，因此原生密钥弹窗、系统文件选择器和通知仍需安装 APK 验收。

使用 `python tests/request_check.py` 检查三种起卦输入和卜宅专题的 16 个四阶段请求。需要源码目录及测试依赖 jsonschema，不会使用真实密钥或访问模型服务。

使用 `node tests/progress_browser.cjs` 检查运行中的步骤、计时、回复、状态断线、12 秒查询超时、重新打开、提交回执丢失、HTTP 401、自动修复和解锁。配套 progress_server.py 只在隔离临时目录中启动受控测试服务，以合成回复代替模型；不会进入 APK 的运行资源。

使用 `node tests/guidance_browser.cjs` 检查提问说明、四类卜宅引导、案例持久化、九类参数筛选、实际卦盘计分、只读试算及手机宽度。测试使用本地合成数据，不把教学例子发给模型。

公开源码的最新复核结果见 `../../docs/TEST_RESULTS.md`。本目录保留可复跑脚本，不提交带本机路径的原始运行日志。
