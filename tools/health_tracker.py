#!/usr/bin/env python3
"""健康数据自动追踪系统 — v1.0
集成到社交关系AI管家，支持微信自然语言记录+自动周报

用法:
  python3 tools/health_tracker.py --log 体重=81 步数=8000 喝水=2.0
  python3 tools/health_tracker.py --report weekly
  python3 tools/health_tracker.py --status
"""
import json, sys, os, re
from pathlib import Path
from datetime import datetime, date, timedelta

HEALTH_FILE = Path(__file__).resolve().parent.parent / "data" / "health_data.json"
SOCIAL_TODOS = Path(__file__).resolve().parent.parent / "data" / "todos.json"

# 默认健康数据模板
DEFAULT_DATA = {
    "user": "陈颖芳",
    "age": 49, "gender": "男", "height_cm": 178,
    "baseline_date": "2026-06-14",
    "baseline": {
        "weight_kg": 81.0, "waist_cm": 96.0,
        "resting_hr_bpm": 71,
        "blood_pressure_sys": 123, "blood_pressure_dia": 92,
    },
    "daily_records": [],
    "weekly_summaries": [],
    "alert_thresholds": {
        "weight_kg": {"max": 85, "target": 75},
        "waist_cm": {"max": 90, "target": 85},
        "blood_pressure_sys": {"max": 130, "target": 120},
        "blood_pressure_dia": {"max": 85, "target": 80},
        "resting_hr_bpm": {"max": 80, "target": 65},
        "steps": {"min": 6000, "target": 10000},
        "water_liters": {"min": 1.5, "target": 2.5},
        "sleep_hours": {"min": 6.5, "target": 7.5},
    },
    "p0_actions": {
        "购买血压计": "✅", "内分泌科就诊": "✅",
        "泌尿外科就诊": "✅", "肠镜+胃镜": "✅",
        "启动降脂饮食": "✅", "眼科验光配镜": "⬜",
        "血管外科评估": "⬜", "牙科检查": "⬜",
        "购买手环/手表": "⬜",
    }
}

def load_data():
    if HEALTH_FILE.exists():
        with open(HEALTH_FILE) as f:
            return json.load(f)
    return dict(DEFAULT_DATA)

def save_data(data):
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_natural(text):
    """从自然语言中提取健康数据，如'体重81'、'步数8000'、'血压123/92'"""
    records = {}
    patterns = [
        (r"体重[:\s]*(\d+\.?\d*)", "weight_kg"),
        (r"腰围[:\s]*(\d+)", "waist_cm"),
        (r"步数[:\s]*(\d+)", "steps"),
        (r"喝水[:\s]*(\d+\.?\d*)", "water_liters"),
        (r"睡眠[:\s]*(\d+\.?\d*)", "sleep_hours"),
        (r"心率[:\s]*(\d+)", "resting_hr_bpm"),
        (r"血压[:\s]*(\d+)/(\d+)", "bp_pair"),
        (r"运动[:\s]*(\d+)", "exercise_min"),
    ]
    for pattern, key in patterns:
        m = re.search(pattern, text)
        if m:
            if key == "bp_pair":
                records["blood_pressure_sys"] = float(m.group(1))
                records["blood_pressure_dia"] = float(m.group(2))
            else:
                records[key] = float(m.group(1))
    return records

def record_daily(data, records):
    today_str = date.today().isoformat()
    # 查找今日是否有记录
    for r in data["daily_records"]:
        if r["date"] == today_str:
            r.update(records)
            r["note"] = f"自动记录于 {datetime.now().strftime('%H:%M')}"
            return r
    # 新建今日记录
    entry = {"date": today_str, **records, "note": f"自动记录于 {datetime.now().strftime('%H:%M')}"}
    data["daily_records"].append(entry)
    return entry

def generate_weekly_report(data):
    today = date.today()
    week_ago = today - timedelta(days=7)
    week_records = [r for r in data["daily_records"] if r["date"] >= week_ago.isoformat()]

    lines = ["📊 健康周报", f"周期: {week_ago.isoformat()} → {today.isoformat()}", ""]
    if not week_records:
        lines.append("⚠️ 本周无健康记录")
        lines.append("")
        lines.append("💡 试试在微信跟我说：")
        lines.append('  "体重81 步数8000 喝水2L"')
        return "\n".join(lines)

    # 计算均值
    fields = {
        "体重(kg)": [r.get("weight_kg") for r in week_records],
        "舒张压": [r.get("blood_pressure_dia") for r in week_records],
        "静息心率": [r.get("resting_hr_bpm") for r in week_records],
        "步数": [r.get("steps") for r in week_records],
        "饮水(L)": [r.get("water_liters") for r in week_records],
        "睡眠(h)": [r.get("sleep_hours") for r in week_records],
    }
    lines.append(f"📝 记录天数: {len(week_records)}天")
    for label, values in fields.items():
        vals = [v for v in values if v is not None]
        if vals:
            avg = sum(vals) / len(vals)
            lines.append(f"  {label}: {avg:.1f} (记录{len(vals)}天)")

    # 跟阈值对比
    thresholds = data.get("alert_thresholds", {})
    alerts = []
    field_map = {
        "weight_kg": ("体重", lambda v, t: v > t["max"]),
        "steps": ("步数", lambda v, t: v < t["min"]),
        "water_liters": ("饮水", lambda v, t: v < t["min"]),
        "sleep_hours": ("睡眠", lambda v, t: v < t["min"]),
    }
    for fkey, (label, alert_fn) in field_map.items():
        vals = [r.get(fkey) for r in week_records if r.get(fkey) is not None]
        if vals and fkey in thresholds:
            avg = sum(vals) / len(vals)
            if alert_fn(avg, thresholds[fkey]):
                target = thresholds[fkey].get("target", thresholds[fkey].get("min", "?"))
                alerts.append(f"⚠️ {label} {avg:.1f} (目标{target})")

    if alerts:
        lines.append("")
        lines.append("🔴 需关注：")
        for a in alerts:
            lines.append(f"  {a}")

    lines.append("")
    total = len(week_records)
    if total >= 5:
        lines.append("✅ 本周记录≥5天，达标！")
    else:
        lines.append(f"💪 记录{total}天，目标每周≥5天")

    return "\n".join(lines)

def get_status_text(data):
    today = date.today()
    last7 = [r for r in data["daily_records"] if r["date"] >= (today - timedelta(days=7)).isoformat()]
    total = len(data["daily_records"])
    return f"📊 健康数据: 累计{total}天记录 | 本周{len(last7)}天 | 基线: {data.get('baseline_date','?')}"

# ── CLI ──
if __name__ == "__main__":
    args = sys.argv[1:]
    data = load_data()

    if "--log" in args:
        idx = args.index("--log")
        texts = args[idx+1:]
        records = {}
        for t in texts:
            records.update(parse_natural(t))
        if records:
            entry = record_daily(data, records)
            save_data(data)
            recorded = " ".join(f"{k}={v}" for k, v in records.items())
            print(f"✅ 已记录: {recorded}")
        else:
            print("⚠️ 未识别到健康数据。试试: 体重81 步数8000 喝水2L")

    elif "--report" in args:
        idx = args.index("--report")
        period = args[idx+1] if idx+1 < len(args) else "weekly"
        if period == "weekly" or period == "周报":
            print(generate_weekly_report(data))

    elif "--status" in args:
        print(get_status_text(data))

    else:
        print("用法:")
        print("  python3 tools/health_tracker.py --log 体重81 步数8000 喝水2L")
        print("  python3 tools/health_tracker.py --report weekly")
        print("  python3 tools/health_tracker.py --status")
