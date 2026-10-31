# 知人接入六爻本地容器 — 第一阶段（开发分支）

## 已实现
- 新增独立人物数据库 zhiren.sqlite3；不与原六爻 profile_store 直接合并或互相读取。
- 通过既有 127.0.0.1 会话、Host/Origin、X-App-Request 和幂等键保护 API。
- /zhiren 页面：分类、人物资料编辑、本地规则智能找人、活动邀请名单（默认全选、可撤销）、发布草稿、多名片轮播。
- 每条推荐都显示实际命中原因；当没有匹配证据时返回空列表。
- 保存后的草稿标记 not_sent，既无云端同步也不向任何人发送通知。
- skills/ 下提供知人及六爻的独立 SKILL.md，描述能力和数据边界。

## 未实现，不应误认为已上线
- 真正大模型检索、Agent 自主判断和多方代交流。
- 人像照片上传与加密图库、QR/vCard 名片交换、远程消息传输。
- 公共 Profile（主题、布局）、跨 Skill 全局事件总线和独立周报月报。
- 端到端通信、系统推送、权限细粒度审计、Android 真机验收。
- Android 安装包；需要重新打包 APK 后方可在设备中使用。

## 验证
先在本机执行：
  python -m unittest liuyao_app.test_zhiren

如果修改了前端 JS，按当前项目已有打包流程：
  cd android && npm ci && npm run build:web && cd ..
  python android/prepare.py
  cd android && ./gradlew assembleDebug

桌面或浏览器启动原程序后，从左侧“知人”入口进入，或访问同一运行端口的 /zhiren。

## 数据与安全
- 数据默认保存在原 APP data_directory 下的 zhiren.sqlite3。当前版是本地存储，不是已加密的数据仓库；应在设备锁定、加密存储和备份机制完善后再录入真实敏感资料。
- HTML 使用相同来源的接口及会话 cookie；页面遵循现有 CSP，不引入 CDN。
- 由于原六爻公开源码没有真实规则表，仍应使用原有私有加密规则包，不要将真实规则、口令、联系人或 API 密钥提交 Git。
- 此阶段不修改六爻排盘、规则引擎、模型密钥和历史数据库。
