# Android 工程

完整项目说明见仓库根目录 [`README.md`](../README.md)。

## 快速构建

环境：JDK 17、Python 3.12、Android SDK Platform 35、Build Tools 35.0.0。

```bash
# 在仓库根目录生成应用 payload
python android/prepare.py

# 构建调试 APK
cd android
./gradlew assembleDebug
```

Windows 使用 `.\gradlew.bat assembleDebug`。

修改 `liuyao_app/static/*.js` 后，先运行：

```bash
cd android
npm ci
npm run build:web
cd ..
python android/prepare.py
```

`build-web.mjs` 会生成兼容旧 WebView 的脚本并记录源码、输出摘要；`prepare.py` 会核对摘要，再生成确定性的 `app/src/main/assets/content.zip` 与 `content.sha256`。

公开 payload 不含真实规则表或编译规则。APK 首次启动后需在“规则”页面导入单独取得的 `.lyrules` 加密规则包，详见根目录 README。

## SDK 配置

在本机创建 `android/local.properties`：

```properties
sdk.dir=/path/to/Android/Sdk
```

此文件已被 Git 忽略，不能提交个人路径。

## 发布版本

发布签名只从环境变量读取：

- `LIUYAO_KEYSTORE`
- `LIUYAO_STORE_PASSWORD`
- `LIUYAO_KEY_ALIAS`（默认 `liuyao`）
- `LIUYAO_KEY_PASSWORD`（默认沿用仓库密码）

```bash
./gradlew -PseparateInstall=true assembleRelease
```

仓库不包含 Keystore、密码、已签名 APK 或真实 API 密钥。
