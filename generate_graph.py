#!/usr/bin/env python3
"""生成社交关系图谱"""
import json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import networkx as nx
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')

for fp in ['/System/Library/AssetsV2/com_apple_MobileAsset_Font8/86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc',
           '/System/Library/Fonts/STHeiti Medium.ttc']:
    if os.path.exists(fp):
        fm.fontManager.addfont(fp)
plt.rcParams['font.sans-serif'] = ['PingFang HK', 'STHeiti', 'Heiti TC']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

with open(os.path.join(DATA, 'contacts.json')) as f:
    contacts = json.load(f)

RELATION_COLORS = {
    '同门': '#E74C3C', '校友': '#3498DB', '同行': '#2ECC71',
    '创业': '#F39C12', '其他': '#95A5A6', '自己': '#2C3E50',
}

rel_groups = defaultdict(list)
for c in contacts:
    rel = c.get('relation', '其他')
    if rel not in RELATION_COLORS:
        rel = '其他'
    rel_groups[rel].append(c)

# 只画有微信或强度≥3的核心联系人（图谱不至于太密）
core = [c for c in contacts if c.get('strength', 1) >= 3 or c.get('platforms', {}).get('weixin')]

G = nx.Graph()
G.add_node('我', type='self', size=1000)

relation_groups = defaultdict(list)
for c in contacts:
    name = c['name']
    rel = c.get('relation', '其他')
    if rel not in RELATION_COLORS:
        rel = '其他'
    strength = c.get('strength', 2)
    size = 200 + strength * 50
    G.add_node(name, type='contact', rel=rel, strength=strength, size=size)
    G.add_edge('我', name, weight=strength, rel=rel)
    relation_groups[rel].append(c)

pos = nx.spring_layout(G, k=0.8, iterations=30, seed=42)

fig, ax = plt.subplots(1, 1, figsize=(20, 14))
fig.patch.set_facecolor('#FAFAFA')

for rel, color in RELATION_COLORS.items():
    edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('rel') == rel]
    if edges:
        widths = [G[u][v]['weight'] * 1.2 for u, v in edges]
        nx.draw_networkx_edges(G, pos, edgelist=edges, width=widths,
                               edge_color=color, alpha=0.2, style='-', ax=ax)

node_colors = []
node_sizes = []
for node in G.nodes():
    data = G.nodes[node]
    if data.get('type') == 'self':
        node_colors.append('#2C3E50')
        node_sizes.append(1000)
    else:
        rel = data.get('rel', '其他')
        node_colors.append(RELATION_COLORS.get(rel, '#95A5A6'))
        node_sizes.append(data.get('size', 300))

nx.draw_networkx_nodes(G, pos, node_size=node_sizes,
                       node_color=node_colors, edgecolors='#FFFFFF',
                       linewidths=1.5, alpha=0.85, ax=ax)

labels = {}
for node in G.nodes():
    data = G.nodes[node]
    if data.get('type') == 'self':
        labels[node] = node
    else:
        s = data.get('strength', 2)
        labels[node] = f"{node}\n({s})"

nx.draw_networkx_labels(G, pos, labels=labels, font_size=6,
                       font_color='#2C3E50', ax=ax)

legend = []
for rel, color in RELATION_COLORS.items():
    cnt = len(rel_groups.get(rel, []))
    if cnt > 0:
        legend.append(mpatches.Patch(color=color, alpha=0.7, label=f'{rel} ({cnt}人)'))

ax.legend(handles=legend, loc='upper left', fontsize=10, framealpha=0.9)
ax.axis('off')
plt.title(f'社交关系图谱 ({len(contacts)}人)', fontsize=18, fontweight='bold', color='#2C3E50', pad=20)

out_path = os.path.join(DATA, 'relationship_graph.png')
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'✅ 已生成: {out_path}')
print(f'联系人: {len(contacts)}人 | 图中节点: {len(G.nodes)}个')
for rel in RELATION_COLORS:
    cnt = len(rel_groups.get(rel, []))
    if cnt:
        print(f'  {rel}: {cnt}人')
plt.close()
