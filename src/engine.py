"""Core engine for Social Relationship AI Agent."""
import json, os, uuid, re, yaml
from datetime import datetime, date, timedelta
from pathlib import Path

# ── 配置加载 ──

def _get_home_dir():
    """获取 social-agent 主目录

    优先级：
    1. 环境变量 SOCIAL_AGENT_HOME
    2. 包内目录（开发模式：src/engine.py 的父目录的父目录）
    3. ~/.social-agent/（PyPI 用户目录）
    """
    env = os.environ.get("SOCIAL_AGENT_HOME")
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    # 包内目录（开发模式：src/engine.py → 项目根；PyPI：src/engine.py → src/）
    pkg_root = Path(__file__).resolve().parent.parent
    if (pkg_root / "config").is_dir():
        return pkg_root
    # PyPI 安装：config/ 在 src/ 内
    pkg_src = Path(__file__).resolve().parent
    if (pkg_src / "config").is_dir():
        return pkg_src

    # PyPI 用户目录
    user_dir = Path.home() / ".social-agent"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _load_config():
    """读取 config.yaml，如不存在则使用默认值。"""
    home = _get_home_dir()
    config_paths = [
        home / "config" / "config.local.yaml",
        home / "config" / "config.yaml",
    ]
    for cp in config_paths:
        if cp.exists():
            with open(cp, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}

_CONFIG = _load_config()
_DATA_DIR = Path(_CONFIG.get("data_dir", str(_get_home_dir() / "data")))

CONTACTS_FILE = _DATA_DIR / "contacts.json"
TIMELINE_FILE = _DATA_DIR / "timeline.json"
TODOS_FILE = _DATA_DIR / "todos.json"

def _load(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(path, data):
    """安全写入：防止空数据覆盖已有内容。"""
    # 检查：如果新数据为空且文件已有内容，拒绝写入
    if isinstance(data, (list, dict)) and len(data) == 0:
        if path.exists() and path.stat().st_size > 2:
            import warnings
            warnings.warn(f"⚠ 安全机制：拒绝空数据覆盖 {path.name}（已有 {path.stat().st_size} 字节数据）")
            return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 双层架构 tier (SPEC v4 §17) ──

TIER_CORE_MIN_STRENGTH = 3

def contact_tier(contact):
    """派生 tier：core（strength≥3）/ reserve（≤2）。

    按 strength 实时计算，不持久化，避免字段与强度不同步。
    """
    return "core" if contact.get("strength", 1) >= TIER_CORE_MIN_STRENGTH else "reserve"


def promotion_hint(contact):
    """储备池晋升提示（SPEC v4 §17）：reserve 联系人发生真实互动时返回提示文案。

    只提示，不自动改强度、不自动跑补全（原则二 + 原则七）。
    """
    if contact_tier(contact) != "reserve" or contact.get("relation") == "self":
        return None
    name = contact.get("name", contact.get("id", "?"))
    return (f"💡 {name} 当前在储备池（强度{contact.get('strength', 1)}），出现真实互动。\n"
            f"   建议评估晋升: python3 src/social.py edit-contact {contact['id']} --strength 3\n"
            f"   补全画像:     python3 src/social.py enrich --contact {contact['id']} --web")

# ── Contacts ──

def list_contacts(role=None, tag=None, tier=None):
    contacts = _load(CONTACTS_FILE)
    if role:
        contacts = [c for c in contacts if c.get("role") == role or c.get("sub_relation") == role]
    if tag:
        contacts = [c for c in contacts if tag in c.get("tags", [])]
    if tier:
        contacts = [c for c in contacts if contact_tier(c) == tier]
    return contacts

def add_contact(contact_id, name, role, tags=None, platforms=None, notes="", sub_relation=""):
    contacts = _load(CONTACTS_FILE)
    if any(c["id"] == contact_id for c in contacts):
        return False, f"联系人 {contact_id} 已存在"
    contact = {
        "id": contact_id, "name": name,
        "relation": role, "role": role,  # relation 是规范名，role 是向后兼容
        "sub_relation": sub_relation,
        "stage": "",
        "strength": 3, "tags": tags or [], "sub_relation": sub_relation or "",
        "platforms": platforms or {}, "notes": notes,
        "memories": [],
        "important_dates": [],
        "created": date.today().isoformat(),
    }
    _apply_role_layers(contact)
    contacts.append(contact)
    _save(CONTACTS_FILE, contacts)
    return True, f"已添加联系人: {name}"

def get_contact(contact_id):
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            return c
    return None

def resolve_contact(query):
    """通过ID/姓名/别名/模糊匹配解析联系人。

    查找顺序：
    1. 精确ID匹配
    2. 精确姓名匹配
    3. 别名匹配（alias字段）
    4. 姓名包含匹配（模糊搜索）
    5. 全字段模糊搜索（取最高分）

    Returns: (contact, match_type) 或 (None, None)
    """
    contacts = _load(CONTACTS_FILE)
    q = query.strip()
    if not q:
        return None, None

    q_lower = q.lower()

    # 1. 精确ID
    for c in contacts:
        if c["id"] == q:
            return c, "id"

    # 2. 精确姓名
    for c in contacts:
        if c.get("name", "").lower() == q_lower:
            return c, "name"

    # 3. 别名匹配
    for c in contacts:
        aliases = c.get("alias", [])
        if isinstance(aliases, list):
            for a in aliases:
                if a.lower() == q_lower:
                    return c, "alias"
        elif isinstance(aliases, str) and aliases.lower() == q_lower:
            return c, "alias"

    # 4. 姓名包含（姓名以query开头或query包含在姓名中）
    candidates = []
    for c in contacts:
        name = c.get("name", "").lower()
        if name.startswith(q_lower) or q_lower in name:
            candidates.append((c, len(name)))  # 短的优先
    if candidates:
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0], "fuzzy_name"

    # 5. 全字段模糊搜索
    results = search_contacts(q)
    if results:
        return results[0], "fuzzy"

    return None, None

def update_contact(contact_id, updates):
    """更新联系人指定字段。updates为dict，支持：name, role, relation, sub_relation, strength, tags, notes, platforms, stage, full_name"""
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            changed = []
            for key, val in updates.items():
                if val is not None and key in ("name", "role", "relation", "sub_relation", "strength", "notes", "stage", "full_name"):
                    c[key] = val
                    changed.append(key)
                    # 同步 relation/role 保持一致性
                    if key == "role" and "relation" not in updates:
                        c["relation"] = val
                    elif key == "relation" and "role" not in updates:
                        c["role"] = val
                elif val is not None and key == "tags":
                    if isinstance(val, str):
                        val = [t.strip() for t in val.split() if t.strip()]
                    c["tags"] = list(set(c.get("tags", []) + val))
                    changed.append("tags")
                elif val is not None and key == "platforms":
                    if isinstance(val, dict):
                        c["platforms"].update(val)
                        changed.append("platforms")
            _apply_role_layers(c)
            _save(CONTACTS_FILE, contacts)
            return True, f"已更新 {contact_id}: {', '.join(changed)}"
    return False, f"未找到联系人: {contact_id}"

# ── 角色互动层数 (SPEC 0.3) ──

def role_layers(contact):
    """纯函数：计算联系人的角色互动层数列表（不修改联系人）。

    检测维度：职业层/校友层/组织层/社交层/合作层/家庭层
    """
    tags = set(t.lower() for t in contact.get("tags", []))
    relation = contact.get("relation", contact.get("role", "")).lower()
    sub = contact.get("sub_relation", "").lower()
    raw_notes_cl = contact.get("notes")
    if isinstance(raw_notes_cl, list):
        notes = " ".join(raw_notes_cl).lower() if raw_notes_cl else ""
    else:
        notes = str(raw_notes_cl or "").lower()

    layers = []

    # 职业层: 同行/同单位/同行业
    if any(k in tags for k in ("同行",)) or relation in ("同行",) or relation in ("合作",):
        layers.append("职层")
    elif any(k in sub for k in ("银行", "金融", "科技", "保险", "证券", "审计", "邮储", "华瑞")):
        layers.append("职层")

    # 校友层
    if "校友" in tags or relation == "校友":
        layers.append("校层")

    # 组织层: 同社团/协会
    if any(k in tags for k in ("民建", "协会", "社团", "党派", "会员")) or "民建" in notes:
        layers.append("组层")

    # 社交层: 群友/群
    if any(k in tags for k in ("群友", "群", "社交")):
        layers.append("群层")

    # 合作层: 创业/项目合作
    if any(k in tags for k in ("创业", "合作", "项目")) or relation in ("创业", "合作"):
        layers.append("合层")

    # 家庭层
    if relation == "family" or "家人" in tags or relation == "家人":
        layers.append("家层")

    # 去重
    return list(dict.fromkeys(layers))


def _apply_role_layers(contact):
    """计算联系人的角色互动层数，添加角色x1/x2/x3标签（修改联系人）。"""
    unique_layers = role_layers(contact)
    layer_count = len(unique_layers)

    # 移除旧的角色x标签
    new_tags = [t for t in contact.get("tags", []) if not t.startswith("角色x")]

    # 添加新的角色x标签
    if layer_count >= 3:
        new_tags.append("角色x3")
    elif layer_count == 2:
        new_tags.append("角色x2")
    elif layer_count == 1:
        new_tags.append("角色x1")

    contact["tags"] = new_tags
    contact["_layers"] = unique_layers
    return contact


def search_contacts(query, field=None):
    """全文搜索联系人。field可为name/tags/notes，不传则搜全部。"""
    contacts = _load(CONTACTS_FILE)
    q = query.lower()
    results = []
    for c in contacts:
        if field and field not in ("name", "tags", "notes", "memories"):
            field = None
        if field == "name":
            if q in c.get("name", "").lower():
                results.append(c)
        elif field == "tags":
            if any(q in t.lower() for t in c.get("tags", [])):
                results.append(c)
        elif field == "notes":
            raw_notes_s = c.get("notes")
            if isinstance(raw_notes_s, list):
                notes_text = " ".join(raw_notes_s) if raw_notes_s else ""
            else:
                notes_text = str(raw_notes_s or "")
            if q in notes_text.lower():
                results.append(c)
        elif field == "memories":
            if any(q in m.get("content", "").lower() for m in c.get("memories", [])):
                results.append(c)
        else:
            # 全字段搜索
            score = 0
            if q in c.get("name", "").lower():
                score += 10
            if c.get("id") and q in c["id"].lower():
                score += 8
            if any(q in t.lower() for t in c.get("tags", [])):
                score += 5
            raw_notes = c.get("notes")
            if isinstance(raw_notes, list):
                notes_text = " ".join(raw_notes) if raw_notes else ""
            else:
                notes_text = str(raw_notes or "")
            if q in notes_text.lower():
                score += 3
            if any(q in m.get("content", "").lower() for m in c.get("memories", [])):
                score += 3
            if score > 0:
                results.append((score, c))
    if results and isinstance(results[0], tuple):
        results.sort(key=lambda x: -x[0])
        results = [r[1] for r in results]
    return results

def add_memory(contact_id, content, tags=None):
    """为联系人添加一条结构化记忆。"""
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            if "memories" not in c:
                c["memories"] = []
            memory = {
                "id": f"mem-{uuid.uuid4().hex[:6]}",
                "content": content,
                "tags": tags or [],
                "created": datetime.now().isoformat(),
            }
            c["memories"].append(memory)
            _save(CONTACTS_FILE, contacts)
            # 轻度提升强度：上级领导/家人可到5，其他不超过4
            max_strength = 5 if c.get("relation") in ("上级领导", "family", "家人") else 4
            if c.get("strength", 3) < max_strength and c.get("strength", 3) >= 1 and c.get("relation") != "self":
                old_s = c["strength"]
                c["strength"] = min(old_s + 1, max_strength)
                _save(CONTACTS_FILE, contacts)
                return True, f"已添加记忆: {content[:30]}...（强度{old_s}→{c['strength']}）"
            return True, f"已添加记忆: {content[:30]}..."
    return False, f"未找到联系人: {contact_id}"

def extract_birthday(text):
    """从文本中提取生日信息，返回 (月, 日) 或 None。"""
    # 匹配 "X月X日" 或 "XX月XX日" 或 "1129" 格式
    patterns = [
        (r"(\d{1,2})月(\d{1,2})[日号]", lambda m: (int(m.group(1)), int(m.group(2)))),
        (r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]", lambda m: (int(m.group(2)), int(m.group(3)))),
    ]
    for pat, fn in patterns:
        m = re.search(pat, text)
        if m:
            return fn(m)
    # 四位数数字如1129
    m = re.search(r"\b(?:生日[:：\s]*)?(\d{4})\b", text)
    if m:
        n = int(m.group(1))
        if 101 <= n <= 1231:
            return (n // 100, n % 100)
    return None

def get_birthdays(days=30):
    """获取未来days天内有生日的联系人。"""
    contacts = _load(CONTACTS_FILE)
    today = date.today()
    results = []

    for c in contacts:
        # 从notes中提取
        raw_notes_bd = c.get("notes")
        if isinstance(raw_notes_bd, list):
            notes_bd = " ".join(raw_notes_bd) if raw_notes_bd else ""
        else:
            notes_bd = str(raw_notes_bd or "")
        bd = extract_birthday(notes_bd)
        # 从memories中提取
        if not bd:
            for m in c.get("memories", []):
                bd = extract_birthday(m.get("content", ""))
                if bd:
                    break
        # 从important_dates字段提取
        if not bd:
            for d_entry in c.get("important_dates", []):
                if "生日" in d_entry.get("type", ""):
                    parts = d_entry.get("date", "").split("-")
                    if len(parts) >= 2:
                        bd = (int(parts[0]), int(parts[1]))

        if bd:
            month, day = bd
            try:
                bd_this_year = date(today.year, month, day)
                if bd_this_year < today:
                    bd_this_year = date(today.year + 1, month, day)
                delta = (bd_this_year - today).days
                if 0 <= delta <= days:
                    results.append({
                        "contact": c["name"],
                        "id": c["id"],
                        "birthday": f"{month}月{day}日",
                        "days_left": delta,
                        "age": today.year - 1964 if "1964" in notes_bd else None,
                    })
            except ValueError:
                pass

    results.sort(key=lambda r: r["days_left"])
    return results

# ── Timeline ──

def list_timeline(contact=None, days=30):
    records = _load(TIMELINE_FILE)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    records = [r for r in records if r.get("date", "") >= cutoff]
    if contact:
        records = [r for r in records if r.get("contact") == contact]
    return sorted(records, key=lambda r: r.get("date", ""), reverse=True)

def add_timeline(contact, summary, type_="message", key_points=None, pending=""):
    records = _load(TIMELINE_FILE)
    # Auto-extract pending and key points using AI if not provided
    if not pending and not key_points:
        ai_result = _ai_extract(contact, summary)
        if ai_result:
            pending = ai_result.get("pending", pending)
            key_points = ai_result.get("key_points", key_points or [])
    record = {
        "id": f"t-{uuid.uuid4().hex[:6]}",
        "date": date.today().isoformat(),
        "contact": contact, "type": type_,
        "summary": summary, "pending": pending,
        "key_points": key_points or [],
        "created": datetime.now().isoformat(),
    }
    records.append(record)
    _save(TIMELINE_FILE, records)
    if pending:
        _auto_add_todo(contact, pending, record["id"])
    return record

def _ai_extract(contact, summary):
    try:
        import subprocess, json as _json
        prompt = f"""从这条互动记录中提取待办事项和关键信息。

联系人：{contact}
互动记录：{summary}

请以JSON格式返回：
{{"pending": "如果有需要跟进的事用一句话描述（没有就留空）",
  "key_points": ["关键点1", "关键点2"]}}"""
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=15,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return _json.loads(text[start:end])
    except:
        pass
    return None
    if pending:
        _auto_add_todo(contact, pending, record["id"])
    return record

def _auto_add_todo(contact, task, source_id):
    todos = _load(TODOS_FILE)
    # Auto-detect priority
    priority = "P1"
    if any(kw in task for kw in ["TS", "投资", "融资", "条款", "DD"]):
        priority = "P0"
    elif any(kw in task for kw in ["引荐", "会面", "签约"]):
        priority = "P0"
    # Auto-set due date (3 days for P0, 7 days for P1)
    days = 3 if priority == "P0" else 7
    due = (date.today() + timedelta(days=days)).isoformat()

    todo = {
        "id": f"todo-{uuid.uuid4().hex[:6]}",
        "contact": contact, "due": due,
        "task": task, "priority": priority,
        "status": "pending", "source": source_id,
        "created": datetime.now().isoformat(),
    }
    todos.append(todo)
    _save(TODOS_FILE, todos)
    return todo

# ── Todos ──

STALE_TODO_DAYS = 30

def list_todos(priority=None, status="pending"):
    todos = _load(TODOS_FILE)
    if status:
        todos = [t for t in todos if t.get("status") == status]
    if priority:
        todos = [t for t in todos if t.get("priority") == priority]
    # 字段归一化（不落盘）：部分写入方用 content 而非 task
    for t in todos:
        if "task" not in t and t.get("content"):
            t["task"] = t["content"]
    # 待办老化标注（SPEC v4 §17）：pending 超30天未动 → stale=True（仅标注，不取消，核心规则3）
    today = date.today()
    for t in todos:
        if t.get("status") == "pending":
            created = str(t.get("created", ""))[:10]
            try:
                age = (today - date.fromisoformat(created)).days
            except ValueError:
                continue
            if age >= STALE_TODO_DAYS:
                t["stale"] = True
                t["stale_days"] = age
    # Sort: P0 first, then by due date
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    todos.sort(key=lambda t: (priority_order.get(t.get("priority", "P2"), 9), t.get("due", "")))
    return todos

def complete_todo(todo_id):
    todos = _load(TODOS_FILE)
    for t in todos:
        if t["id"] == todo_id:
            t["status"] = "completed"
            t["completed_at"] = datetime.now().isoformat()
            _save(TODOS_FILE, todos)
            # 自动写入时间线
            try:
                timeline = _load(TIMELINE_FILE)
                timeline.append({
                    "id": f"auto-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    "type": "task_completed",
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "title": f"✅ 完成: {t['task'][:40]}",
                    "detail": f"{t.get('contact','')}: {t['task'][:80]}",
                    "source": "auto-complete-todo"
                })
                _save(TIMELINE_FILE, timeline)
            except Exception:
                pass  # 时间线写入失败不影响待办本身
            return True, f"已完成: {t['task']}"
    return False, "未找到该待办"

# ── Dashboard ──

def get_dashboard(scope="core"):
    """仪表盘。scope="core" 冷却检查只扫核心圈（strength≥3）；scope="all" 扫全量。"""
    contacts = _load(CONTACTS_FILE)
    todos = list_todos()
    timeline = list_timeline(days=7)

    # Count by role
    roles = {}
    for c in contacts:
        r = c.get("role", "其他")
        roles[r] = roles.get(r, 0) + 1

    # Count overdue todos
    today = date.today().isoformat()
    overdue = [t for t in todos if t.get("due", "") < today and t.get("status") == "pending"]

    # Health check: relationships not contacted（默认仅 core 层，SPEC v4 §17）
    timeline_all = _load(TIMELINE_FILE)
    cold = []   # 21天+ 🔴
    warm = []   # 14-20天 🟡
    scan = contacts if scope == "all" else [c for c in contacts if contact_tier(c) == "core"]
    for c in scan:
        # 跳过自己
        if c.get("relation") == "self" or c.get("id") == "陈颖芳":
            continue
        last = max((r.get("date", "") for r in timeline_all
                    if r.get("contact") == c["id"]), default="")
        if last:
            days_since = (date.today() - date.fromisoformat(last)).days
            if days_since >= 21:
                cold.append({"contact": c["name"], "days": days_since, "level": "🔴"})
            elif days_since >= 14:
                warm.append({"contact": c["name"], "days": days_since, "level": "🟡"})
        else:
            # 无任何时间线记录的，视为超长期冷却
            cold.append({"contact": c["name"], "days": 999, "level": "🔴", "never_recorded": True})

    return {
        "total_contacts": len(contacts),
        "by_role": roles,
        "pending_todos": len(todos),
        "overdue_todos": overdue,
        "recent_activities": len(timeline),
        "cold_relationships": cold,
        "warm_relationships": warm,
    }

# ── 自动强度调整 ──

def auto_adjust_strength():
    """基于时间线和关系方法论，自动分析需调整的强度。

    规则：
    - 强度5（家人）：永不自动调整
    - 强度4（领导/引路人）：90天无互动→建议降3；180天无互动→建议降2
    - 强度3（较熟）：90天无互动→建议降2；180天无互动→建议降1
    - 强度2（普通）：永不自动调整（已足够低）
    - 强度1（弱关系）：永不自动调整（已最低）
    - 互动频率高（60天内≥2次）且强度<4→建议升1
    """
    contacts = _load(CONTACTS_FILE)
    timeline = _load(TIMELINE_FILE)
    today = date.today()
    suggestions = []

    for c in contacts:
        sid = c["id"]
        s = c.get("strength", 1)
        name = c.get("name", "?")
        rel = c.get("relation", "")

        # 跳过不可调整的
        if s >= 5 or s <= 2:
            continue
        if rel == "self":
            continue

        # 获取该联系人最近互动
        contact_records = [r for r in timeline if r.get("contact") == sid]
        if not contact_records:
            continue

        last_date_str = max(r.get("date", "") for r in contact_records)
        try:
            last_date = date.fromisoformat(last_date_str)
            days_since = (today - last_date).days
        except:
            continue

        # 近60天互动频率
        cutoff_60 = (today - timedelta(days=60)).isoformat()
        recent_count = len([r for r in contact_records if r.get("date", "") >= cutoff_60])

        # 降级
        if s == 4:
            if days_since >= 180:
                suggestions.append({"contact_id": sid, "name": name, "current": s, "suggested": 2, "reason": f"{days_since}天无互动，建议从4降为2"})
            elif days_since >= 90:
                suggestions.append({"contact_id": sid, "name": name, "current": s, "suggested": 3, "reason": f"{days_since}天无互动，建议从4降为3"})
        elif s == 3:
            if days_since >= 180:
                suggestions.append({"contact_id": sid, "name": name, "current": s, "suggested": 1, "reason": f"{days_since}天无互动，建议从3降为1"})
            elif days_since >= 90:
                suggestions.append({"contact_id": sid, "name": name, "current": s, "suggested": 2, "reason": f"{days_since}天无互动，建议从3降为2"})

        # 升级（互动频繁且强度不高）
        if recent_count >= 2 and s < 4:
            suggestions.append({"contact_id": sid, "name": name, "current": s, "suggested": min(s + 1, 4), "reason": f"近60天互动{recent_count}次，建议从{s}升为{min(s+1,4)}"})

    # 去重：升降冲突时降级优先
    final = {}
    for sug in suggestions:
        cid = sug["contact_id"]
        if cid in final:
            if sug["suggested"] < sug["current"]:
                final[cid] = sug
        else:
            final[cid] = sug
    return list(final.values())

def apply_adjustment(contact_id, new_strength):
    """执行一条强度调整建议。"""
    return update_contact(contact_id, {"strength": new_strength})


# ── v2.5.0 批量画像补全 ──

def _enrich_priority(contact):
    """计算联系人画像补全优先级（分数越高越优先处理）。
    
    注意：外部调用处应在循环前过滤已处理联系人，本函数不负责版本过滤。
    """
    strength = contact.get("strength", 1)
    relation = contact.get("relation", "") or contact.get("role", "")
    raw_notes = contact.get("notes")
    if isinstance(raw_notes, list):
        notes = " ".join(raw_notes) if raw_notes else ""
    else:
        notes = str(raw_notes or "")
    tags = contact.get("tags", []) or []
    memories = contact.get("memories", []) or []

    # 按信息密度从高到低排序
    if strength >= 3 and not relation:
        score = 100
    elif notes.strip() and not relation:
        score = 80
    elif tags and not relation:
        score = 60
    elif memories and not relation:
        score = 40
    elif notes.strip() or tags or memories:
        score = 20
    else:
        score = 10  # 仅有名称

    # 强度加成：越重要的关系越优先补全
    score += strength * 2
    return score


def get_enrichment_candidates(batch_size=10, force=False):
    """获取下一批待画像补全的联系人，按优先级排序。

    Args:
        batch_size: 批次大小（默认10）
        force: 是否重新处理已补全的联系人

    Returns:
        list[dict]: 联系人列表
    """
    contacts = _load(CONTACTS_FILE)
    scored = []
    for c in contacts:
        version = c.get("_enrich_version", 0)
        if version > 0 and not force:
            continue
        # 在 force 模式下仍给已处理联系人打分
        if version > 0 and force:
            score = _enrich_priority(c) + 1000  # 优先处理已有的（刷新）
        else:
            score = _enrich_priority(c)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:batch_size]]


def get_enrichment_stats():
    """返回画像补全统计信息。"""
    contacts = _load(CONTACTS_FILE)
    enriched = [c for c in contacts if c.get("_enrich_version", 0) > 0]
    pending = [c for c in contacts if c.get("_enrich_version", 0) == 0]

    # 按 relation 统计已补全的
    by_relation = {}
    for c in enriched:
        r = c.get("relation", c.get("role", "未知"))
        by_relation[r] = by_relation.get(r, 0) + 1

    # 待补全按强度分布
    by_strength = {}
    for c in pending:
        s = c.get("strength", 0)
        by_strength[s] = by_strength.get(s, 0) + 1

    return {
        "total": len(contacts),
        "enriched": len(enriched),
        "pending": len(pending),
        "pending_pct": round(len(pending) / max(len(contacts), 1) * 100, 1),
        "by_relation": by_relation,
        "by_strength_pending": dict(sorted(by_strength.items())),
    }


def mark_enriched(contact_id):
    """将联系人标记为已补全（_enrich_version += 1）。"""
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            c["_enrich_version"] = c.get("_enrich_version", 0) + 1
            _save(CONTACTS_FILE, contacts)
            return True
    return False


# ── 目标锚定 leverage (SPEC v4 §18) ──

def load_goals():
    """读取 config/goals.yaml 的目标框架。

    返回 {"goals": [...], "directions": [...]}。
    文件缺失时返回默认六维框架（与 SPEC §18.1 一致）。
    """
    home = _get_home_dir()
    paths = [
        home / "config" / "goals.local.yaml",
        home / "config" / "goals.yaml",
    ]
    for p in paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {
                "goals": data.get("goals", []),
                "directions": data.get("directions", ["我求于他", "他求于我", "互惠"]),
            }
    # 默认六维（SPEC §18.1）
    return {
        "goals": ["事业", "投资", "家庭", "健康", "AI能力", "知识"],
        "directions": ["我求于他", "他求于我", "互惠"],
    }


def get_leverage(contact_id):
    """读取联系人 leverage 字段。无则返回 None。"""
    c = get_contact(contact_id)
    if not c:
        return None
    return c.get("leverage")


def set_leverage(contact_id, goals, how, direction, confirmed=None):
    """写入 leverage 字段（SPEC v4 §18.2）。

    Args:
        contact_id: 联系人 ID
        goals: 目标维度列表（如 ["事业", "AI能力"]）
        how: 撬动方式一句话
        direction: 我求于他 / 他求于我 / 互惠
        confirmed: 确认日期（ISO 字符串）；None 表示仅 AI 建议、未生效

    Returns:
        (ok, msg)
    """
    valid_dirs = load_goals()["directions"]
    if direction not in valid_dirs:
        return False, f"direction 非法：{direction}，可选 {valid_dirs}"

    leverage = {
        "goals": list(goals),
        "how": how,
        "direction": direction,
        "confirmed": confirmed,
    }
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            c["leverage"] = leverage
            _save(CONTACTS_FILE, contacts)
            return True, f"已锚定 {c.get('name', contact_id)}: goals={goals}, direction={direction}"
    return False, f"未找到联系人: {contact_id}"


def list_unanchored(min_strength=None, tier="core", limit=None):
    """列出未锚定（无 leverage 或 leverage.confirmed 为空）的联系人。

    排序：strength 降序 → name 升序（先锚定高强度，SPEC §18.3）。

    Args:
        min_strength: 仅返回 strength≥此值的联系人（None=按 tier 过滤）
        tier: "core"（默认）/ "reserve" / None（不限）
        limit: 最多返回条数
    """
    contacts = _load(CONTACTS_FILE)
    result = []
    for c in contacts:
        if c.get("relation") == "self":
            continue
        s = c.get("strength", 1)
        if min_strength is not None and s < min_strength:
            continue
        if tier is not None and contact_tier(c) != tier:
            continue
        lev = c.get("leverage")
        if not lev or not lev.get("confirmed"):
            result.append(c)
    result.sort(key=lambda c: (-c.get("strength", 1), c.get("name", c.get("id", ""))))
    if limit:
        result = result[:limit]
    return result


def list_anchored(tier=None):
    """列出已锚定（leverage.confirmed 非空）的联系人。"""
    contacts = _load(CONTACTS_FILE)
    result = []
    for c in contacts:
        if tier is not None and contact_tier(c) != tier:
            continue
        lev = c.get("leverage")
        if lev and lev.get("confirmed"):
            result.append(c)
    return result


def anchor_stats():
    """返回锚定进度统计（SPEC v4 §18.3）。"""
    contacts = _load(CONTACTS_FILE)
    core = [c for c in contacts if contact_tier(c) == "core" and c.get("relation") != "self"]
    anchored = [c for c in core if c.get("leverage", {}).get("confirmed")]
    pending = [c for c in core if not c.get("leverage", {}).get("confirmed")]

    # 按强度分布
    by_strength_anchored = {}
    by_strength_pending = {}
    for c in anchored:
        s = c.get("strength", 1)
        by_strength_anchored[s] = by_strength_anchored.get(s, 0) + 1
    for c in pending:
        s = c.get("strength", 1)
        by_strength_pending[s] = by_strength_pending.get(s, 0) + 1

    # 按目标维度分布（已锚定）
    by_goal = {}
    for c in anchored:
        for g in c.get("leverage", {}).get("goals", []):
            by_goal[g] = by_goal.get(g, 0) + 1

    # 按 direction 分布
    by_direction = {}
    for c in anchored:
        d = c.get("leverage", {}).get("direction", "?")
        by_direction[d] = by_direction.get(d, 0) + 1

    return {
        "core_total": len(core),
        "anchored": len(anchored),
        "pending": len(pending),
        "anchored_pct": round(len(anchored) / max(len(core), 1) * 100, 1),
        "by_strength_anchored": dict(sorted(by_strength_anchored.items(), reverse=True)),
        "by_strength_pending": dict(sorted(by_strength_pending.items(), reverse=True)),
        "by_goal": by_goal,
        "by_direction": by_direction,
    }


# ── 兑现追踪 outcome (SPEC v4 §20) ──

def add_outcome(contact, summary, goal=None, date_str=None):
    """记录一条 outcome（成果）到 timeline。

    SPEC v4 §20.1: timeline type=outcome，含 goal 关联。
    只做可追溯记录，不算 ROI（原则七）。

    Args:
        contact: 联系人 ID
        summary: 成果摘要（如"经张总引荐认识XX行科技部负责人"）
        goal: 关联的六维目标之一（可空）
        date_str: 日期（默认今日）

    Returns:
        timeline record dict
    """
    records = _load(TIMELINE_FILE)
    record = {
        "id": f"t-{uuid.uuid4().hex[:6]}",
        "date": date_str or date.today().isoformat(),
        "contact": contact,
        "type": "outcome",
        "summary": summary,
        "goal": goal,
        "key_points": [],
        "pending": "",
        "created": datetime.now().isoformat(),
    }
    records.append(record)
    _save(TIMELINE_FILE, records)
    return record


def list_outcomes(contact=None, goal=None, year=None, limit=None):
    """查询 outcome 记录（SPEC v4 §20.2）。

    Args:
        contact: 过滤联系人 ID
        goal: 过滤目标维度
        year: 过滤年份（int 或 str）
        limit: 最多返回条数

    Returns:
        list of timeline records (type=outcome)，按日期降序
    """
    records = _load(TIMELINE_FILE)
    outcomes = [r for r in records if r.get("type") == "outcome"]
    if contact:
        outcomes = [r for r in outcomes if r.get("contact") == contact]
    if goal:
        outcomes = [r for r in outcomes if r.get("goal") == goal]
    if year:
        year_str = str(year)
        outcomes = [r for r in outcomes if r.get("date", "").startswith(year_str)]
    outcomes.sort(key=lambda r: r.get("date", ""), reverse=True)
    if limit:
        outcomes = outcomes[:limit]
    return outcomes


def outcome_stats(year=None):
    """返回 outcome 统计（按目标维度/按联系人/按月份分布）。"""
    outcomes = list_outcomes(year=year)
    by_goal = {}
    by_contact = {}
    by_month = {}
    for r in outcomes:
        g = r.get("goal") or "未标注"
        by_goal[g] = by_goal.get(g, 0) + 1
        c = r.get("contact", "?")
        by_contact[c] = by_contact.get(c, 0) + 1
        m = r.get("date", "")[:7]
        if m:
            by_month[m] = by_month.get(m, 0) + 1
    return {
        "total": len(outcomes),
        "by_goal": dict(sorted(by_goal.items(), key=lambda x: -x[1])),
        "by_contact": dict(sorted(by_contact.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
    }


# ── 建议引擎 advise (SPEC v4 §19) ──

def _days_since_last(contact):
    """距上次互动天数（基于 timeline）。"""
    cid = contact.get("id")
    if not cid:
        return 9999
    tls = list_timeline(contact=cid, days=9999)
    if not tls:
        return 9999
    last_date = tls[0].get("date", "")
    if not last_date:
        return 9999
    try:
        d = date.fromisoformat(last_date)
        return (date.today() - d).days
    except (ValueError, TypeError):
        return 9999


def _has_upcoming_birthday(contact, days=14):
    """未来 N 天内是否有生日。"""
    cid = contact.get("id")
    if not cid:
        return False, None
    bdays = get_birthdays(days=days)
    for b in bdays:
        if b.get("id") == cid or b.get("contact") == cid:
            return True, b
    return False, None


def _has_pending_todo(contact):
    """该联系人是否有 pending 待办。"""
    cid = contact.get("id")
    if not cid:
        return False, None
    todos = list_todos(status="pending")
    for t in todos:
        if t.get("contact") == cid:
            return True, t
    return False, None


def advise_candidates(top=5, tier="core"):
    """聚合多信号源生成本周经营建议候选（SPEC v4 §19.1）。

    信号源（均为已有数据，原则六：信号先行）：
    1. 冷却状态（14/21天未联系 → 红/黄）
    2. health 分（低分优先）
    3. important_dates（未来14天生日）
    4. leverage 锚定（有锚定的优先——why 已明确）
    5. timeline 上下文（上次聊什么→聊什么）
    6. todos（有 pending 待办优先）

    排序：综合得分降序，取 top N（SPEC §19.2: 3-5 条封顶）。

    Returns:
        list of dict: [{"contact": {...}, "signals": [...], "score": N, "last_interaction": str, "leverage": {...}|None}]
    """
    contacts = list_contacts(tier=tier)
    candidates = []

    for c in contacts:
        if c.get("relation") == "self":
            continue
        cid = c["id"]
        signals = []
        score = 0

        # 信号1: 冷却状态
        days_since = _days_since_last(c)
        if days_since >= 21:
            signals.append(f"{days_since}天未联系🔴")
            score += 30
        elif days_since >= 14:
            signals.append(f"{days_since}天未联系🟡")
            score += 20
        elif days_since == 9999:
            signals.append("从未联系🔴")
            score += 25
        elif days_since <= 3:
            # 刚联系过，降权
            score -= 10

        # 信号2: 生日
        has_bday, bday_info = _has_upcoming_birthday(c, days=14)
        if has_bday:
            signals.append(f"即将生日（{bday_info.get('date', '?')}）")
            score += 35

        # 信号3: leverage 锚定（有锚定的优先——why 已明确）
        lev = c.get("leverage")
        if lev and lev.get("confirmed"):
            goals_str = "/".join(lev.get("goals", []))
            signals.append(f"锚定[{goals_str}]")
            score += 15

        # 信号4: pending 待办
        has_todo, todo_info = _has_pending_todo(c)
        if has_todo:
            task = todo_info.get("task", todo_info.get("content", ""))
            signals.append(f"待办: {task[:30]}")
            score += 25

        # 信号5: 强度加分（高强度关系更值得维护）
        s = c.get("strength", 1)
        score += s * 2

        if score > 0 and signals:
            # 获取上次互动摘要
            tls = list_timeline(contact=cid, days=9999)
            last_summary = tls[0].get("summary", "") if tls else ""
            candidates.append({
                "contact": c,
                "signals": signals,
                "score": score,
                "days_since": days_since,
                "last_interaction": last_summary,
                "leverage": lev,
                "has_birthday": has_bday,
                "birthday_info": bday_info,
                "has_todo": has_todo,
                "todo_info": todo_info,
            })

    candidates.sort(key=lambda x: -x["score"])
    return candidates[:top]
