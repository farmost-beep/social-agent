#!/bin/bash
# 社交关系AI管家 — 自动定时提醒 v2.0
# 每天早上8:57和晚上19:57推送待办+生日+冷关系提醒到微信
# launchd 已配置，无需手动操作
# 手动测试: bash tools/auto_reminder.sh morning

SOCIAL_DIR="/Users/cyingfang/.claude/skills/social-agent"
DATA_DIR="$SOCIAL_DIR/data"
NODE_SCRIPT="/Users/cyingfang/claude/scripts/direct_send.mjs"
SELF_WXID="o9cq80yA9s4SlCPQNAYivVNJMD50@im.wechat"

generate_reminder() {
    local period=$1

    python3 << PYEOF
import json, sys, math
from datetime import datetime, date, timedelta
from pathlib import Path

data_dir = Path("$DATA_DIR")
period = "$period"

today = date.today()
weekday = today.weekday()  # 0=周一, 6=周日
is_weekend = weekday >= 5

# ── 1. 加载数据 ──
try:
    with open(data_dir / "todos.json") as f:
        todos = json.load(f)
except:
    todos = []
try:
    with open(data_dir / "contacts.json") as f:
        contacts = json.load(f)
except:
    contacts = []
try:
    with open(data_dir / "timeline.json") as f:
        timeline = json.load(f)
except:
    timeline = []

contact_names = {}
for c in contacts:
    contact_names[c["id"]] = c.get("name", c["id"])

# ── 2. 待办分析 ──
pending_todos = [t for t in todos if t.get("status") == "pending"]

# 逾期升级：逾期3天以上的P1自动视为P0
overdue_todos = []
urgent_todos = []
normal_todos = []
for t in pending_todos:
    due_str = t.get("due", "")
    priority = t.get("priority", "P1")
    if due_str and due_str < today.isoformat():
        days_overdue = (today - date.fromisoformat(due_str)).days
        t["_overdue_days"] = days_overdue
        if days_overdue >= 3 and priority == "P1":
            priority = "P0!"  # 标记升级
        overdue_todos.append((t, days_overdue, priority))
    elif due_str and due_str <= (today + timedelta(days=3)).isoformat():
        urgent_todos.append(t)
    else:
        normal_todos.append(t)

overdue_todos.sort(key=lambda x: -x[1])  # 超期最久的在前

# ── 3. 生日提醒（未来14天内） ──
birthday_reminders = []
for c in contacts:
    notes = c.get("notes", "")
    # 从 notes 或 important_dates 中提取生日
    for d in c.get("important_dates", []):
        if d.get("type") == "birthday":
            bd = d.get("date", "")
            if len(bd) >= 5:  # MM-DD
                try:
                    bd_date = date(today.year, int(bd[:2]), int(bd[3:5]))
                    delta = (bd_date - today).days
                    if 0 <= delta <= 14:
                        birthday_reminders.append((c.get("name", c["id"]), delta, bd))
                except:
                    pass
    # 也从tags/notes正则提取
    import re
    bd_match = re.search(r"(\d{1,2})月(\d{1,2})日", notes)
    if bd_match:
        try:
            bd_date = date(today.year, int(bd_match.group(1)), int(bd_match.group(2)))
            delta = (bd_date - today).days
            if 0 <= delta <= 14:
                name = c.get("name", c["id"])
                if not any(n[0] == name for n in birthday_reminders):
                    birthday_reminders.append((name, delta, f"{bd_match.group(1)}月{bd_match.group(2)}日"))
        except:
            pass

birthday_reminders.sort(key=lambda x: x[1])

# ── 4. 冷关系分析（14天+未联系，仅限strength≥3） ──
cold_contacts = []
for c in contacts:
    cid = c["id"]
    if c.get("relation") in ("self", "family"):
        continue
    if c.get("strength", 3) < 3:
        continue
    c_records = [t for t in timeline if t.get("contact") == cid]
    if not c_records:
        continue
    last = max(r["date"] for r in c_records if r.get("date"))
    days_since = (today - date.fromisoformat(last)).days
    if days_since >= 14:
        cold_contacts.append((contact_names.get(cid, cid), days_since, c.get("strength", 3)))

cold_contacts.sort(key=lambda x: -x[2])

# ── 5. 今日活动 ──
today_activities = [t for t in timeline if t.get("date") == today.isoformat()]

# ── 5b. 今日健康数据 ──
try:
    with open(data_dir / "health_data.json") as f:
        hd = json.load(f)
    today_health = [r for r in hd.get("daily_records", []) if r["date"] == today.isoformat()]
except:
    today_health = []
    hd = {"daily_records": []}

# ── 6. 今日重点关注（选1条最重要的） ──
focus = None
if overdue_todos:
    t, days, pri = overdue_todos[0]
    name = contact_names.get(t["contact"], t["contact"])
    focus = f"🔴 最紧迫：{name} — {t['task'][:40]}（已超期{days}天）"
elif urgent_todos:
    t = urgent_todos[0]
    name = contact_names.get(t["contact"], t["contact"])
    focus = f"📌 优先：{name} — {t['task'][:40]}（截止{t.get('due','?')}）"
elif birthday_reminders:
    name, delta, bd = birthday_reminders[0]
    if delta == 0:
        focus = f"🎂 今天 {name} 生日！"
    else:
        focus = f"🎂 {name} 还有{delta}天生日（{bd}）"

# ── 7. 生成消息 ──
lines = []

if period == "morning":
    day_type = "周末" if is_weekend else "工作日"
    lines.append(f"☀️ 早上好！{today.isoformat()} 周{today.weekday()+1} ({day_type})")
elif period == "evening":
    lines.append(f"🌙 晚间回顾 — {today.isoformat()}")
else:
    lines.append(f"📋 社交关系AI管家提醒 — {today.isoformat()}")

lines.append("")

# 今日重点关注
if focus:
    lines.append(focus)
    lines.append("")

# 超期待办
if overdue_todos:
    lines.append(f"🔴 超期待办 ({len(overdue_todos)}项)：")
    for t, days, pri in overdue_todos[:5]:
        name = contact_names.get(t["contact"], t["contact"])
        flag = " ⬆️" if pri == "P0!" else ""
        lines.append(f"  {pri}{flag} {name} — {t['task'][:35]}（超期{days}天）")
    lines.append("")

# 近期待办（早上：3天内到期）
if period == "morning" and urgent_todos:
    lines.append(f"📌 近期待办 ({len(urgent_todos)}项)：")
    for t in urgent_todos[:3]:
        name = contact_names.get(t["contact"], t["contact"])
        lines.append(f"  [{t['priority']}] {name} — {t['task'][:35]}（截止{t.get('due','?')}）")
    lines.append("")

# 生日提醒
if birthday_reminders:
    lines.append(f"🎂 生日提醒 ({len(birthday_reminders)}项)：")
    for name, delta, bd in birthday_reminders:
        if delta == 0:
            lines.append(f"  🎉 {name} 今天生日！快送祝福")
        else:
            lines.append(f"  {name} — {delta}天后（{bd}）")
    lines.append("")

# 冷关系（仅限早晨，或冷关系很重要时）
if period == "morning" and cold_contacts:
    lines.append(f"💡 冷关系提醒 ({len(cold_contacts)}人14天+未联系)：")
    for name, days, strength in cold_contacts[:3]:
        icon = "🔴" if days >= 21 else "🟡"
        lines.append(f"  {icon} {name} — {days}天（强度{strength}）")
    if len(cold_contacts) > 3:
        lines.append(f"  ...还有{len(cold_contacts)-3}人")
    lines.append("")

# 今日记录（晚上）
if period == "evening":
    if today_activities:
        lines.append(f"📝 今日记录 ({len(today_activities)}条)：")
        for a in today_activities[:3]:
            lines.append(f"  • {a.get('summary', '')[:40]}")
        lines.append("")
    else:
        lines.append("📝 今日还没有互动记录")
        lines.append("")

    # 健康数据（晚上显示今日记录）
    if today_health:
        h = today_health[0]
        health_items = []
        if h.get("weight_kg"): health_items.append(f"体重{h['weight_kg']}kg")
        if h.get("steps"): health_items.append(f"步数{int(h['steps'])}")
        if h.get("water_liters"): health_items.append(f"饮水{h['water_liters']}L")
        if h.get("sleep_hours"): health_items.append(f"睡眠{h['sleep_hours']}h")
        if h.get("resting_hr_bpm"): health_items.append(f"心率{int(h['resting_hr_bpm'])}")
        if health_items:
            lines.append("🏃 今日健康：")
            lines.append(f"  {' | '.join(health_items)}")
            lines.append("")
    else:
        health_records_count = len(hd.get("daily_records", []))
        lines.append(f"🏃 健康数据累计{health_records_count}天")
        if period == "evening":
            lines.append("  💡 跟我说：体重81 步数8000 喝水2L")
        lines.append("")

# 周末特别提示
if is_weekend and period == "morning":
    lines.append("🌤️ 周末愉快！可以约朋友聚聚")
    lines.append("")

# 总结
total_pending = len(pending_todos)
lines.append(f"📊 待办:{total_pending} | 超期:{len(overdue_todos)} | 冷关系:{len(cold_contacts)} | 生日:{len(birthday_reminders)}")

if total_pending == 0 and not cold_contacts and not birthday_reminders:
    lines.append("✅ 一切正常，安心过好今天！")

print("\n".join(lines))
PYEOF
}

# ── 主流程 ──
PERIOD=${1:-morning}
REMINDER=$(generate_reminder "$PERIOD")

echo "=== 社交关系AI管家 自动提醒 v2.0 ==="
echo "时间: $(date)"
echo "时段: $PERIOD"
echo ""

if [ -f "$NODE_SCRIPT" ]; then
    node "$NODE_SCRIPT" "$SELF_WXID" "$REMINDER" 2>&1
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo "✅ 已推送至微信"
    else
        echo "⚠️ 推送失败"
        echo "$REMINDER"
    fi
else
    echo "⚠️ direct_send.mjs 未找到"
    echo "$REMINDER"
fi
