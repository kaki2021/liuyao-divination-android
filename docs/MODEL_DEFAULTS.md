# DeepSeek 默认模型与质量

当前默认厂商为DeepSeek，模型为 `deepseek-v4-pro`，思考质量为 `max`。模型设置与页面上的当前模型提示会显示实际配置的质量。理解问题、取用、综合解卦、整理报告四个阶段均使用同一套模型设置。

发送到DeepSeek的JSON控制参数为：

```json
{
  "model": "deepseek-v4-pro",
  "thinking": {"type": "enabled"},
  "reasoning_effort": "max",
  "max_tokens": 131072
}
```

max是思考强度。输出额度包含思考与最终回答，采用官方max档的128K默认额度，避免旧8192额度过早截断；这不是要求每次生成128K。单次请求默认等待600秒，四阶段进度照常显示。正式接口的账号权限与实际响应仍由DeepSeek决定，软件不会在失败时偷偷换成其他模型。

已有旧默认Flash配置时，启动会一次性更新为Pro与max，保留API Key及其他配置，并把原文件备份为同目录下的 `.env.before-deepseek-pro-max`。自定义模型允许列表不会被替换。更新之后手动选择的模型会继续保留；旧浏览器记录的Flash默认选择会在首次使用时改为Pro。

如需调整质量，在模型设置显示的配置文件中修改 `DEEPSEEK_REASONING_EFFORT` 为 `low`、`high`、`max` 或 `none`，保存后重启。新质量参数优先于旧 `DEEPSEEK_THINKING` 开关。用户明确配置的其他模型与质量保留其设置。

## 与卜宅改进的关系

新增10条原理用于明确启用的“卜宅／选房专题”，按场所、起卦身份与阶段选择适用规则。仅在问题中出现“地理”“风水”等词不会自动开启，也不是所有涉及地点的问题都会使用选房规则。

普通占问的排盘、六亲、取用规则与70项实验评分参数未改变。这次模型默认设置会影响所有使用DeepSeek的分析，AI的表述、条件解释和综合判断可能改变；已保存的历史报告保留原样。

## 核对与测试

官方接口说明（核对于2026-09-19）：

- [Chat Completions API](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/)
- [思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)

本次针对适配器、配置升级、启动器、分析流程和真实本地HTTP服务执行83项回归测试；通过模拟传输逐项核对四阶段实际请求，以及质量参数随分析审计保留；7项浏览器检查验证新默认值、旧选择迁移、主动选择保留及质量展示。没有调用付费模型，未做Windows真机或真实DeepSeek账号联调。完整包另经CRC、逐文件摘要与独立解压启动检查。

卜宅改进说明见 `BUZHAI_REVIEW.md`；公开源码的复核结果统一汇总在 `TEST_RESULTS.md`。
