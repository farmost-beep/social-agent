#!/usr/bin/env python3
"""社交关系AI管家 v3.0 Agent — 住在微信里的AI管家。

运行模式：
  python3 agent.py                  # 单次检查+推送
  python3 agent.py --daemon         # 守护进程模式（每小时检查）
  python3 agent.py --chat "消息"    # 处理一条用户消息

定时推送（cron）：
  09:00 今日概览
  14:00 建议联系
  21:00 今日回顾
"""
import sys, os, time, json, subprocess
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from lib.engine import *
from lib.push import push_to_wechat
from intent import process_message


def build_morning():
    """09:00 今日概览"""
    d = get_dashboard()
    lines = ["☀️ 今日概览\n"]
    todos = list_todos()
    if todos:
        lines.append(f"待办 {len(todos)}项：")
        for t in todos[:5]:
            c = get_contact(t["contact"])
            name = c["name"] if c else t["contact"]
            tag = "🔴" if t["priority"] == "P0" else "🟡"
            lines.append(f"  {tag} {name} - {t['task']}")
        lines.append("")
    if d["cold_relationships"]:
        lines.append(f"冷却关系 {len(d['cold_relationships'])}个：")
        for c in d["cold_relationships"]:
            lines.append(f"  {c['contact']} - {c['days']}天未联系")
        lines.append("")
    if d["overdue_todos"]:
        lines.append(f"⚠️ 有 {len(d['overdue_todos'])} 项已超期")
    if not todos and not d["cold_relationships"]:
        lines.append("今日无事，安心赚钱。")
    return "\n".join(lines)


def build_afternoon():
    """14:00 建议联系"""
    reminders = []
    for c_obj in list_contacts():
        rs = list_timeline(contact=c_obj["id"], days=60)
        if not rs:
            reminders.append((c_obj["name"], 999, ""))
            continue
        days = (date.today() - date.fromisoformat(rs[0]["date"])).days
        if days >= 14:
            reminders.append((c_obj["name"], days, rs[0].get("summary", "")))

    if not reminders:
        push_to_wechat("社交AI管家", "💡 建议联系\n\n今天没有需要特别跟进的关系。")
        return

    lines = ["💡 建议联系\n"]
    for name, days, summary in sorted(reminders, key=lambda x: -x[1]):
        tag = "🔴" if days >= 21 else "🟡"
        note = f"{days}天没联系" if days < 999 else "暂无记录"
        lines.append(f"  {tag} {name}（{note}）")
        if summary:
            lines.append(f"     上次：{summary[:30]}")
    push_to_wechat("社交AI管家", "\n".join(lines))


def build_evening():
    """21:00 今日回顾"""
    timeline = list_timeline(days=1)
    todos = list_todos()
    d = get_dashboard()
    lines = ["🌙 今日回顾\n"]
    if timeline:
        lines.append(f"今天记录了 {len(timeline)} 条互动：")
        for r in timeline[:5]:
            c = get_contact(r["contact"])
            name = c["name"] if c else r["contact"]
            lines.append(f"  · {name}: {r['summary'][:40]}")
    else:
        lines.append("今天没有记录新互动。")
    lines.append("")
    lines.append(f"当前待办 {len(todos)} 项，联系人 {d['total_contacts']} 人。")
    lines.append("\n需要我做什么，随时跟我说。")
    push_to_wechat("社交AI管家", "\n".join(lines))


def chat(message):
    """Handle a chat message from user."""
    response = process_message(message)
    return response


def single_check():
    """Single check - send morning/afternoon/evening based on current hour."""
    hour = datetime.now().hour
    if 8 <= hour <= 10:
        msg = build_morning()
        push_to_wechat("社交AI管家", msg)
        print("Morning briefing sent")
    elif 13 <= hour <= 15:
        build_afternoon()
        print("Afternoon reminder sent")
    elif 20 <= hour <= 22:
        build_evening()
        print("Evening review sent")
    else:
        # Just check for urgent items
        d = get_dashboard()
        if d["overdue_todos"]:
            lines = ["⏰ 有超期待办："]
            for t in d["overdue_todos"]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                lines.append(f"· {name} - {t['task']}")
            push_to_wechat("社交AI管家", "\n".join(lines))
            print("Urgent reminder sent")
        else:
            print("No urgent items, skipped")


def daemon():
    """Run as daemon - check every 30 minutes."""
    print("🤖 社交关系AI管家 Agent 已启动")
    print("  定时推送：09:00 / 14:00 / 21:00")
    print("  每30分钟检查紧急待办\n")

    last_morning = last_afternoon = last_evening = -1

    while True:
        hour = datetime.now().hour
        minute = datetime.now().minute

        # Morning: 9:00-9:05
        if hour == 9 and minute < 5 and last_morning != date.today().day:
            msg = build_morning()
            push_to_wechat("社交AI管家", msg)
            last_morning = date.today().day
            print(f"[{datetime.now().strftime('%H:%M')}] 早间概览已推送")

        # Afternoon: 14:00-14:05
        elif hour == 14 and minute < 5 and last_afternoon != date.today().day:
            build_afternoon()
            last_afternoon = date.today().day
            print(f"[{datetime.now().strftime('%H:%M')}] 午后提醒已推送")

        # Evening: 21:00-21:05
        elif hour == 21 and minute < 5 and last_evening != date.today().day:
            build_evening()
            last_evening = date.today().day
            print(f"[{datetime.now().strftime('%H:%M')}] 晚间回顾已推送")

        # Urgent check every 30 minutes
        elif minute % 30 < 2:
            d = get_dashboard()
            if d["overdue_todos"]:
                lines = ["⏰ 超期待办提醒："]
                for t in d["overdue_todos"]:
                    c = get_contact(t["contact"])
                    name = c["name"] if c else t["contact"]
                    lines.append(f"· {name} - {t['task']}")
                push_to_wechat("社交AI管家", "\n".join(lines))

        time.sleep(60)  # Check every minute


def main():
    if len(sys.argv) < 2:
        single_check()
        return

    cmd = sys.argv[1]

    if cmd == "--daemon":
        daemon()
    elif cmd == "--chat":
        if len(sys.argv) < 3:
            msg = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
            if not msg:
                print("用法：agent.py --chat 消息内容")
                return
        else:
            msg = sys.argv[2]
        response = chat(msg)
        print(response)
    elif cmd == "--morning":
        msg = build_morning()
        push_to_wechat("社交AI管家", msg)
        print(msg)
    elif cmd == "--afternoon":
        build_afternoon()
    elif cmd == "--evening":
        build_evening()
    else:
        single_check()


if __name__ == "__main__":
    main()
