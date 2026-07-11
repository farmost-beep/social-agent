# 社交关系AI管家

> 本地运行的AI管家，自动追踪所有社交关系中「最近干了什么」和「下一步该干什么」。

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)](docs/CHANGELOG.md)

## 安装

```bash
pip install -e .

# 设置 API Key（三选一）
export ANTHROPIC_API_KEY=sk-ant-...                    # Claude（默认）
export OPENAI_API_KEY=sk-...                           # OpenAI
export OPENAI_API_KEY=... OPENAI_BASE_URL=https://api.minimaxi.com/v1  # MiniMax
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
