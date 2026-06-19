#!/usr/bin/env python3
"""社交关系图谱生成器 — 关系图谱 · v1.0

读取 contacts.json + timeline.json → 生成交互式HTML关系图谱
用法: python3 tools/relationship_graph.py [--output 关系图谱.html]
"""
import json, sys, os
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "关系图谱.html"

# ── 颜色方案 ──
ROLE_COLORS = {
    "校友": "#4A90D9", "校友/创业": "#4A90D9", "同门": "#7B68EE",
    "同行": "#2ECC71", "同行/创业": "#2ECC71",
    "创业": "#E67E22", "导师": "#E74C3C", "合作": "#1ABC9C",
    "family": "#E74C3C", "self": "#95A5A6", "其他": "#95A5A6",
}
DEFAULT_COLOR = "#95A5A6"

# ── 加载数据 ──
with open(DATA_DIR / "contacts.json") as f:
    contacts = json.load(f)
with open(DATA_DIR / "timeline.json") as f:
    timeline = json.load(f)
with open(DATA_DIR / "todos.json") as f:
    todos = json.load(f)

# ── 构建活跃联系人集合 ──
active_ids = set()
for t in timeline:
    if t.get("contact"):
        active_ids.add(t["contact"])
for t in todos:
    if t.get("contact"):
        active_ids.add(t["contact"])

# 强度≥3的关键联系人
for c in contacts:
    if c.get("strength", 3) >= 3:
        active_ids.add(c["id"])

# 有笔记/记忆的联系人（有画像信息）
for c in contacts:
    notes = c.get("notes", "")
    if notes and len(notes) > 30:  # 有实质内容
        active_ids.add(c["id"])
    if c.get("memories"):
        active_ids.add(c["id"])

# 家人
for c in contacts:
    if c.get("relation") in ("family",) and c.get("name") != "陈颖芳":
        active_ids.add(c["id"])

# ── 构建联系人映射 ──
contact_map = {c["id"]: c for c in contacts}

# ── 提取群组信息 ──
# 群组: 从tags中提取 "群:*" 标签
group_members = defaultdict(list)
for c in contacts:
    if c["id"] not in active_ids:
        continue
    for tag in c.get("tags", []):
        if tag.startswith("群:") or tag.startswith("群聊"):
            group_members[tag].append(c["id"])

# 子关系/部门级关联（同角色+同子关系 = 真关联）
sub_role_groups = defaultdict(list)
for c in contacts:
    if c["id"] not in active_ids:
        continue
    sub = c.get("sub_relation", "")
    if sub:
        sub_role_groups[f"{c.get('relation','?')}:{sub}"].append(c["id"])

# ── 生成节点和边 ──
nodes = []
edges = []
seen_edges = set()

def add_edge(a, b, label="", weight=1, color="#b0b0b0"):
    key = tuple(sorted([a, b]))
    if key not in seen_edges:
        seen_edges.add(key)
        edges.append({"from": a, "to": b, "title": label, "width": weight, "color": {"color": color}})

# 群组强关联（同在一个微信群 = 真实社交关系）
for group, members in group_members.items():
    for i in range(len(members)):
        for j in range(i+1, len(members)):
            add_edge(members[i], members[j], group.replace("群:", ""), 3, "#3498db")

# 子关系关联（同行+同子领域 = 真关联）
for group, members in sub_role_groups.items():
    for i in range(min(len(members), 50)):  # 限制每组最多50人
        for j in range(i+1, min(len(members), 50)):
            add_edge(members[i], members[j], "", 1, "#95a5a6")

# 互动关联（有共同互动的人）
interaction_pairs = defaultdict(int)
for i in range(len(timeline)):
    for j in range(i+1, min(i+10, len(timeline))):
        a, b = timeline[i].get("contact"), timeline[j].get("contact")
        if a and b and a != b and a in active_ids and b in active_ids:
            interaction_pairs[tuple(sorted([a, b]))] += 1
for (a, b), count in interaction_pairs.items():
    if count >= 2:  # 至少2次同时在时间线中出现
        add_edge(a, b, f"互动{count}次", min(count, 5), "#2ecc71")

# 构建节点数据
role_counts = defaultdict(int)
for c in contacts:
    if c["id"] in active_ids:
        role = c.get("relation", "其他")
        role_counts[role] += 1

for c in contacts:
    if c["id"] not in active_ids:
        continue
    name = c.get("name", c["id"])
    role = c.get("relation", "其他")
    strength = c.get("strength", 3)
    tags = c.get("tags", [])

    # 节点大小: strength * 5 + 5
    size = max(10, strength * 6)

    # 高亮有记忆/待办的
    has_memories = len(c.get("memories", [])) > 0
    has_todo = any(t.get("contact") == c["id"] for t in todos if t.get("status") == "pending")

    title_lines = [f"<b>{name}</b>", f"角色: {role}", f"强度: {strength}/5"]
    if tags:
        title_lines.append(f"标签: {', '.join(tags[:8])}")
    if has_todo:
        pending = [t for t in todos if t.get("contact") == c["id"] and t.get("status") == "pending"]
        if pending:
            title_lines.append(f"<br/><b>待办:</b>")
            for p in pending[:3]:
                title_lines.append(f"· {p['task'][:30]}")
    title = "<br/>".join(title_lines)

    color = ROLE_COLORS.get(role, DEFAULT_COLOR)

    nodes.append({
        "id": c["id"],
        "label": name,
        "title": title,
        "size": size,
        "color": color,
        "group": role,
        "borderWidth": 3 if has_todo else 1,
        "borderWidthSelected": 4,
        "font": {"size": 12, "face": "PingFang SC, Microsoft YaHei, sans-serif"},
    })

print(f"节点: {len(nodes)} | 边: {len(edges)}")
print(f"角色分布: {dict(role_counts)}")

# ── 生成HTML ──
nodes_json = json.dumps(nodes, ensure_ascii=False)
edges_json = json.dumps(edges, ensure_ascii=False)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>社交关系图谱</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: PingFang SC, Microsoft YaHei, sans-serif; background: #f5f6fa; }
#header {
  background: linear-gradient(135deg, #2c3e50, #3498db);
  color: white; padding: 16px 24px;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 2px 10px rgba(0,0,0,0.15);
  position: sticky; top: 0; z-index: 100;
}
#header h1 { font-size: 20px; font-weight: 600; }
#header .stats { font-size: 13px; opacity: 0.9; }
#header .stats span { margin-left: 16px; }
#legend {
  display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 24px;
  background: white; border-bottom: 1px solid #e8e8e8;
  position: sticky; top: 56px; z-index: 99;
}
.legend-item {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; padding: 2px 10px;
  border-radius: 12px; background: #f0f0f0; cursor: pointer;
  transition: all 0.2s;
}
.legend-item:hover { transform: scale(1.05); }
.legend-item .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.legend-item.active { background: #e0e0e0; font-weight: 600; }
#network { width: 100%; height: calc(100vh - 120px); background: white; }
#tooltip { display: none; }
#search-box {
  margin-left: 16px; padding: 4px 12px;
  border: none; border-radius: 16px;
  font-size: 13px; width: 180px;
  background: rgba(255,255,255,0.2); color: white;
  outline: none; transition: all 0.3s;
}
#search-box::placeholder { color: rgba(255,255,255,0.6); }
#search-box:focus { background: rgba(255,255,255,0.3); width: 240px; }
</style>
</head>
<body>
<div id="header">
  <div style="display:flex;align-items:center;gap:12px">
    <h1>🕸️ 社交关系图谱</h1>
    <input id="search-box" placeholder="搜索联系人..." />
  </div>
  <div class="stats">
    <span>👤 <b>NODES_COUNT</b> 人</span>
    <span>🔗 <b>EDGES_COUNT</b> 条关系</span>
    <span>📅 <span id="update-date">今天</span></span>
  </div>
</div>
<div id="legend">LEGEND_ITEMS</div>
<div id="network"></div>

<script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<script>
const nodes = new vis.DataSet(NODES_DATA);
const edges = new vis.DataSet(EDGES_DATA);

const container = document.getElementById('network');
const data = { nodes, edges };
const options = {
  nodes: {
    shape: 'dot',
    scaling: { min: 10, max: 40, label: { enabled: true } },
    font: { size: 12, face: 'PingFang SC, Microsoft YaHei, sans-serif' },
    borderWidth: 1, borderWidthSelected: 3,
  },
  edges: {
    width: 1, color: { color: '#b0b0b0', highlight: '#3498db' },
    smooth: { type: 'continuous' },
    font: { size: 8, face: 'PingFang SC' },
  },
  physics: {
    solver: 'forceAtlas2Based',
    forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 180, springConstant: 0.02 },
    stabilization: { iterations: 200 },
  },
  interaction: {
    hover: true, tooltipDelay: 200,
    navigationButtons: true, keyboard: true,
  },
  groups: GROUP_DEFS,
};

const network = new vis.Network(container, data, options);

// 搜索
document.getElementById('search-box').addEventListener('input', function() {
  const q = this.value.trim().toLowerCase();
  if (!q) { nodes.forEach(n => nodes.update({ id: n.id, opacity: 1 })); return; }
  nodes.forEach(n => {
    const match = n.label.toLowerCase().includes(q);
    nodes.update({ id: n.id, opacity: match ? 1 : 0.1 });
  });
  if (q) {
    const match = nodes.get().filter(n => n.label.toLowerCase().includes(q));
    if (match.length > 0) network.selectNodes([match[0].id]);
  }
});

// 图例筛选
document.querySelectorAll('.legend-item').forEach(el => {
  el.addEventListener('click', function() {
    const group = this.dataset.group;
    const active = this.classList.contains('active');
    if (group === 'all') {
      document.querySelectorAll('.legend-item').forEach(i => i.classList.remove('active'));
      nodes.forEach(n => nodes.update({ id: n.id, hidden: false }));
      this.classList.add('active');
      return;
    }
    this.classList.toggle('active');
    const enabled = new Set();
    document.querySelectorAll('.legend-item.active').forEach(i => enabled.add(i.dataset.group));
    nodes.forEach(n => {
      const hidden = enabled.size > 0 && !enabled.has(n.group);
      nodes.update({ id: n.id, hidden });
    });
  });
});

// 窗口自适应
window.addEventListener('resize', () => network.fit());
</script>
</body>
</html>"""

# 构建图例
color_map = defaultdict(list)
for n in nodes:
    color_map[n["group"]].append(n["color"])

legend_items = '<div class="legend-item active" data-group="all">全部</div>'
for role, color in sorted(ROLE_COLORS.items()):
    if role in role_counts and role_counts[role] > 0:
        count = role_counts[role]
        legend_items += f'<div class="legend-item active" data-group="{role}"><span class="dot" style="background:{color}"></span>{role}({count})</div>'

# 角色组定义
group_defs = {}
for role, color in ROLE_COLORS.items():
    if role in role_counts:
        group_defs[role] = {"color": {"background": color, "border": color}, "shape": "dot"}

html = HTML_TEMPLATE.replace("NODES_DATA", nodes_json)
html = html.replace("EDGES_DATA", edges_json)
html = html.replace("LEGEND_ITEMS", legend_items)
html = html.replace("NODES_COUNT", str(len(nodes)))
html = html.replace("EDGES_COUNT", str(len(edges)))
html = html.replace("GROUP_DEFS", json.dumps(group_defs))

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✅ 关系图谱已生成: {OUTPUT}")
print(f"   浏览器打开即可查看（支持搜索/缩放/图例筛选/悬停详情）")
