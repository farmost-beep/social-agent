# Social Agent

> A locally-run AI steward that automatically tracks "what happened recently" and "what to do next" across all your social relationships.

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0.3-blue.svg)](docs/CHANGELOG.md)

[中文文档](README.md)

## Installation

**pip (recommended)**

```bash
pip install social-agent
```

**npm**

```bash
npx @farmost/social-agent status
```

**One-line script**

```bash
bash <(curl -sL https://raw.githubusercontent.com/farmost-beep/social-agent/main/install.sh)
```

If you already have Claude Code configured (`~/.claude/settings.json`), no extra setup needed — the CLI reuses system LLM config. Otherwise, pick one:

```bash
# Claude (default, no engine setup needed)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export LLM_ENGINE=openai
export OPENAI_API_KEY=sk-...

# MiniMax
export LLM_ENGINE=openai
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
```

## Commands

```bash
social status                  # Contact status overview
social todos                   # Todo list
social advise                  # Who to contact + why + what to say
social draft -m "context" -c John  # AI draft message
social chat "message"          # Direct chat
social anchor                  # Goal anchoring (contacts ↔ six-dimension goals)
social outcomes                # Outcome tracking
social config show             # View config
```

## WeChat Integration

social-agent integrates deeply with WeChat in three ways:

### 1. WeChat Chat (Recommended)

Use [cc-connect](https://github.com/chenhg5/cc-connect) to bridge WeChat to the AI steward. cc-connect supports Feishu, Telegram, Slack, DingTalk, Discord, LINE, WeChat Work, personal WeChat, QQ, and more — managing multiple projects simultaneously.

```bash
# 1. Install (choose one)
npm install -g cc-connect          # npm
brew install cc-connect            # Homebrew
# Or download binary from GitHub Releases: https://github.com/chenhg5/cc-connect/releases

# 2. Configure personal WeChat (ilink, QR login)
cc-connect weixin setup --project my-project
# → Scan QR to confirm → token auto-written to ~/.cc-connect/config.toml

# 3. Install as system service (launchd auto-start)
cc-connect daemon install
cc-connect daemon status           # Check status

# 4. Verify: send a message in WeChat, cc-connect responds automatically
```

Already have an ilink token? Skip the QR scan:

```bash
cc-connect weixin bind --project my-project --token '<your_token>'
```

Minimal config.toml (run `cc-connect config example` for full reference):

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

Once bound, send a message to yourself in WeChat to trigger natural-language interaction:

| You say | AI does |
|:----|:-----|
| Note: chatted with John about project progress | Log timeline + extract todos |
| How's John doing lately | Query recent interactions + todos |
| Draft a message to John | AI draft → confirm to send |
| Who should I contact recently | List cooling relationships + suggestions |
| What to follow up on | List P0/P1 todos |

WeChat slash commands: `/help` · `/clear` · `/status` · `/model` · `/skills`

#### Conversation Examples

**Scenario 1: Log Interaction**
```
You: Note: had dinner with Wang yesterday, discussed industry summit partnership, he said he'll introduce the summit organizer next week

AI: ✓ Logged
  Contact: Wang Ming (Lao Wang)
  Date: 2026-07-11
  Summary: Industry summit partnership discussion, organizer intro
  Todos extracted:
    🔴 P0 Wang introduces summit organizer (waiting for his arrangement)
```

**Scenario 2: Query Relationship Status**
```
You: How's Lao Wang doing lately

AI: 📌 Wang Ming (Lao Wang) Relationship Status

  Recent interactions:
    07-11 Industry summit partnership discussion, organizer intro
    06-28 Attended industry salon together
    06-15 WeChat casual chat

  Todos (2 items):
    🔴 P0 Wang introduces summit organizer (waiting for his arrangement)
    🟡 P1 Summit registration confirmation (due 07-20)

  Relationship health score: 82/100 🟢
  Last contact: 1 day ago
```

**Scenario 3: AI Draft**
```
You: Draft a message to Lao Wang, ask about the summit organizer intro

AI: 📝 Draft (tone: friendly)

  Lao Wang, regarding the summit organizer intro we discussed, could you check when they might be available?
  No rush, take care of your stuff first, I'll work around your schedule.

  Reply "confirm" to send, or tell me what to change.
```

**Scenario 4: Who to Contact**
```
You: Who should I contact recently

AI: 💡 Suggested contacts this week (3 people)

  🔴 Zhang — 21 days no contact (last: project progress discussion)
     Suggested topic: whether Q3 budget plan needs adjustment
  🟡 Li — 18 days no contact (last: partnership discussion)
     Suggested topic: the tech proposal mentioned last time is ready, can sync
  🟡 Zhao — 16 days no contact (last: industry event meetup)
     Suggested topic: Q3 cooperation framework can move forward
```

**Scenario 5: Todo Follow-up**
```
You: What to follow up on

AI: 📋 Todo list (5 items)

  🔴 P0 Wang introduces summit organizer — waiting for his arrangement
  🔴 P0 Zhang project acceptance — due 07-15 (3 days left)
  🟡 P1 Summit registration confirmation — due 07-20
  🟡 P1 Send tech proposal to Li — due 07-18
  🟢 P2 Discuss Q3 cooperation with Zhao — no deadline
```

<details>
<summary><b>Alternative bridge: wechat-claude-code</b> (click to expand)</summary>

[wechat-claude-code](https://github.com/Wechat-ggGitHub/wechat-claude-code) is another WeChat bridge tool, focused solely on WeChat, sending via iLink API.

```bash
npx skills add Wechat-ggGitHub/wechat-claude-code   # Install bridge
cd ~/.claude/skills/wechat-claude-code
npm run setup            # Scan QR to bind WeChat
npm run daemon -- start  # Start daemon (auto-start on boot)
```

</details>

### 2. Scheduled Push Notifications

Automatically push reminders to WeChat via launchd/cron — no manual action needed:

| Time | Push content |
|:----|:-----|
| 08:57 | Morning briefing: todos, birthdays, cold relationship reminders |
| 19:57 | Evening review: today's interactions, health data |
| 1h before event | Advance reminder for timed schedules |

Schedule advance reminders (local cron, decoupled from Claude Code):

```bash
social remind --cron   # Print crontab setup
# Scans today's schedules every 15 min, pushes 1h advance reminder
*/15 7-22 * * * cd ~/.claude/skills/social-agent && python3 -m social_cli remind
```

### 3. Send Messages to Contacts

```bash
social send -c "John" -m "Long time no see, how are you?" --confirm  # Send
social wxid-bind John wxid_xxxxx@im.wechat                           # Bind WeChat ID
social send-check                                                    # Check push environment
social advise --push                                                 # Push weekly suggestions
```

Send priority: cc-connect bridge (requires wxid binding, most reliable) → AppleScript Mac WeChat control (fallback).

## Data

Local JSON storage, no cloud:

| File | Description |
|:----|:-----|
| `data/contacts.json` | Contact database |
| `data/timeline.json` | Interaction timeline |
| `data/todos.json` | Todo queue |

## Documentation

- [Design Spec](docs/SPEC.md) · [v4 Architecture](docs/SPEC_v4.md) · [Config Guide](docs/CONFIG.md)
- [Changelog](docs/CHANGELOG.md) · [Migration Guide](docs/MIGRATION.md)

## License

MIT
