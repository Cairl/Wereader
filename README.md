# 微信读书自动阅读

微信读书网页版阅读模拟工具

## 功能概述

* 模拟阅读行为，累计阅读时常
* 每日定时执行，无需本地启动
* 自动推送日志，支持多方渠道

## 使用步骤

### 获取信息（必须）

1. 使用浏览器登录微信读书网页版
2. 打开开发者工具并进入 **Network** 面板
3. 找到 `read` 接口请求
4. 右键该请求，复制为 **cURL (bash)** 格式

### 添加账号（必须）

1. Fork 本仓库
2. 进入 **Settings → Secrets**
3. 新建变量 `WXREAD_CURL_BASH`，填入前面复制的内容

### 推送通知（可选）

添加以下 Secret 可启用消息推送：

| 名称 | 值 |
| - | - |
| `PUSH_PUSHPLUS_TOKEN` | PushPlus 令牌 |
| `PUSH_WXPUSHER_TOKEN` | WxPusher 令牌 |
| `PUSH_TELEGRAM_TOKEN` | Telegram 机器人令牌 |
| `PUSH_TELEGRAM_CHAT_ID` | Telegram 会话 ID |
| `PUSH_SERVERCHAN_SENDKEY` | ServerChan 发送密钥 |

### 阅读时长（可选）

在 **Variables** 中添加 `READ_MINUTES`，可修改每日目标阅读时长（默认 60 分钟）

### 运行时间（可选）

GitHub Action 默认每日 02:00 自动执行，如需调整可修改 `.github/workflows/deploy.yml` 中的正则表达式

## 免责声明

本项目仅用于学习与技术研究，使用者应自行遵守相关法律法规及平台规则，由此产生的任何后果与项目作者无关。

