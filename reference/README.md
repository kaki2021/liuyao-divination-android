# 当前版本关键源码参考

这些文件是从组合构建使用的源码摘出的评审快照，用于了解功能实现，**不是完整可构建工程**。本分支的其余工程来自较早的公开 MVP，与最终测试 APK 并非同一代码树。

| 文件 | 用途 |
| --- | --- |
| `structured_profile_ui.js` | 完整资料、分类和编辑 UI |
| `people_assistant.py` | 人物助手的结构化提取与审核写入 |
| `people_assistant_ui.js` | 人物助手建议的人工核对 UI |
| `people_memory_ui.js` | 交流与约定等私人记录 UI |
| `offline_card_ui.js` | 离线名片及扫码交互 |
| `v09_data_service.py` | 人物 UI 状态与本地持久化服务 |
| `GongPlaceFormatter.java` / `TestGongPlaceFormatter.java` | 地理编码结果的区县格式化及样例测试 |
| `test_people_assistant.py` | 人物助手服务测试 |

请勿向此分支提交个人资料、模型密钥、签名材料或私有规则。请阅读 [设计与状态说明](../docs/gong/README.md)。
