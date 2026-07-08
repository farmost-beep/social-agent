# Social-CLI v3.0 迁移指南

> 从 social-agent v2.5 → social-cli v3.0 的迁移说明
> 升级日期：2026-07-08

---

## 🎯 一句话总结

**v3.0 不破坏任何 v2.5 的代码或数据**，只需要重新安装包，老命令继续可用。

---

## ✅ 兼容性矩阵

| 项目 | v2.5 | v3.0 | 兼容？ |
|:----|:----:|:----:|:-----:|
| 数据格式（contacts.json 等）| ✅ | ✅ 不变 | ✅ 完全兼容 |
| 公开 Python API | `ai.draft_message()` 等 | 同名同签名 | ✅ 完全兼容 |
| `social-agent` 命令 | ✅ 主命令 | ✅ 保留为别名 | ✅ 完全兼容 |
| `python3 src/social.py` | ✅ | ✅ 仍可用 | ✅ 完全兼容 |
| 配置文件 `config.yaml` | ✅ | ✅ 兼容 | ✅ 完全兼容 |
| **新增** `social` 命令 | ❌ | ✅ 主命令 | 🆕 新增 |
| **新增** 独立运行（无 Claude Code）| ❌ | ✅ | 🆕 新增 |
| **新增** LLM provider 切换 | ❌ | ✅ | 🆕 新增 |

**结论**：升级零风险，老用户完全不需要修改任何代码。

---

## 📦 升级步骤

### 步骤 1：拉取新代码

```bash
cd ~/.claude/skills/social-agent
git pull
```

### 步骤 2：重新安装包

```bash
pip install --break-system-packages -e .
```

### 步骤 3：验证

```bash
# 验证全局命令可用
social version

# 验证老命令仍可用
social-agent status

# 验证数据未损坏
python3 src/social.py dashboard
```

**总耗时**：约 30 秒。

---

## 🆕 启用 v3.0 新能力（可选）

### 新能力 1：脱离 Claude Code 独立运行

如果你只想用 CLI 工具，不再需要在 Claude Code 里操作：

```bash
# 设置 API Key（任选一个）
export ANTHROPIC_API_KEY=sk-ant-...
# 或
export OPENAI_API_KEY=sk-...

# 直接用
social status
social draft -m "上周见过" -c 张三
```

### 新能力 2：切换 LLM Provider

```bash
# 默认 Claude（无需配置环境变量，自动从 ANTHROPIC_API_KEY 读）
social config show

# 切到 OpenAI
export LLM_ENGINE=openai
export OPENAI_API_KEY=sk-...

# 切到 MiniMax（通过 OpenAI 兼容协议）
export LLM_ENGINE=openai
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
export OPENAI_MODEL=MiniMax-Text-01
export OPENAI_API_KEY=...

# 验证
social config show
social chat "hello"
```

### 新能力 3：直接对话模式

```bash
social chat "帮我写一段感谢张总的微信消息"
```

无需启动 Claude Code。

---

## 🔄 命令映射

### 完全兼容（无需修改）

| v2.5 命令 | v3.0 等价命令 |
|:---------|:------------|
| `python3 src/social.py status` | `social status` 或 `social-agent status` |
| `python3 src/social.py dashboard` | `social-agent dashboard` |
| `python3 src/social.py todos` | `social-agent todos` |
| `python3 src/social.py add-contact X --name "Y"` | `social-agent add-contact X --name "Y"` |

### 新增命令

| v3.0 命令 | 用途 |
|:---------|:-----|
| `social version` | 查看版本 |
| `social config show` | 查看 LLM 配置 |
| `social config providers` | 列出可用 LLM |
| `social chat "msg"` | 与 AI 对话（无需启动 Claude Code）|
| `social draft -m "上下文"` | AI 拟稿（独立模式）|

---

## ⚙️ 配置变化

### 新增环境变量

| 变量 | 用途 | 默认 |
|:----|:-----|:----:|
| `LLM_ENGINE` | 选择 provider（claude/openai）| claude |
| `ANTHROPIC_BASE_URL` | Claude API 代理地址 | api.anthropic.com |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | api.openai.com/v1 |

### 配置文件

`config/config.yaml` 的 `ai` 段可指定 provider：

```yaml
ai:
  engine: "openai"             # claude 或 openai
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"  # 环境变量名
```

**注意**：v3.0 推荐用环境变量管理 API Key，配置文件只放非敏感信息。

---

## 🚨 常见问题

### Q1：升级后 `social` 命令找不到？

**原因**：未执行 `pip install -e .` 或 PATH 未更新。

**解决**：
```bash
cd social-agent
pip install --break-system-packages -e .
which social    # 应该是 /opt/homebrew/bin/social 或类似
```

### Q2：升级后 `social-agent` 命令报错？

**原因**：旧 v2.5 包未卸载。

**解决**：
```bash
pip uninstall social-agent
pip install --break-system-packages -e .
```

### Q3：API Key 在哪里设置？

**v3.0 推荐方式**：环境变量
```bash
# 加到 ~/.zshrc 或 ~/.bash_profile 永久生效
export ANTHROPIC_API_KEY=sk-ant-...
```

### Q4：能否继续用 subprocess `claude --print`？

**可以**。v3.0 改造了 `ai.py`，但保留了 subprocess 兜底：
- 主路径：HTTP API（更可靠）
- 兜底路径：`claude --print`（v2 兼容）

只要 LLMClient 调用失败，自动降级到 subprocess。

### Q5：测试覆盖变了多少？

| 版本 | 测试数 |
|:----|:-----:|
| v2.5 | 15 |
| v3.0 | **76**（+25 LLM + 14 AI + 22 CLI）|

### Q6：数据会被覆盖吗？

**不会**。`data/contacts.json`、`data/timeline.json` 等所有用户数据**完全保留**。

---

## 🎓 推荐升级路径

### 保守用户（最稳）
1. `git pull && pip install -e .`
2. 继续用 `social-agent` 命令
3. 不主动切换 LLM provider
4. **风险：零**

### 进取用户（尝鲜）
1. 同上
2. 配置 `LLM_ENGINE` 切换到 OpenAI 或 MiniMax
3. 尝试 `social chat` 直接对话
4. 遇到问题回退到 `social-agent`

### 高级用户（完整迁移）
1. 卸载旧版：`pip uninstall social-agent`
2. 重新安装：`pip install -e .`
3. 全部命令用 `social`（替代 `social-agent`）
4. 配置自定义 LLM provider

---

## 📞 遇到问题？

1. 查看 [docs/CHANGELOG.md](CHANGELOG.md) 完整变更日志
2. 查看 [docs/SPEC.md](SPEC.md) 设计规约
3. 跑测试验证：`python3 -m unittest tests.test_llm tests.test_ai tests.test_cli`

---

**最后更新**：2026-07-08
**适用版本**：social-agent 2.5.x → social-cli 3.0.0