#!/usr/bin/env python3
"""从微信通讯录导出导入联系人到社交AI管家"""
import json, re, openpyxl
from pathlib import Path
from collections import defaultdict

BASE = Path("/Users/cyingfang/.claude/skills/social-agent")
DATA = BASE / "data"

# 加载现有联系人
with open(DATA / "contacts.json") as f:
    contacts = json.load(f)

# 加载wechat_ids映射
wxid_file = DATA / "wechat_ids.json"
with open(wxid_file) as f:
    wechat_ids = json.load(f)

# 读取微信通讯录导出
path = "/Users/cyingfang/claude/deliverables/career/微信通讯录导出-20260613.xlsx"
wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
ws = wb.active

rows = list(ws.iter_rows(values_only=True))
headers = [str(c) if c else f'col_{j}' for j, c in enumerate(rows[0])]
data = rows[1:]

# 只处理私聊联系人
private = [r for r in data if r[4] == '私聊']
print(f"私聊联系人: {len(private)}人")

# 按标签分组
ustc_contacts = [r for r in private if '0ustc' in str(r[5]).lower() or 'ustc' in str(r[5]).lower()]
print(f"  USTC校友: {len(ustc_contacts)}人")

# ── 1. 匹配现有联系人，更新微信ID ──
def normalize(name):
    """标准化名字用于匹配"""
    n = name.replace(' ', '').replace('　', '').replace('-', '').replace('_', '').lower()
    # 去除非中英文数字
    n = re.sub(r'[^一-鿿\w]', '', n)
    return n

def match_wechat_contact(wx_row, contact):
    """判断微信通讯录行是否匹配某个联系人"""
    wx_note = str(wx_row[2] or '').strip()   # 备注名称
    wx_nick = str(wx_row[3] or '').strip()   # 昵称
    wx_id = str(wx_row[1] or '').strip()     # 微信号
    wx_orig = str(wx_row[0] or '').strip()   # 原始ID

    c_name = normalize(contact['name'])
    c_alias = [normalize(a) for a in contact.get('alias', [])]
    c_notes = normalize(contact.get('notes', ''))

    wx_names = [normalize(wx_note), normalize(wx_nick)]

    # 精确匹配
    for wn in wx_names:
        if wn == c_name:
            return True
        if wn in c_alias:
            return True

    # 模糊匹配: 备注名包含联系人名或反之
    for wn in wx_names:
        if wn and c_name and (wn in c_name or c_name in wn):
            if len(wn) >= 2 and len(c_name) >= 2:
                return True

    # 微信号匹配备注
    if wx_id and (wx_id.lower() in c_notes or c_name in wx_id.lower()):
        return True

    return False

# 建立反向索引：微信号/原始ID → 微信行
wx_by_id = {}
for r in private:
    orig_id = str(r[0] or '').strip()
    wx_id = str(r[1] or '').strip()
    if orig_id:
        wx_by_id[orig_id] = r
    if wx_id:
        wx_by_id[wx_id] = r

# 匹配并更新
matched = 0
new_wxid = 0
for c in contacts:
    # 先查已有platforms.weixin是否能匹配
    wx_name = c.get('platforms', {}).get('weixin', '')
    if wx_name:
        for rid, r in wx_by_id.items():
            if str(r[2] or '') == wx_name or str(r[3] or '') == wx_name:
                orig_id = str(r[0] or '').strip()
                if orig_id and c['name'] not in wechat_ids:
                    wechat_ids[c['name']] = orig_id
                    new_wxid += 1
                matched += 1
                break

    # 别名/名称匹配
    if c['name'] not in wechat_ids:
        for r in private:
            if match_wechat_contact(r, c):
                orig_id = str(r[0] or '').strip()
                if orig_id and orig_id.startswith('wxid_'):
                    wechat_ids[c['name']] = orig_id
                    new_wxid += 1
                matched += 1
                break

print(f"\n已匹配现有联系人: {matched}人")
print(f"新增微信内部ID: {new_wxid}个")

# ── 2. 导入新联系人（USTC校友中未在通讯录的）──
existing_names = {normalize(c['name']) for c in contacts}
existing_aliases = set()
for c in contacts:
    for a in c.get('alias', []):
        existing_aliases.add(normalize(a))

new_imported = 0
for r in ustc_contacts:
    wx_note = str(r[2] or '').strip()
    wx_nick = str(r[3] or '').strip()
    wx_id = str(r[1] or '').strip()
    orig_id = str(r[0] or '').strip()
    phone = str(r[6] or '').strip()
    location = '/'.join(filter(None, [str(r[7] or ''), str(r[8] or ''), str(r[9] or '')]))

    # 取最合适的名字
    name = wx_note or wx_nick or wx_id or orig_id[:15]
    n_name = normalize(name)

    # 去重
    if n_name in existing_names or n_name in existing_aliases:
        continue

    # 也检查昵称是否有重叠
    nick_norm = normalize(wx_nick)
    if nick_norm and nick_norm in existing_names:
        continue

    # 构建联系人
    platforms = {}
    if orig_id:
        platforms['weixin'] = wx_nick or wx_note or orig_id[:10]
    elif wx_id:
        platforms['weixin'] = wx_id

    tags = ['科大校友', '微信通讯录']

    notes_parts = []
    if wx_note:
        notes_parts.append(f"备注:{wx_note}")
    if location:
        notes_parts.append(location)
    if phone:
        notes_parts.append(f"电话:{phone}")

    contact = {
        'id': re.sub(r'[^a-zA-Z0-9一-鿿]', '', n_name)[:20] or f"wx_{len(contacts)+len(new_imported)}",
        'name': name,
        'relation': '校友',
        'sub_relation': '科大校友',
        'strength': 2,
        'tags': tags,
        'platforms': platforms,
        'notes': '；'.join(notes_parts) if notes_parts else '',
        'source': '微信通讯录导出',
        'created': '2026-06-13'
    }
    contacts.append(contact)
    existing_names.add(n_name)

    # 存wxid到映射
    if orig_id and orig_id.startswith('wxid_') and name not in wechat_ids:
        wechat_ids[name] = orig_id

    new_imported += 1

print(f"新增联系人: {new_imported}人")

# ── 3. 写回 ──
with open(DATA / "contacts.json", 'w', encoding='utf-8') as f:
    json.dump(contacts, f, ensure_ascii=False, indent=2)

with open(wxid_file, 'w', encoding='utf-8') as f:
    json.dump(wechat_ids, f, ensure_ascii=False, indent=2)

# ── 4. 统计 ──
from collections import Counter
rel_count = Counter(c['relation'] for c in contacts)
with_wx = sum(1 for c in contacts if c.get('platforms', {}).get('weixin'))
with_wxid = len(wechat_ids)

print(f"\n=== 导入完成 ===")
print(f"联系人总数: {len(contacts)}人")
for rel, cnt in rel_count.most_common():
    print(f"  {rel}: {cnt}人")
print(f"含微信名: {with_wx}人")
print(f"含微信内部ID(wxid): {with_wxid}个")
print(f"新增微信ID映射: {new_wxid}个")

# 显示前几个匹配到的wxid
print(f"\n新增的微信内部ID（前10个）:")
added = 0
for name, wxid in sorted(wechat_ids.items()):
    if wxid.startswith('wxid_') and added < 10:
        print(f"  {name}: {wxid}")
        added += 1

wb.close()
