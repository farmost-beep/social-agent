# 版本日志

## 4.0.0 (规划生效 2026-07-10，阶段2 落地 2026-07-10) — 初心回归：从温度计到参谋

规约见 `docs/SPEC_v4.md`（§16-22），2026-07-10 确认生效，按五阶段实施。

### 主线（三支柱）
- **目标锚定**：core 层联系人新增 `leverage` 字段（goals/how/direction/confirmed），关联用户六维目标（事业/投资/家庭/健康/AI能力/知识）；新命令 `social anchor`。逐人确认，不批量设定
- **建议引擎**：新命令 `social advise`，输出"联系谁+为什么+聊什么"三元组，每周 3-5 条封顶；每周一晨间周推经营简报
- **兑现追踪**：timeline 新增 `type=outcome` 成果记录（含 goal 关联）；新命令 `social outcomes`。只记录不算 ROI

### 阶段2 落地（2026-07-10，目标锚定）

**新功能**：
- **`config/goals.yaml`**：六维目标框架配置（事业/投资/家庭/健康/AI能力/知识），支持 `goals.local.yaml` 覆盖；`engine.load_goals()` 读取，文件缺失时回退默认六维
- **`leverage` 字段**：直接存入 `contacts.json` 联系人对象（与 tags/notes 同级）
  - `engine.set_leverage()` / `get_leverage()` / `list_unanchored()` / `list_anchored()` / `anchor_stats()`
  - `confirmed` 为空 = 仅 AI 建议未生效；`list_unanchored` 把这类视为待锚定（严格区分建议与确认）
- **`social anchor` 三态命令**：
  - `social anchor` —— 交互式批量锚定（默认 batch=5，按 strength 降序+未锚定优先；`[y]确认 [n]跳过 [e]编辑 [q]退出`）
  - `social anchor <contact>` —— 单人锚定（显示 AI 建议→确认/编辑/跳过）
  - `social anchor --stats` —— 进度统计（已锚定/待锚定/按强度/按目标维度/按 direction 分布）
  - `--batch N` / `--min-strength S` / `--all` / `--confirm`（跳过交互直接写入）/ `--dry-run` / `--force`（强制锚定 reserve 或重新锚定已锚定）
- **`ai.suggest_leverage()`**：复用 `_call_llm`，输入联系人 timeline+tags+role+notes，输出 `{goals, how, direction}` JSON；失败降级为基于 tags/relation 的规则推断（保证离线可用）

**实施偏差（相对 SPEC v4 §18.3 草案措辞，均已回写规约 §18.4）**：
- `leverage` 直接存 `contacts.json`（非独立文件）——单文件易查询
- 批量默认 5 人（非 10）——避免单次 CLI 疲劳；`--all` 可一次过完
- 储备池联系人需 `--force` 才能锚定——SPEC §18.3 仅 core 层为默认，留逃生口但不鼓励
- `--confirm` 标志提供批量自动化通道，但默认走人工确认（原则二）

**测试**：新增 `tests/test_v40_anchor.py` 30 用例（goals 加载/leverage 读写/排序/统计/JSON 解析/规则降级/整合），总计 167 全部通过。

### 阶段4+5 落地（2026-07-10，建议引擎 + 兑现追踪）

**阶段4 建议引擎（§19）**：
- **`engine.advise_candidates()`**：聚合五信号源打分排序——冷却状态（14/21天→黄/红 +20/+30）、生日（+35）、leverage 锚定（+15）、pending 待办（+25）、强度（×2）；self/reserve 排除；按 score 降序取 top N
- **`ai.draft_advise()`**：把候选转成"联系谁+为什么+聊什么"三元组
  - why = 信号拼接（规则，可追溯）
  - what = LLM 生成一句话（失败降级 `_rule_based_what`：生日>待办>leverage>上次话题>冷关系兜底）
- **`social advise` 命令**：`--top 5`（SPEC §19.2 封顶 3-5）/ `--all`（扫全量）/ `--push`（微信推送）；每条附 `social draft -c <id> -m "..."` 衔接命令；不自动创建待办

**阶段5 兑现追踪（§20）**：
- **`engine.add_outcome()`**：timeline type=outcome 记录，含 goal 关联六维
- **`engine.list_outcomes()`**：按联系人/目标维度/年份过滤，日期降序
- **`engine.outcome_stats()`**：按目标维度/联系人/月份分布统计
- **`social outcomes` 命令**：三态——查询（默认）/`--add`（记录新成果，需位置参数联系人+`--summary`）/`--stats`（统计）；不算 ROI（原则七）

**修复**：
- 修复 `cmd_anchor`/`cmd_outcomes` 中 `resolve_contact` 解包错误（返回 `(contact_dict, match_type)` 非 `(id, dict)`）

**测试**：新增 `tests/test_v40_advise_outcome.py` 34 用例（outcome 读写/统计/advise 辅助函数/候选排序/三元组生成/规则降级/报告整合），总计 201 全部通过。

### 前置地基（v3.1，可独立发版）
- 文档一致性修复（SPEC_v3 §11 状态表过时：health 简化版、enrich --web 实际已实现）
- 落地 `enrichment_log.json` 写入
- 双层架构：`tier` 字段（core=strength≥3 约317人 / reserve），主动经营功能默认只扫 core 层
- 储备池晋升机制：真实互动触发晋升评估 + 单人 enrich --web
- health 三因子：recency×0.4 + depth×0.3 + layers×0.3
- 提醒调度解耦：CronCreate → 本地 launchd/cron + `social remind`
- 待办老化：pending >30天 标记 stale（只提示不自动取消）

### 范围冻结
- `_connections` 图谱、`_groups` 群感知、import-chat/calls 冻结至 v4.x+
- 批量 enrich 灰色联系人路线废弃（实测证伪：一个月仅 3/4,683），改为晋升触发式

---

## 3.1.0 (2026-07-10) — 分层经营地基（SPEC v4 §17 实施）

### 新功能
- **双层架构 tier**：`engine.contact_tier()` 派生属性（core=strength≥3 / reserve），`list_contacts(tier=...)` 过滤
  - `dashboard` / `check` / `health` 冷却与健康扫描**默认只扫核心圈**（317人），`--all` 扫全量（4,683人）
- **储备池晋升提示**：`log` / `note` 命中 reserve 联系人时提示晋升评估 + 单人补全命令（只提示不自动改，遵守原则二）
- **单人补全**：`social.py enrich --contact <人> [--web]`（晋升触发式，替代批量灰色补全路线）
- **health 三因子**：`recency×0.4 + depth×0.3 + layers×0.3`（layers 按角色互动层数实时计算），单人视图显示分项
- **`social remind`**：日程提前提醒本地化（解耦 Claude Code CronCreate）
  - 扫描今日待办中的时间标注（due ISO datetime / 14:30 / 下午3点半），窗口内推送微信
  - `--cron` 打印 crontab 接入配置；`data/remind_state.json` 去重（同待办同日只提醒一次）
- **待办老化**：pending >30天标记 🕸️ stale 置顶提示（仅标注，不自动取消，核心规则3）
- v3 CLI enrich 路径接入 `enrichment_log.json` 写入（此前仅 v2 路径有日志）

### 修复
- 修复 `todos` 对 `content` 字段待办（13条）崩溃：读取时归一化 `content→task`（不落盘）
- 消除 `social.py` main() 中 dashboard/check 的重复内联实现（曾致 cmd_dashboard 修改不生效）
- `_apply_role_layers` 拆出纯函数 `role_layers()`（health layers 因子复用，不再副作用改 tags）
- 修复 `test_version` 硬编码版本号（改为断言 `__version__`）
- 文档修正：SPEC_v3 §11 状态表与代码不符（health/enrich --web 实际已实现）

### 测试
- 新增 `tests/test_v31.py` 22 个用例，总计 137 个全部通过

### 实施偏差（相对 SPEC v4 §17 草案措辞，均已回写规约）
- tier 为**派生属性**（按 strength 实时计算），不持久化字段——避免 4,683 条记录与强度不同步
- 晋升机制为**提示+命令建议**，不自动执行 enrich——避免 log 命令被网络调用阻塞
- 提醒调度用 **crontab 打印接入配置**，不自动安装 launchd——系统级修改留给用户确认

---

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
