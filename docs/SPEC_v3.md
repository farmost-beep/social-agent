---
title: 社交关系AI管家 · 产品设计规约 v3.0
version: 3.0.0
updated: 2026-07-08
status: 生效
predecessor: docs/SPEC.md (v2.3.0)
---

# 社交关系AI管家 产品设计规约 (SPEC v3.0)

> **本规约定义 v3.0 的设计理念、数据模型、操作规则和架构演进。**
> §0-3 章节基础理论继承自 [SPEC v2.3](SPEC.md)，重点新增内容在 §9-12。

## 🎯 v3.0 核心变化

v3.0 是**架构级别升级**，核心是**解耦 Claude Code 依赖**：

| 维度 | v2.3 | v3.0 |
|:----|:----:|:----:|
| 大模型调用 | `subprocess claude --print` | **LLM 抽象层（HTTP API）** |
| 是否必须 Claude Code | ✅ 是 | ❌ 不需要 |
| CLI 入口 | `python3 src/social.py` | **`social` 全局命令** |
| 模型可切换 | ❌ 锁死 Claude | **Claude / OpenAI / MiniMax** |
| 安装方式 | 手动克隆 | **`pip install -e .`** |
| 测试覆盖 | 15 个 | **76 个** |
| 公开 Python API | 不变 | **不变（向后兼容）** |

---

## §0-3 基础理论（继承 v2.3）

> 以下章节基础理论**完全沿用 v2.3**，本文档不再重复展开。
> 详见 [SPEC.md (v2.3)](SPEC.md) 对应章节。

### §0 理论基础

包含：
- §0.1 关系强度的定义：社交价值
- §0.2 社会角色框架
- §0.3 角色互动层数
- §0.4 核心原则（5 条）

**关键公式**（v2.3 §0.2）：
```
社交价值 = Σ (我的角色A × 对方角色B × 双向互动力)
```

### §1 核心设计理念

- 以**人 + 关系**为核心（非通讯录）
- 统一数据源（不分散存储）
- 社交资源的定义

### §2 数据模型

```json
{
  "id": "唯一标识符",
  "name": "显示名称",
  "relation": "关系分类",
  "sub_relation": "子分类",
  "strength": 1-5,
  "tags": ["标签"],
  "platforms": { "weixin": "", "phone": "", "email": "" },
  "notes": "自由文本备注",
  "memories": [],
  "important_dates": [],
  "stage": "",
  "created": "创建日期"
}
```

### §3 操作规则

7 条核心规则（见 SKILL.md），其中关键 3 条：
1. **必须读 `contacts.json` 真实数据**（禁止从上下文猜）
2. **删除/取消待办必须用户确认**（AI 不得自行操作）
3. **时间冲突不自动取消**（同时保留，标注提醒）

**v3.0 新增规则**：
4. **大模型调用优先走 LLM 抽象层**（失败降级到 subprocess，见 §9.5）

---

## §9. v3.0 LLM 抽象层架构 🆕

### 9.1 设计目标

| 目标 | 解决方案 |
|:----|:--------|
| 摆脱 Claude Code 依赖 | 直接 HTTP 调用 LLM API |
| 支持多 provider | 抽象基类 + Provider 实现 |
| 错误处理统一 | 异常体系（5 类）|
| 可单测 | 接口设计允许 mock |
| 优雅降级 | 双路径调用（HTTP → subprocess）|

### 9.2 架构图

```
+-----------------------------------+
|  调用方                            |
|  (social_cli / ai.py / engine)    |
+-----------------+-----------------+
                  |
                  v
+-----------------------------------+
|  LLMClient（抽象基类）              |
|  + complete()                     |
|  + complete_with_retry()          |
+-----------------+-----------------+
                  |
        +---------+---------+
        |                   |
        v                   v
+----------------+  +-----------------+
| ClaudeClient   |  | OpenAIClient    |
| (Anthropic API)|  | (兼容协议)      |
+----------------+  +-----------------+
        |                   |
        v                   v
  api.anthropic.com   api.openai.com
                       api.minimaxi.com
                       (其他兼容服务)
```

### 9.3 模块结构

```
src/llm/
├── __init__.py    # 公开 API 导出
├── base.py        # LLMClient + 异常体系
├── claude.py      # ClaudeClient（Anthropic API）
├── openai.py      # OpenAIClient（兼容协议）
└── router.py      # Router（配置驱动 + 单例工厂）
```

### 9.4 异常体系

| 异常类 | 触发条件 | 重试策略 | HTTP 状态码 |
|:------|:--------|:--------|:-----------|
| `LLMAuthError` | API Key 无效/缺失 | **不重试** | 401 / 403 |
| `LLMRateLimitError` | 速率限制 | 指数退避 | 429 |
| `LLMTimeoutError` | 调用超时 | 重试 | 408 / 504 / 524 |
| `LLMResponseError` | 响应解析失败 | 重试 | 5xx / JSON 异常 |
| `LLMError`（基类）| 其他错误 | 不重试 | 其他 |

所有异常继承 `LLMError`，可统一捕获。

### 9.5 重试机制

```python
# base.py
def complete_with_retry(self, prompt, max_retries=2):
    """指数退避重试：1s → 2s → 4s"""
```

**重试规则**：
- ✅ 速率限制（429）→ 退避重试
- ✅ 超时 → 重试
- ✅ 服务端错误（5xx）→ 重试
- ❌ 认证失败（401/403）→ **不重试**
- ❌ 客户端错误（4xx 其他）→ **不重试**

### 9.6 Provider 接口

```python
class LLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """同步调用，返回完整文本"""
        pass
```

**接口要求**：
- 必须实现 `complete()`
- 可选重写 `complete_with_retry()`（默认基类提供）
- 不强制实现流式（v3.0 暂不需要）

### 9.7 Provider 注册表

```python
# router.py
_PROVIDERS: Dict[str, Type[LLMClient]] = {
    "claude": ClaudeClient,
    "openai": OpenAIClient,
    # 未来扩展：在此处添加
    # "minimax": MiniMaxClient,
    # "local_ollama": OllamaClient,
}
```

**扩展方式**：新增 provider 只需：
1. 继承 `LLMClient` 实现 `complete()`
2. 在 `_PROVIDERS` 注册
3. 配置文件中声明

### 9.8 配置优先级

```
config.local.yaml > config.yaml > 环境变量
```

**配置示例**（`config/config.yaml`）：
```yaml
ai:
  engine: "claude"            # claude / openai
  model: "claude-sonnet-4-6"
  api_key_env: "ANTHROPIC_API_KEY"
```

**环境变量**：
| 变量 | 用途 |
|:----|:-----|
| `LLM_ENGINE` | provider 选择 |
| `ANTHROPIC_API_KEY` | Claude 认证 |
| `ANTHROPIC_BASE_URL` | Claude 代理地址 |
| `OPENAI_API_KEY` | OpenAI / MiniMax 认证 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 |
| `OPENAI_MODEL` | OpenAI 模型名 |

### 9.9 双路径降级

`src/ai.py` 采用双路径调用，保证向后兼容：

```
draft_message(contact, context)
       │
       v
   _call_llm(prompt)
       │
       ├──路径 1：_call_via_llm_client()
       │        ↓ 失败
       │   返回 None
       │
       ├──路径 2：_call_via_subprocess()
       │        ↓ 失败
       │   返回 None
       │
       ↓
   返回 "" → 友好错误字符串
```

**关键承诺**：
- 公开 API 永不抛异常（始终返回字符串）
- v2 调用方零修改
- LLM 失败不中断业务流程

---

## §10. social_cli 统一 CLI 🆕

### 10.1 设计目标

| 目标 | 解决方案 |
|:----|:--------|
| 统一入口 | `social` 命令替代分散的 `python3 src/social.py` |
| 易安装 | `pip install -e .` 全局可用 |
| 向后兼容 | 保留 `social-agent` 别名 |
| 零新依赖 | argparse（标准库）|
| 可扩展 | 子命令独立函数 |

### 10.2 命令树

```
social [--version] [--help] <command> [args]

Commands:
  status              联系人状态总览
  todos               查看待办
  enrich              批量画像补全（v2.5 规划）
  health              关系健康分（v2.5 规划）
  draft               AI拟稿（独立模式）
  config              配置管理（show/set/providers）
  chat                与AI对话
  version             版本信息
```

### 10.3 完整子命令表

| 命令 | 用途 | v3.0 实现 |
|:----|:-----|:---------:|
| `social version` | 版本信息 | ✅ |
| `social status` | 联系人状态 | ✅（转发旧代码）|
| `social todos` | 待办列表 | ✅（转发旧代码）|
| `social enrich [--batch N] [--dry-run] [--force] [--stats] [--web]` | 画像补全 | ✅（转发旧代码）|
| `social health [contact] [--fix] [--ranking]` | 健康分 | ⚠️ 占位（v2.5 未实现）|
| `social draft -m "msg" [-c contact] [--tone 亲切/正式/简洁]` | AI 拟稿 | ✅ |
| `social config show` | 查看 LLM 配置 | ✅ |
| `social config providers` | 列出 provider | ✅ |
| `social config set <key> <value>` | 设置配置 | ⚠️ 提示用环境变量 |
| `social chat "msg"` | 直接对话 | ✅ |

### 10.4 双入口点

`setup.py` 注册两个 console_scripts 入口：

```python
entry_points={
    "console_scripts": [
        "social-agent=src.social:main",     # v2 兼容
        "social=social_cli.cli:main",        # v3 主命令
    ],
}
```

**用户选择**：
- 老用户：`social-agent status`（继续用）
- 新用户：`social status`（推荐）

### 10.5 错误处理契约

CLI 必须遵守的契约：

| 场景 | 行为 | 退出码 |
|:----|:----|:------:|
| 成功 | 打印结果 | 0 |
| 用户中断（Ctrl+C）| 优雅退出 | 130 |
| 通用异常 | 打印错误字符串 | 1 |
| argparse 校验失败 | 自动 exit | 2 |
| 未知子命令 | argparse 自动 exit | 2 |

**关键原则**：失败返回字符串，不抛异常中断。

### 10.6 模块结构

```
social_cli/
├── __init__.py    # 版本标识 (__version__ = "3.0.0")
├── __main__.py    # python -m social_cli 入口
└── cli.py         # argparse 框架 + 命令分发
```

### 10.7 扩展新子命令

3 步添加新子命令：

```python
# 1. 实现处理函数
def cmd_mynew(args) -> int:
    print("hello")
    return 0

# 2. 注册到 _COMMANDS
_COMMANDS["mynew"] = cmd_mynew

# 3. 在 build_parser() 添加子解析器
p = subparsers.add_parser("mynew", help="...")
p.add_argument("--foo", help="...")
```

---

## §11. v2.5 规划功能实现状态 🆕

> v2.5 SPEC（§8）规划了 5 个功能。本节记录 **v3.0 时的实现状态**。

### 11.1 实现状态总览

| 功能 | SPEC v2.5 优先级 | v3.0 状态 | 备注 |
|:----|:---------------|:---------|:-----|
| 批量画像补全 `enrich` | **P0** | ⚠️ **部分** | CLI 转发旧代码；DuckDuckGo `--web` 未实现 |
| 关系图谱 `connect/connections` | P1 | ❌ **未实现** | 数据模型 `_connections` 未加 |
| 群聊感知 `list-groups/group-members` | P1 | ❌ **未实现** | 数据模型 `_groups` 未加 |
| 互动信号采集 `import-chat/import-calls` | P2 | ❌ **未实现** | — |
| 关系健康分 `health` | P2 | ❌ **未实现** | CLI 仅占位 |

### 11.2 P0: enrich（部分实现）

**已实现**：
- ✅ CLI 子命令（`social enrich`）
- ✅ 转发到 `src/social.py cmd_enrich`
- ✅ 基础保护规则（不覆盖 relation、不删除 notes）

**未实现**：
- ❌ `--web` DuckDuckGo 集成
- ❌ `_enrich_version` 字段追踪
- ❌ `enrichment_log.json` 独立日志

**当前影响**：可用但功能不完整。

### 11.3 P1: 关系图谱（未实现）

**规划功能**：
```bash
social connect A B --type 同事
social connections 张三
social find-path 张三 李四
```

**数据模型**（规划中）：
```json
{
  "_connections": [
    {
      "target_id": "zhang-san-001",
      "type": "同事",
      "strength_estimate": 4,
      "notes": "同在邮储科技部工作",
      "created": "2026-06-14",
      "updated": "2026-06-14"
    }
  ]
}
```

**未实现原因**：数据真空（4,681 联系人中 `_connections` 全部为 0），需先有数据基础。

### 11.4 P1: 群聊感知（未实现）

**规划功能**：
```bash
social list-groups
social group-members "USTC校友上海群"
social add-to-group 张三 --group "群名"
```

**数据模型**（规划中）：
```json
{
  "_groups": ["USTC校友上海群", "上海金融同业群"]
}
```

**未实现原因**：微信群 API 接入复杂，本地 OCR 提取能力受限。

### 11.5 P2: 互动信号采集（未实现）

**规划功能**：
```bash
social import-chat <file.txt>
social import-calls <file.csv>
```

**未实现原因**：微信聊天记录导出有合规风险；用户主动说"记一下"成本已经很低。

### 11.6 P2: 关系健康分（未实现）

**规划功能**（SPEC v2.5 §8.6）：
```bash
social health              # 所有联系人
social health 张三          # 单个人
social health --fix        # 需关注的
social health --ranking    # 排行榜
```

**评分模型**（规划中）：
```
health_score = recency × 0.40 + depth × 0.30 + layers × 0.20 + events × 0.10
```

**未实现原因**：依赖 `_connections` / `_groups` 等数据基础，需先实现 P1。

### 11.7 后续实施优先级建议

| 建议顺序 | 功能 | 依赖 | 工作量预估 |
|:--------|:-----|:-----|:----------:|
| 1 | `health` 简化版（仅 recency + depth 两因子）| 无 | 1 周 |
| 2 | `enrich --web` DuckDuckGo 集成 | 无 | 1 周 |
| 3 | `_connections` 数据模型 + `connect` 命令 | 无 | 1 周 |
| 4 | `_groups` 数据模型 + 群感知 | 微信 API | 2 周 |
| 5 | `import-chat/calls` | 文件格式支持 | 2 周 |

---

## §12. v3.0 演进原则 🆕

在 v2.3 原则一-五基础上，新增：

### 原则六：信号先行
> 优先从已有数据中挖掘信息，再让用户补充——在要求用户输入之前，先问"系统已经知道什么"。

### 原则七：保守推理，可追溯
> AI 推理结果必须标注置信度，低置信度的只追加不覆盖，所有自动变更可回溯。

### 原则八：连接是关系的增强，不是替代
> 联系人之间的连接作为辅助信息存在，不用于替代强度计算或冷却检查。

### 原则九：抽象优于硬编码 🆕
> 新增依赖前，先问项目本身或标准库能否做到。LLM 抽象层是这一原则的体现——用 httpx 一行胜过第三方 SDK 一包。

### 原则十：兼容优于革命 🆕
> 重大架构变更时，保留旧入口作为兼容路径。v3.0 保留 `social-agent` 命令正是此原则。

### 原则十一：降级优于崩溃 🆕
> 任何外部依赖失败时，优先降级到兜底路径，不抛异常中断业务流程。`_call_via_subprocess` 兜底是这一原则的体现。

### 原则十二：测试优于文档 🆕
> 重要的契约必须有自动化测试覆盖。76 个测试是 v3.0 架构的"可执行文档"。

---

## §13. 版本与迁移

### 13.1 版本演进

| 版本 | 日期 | 主要变更 |
|:----|:----:|:--------|
| 2.0.0 | 2026-06-14 | 数据模型重构 |
| 2.1.0 | 2026-06-14 | 终极标尺定义 |
| 2.2.0 | 2026-06-14 | 社会角色框架 |
| 2.3.0 | 2026-06-14 | 角色互动层数体系 |
| 2.4.0 | 2026-06-14 | 角色层数自动计算 |
| 2.5.0 | 规划中 | 5 个新功能（enrich/connect/groups/import/health）|
| **3.0.0** | **2026-07-08** | **LLM 抽象层 + social_cli 统一入口** |

### 13.2 迁移路径

详见 [docs/MIGRATION.md](MIGRATION.md)：
- 数据格式零变更
- 公开 Python API 签名不变
- 老命令 `social-agent` 保留
- 30 秒完成升级：`pip install -e .`

### 13.3 Git Tag

```
v3.0.0  Social-CLI v3.0.0 — 解耦 Claude Code 独立化
```

---

## §14. 文档索引

| 文档 | 用途 |
|:-----|:-----|
| [SPEC.md (v2.3)](SPEC.md) | 前身规约（基础理论 0-3、自动化规则 7、v2.5 规划 8）|
| [SPEC_v3.md](SPEC_v3.md) | **本规约 v3.0**（§9-12 新增架构）|
| [README.md](../README.md) | 用户快速开始 + v3.0 章节 |
| [CHANGELOG.md](CHANGELOG.md) | 版本日志 |
| [MIGRATION.md](MIGRATION.md) | v2.5 → v3.0 迁移指南 |
| [CONFIG.md](CONFIG.md) | 配置文件详解 |
| [../SKILL.md](../SKILL.md) | Claude Code skill 触发规则 |

---

## §15. 核心代码索引（v3.0）

| 模块 | 路径 | 用途 |
|:----|:-----|:-----|
| LLM 抽象层 | `src/llm/base.py` | 抽象基类 + 异常 |
| Claude 实现 | `src/llm/claude.py` | Anthropic API |
| OpenAI 实现 | `src/llm/openai.py` | OpenAI 兼容协议 |
| Router | `src/llm/router.py` | 配置驱动路由 |
| AI 模块 | `src/ai.py` | 双路径调用 + 降级 |
| CLI 入口 | `social_cli/cli.py` | argparse 子命令 |
| CLI 测试 | `tests/test_cli.py` | 22 个用例 |
| LLM 测试 | `tests/test_llm.py` | 25 个用例 |
| AI 测试 | `tests/test_ai.py` | 14 个用例 |

---

**最后更新**：2026-07-08
**适用版本**：social-cli 3.0.0
**前身规约**：[SPEC.md (v2.3)](SPEC.md)