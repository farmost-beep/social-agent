#!/usr/bin/env python3
"""社交关系AI管家 Web版 — 关键关系录入+看板"""
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import lib.engine as engine
from lib.ai import draft_message

app = Flask(__name__)

HOME = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>社交关系AI管家</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,Helvetica,sans-serif;background:#f5f5f5;color:#333;padding:16px;max-width:800px;margin:0 auto}
.header{background:linear-gradient(135deg,#07c160,#06ad56);color:#fff;padding:24px 20px;border-radius:10px;margin-bottom:20px}
.header h1{font-size:22px;margin-bottom:4px}
.header p{font-size:13px;opacity:.9}
.nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.nav a{background:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;color:#333;font-size:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.nav a:hover{background:#f0faf4}
.card{background:#fff;border-radius:10px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.card h3{font-size:15px;margin-bottom:8px}
.stat-row{display:flex;gap:16px;flex-wrap:wrap}
.stat{flex:1;min-width:100px;background:#f8faf8;border-radius:8px;padding:14px;text-align:center}
.stat .num{font-size:28px;font-weight:bold;color:#07c160}
.stat .label{font-size:12px;color:#888;margin-top:4px}
.contact-item{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid #f0f0f0}
.contact-item:last-child{border-bottom:none}
.contact-name{font-size:15px;font-weight:500}
.contact-role{font-size:12px;color:#888;margin-top:2px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#f0faf4;color:#07c160}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#f0f4ff;color:#3c8cff;margin:2px}
.todo-item{padding:10px 0;border-bottom:1px solid #f0f0f0;display:flex;align-items:center;gap:10px}
.todo-item:last-child{border-bottom:none}
.p0{color:#e74c3c;font-weight:bold;font-size:12px}
.p1{color:#f39c12;font-weight:bold;font-size:12px}
.done{text-decoration:line-through;color:#999}
form{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
label{display:block;font-size:13px;color:#666;margin:12px 0 4px}
input,select,textarea{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:14px;font-family:inherit}
textarea{resize:vertical;min-height:60px}
.btn{background:#07c160;color:#fff;border:none;padding:12px 24px;border-radius:6px;font-size:15px;cursor:pointer;margin-top:16px;width:100%}
.btn:hover{background:#06ad56}
.btn-secondary{background:#fff;color:#333;border:1px solid #ddd;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer;text-decoration:none;display:inline-block}
.draft-box{background:#fff8f0;border:1px solid #ffe0b0;border-radius:8px;padding:14px;margin:12px 0;font-size:14px;line-height:1.8}
.footer{text-align:center;padding:20px;font-size:12px;color:#aaa}
@media(max-width:600px){.stat{min-width:80px}.stat .num{font-size:22px}}
</style>
</head>
<body>
<div class="header">
  <h1>社交关系AI管家</h1>
  <p>一个比你更记得住人情世故的AI管家</p>
</div>

<div class="nav">
  <a href="/">仪表盘</a>
  <a href="/contacts">联系人</a>
  <a href="/add">添加联系人</a>
  <a href="/todos">待办</a>
</div>

<div class="card">
  <h3>概览</h3>
  <div class="stat-row">
    <div class="stat"><div class="num">{{d.total_contacts}}</div><div class="label">联系人</div></div>
    <div class="stat"><div class="num">{{d.pending_todos}}</div><div class="label">待办</div></div>
    <div class="stat"><div class="num">{{d.overdue_todos|length}}</div><div class="label">超期</div></div>
    <div class="stat"><div class="num">{{d.cold_relationships|length}}</div><div class="label">冷却</div></div>
  </div>
</div>

<div class="card">
  <h3>按角色</h3>
  <div class="stat-row">
    {% for role, count in d.by_role.items() %}
    <div class="stat"><div class="num" style="font-size:20px;">{{count}}</div><div class="label">{{role}}</div></div>
    {% endfor %}
  </div>
</div>

{% if todos %}
<div class="card">
  <h3>待办事项</h3>
  {% for t in todos %}
  <div class="todo-item">
    <span class="{{'p0' if t.priority=='P0' else 'p1'}}">{{t.priority}}</span>
    <span>{{t.contact_name or t.contact}} - {{t.task[:40]}}</span>
    <span style="font-size:12px;color:#999;margin-left:auto">{{t.due}}</span>
  </div>
  {% endfor %}
</div>
{% endif %}

<div class="card">
  <h3>最近联系人</h3>
  {% for c in contacts %}
  <div class="contact-item">
    <div>
      <div class="contact-name">
        <a href="/contact/{{c.id}}" style="color:#333;text-decoration:none">{{c.name}}</a>
      </div>
      <div><span class="badge">{{c.role}}</span>{% for t in c.tags %}<span class="tag">{{t}}</span>{% endfor %}</div>
    </div>
    <span style="font-size:12px;color:#888">{{c.strength}}/5</span>
  </div>
  {% endfor %}
</div>

<div class="footer">社交关系AI管家 v1.0</div>
</body>
</html>
'''

CONTACTS_PAGE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>联系人 - 社交关系AI管家</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,Helvetica,sans-serif;background:#f5f5f5;color:#333;padding:16px;max-width:800px;margin:0 auto}
.header{background:#07c160;color:#fff;padding:20px;border-radius:10px 10px 0 0}
.header h1{font-size:20px}
.nav{background:#fff;padding:12px 16px;border-bottom:1px solid #eee;display:flex;gap:16px;font-size:14px}
.nav a{color:#333;text-decoration:none}
.nav a:hover{color:#07c160}
.list{background:#fff;border-radius:0 0 10px 10px;padding:0 16px}
.item{padding:14px 0;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center}
.item:last-child{border-bottom:none}
.name{font-size:16px;font-weight:500;text-decoration:none;color:#333}
.role{font-size:12px;color:#888}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#f0faf4;color:#07c160;margin-right:4px}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#f0f4ff;color:#3c8cff;margin:2px}
.empty{padding:40px;text-align:center;color:#999}
</style>
</head>
<body>
<div class="header"><h1>联系人</h1></div>
<div class="nav">
  <a href="/">仪表盘</a>
  <a href="/add">添加联系人</a>
  <a href="/todos">待办</a>
</div>
<div class="list">
{% for c in contacts %}
<div class="item">
  <div>
    <a href="/contact/{{c.id}}" class="name">{{c.name}}</a>
    <div style="margin-top:4px"><span class="badge">{{c.role}}</span>
    {% for t in c.tags %}<span class="tag">{{t}}</span>{% endfor %}</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:12px;color:#999">强度 {{c.strength}}/5</div>
    <div style="font-size:11px;color:#aaa">{{c.stage or '-'}}</div>
  </div>
</div>
{% else %}
<div class="empty">暂无联系人，<a href="/add">添加第一个</a></div>
{% endfor %}
</div>
</body>
</html>
'''

CONTACT_DETAIL = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{{c.name}} - 社交关系AI管家</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,Helvetica,sans-serif;background:#f5f5f5;color:#333;padding:16px;max-width:800px;margin:0 auto}
.card{background:#fff;border-radius:10px;padding:20px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.header{background:linear-gradient(135deg,#07c160,#06ad56);color:#fff;border-radius:10px;padding:24px 20px;margin-bottom:16px}
.header h1{font-size:22px;margin-bottom:4px}
.header .role{font-size:13px;opacity:.9}
.info-row{display:flex;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:14px}
.info-row .label{width:80px;color:#888}
.timeline-item{padding:12px 0;border-bottom:1px solid #f0f0f0}
.timeline-item .date{font-size:12px;color:#999}
.timeline-item .text{font-size:14px;line-height:1.6;margin:4px 0}
.timeline-item .pending{font-size:12px;color:#e74c3c;background:#fff0f0;padding:4px 8px;border-radius:4px;display:inline-block;margin-top:4px}
.nav a{color:#07c160;text-decoration:none;font-size:14px;display:inline-block;margin-bottom:12px}
.tag{display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;background:#f0f4ff;color:#3c8cff;margin:2px}
.empty{padding:30px;text-align:center;color:#999;font-size:14px}
.btn-secondary{background:#fff;color:#333;border:1px solid #ddd;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer;text-decoration:none;display:inline-block;margin-right:8px}
</style>
</head>
<body>
<div class="nav"><a href="/">仪表盘</a> / <a href="/contacts">联系人</a> / {{c.name}}</div>
<div class="header">
  <h1>{{c.name}}</h1>
  <div class="role">{{c.role}} · 强度 {{c.strength}}/5 · {{c.stage or '待定'}}</div>
</div>

<div class="card">
  <h3 style="margin-bottom:10px">信息</h3>
  {% if c.tags %}<div>{% for t in c.tags %}<span class="tag">{{t}}</span>{% endfor %}</div>{% endif %}
  {% if c.notes %}<div class="info-row"><span class="label">备注</span><span>{{c.notes}}</span></div>{% endif %}
</div>

<div class="card">
  <h3 style="margin-bottom:10px">最近互动</h3>
  {% if records %}
  {% for r in records[:10] %}
  <div class="timeline-item">
    <div class="date">{{r.date}} · {{r.type}}</div>
    <div class="text">{{r.summary}}</div>
    {% if r.pending %}<div class="pending">待办: {{r.pending}}</div>{% endif %}
  </div>
  {% endfor %}
  {% else %}
  <div class="empty">暂无互动记录</div>
  {% endif %}
</div>
</body>
</html>
'''

ADD_PAGE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>添加联系人 - 社交关系AI管家</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,Helvetica,sans-serif;background:#f5f5f5;color:#333;padding:16px;max-width:600px;margin:0 auto}
.header{background:#07c160;color:#fff;padding:20px;border-radius:10px 10px 0 0}
.header h1{font-size:20px}
.nav{background:#fff;padding:12px 16px;border-bottom:1px solid #eee;display:flex;gap:16px;font-size:14px}
.nav a{color:#333;text-decoration:none}
form{background:#fff;padding:20px;border-radius:0 0 10px 10px}
label{display:block;font-size:13px;color:#666;margin:14px 0 4px}
input,select,textarea{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:14px;font-family:inherit}
textarea{resize:vertical;min-height:60px}
.btn{background:#07c160;color:#fff;border:none;padding:12px 24px;border-radius:6px;font-size:15px;cursor:pointer;margin-top:18px;width:100%}
.btn:hover{background:#06ad56}
.success{background:#f0faf4;color:#07c160;padding:12px;border-radius:6px;margin-bottom:12px;font-size:14px;text-align:center}
</style>
</head>
<body>
<div class="header"><h1>添加联系人</h1></div>
<div class="nav"><a href="/">仪表盘</a><a href="/contacts">联系人</a><a href="/todos">待办</a></div>

{% if msg %}<div style="padding:12px 0"><div class="success">{{msg}}</div></div>{% endif %}

<form method="POST" action="/add">
  <label>ID（英文/拼音，唯一标识）</label>
  <input type="text" name="contact_id" placeholder="lizong" required>

  <label>姓名</label>
  <input type="text" name="name" placeholder="李总" required>

  <label>角色</label>
  <select name="role">
    <option value="投资人">投资人</option>
    <option value="合伙人">合伙人</option>
    <option value="客户">客户</option>
    <option value="导师">导师</option>
    <option value="其他">其他</option>
  </select>

  <label>标签（空格分隔）</label>
  <input type="text" name="tags" placeholder="A轮 AI赛道">

  <label>当前阶段</label>
  <input type="text" name="stage" placeholder="TS谈判中">

  <label>关系强度（1-5）</label>
  <select name="strength">
    <option value="3">3 - 普通</option>
    <option value="4">4 - 密切</option>
    <option value="5">5 - 核心</option>
    <option value="2">2 - 一般</option>
    <option value="1">1 - 浅层</option>
  </select>

  <label>备注</label>
  <textarea name="notes" placeholder="通过谁认识的、有什么背景信息"></textarea>

  <button class="btn" type="submit">保存联系人</button>
</form>
</body>
</html>
'''

TODOS_PAGE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>待办 - 社交关系AI管家</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,Helvetica,sans-serif;background:#f5f5f5;color:#333;padding:16px;max-width:600px;margin:0 auto}
.header{background:#07c160;color:#fff;padding:20px;border-radius:10px 10px 0 0}
.header h1{font-size:20px}
.nav{background:#fff;padding:12px 16px;border-bottom:1px solid #eee;display:flex;gap:16px;font-size:14px}
.nav a{color:#333;text-decoration:none}
.list{background:#fff;padding:0 16px;border-radius:0 0 10px 10px}
.item{padding:14px 0;border-bottom:1px solid #f0f0f0;display:flex;align-items:center;gap:10px}
.item:last-child{border-bottom:none}
.p0{background:#ffecec;color:#e74c3c;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold}
.p1{background:#fff8e8;color:#f39c12;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold}
.content{flex:1}
.content .name{font-size:14px;font-weight:500}
.content .task{font-size:13px;color:#666;margin-top:2px}
.due{font-size:11px;color:#999}
.over{color:#e74c3c}
.empty{padding:40px;text-align:center;color:#999}
</style>
</head>
<body>
<div class="header"><h1>待办事项</h1></div>
<div class="nav"><a href="/">仪表盘</a><a href="/contacts">联系人</a><a href="/add">添加联系人</a></div>
<div class="list">
{% for t in todos %}
<div class="item">
  <span class="{{'p0' if t.priority=='P0' else 'p1'}}">{{t.priority}}</span>
  <div class="content">
    <div class="name">{{t.contact_name or t.contact}}</div>
    <div class="task">{{t.task}}</div>
  </div>
  <div class="due {% if t.due_soon %}over{% endif %}">{{t.due}}</div>
</div>
{% else %}
<div class="empty">暂无待办 ✅</div>
{% endfor %}
</div>
</body>
</html>
'''

@app.route('/')
def home():
    d = engine.get_dashboard()
    todos = engine.list_todos()
    for t in todos:
        c = engine.get_contact(t["contact"])
        t["contact_name"] = c["name"] if c else t["contact"]
    contacts = engine.list_contacts()
    return render_template_string(HOME, d=d, todos=todos[:5], contacts=contacts)

@app.route('/contacts')
def contacts():
    return render_template_string(CONTACTS_PAGE, contacts=engine.list_contacts())

@app.route('/contact/<contact_id>')
def contact_detail(contact_id):
    c = engine.get_contact(contact_id)
    if not c:
        return "联系人不存在", 404
    records = engine.list_timeline(contact=contact_id, days=365)
    return render_template_string(CONTACT_DETAIL, c=c, records=records)

@app.route('/add', methods=['GET', 'POST'])
def add_contact_web():
    msg = ""
    if request.method == 'POST':
        cid = request.form.get('contact_id', '').strip()
        name = request.form.get('name', '').strip()
        role = request.form.get('role', '其他')
        tags_s = request.form.get('tags', '').strip()
        stage = request.form.get('stage', '').strip()
        strength = int(request.form.get('strength', 3))
        notes = request.form.get('notes', '').strip()
        tags = [t for t in tags_s.split() if t] if tags_s else []
        if cid and name:
            ok, msg_text = engine.add_contact(cid, name, role, tags, None, notes)
            if ok:
                # Update stage and strength
                contacts = engine._load(engine.CONTACTS_FILE)
                for c in contacts:
                    if c["id"] == cid:
                        if stage: c["stage"] = stage
                        c["strength"] = strength
                engine._save(engine.CONTACTS_FILE, contacts)
                msg = f"已添加: {name}"
            else:
                msg = msg_text
        else:
            msg = "ID和姓名为必填项"
    return render_template_string(ADD_PAGE, msg=msg)

@app.route('/todos')
def todos_page():
    todos = engine.list_todos()
    for t in todos:
        c = engine.get_contact(t["contact"])
        t["contact_name"] = c["name"] if c else t["contact"]
        t["due_soon"] = t.get("due", "") and t["due"] < engine.date.today().isoformat()
    return render_template_string(TODOS_PAGE, todos=todos)

if __name__ == '__main__':
    print("社交关系AI管家 Web版")
    print(f"打开浏览器访问: http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
