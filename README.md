# 社交关系AI管家

> 本地运行的AI管家，自动追踪所有社交关系中「最近干了什么」和「下一步该干什么」。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0.3-blue.svg)](docs/CHANGELOG.md)

## 安装

**pip（推荐）**

```bash
pip install social-agent
```

**npm**

```bash
npx @farmost/social-agent status
```

**一键脚本**

```bash
bash <(curl -sL https://raw.githubusercontent.com/farmost-beep/social-agent/main/install.sh)
```

已配置 Claude Code（`~/.claude/settings.json`）的用户无需额外设置，CLI 自动复用系统 LLM 配置。未配置则三选一：

```bash
# Claude（默认，无需额外设置 engine）
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export LLM_ENGINE=openai
export OPENAI_API_KEY=sk-...

# MiniMax
export LLM_ENGINE=openai
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
```

## 命令

```bash
social status                  # 联系人状态总览
social todos                   # 待办列表
social advise                  # 该联系谁+为什么+聊什么
social draft -m "上下文" -c 张三  # AI 拟稿
social chat "消息"              # 直接对话
social anchor                  # 目标锚定（联系人↔六维目标）
social outcomes                # 兑现追踪
social config show             # 查看配置
```

## 微信使用

social-agent 与微信深度集成，三种方式：

### 1. 微信对话（推荐）

通过 [wechat-claude-code](https://github.com/Wechat-ggGitHub/wechat-claude-code) 桥接，在微信中直接与 AI 管家对话：

```bash
npx skills add Wechat-ggGitHub/wechat-claude-code   # 安装桥接
cd ~/.claude/skills/wechat-claude-code
npm run setup          # 扫码绑定微信
npm run daemon -- start  # 启动守护进程（开机自启）
```

绑定后，在微信中给自己发消息即可触发，自然语言交互：

| 你说 | AI 做 |
|:----|:-----|
| 记一下：和张总聊了项目进展 | 记录时间线 + 提取待办 |
| 张总最近咋样 | 查询最近互动 + 待办 |
| 给张总拟条消息 | AI 拟稿 → 确认后发送 |
| 最近该联系谁 | 列出冷却关系 + 建议 |
| 最近有啥要跟进的 | 列出 P0/P1 待办 |

微信端斜杠命令：`/help` · `/clear` · `/status` · `/model` · `/skills`

#### 对话示例

**场景1：记录互动**
```
你：记一下：昨天和老王吃饭，聊了行业峰会合作的事，他说下周引荐峰会主办方给我

AI：✓ 已记录
  联系人：王明（老王）
  时间：2026-07-11
  摘要：行业峰会合作交流，引荐主办方
  待办已提取：
    🔴 P0 老王引荐峰会主办方（等他安排）
```

**场景2：查询关系状态**
```
你：老王最近咋样

AI：📌 王明（老王）关系状态

  最近互动：
    07-11 行业峰会合作交流，引荐主办方
    06-28 一起参加行业沙龙
    06-15 微信闲聊

  待办 2 项：
    🔴 P0 老王引荐峰会主办方（等他安排）
    🟡 P1 峰会报名确认（截止 07-20）

  关系健康分：82/100 🟢
  上次联系：1天前
```

**场景3：AI 拟稿**
```
你：给老王拟条消息，问下峰会主办方引荐的事

AI：📝 草稿（语气：亲切）

  老王，上次聊的峰会主办方引荐的事，方便的话帮我问问什么时候有空？
  不着急，你先忙，我随时配合你的时间。

  发送回复"确认"即可发出，或告诉我要改哪里。
```

**场景4：该联系谁**
```
你：最近该联系谁

AI：💡 本周建议联系（3人）

  🔴 张总 — 21天未联系（上次：项目进展沟通）
     建议聊：新季度预算方案是否需要调整
  🟡 李总 — 18天未联系（上次：合作洽谈）
     建议聊：上次提到的技术方案已出，可同步
  🟡 赵总 — 16天未联系（上次：行业活动碰面）
     建议聊：Q3合作框架可以推进了
```

**场景5：待办跟进**
```
你：最近有啥要跟进的

AI：📋 待办列表（5项）

  🔴 P0 老王引荐峰会主办方 — 等他安排
  🔴 P0 张总项目验收 — 截止 07-15（还剩3天）
  🟡 P1 峰会报名确认 — 截止 07-20
  🟡 P1 给李总发技术方案 — 截止 07-18
  🟢 P2 约赵总聊Q3合作 — 无截止
```

<details>
<summary><b>备选桥接：cc-connect</b>（点击展开）</summary>

[cc-connect](https://github.com/chenhg5/cc-connect) 是另一款桥接工具，支持飞书/Telegram/Slack/钉钉/Discord/LINE/企业微信/个人微信/QQ 等多平台，可同时管理多个项目。social-agent 配置中已将其列为默认 push channel（见 `docs/CONFIG.md`）。

```bash
# 1. 安装（三选一）
npm install -g cc-connect          # npm
brew install cc-connect            # Homebrew
# 或从 GitHub Releases 下载二进制: https://github.com/chenhg5/cc-connect/releases

# 2. 配置个人微信（ilink，扫码登录）
cc-connect weixin setup --project my-project
# → 扫码确认 → token 自动写入 ~/.cc-connect/config.toml

# 3. 安装为系统服务（launchd 开机自启）
cc-connect daemon install
cc-connect daemon status           # 查看运行状态

# 4. 验证：在微信中发一条消息，cc-connect 自动响应
```

已有 ilink token 时可跳过扫码：

```bash
cc-connect weixin bind --project my-project --token '<your_token>'
```

config.toml 最小配置（完整示例运行 `cc-connect config example`）：

```toml
[[projects]]
name = "my-project"

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/path/to/your/project"

[[projects.platforms]]
type = "weixin"

[projects.platforms.options]
base_url = "https://ilinkai.weixin.qq.com"
token = "<your_ilink_token>"
```

</details>

### 2. 自动定时推送

通过 launchd/cron 自动推送提醒到微信，无需主动操作：

| 时段 | 推送内容 |
|:----|:-----|
| 08:57 | 晨间概览：待办、生日、冷关系提醒 |
| 19:57 | 晚间回顾：今日互动记录、健康数据 |
| 日程前 1h | 带时间标注的日程提前提醒 |

日程提前提醒（本地 cron 调度，解耦 Claude Code）：

```bash
social remind --cron   # 打印 crontab 接入配置
# 每15分钟扫描今日日程，提前1小时推送
*/15 7-22 * * * cd ~/.claude/skills/social-agent && python3 -m social_cli remind
```

### 3. 主动发消息给联系人

```bash
social send -c "张三" -m "好久没联系，最近怎么样？" --confirm  # 发送
social wxid-bind 张三 wxid_xxxxx@im.wechat                    # 绑定微信ID
social send-check                                            # 检查推送环境
social advise --push                                         # 本周建议推送
```

发送优先级：wechat-claude-code 桥接（需绑定 wxid，最可靠）→ AppleScript 控制 Mac 微信（备用）。

## 数据

本地 JSON 存储，不上云：

| 文件 | 说明 |
|:----|:-----|
| `data/contacts.json` | 联系人库 |
| `data/timeline.json` | 互动时间线 |
| `data/todos.json` | 待办队列 |

## 文档

- [设计规约](docs/SPEC.md) · [v4 架构](docs/SPEC_v4.md) · [配置指南](docs/CONFIG.md)
- [版本日志](docs/CHANGELOG.md) · [迁移指南](docs/MIGRATION.md)

## 许可证

MIT
