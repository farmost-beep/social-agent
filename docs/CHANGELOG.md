# 版本日志

## 3.0.0 (2026-07-08) — Social-CLI 独立化

### 核心变更：解耦 Claude Code 依赖

v3.0 起，social-agent 升级为 **social-cli**，可独立于 Claude Code 运行。

#### 架构升级
- 新增 `src/llm/` 模块（LLM 抽象层）
  - `LLMClient` 抽象基类 + 5 类异常（LLMAuthError / LLMRateLimitError / LLMTimeoutError / LLMResponseError / LLMError）
  - `ClaudeClient`（Anthropic API 直连，无需 SDK）
  - `OpenAIClient`（OpenAI 兼容协议，支持 MiniMax / Azure OpenAI / 其他）
  - `Router` 单例工厂，根据配置自动选择 provider
- `src/ai.py` 改造
  - 优先调用 LLM 抽象层（HTTP API）
  - 失败降级到 `subprocess claude --print`（v2 兼容路径）
  - 公开 API 签名不变（draft_message / generate_reminder），向后兼容
- 新增 `social_cli/` 包
  - `cli.py` argparse 统一入口（status / todos / enrich / health / draft / config / chat / version）
  - `__main__.py` 支持 `python -m social_cli`
- `setup.py` 新增 `social` console_scripts 入口点
  - 保留 `social-agent` 旧命令（v2 兼容）
  - 双入口点共存

#### 新功能
- LLM provider 切换：CLI 命令 `social config show/providers`，环境变量 `LLM_ENGINE`
- `social chat <message>` 直接对话模式（无需启动 Claude Code）
- `social draft -m "上下文" -c 联系人` 独立拟稿
- 配置透明化：`social config show` 列出当前环境变量

#### 改进
- 测试覆盖率提升：v2.5 仅 15 个 → v3.0 共 76 个
  - `tests/test_llm.py`：25 个（抽象层 + Claude + OpenAI + Router）
  - `tests/test_ai.py`：14 个（mock LLMClient + subprocess 降级）
  - `tests/test_cli.py`：22 个（argparse + 各子命令 + 错误处理）
- 错误处理：失败返回友好字符串，不再抛异常中断
- 重试机制：`complete_with_retry()` 指数退避（1s/2s/4s）

#### 新增依赖
- `httpx>=0.24`（HTTP 客户端，用于直接调用 LLM API）

#### 破坏性变更
- **无 API 破坏**：所有公开函数签名保持兼容
- **行为变化**：v2 默认走 `claude --print`（subprocess）；v3 默认走 HTTP API（更可靠）

#### 迁移指南
- 见 `docs/MIGRATION.md`
- 升级命令：`pip install --upgrade -e .`
- 老用户无需修改任何调用代码

---

## 2.5.0 (规划中)

### P0 — 批量画像补全管道
- `enrich` 命令：AI 驱动的批量联系人画像补全
- 输入信号：姓名/备注/标签/记忆/群组归属 多源融合
- `--web` 模式：通过 DuckDuckGo 搜索获取联系人公开信息，注入提示词作为额外上下文（免费，无需 API Key）
- 搜索策略：从标签/备注/角色提取上下文关键词，构造查询，取前 3 条结果摘要
- 同一批次查询自动缓存，300ms 间隔防反爬
- 三级置信度：强证据(8-10)→写入relation+tags、中等(5-7)→追加notes、弱→跳过
- 保护规则：不覆盖已有relation、不删除notes、不改strength、tags只追加不覆写
- `--dry-run` 预览、`--batch` 批次控制、`--force` 重新处理、`--stats` 统计视图
- 补全日志 `data/enrichment_log.json`，每次操作可追溯

### P1 — 关系图谱
- 数据模型新增 `_connections` 字段（Connection 结构体）
- `connect` 命令添加双向连接，自动同步 B→A
- `connections <contact>` 查看个人关系网
- `find-path <A> <B>` 跨联系人路径查找（BFS）
- `scripts/graph.py` 可视化（支持 --contact ego 网络）
- 仪表盘集成：总连接数/密度/TOP5

### P1 — 群聊智能感知
- 数据模型新增 `_groups` 字段（群名数组）
- `list-groups` / `group-members` / `add-to-group` 命令
- `import-groups --from-contacts` 从 OCR 导入数据自动提取群归属
- 同群联系人自动打 `群友` 标签

### P2 — 互动信号自动采集
- `import-chat <file>` 微信聊天记录 .txt 导入
- `import-calls <file>` 通话记录 CSV 导入
- 按日期+联系人聚合，自动去重
- 不修改联系人数据，仅 append 时间线

### P2 — 关系健康分
- `health` 命令：综合评分(0-100)，四因子加权（recency 40% / depth 30% / layers 20% / events 10%）
- `health --fix` 列出需关注的关系（< 50 分）
- `health --ranking` 排行榜
- 四色等级：🟢健康(80+) / 🟡关注(50-79) / 🟠预警(20-49) / 🔴危险(0-19)
- 仪表盘集成：分布图 + 平均分 + 下降最快 TOP5
- 早间推送集成健康总览

### 演进原则补充
- 原则六（信号先行）、原则七（保守推理可追溯）、原则八（连接是增强非替代）

## 2.4.0 (2026-06-14)

### 新增
- 角色互动层数自动计算（SPEC 0.3）：6维度检测（职层/校层/组层/群层/合层/家层），自动添加角色x1/x2/x3标签
- add-contact 支持 --sub-relation 参数
- relation/role 字段统一：创建时同步设置，更新时自动同步
- 仪表盘增加🟡14天冷却预警（原仅🔴21天）

## 2.3.0 (2026-06-14)

### 新增
- 角色互动层数体系（0.3节）：职业层/校友层/组织层/社交层/合作层/家庭层
- 联系人标签系统同步角色层数（角色x1/x2/x3）

### 变更
- 社会角色框架（0.2）：引入社交价值公式
- 终极标尺：社交价值 = 对用户目标的贡献度

### 修复
- SPEC脱敏：移除个人数据

## 2.2.0 (2026-06-14)

### 新增
- 社会角色框架：社交关系=角色×角色互动
- 社交价值公式：我的角色×对方角色×双向互动
- 五项核心原则

## 2.1.0 (2026-06-14)

### 新增
- 终极标尺定义：社交价值 = 对幸福人生总体目标的贡献度

## 2.0.0 (2026-06-14)

### 变更
- **主版本变更**：强度定义从情感亲疏改为社交价值排序
- 删除血缘/生涯/场景纽带模型，替换为决策层/合作层/信息层

## 1.1.0 (2026-06-14)

### 新增
- 自动强度调整机制（基于时间线互动频率）
- note命令强度自提升（不超过4）
- adjust命令

## 1.0.0 (2026-06-14)

### 初始版本
- 定义设计理念、数据模型、操作规则
- 版本管理框架
