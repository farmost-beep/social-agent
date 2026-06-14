# 配置指南

## config.yaml

```yaml
# 数据存储路径
data_dir: "./data"

# AI模型配置
ai:
  engine: "claude"           # 可选: claude, openai
  model: "claude-sonnet-4-6"
  api_key_env: "ANTHROPIC_API_KEY"

# 微信推送配置（可选）
push:
  enabled: false
  channel: "wxpusher"
  app_token_env: "WX_PUSHER_TOKEN"

# 用户角色模板
roles_template: "./config/roles.yaml"
```

## 环境变量

| 变量 | 必须 | 说明 |
|:----|:----:|:----|
| `ANTHROPIC_API_KEY` | ✅ (使用Claude时) | Anthropic API密钥 |
| `OPENAI_API_KEY` | ✅ (使用OpenAI时) | OpenAI API密钥 |

## 数据目录

`data/` 目录结构：

```
data/
├── contacts.json      # 联系人库
├── timeline.json      # 时间线
├── todos.json         # 待办队列
└── wechat_ids.json    # 微信ID映射
```

首次使用请从 `data_template/` 复制空模板：

```bash
cp -r data_template/* data/
```

## AI引擎选择

### Claude（默认）
```yaml
ai:
  engine: "claude"
  model: "claude-sonnet-4-6"
```

### OpenAI
```yaml
ai:
  engine: "openai"  
  model: "gpt-4o"
```

## 微信推送配置

### cc-connect（默认）
```yaml
push:
  enabled: true
  channel: "cc-connect"
```
需安装 `cc-connect` 并配置本地 Webhook。
