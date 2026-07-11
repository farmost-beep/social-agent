"""social_cli CLI 入口 - Social-CLI v3.0

统一入口，支持以下子命令：
- status     联系人状态总览
- todos      待办列表
- enrich     批量画像补全（v2.5 规划）
- health     关系健康分（v2.5 规划）
- draft      AI拟稿
- config     配置管理
- chat       与AI对话
- version    版本信息

设计原则：
- argparse 标准库，零新依赖
- 各子命令独立函数，便于单测
- 错误返回字符串，不抛异常（与 ai.py 一致）
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# 包内相对导入
from . import __version__

# ── 项目根定位 ──
# 用于定位数据目录（contacts.json 等）
# 模块导入通过包机制（from src.engine import）工作，不再需要 sys.path hack

_PROJECT_ROOT: Optional[Path] = None


def _find_project_root() -> Optional[Path]:
    """定位 social-agent 项目根目录（含 config/ 和 data/）

    优先级：
    1. 环境变量 SOCIAL_AGENT_HOME
    2. social_cli 包的父目录（开发模式 pip install -e .）
    3. src 包内目录（PyPI 安装，config/ 在 src/config/）
    4. ~/.social-agent/（PyPI 用户目录）
    5. 从 cwd 向上 5 层找含 config/ 和 src/ 的目录
    """
    # 1. 环境变量
    env = os.environ.get("SOCIAL_AGENT_HOME")
    if env and (Path(env) / "config").is_dir():
        return Path(env)

    # 2. 从 social_cli 包位置向上找（开发模式）
    pkg_parent = Path(__file__).resolve().parent.parent
    if (pkg_parent / "config").is_dir():
        return pkg_parent

    # 3. PyPI 安装：config/ 在 src 包内
    import importlib.util
    spec = importlib.util.find_spec("src")
    if spec and spec.origin:
        src_dir = Path(spec.origin).resolve().parent
        if (src_dir / "config").is_dir():
            return src_dir

    # 4. PyPI 用户目录
    user_dir = Path.home() / ".social-agent"
    if user_dir.is_dir() and (user_dir / "config").is_dir():
        return user_dir

    # 5. 从 cwd 向上找
    cwd = Path.cwd()
    p = cwd
    for _ in range(5):
        if (p / "config").is_dir() and (p / "src").is_dir():
            return p
        if (p / "data" / "contacts.json").exists():
            return p
        p = p.parent
        if p == p.parent:
            break

    return None


def _ensure_project_path() -> Optional[Path]:
    """定位项目根并切换 cwd（让 engine.py 的相对数据路径解析正确）

    src/ 模块已改为包内导入（from src.engine import），
    不再需要 sys.path hack。此函数仅用于数据目录定位。
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    root = _find_project_root()
    if root is None:
        return None

    # 切换 cwd 到项目根（让 engine.py 的默认 data_dir=./data 解析正确）
    if Path.cwd() != root:
        os.chdir(root)

    _PROJECT_ROOT = root
    return root


# 启动时自动定位
_ensure_project_path()


# ── 子命令实现 ──
# v3.0 最小版：先实现"读取类"和"配置类"命令
# 写入类命令（enrich等）暂时转发到旧 src/ 实现

def cmd_status(args) -> int:
    """联系人状态总览。v3.0 先转发到旧实现。"""
    root = _ensure_project_path()
    if root is None:
        print("✗ 找不到 social-agent 项目根，请设置 SOCIAL_AGENT_HOME 环境变量")
        return 1
    try:
        from src.social import cmd_dashboard  # type: ignore
        return cmd_dashboard(args)
    except ImportError as e:
        print(f"✗ 无法加载 src.social: {e}")
        print(f"  当前项目根: {root}")
        return 1


def cmd_todos(args) -> int:
    """查看待办列表。v3.0 直接调 engine.list_todos()

    默认显示 pending 状态
    --all       : 显示全部（含 completed）
    --completed : 只显示已完成
    --recent N  : 显示最近 N 天内创建/完成的
    """
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from src.engine import list_todos, _load, TODOS_FILE
    except ImportError as e:
        print(f"✗ 无法加载 engine: {e}")
        return 1

    # 决定状态过滤
    if args.completed:
        status_filter = "completed"
        title = "✅ 已完成"
    elif args.all:
        status_filter = None  # 不过滤
        title = "📋 全部待办"
    else:
        status_filter = "pending"
        title = "📋 待办列表"

    # 取数据
    if args.all:
        todos = _load(TODOS_FILE)  # 全部
    else:
        todos = list_todos(status=status_filter)

    # 按 created 倒序（最新的在前）
    todos = sorted(todos, key=lambda t: t.get("created", ""), reverse=True)

    # 近期过滤
    if args.recent:
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=args.recent)).isoformat()
        todos = [t for t in todos if t.get("created", "") >= cutoff]

    if not todos:
        print(f"✓ {title}：无")
        return 0

    print(f"\n{title}（共 {len(todos)} 项）\n")
    today = __import__('datetime').date.today().isoformat()
    for i, t in enumerate(todos, 1):
        priority = t.get("priority", "P2")
        contact = t.get("contact", "—")
        task = t.get("task", "")[:55]
        due = t.get("due", "")
        status = t.get("status", "pending")
        created = t.get("created", "")[:10]

        # 状态图标
        if status == "completed":
            status_icon = "✅"
        elif due and due < today:
            status_icon = "⚠️"
        else:
            status_icon = "  "

        # 优先级图标
        pri_icon = "🔴" if priority == "P0" else ("🟡" if priority == "P1" else "  ")

        due_str = f" (到期 {due})" if due else ""
        new_str = f" 🆕" if created == today else ""
        stale_str = f" 🕸️已挂{t.get('stale_days','?')}天" if t.get("stale") else ""
        print(f"  {status_icon}{pri_icon} {i:2d}. [{contact}]{due_str} {task}{new_str}{stale_str}")
    stale_count = sum(1 for t in todos if t.get("stale"))
    if stale_count:
        print(f"\n  🕸️ {stale_count} 条待办超30天未动，请确认是否仍需跟进（不会自动取消）")
    return 0


def cmd_enrich(args) -> int:
    """批量画像补全（v3.0 简化版实现）

    与 v2.5 旧实现的区别：
    - 直接调 LLMClient，不依赖旧 src.social.cmd_enrich
    - 保守策略：confidence < 3 跳过，已有 relation 不覆盖
    - 自动写入 _enrich_version 字段
    - --stats 显示统计（复用旧版）
    """
    # --stats 走 v2.5 旧实现（统计功能未重写）
    if getattr(args, 'stats', False):
        root = _ensure_project_path()
        if root is None:
            print("✗ 找不到 social-agent 项目根")
            return 1
        try:
            from src.social import cmd_enrich as _impl  # type: ignore
        except ImportError as e:
            print(f"✗ 无法加载 src.social: {e}")
            return 1
        return _impl(['--stats'])

    return _enrich_run(args)


# ── v3.0.4 新增：简化版 enrich 实现（绕过旧 v2.5 实现） ──

_ENRICH_SYSTEM_PROMPT = """你是社交关系AI助手，擅长从姓名片段和已有信息推断联系人画像。
根据用户提供的联系人信息，输出 JSON 格式补全结果。
要求：
1. 只能输出 JSON，不要解释
2. relation 必须是：同行/校友/合作/家人/其他
3. sub_relation 不超过 8 字
4. tags 1-3 个简短标签
5. confidence 1-10（10=完全确定，1=纯猜测）"""


def _enrich_pick_candidates(contacts: list, batch: int, force: bool) -> list:
    """挑选待补全的联系人

    优先级（v3.0 简化版）：
    1. 强度 ≤ 2 且 relation 为空（最高价值但未分类）
    2. 强度 ≤ 2 且无 tags
    3. 跳过已有 _enrich_version >= 1（除非 --force）
    """
    candidates = []
    for c in contacts:
        if not force and c.get("_enrich_version", 0) >= 1:
            continue
        if c.get("strength", 0) > 2:
            continue
        if not c.get("relation"):
            candidates.append((c, 1))  # 最高优先级
        elif not c.get("tags") or not any(t for t in c.get("tags", [])):
            candidates.append((c, 2))
    candidates.sort(key=lambda x: x[1])
    return [c for c, _ in candidates[:batch]]


def _enrich_call_llm(client, contact: dict) -> dict:
    """调用 LLM 补全单个联系人，返回 dict {relation, sub_relation, tags, confidence}"""
    import json as _json

    name = contact.get("name", "未知")
    existing_notes = contact.get("notes", "")[:200]
    existing_tags = contact.get("tags", [])

    user_prompt = f"""联系人姓名：{name}
已有备注：{existing_notes or '（无）'}
已有标签：{existing_tags or '（无）'}
强度：{contact.get('strength', 0)}

请输出 JSON 补全结果。"""

    response = client.complete_with_retry(user_prompt, system=_ENRICH_SYSTEM_PROMPT, max_retries=1)

    # 尝试从响应中提取 JSON
    response = response.strip()
    # 去除可能的代码块标记
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join(l for l in lines if not l.strip().startswith("```"))

    try:
        return _json.loads(response)
    except _json.JSONDecodeError:
        # 尝试提取 {...} 块
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return _json.loads(match.group(0))
            except _json.JSONDecodeError:
                pass
        return {"confidence": 0, "_error": f"无法解析: {response[:100]}"}


def _enrich_apply(contact: dict, llm_result: dict) -> bool:
    """把 LLM 结果应用到联系人，返回是否成功

    保护规则（SPEC §8.2.3）：
    - confidence < 3 跳过
    - 已有 relation 不覆盖
    - tags 只追加不覆盖
    - 不动 strength / notes
    """
    confidence = llm_result.get("confidence", 0)
    if confidence < 3:
        return False

    changed = False
    if not contact.get("relation"):
        new_rel = llm_result.get("relation", "").strip()
        if new_rel and new_rel in ("同行", "校友", "合作", "家人", "其他"):
            contact["relation"] = new_rel
            changed = True

    if not contact.get("sub_relation"):
        new_sub = llm_result.get("sub_relation", "").strip()
        if new_sub:
            contact["sub_relation"] = new_sub
            changed = True

    new_tags = llm_result.get("tags", [])
    if isinstance(new_tags, list):
        existing_tags = contact.get("tags", []) or []
        # 过滤空字符串 + 去重 + 追加
        for tag in new_tags:
            tag = str(tag).strip()
            if tag and tag not in existing_tags:
                existing_tags.append(tag)
        # 清理已有 tags 中的空字符串
        contact["tags"] = [t for t in existing_tags if t and t.strip()]
        if new_tags:
            changed = True

    return changed


def _enrich_run(args) -> int:
    """v3.0 简化版 enrich 实现

    特性：
    - 用 LLMClient 推断 relation/sub_relation/tags
    - 保守策略：confidence < 3 跳过，已有 relation 不覆盖
    - 标记 _enrich_version
    - 实时进度输出
    """
    import json as _json

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        from src.engine import _load, _save, CONTACTS_FILE
        from src.llm import get_client
    except ImportError as e:
        print(f"✗ 无法加载依赖: {e}")
        return 1

    contacts = _load(CONTACTS_FILE)
    if not isinstance(contacts, list):
        print("✗ contacts.json 格式异常（非列表）")
        return 1

    batch = args.batch if args.batch is not None else 5
    candidates = _enrich_pick_candidates(contacts, batch, args.force)

    print(f"\n📊 enrich 状态")
    print(f"  总联系人: {len(contacts)}")
    print(f"  待补全（强度≤2且无relation/tags）: {len([c for c in contacts if c.get('strength',0)<=2 and (not c.get('relation') or not c.get('tags') or not any(c.get('tags',[])))])}")
    print(f"  本次处理: {len(candidates)}")
    print()

    if not candidates:
        print("✓ 没有待补全的联系人")
        return 0

    if args.dry_run:
        print("🔍 预览（dry-run）:")
        for c in candidates:
            print(f"  - [{c.get('strength',0)}] {c.get('name','?')} ({c.get('id','?')})")
        return 0

    # 实际跑
    try:
        client = get_client()
    except Exception as e:
        print(f"✗ LLM 初始化失败: {e}")
        return 1

    success = 0
    skipped = 0
    failed = 0

    for i, c in enumerate(candidates, 1):
        name = c.get("name", "?")
        print(f"  [{i}/{len(candidates)}] {name}...", end=" ", flush=True)

        try:
            result = _enrich_call_llm(client, c)
            if result.get("_error"):
                print(f"✗ 解析失败: {result['_error'][:40]}")
                failed += 1
                continue

            confidence = result.get("confidence", 0)
            if _enrich_apply(c, result):
                c["_enrich_version"] = c.get("_enrich_version", 0) + 1
                success += 1
                rel = c.get("relation", "")
                tags = c.get("tags", [])
                print(f"✓ conf={confidence} rel={rel} tags={tags[:2]}")
                # 写入补全日志（SPEC v2.5 §8.1.3 / v3.1 接入）
                try:
                    from src.enrich import _log_enrichment
                    _log_enrichment(c.get("id", ""), name, [
                        {"field": "relation", "to": rel, "confidence": confidence},
                        {"field": "tags", "to": tags, "confidence": confidence},
                    ])
                except Exception:
                    pass  # 日志失败不影响补全本身
            else:
                skipped += 1
                print(f"⏭ confidence={confidence} 跳过（<3 或无变化）")

        except Exception as e:
            print(f"✗ 异常: {str(e)[:50]}")
            failed += 1

    # 保存
    if success > 0:
        _save(CONTACTS_FILE, contacts)
        print(f"\n✓ 已保存 {success} 个联系人的补全结果到 {CONTACTS_FILE.name}")
    else:
        print(f"\n⚠ 无变化，未写入文件")

    print(f"\n📈 本次汇总: 成功 {success} / 跳过 {skipped} / 失败 {failed}")
    return 0


# ── v3.0 health 健康分辅助函数（模块级，便于测试） ──

def _recency_score(days):
    """根据天数映射 recency 分"""
    if days <= 7: return 100
    if days <= 14: return 80
    if days <= 30: return 60
    if days <= 90: return 40
    return 20


def _grade_icon(score):
    if score >= 80: return "🟢"
    if score >= 50: return "🟡"
    if score >= 20: return "🟠"
    return "🔴"


def _grade_label(score):
    if score >= 80: return "健康"
    if score >= 50: return "关注"
    if score >= 20: return "预警"
    return "危险"


def _days_since(timeline, contact_id):
    """计算最后互动距今的天数"""
    from datetime import date, datetime
    if not timeline:
        return 999
    related = [t for t in timeline if t.get("contact") == contact_id]
    if not related:
        return 999
    last_date = max(t.get("date", "") for t in related)
    try:
        d = datetime.strptime(last_date[:10], "%Y-%m-%d").date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return 999


def _depth_score(timeline, contact_id):
    """根据最近 3 次互动类型计算 depth 分"""
    if not timeline:
        return 0
    related = sorted(
        [t for t in timeline if t.get("contact") == contact_id],
        key=lambda t: t.get("date", ""),
        reverse=True
    )[:3]
    if not related:
        return 0
    type_score = {"meeting": 100, "call": 70, "message": 40, "milestone": 50}
    scores = [type_score.get(t.get("type", "message"), 40) for t in related]
    return sum(scores) // len(scores)


def _layers_score(contact) -> int:
    """角色互动层数分（SPEC v2.5 §8.6.2）：x3=100, x2=66, x1=33, 无=0"""
    layers = contact.get("_layers")
    if layers is None:
        try:
            from src.engine import role_layers
            layers = role_layers(contact)
        except ImportError:
            layers = []
    n = len(layers or [])
    if n >= 3: return 100
    if n == 2: return 66
    if n == 1: return 33
    return 0


def _health_score(r_score: int, d_score: int, l_score: int) -> int:
    """v3.1 三因子公式：recency × 0.4 + depth × 0.3 + layers × 0.3"""
    return int(r_score * 0.4 + d_score * 0.3 + l_score * 0.3)


def cmd_health(args) -> int:
    """关系健康分（v3.1 三因子版）

    公式：health_score = recency × 0.4 + depth × 0.3 + layers × 0.3
    默认只扫核心圈（strength≥3，SPEC v4 §17），--all 扫全量。

    等级：
    - 🟢 健康 (80-100)
    - 🟡 关注 (50-79)
    - 🟠 预警 (20-49)
    - 🔴 危险 (0-19)
    """
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        from src.engine import _load, CONTACTS_FILE, TIMELINE_FILE, contact_tier
    except ImportError as e:
        print(f"✗ 无法加载 engine: {e}")
        return 1

    # 加载数据
    contacts = _load(CONTACTS_FILE)
    timeline = _load(TIMELINE_FILE)

    if not isinstance(contacts, list):
        print("✗ contacts.json 格式异常")
        return 1

    # 范围：默认核心圈；单人查询或 --all 时扫全量
    scope_all = getattr(args, "all", False) or bool(args.contact)
    if not scope_all:
        contacts = [c for c in contacts if contact_tier(c) == "core"]

    # 计算每个联系人的健康分
    scored = []
    for c in contacts:
        cid = c.get("id", "")
        if not cid:
            continue
        days = _days_since(timeline, cid)
        d_score = _depth_score(timeline, cid)
        r_score = _recency_score(days)
        l_score = _layers_score(c)
        total = _health_score(r_score, d_score, l_score)
        scored.append({
            "contact": c,
            "name": c.get("name", "?"),
            "strength": c.get("strength", 0),
            "days": days if days < 999 else "从未",
            "score": total,
            "grade": _grade_icon(total),
            "label": _grade_label(total),
        })

    # 排序：分数低（最该关注）的优先
    scored.sort(key=lambda x: x["score"])

    # 输出
    if args.contact:
        # 单人模式：找所有匹配项（避免歧义）
        matches = [s for s in scored if args.contact in s["name"] or args.contact == s["contact"].get("id")]
        if not matches:
            print(f"✗ 找不到联系人: {args.contact}")
            return 1
        if len(matches) > 1:
            print(f"\n⚠ '{args.contact}' 匹配 {len(matches)} 个联系人，请更精确指定：")
            for s in matches[:10]:
                days_str = f"{s['days']}天" if isinstance(s['days'], int) else "从未联系"
                print(f"  {s['grade']} {s['score']:3d}分 [{s['strength']}] {s['name']} (id={s['contact'].get('id')}) — 上次 {days_str}")
            return 0
        s = matches[0]
        days_str = f"{s['days']}天" if isinstance(s['days'], int) else "从未联系"
        recency = _recency_score(s['days'] if isinstance(s['days'], int) else 999)
        depth = _depth_score(timeline, s["contact"].get("id", ""))
        layers = _layers_score(s["contact"])
        print(f"\n{_grade_icon(s['score'])} {s['name']} {s['score']}分 — {s['label']}")
        print(f"  强度: {s['strength']}")
        print(f"  距上次联系: {days_str}")
        print(f"  recency: {recency}/100 (×0.4)")
        print(f"  depth:   {depth}/100 (×0.3)")
        print(f"  layers:  {layers}/100 (×0.3)")
        return 0

    scope_note = "全量" if scope_all else "核心圈，--all 看全量"
    if args.fix:
        scored = [s for s in scored if s["score"] < 50]
        print(f"\n⚠️ 需关注的健康问题（{len(scored)} 人，{scope_note}）\n")
    else:
        print(f"\n📊 关系健康分（{len(scored)} 人，{scope_note}）\n")

    if args.ranking:
        scored.sort(key=lambda x: x["score"], reverse=True)
        print("（排行：分数从高到低）\n")

    limit = 30 if not args.fix else 50
    for s in scored[:limit]:
        if isinstance(s['days'], int):
            days_str = f"{s['days']}天"
        else:
            days_str = "从未联系"
        print(f"  {s['grade']} {s['score']:3d}分 [{s['strength']}] {s['name']} — 上次 {days_str}")

    if len(scored) > limit:
        print(f"\n  ... (还有 {len(scored) - limit} 人未显示)")
    return 0


# ── anchor: 目标锚定 (SPEC v4 §18) ──

def _print_anchor_card(contact, suggestion):
    """打印联系人卡片 + AI 锚定建议。"""
    name = contact.get("name", contact.get("id", "?"))
    strength = contact.get("strength", 1)
    relation = contact.get("relation", contact.get("role", ""))
    sub = contact.get("sub_relation", "")
    tags = contact.get("tags", [])
    print(f"\n{'─'*60}")
    print(f"  {name}  (强度{strength} · {relation}" + (f"/{sub}" if sub else "") + ")")
    if tags:
        print(f"  标签: {', '.join(tags[:8])}" + (" ..." if len(tags) > 8 else ""))
    notes = contact.get("notes", "")
    if isinstance(notes, list):
        notes = " ".join(str(n) for n in notes)
    if notes:
        print(f"  备注: {str(notes)[:100]}")
    print(f"\n  💡 AI 锚定建议:")
    print(f"     goals:     {suggestion.get('goals', [])}")
    print(f"     how:       {suggestion.get('how', '')}")
    print(f"     direction: {suggestion.get('direction', '')}")


def _prompt_confirm():
    """交互式确认。返回 'y'/'n'/'e'/'q'。"""
    try:
        ans = input("\n  [y]确认 [n]跳过 [e]编辑 [q]退出 (默认 n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"
    return ans or "n"


def _prompt_edit(suggestion, goals, directions):
    """编辑建议。返回新 suggestion dict 或 None（取消）。"""
    print(f"\n  当前 goals: {suggestion.get('goals', [])}")
    print(f"  可选: {', '.join(goals)}")
    try:
        gs = input("  输入新 goals（逗号分隔，回车保留）: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    new_goals = None
    if gs:
        new_goals = [g.strip() for g in gs.split(",") if g.strip() in goals]
        if not new_goals:
            print("  ⚠ 无有效维度，保留原建议")
            new_goals = None

    try:
        how = input(f"  输入新 how（回车保留「{suggestion.get('how','')}」）: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not how:
        how = suggestion.get("how", "")

    print(f"  可选 direction: {', '.join(directions)}")
    try:
        d = input(f"  输入新 direction（回车保留「{suggestion.get('direction','')}」）: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if d and d not in directions:
        print(f"  ⚠ 非法 direction，保留「{suggestion.get('direction','')}」")
        d = suggestion.get("direction", "")
    elif not d:
        d = suggestion.get("direction", "")

    return {
        "goals": new_goals or suggestion.get("goals", []),
        "how": how,
        "direction": d,
    }


def cmd_anchor(args) -> int:
    """目标锚定（SPEC v4 §18）。

    三态：
    - social anchor             交互式批量锚定（默认 batch=5）
    - social anchor <contact>   单人锚定
    - social anchor --stats     锚定进度统计
    """
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    from src.engine import (
        load_goals, list_unanchored, list_anchored, anchor_stats,
        get_contact, resolve_contact, set_leverage, get_leverage,
        contact_tier, list_timeline,
    )
    from src.ai import suggest_leverage

    goals_cfg = load_goals()
    goals = goals_cfg["goals"]
    directions = goals_cfg["directions"]

    # ── --stats ──
    if args.stats:
        s = anchor_stats()
        print(f"\n📊 目标锚定进度（SPEC v4 §18）")
        print(f"{'─'*40}")
        print(f"  核心圈总数:   {s['core_total']}")
        print(f"  已锚定:       {s['anchored']} ({s['anchored_pct']}%)")
        print(f"  待锚定:       {s['pending']}")
        if s["by_strength_anchored"]:
            print(f"\n  已锚定按强度: {s['by_strength_anchored']}")
        if s["by_strength_pending"]:
            print(f"  待锚定按强度: {s['by_strength_pending']}")
        if s["by_goal"]:
            print(f"\n  已锚定按目标维度:")
            for g, n in sorted(s["by_goal"].items(), key=lambda x: -x[1]):
                print(f"    {g}: {n}")
        if s["by_direction"]:
            print(f"\n  已锚定按 direction:")
            for d, n in s["by_direction"].items():
                print(f"    {d}: {n}")
        if s["pending"] > 0:
            print(f"\n  下一步: social anchor  (默认先锚定强度最高的 {min(args.batch, s['pending'])} 人)")
        return 0

    # ── 单人锚定 ──
    if args.contact:
        c, _ = resolve_contact(args.contact)
        if not c:
            print(f"✗ 未找到联系人: {args.contact}")
            return 1
        cid = c["id"]
        if contact_tier(c) != "core":
            print(f"⚠ {c.get('name', cid)} 在储备池（强度{c.get('strength',1)}），SPEC §18.3 仅锚定 core 层")
            if not args.force:
                print("  使用 --force 强制锚定储备池联系人")
                return 1

        # 已锚定则先展示
        existing = get_leverage(cid)
        if existing and existing.get("confirmed"):
            print(f"\n📌 {c.get('name', cid)} 已锚定（{existing['confirmed']}）:")
            print(f"   goals:     {existing.get('goals', [])}")
            print(f"   how:       {existing.get('how', '')}")
            print(f"   direction: {existing.get('direction', '')}")
            if not args.force:
                print("\n  使用 --force 重新锚定")
                return 0

        # 生成建议
        tls = list_timeline(contact=cid, days=180) if cid else []
        tl_summary = "；".join(t.get("summary", "") for t in tls[:3]) if tls else ""
        suggestion = suggest_leverage(c, goals, timeline_summary=tl_summary, directions=directions)

        _print_anchor_card(c, suggestion)

        if args.dry_run:
            return 0

        if args.confirm:
            # --confirm 直接写入（不交互）
            today = __import__("datetime").date.today().isoformat()
            ok, msg = set_leverage(cid, suggestion["goals"], suggestion["how"], suggestion["direction"], confirmed=today)
            print(f"\n  {'✓' if ok else '✗'} {msg}")
            return 0 if ok else 1

        ans = _prompt_confirm()
        if ans == "q":
            print("\n  已退出")
            return 0
        if ans == "n":
            print("  跳过")
            return 0

        final = suggestion
        if ans == "e":
            edited = _prompt_edit(suggestion, goals, directions)
            if not edited:
                print("  取消")
                return 0
            final = edited

        # 写入（confirmed=今日，用户已确认）
        today = __import__("datetime").date.today().isoformat()
        ok, msg = set_leverage(cid, final["goals"], final["how"], final["direction"], confirmed=today)
        print(f"\n  {'✓' if ok else '✗'} {msg}")
        return 0 if ok else 1

    # ── 批量交互式 ──
    min_s = args.min_strength
    batch = args.batch
    candidates = list_unanchored(min_strength=min_s, tier="core", limit=batch if not args.all else None)
    if not candidates:
        print("\n✓ 核心圈已全部锚定（或当前过滤条件下无候选）")
        print("  social anchor --stats 查看进度")
        return 0

    print(f"\n🎯 目标锚定（SPEC v4 §18）—— 本次 {len(candidates)} 人候选")
    print(f"  目标维度: {', '.join(goals)}")
    print(f"  操作: [y]确认 [n]跳过 [e]编辑 [q]退出\n")

    confirmed_count = 0
    skipped_count = 0
    for c in candidates:
        cid = c["id"]
        tls = list_timeline(contact=cid, days=180)
        tl_summary = "；".join(t.get("summary", "") for t in tls[:3]) if tls else ""
        suggestion = suggest_leverage(c, goals, timeline_summary=tl_summary, directions=directions)

        _print_anchor_card(c, suggestion)

        if args.dry_run:
            skipped_count += 1
            continue

        # --confirm: 跳过交互直接写入 AI 建议
        if args.confirm:
            today = __import__("datetime").date.today().isoformat()
            ok, msg = set_leverage(cid, suggestion["goals"], suggestion["how"], suggestion["direction"], confirmed=today)
            print(f"  {'✓' if ok else '✗'} {msg}")
            if ok:
                confirmed_count += 1
            else:
                skipped_count += 1
            continue

        ans = _prompt_confirm()
        if ans == "q":
            print("\n  已退出")
            break
        if ans == "n":
            skipped_count += 1
            print("  跳过")
            continue

        final = suggestion
        if ans == "e":
            edited = _prompt_edit(suggestion, goals, directions)
            if not edited:
                print("  取消")
                skipped_count += 1
                continue
            final = edited

        today = __import__("datetime").date.today().isoformat()
        ok, msg = set_leverage(cid, final["goals"], final["how"], final["direction"], confirmed=today)
        print(f"  {'✓' if ok else '✗'} {msg}")
        if ok:
            confirmed_count += 1

    print(f"\n{'─'*40}")
    print(f"  本次: 确认 {confirmed_count} · 跳过 {skipped_count}")
    stats = anchor_stats()
    print(f"  总进度: {stats['anchored']}/{stats['core_total']} ({stats['anchored_pct']}%)")
    if stats["pending"] > 0:
        print(f"  下一步: social anchor  (继续锚定下一批)")
    return 0


# ── advise: 建议引擎 (SPEC v4 §19) ──

def cmd_advise(args) -> int:
    """本周经营建议（SPEC v4 §19）—— 联系谁+为什么+聊什么三元组。"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    from src.engine import advise_candidates
    from src.ai import generate_advise_report

    top = args.top
    tier = "all" if args.all else "core"
    candidates = advise_candidates(top=top, tier=tier)
    if not candidates:
        print("\n✓ 当前无经营建议候选（核心圈均近期已联系且无待办/生日信号）")
        return 0

    report = generate_advise_report(candidates, top=top)

    today = __import__("datetime").date.today().isoformat()
    print(f"\n📋 本周经营建议（{today}）—— SPEC v4 §19")
    print(f"{'─'*60}")
    for i, r in enumerate(report, 1):
        print(f"\n{i}. 联系 {r['who']} —— {r['why']}")
        print(f"   → {r['what']}")
        cid = next((c["contact"]["id"] for c in candidates if c["contact"].get("name") == r["who"]), None)
        if cid:
            print(f"   拟稿: social draft -c {cid} -m \"{r['what'][:30]}\"")

    print(f"\n{'─'*60}")
    print(f"  共 {len(report)} 条建议 · 3-5 条封顶（SPEC §19.2）")
    print(f"  建议仅建议，不自动创建待办（核心规则3精神延伸）")
    if args.push:
        print(f"\n  📱 推送模式：尝试推送到微信...")
        # 复用 push 框架
        try:
            from src.push import send_message
            msg = "\n".join(f"{i}. {r['who']}: {r['what']}" for i, r in enumerate(report, 1))
            send_message(f"📋 本周经营建议\n{msg}")
            print("  ✓ 已推送")
        except Exception as e:
            print(f"  ⚠ 推送失败: {e}")
    return 0


# ── outcomes: 兑现追踪 (SPEC v4 §20) ──

def cmd_outcomes(args) -> int:
    """兑现追踪查询（SPEC v4 §20）—— timeline type=outcome 记录。"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    from src.engine import list_outcomes, outcome_stats, add_outcome, resolve_contact

    # ── --add 模式：记录新成果 ──
    if args.add:
        if not args.contact:
            print("✗ --add 需要指定联系人（位置参数）")
            print("  用法: social outcomes <联系人> --add --summary '...'")
            return 1
        if not args.summary:
            print("✗ --add 需要 --summary 描述成果")
            return 1
        c, _ = resolve_contact(args.contact)
        if not c:
            print(f"✗ 未找到联系人: {args.contact}")
            return 1
        cid = c["id"]
        rec = add_outcome(cid, args.summary, goal=args.goal, date_str=args.date)
        print(f"✓ 已记录成果: {rec['id']}")
        print(f"  联系人: {c.get('name', cid)}")
        print(f"  摘要:   {args.summary}")
        if args.goal:
            print(f"  目标:   {args.goal}")
        return 0

    # ── --stats 模式 ──
    if args.stats:
        s = outcome_stats(year=args.year)
        print(f"\n📊 兑现追踪统计（SPEC v4 §20）")
        print(f"{'─'*40}")
        print(f"  成果总数: {s['total']}")
        if s["by_goal"]:
            print(f"\n  按目标维度:")
            for g, n in s["by_goal"].items():
                print(f"    {g}: {n}")
        if s["by_contact"]:
            print(f"\n  按联系人 (前10):")
            for c, n in list(s["by_contact"].items())[:10]:
                print(f"    {c}: {n}")
        if s["by_month"]:
            print(f"\n  按月份:")
            for m, n in s["by_month"].items():
                print(f"    {m}: {n}")
        if s["total"] == 0:
            print("\n  尚无成果记录。用 --add --contact <人> --summary '...' 记录第一笔")
        return 0

    # ── 查询模式 ──
    contact_id = None
    if args.contact:
        c, _ = resolve_contact(args.contact)
        if not c:
            print(f"✗ 未找到联系人: {args.contact}")
            return 1
        contact_id = c["id"]
        print(f"\n📌 {c.get('name', contact_id)} 的成果记录:")
    else:
        print(f"\n📌 兑现追踪记录（SPEC v4 §20）")

    outcomes = list_outcomes(contact=contact_id, goal=args.goal, year=args.year, limit=args.limit)
    if not outcomes:
        print("  无记录")
        if not args.contact:
            print("  用 --add --contact <人> --summary '...' 记录成果")
        return 0

    print(f"{'─'*60}")
    for r in outcomes:
        goal_tag = f" [{r.get('goal', '?')}]" if r.get("goal") else ""
        print(f"\n  {r['date']}{goal_tag} — {r.get('contact', '?')}")
        print(f"    {r.get('summary', '')}")
    print(f"\n  共 {len(outcomes)} 条" + (f"（限制 {args.limit}）" if args.limit and len(outcomes) == args.limit else ""))
    return 0


def cmd_draft(args) -> int:
    """AI拟稿。v3.0 使用新 LLM 抽象层。"""
    if not args.message:
        print("✗ 请提供要拟稿的提示（-m）或联系人名")
        return 1

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        # 动态导入 src.ai（兼容旧数据）
        from src.ai import draft_message  # type: ignore
        result = draft_message(
            contact_name=args.contact or "未知",
            context_summary=args.message,
            tone=args.tone,
        )
        print(result)
        return 0
    except ImportError as e:
        print(f"✗ 无法加载 src.ai: {e}")
        return 1


def cmd_config(args) -> int:
    """配置管理：查看/设置 LLM provider。"""
    if not args.action:
        # 无子命令时显示 help（与其他子命令行为一致）
        print("用法: social config {show,providers,set}")
        print()
        print("  show       显示当前 LLM 配置")
        print("  providers  列出可用 LLM providers")
        print("  set        设置配置（提示用环境变量）")
        print()
        print("试试: social config show")
        return 0

    if args.action == "show":
        return _config_show()
    elif args.action == "set":
        return _config_set(args.key, args.value)
    elif args.action == "providers":
        return _config_providers()
    return 1


def _config_show() -> int:
    """显示当前 LLM 配置"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from src.llm import list_providers
    except ImportError as e:
        print(f"✗ 无法加载 src.llm: {e}")
        return 1

    providers = list_providers()
    print(f"可用 providers: {', '.join(providers)}")
    print(f"当前默认: claude")
    print()
    print("环境变量:")
    import os
    # 同时显示 ANTHROPIC_AUTH_TOKEN（兼容 Claude Code 内部变量名）
    for var in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY",
                "ANTHROPIC_BASE_URL", "LLM_ENGINE"]:
        val = os.environ.get(var, "(未设置)")
        masked = val[:8] + "***" if len(val) > 12 and val != "(未设置)" else val
        print(f"  {var} = {masked}")
    return 0


def _config_set(key: Optional[str], value: Optional[str]) -> int:
    """设置配置项（提示用户用环境变量）"""
    print("⚠ v3.0 配置通过环境变量管理：")
    print()
    print("切换 LLM provider:")
    print("  export LLM_ENGINE=openai   # 或 claude")
    print()
    print("设置 API Key:")
    print("  export ANTHROPIC_API_KEY=sk-ant-...")
    print("  export OPENAI_API_KEY=sk-...")
    print()
    print("自定义 base_url（用于代理/MiniMax等）:")
    print("  export ANTHROPIC_BASE_URL=https://proxy.example.com")
    print("  export OPENAI_BASE_URL=https://api.MiniMax.cn/v1")
    return 0


def _config_providers() -> int:
    """列出所有可用 provider"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from src.llm import list_providers
    except ImportError as e:
        print(f"✗ 无法加载 src.llm: {e}")
        return 1
    print("可用 LLM providers:")
    for p in list_providers():
        print(f"  - {p}")
    return 0


def cmd_chat(args) -> int:
    """与AI对话（直接调用 LLM）"""
    if not args.message:
        print("✗ 请提供消息内容")
        return 1

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        from src.llm import get_client
        client = get_client()
        system = "你是社交关系AI助手。"
        result = client.complete(args.message, system=system)
        print(result)
        return 0
    except Exception as e:
        print(f"✗ 调用失败: {e}")
        return 1


def cmd_send(args) -> int:
    """通过 Mac 微信推送消息（v3.1 新增）"""
    if not args.message:
        print("✗ 请提供消息内容（-m）")
        return 1

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        from social_cli.push import push_to_wechat, check_available, find_contact_weixin_id
    except ImportError as e:
        print(f"✗ 无法加载 push 模块: {e}")
        return 1

    # 如果未指定 contact，用 draft 先拟稿
    contact = args.contact
    if not contact:
        print("✗ 请指定联系人（-c 姓名）")
        return 1

    # 安全确认：默认不真发，除非 --confirm
    if not args.confirm:
        print(f"\n📤 将发送消息到微信：")
        print(f"  收件人: {contact}")
        print(f"  消息:   {args.message[:100]}")
        print()
        print("⚠️  使用 --confirm 确认发送")
        print("    social send -c \"联系人\" -m \"消息\" --confirm")
        return 1

    result = push_to_wechat(contact, args.message)
    if result["success"]:
        print(f"✓ 已发送到「{contact}」: {args.message[:60]}")
        return 0
    else:
        print(f"✗ 发送失败: {result.get('error', '未知错误')}")
        return 1


def cmd_wxid_bind(args) -> int:
    """绑定联系人的微信 wxid（v3.1 新增）"""
    if not args.contact or not args.wxid:
        print("✗ 用法: social wxid-bind <联系人> <wxid>")
        return 1

    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    try:
        from src.engine import _load, _save, CONTACTS_FILE
    except ImportError:
        print("✗ 无法加载 engine 模块")
        return 1

    contacts = _load(CONTACTS_FILE)
    if not isinstance(contacts, list):
        print("✗ contacts.json 格式异常")
        return 1

    # 找联系人
    found = [c for c in contacts if c.get("name", "").strip() == args.contact]
    if not found:
        print(f"✗ 未找到联系人「{args.contact}」")
        return 1

    for c in found:
        if "platforms" not in c or not isinstance(c.get("platforms"), dict):
            c["platforms"] = {}
        c["platforms"]["weixin"] = args.wxid
        print(f"✓ 已绑定「{c['name']}」→ wxid: {args.wxid}")

    _save(CONTACTS_FILE, contacts)
    print(f"✓ 已保存到 {CONTACTS_FILE.name}")
    return 0


def cmd_send_check(args) -> int:
    """检查推送环境是否就绪（v3.1 新增）"""
    if _ensure_project_path() is None:
        print("✗ 找不到 social-agent 项目根")
        return 1
    try:
        from social_cli.push import check_available, find_contact_weixin_id
    except ImportError as e:
        print(f"✗ 无法加载 push 模块: {e}")
        return 1

    status = check_available()
    print(f"\n📤 微信推送环境检查\n")
    for c in status["checks"]:
        print(f"  {c['status']} {c['check']}")
    print(f"\n  总体可用性: {'✅ 可用' if status['available'] else '❌ 部分不可用'}")

    # 如果是某个联系人
    if args.contact:
        wid = find_contact_weixin_id(args.contact)
        if wid:
            print(f"  📱 联系人「{args.contact}」微信ID: {wid[:30]}")
        else:
            print(f"  ⚠️ 未找到「{args.contact}」的微信ID")

    return 0


# ── v3.1 remind：日程提前提醒（本地 cron 调度，解耦 Claude Code CronCreate） ──

import re as _re

def _extract_event_time(text: str):
    """从待办文本中提取时间标注，返回 (hour, minute) 或 None。

    支持：14:30 / 14点 / 14点半 / 下午2点 / 晚上8点半
    """
    if not text:
        return None
    m = _re.search(r"(\d{1,2}):(\d{2})", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return (h, mi)
    m = _re.search(r"(上午|下午|晚上|中午)?\s*(\d{1,2})\s*点(半)?", text)
    if m:
        period, h, half = m.group(1), int(m.group(2)), m.group(3)
        if h > 23:
            return None
        if period in ("下午", "晚上") and h < 12:
            h += 12
        elif period == "中午" and h < 11:
            h += 12
        mi = 30 if half else 0
        return (h, mi) if h <= 23 else None
    return None


def cmd_remind(args) -> int:
    """日程提前提醒（SPEC v4 §17 提醒调度解耦）

    扫描今日到期的 pending 待办中带时间标注的日程，
    落在 [now, now+ahead分钟] 窗口内的推送提醒。
    去重状态记录在 data/remind_state.json（同一待办同一天只提醒一次）。
    """
    root = _ensure_project_path()
    if root is None:
        print("✗ 找不到 social-agent 项目根")
        return 1

    if args.cron:
        print("📋 crontab 接入（本地调度，无需 Claude Code）：")
        print("   crontab -e 添加一行：")
        print(f"   */15 7-22 * * * cd {root} && {sys.executable} -m social_cli remind >> ~/.social-remind.log 2>&1")
        return 0

    try:
        from src.engine import list_todos, get_contact
    except ImportError as e:
        print(f"✗ 无法加载 engine: {e}")
        return 1

    import json as _json
    from datetime import date as _date, datetime as _dt, timedelta as _td

    now = _dt.now()
    today = _date.today().isoformat()
    state_file = root / "data" / "remind_state.json"
    state = {}
    if state_file.exists():
        try:
            state = _json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    todos = [t for t in list_todos() if str(t.get("due", ""))[:10] == today]
    hits = []
    for t in todos:
        # 优先从 due 的 ISO datetime 提取时间（如 2026-07-10T09:00:00），其次从任务文本
        due = str(t.get("due", ""))
        ev = None
        if "T" in due:
            m = _re.match(r"\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})", due)
            if m:
                ev = (int(m.group(1)), int(m.group(2)))
        if not ev:
            ev = _extract_event_time(t.get("task", ""))
        if not ev:
            continue
        event_dt = now.replace(hour=ev[0], minute=ev[1], second=0, microsecond=0)
        if now <= event_dt <= now + _td(minutes=args.ahead):
            if state.get(t["id"]) == today:
                continue  # 今天已提醒过
            hits.append((t, event_dt))

    if not hits:
        print(f"✓ 未来 {args.ahead} 分钟内无需提醒的日程")
        return 0

    for t, event_dt in hits:
        contact = get_contact(t.get("contact", ""))
        name = contact["name"] if contact else t.get("contact", "")
        msg = f"⏰ 日程提醒：{event_dt.strftime('%H:%M')} {name} — {t.get('task','')}"
        if args.dry_run:
            print(f"[dry-run] {msg}")
            continue
        try:
            from src.push import push_to_wechat
            ok, info = push_to_wechat("日程提醒", msg)
            print(f"{'✓ 已推送' if ok else '⚠ 推送失败(' + info + ')'}: {msg}")
        except ImportError:
            ok = False
            print(f"⚠ 推送模块不可用，仅打印: {msg}")
        if not args.dry_run:
            state[t["id"]] = today

    if not args.dry_run:
        try:
            state_file.write_text(_json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"⚠ 提醒状态保存失败: {e}")
    return 0


def cmd_version(args) -> int:
    """显示版本"""
    print(f"social-cli {__version__}")
    print(f"Python {sys.version.split()[0]}")
    print(f"路径: {Path(__file__).resolve().parent}")
    return 0


# ── argparse 框架 ──

def build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器"""
    parser = argparse.ArgumentParser(
        prog="social",
        description="社交关系AI管家 - Social-CLI v3.0",
        epilog="更多信息请查看 docs/SPEC.md",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # status
    p_status = subparsers.add_parser("status", help="联系人状态总览")

    # todos
    p_todos = subparsers.add_parser("todos", help="查看待办列表")
    p_todos.add_argument("--all", action="store_true", help="显示全部（含已完成）")
    p_todos.add_argument("--completed", action="store_true", help="只看已完成")
    p_todos.add_argument("--recent", type=int, metavar="N", help="只看最近 N 天创建")

    # enrich
    p_enrich = subparsers.add_parser("enrich", help="批量画像补全")
    p_enrich.add_argument("--batch", type=int, default=5, help="批次大小（默认 5）")
    p_enrich.add_argument("--dry-run", action="store_true", help="预览模式")
    p_enrich.add_argument("--force", action="store_true", help="重新处理")
    p_enrich.add_argument("--stats", action="store_true", help="只看统计")
    p_enrich.add_argument("--web", action="store_true", help="启用网络搜索")

    # health
    p_health = subparsers.add_parser("health", help="关系健康分（默认核心圈）")
    p_health.add_argument("contact", nargs="?", help="联系人（可选）")
    p_health.add_argument("--fix", action="store_true", help="只看需关注的")
    p_health.add_argument("--ranking", action="store_true", help="排行榜")
    p_health.add_argument("--all", action="store_true", help="扫全量联系人（默认仅核心圈 strength≥3）")

    # remind (v3.1)
    p_remind = subparsers.add_parser("remind", help="日程提前提醒（本地 cron 调度，v3.1）")
    p_remind.add_argument("--ahead", type=int, default=60, metavar="MIN", help="提前提醒窗口分钟数（默认 60）")
    p_remind.add_argument("--dry-run", action="store_true", help="只打印不推送")
    p_remind.add_argument("--cron", action="store_true", help="打印 crontab 接入配置")

    # anchor (v4.0 §18)
    p_anchor = subparsers.add_parser("anchor", help="目标锚定（v4.0 §18）")
    p_anchor.add_argument("contact", nargs="?", help="单人锚定（联系人名/ID）")
    p_anchor.add_argument("--stats", action="store_true", help="锚定进度统计")
    p_anchor.add_argument("--batch", type=int, default=5, metavar="N", help="批量锚定每次人数（默认 5）")
    p_anchor.add_argument("--min-strength", type=int, metavar="S", help="仅锚定 strength≥S 的联系人")
    p_anchor.add_argument("--all", action="store_true", help="不限批次大小，列出全部候选")
    p_anchor.add_argument("--confirm", action="store_true", help="跳过交互直接写入 AI 建议（批量自动化）")
    p_anchor.add_argument("--dry-run", action="store_true", help="只打印建议不写入")
    p_anchor.add_argument("--force", action="store_true", help="强制重新锚定已锚定/储备池联系人")

    # advise (v4.0 §19)
    p_advise = subparsers.add_parser("advise", help="本周经营建议（v4.0 §19）")
    p_advise.add_argument("--top", type=int, default=5, metavar="N", help="建议条数（默认 5，SPEC §19.2 封顶 3-5）")
    p_advise.add_argument("--all", action="store_true", help="扫全量联系人（默认仅核心圈）")
    p_advise.add_argument("--push", action="store_true", help="推送到微信")

    # outcomes (v4.0 §20)
    p_outcomes = subparsers.add_parser("outcomes", help="兑现追踪（v4.0 §20）")
    p_outcomes.add_argument("contact", nargs="?", help="过滤联系人")
    p_outcomes.add_argument("--goal", help="过滤目标维度（事业/投资/家庭/健康/AI能力/知识）")
    p_outcomes.add_argument("--year", type=int, help="过滤年份")
    p_outcomes.add_argument("--limit", type=int, default=50, metavar="N", help="最多返回条数（默认 50）")
    p_outcomes.add_argument("--stats", action="store_true", help="统计模式")
    p_outcomes.add_argument("--add", action="store_true", help="记录新成果（需 --contact --summary）")
    p_outcomes.add_argument("--summary", help="成果摘要（--add 模式）")
    p_outcomes.add_argument("--date", help="成果日期（--add 模式，默认今日）")

    # draft
    p_draft = subparsers.add_parser("draft", help="AI拟稿")
    p_draft.add_argument("-m", "--message", required=True, help="上下文摘要")
    p_draft.add_argument("-c", "--contact", help="联系人名称")
    p_draft.add_argument(
        "--tone", choices=["亲切", "正式", "简洁"],
        help="语气（默认从配置读取）"
    )

    # config
    p_config = subparsers.add_parser("config", help="配置管理")
    config_sub = p_config.add_subparsers(dest="action", help="操作")
    config_sub.add_parser("show", help="显示当前配置")
    config_sub.add_parser("providers", help="列出可用 providers")
    p_set = config_sub.add_parser("set", help="设置配置（提示用环境变量）")
    p_set.add_argument("key", nargs="?", help="配置键")
    p_set.add_argument("value", nargs="?", help="配置值")

    # chat
    p_chat = subparsers.add_parser("chat", help="与AI对话")
    p_chat.add_argument("message", help="消息内容")

    # send (v3.1)
    p_send = subparsers.add_parser("send", help="通过 Mac 微信推送消息（v3.1）")
    p_send.add_argument("-c", "--contact", required=True, help="微信联系人名称")
    p_send.add_argument("-m", "--message", required=True, help="消息内容")
    p_send.add_argument("--confirm", action="store_true", help="确认发送（默认不真发）")

    # send-check (v3.1)
    p_check = subparsers.add_parser("send-check", help="检查推送环境（v3.1）")
    p_check.add_argument("contact", nargs="?", help="联系人名称（可选）")

    # wxid-bind (v3.1)
    p_wxid = subparsers.add_parser("wxid-bind", help="绑定联系人 wxid（v3.1）")
    p_wxid.add_argument("contact", help="联系人名称")
    p_wxid.add_argument("wxid", help="微信 wxid（含 @im.wechat 后缀）")

    # version
    subparsers.add_parser("version", help="显示版本")

    return parser


# ── 主入口 ──

# 命令 → 处理函数的映射
_COMMANDS = {
    "status": cmd_status,
    "todos": cmd_todos,
    "enrich": cmd_enrich,
    "health": cmd_health,
    "draft": cmd_draft,
    "config": cmd_config,
    "chat": cmd_chat,
    "remind": cmd_remind,
    "anchor": cmd_anchor,
    "advise": cmd_advise,
    "outcomes": cmd_outcomes,
    "send": cmd_send,
    "send-check": cmd_send_check,
    "wxid-bind": cmd_wxid_bind,
    "version": cmd_version,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 主入口

    Args:
        argv: 命令行参数（None 时用 sys.argv[1:]）

    Returns:
        退出码（0=成功，非0=失败）
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # 无子命令时显示帮助
    if not args.command:
        parser.print_help()
        return 0

    # 分发到对应处理函数
    handler = _COMMANDS.get(args.command)
    if handler is None:
        print(f"✗ 未知命令: {args.command}")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n⚠ 用户中断")
        return 130
    except Exception as e:
        print(f"✗ 异常: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())