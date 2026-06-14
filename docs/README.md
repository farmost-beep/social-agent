# 社交关系AI管家

> 一个比你更记得住人情世故的AI管家。自动追踪所有社交关系中「最近干了什么」和「下一步该干什么」。

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

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

```bash
# 1. 克隆到 Claude Code skills 目录
cd ~/.claude/skills
git clone https://github.com/farmost-beep/social-agent.git
cd social-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据
cp -r data_template/* data/

# 4. 导入联系人
python3 src/social.py add-contact <ID> --name "姓名" --role "角色"

# 5. 查看仪表盘
python3 src/social.py dashboard
```

## 📖 使用指南

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

## 💬 微信交互

通过 cc-connect 桥接，可直接在微信中与管家对话：

| 你说 | 它做 |
|:----|:-----|
| `记一下：和张总聊了合作` | 记录互动，自动提取待办 |
| `张总最近咋样` | 查最近互动记录 |
| `最近该联系谁` | 列出14天+未联系的冷关系 |
| `最近有啥待办` | 列出待办事项 |
| `给李哥发消息` | 拟稿并推送（有微信ID则直发） |
| `李哥是李总` | 设别名，以后说"李哥"也能找到 |

## ⏰ 自动化推送

| 时段 | 内容 | 说明 |
|:---|:-----|:-----|
| ☀️ 09:00 | 早间概览 | 今日待办 + 冷却关系提醒 |
| 💡 14:00 | 午后建议 | 列出14天+未联系的冷关系 |
| 🌙 21:00 | 晚间回顾 | 今日互动总结 + 待办状态 |

## 🧠 设计理念

参见 [docs/SPEC.md](docs/SPEC.md) 完整设计规约。

**核心逻辑链：**

```
用户目标 → 社交价值 → 角色×角色×互动 → 强度1-5 → 自动化维护
```

## 📁 项目结构

```
social-agent/
├── SKILL.md               # 技能定义
├── README.md              # 使用说明
├── config/
│   ├── config.yaml        # 配置模板
│   └── roles.yaml         # 角色模板
├── src/
│   ├── social.py          # CLI入口
│   ├── agent.py           # Agent守护进程
│   ├── intent.py          # 意图识别
│   ├── web.py             # Web界面
│   ├── engine.py          # 核心引擎
│   ├── ai.py              # AI拟稿
│   ├── push.py            # 推送模块
│   └── cli.py             # 命令行入口（产品化版本）
├── data/                   # 用户数据
├── data_template/          # 空数据模板
├── docs/                   # 文档
├── tests/                  # 测试
├── requirements.txt
├── setup.py
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

- Claude Code（AI拟稿引擎）
- Python 3.9+
- 微信推送：cc-connect 桥接（可选）
- 关系图谱：matplotlib + networkx（可选）

## 📄 许可证

Apache 2.0
