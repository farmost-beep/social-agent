#!/usr/bin/env python3
"""社交管家快速使用指南 PDF 生成器 — reportlab 美化版"""

import re
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

# ════════════════════════════════════
#  字体与配色
# ════════════════════════════════════

FONT = '/Library/Fonts/Arial Unicode.ttf'
pdfmetrics.registerFont(TTFont('AU', FONT))

C = {
    'primary':   HexColor('#2563eb'),
    'primary_dk':HexColor('#1d4ed8'),
    'accent':    HexColor('#f59e0b'),
    'bg_code':   HexColor('#1e293b'),
    'text':      HexColor('#1e293b'),
    'muted':     HexColor('#64748b'),
    'border':    HexColor('#e2e8f0'),
    'white':     white,
    'green':     HexColor('#16a34a'),
    'title_bg':  HexColor('#0f172a'),
    'hover':     HexColor('#f1f5f9'),
    'info_bg':   HexColor('#eff6ff'),
}

PW = 186 * mm  # page usable width


def esc(t):
    return t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def fin(t):
    """Inline formatting: **bold** `code`"""
    t = esc(t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'`(.+?)`', r'<font face="AU" size="8"><b><i>\1</i></b></font>', t)
    return t

def p(text, style='b', **kw):
    return Paragraph(fin(text), S[style], **kw)

def sp(h=5):
    return Spacer(1, h)

def hr(color=C['border'], thick=0.5, space=5):
    return HRFlowable(width='100%', thickness=thick, color=color, spaceAfter=space)

# ════════════════════════════════════
#  样式表
# ════════════════════════════════════

S = {}

def _ps(name, **kw):
    defaults = dict(fontName='AU')
    defaults.update(kw)
    S[name] = ParagraphStyle(name, **defaults)

_ps('ct', fontSize=28, leading=38, alignment=TA_CENTER, textColor=C['white'])
_ps('cs', fontSize=10, leading=16, alignment=TA_CENTER, textColor=HexColor('#94a3b8'))
_ps('cn', fontSize=9, leading=14, alignment=TA_CENTER, textColor=HexColor('#cbd5e1'))
_ps('h1', fontSize=20, leading=28, spaceBefore=6, spaceAfter=8, textColor=C['primary_dk'])
_ps('h2', fontSize=13, leading=18, spaceBefore=10, spaceAfter=4, textColor=C['primary'])
_ps('b', fontSize=9, leading=14, spaceBefore=1, spaceAfter=3, textColor=C['text'])
_ps('bs', fontSize=8, leading=12, spaceBefore=1, spaceAfter=2, textColor=C['muted'])
_ps('cb', fontSize=7.5, leading=11, spaceBefore=1, spaceAfter=1, leftIndent=2, textColor=HexColor('#e2e8f0'))
_ps('bl', fontSize=9, leading=14, spaceBefore=1, spaceAfter=1, leftIndent=16, bulletIndent=6, textColor=C['text'])
_ps('th', fontSize=8.5, leading=12, textColor=C['white'], alignment=TA_CENTER)
_ps('td', fontSize=8, leading=12, textColor=C['text'])
_ps('small', fontSize=7, leading=10, textColor=C['muted'])


# ════════════════════════════════════
#  组件
# ════════════════════════════════════

def code_block(text, width=None):
    """Dark code block."""
    w = width or PW - 4*mm
    lines = text.strip().split('\n')
    paras = []
    for line in lines:
        display = line.replace(' ', ' ')
        paras.append(Paragraph(display, S['cb']))
    if not paras:
        return [sp(2)]
    inner = Table([[paras]], colWidths=[w])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C['bg_code']),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return [sp(3), inner, sp(3)]


def make_table(header, rows, col_widths=None):
    """Styled table with header + alternating rows."""
    h = [Paragraph(c, S['th']) for c in header]
    data = [h]
    for r in rows:
        data.append([Paragraph(fin(str(c)), S['td']) for c in r])
    n = len(header)
    cw = col_widths or [PW / n] * n
    t = Table(data, colWidths=cw, repeatRows=1)
    cmds = [
        ('BACKGROUND', (0,0), (-1,0), C['primary']),
        ('TEXTCOLOR', (0,0), (-1,0), C['white']),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.4, C['border']),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(('BACKGROUND', (0,i), (-1,i), C['hover']))
    t.setStyle(TableStyle(cmds))
    return t


def info_box(text, icon='💡'):
    """Info callout box."""
    content = f'<b>{icon}</b> {esc(text)}'
    sty = ParagraphStyle('ib', fontName='AU', fontSize=8.5, leading=13,
                         textColor=C['primary_dk'], leftIndent=2, spaceBefore=1, spaceAfter=3)
    t = Table([[Paragraph(content, sty)]], colWidths=[PW - 2*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C['info_bg']),
        ('BOX', (0,0), (-1,-1), 0.5, C['primary']),
        ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    return [sp(2), t, sp(2)]


def section_divider():
    return hr(C['primary'], 1, 6)


# ════════════════════════════════════
#  卡片包装器
# ════════════════════════════════════

def card(title, body_lines, color_hex, width=None):
    """A single card with colored left accent."""
    w = width or PW - 4*mm
    items = [Paragraph(f'<b>{title}</b>', ParagraphStyle('ct_',
        fontName='AU', fontSize=10.5, leading=15, textColor=color_hex, spaceAfter=3))]
    for line in body_lines:
        items.append(Paragraph(fin(line), S['b']))
    inner = Table([[items]], colWidths=[w - 4*mm])
    inner.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    wrap = Table([[inner]], colWidths=[w])
    wrap.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.8, color_hex),
        ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ROUNDEDCORNERS', (0,0), (-1,-1), 3),
    ]))
    return [wrap, sp(4)]


# ════════════════════════════════════
#  构建 PDF
# ════════════════════════════════════

def build(output):
    doc = SimpleDocTemplate(output, pagesize=A4,
        topMargin=16*mm, bottomMargin=14*mm,
        leftMargin=18*mm, rightMargin=16*mm,
        title='社交关系AI管家 · 快速使用指南',
        author='社交管家团队')

    story = []

    # ════════════════════════════════
    #  第1页 · 封面 + 快速安装 + 快速上手
    # ════════════════════════════════

    story.append(sp(25))

    # 品牌标题块
    title_block = [
        [Paragraph('社交关系AI管家', ParagraphStyle('tt',
            fontName='AU', fontSize=28, leading=38, alignment=TA_CENTER,
            textColor=C['white']))],
        [Paragraph('快 速 使 用 指 南', ParagraphStyle('tt2',
            fontName='AU', fontSize=16, leading=24, alignment=TA_CENTER,
            textColor=HexColor('#93c5fd')))],
        [sp(3)],
        [Paragraph('一个本地运行的AI插件，自动追踪你所有社交关系中的<br/>"最近干了什么"和"下一步该干什么"，帮你拟好消息，推到该去的地方。', S['cs'])],
    ]
    tb = Table(title_block, colWidths=[PW - 2*mm])
    tb.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C['title_bg']),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (0,0), 16),
        ('BOTTOMPADDING', (0,-1), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('ROUNDEDCORNERS', (0,0), (-1,-1), 4),
    ]))
    story.append(tb)
    story.append(sp(8))

    # ── ⚡ 快速安装 ──
    story.append(p('⚡ 快速安装', 'h1'))
    story.append(section_divider())

    install_rows = [
        [Paragraph('<b>1</b>', ParagraphStyle('n1', fontName='AU',
            fontSize=12, leading=16, alignment=TA_CENTER, textColor=C['primary'])),
         Paragraph('<b>安装 Skill</b>', ParagraphStyle('n1l', fontName='AU',
             fontSize=9.5, leading=14, textColor=C['text'])),
         Paragraph('<font face="AU" size="8.5">npx skills add social-agent -g -y</font>',
             ParagraphStyle('n1r', fontName='AU', fontSize=8, leading=13, textColor=C['text']))],
        [Paragraph('<b>2</b>', ParagraphStyle('n2', fontName='AU',
            fontSize=12, leading=16, alignment=TA_CENTER, textColor=C['primary'])),
         Paragraph('<b>克隆仓库</b>', ParagraphStyle('n2l', fontName='AU',
             fontSize=9.5, leading=14, textColor=C['text'])),
         Paragraph('<font face="AU" size="8.5">git clone https://github.com/farmost-beep/social-agent.git</font>',
             ParagraphStyle('n2r', fontName='AU', fontSize=8, leading=13, textColor=C['text']))],
        [Paragraph('<b>3</b>', ParagraphStyle('n3', fontName='AU',
            fontSize=12, leading=16, alignment=TA_CENTER, textColor=C['primary'])),
         Paragraph('<b>导入联系人</b>', ParagraphStyle('n3l', fontName='AU',
             fontSize=9.5, leading=14, textColor=C['text'])),
         Paragraph('<font face="AU" size="8.5">cd ~/.claude/skills/social-agent && python3 import_contacts.py</font>',
             ParagraphStyle('n3r', fontName='AU', fontSize=8, leading=13, textColor=C['text']))],
        [Paragraph('<b>4</b>', ParagraphStyle('n4', fontName='AU',
            fontSize=12, leading=16, alignment=TA_CENTER, textColor=C['primary'])),
         Paragraph('<b>查看仪表盘</b>', ParagraphStyle('n4l', fontName='AU',
             fontSize=9.5, leading=14, textColor=C['text'])),
         Paragraph('<font face="AU" size="8.5">python3 social.py dashboard</font>',
             ParagraphStyle('n4r', fontName='AU', fontSize=8, leading=13, textColor=C['text']))],
        [Paragraph('<b>5</b>', ParagraphStyle('n5', fontName='AU',
            fontSize=12, leading=16, alignment=TA_CENTER, textColor=C['primary'])),
         Paragraph('<b>AI 对话</b>', ParagraphStyle('n5l', fontName='AU',
             fontSize=9.5, leading=14, textColor=C['text'])),
         Paragraph('<font face="AU" size="8.5">python3 agent.py --chat "最近该联系谁"</font>',
             ParagraphStyle('n5r', fontName='AU', fontSize=8, leading=13, textColor=C['text']))],
    ]
    it = Table(install_rows, colWidths=[7*mm, 28*mm, PW - 39*mm])
    it.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, C['border']),
        ('LINEBELOW', (0,-1), (-1,-1), 1.5, C['primary']),
        ('LEFTPADDING', (0,0), (0,0), 2), ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(it)
    story.append(sp(2))

    story.append(p('前置条件：Python 3.9+ · Claude Code · (可选) wechat-claude-code 桥接', 'small'))
    story.append(sp(6))

    # ── 🚀 快速上手 ──
    story.append(p('🚀 快速上手 · 3 个核心操作', 'h1'))
    story.append(section_divider())

    story.extend(card('📝 记录互动',
        ['在 Claude Code 对话中说：',
         '<b>"记一下：和张总聊了项目合作"</b>',
         '→ 自动创建联系人 → 记录时间线 → 提取待办'],
        C['primary']))

    story.extend(card('🔍 查询冷却关系',
        ['在 Claude Code 对话中说：',
         '<b>"最近该联系谁"</b>',
         '→ 列出 14 天+ 未联系的冷却关系'],
        C['accent']))

    story.extend(card('✍️ AI 拟稿',
        ['在 Claude Code 对话中说：',
         '<b>"给王哥拟条消息"</b>',
         '→ AI 生成草稿 → 确认 → 微信直发'],
        C['green']))

    story.append(PageBreak())

    # ════════════════════════════════
    #  第2页 · 微信交互 + CLI
    # ════════════════════════════════

    story.append(p('💬 微信互动（最方便）', 'h1'))
    story.append(section_divider())
    story.append(p('对接 <b>wechat-claude-code</b> 桥接后，直接在微信发消息操控管家：', 'b'))
    story.append(sp(2))

    wx_rows = [
        ['你说', '管家做什么'],
        ['记一下：和张总聊了合作', '记录互动，自动提取待办'],
        ['张总最近咋样', '查询最近互动 + 待办'],
        ['最近该联系谁', '列出 14 天+ 冷却关系'],
        ['最近有啥要跟进的', '列出 P0/P1 待办'],
        ['给王哥拟条消息', 'AI 生成草稿，确认后发送'],
        ['给王哥拟条消息，正式一点', '带语气调节的 AI 拟稿'],
        ['王哥的微信ID是xxx', '存储微信 ID，可直发'],
        ['李哥是李总', '设别名，说"李哥"也能找到'],
        ['有多少联系人', '返回实时统计'],
    ]
    story.append(make_table(wx_rows[0], wx_rows[1:],
        col_widths=[PW*0.42, PW*0.58]))
    story.append(sp(6))

    # ── CLI ──
    story.append(p('🖥️ 命令行操作', 'h1'))
    story.append(section_divider())
    story.append(p('在 <b>~/.claude/skills/social-agent/</b> 目录下执行：', 'b'))
    story.append(sp(1))

    cmd_rows = [
        [Paragraph('<font face="AU" size="8"><b>python3 social.py dashboard</b></font>',
            ParagraphStyle('cr', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('全局仪表盘', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 social.py status [联系人]</b></font>',
            ParagraphStyle('cr2', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('查看时间线', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 social.py log &lt;联系人&gt; &lt;摘要&gt;</b></font>',
            ParagraphStyle('cr3', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('记录互动，自动提取待办', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 social.py todos</b></font>',
            ParagraphStyle('cr4', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('查看待办', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 social.py draft &lt;联系人&gt; [--tone]</b></font>',
            ParagraphStyle('cr5', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('AI 拟稿', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 social.py send &lt;联系人&gt; [--tone]</b></font>',
            ParagraphStyle('cr6', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('拟稿 + 微信发送', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 social.py check</b></font>',
            ParagraphStyle('cr7', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('检查冷却关系', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 agent.py --chat "消息"</b></font>',
            ParagraphStyle('cr8', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('AI 自然语言交互', S['td'])],
        [Paragraph('<font face="AU" size="8"><b>python3 agent.py --morning/--afternoon/--evening</b></font>',
            ParagraphStyle('cr9', fontName='AU', fontSize=8, leading=12, textColor=C['text'])),
         Paragraph('定时推送', S['td'])],
    ]
    ct = Table(cmd_rows, colWidths=[PW*0.55, PW*0.45])
    ct.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, C['border']),
        ('LINEBELOW', (0,-1), (-1,-1), 0.8, C['primary']),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('BACKGROUND', (0,0), (0,-1), HexColor('#f1f5f9')),
    ]))
    story.append(ct)

    # ════════════════════════════════
    #  第3页 · 高级功能 + 数据导入 + 推送
    # ════════════════════════════════

    story.append(PageBreak())
    story.append(p('🔧 高级功能', 'h1'))
    story.append(section_divider())

    # 别名
    story.append(p('🔖 别名系统', 'h2'))
    story.append(p('不用记全名，随时设别名：', 'b'))
    story.extend(code_block('"李哥是李总"         # Claude 对话中直接说\npython3 agent.py --chat "李哥是李总"  # 或命令行'))
    story.append(p('之后说"李哥"就能找到对应的联系人。', 'b'))
    story.append(sp(2))

    # 微信直发
    story.append(p('📨 微信直发', 'h2'))
    story.append(p('存好对方微信内部 ID 后，消息直接推送到对方微信：', 'b'))
    story.extend(code_block(
        'python3 agent.py --chat "王哥的微信ID是wxid_xxx@im.wechat"\n'
        '→ "给王哥发消息：周末一起吃饭"\n'
        '→ 拟稿 → 确认 → 直发'))
    story.append(p('内部 ID 需对方给机器人发过消息后从日志提取。', 'bs'))
    story.append(sp(2))

    # AI拟稿
    story.append(p('🎨 AI 拟稿 · 语气调节', 'h2'))
    story.append(p('支持三种语气：', 'b'))
    tone_rows = [
        ['亲切（默认）', '朋友聊天风格，用"你"', '日常社交'],
        ['正式', '专业语气，用"您"', '商务客户'],
        ['简洁', '不超过 30 字，直说重点', '熟人/快速确认'],
    ]
    story.append(make_table(['语气', '风格', '适用场景'], tone_rows,
        col_widths=[PW*0.25, PW*0.45, PW*0.30]))
    story.extend(code_block('python3 social.py draft 李总 --tone 正式'))
    story.append(sp(2))

    # 待办
    story.append(p('📋 待办自动管理', 'h2'))
    story.append(p('记录互动时，系统自动提取待办并设定优先级：', 'b'))
    story.append(make_table(['优先级', '触发关键词', '默认截止'],
        [['P0 🔴', '投资/融资/条款/DD/引荐/签约', '3 天'],
         ['P1 🟡', '普通待办', '7 天']],
        col_widths=[PW*0.2, PW*0.5, PW*0.3]))
    story.append(p('超期待办自动标红提醒。', 'bs'))
    story.append(sp(4))

    # ── 数据导入 ──
    story.append(p('📥 数据导入', 'h1'))
    story.append(section_divider())
    story.extend(code_block('cd ~/.claude/skills/social-agent\npython3 import_contacts.py'))
    story.append(p('自动扫描本地数据源，按姓名去重，自动分类（同门/同行/创业/校友），有微信则强度+1。', 'b'))

    src_rows = [
        ['校友联系方式', 'deliverables/career/校友联系方式.xls', '科大校友总表'],
        ['校友联系方式2', 'deliverables/career/校友联系方式2.xls', '补充表'],
        ['校友活动终表', 'deliverables/career/校友活动终表.xls', '活动报名表'],
        ['VCF 通讯录', 'deliverables/.../*.vcf', '微信导出通讯录'],
    ]
    story.append(make_table(['数据源', '路径', '说明'], src_rows,
        col_widths=[PW*0.2, PW*0.5, PW*0.3]))
    story.extend(info_box('同门判定只看 dept 和 company 字段，不看 grade（避免"09 级"误判为"九系"）', '⚠️'))

    # ── 自动推送 ──
    story.append(p('⏰ 自动化推送', 'h1'))
    story.append(section_divider())
    story.append(p('配置 crontab 后可定时推送提醒到微信：', 'b'))
    push_rows = [
        ['☀️ 09:00', '早间概览', '待办 + 冷却关系 + 超期预警'],
        ['💡 14:00', '午后建议', '14 天+ 冷却关系'],
        ['🌙 21:00', '晚间回顾', '今日总结 + 待办状态'],
    ]
    story.append(make_table(['时段', '内容', '说明'], push_rows,
        col_widths=[PW*0.2, PW*0.3, PW*0.5]))
    story.extend(code_block(
        '# crontab -e\n'
        '0 9 * * * cd ~/.claude/skills/social-agent && python3 agent.py\n'
        '0 14 * * * cd ~/.claude/skills/social-agent && python3 agent.py --afternoon\n'
        '0 21 * * * cd ~/.claude/skills/social-agent && python3 agent.py --evening'))

    # ════════════════════════════════
    #  第4页 · 文件结构 + FAQ
    # ════════════════════════════════

    story.append(PageBreak())
    story.append(p('📁 文件结构', 'h1'))
    story.append(section_divider())
    story.extend(code_block(
        '~/.claude/skills/social-agent/\n'
        '├── social.py              CLI 入口\n'
        '├── agent.py               Agent 守护进程\n'
        '├── intent.py              意图识别引擎\n'
        '├── import_contacts.py     批量导入\n'
        '├── generate_graph.py      关系图谱\n'
        '├── web.py                 Web 界面(可选)\n'
        '├── SKILL.md               Skill 注册文件\n'
        '├── lib/\n'
        '│   ├── engine.py          核心引擎\n'
        '│   ├── ai.py              AI 拟稿\n'
        '│   └── push.py            微信推送\n'
        '└── data/                  纯本地数据\n'
        '    ├── contacts.json      联系人库\n'
        '    ├── timeline.json      互动时间线\n'
        '    ├── todos.json         待办队列\n'
        '    ├── wechat_ids.json    微信 ID 映射\n'
        '    └── relationship_graph.png'))
    story.append(sp(8))

    # FAQ
    story.append(p('❓ 常见问题', 'h1'))
    story.append(section_divider())
    qa_rows = []
    qas = [
        ('数据安全吗？', '纯本地 JSON，不上云。备份只需备份 data/ 目录。'),
        ('没有微信桥接能用吗？', '能。核心功能在 Claude Code 对话中直接使用。'),
        ('怎么备份？', 'cp -r data/ ~/backups/social-agent-$(date +%Y%m%d)'),
        ('误分类怎么办？', '编辑 contacts.json 修改 relation/tags，重跑 dashboard 确认。'),
        ('别名和微信ID冲突吗？', '不冲突。别名用于索引，微信ID用于直发，两套独立系统。'),
    ]
    for q, a in qas:
        sty = ParagraphStyle('q_', fontName='AU', fontSize=8.5, leading=12,
                             textColor=C['primary_dk'], spaceAfter=1)
        sty2 = ParagraphStyle('a_', fontName='AU', fontSize=8, leading=12,
                              textColor=C['text'])
        qa_rows.append([
            Paragraph(f'<b>{esc(q)}</b>', sty),
            Paragraph(esc(a), sty2),
        ])
    qat = Table(qa_rows, colWidths=[PW*0.32, PW*0.68])
    qat.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, C['border']),
        ('LINEBELOW', (0,-1), (-1,-1), 0.8, C['primary']),
        ('BACKGROUND', (0,0), (0,-1), HexColor('#eff6ff')),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(qat)
    story.append(sp(12))

    # Footer
    story.append(hr(C['muted'], 0.5, 4))
    story.append(p('仓库：github.com/farmost-beep/social-agent · 数据纯本地不上云 · v0.1', 'small'))
    story.append(sp(2))
    story.append(p('"一个比你更记得住人情世故的AI管家。"', 'small'))

    # ════════════════════════════════
    #  生成
    # ════════════════════════════════
    doc.build(story)
    print(f'✅ PDF: {output}')


if __name__ == '__main__':
    out = '/Users/cyingfang/.claude/skills/social-agent/社交管家使用说明书.pdf'
    build(out)
