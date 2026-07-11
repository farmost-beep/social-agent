"""Intent recognition - turns natural language into engine actions."""
import re, subprocess, json
from datetime import date, datetime
from pathlib import Path
from src.engine import *
from src.ai import draft_message
from src.push import push_to_wechat, send_message, set_wechat_id, get_wechat_id

CONTACTS_FILE = Path(__file__).resolve().parent / "data" / "contacts.json"

def _save_contacts(contacts_data=None):
    """Save contacts back to file (for alias updates).

    Args:
        contacts_data: Modified contacts list to save. If None, reloads from file (but
                       that discards in-memory modifications, so always pass data!).
    """
    import json, tempfile, shutil
    if contacts_data is None:
        contacts_data = list_contacts()
    # 先写临时文件再替换，防止写空
    tmp = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False,
                                      dir=str(Path(__file__).resolve().parent / "data"))
    json.dump(contacts_data, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    shutil.move(tmp.name, CONTACTS_FILE)

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

    # "给XX发消息" - send with auto-generated draft
    m = re.match(r'^给(.{1,8})发消息$', text)
    if m:
        return {"action": "draft_and_send", "contact": _find_contact(m.group(1).strip())}

    # "拟条消息给xxx" or "给xxx拟条消息"
    m = re.match(r'(?:拟[条个]?消息给|给)(.{1,8}?)(?:拟[条个]?消息)?[，,]?\s*(.*)', text)
    if m:
        name = m.group(1)
        topic = m.group(2).strip()
        return {"action": "draft", "contact": _find_contact(name), "topic": topic, "tone": "亲切"}

    # "XX是XX" - set alias (e.g. "肖哥是肖庆民")
    m = re.match(r'^(.{1,8})是(.{1,8})$', text)
    if m:
        alias = m.group(1).strip()
        name = m.group(2).strip()
        return {"action": "set_alias", "alias": alias, "name": name}

    # "XX的微信ID是xxx" or "XX的微信号是xxx"
    m = re.match(r'^(.{1,8})的微信(I[Dd]|号)是(.+)$', text)
    if m:
        name = m.group(1).strip()
        wxid = m.group(3).strip()
        return {"action": "set_wxid", "name": name, "wxid": wxid}

    # "发消息给xxx说..." or "告诉xxx..."
    m = re.match(r'(?:发消息给|告诉|通知)(.{1,8}?)(?:说|[，,：:])\s*(.+)', text)
    if m:
        return {"action": "send", "contact": _find_contact(m.group(1)), "text": m.group(2)}

    # "最近有啥要跟进的" or "待办" or "有什么待办"
    if any(kw in text for kw in ['待办', '跟进', '要做什么', '有什么事']):
        return {"action": "todos"}

    # "多少联系人/联系人列表/联系人" - contact count or list
    if any(kw in text for kw in ['多少联系人', '多少人', '联系人列表', '所有联系人', '看看联系人']):
        return {"action": "contact_list"}

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
    """Find contact ID by name (also checks aliases)."""
    contacts = list_contacts()
    name_clean = name.strip()
    for c in contacts:
        if c["name"] == name_clean or c["id"] == name_clean:
            return c["id"]
        # Check aliases
        if name_clean in c.get("alias", []):
            return c["id"]
        if any(name_clean in a for a in c.get("alias", [])):
            return c["id"]
    # Fuzzy match
    for c in contacts:
        if name_clean in c["name"] or name_clean in c["id"]:
            return c["id"]
    return name_clean  # Return as-is if not found

def _find_contact_obj(name):
    contacts = list_contacts()
    name_clean = name.strip()
    for c in contacts:
        if c["name"] == name_clean or c["id"] == name_clean:
            return c
        # Check aliases
        if name_clean in c.get("alias", []):
            return c
    for c in contacts:
        if name_clean in c["name"] or name_clean in c["id"]:
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

    elif act == "set_alias":
        alias = action.get("alias", "")
        name = action.get("name", "")
        contacts = list_contacts()
        c = None
        for contact in contacts:
            if contact["name"] == name or contact["id"] == name:
                c = contact
                break
        if not c:
            return f"未找到联系人「{name}」，先聊聊再设别名吧"
        c.setdefault("alias", [])
        if alias not in c["alias"]:
            c["alias"].append(alias)
        _save_contacts(contacts)
        return f"好，记住了，「{alias}」就是「{c['name']}」。"

    elif act == "set_wxid":
        name = action.get("name", "")
        wxid = action.get("wxid", "")
        contacts = list_contacts()
        c = None
        for contact in contacts:
            if contact["name"] == name or contact["id"] == name:
                c = contact
                break
            if name in contact.get("alias", []):
                c = contact
                break
        if not c:
            # 还未建联系人，直接存到wechat_ids.json
            set_wechat_id(name, wxid)
            return f"好，记住了「{name}」的微信ID。以后可以直接发消息过去了。"
        set_wechat_id(c["name"], wxid)
        return f"好，记住了「{c['name']}」的微信ID。以后给{c['name']}发消息会直接发到对方微信。"

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

    elif act == "contact_list":
        contacts = list_contacts()
        from collections import Counter
        rel_count = Counter(c.get('relation', '校友') for c in contacts)
        with_wx = sum(1 for c in contacts if c.get('platforms', {}).get('weixin'))
        parts = [f"联系人总数: {len(contacts)}人"]
        for rel, cnt in rel_count.most_common():
            parts.append(f"  {rel}: {cnt}人")
        parts.append(f"  含微信: {with_wx}人")
        return "\n".join(parts)

    elif act == "todos":
        todos = list_todos()
        if not todos:
            return "没有待办，今日有事。"
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

    elif act == "draft_and_send":
        contact_id = action.get("contact")
        c = get_contact(contact_id)
        if not c:
            return f"未找到联系人"
        records = list_timeline(contact=contact_id, days=60)
        context = " | ".join(f"{r['date']}: {r['summary']}" for r in records[:3]) if records else "无记录"
        draft = draft_message(c["name"], context, "亲切")
        ok, msg = send_message(c["name"], draft)
        return f"拟稿：\n\n{draft}\n\n推送: {'✅ 已发送' if ok else '❌ 发送失败'}"

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
            d = get_dashboard()
            contact_count = d['total_contacts']
            pending = d['pending_todos']
            prompt = f"""用户发了这条消息，作为社交关系AI管家，回复它。

当前数据（真实数据）：
- 联系人: {contact_count}人
- 待办: {pending}项

用户消息：{action['text']}

你的角色是住在微信里的AI管家，负责帮用户打理人际关系。回复要简短自然，像朋友聊天。

可能的操作包括：
- 记录互动（记一下：xxx）
- 查询联系人状态（xxx最近咋样）
- 查看待办
- 拟消息
- 建议该联系谁

如果用户说了什么需要记录的内容，直接说"已记录"并提取关键信息。
如果用户在问联系人数或联系人相关的信息，直接引用上面的真实数据回答。"""
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True, text=True, timeout=20,
                cwd=str(Path(__file__).resolve().parent),
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
