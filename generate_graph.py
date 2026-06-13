#!/usr/bin/env python3
"""生成社交关系图谱"""
import json, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import networkx as nx
from collections import defaultdict

# 设置中文字体 — 使用系统字体
# 注册字体路径
font_paths = [
    '/System/Library/AssetsV2/com_apple_MobileAsset_Font8/86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Medium.ttc',
    '/System/Library/AssetsV2/com_apple_MobileAsset_Font8/53fe5be564086fefc7523ccd0a31200acf92e0e5.asset/AssetData/STHEITI.ttf',
]
for fp in font_paths:
    if os.path.exists(fp):
        fm.fontManager.addfont(fp)

# 设置全局字体
plt.rcParams['font.sans-serif'] = ['PingFang HK', 'STHeiti', 'Heiti TC']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')

# 加载数据
with open(os.path.join(DATA, 'contacts.json')) as f:
    contacts = json.load(f)
with open(os.path.join(DATA, 'timeline.json')) as f:
    events = json.load(f)

# ---------- 定义关系类别和颜色 ----------
RELATION_COLORS = {
    '同门': '#E74C3C',    # 红色 — 最紧密
    '校友': '#3498DB',    # 蓝色
    '同行': '#2ECC71',    # 绿色
    '创业': '#F39C12',    # 橙色
}
RELATION_ORDER = ['同门', '校友', '同行', '创业']  # 优先级

# 为每个关系分配子类别
def get_relation_color(rel):
    return RELATION_COLORS.get(rel, '#95A5A6')

# ---------- 构建图 ----------
G = nx.Graph()
G.add_node('陈颖芳（我）', type='self', rel='self', size=800)

relation_groups = defaultdict(list)  # relation -> [contacts]

for c in contacts:
    name = c['name']
    rel = c.get('relation', '校友')
    strength = c.get('strength', 2)
    tags = c.get('tags', [])
    sub = c.get('sub_relation', '')

    # 归属组
    relation_groups[rel].append(c)

    # 节点大小 = strength 映射
    size = 300 + strength * 60

    # 添加联系人节点
    G.add_node(name, type='contact', rel=rel, sub=sub, strength=strength, tags=tags, size=size)

    # 连到中心"我"
    weight = strength
    G.add_edge('陈颖芳（我）', name, weight=weight, rel=rel)

# ---------- 布局 ----------
pos = nx.spring_layout(G, k=0.6, iterations=50, seed=42)

# ---------- 绘图 ----------
fig, ax = plt.subplots(1, 1, figsize=(20, 14))
fig.patch.set_facecolor('#FAFAFA')

# 绘制连线 — 按关系类型分层
for rel, color in RELATION_COLORS.items():
    edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('rel') == rel]
    if edges:
        widths = [G[u][v]['weight'] * 1.5 for u, v in edges]
        nx.draw_networkx_edges(G, pos, edgelist=edges, width=widths,
                               edge_color=color, alpha=0.25, style='-', ax=ax)

# 绘制节点 — 按关系类型分层绘制（self优先在最上层）
node_colors = []
node_sizes = []
node_edge_colors = []

for node in G.nodes():
    data = G.nodes[node]
    if data.get('type') == 'self':
        node_colors.append('#2C3E50')
        node_edge_colors.append('#1A252F')
        node_sizes.append(800)
    else:
        rel = data.get('rel', '校友')
        color = get_relation_color(rel)
        node_colors.append(color)
        node_edge_colors.append('#FFFFFF')
        node_sizes.append(data.get('size', 400))

# 先画所有节点一批
nx.draw_networkx_nodes(G, pos, node_size=node_sizes,
                       node_color=node_colors, edgecolors=node_edge_colors,
                       linewidths=2, alpha=0.9, ax=ax)

# 标注 — 只用中文
labels = {}
for node in G.nodes():
    data = G.nodes[node]
    if data.get('type') == 'self':
        labels[node] = node
    else:
        # 显示名称 + 子关系缩写
        sub = data.get('sub', '')
        name_display = node
        if sub:
            name_display = f"{node}\n({sub})"
        else:
            name_display = node
        labels[node] = name_display

nx.draw_networkx_labels(G, pos, labels=labels, font_size=8,
                        font_color='#2C3E50', ax=ax)

# ---------- 图例 ----------
legend_elements = []
for rel, color in RELATION_COLORS.items():
    count = len(relation_groups.get(rel, []))
    legend_elements.append(mpatches.Patch(color=color, alpha=0.7,
                                          label=f'{rel} ({count}人)'))

# 强度图例
legend_elements.append(plt.Line2D([0], [0], marker='o', color='w',
                                   markerfacecolor='#95A5E6', markersize=8,
                                   label='强度1-2 (普通)'))
legend_elements.append(plt.Line2D([0], [0], marker='o', color='w',
                                   markerfacecolor='#2C3E50', markersize=10,
                                   label='强度3-4 (较强)'))
legend_elements.append(plt.Line2D([0], [0], marker='o', color='w',
                                   markerfacecolor='#E74C3C', markersize=12,
                                   label='强度5 (紧密)'))

ax.legend(handles=legend_elements, loc='upper left', fontsize=10,
          framealpha=0.9, edgecolor='#DDD')

# ---------- 统计信息 ----------
total = len(contacts)
strength_counts = defaultdict(int)
for c in contacts:
    strength_counts[c.get('strength', 0)] += 1

stats_text = (
    f"[关系统计]\n"
    f"联系人总数: {total}人\n"
    f"强度5(紧密): {strength_counts.get(5,0)}人\n"
    f"强度3-4(较强): {strength_counts.get(4,0)+strength_counts.get(3,0)}人\n"
    f"强度1-2(普通): {strength_counts.get(2,0)+strength_counts.get(1,0)}人\n"
    f"最近互动: 许封(今天)"
)
plt.text(0.01, 0.99, stats_text, transform=ax.transAxes, fontsize=11,
         verticalalignment='top',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))

# 标题
plt.title('我的社交关系图谱', fontsize=20,
          fontweight='bold', color='#2C3E50', pad=20)

ax.axis('off')

# ---------- 保存 ----------
out_path = os.path.join(DATA, 'relationship_graph.png')
plt.savefig(out_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"✅ 关系图谱已生成: {out_path}")
print(f"   总联系人: {total}人")
for rel in RELATION_ORDER:
    count = len(relation_groups.get(rel, []))
    print(f"   {rel}: {count}人")
plt.close()
