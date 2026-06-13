#!/usr/bin/env python3
"""社交关系AI管家 — 一个比你更记得住人情世故的AI管家。

用法:
  social.py add-contact <id> <name> --role <角色>   添加联系人
  social.py log <contact> <摘要>                     记录互动
  social.py todos [--priority P0]                    查看待办
  social.py done <todo-id>                           完成待办
  social.py draft <contact> [--tone 亲切]            AI拟稿
  social.py send <contact> [--tone 亲切]             拟稿并发送
  social.py status [<contact>]                       查看状态/时间线
  social.py dashboard                                仪表盘
  social.py check                                    检查需跟进的提醒
"""
import sys, argparse
from lib.engine import *
from lib.ai import draft_message, generate_reminder
from lib.push import push_to_wechat, send_message

def cmd_dashboard(args):
    d = get_dashboard()
    print(f"\n{'='*40}")
    print(f"  社交关系AI管家 · 仪表盘")
    print(f"{'='*40}")
    print(f"  联系人: {d['total_contacts']}人")
    print(f"  各角色: {d['by_role']}")
    print(f"  待办: {d['pending_todos']}项 (超期{d['overdue_todos'].__len__()}项)")
    print(f"  近7天活动: {d['recent_activities']}条")
    print(f"  冷却关系: {len(d['cold_relationships'])}个")
    for c in d['cold_relationships']:
        print(f"    ⚠️ {c['contact']} — {c['days']}天未联系")
    print(f"{'='*40}\n")
    # Show top todos
    todos = list_todos()
    if todos:
        print("🔴 优先待办:")
        for t in todos[:5]:
            c = get_contact(t["contact"])
            name = c["name"] if c else t["contact"]
            print(f"  [{t['priority']}] {name} — {t['task']} (截止{t.get('due','?')})")
    return 0

def cmd_check(args):
    """Check all relationships and generate reminders."""
    contacts = list_contacts()
    reminders = []
    for c in contacts:
        records = list_timeline(contact=c["id"], days=60)
        if not records:
            reminders.append((c["name"], 999, "暂无互动记录"))
            continue
        last = records[0]
        days_since = (date.today() - date.fromisoformat(last["date"])).days
        if days_since >= 14:
            reminders.append((c["name"], days_since, last.get("summary", "")))

    if not reminders:
        print("✅ 所有关系都在14天内联系过，无需提醒")
        return 0

    print(f"\n📢 需要跟进的关系 ({len(reminders)}个):")
    print("-" * 40)
    for name, days, summary in reminders:
        if days >= 21:
            print(f"  🔴 {name} — {days}天未联系")
        elif days >= 14:
            print(f"  🟡 {name} — {days}天未联系")
        if summary:
            print(f"     上次: {summary[:40]}")
    print()
    return 0

def main():
    if len(sys.argv) < 2:
        print("社交关系AI管家 — 一个比你更记得住人情世故的AI管家\n")
        print("用法:")
        print("  social.py add-contact <ID> --name NAME --role ROLE")
        print("  social.py log <CONTACT> <SUMMARY>")
        print("  social.py todos [--priority P0]")
        print("  social.py done <TODO_ID>")
        print("  social.py draft <CONTACT> [--tone 亲切]")
        print("  social.py send <CONTACT> [--tone 亲切]")
        print("  social.py status [CONTACT]")
        print("  social.py dashboard")
        print("  social.py check")
        return 1

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "add-contact":
        if len(args) < 1:
            print("用法: social.py add-contact <ID> --name NAME --role ROLE")
            return 1
        contact_id = args[0]
        opts = _parse_opts(args[1:], ["--name", "--role", "--tags", "--notes"])
        name = opts.get("--name", contact_id)
        role = opts.get("--role", "其他")
        tags = opts.get("--tags", "").split() if opts.get("--tags") else []
        notes = opts.get("--notes", "")
        ok, msg = add_contact(contact_id, name, role, tags, None, notes)
        print(msg)
        return 0 if ok else 1

    elif cmd == "log":
        if len(args) < 2:
            print("用法: social.py log <CONTACT> <SUMMARY>")
            return 1
        contact = args[0]
        summary = " ".join(a for a in args[1:] if not a.startswith("--"))
        opts = _parse_opts(args[1:], ["--type"])
        type_ = opts.get("--type", "message")
        record = add_timeline(contact, summary, type_=type_)
        print(f"已记录: {record['summary'][:40]}")
        if record.get("pending"):
            print(f"待办已创建: {record['pending']}")
        return 0

    elif cmd == "todos":
        opts = _parse_opts(args, ["--priority"])
        todos = list_todos(priority=opts.get("--priority"))
        if not todos:
            print("没有待办事项 ✅")
            return 0
        today = date.today().isoformat()
        for t in todos:
            overdue = " ⏰" if t.get("due", "") < today else ""
            tag = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(t.get("priority", "P1"), "⬜")
            contact = get_contact(t["contact"])
            name = contact["name"] if contact else t["contact"]
            print(f"  {tag} [{t['priority']}] {name} - {t['task']} (截止{t.get('due','?')}){overdue}")
        return 0

    elif cmd == "done":
        if not args:
            print("用法: social.py done <TODO_ID>")
            return 1
        ok, msg = complete_todo(args[0])
        print(msg)
        return 0 if ok else 1

    elif cmd == "draft":
        if not args:
            print("用法: social.py draft <CONTACT> [--tone 亲切]")
            return 1
        contact_id = args[0]
        opts = _parse_opts(args[1:], ["--tone"])
        tone = opts.get("--tone", "亲切")
        contact = get_contact(contact_id)
        if not contact:
            print(f"未找到联系人: {contact_id}")
            return 1
        timeline = list_timeline(contact=contact_id, days=60)
        context = "无最近互动记录"
        if timeline:
            context = " | ".join(f"{r['date']}: {r['summary']}" for r in timeline[:3])
        print(f"正在为{contact['name']}拟稿（{tone}风格）...", file=sys.stderr)
        draft = draft_message(contact["name"], context, tone)
        print(f"\n{draft}\n")
        return 0

    elif cmd == "send":
        if not args:
            print("用法: social.py send <CONTACT> [--tone 亲切]")
            return 1
        contact_id = args[0]
        opts = _parse_opts(args[1:], ["--tone"])
        tone = opts.get("--tone", "亲切")
        contact = get_contact(contact_id)
        if not contact:
            print(f"未找到联系人: {contact_id}")
            return 1
        timeline = list_timeline(contact=contact_id, days=60)
        context = "无最近互动记录"
        if timeline:
            context = " | ".join(f"{r['date']}: {r['summary']}" for r in timeline[:3])
        print(f"正在为{contact['name']}拟稿...", file=sys.stderr)
        draft = draft_message(contact["name"], context, tone)
        print(f"\n{draft}\n")
        ok, msg = send_message(contact["name"], draft)
        print(f"推送: {msg}")
        return 0 if ok else 1

    elif cmd == "status":
        if args:
            c = get_contact(args[0])
            if not c:
                print(f"未找到: {args[0]}")
                return 1
            print(f"\n{'='*40}")
            print(f"  {c['name']} ({c.get('role','?')})")
            print(f"{'='*40}")
            print(f"  阶段: {c.get('stage','-')}")
            print(f"  强度: {c.get('strength',3)}/5")
            records = list_timeline(contact=args[0], days=90)
            if records:
                print(f"  最近互动 ({len(records)}条):")
                for r in records[:5]:
                    print(f"    {r['date']}: {r['summary'][:50]}")
                    if r.get("pending"):
                        print(f"      -> {r['pending']}")
            else:
                print("  暂无互动记录")
        else:
            contacts = list_contacts()
            print(f"\n联系人 ({len(contacts)}人)")
            for c in contacts:
                records = list_timeline(contact=c["id"], days=30)
                last = records[0]["date"] if records else "从未"
                print(f"  {c['name']:8s} {c.get('role','?'):6s} 最近:{last}")
        return 0

    elif cmd == "dashboard":
        d = get_dashboard()
        print(f"\n社交关系AI管家 - 仪表盘")
        print(f"联系人: {d['total_contacts']}人 | 角色: {d['by_role']}")
        print(f"待办: {d['pending_todos']}项 (超期{len(d['overdue_todos'])}项)")
        print(f"近7天活动: {d['recent_activities']}条")
        print(f"冷却关系: {len(d['cold_relationships'])}个")
        for c in d['cold_relationships']:
            print(f"  {c['contact']} - {c['days']}天未联系")
        todos = list_todos()
        if todos:
            print(f"\n优先待办:")
            for t in todos[:5]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                print(f"  [{t['priority']}] {name} - {t['task']}")
        return 0

    elif cmd == "check":
        reminders = []
        contacts = list_contacts()
        for c in contacts:
            records = list_timeline(contact=c["id"], days=60)
            if not records:
                reminders.append((c["name"], 999, ""))
                continue
            last = records[0]
            days_since = (date.today() - date.fromisoformat(last["date"])).days
            if days_since >= 14:
                reminders.append((c["name"], days_since, last.get("summary", "")))
        if not reminders:
            print("所有关系都在14天内联系过")
            return 0
        print(f"需要跟进 ({len(reminders)}个):")
        for name, days, summary in reminders:
            level = "P0" if days >= 21 else "P1"
            print(f"  [{level}] {name} - {days}天未联系")
            if summary:
                print(f"    上次: {summary[:40]}")
        return 0

    elif cmd == "remind":
        d = get_dashboard()
        lines = [f"今日待办提醒 ({date.today().isoformat()})"]
        if d["overdue_todos"]:
            lines.append(f"\n超期待办 {len(d['overdue_todos'])}项:")
            for t in d["overdue_todos"]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                lines.append(f"  P0 {name} - {t['task']}")
        todos = [t for t in list_todos() if t.get("status") == "pending"]
        if todos:
            lines.append(f"\n待办 {len(todos)}项:")
            for t in todos[:5]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                lines.append(f"  [{t['priority']}] {name} - {t['task']}")
        if d["cold_relationships"]:
            lines.append(f"\n冷却关系 {len(d['cold_relationships'])}个:")
            for c in d["cold_relationships"]:
                lines.append(f"  {c['contact']} - {c['days']}天未联系")
        if not todos and not d["overdue_todos"] and not d["cold_relationships"]:
            lines.append("\n今日无事，安心赚钱。")
        msg = "\n".join(lines)
        ok, result = push_to_wechat("社交关系AI管家", msg)
        print(result)
        return 0 if ok else 1

    else:
        print(f"未知命令: {cmd}")
        return 1


def _parse_opts(args, valid_opts):
    opts = {}
    i = 0
    while i < len(args):
        if args[i] in valid_opts:
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[args[i]] = args[i + 1]
                i += 2
            else:
                opts[args[i]] = ""
                i += 1
        else:
            i += 1
    return opts

if __name__ == "__main__":
    sys.exit(main())
