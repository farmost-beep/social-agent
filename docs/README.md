# 社交关系AI管家

> 一个比你更记得住人情世故的AI管家。自动追踪所有社交关系中「最近干了什么」和「下一步该干什么」，帮你拟好消息，推到该去的地方。

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
# 1. 安装
git clone https://github.com/your-org/social-relationship-manager.git
cd social-relationship-manager
pip install -r requirements.txt

# 2. 配置
cp config/config.yaml config/config.local.yaml
# 编辑 config.local.yaml 设置数据目录和AI引擎

# 3. 初始化数据
cp -r data_template/* data/

# 4. 导入联系人
python src/cli.py add-contact <ID> --name "姓名" --role "角色"

# 5. 查看仪表盘
python src/cli.py dashboard
```

## 📖 使用指南

```bash
# 联系人管理
python src/cli.py add-contact <ID> --name NAME --role ROLE --tags TAGS --notes NOTES
python src/cli.py edit-contact <ID> --name NAME --strength N
python src/cli.py search QUERY --field name|tags|notes

# 互动与记忆
python src/cli.py log <CONTACT> <互动摘要>
python src/cli.py note <CONTACT> <记忆内容> --tags TAGS

# 查看状态
python src/cli.py status [CONTACT]
python src/cli.py dashboard
python src/cli.py birthdays --days 30

# 强度管理
python src/cli.py adjust       # 查看调整建议
python src/cli.py adjust --apply  # 执行调整

# AI消息拟稿
python src/cli.py draft <CONTACT> --tone 亲切|正式|简洁
python src/cli.py send <CONTACT> --tone 亲切
```

## 🧠 设计理念

参见 [docs/SPEC.md](docs/SPEC.md) 完整设计规约。

**核心逻辑链：**

```
用户目标 → 社交价值 → 角色×角色×互动 → 强度1-5 → 自动化维护
```

## 📁 项目结构

```
social-relationship-manager/
├── src/                    # 源代码
│   ├── cli.py             # 命令行入口
│   ├── engine.py          # 核心引擎
│   ├── ai.py              # AI拟稿
│   ├── push.py            # 推送模块
│   ├── agent.py           # Agent守护进程
│   └── intent.py          # 意图识别
├── config/
│   ├── config.yaml        # 配置模板
│   └── roles.yaml         # 角色模板
├── data/                   # 用户数据
├── docs/
│   ├── SPEC.md            # 设计规约
│   ├── CONFIG.md          # 配置指南
│   └── CHANGELOG.md       # 版本日志
├── requirements.txt
└── setup.py
```

## ⚙️ 配置

见 [docs/CONFIG.md](docs/CONFIG.md)

## 📄 许可证

Apache 2.0
