#!/bin/bash
# 每日AI前沿扫描 — 宁缺毋滥
# 每天早上扫描AI领域最新发展，只推送真正重要的信号
# launchd 定时触发（每天 07:27）

SOCIAL_DIR="/Users/cyingfang/.claude/skills/social-agent"
NODE_SCRIPT="/Users/cyingfang/claude/scripts/direct_send.mjs"
SELF_WXID="o9cq80yA9s4SlCPQNAYivVNJMD50@im.wechat"
FRONTIER="/Users/cyingfang/frontier"
SCAN_LOG="/tmp/daily_ai_scan.log"

echo "=== 每日AI扫描: $(date) ===" > "$SCAN_LOG"

REPORT=$(python3 -c "
import os, re
from datetime import date

today = date.today().isoformat()
frontier = '/Users/cyingfang/frontier'
lines = []
lines.append('📡 AI前沿扫描')
lines.append('📅 ' + today)
lines.append('')

signal_path = os.path.join(frontier, '信号看板.md')
if os.path.exists(signal_path):
    with open(signal_path) as f:
        content = f.read()
    high_count = content.count('🔴')
    update_m = re.search(r'更新[：:]?\s*(\d{4}-\d{2}-\d{2})', content)
    last_update = update_m.group(1) if update_m else '未知'

    lines.append(f'信号看板: 🔴{high_count}条高优先级信号追踪中')
    lines.append(f'最近更新: {last_update}')
    lines.append('')

    in_high = False
    for line in content.split(chr(10)):
        if '高优先级' in line and 'VIX' in line:
            in_high = True
            continue
        if in_high:
            if '中优先级' in line:
                break
            if line.strip().startswith('|') and '🔴' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    num = parts[0].strip().replace('#','')
                    name = parts[1].strip()[:40]
                    lines.append(f'  #{num} {name}')

    lines.append('')
    articles_dir = os.path.join(frontier, '公众号')
    if os.path.exists(articles_dir):
        today_count = sum(1 for f in os.listdir(articles_dir) if today in f and f.endswith('.html'))
        if today_count > 0:
            lines.append(f'📝 今日公众号: {today_count}篇')
        else:
            lines.append('📝 今日尚无发布')

    lines.append('')
    lines.append('💡 对我说\"前沿扫描\"开始深度搜索')

print(chr(10).join(lines))
")

echo "$REPORT" >> "$SCAN_LOG"
echo "" >> "$SCAN_LOG"

if [ -f "$NODE_SCRIPT" ]; then
    echo "$REPORT" > /tmp/daily_ai_msg.txt
    MSG=$(cat /tmp/daily_ai_msg.txt)
    node "$NODE_SCRIPT" "$SELF_WXID" "$MSG" 2>&1 >> "$SCAN_LOG"
    echo "$(date) ✅ 已推送" >> "$SCAN_LOG"
else
    echo "⚠️ direct_send.mjs 未找到" >> "$SCAN_LOG"
fi

cat "$SCAN_LOG"
