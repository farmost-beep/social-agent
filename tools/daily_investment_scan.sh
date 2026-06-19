#!/bin/bash
# 每日投资扫描 — 昆仑万维持仓+市场信号
# 每天 07:17 运行，扫描结果推送到微信

NODE_SCRIPT="/Users/cyingfang/claude/scripts/direct_send.mjs"
SELF_WXID="o9cq80yA9s4SlCPQNAYivVNJMD50@im.wechat"

REPORT=$(python3 /Users/cyingfang/claude/scripts/investment_flywheel.py 2>/dev/null)
echo "=== 每日投资扫描: $(date) ==="

if [ -f "$NODE_SCRIPT" ]; then
    node "$NODE_SCRIPT" "$SELF_WXID" "$REPORT" 2>&1
    echo "✅ 已推送"
else
    echo "⚠️ direct_send.mjs 未找到"
    echo "$REPORT"
fi
