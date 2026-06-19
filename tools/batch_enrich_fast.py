#!/usr/bin/env python3
"""快速批量联系人画像补全 — 无AI依赖，基于模式匹配
用法: python3 tools/batch_enrich_fast.py
"""
import json, re
from pathlib import Path
from datetime import date

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

with open(DATA_DIR / "contacts.json") as f:
    contacts = json.load(f)

# ── 关键词→标签/角色 映射规则 ──
ROLE_RULES = [
    (r"(银行|金融|保险|证券|基金|投资|私募|quant|量化|信托|信贷)", "同行"),
    (r"(创业|创始人|CEO|董事长|总经理|总裁|合伙人)", "创业"),
    (r"(教授|博士|导师|学术|研究|院士|科研)", "导师"),
    (r"(校友|科大|USTC|ustc|中科大)", "校友"),
    (r"(合作|客户|供应商|伙伴|代理)", "合作"),
    (r"(家人|父亲|母亲|儿子|女儿|妻子|太太|老婆|老公)", "family"),
]

TAG_RULES = [
    (r"(上海|北京|深圳|广州|杭州|南京|苏州|合肥)", "地区"),
    (r"(AI|人工智能|机器|深度学习|NLP|大模型|GPT|Claude)", "AI"),
    (r"(支付|电商|O2O|saas|SaaS|ERP)", "科技"),
    (r"(医疗|药|健康|生物|基因)", "医疗健康"),
    (r"(量子|芯片|半导体|集成电路|光刻)", "硬科技"),
    (r"(法律|律师|合规|审计|会计)", "专业服务"),
    (r"(媒体|记者|编辑|公众号|自媒体)", "媒体"),
    (r"(房产|地产|物业|建筑)", "地产"),
]

# ── 处理 ──
updated = 0
skipped = 0
for c in contacts:
    cid = c["id"]
    # 已补全的跳过
    if c.get("_enrich_version", 0) >= 1:
        skipped += 1
        continue

    notes = c.get("notes", "")
    name = c.get("name", cid)
    tags = set(c.get("tags", []))

    # 1. 基于notes推断角色
    current_role = c.get("relation", "")
    if not current_role or current_role == "其他":
        for pattern, role in ROLE_RULES:
            if re.search(pattern, notes, re.IGNORECASE) or re.search(pattern, name):
                c["relation"] = role
                if role == "校友" and re.search(r"(银行|金融|投资|基金)", notes):
                    c["sub_relation"] = "金融"
                break

    # 2. 打标签
    new_tags = []
    for pattern, tag in TAG_RULES:
        if re.search(pattern, notes, re.IGNORECASE) or re.search(pattern, name):
            if tag not in tags:
                new_tags.append(tag)

    # 3. 从微信备注提取地区
    # 备注格式通常含 "中国/上海/浦东" 这样的信息
    location_match = re.search(r"中国/([一-鿿]+)", notes)
    if location_match and "地区" not in tags:
        new_tags.append(f"地区:{location_match.group(1)}")

    if new_tags:
        tags.update(new_tags)

    # 4. 标记已处理
    if new_tags or (not c.get("relation") or c["relation"] == "其他"):
        c["tags"] = sorted(list(tags))
        c["_enrich_version"] = 1
        if not c.get("created"):
            c["created"] = str(date.today())
        updated += 1
    else:
        # 标记为已处理（无需补全）
        c["_enrich_version"] = 1
        skipped += 1

# 保存
with open(DATA_DIR / "contacts.json", "w") as f:
    json.dump(contacts, f, ensure_ascii=False, indent=2)

stats = {}
for c in contacts:
    r = c.get("relation", "其他")
    stats[r] = stats.get(r, 0) + 1

print(f"✅ 批量补全完成")
print(f"   已更新: {updated} 人")
print(f"   已跳过(已有): {skipped} 人")
print(f"   角色分布: {json.dumps(stats, ensure_ascii=False)}")
