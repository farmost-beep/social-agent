# 社交关系AI管家

> 一个本地运行的AI管家，自动追踪所有社交关系中「最近干了什么」和「下一步该干什么」。
> 一个比你更记得住人情世故的AI管家。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](docs/CHANGELOG.md)

## 🆕 v3.0 重大更新：Social-CLI 独立化

从 v3.0 起，social-agent **不再依赖 Claude Code**，可作为独立 CLI 工具直接运行。

### 核心变化

| 维度 | v2.5 | v3.0 |
|:----|:----:|:----:|
| 是否必须 Claude Code | ✅ 是 | ❌ 不需要 |
| 大模型可切换 | ❌ 仅 Claude | ✅ Claude / OpenAI / MiniMax |
| 安装方式 | 手动克隆 | `pip install -e .` |
| CLI 入口 | `python3 src/social.py` | `social`（全局命令）|
| 测试覆盖 | 15 个 | **76 个** |

### 快速体验 v3.0

```bash
# 1. 安装
cd social-agent/
pip install --break-system-packages -e .

# 2. 设置 API Key（二选一）
export ANTHROPIC_API_KEY=sk-ant-...        # Claude
# 或
export OPENAI_API_KEY=sk-...               # OpenAI / MiniMax
export OPENAI_BASE_URL=https://api.minimaxi.com/v1  # MiniMax

# 3. 试用
social version
social config show
social chat "你好"
social draft -m "上周见过张总聊项目" -c 张三
```

### 切换 LLM Provider

```bash
# 用 Claude（默认）
export LLM_ENGINE=claude
export ANTHROPIC_API_KEY=sk-ant-...

# 切到 OpenAI
export LLM_ENGINE=openai
export OPENAI_API_KEY=sk-...

# 切到 MiniMax
export LLM_ENGINE=openai
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
export OPENAI_MODEL=MiniMax-Text-01
export OPENAI_API_KEY=...
```

详见 [docs/MIGRATION.md](docs/MIGRATION.md)

## ✨ 功能

| 功能 | 说明 |
|:----|:-----|
| 📇 **联系人管理** | 结构化存储联系人，支持标签/记忆/强度分级 |
| 📝 **互动记录** | 记录每次交流，自动提取待办事项 |
| 📊 **关系强度** | 基于社交价值的 1-5 级强度，自动动态调整 |
| 🎂 **生日提醒** | 自动从备注中提取生日，到期提醒 |
| 🤖 **AI拟稿** | 根据互动历史生成微信消息草稿 |
| 📋 **待办管理** | 自动生成跟进待办，P0/P1 优先级 |
| 🚨 **冷却预警** | 14天/21天未联系自动提醒 |
| 🔄 **自动调整** | 基于互动频率自动建议强度升降 |

## 🚀 快速开始

### pip 安装（v3.0 推荐） 🆕

```bash
# 1. 进入项目目录
cd ~/.claude/skills/social-agent

# 2. pip 安装（开发模式）
pip install --break-system-packages -e .

# 3. 设置 API Key（二选一）
export ANTHROPIC_API_KEY=sk-ant-...        # Claude
# 或
export OPENAI_API_KEY=sk-...               # OpenAI / MiniMax

# 4. 试用
social version
social status
```

### 一键脚本安装（v2 兼容）

```bash
bash <(curl -sL https://raw.githubusercontent.com/farmost-beep/social-agent/main/install.sh)
```

### npm 安装（v2 兼容）

```bash
npx social-agent dashboard
```

首次运行自动安装 Python 依赖和初始化数据。

### 手动安装（v2 兼容）

```bash
# 1. 克隆到 Claude Code skills 目录
cd ~/.claude/skills
git clone https://github.com/farmost-beep/social-agent.git
cd social-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化空数据
cp -r data_template/* data/

# 4. 导入第一个联系人
python3 src/social.py add-contact <ID> --name "姓名" --role "角色"

# 5. 查看仪表盘
python3 src/social.py dashboard
```

## 💬 使用方式

### 方式一：微信里跟机器人聊（推荐）

桥接守护进程在后台运行，直接在微信里发消息：

| 你说 | 它做 |
|:----|:-----|
| `记一下：和张总聊了合作` | 记录互动，自动提取待办 |
| `张总最近咋样` | 查最近互动记录 |
| `最近该联系谁` | 列出14天+未联系的冷关系 |
| `最近有啥待办` | 列出待办事项 |
| `多少联系人` | 返回联系人实时统计 |
| `给李哥发消息` | 拟稿并推送（有微信ID则直发） |
| `李哥是李总` | 设别名，以后说"李哥"也能找到 |

### 方式二：Claude Code 对话直接用

直接跟 Claude 说上述指令，AI 读取本地 JSON 返回实时数据。

### 方式三：命令行

#### v3.0 新统一命令（推荐） 🆕

```bash
# 全局可用（pip install -e . 之后）
social version                       # 查看版本
social status                        # 联系人状态
social todos                         # 待办列表
social config show                   # 查看 LLM 配置

# AI 拟稿（无需启动 Claude Code）
social draft -m "上周见过张总聊项目" -c 张三
social draft -m "给李哥拜个早年" -c 李哥 --tone 正式

# 与 AI 对话
social chat "你好"

# 守护进程
python3 src/agent.py                  # 单次检查
python3 src/agent.py --daemon         # 后台运行
python3 src/agent.py --chat "消息"    # 自然语言交互
```

#### v2 兼容命令（仍可用）

```bash
# 联系人管理
python3 src/social.py add-contact <ID> --name NAME --role ROLE --tags TAGS --notes NOTES
python3 src/social.py edit-contact <ID> --name NAME --strength N
python3 src/social.py search QUERY --field name|tags|notes

# 互动与记忆
python3 src/social.py log <CONTACT> <互动摘要>
python3 src/social.py note <CONTACT> <记忆内容> --tags TAGS

# 查看状态
python3 src/social.py status [CONTACT]
python3 src/social.py dashboard
python3 src/social.py birthdays --days 30

# 强度管理
python3 src/social.py adjust         # 查看调整建议
python3 src/social.py adjust --apply  # 执行调整
python3 src/social.py check           # 检查14天+未联系的关系

# AI消息拟稿
python3 src/social.py draft <CONTACT> --tone 亲切|正式|简洁
python3 src/social.py send <CONTACT> --tone 亲切
```

## ⏰ 自动化推送

| 时段 | 内容 | 说明 |
|:---|:-----|:-----|
| ☀️ 09:00 | 早间概览 | 今日待办 + 冷却关系提醒 |
| 💡 14:00 | 午后建议 | 列出14天+未联系的冷关系 |
| 🌙 21:00 | 晚间回顾 | 今日互动总结 + 待办状态 |

## 🧠 高级功能

### 别名系统

不用记全名，随时设别名：

```
李哥是李总
→ 以后说"李哥"也能找到李总
```

### 微信直发

存好联系人的内部微信ID后，消息直接发到对方微信：

```
李总的微信ID是wxid_xxxxxxxxxxxx@im.wechat
→ 以后"给李总发消息"直接推送到对方微信
```

### 关系图谱

可视化所有联系人按关系分类，节点大小代表关系强度。图谱生成脚本见仓库 backup 目录。

## 📖 命令一览

### v3.0 新统一命令（推荐） 🆕

`social` 是 v3.0 起的统一 CLI 入口（pip install -e . 后全局可用）：

| 命令 | 说明 |
|:----|:-----|
| `social version` | 查看版本信息 |
| `social status` | 联系人状态总览 |
| `social todos` | 待办列表 |
| `social draft -m "上下文"` | AI 拟稿（独立模式，无需启动 Claude Code）|
| `social chat "msg"` | 直接与 AI 对话 |
| `social config show` | 查看 LLM 配置 |
| `social config providers` | 列出可用 LLM providers |
| `social enrich --batch 50` | 批量画像补全（v2.5 规划）|
| `social health` | 关系健康分（v2.5 规划）|

### v2 兼容命令（仍可用）

| 命令 | 说明 |
|:----|:-----|
| `social-agent status` | 查看联系人状态或时间线 |
| `social-agent dashboard` | 全局仪表盘 |
| `social-agent add-contact` | 添加联系人 |
| `social-agent edit-contact` | 编辑联系人信息 |
| `social-agent search` | 搜索联系人 |
| `social-agent log` | 记录互动，自动提取待办 |
| `social-agent note` | 添加结构化记忆 |
| `social-agent todos` | 查看待办列表 |
| `social-agent done` | 完成待办 |
| `social-agent draft` | AI 拟稿，支持语气调节 |
| `social-agent send` | 拟稿并推送到微信 |
| `social-agent check` | 检查14天+未联系的关系 |
| `social-agent adjust` | 查看/执行强度调整建议 |
| `social-agent birthdays` | 查看近期生日 |

## 🧠 设计理念

参见 [docs/SPEC.md](docs/SPEC.md) 完整设计规约。

**核心逻辑链：**

```
用户目标 → 社交价值 → 角色×角色×互动 → 强度1-5 → 自动化维护
```

## 📁 项目结构

```
social-agent/
├── SKILL.md               # Claude Code 技能定义
├── README.md              # 本文件
├── config/
│   └── config.yaml        # 配置模板
├── src/                   # Python 源码（v2 兼容）
│   ├── social.py          # CLI入口（social-agent 命令）
│   ├── agent.py           # 守护进程
│   ├── engine.py          # 核心引擎
│   ├── ai.py              # AI拟稿（v3 改造：双路径调用）
│   ├── llm/               # ★ v3 新增：LLM 抽象层
│   │   ├── base.py        # LLMClient 基类 + 异常体系
│   │   ├── claude.py      # Anthropic API 直连
│   │   ├── openai.py      # OpenAI 兼容（含 MiniMax）
│   │   └── router.py      # 配置驱动路由
│   ├── push.py            # 推送模块
│   └── web.py             # Web界面
├── social_cli/            # ★ v3 新增：统一 CLI 入口
│   ├── __init__.py
│   ├── __main__.py        # python -m social_cli
│   └── cli.py             # argparse 子命令
├── data/                   # 用户数据（本地，不上云）
├── data_template/          # 空数据模板
├── docs/                   # 文档
│   ├── SPEC.md            # 设计规约
│   ├── CONFIG.md          # 配置指南
│   ├── CHANGELOG.md       # 版本日志
│   └── MIGRATION.md       # ★ v3 新增：迁移指南
├── tests/                  # 测试（v3 共 76 个）
│   ├── test_engine.py     # 引擎核心（15）
│   ├── test_llm.py        # ★ v3 新增（25）
│   ├── test_ai.py         # ★ v3 新增（14）
│   └── test_cli.py        # ★ v3 新增（22）
├── install.sh             # 一键安装脚本
├── requirements.txt
├── setup.py               # ★ v3 更新：双入口点
└── LICENSE
```

## ⚙️ 配置

见 [docs/CONFIG.md](docs/CONFIG.md)

## 📁 数据文件

| 文件 | 说明 |
|:----|:-----|
| `data/contacts.json` | 联系人库 |
| `data/timeline.json` | 互动时间线 |
| `data/todos.json` | 待办队列 |
| `data/wechat_ids.json` | 微信内部ID映射 |

## 🖇️ 依赖

**核心依赖（必需）：**
- Python 3.9+
- httpx ≥ 0.24（v3.0 LLM 抽象层）
- pyyaml ≥ 6.0

**LLM Provider（至少一个）：**
- Claude：设置 `ANTHROPIC_API_KEY` 环境变量
- OpenAI / MiniMax / 其他：设置 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 环境变量

**可选依赖：**
- ~~Claude Code（v3.0 起不再必需，可作为 LLM Client 的兼容兜底）~~
- 微信推送：cc-connect 桥接
- 关系图谱：matplotlib + networkx
- Web 界面：flask ≥ 2.0（`pip install -e .[web]`）

## 📄 许可证

MIT
