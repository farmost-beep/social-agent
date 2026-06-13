"""Core engine for Social Relationship AI Agent."""
import json, os, uuid
from datetime import datetime, date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CONTACTS_FILE = DATA_DIR / "contacts.json"
TIMELINE_FILE = DATA_DIR / "timeline.json"
TODOS_FILE = DATA_DIR / "todos.json"

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
        contacts = [c for c in contacts if c.get("role") == role]
    if tag:
        contacts = [c for c in contacts if tag in c.get("tags", [])]
    return contacts

def add_contact(contact_id, name, role, tags=None, platforms=None, notes=""):
    contacts = _load(CONTACTS_FILE)
    if any(c["id"] == contact_id for c in contacts):
        return False, f"联系人 {contact_id} 已存在"
    contacts.append({
        "id": contact_id, "name": name, "role": role, "stage": "",
        "strength": 3, "tags": tags or [],
        "platforms": platforms or {}, "notes": notes,
        "created": date.today().isoformat(),
    })
    _save(CONTACTS_FILE, contacts)
    return True, f"已添加联系人: {name}"

def get_contact(contact_id):
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            return c
    return None

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

    # Health check: relationships not contacted in 21+ days
    cold = []
    for c in contacts:
        last = max((r.get("date", "") for r in _load(TIMELINE_FILE)
                    if r.get("contact") == c["id"]), default="")
        if last:
            days_since = (date.today() - date.fromisoformat(last)).days
            if days_since >= 21:
                cold.append({"contact": c["name"], "days": days_since})

    return {
        "total_contacts": len(contacts),
        "by_role": roles,
        "pending_todos": len(todos),
        "overdue_todos": overdue,
        "recent_activities": len(timeline),
        "cold_relationships": cold,
    }
