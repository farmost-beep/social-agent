#!/usr/bin/env python3
"""通讯录去重：合并相同联系人，删除多余重复"""
import json, re
from collections import defaultdict

BASE = "/Users/cyingfang/.claude/skills/social-agent/data"
with open(f"{BASE}/contacts.json") as f:
    contacts = json.load(f)
with open(f"{BASE}/wechat_ids.json") as f:
    wechat_ids = json.load(f)

def normalize(name):
    n = re.sub(r'[^一-鿿\w]', '', name).lower()
    n = re.sub(r'^\d+', '', n)
    n = re.sub(r'\d+$', '', n)
    return n.strip()

def is_vcf_dup(items):
    """判断是否全是VCF导入的无联系方式重复"""
    return all(c.get('source') == 'vcf_import' and not c.get('platforms') for c in items)

# 按标准化名称分组
groups = defaultdict(list)
for i, c in enumerate(contacts):
    key = normalize(c['name'])
    groups[key].append((i, c))

# 需要删除的索引
to_delete = set()
# 需要更新的联系人
to_update = []

for key, items in groups.items():
    if len(items) < 2:
        continue

    indices = [idx for idx, _ in items]
    items_data = [c for _, c in items]

    # 类型1: VCF纯重复 → 保留一个，删多余
    if is_vcf_dup(items_data):
        keep_idx = indices[0]
        to_delete.update(indices[1:])
        continue

    # 类型2: 合并（保留最强信息的一个）
    # 选强度最高的为主
    best = max(items_data, key=lambda c: (
        c.get('strength', 1),
        1 if c.get('platforms') else 0,
        1 if c.get('source') != 'vcf_import' else 0,
        1 if c.get('notes') else 0
    ))
    best_pos = items_data.index(best)
    best_idx = indices[best_pos]

    # 合并其他记录的信息到best
    for pos, (idx, c) in enumerate(items):
        if pos == best_pos:
            continue
        # 合并alias
        for a in c.get('alias', []):
            if a not in best.get('alias', []):
                best.setdefault('alias', []).append(a)
        # 合并platforms
        for k, v in c.get('platforms', {}).items():
            if k not in best.get('platforms', {}):
                best.setdefault('platforms', {})[k] = v
        # 合并tags
        for t in c.get('tags', []):
            if t not in best.get('tags', []):
                best.setdefault('tags', []).append(t)
        # 合并notes
        if c.get('notes') and not best.get('notes'):
            best['notes'] = c['notes']
        # 如果强度更高的保留强度
        if c.get('strength', 1) > best['strength']:
            best['strength'] = c['strength']
        # 同步wechat_ids
        if c['name'] in wechat_ids and best['name'] not in wechat_ids:
            wechat_ids[best['name']] = wechat_ids.pop(c['name'])

        to_delete.add(idx)

    to_update.append((best_idx, best))

# 执行删除和更新
for idx in sorted(to_delete, reverse=True):
    del contacts[idx]

for idx, updated_c in to_update:
    contacts[idx] = updated_c

# 写回
with open(f"{BASE}/contacts.json", 'w', encoding='utf-8') as f:
    json.dump(contacts, f, ensure_ascii=False, indent=2)

with open(f"{BASE}/wechat_ids.json", 'w', encoding='utf-8') as f:
    json.dump(wechat_ids, f, ensure_ascii=False, indent=2)

from collections import Counter
rel_count = Counter(c['relation'] for c in contacts)
print(f"删除重复: {len(to_delete)}条")
print(f"合并更新: {len(to_update)}组")
print(f"\n联系人: {len(contacts)}人")
for rel, cnt in rel_count.most_common():
    print(f"  {rel}: {cnt}人")
