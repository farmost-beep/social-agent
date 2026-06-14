#!/usr/bin/env python3
"""导入微信通讯录全部联系人到社交管家，按标签分类"""
import json, re, openpyxl
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path("/Users/cyingfang/.claude/skills/social-agent")
DATA = BASE / "data"

# 加载现有数据
with open(DATA / "contacts.json") as f:
    contacts = json.load(f)
with open(DATA / "wechat_ids.json") as f:
    wechat_ids = json.load(f)

# 读取微信通讯录
path = "/Users/cyingfang/claude/deliverables/career/微信通讯录导出-20260613.xlsx"
wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
data = rows[1:]

private = [r for r in data if r[4] == '私聊']

# ── 标签→关系 映射 ──
def classify_by_tags(tag_str):
    """根据标签判断关系类型"""
    if not tag_str:
        return '其他', '微信联系人'
    tags = set(t.strip() for t in tag_str.split('|') if t.strip())

    if '0ustc' in tags:
        return '校友', '科大校友'
    if '民建' in tags:
        return '同行', '民建'
    if '职教社' in tags:
        return '同行', '职教社'
    if '邮储' in tags or '1youb' in tags or '邮储上分' in tags:
        return '同行', '邮储银行'
    if '1shrb' in tags:
        return '同行', '金融同行'
    if '1bea' in tags:
        return '同行', '同行'
    if '1cupd' in tags:
        return '同行', '金融同行'
    if '1dc' in tags:
        return '同行', '同行'
    if '1metlife' in tags:
        return '同行', '保险'
    if '猎头' in tags:
        return '其他', '猎头'
    if '监管' in tags:
        return '同行', '监管'
    if '外审' in tags:
        return '同行', '审计'
    if '长江证券' in tags:
        return '同行', '证券'
    if '律师' in tags or '方达' in tags:
        return '同行', '律师'
    if '腾讯' in tags:
        return '同行', '互联网'
    if '均瑶集团' in tags:
        return '同行', '企业'
    if '上仲' in tags:
        return '同行', '仲裁'
    if '库帕思' in tags or '中科慧眼' in tags or '绿色技术银行' in tags:
        return '同行', '企业'
    if '493同学群' in tags or '初中' in tags:
        return '校友', '初中同学'
    if '青中' in tags or '青田' in tags or '黄山' in tags:
        return '校友', '青田中学'
    if 'MLBA' in tags:
        return '校友', 'MBA校友'

    return '其他', '微信联系人'


def best_name(r):
    """从微信记录中取最佳名字"""
    note = str(r[2] or '').strip()
    nick = str(r[3] or '').strip()
    wxid = str(r[0] or '').strip()
    wx = str(r[1] or '').strip()
    return note or nick or wx or wxid[:15]


def normalize(n):
    n = re.sub(r'[^一-鿿\w]', '', n).lower()
    return n


# 现有联系人索引
existing_norm = {normalize(c['name']) for c in contacts}
for c in contacts:
    for a in c.get('alias', []):
        existing_norm.add(normalize(a))

# ── 导入所有私聊联系人 ──
new_count = 0
match_count = 0
wxid_new = 0
by_relation = Counter()
no_wxid = 0

for r in private:
    name = best_name(r)
    n_name = normalize(name)
    if not name:
        continue

    # 去重
    if n_name in existing_norm:
        match_count += 1
        continue

    orig_id = str(r[0] or '').strip()
    wx_id = str(r[1] or '').strip()
    phone = str(r[6] or '').strip()
    location = '/'.join(filter(None, [str(r[7] or ''), str(r[8] or ''), str(r[9] or '')]))
    tag_str = str(r[5] or '').strip()
    signature = str(r[11] or '').strip()
    note_text = str(r[10] or '').strip()

    relation, sub_relation = classify_by_tags(tag_str)

    # platforms
    platforms = {}
    if orig_id:
        platforms['weixin'] = orig_id[:30]
    elif wx_id:
        platforms['weixin'] = wx_id[:30]

    if phone:
        platforms['phone'] = phone

    # tags
    tags = ['微信通讯录']
    if tag_str:
        for t in tag_str.replace('|', ',').split(','):
            t = t.strip()
            if t and t not in ('0', 'Grow', 'star', '常联系', 'Vul', 'forever9509'):
                tags.append(t)

    # notes
    notes_parts = []
    if note_text:
        notes_parts.append(f"备注:{note_text}")
    if location:
        notes_parts.append(location)
    if signature:
        notes_parts.append(f"签名:{signature[:30]}")

    contact = {
        'id': re.sub(r'[^a-zA-Z0-9一-鿿]', '', name)[:20] or f"wx_{len(contacts)+new_count}",
        'name': name,
        'relation': relation,
        'sub_relation': sub_relation,
        'strength': 2 if platforms else 1,
        'tags': tags,
        'platforms': platforms,
        'notes': '；'.join(notes_parts) if notes_parts else '',
        'source': '微信通讯录导出',
        'created': '2026-06-13'
    }
    contacts.append(contact)
    existing_norm.add(n_name)
    by_relation[relation] += 1
    new_count += 1

    # 存wxid映射
    if orig_id and orig_id.startswith('wxid_') and name not in wechat_ids:
        wechat_ids[name] = orig_id
        wxid_new += 1
    elif wx_id and not orig_id.startswith('wxid_') and name not in wechat_ids:
        wechat_ids[name] = orig_id or wx_id
        wxid_new += 1

    if not platforms:
        no_wxid += 1

# ── 写回 ──
with open(DATA / "contacts.json", 'w', encoding='utf-8') as f:
    json.dump(contacts, f, ensure_ascii=False, indent=2)

with open(DATA / "wechat_ids.json", 'w', encoding='utf-8') as f:
    json.dump(wechat_ids, f, ensure_ascii=False, indent=2)

# ── 统计 ──
print(f"=== 导入完成 ===")
print(f"新增联系人: {new_count}人")
print(f"匹配已有(去重): {match_count}人次")
print(f"新增wxid映射: {wxid_new}个")
print(f"无联系方式: {no_wxid}人")
print(f"\n联系人总数: {len(contacts)}人")
print(f"\n按关系分类:")
for rel, cnt in by_relation.most_common():
    print(f"  {rel}: {cnt}人")

rel_total = Counter(c['relation'] for c in contacts)
print(f"\n最终关系分布:")
for rel, cnt in rel_total.most_common():
    print(f"  {rel}: {cnt}人")

with_wx = sum(1 for c in contacts if c.get('platforms',{}).get('weixin'))
with_wxid = sum(1 for c in contacts if c.get('platforms',{}).get('weixin','').startswith('wxid_'))
print(f"\n含微信: {with_wx}人")
print(f"含wxid(可直发): {with_wxid}人")

# 更新时间线
with open(DATA / "timeline.json") as f:
    timeline = json.load(f)
timeline.append({
    'id': f't-allwx-{len(timeline)+1:03d}',
    'date': '2026-06-13',
    'summary': f'从微信通讯录导入全部{new_count}位联系人（含{with_wxid}个wxid），联系人总数达{len(contacts)}人',
    'type': 'milestone',
    'tags': ['微信通讯录', '全量导入']
})
with open(DATA / "timeline.json", 'w', encoding='utf-8') as f:
    json.dump(timeline, f, ensure_ascii=False, indent=2)
print(f"\n时间线已更新")

wb.close()
