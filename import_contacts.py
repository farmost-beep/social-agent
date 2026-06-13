#!/usr/bin/env python3
"""从校友联系文件批量导入联系人到社交AI管家"""
import json, os, re, xlrd

BASE = '/Users/cyingfang/.claude/skills/social-agent'
DATA = os.path.join(BASE, 'data')

# ---------- 1. 加载现有联系人 ----------
with open(os.path.join(DATA, 'contacts.json')) as f:
    existing = json.load(f)

existing_names_clean = {}
for c in existing:
    # 名字标准化：去掉空格、小写
    clean = c['name'].replace(' ', '').replace('　', '').lower()
    existing_names_clean[clean] = c

print(f"现有联系人: {len(existing)}人")

# ---------- 2. 读取数据源 ----------
def read_xls1(path):
    """读取校友联系方式.xls 总表"""
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_name('总表')
    result = []
    for r in range(1, sh.nrows):
        name = str(sh.cell_value(r, 0)).strip()
        if not name or name == '陈颖芳':
            continue
        result.append({
            'name': name,
            'phone': str(sh.cell_value(r, 1)).strip() if r < sh.nrows else '',
            'grade': str(sh.cell_value(r, 3)).strip().replace('级级','级').replace('级级级','级'),
            'dept': str(sh.cell_value(r, 4)).strip(),
            'company': str(sh.cell_value(r, 5)).strip(),
            'wx': str(sh.cell_value(r, 7)).strip(),
        })
    return result

def read_xls2(path):
    """读取校友联系方式2.xls"""
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_name('Sheet1')
    result = []
    for r in range(4, sh.nrows):
        name = str(sh.cell_value(r, 0)).strip()
        if not name:
            continue
        result.append({
            'name': name,
            'phone': str(sh.cell_value(r, 1)).strip() if sh.ncols > 1 else '',
            'dept': str(sh.cell_value(r, 2)).strip() if sh.ncols > 2 else '',
            'company': str(sh.cell_value(r, 4)).strip() if sh.ncols > 4 else '',
            'wx': str(sh.cell_value(r, 6)).strip() if sh.ncols > 6 else '',
        })
    return result

# ---------- 3. 合并去重 ----------
contacts1 = read_xls1('deliverables/career/校友联系方式.xls')
contacts2 = read_xls2('deliverables/career/校友联系方式2.xls')
print(f"总表1: {len(contacts1)}人, 总表2: {len(contacts2)}人")

# 合并，按名称去重
seen = set()
all_raw = []
for c in contacts1 + contacts2:
    key = c['name'].replace(' ', '').lower()
    if key not in seen:
        seen.add(key)
        all_raw.append(c)

# 优先用总表1的数据（信息更完整）
# 总表2中有相同名字的，用总表2的微信覆盖
covered = {}
for c in all_raw:
    key = c['name'].replace(' ', '').lower()
    if key not in covered:
        covered[key] = c
    else:
        # 用总表2的wx覆盖
        if c.get('wx'):
            covered[key]['wx'] = c['wx']
        if c.get('company') and not covered[key].get('company'):
            covered[key]['company'] = c['company']

all_raw = list(covered.values())

# ---------- 4. 去重现有联系人 ----------
# 定义模糊匹配
def name_match(name1, name2):
    """检查两个名字是否指向同一人（处理英文名+中文名组合）"""
    n1 = name1.replace(' ', '').lower()
    n2 = name2.replace(' ', '').lower()
    if n1 == n2:
        return True
    # 短名在长名中
    if len(n1) >= 2 and n1 in n2:
        return True
    if len(n2) >= 2 and n2 in n1:
        return True
    return False

new_contacts_raw = []
dup_count = 0
for c in all_raw:
    is_dup = False
    for existing_name, ex_c in existing_names_clean.items():
        if name_match(c['name'], existing_name):
            # 名字匹配：如果现有记录缺平台信息，补充
            platforms = ex_c.get('platforms', {})
            orig_name = ex_c['name']
            if c.get('wx') and not platforms.get('weixin'):
                platforms['weixin'] = c['wx']
            if c.get('company') and not ex_c.get('notes', ''):
                ex_c['notes'] = c['company']
            if platforms != ex_c.get('platforms', {}):
                ex_c['platforms'] = platforms
            dup_count += 1
            is_dup = True
            break
    if not is_dup:
        new_contacts_raw.append(c)

print(f"已存在的重复: {dup_count}人")
print(f"待导入新联系人: {len(new_contacts_raw)}人")

# ---------- 5. 分类和富化 ----------
# 同门关键词
TONG_MEN_KEYWORDS = ['9系', '精密机械', '九系']
# 金融行业关键词
FINANCE_KEYWORDS = ['银行', '证券', '基金', '保险', '金融', '投资', '理财',
                     '信托', '期货', '量化', '资本', '资产', '财富', '股',
                     '债券', '交易', '风控', '信贷', '融资', '租赁', '保险']
# 创业关键词
STARTUP_KEYWORDS = ['创始人', 'CEO', '总经理', '执行董事', '创始', '合伙人', '董事长']

def classify_contact(c):
    """分类联系人：同门/同行/创业/校友"""
    name = c['name']
    dept = c.get('dept', '')
    company = c.get('company', '')
    grade = c.get('grade', '')
    text = f"{dept} {company} {grade}"

    # 1. 先检查是否同门（仅限dept/company含九系/9系，排除grade字段以免误匹配入学年份）
    dept_company_text = f"{dept} {company}"
    for kw in TONG_MEN_KEYWORDS:
        if kw in dept_company_text or kw in company:
            return {
                'relation': '同门',
                'sub_relation': '九系/精密机械',
                'strength': 3,
                'tags': ['科大校友', '九系']
            }

    # 2. 检查是否创业（先于同行，因为创业也可能在金融行业）
    for kw in STARTUP_KEYWORDS:
        if kw in company or kw in text:
            return {
                'relation': '创业',
                'sub_relation': '创业校友',
                'strength': 3,
                'tags': ['科大校友', '创业']
            }

    # 3. 检查是否金融同行
    for kw in FINANCE_KEYWORDS:
        if kw in company or kw in text:
            # 进一步分类
            if any(bk in company for bk in ['银行']):
                return {
                    'relation': '同行',
                    'sub_relation': '金融/银行',
                    'strength': 2,
                    'tags': ['科大校友', '金融同行', '银行']
                }
            elif any(sk in company for sk in ['证券', '投资银行']):
                return {
                    'relation': '同行',
                    'sub_relation': '金融/证券',
                    'strength': 2,
                    'tags': ['科大校友', '金融同行', '证券']
                }
            elif any(fk in company for fk in ['基金', '基金管理']):
                return {
                    'relation': '同行',
                    'sub_relation': '金融/基金',
                    'strength': 2,
                    'tags': ['科大校友', '金融同行', '基金']
                }
            else:
                return {
                    'relation': '同行',
                    'sub_relation': '金融',
                    'strength': 2,
                    'tags': ['科大校友', '金融同行']
                }

    # 4. 默认：校友
    grade_tag = ""
    grade_clean = grade.replace('级', '').replace(' ', '')
    if grade_clean:
        grade_tag = grade_clean

    tags = ['科大校友']
    if grade_tag:
        tags.append(grade_tag)

    return {
        'relation': '校友',
        'sub_relation': '科大校友',
        'strength': 2,
        'tags': tags
    }

# ---------- 6. 生成新联系人 ----------
new_contacts = []
for c in new_contacts_raw:
    cls = classify_contact(c)

    # 构建简介
    notes_parts = []
    if c.get('grade'):
        notes_parts.append(f"{c['grade']}级")
    if c.get('dept'):
        notes_parts.append(c['dept'])
    if c.get('company'):
        notes_parts.append(c['company'])
    notes = '，'.join(notes_parts) if notes_parts else ''

    # 有微信/手机号的，强度+1
    strength = cls['strength']
    platforms = {}
    if c.get('wx'):
        platforms['weixin'] = c['wx']
        if strength < 4:
            strength += 1

    contact = {
        'id': re.sub(r'[^a-zA-Z0-9一-鿿]', '', c['name']).lower()[:20],
        'name': c['name'],
        'relation': cls['relation'],
        'sub_relation': cls['sub_relation'],
        'strength': strength,
        'tags': cls['tags'],
        'platforms': platforms,
        'notes': notes,
        'created': '2026-06-13',
        'source': '校友活动报名表'
    }
    new_contacts.append(contact)

# ---------- 7. 写入 ----------
all_contacts = existing + new_contacts

with open(os.path.join(DATA, 'contacts.json'), 'w', encoding='utf-8') as f:
    json.dump(all_contacts, f, ensure_ascii=False, indent=2)

# ---------- 8. 统计输出 ----------
print(f"\n✅ 导入完成！")
print(f"  现有: {len(existing)}人 → 最新: {len(all_contacts)}人")
print(f"  新增: {len(new_contacts)}人")
print()

# 按关系类别统计
from collections import Counter
rel_count = Counter(c['relation'] for c in new_contacts)
for rel, cnt in rel_count.most_common():
    print(f"  {rel}: {cnt}人")

print()
# 有微信的
with_wx = [c for c in new_contacts if c.get('platforms', {}).get('weixin')]
print(f"  含微信/手机号可联系: {len(with_wx)}人")
if with_wx:
    print(f"  前十:")
    for c in with_wx[:10]:
        wx = c['platforms'].get('weixin', '')
        print(f"    📱 {c['name']} → 微信:{wx}")
    if len(with_wx) > 10:
        print(f"    ...还有{len(with_wx)-10}人")

print()
# 同门提示
tongmen = [c for c in new_contacts if c['relation'] == '同门']
if tongmen:
    print(f"  🔴 同门新发现: {len(tongmen)}人")
    for c in tongmen:
        print(f"    {c['name']} ({c.get('notes','')})")

# 更新timeline
with open(os.path.join(DATA, 'timeline.json'), 'r', encoding='utf-8') as f:
    timeline = json.load(f)

timeline.append({
    'id': f"t-import-{len(timeline)+1:03d}",
    'date': '2026-06-13',
    'summary': f"从校友活动报名表批量导入{len(new_contacts)}位科大校友联系人（含{len(with_wx)}个联系方式），至此联系人总数达{len(all_contacts)}人",
    'type': 'milestone',
    'tags': ['批量导入', '校友']
})

with open(os.path.join(DATA, 'timeline.json'), 'w', encoding='utf-8') as f:
    json.dump(timeline, f, ensure_ascii=False, indent=2)

print(f"\n  📝 时间线已更新")
