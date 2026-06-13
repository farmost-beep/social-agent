"""Intent recognition - turns natural language into engine actions."""
import re, subprocess, json
from datetime import date, datetime
from lib.engine import *
from lib.ai import draft_message
from lib.push import push_to_wechat, send_message

def parse(text):
    """Parse user message and return action dict."""
    text = text.strip()

    # "记一下：xxx" or "记录：xxx"
    m = re.match(r'^(记[一下录]?[：:]?)\s*(.+)', text)
    if m:
        content = m.group(2)
        return _parse_log(content)

    # "xxx最近咋样/最近什么情况/怎么样了"
    m = re.match(r'^(.{1,8})最近(咋样|什么情况|怎么样|如何|怎样)', text)
    if m or text.endswith('最近咋样') or text.endswith('最近怎么样'):
        name = (m.group(1) if m else text[:-4]).strip()
        return {"action": "query", "contact": _find_contact(name)}

    # "帮我想想该联系谁" or "最近该联系谁"
    if any(kw in text for kw in ['该联系谁', '该找谁', '联系谁', '找谁聊']):
        return {"action": "check_reminders"}

    # "拟条消息给xxx" or "给xxx拟条消息"
    m = re.match(r'(?:拟[条个]?消息给|给)(.{1,8}?)(?:拟[条个]?消息)?[，,]?\s*(.*)', text)
    if m:
        name = m.group(1)
        topic = m.group(2).strip()
        return {"action": "draft", "contact": _find_contact(name), "topic": topic, "tone": "亲切"}

    # "发消息给xxx说..." or "告诉xxx..."
    m = re.match(r'(?:发消息给|告诉|通知)(.{1,8}?)(?:说|[，,：:])\s*(.+)', text)
    if m:
        return {"action": "send", "contact": _find_contact(m.group(1)), "text": m.group(2)}

    # "最近有啥要跟进的" or "待办" or "有什么待办"
    if any(kw in text for kw in ['待办', '跟进', '要做什么', '有什么事']):
        return {"action": "todos"}

    # "查xxx" - query contact
    m = re.match(r'^查[看询]?\s*(.{1,8})', text)
    if m:
        return {"action": "query", "contact": _find_contact(m.group(1))}

    # "xxx这人有谁/在哪" - might be adding context
    m = re.match(r'^(.{1,8})(?:这人|是谁|是干什么的)', text)
    if m:
        name = m.group(1).strip()
        c = _find_contact_obj(name)
        if c:
            return {"action": "query", "contact": c["id"]}
        return {"action": "unknown", "text": text}

    # Default: try to understand via Claude
    return {"action": "ai_understand", "text": text}

def _find_contact(name):
    """Find contact ID by name."""
    contacts = list_contacts()
    for c in contacts:
        if c["name"] == name or c["id"] == name:
            return c["id"]
    # Fuzzy match
    for c in contacts:
        if name in c["name"] or name in c["id"]:
            return c["id"]
    return name  # Return as-is if not found

def _find_contact_obj(name):
    contacts = list_contacts()
    for c in contacts:
        if c["name"] == name or c["id"] == name:
            return c
    for c in contacts:
        if name in c["name"] or name in c["id"]:
            return c
    return None

def _parse_log(content):
    """Parse '记一下: xxx' content."""
    # Try to extract who and what
    contacts = list_contacts()
    mentioned = None
    for c in contacts:
        if c["name"] in content or c["id"] in content:
            mentioned = c
            break

    result = {"action": "log", "summary": content}

    # Try to extract contact from pattern like "和张总聊了..."
    m = re.match(r'和(.{2,4})(?:[聊谈约]|聊了|谈了|约了|沟通|吃饭|见面|通话)', content)
    if m:
        name = m.group(1)
        c = _find_contact_obj(name)
        if c:
            result["contact"] = c["id"]

    if not result.get("contact") and mentioned:
        result["contact"] = mentioned["id"]

    # Detect meeting/call/message types
    if any(kw in content for kw in ['见面', '吃饭', '咖啡', '约', '国贸']):
        result["type"] = "meeting"
    elif any(kw in content for kw in ['电话', '通话']):
        result["type"] = "call"
    elif any(kw in content for kw in ['邮件', 'email']):
        result["type"] = "email"
    else:
        result["type"] = "message"

    return result

def execute(action):
    """Execute the parsed action and return response text."""
    act = action.get("action", "unknown")

    if act == "log":
        contact = action.get("contact")
        summary = action.get("summary", "")
        type_ = action.get("type", "message")
        if contact:
            record = add_timeline(contact, summary, type_=type_)
            reply = f"已记录。"
            if record.get("pending"):
                reply += f"\n待办已建：{record['pending']}"
            return reply
        else:
            # Auto-create contact from "和XXX聊" pattern
            # Extract name from "和XXX聊/谈/约/吃饭/见面..." patterns
            m = re.search(r'和(.{2,4})(?:[聊谈约]|聊了|谈了|约了|沟通|吃饭|见面|通话|开了)', summary)
            if m:
                name = m.group(1).strip()
                if not _find_contact_obj(name):
                    cid = name[:20]
                    add_contact(cid, name, "其他", [], None, f"自动创建 {date.today()}")
                    add_timeline(cid, summary, type_=type_)
                    return f"已添加联系人「{name}」并记录。\n告诉我「{name}是什么关系」可以分类。"
            return f"已记录：{summary}\n（未识别到联系人，直接说名字就行）"

    elif act == "query":
        contact_id = action.get("contact")
        c = get_contact(contact_id)
        if not c:
            return f"未找到联系人：{contact_id}\n试试「记一下：和{contact_id}聊了什么」先建档案"
        records = list_timeline(contact=contact_id, days=90)
        if records:
            r = records[0]
            reply = f"{c['name']}（{c.get('role','?')}）"
            if c.get("stage"):
                reply += f" | 阶段：{c['stage']}"
            reply += f"\n\n最近：{r['date']} {r['summary'][:60]}"
            if r.get("pending"):
                reply += f"\n待办：{r['pending']}"
            return reply
        return f"{c['name']}暂无互动记录"

    elif act == "check_reminders":
        reminders = []
        for c in list_contacts():
            rs = list_timeline(contact=c["id"], days=60)
            if not rs:
                reminders.append((c["name"], 999))
                continue
            days = (date.today() - date.fromisoformat(rs[0]["date"])).days
            if days >= 14:
                reminders.append((c["name"], days))
        if not reminders:
            return "最近都联系过了，没有需要特别跟进的。"
        reply = "建议联系："
        for name, days in sorted(reminders, key=lambda x: -x[1]):
            level = "🔴" if days >= 21 else "🟡"
            note = f"（{days}天没联系）" if days < 999 else "（暂无记录）"
            reply += f"\n{level} {name} {note}"
        return reply

    elif act == "todos":
        todos = list_todos()
        if not todos:
            return "没有待办，今日无事。"
        today = date.today().isoformat()
        reply = f"待办（{len(todos)}项）："
        for t in todos[:8]:
            c = get_contact(t["contact"])
            name = c["name"] if c else t["contact"]
            tag = "🔴" if t["priority"] == "P0" else "🟡"
            due = " ⏰" if t.get("due", "") < today else ""
            reply += f"\n{tag} {name} - {t['task']}{due}"
        return reply

    elif act == "draft":
        contact_id = action.get("contact")
        tone = action.get("tone", "亲切")
        c = get_contact(contact_id)
        if not c:
            return f"未找到联系人"
        records = list_timeline(contact=contact_id, days=60)
        context = " | ".join(f"{r['date']}: {r['summary']}" for r in records[:3]) if records else "无记录"
        draft = draft_message(c["name"], context, tone)
        return f"拟稿：\n\n{draft}"

    elif act == "send":
        contact_id = action.get("contact")
        text = action.get("text", "")
        c = get_contact(contact_id)
        if not c:
            return f"未找到联系人"
        if not text:
            # Generate draft
            records = list_timeline(contact=contact_id, days=60)
            context = " ".join(f"{r['date']}: {r['summary']}" for r in records[:2]) if records else ""
            text = draft_message(c["name"], context, "亲切")
        ok, msg = send_message(c["name"], text)
        return f"消息已发送。" if ok else f"发送失败：{msg}"

    elif act == "ai_understand":
        # Use Claude to understand complex requests
        try:
            prompt = f"""用户发了这条消息，作为社交关系AI管家，回复它。

用户消息：{action['text']}

你的角色是住在微信里的AI管家，负责帮用户打理人际关系。回复要简短自然，像朋友聊天。

可能的操作包括：
- 记录互动（记一下：xxx）
- 查询联系人状态（xxx最近咋样）
- 查看待办
- 拟消息
- 建议该联系谁

如果用户说了什么需要记录的内容，直接说"已记录"并提取关键信息。"""
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True, text=True, timeout=20,
                cwd="/Users/cyingfang/claude/social-agent",
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return f"收到：{action['text'][:50]}"

    return f"不太理解，试试：\n· 记一下：和张总聊了项目\n· 张总最近咋样\n· 有啥待办\n· 拟个消息给张总"

def process_message(user_message):
    """Process a user message end-to-end. Returns response text."""
    action = parse(user_message)
    return execute(action)
