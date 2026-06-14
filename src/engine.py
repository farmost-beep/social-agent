"""Core engine for Social Relationship AI Agent."""
import json, os, uuid, re, yaml
from datetime import datetime, date, timedelta
from pathlib import Path

# ── 配置加载 ──

def _load_config():
    """读取 config.yaml，如不存在则使用默认值。"""
    config_paths = [
        Path(__file__).resolve().parent.parent / "config" / "config.local.yaml",
        Path(__file__).resolve().parent.parent / "config" / "config.yaml",
    ]
    for cp in config_paths:
        if cp.exists():
            with open(cp, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}

_CONFIG = _load_config()
_DATA_DIR = Path(_CONFIG.get("data_dir", str(Path(__file__).resolve().parent.parent / "data")))

CONTACTS_FILE = _DATA_DIR / "contacts.json"
TIMELINE_FILE = _DATA_DIR / "timeline.json"
TODOS_FILE = _DATA_DIR / "todos.json"

def _load(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Contacts ──

def list_contacts(role=None, tag=None):
    contacts = _load(CONTACTS_FILE)
    if role:
        contacts = [c for c in contacts if c.get("role") == role or c.get("sub_relation") == role]
    if tag:
        contacts = [c for c in contacts if tag in c.get("tags", [])]
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
        "strength": 3, "tags": tags or [],
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

def _apply_role_layers(contact):
    """计算联系人的角色互动层数，添加角色x1/x2/x3标签。

    检测维度：职业层/校友层/组织层/社交层/合作层/家庭层
    """
    tags = set(t.lower() for t in contact.get("tags", []))
    relation = contact.get("relation", contact.get("role", "")).lower()
    sub = contact.get("sub_relation", "").lower()
    notes = contact.get("notes", "").lower()

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

    # 去重并计算层数
    unique_layers = list(dict.fromkeys(layers))
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
            if q in c.get("notes", "").lower():
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
            if q in c.get("notes", "").lower():
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
            # 轻度提升强度（不超过4），不碰5级家人
            if c.get("strength", 3) < 4 and c.get("strength", 3) >= 1 and c.get("relation") != "family" and c.get("relation") != "self":
                old_s = c["strength"]
                c["strength"] = min(old_s + 1, 4)
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
        bd = extract_birthday(c.get("notes", ""))
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
                        "age": today.year - 1964 if "1964" in c.get("notes", "") else None,
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

def list_todos(priority=None, status="pending"):
    todos = _load(TODOS_FILE)
    if status:
        todos = [t for t in todos if t.get("status") == status]
    if priority:
        todos = [t for t in todos if t.get("priority") == priority]
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
            return True, f"已完成: {t['task']}"
    return False, "未找到该待办"

# ── Dashboard ──

def get_dashboard():
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

    # Health check: relationships not contacted
    timeline_all = _load(TIMELINE_FILE)
    cold = []   # 21天+ 🔴
    warm = []   # 14-20天 🟡
    for c in contacts:
        last = max((r.get("date", "") for r in timeline_all
                    if r.get("contact") == c["id"]), default="")
        if last:
            days_since = (date.today() - date.fromisoformat(last)).days
            if days_since >= 21:
                cold.append({"contact": c["name"], "days": days_since, "level": "🔴"})
            elif days_since >= 14:
                warm.append({"contact": c["name"], "days": days_since, "level": "🟡"})

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
