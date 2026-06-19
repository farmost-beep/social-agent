#!/usr/bin/env python3
"""社交关系AI管家 — 一个比你更记得住人情世故的AI管家。

用法:
  social.py add-contact <ID> [--name NAME] [--role ROLE] [--sub-relation SUB] [--tags TAGS] [--notes NOTES]  添加联系人
  social.py edit-contact <ID> [--name NAME] [--role ROLE] [--sub-relation SUB] [--strength N] [--tags TAGS] [--notes NOTES]  编辑联系人
  social.py search <QUERY> [--field name|tags|notes]                                     搜索联系人
  social.py note <CONTACT> <CONTENT> [--tags TAGS]                                       添加记忆备注
  social.py adjust [--apply]                                                            分析/执行强度调整建议
  social.py adjust [--apply]                                                            分析/执行强度调整建议
  social.py birthdays [--days 30]                                                        查看近期生日
  social.py log <CONTACT> <摘要>                                                         记录互动
  social.py todos [--priority P0]                                                        查看待办
  social.py done <todo-id>                                                               完成待办
  social.py draft <CONTACT> [--tone 亲切]                                                 AI拟稿
  social.py send <CONTACT> [--tone 亲切]                                                  拟稿并发送
  social.py status [<contact>]                                                           查看状态/时间线
  social.py dashboard                                                                    仪表盘
  social.py check                                                                        检查需跟进的提醒
  social.py enrich [--batch N] [--dry-run] [--force] [--stats] [--web]                      批量画像补全（P0，--web 启用网络信源）
"""
import sys, argparse
from engine import *
from ai import draft_message, generate_reminder
from push import push_to_wechat, send_message
from enrich import enrich_contact, count_from_log

def cmd_dashboard(args):
    d = get_dashboard()
    print(f"\n{'='*40}")
    print(f"  社交关系AI管家 · 仪表盘")
    print(f"{'='*40}")
    print(f"  联系人: {d['total_contacts']}人")
    print(f"  各角色: {d['by_role']}")
    print(f"  待办: {d['pending_todos']}项 (超期{d['overdue_todos'].__len__()}项)")
    print(f"  近7天活动: {d['recent_activities']}条")
    print(f"  冷却关系: 🔴{len(d['cold_relationships'])}个  🟡{len(d.get('warm_relationships',[]))}个")
    for c in d['cold_relationships']:
        print(f"    🔴 {c['contact']} — {c['days']}天未联系")
    for c in d.get('warm_relationships', []):
        print(f"    🟡 {c['contact']} — {c['days']}天未联系")
    print(f"{'='*40}\n")
    # Show top todos
    todos = list_todos()
    if todos:
        print("🔴 优先待办:")
        for t in todos[:5]:
            c = get_contact(t["contact"])
            name = c["name"] if c else t["contact"]
            print(f"  [{t['priority']}] {name} — {t['task']} (截止{t.get('due','?')})")
    return 0

def cmd_check(args):
    """Check all relationships and generate reminders."""
    contacts = list_contacts()
    reminders = []
    for c in contacts:
        records = list_timeline(contact=c["id"], days=60)
        if not records:
            reminders.append((c["name"], 999, "暂无互动记录"))
            continue
        last = records[0]
        days_since = (date.today() - date.fromisoformat(last["date"])).days
        if days_since >= 14:
            reminders.append((c["name"], days_since, last.get("summary", "")))

    if not reminders:
        print("✅ 所有关系都在14天内联系过，无需提醒")
        return 0

    print(f"\n📢 需要跟进的关系 ({len(reminders)}个):")
    print("-" * 40)
    for name, days, summary in reminders:
        if days >= 21:
            print(f"  🔴 {name} — {days}天未联系")
        elif days >= 14:
            print(f"  🟡 {name} — {days}天未联系")
        if summary:
            print(f"     上次: {summary[:40]}")
    print()
    return 0

def cmd_enrich(args):
    """AI 批量画像补全管道 (P0)。"""
    opts = _parse_opts(args, ["--batch", "--dry-run", "--force", "--stats"])
    # 解析 flags
    dry_run = "--dry-run" in args
    force = "--force" in args
    stats = "--stats" in args
    use_web = "--web" in args
    batch = int(opts.get("--batch", "10"))

    if stats:
        s = get_enrichment_stats()
        log_stats = count_from_log()
        print(f"\n📊 画像补全统计")
        print(f"{'='*40}")
        print(f"  联系人总数:    {s['total']}人")
        print(f"  已补全:        {s['enriched']}人")
        print(f"  待补全:        {s['pending']}人 ({s['pending_pct']}%)")
        # 从日志回读置信度统计
        if log_stats["high"] or log_stats["medium"] or log_stats["low"]:
            print(f"  按置信度:      高{log_stats['high']}人 / 中{log_stats['medium']}人 / 低{log_stats['low']}人")
        # 已补全按角色分布
        if s["by_relation"]:
            print(f"  已补全角色分布:")
            for rel, cnt in sorted(s["by_relation"].items(), key=lambda x: -x[1]):
                print(f"    {rel}: {cnt}人")
        # 待补全按强度分布
        if s["by_strength_pending"]:
            print(f"  待补全强度分布: {s['by_strength_pending']}")
        return 0

    # 获取候选人
    candidates = get_enrichment_candidates(batch_size=batch, force=force)
    if not candidates:
        print("✅ 没有待补全的联系人（可加 --force 重新处理已补全的）")
        return 0

    web_flag = " 🌐" if use_web else ""

    if dry_run:
        print(f"\n🔍 预览模式: 下一批 {len(candidates)} 位候选人{web_flag}\n")
        print(f"  {'姓名':12s} {'强度':4s} {'已有角色':8s} {'信息密度':6s}")
        print(f"  {'-'*40}")
        for c in candidates:
            relation = c.get("relation", c.get("role", "")) or "未设定"
            tags_count = len(c.get("tags", []))
            has_notes = "📝" if c.get("notes") else "  "
            info = f"tags{tags_count}" if tags_count else (has_notes if c.get("notes") else "仅名称")
            print(f"  {c['name']:12s} {c.get('strength',3):4d} {relation:8s} {info:6s}")
        print(f"\n💡 执行: python3 social.py enrich --batch {batch}{' --web' if use_web else ''}")
        return 0

    # 执行补全
    mode = "🌐 带网络信源" if use_web else "🔧 本地信源"
    print(f"\n{mode} 批量画像补全: {len(candidates)} 人\n")
    enriched = skipped = errors = 0
    for i, contact in enumerate(candidates, 1):
        result = enrich_contact(contact, dry_run=False, use_web=use_web)
        status = result.get("status", "?")
        conf = result.get("confidence", 0)
        name = result.get("name", "?")

        if status == "enriched":
            enriched += 1
            rel = result.get("actions", [{}])[0].get("to", "?") if result.get("actions") else "?"
            print(f"  ✅ [{i}/{len(candidates)}] {name} → {rel} (conf={conf})")
        elif status == "enriched_light":
            enriched += 1
            print(f"  📝 [{i}/{len(candidates)}] {name} 追加备注 (conf={conf})")
        elif status == "skipped":
            skipped += 1
            reason = result.get("reason", "")
            print(f"  ⏭️  [{i}/{len(candidates)}] {name} 跳过 ({reason})")
        elif status == "no_update":
            skipped += 1
            print(f"  ➖ [{i}/{len(candidates)}] {name} 无需更新")
        else:
            errors += 1
            err = result.get("error", "未知错误")
            print(f"  ❌ [{i}/{len(candidates)}] {name} 失败: {err}")

    print(f"\n{'='*40}")
    print(f"  完成: ✅ {enriched}  /  ⏭️ {skipped}  /  ❌ {errors}")
    print(f"{'='*40}")

    # 显示补全后的统计
    s = get_enrichment_stats()
    if s["pending"] > 0:
        print(f"  剩余待补全: {s['pending']} 人")
        print(f"  继续运行: python3 social.py enrich --batch {batch}")
    return 0


def main():
    if len(sys.argv) < 2:
        print("社交关系AI管家 — 一个比你更记得住人情世故的AI管家\n")
        print("用法:")
        print("  social.py add-contact <ID> [--name NAME] [--role ROLE] [--tags TAGS] [--notes NOTES]")
        print("  social.py edit-contact <ID> [--name NAME] [--role ROLE] [--tags TAGS] [--notes NOTES]")
        print("  social.py search <QUERY> [--field name|tags|notes]")
        print("  social.py note <CONTACT> <CONTENT> [--tags TAGS]")
        print("  social.py birthdays [--days 30]")
        print("  social.py log <CONTACT> <SUMMARY>")
        print("  social.py todos [--priority P0]")
        print("  social.py done <TODO_ID>")
        print("  social.py draft <CONTACT> [--tone 亲切]")
        print("  social.py send <CONTACT> [--tone 亲切]")
        print("  social.py status [CONTACT]")
        print("  social.py dashboard")
        print("  social.py check")
        return 1

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "add-contact":
        if len(args) < 1:
            print("用法: social.py add-contact <ID> [--name NAME] [--role ROLE] [--sub-relation SUB] [--tags TAGS] [--notes NOTES]")
            return 1
        contact_id = args[0]
        opts = _parse_opts(args[1:], ["--name", "--role", "--sub-relation", "--tags", "--notes"])
        name = opts.get("--name", contact_id)
        role = opts.get("--role", "其他")
        sub_relation = opts.get("--sub-relation", "")
        tags = opts.get("--tags", "").split() if opts.get("--tags") else []
        notes = opts.get("--notes", "")
        ok, msg = add_contact(contact_id, name, role, tags, None, notes, sub_relation)
        print(msg)
        return 0 if ok else 1

    elif cmd == "edit-contact":
        if len(args) < 1:
            print("用法: social.py edit-contact <ID> [--name NAME] [--role ROLE] [--tags TAGS] [--notes NOTES]")
            return 1
        contact_id = args[0]
        opts = _parse_opts(args[1:], ["--name", "--role", "--sub-relation", "--strength", "--tags", "--notes", "--stage"])
        updates = {}
        if "--name" in opts:
            updates["name"] = opts["--name"]
        if "--role" in opts:
            updates["role"] = opts["--role"]
        if "--sub-relation" in opts:
            updates["sub_relation"] = opts["--sub-relation"]
        if "--strength" in opts:
            try:
                updates["strength"] = int(opts["--strength"])
            except:
                pass
        if "--tags" in opts:
            updates["tags"] = opts["--tags"]
        if "--notes" in opts:
            updates["notes"] = opts["--notes"]
        if "--stage" in opts:
            updates["stage"] = opts["--stage"]
        if not updates:
            print("未指定任何修改字段")
            return 1
        ok, msg = update_contact(contact_id, updates)
        print(msg)
        return 0 if ok else 1

    elif cmd == "search":
        if not args:
            print("用法: social.py search <QUERY> [--field name|tags|notes]")
            return 1
        query = args[0]
        opts = _parse_opts(args[1:], ["--field"])
        field = opts.get("--field")
        results = search_contacts(query, field)
        if not results:
            print(f"未找到匹配 '{query}' 的联系人")
            return 0
        print(f"\n🔍 搜索 '{query}' 找到 {len(results)} 个结果:\n")
        for c in results[:20]:
            tags_str = ", ".join(c.get("tags", [])[:3])
            note_preview = c.get("notes", "")[:40]
            bd = extract_birthday(c.get("notes", ""))
            bd_str = f" 🎂{bd[0]}月{bd[1]}日" if bd else ""
            print(f"  {c['name']:10s} [{c.get('role','?')}]  {tags_str}{bd_str}")
            if note_preview:
                print(f"    📝 {note_preview}")
        if len(results) > 20:
            print(f"\n  ...还有 {len(results)-20} 个结果")
        return 0

    elif cmd == "note":
        if len(args) < 2:
            print("用法: social.py note <CONTACT> <CONTENT> [--tags TAGS]")
            return 1
        raw_id = args[0]
        # 通过别名/模糊匹配解析联系人
        contact, match_type = resolve_contact(raw_id)
        if not contact:
            return 1
        contact_id = contact["id"]
        if match_type != "id":
            print(f"  ↳ 匹配到: {contact['name']} ({match_type})")
        opts = _parse_opts(args[1:], ["--tags"])
        content_parts = [a for a in args[1:] if not a.startswith("--")]
        content = " ".join(content_parts)
        tags = opts.get("--tags", "").split() if opts.get("--tags") else []
        ok, msg = add_memory(contact_id, content, tags)
        print(msg)
        return 0 if ok else 1

    elif cmd == "birthdays":
        opts = _parse_opts(args, ["--days"])
        days = int(opts.get("--days", "30"))
        results = get_birthdays(days)
        if not results:
            print(f"未来{days}天内没有生日提醒 ✅")
            return 0
        print(f"\n🎂 近期生日 ({len(results)}个):\n")
        for r in results:
            flag = "🔴" if r["days_left"] == 0 else "🟡" if r["days_left"] <= 7 else "🟢"
            print(f"  {flag} {r['contact']:10s} {r['birthday']:6s} 还有{r['days_left']}天")

        return 0

    elif cmd == "adjust":
        apply_flag = "--apply" in sys.argv
        suggestions = auto_adjust_strength()
        if not suggestions:
            print("✅ 当前无需自动调整，所有关系强度合理")
            return 0
        print(f"\n📊 强度自动调整建议 ({len(suggestions)}条):\n")
        for sug in suggestions:
            arrow = "⬆️" if sug["suggested"] > sug["current"] else "⬇️"
            print(f"  {arrow} {sug['name']:12s} {sug['current']}->{sug['suggested']}  {sug['reason']}")
        if apply_flag:
            applied = 0
            for sug in suggestions:
                ok, msg = apply_adjustment(sug["contact_id"], sug["suggested"])
                if ok:
                    applied += 1
            print(f"\n✅ 已执行 {applied}/{len(suggestions)} 条调整")
        else:
            print(f"\n💡 确认执行请加 --apply: social.py adjust --apply")
        return 0

    elif cmd == "log":
        if len(args) < 2:
            print("用法: social.py log <CONTACT> <SUMMARY>")
            return 1
        raw = args[0]
        resolved, match_type = resolve_contact(raw)
        if not resolved:
            print(f"未找到联系人: {raw}")
            return 1
        if match_type != "id":
            print(f"  ↳ 匹配到: {resolved['name']} ({match_type})")
        summary = " ".join(a for a in args[1:] if not a.startswith("--"))
        opts = _parse_opts(args[1:], ["--type"])
        type_ = opts.get("--type", "message")
        record = add_timeline(resolved["id"], summary, type_=type_)
        print(f"已记录: {record['summary'][:40]}")
        if record.get("pending"):
            print(f"待办已创建: {record['pending']}")
        return 0

    elif cmd == "todos":
        opts = _parse_opts(args, ["--priority"])
        todos = list_todos(priority=opts.get("--priority"))
        if not todos:
            print("没有待办事项 ✅")
            return 0
        today = date.today().isoformat()
        for t in todos:
            overdue = " ⏰" if t.get("due", "") < today else ""
            tag = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(t.get("priority", "P1"), "⬜")
            contact = get_contact(t["contact"])
            name = contact["name"] if contact else t["contact"]
            print(f"  {tag} [{t['priority']}] {name} - {t['task']} (截止{t.get('due','?')}){overdue}")
        return 0

    elif cmd == "done":
        if not args:
            print("用法: social.py done <TODO_ID>")
            return 1
        ok, msg = complete_todo(args[0])
        print(msg)
        return 0 if ok else 1

    elif cmd == "draft":
        if not args:
            print("用法: social.py draft <CONTACT> [--tone 亲切]")
            return 1
        raw_id = args[0]
        contact, match_type = resolve_contact(raw_id)
        if not contact:
            print(f"未找到联系人: {raw_id}")
            return 1
        contact_id = contact["id"]
        if match_type != "id":
            print(f"  ↳ 匹配到: {contact['name']} ({match_type})")
        timeline = list_timeline(contact=contact_id, days=60)
        context = "无最近互动记录"
        if timeline:
            context = " | ".join(f"{r['date']}: {r['summary']}" for r in timeline[:3])
        print(f"正在为{contact['name']}拟稿（{tone}风格）...", file=sys.stderr)
        draft = draft_message(contact["name"], context, tone)
        print(f"\n{draft}\n")
        return 0

    elif cmd == "send":
        if not args:
            print("用法: social.py send <CONTACT> [--tone 亲切]")
            return 1
        contact_id = args[0]
        opts = _parse_opts(args[1:], ["--tone"])
        tone = opts.get("--tone", "亲切")
        contact = get_contact(contact_id)
        if not contact:
            print(f"  ↳ 匹配到: {contact['name']} ({match_type})")
        opts = _parse_opts(args[1:], ["--tone"])
        tone = opts.get("--tone", "亲切")
        timeline = list_timeline(contact=contact_id, days=60)
        context = "无最近互动记录"
        if timeline:
            context = " | ".join(f"{r['date']}: {r['summary']}" for r in timeline[:3])
        print(f"正在为{contact['name']}拟稿...", file=sys.stderr)
        draft = draft_message(contact["name"], context, tone)
        print(f"\n{draft}\n")
        ok, msg = send_message(contact["name"], draft)
        print(f"推送: {msg}")
        return 0 if ok else 1

    elif cmd == "status":
        if args:
            contact, match_type = resolve_contact(args[0])
            if not contact:
                print(f"未找到: {args[0]}")
                return 1
            c = contact
            if match_type != "id":
                print(f"  ↳ 匹配到: {c['name']} ({match_type})")
            print(f"\n{'='*40}")
            print(f"  {c['name']} ({c.get('role','?')})")
            print(f"{'='*40}")
            tags_str = ", ".join(c.get("tags", []))
            if tags_str:
                print(f"  标签: {tags_str}")
            print(f"  强度: {c.get('strength',3)}/5")
            print(f"  阶段: {c.get('stage','-')}")
            if c.get("platforms"):
                wx = c["platforms"].get("weixin", "")
                phone = c["platforms"].get("phone", "")
                if wx:
                    print(f"  微信: {wx[:20]}{'...' if len(wx)>20 else ''}")
                if phone:
                    print(f"  电话: {phone}")
            # 显示记忆备注
            memories = c.get("memories", [])
            if memories:
                print(f"  记忆 ({len(memories)}条):")
                for m in memories[-3:]:
                    print(f"    💭 {m.get('content','')[:60]}")
                    if m.get("tags"):
                        print(f"      标签: {', '.join(m['tags'])}")
            # 显示重要日期
            important_dates = c.get("important_dates", [])
            if important_dates:
                print(f"  重要日期:")
                for d_entry in important_dates:
                    print(f"    📅 {d_entry.get('type','')}: {d_entry.get('date','')}")
            # 显示最近互动
            records = list_timeline(contact=args[0], days=90)
            if records:
                print(f"  最近互动 ({len(records)}条):")
                for r in records[:5]:
                    print(f"    {r['date']}: {r['summary'][:50]}")
                    if r.get("pending"):
                        print(f"      -> {r['pending']}")
            else:
                print("  暂无互动记录")
            # 显示待办
            todos = list_todos()
            contact_todos = [t for t in todos if t.get("contact") == args[0] and t.get("status") == "pending"]
            if contact_todos:
                print(f"  待办:")
                for t in contact_todos[:3]:
                    print(f"    [{t['priority']}] {t['task']} (截止{t.get('due','?')})")
        else:
            contacts = list_contacts()
            print(f"\n联系人 ({len(contacts)}人)")
            for c in contacts:
                records = list_timeline(contact=c["id"], days=30)
                last = records[0]["date"] if records else "从未"
                bd = extract_birthday(c.get("notes", ""))
                bd_str = f" 🎂{bd[0]}月{bd[1]}日" if bd else ""
                memories_count = len(c.get("memories", []))
                mem_str = f" 💭{memories_count}条" if memories_count else ""
                print(f"  {c['name']:10s} {c.get('role','?'):6s} 最近:{last}{bd_str}{mem_str}")
        return 0

    elif cmd == "dashboard":
        d = get_dashboard()
        print(f"\n社交关系AI管家 - 仪表盘")
        print(f"联系人: {d['total_contacts']}人 | 角色: {d['by_role']}")
        print(f"待办: {d['pending_todos']}项 (超期{len(d['overdue_todos'])}项)")
        print(f"近7天活动: {d['recent_activities']}条")
        print(f"冷却关系: 🔴{len(d['cold_relationships'])}个  🟡{len(d.get('warm_relationships',[]))}个")
        for c in d['cold_relationships']:
            print(f"  🔴 {c['contact']} - {c['days']}天未联系")
        for c in d.get('warm_relationships', []):
            print(f"  🟡 {c['contact']} - {c['days']}天未联系")
        todos = list_todos()
        if todos:
            print(f"\n优先待办:")
            for t in todos[:5]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                print(f"  [{t['priority']}] {name} - {t['task']}")
        return 0

    elif cmd == "check":
        reminders = []
        contacts = list_contacts()
        for c in contacts:
            records = list_timeline(contact=c["id"], days=60)
            if not records:
                reminders.append((c["name"], 999, ""))
                continue
            last = records[0]
            days_since = (date.today() - date.fromisoformat(last["date"])).days
            if days_since >= 14:
                reminders.append((c["name"], days_since, last.get("summary", "")))
        if not reminders:
            print("所有关系都在14天内联系过")
            return 0
        print(f"需要跟进 ({len(reminders)}个):")
        for name, days, summary in reminders:
            level = "P0" if days >= 21 else "P1"
            print(f"  [{level}] {name} - {days}天未联系")
            if summary:
                print(f"    上次: {summary[:40]}")
        return 0

    elif cmd == "enrich":
        return cmd_enrich(args)

    elif cmd == "remind":
        d = get_dashboard()
        lines = [f"今日待办提醒 ({date.today().isoformat()})"]
        if d["overdue_todos"]:
            lines.append(f"\n超期待办 {len(d['overdue_todos'])}项:")
            for t in d["overdue_todos"]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                lines.append(f"  P0 {name} - {t['task']}")
        todos = [t for t in list_todos() if t.get("status") == "pending"]
        if todos:
            lines.append(f"\n待办 {len(todos)}项:")
            for t in todos[:5]:
                c = get_contact(t["contact"])
                name = c["name"] if c else t["contact"]
                lines.append(f"  [{t['priority']}] {name} - {t['task']}")
        if d["cold_relationships"]:
            lines.append(f"\n冷却关系 {len(d['cold_relationships'])}个:")
            for c in d["cold_relationships"]:
                lines.append(f"  {c['contact']} - {c['days']}天未联系")
        if not todos and not d["overdue_todos"] and not d["cold_relationships"]:
            lines.append("\n今日有事，安心赚钱。")
        msg = "\n".join(lines)
        ok, result = push_to_wechat("社交关系AI管家", msg)
        print(result)
        return 0 if ok else 1

    else:
        print(f"未知命令: {cmd}")
        return 1


def _parse_opts(args, valid_opts):
    opts = {}
    i = 0
    while i < len(args):
        if args[i] in valid_opts:
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[args[i]] = args[i + 1]
                i += 2
            else:
                opts[args[i]] = ""
                i += 1
        else:
            i += 1
    return opts

if __name__ == "__main__":
    sys.exit(main())
