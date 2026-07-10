"""v4.0 阶段4+5 测试：advise 建议引擎 + outcome 兑现追踪"""
import json, sys, unittest, tempfile, shutil
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine
from engine import (
    add_outcome, list_outcomes, outcome_stats,
    advise_candidates, _days_since_last, _has_upcoming_birthday, _has_pending_todo,
    contact_tier, _load, _save, CONTACTS_FILE, TIMELINE_FILE, TODOS_FILE,
)
from ai import draft_advise, _rule_based_what, generate_advise_report


def _make_contacts(tmp):
    """写入测试联系人到临时 contacts.json。"""
    engine.CONTACTS_FILE = Path(tmp) / "contacts.json"
    contacts = [
        {"id": "c_cold", "name": "冷关系", "relation": "同行", "strength": 4, "tags": ["金融科技"]},
        {"id": "c_warm", "name": "热关系", "relation": "同行", "strength": 3, "tags": []},
        {"id": "c_anchored", "name": "已锚", "relation": "同行", "strength": 5, "tags": [],
         "leverage": {"goals": ["事业"], "how": "AI提案", "direction": "互惠", "confirmed": "2026-07-10"}},
        {"id": "c_bday", "name": "寿星", "relation": "朋友", "strength": 4, "tags": [],
         "important_dates": [{"type": "birthday", "date": "07-15"}]},
        {"id": "c_todo", "name": "有待办", "relation": "同行", "strength": 3, "tags": []},
        {"id": "c_self", "name": "我", "relation": "self", "strength": 5, "tags": []},
        {"id": "c_reserve", "name": "储备", "relation": "陌生", "strength": 1, "tags": []},
    ]
    with open(engine.CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False)


def _make_timeline(tmp, records=None):
    """写入测试 timeline。"""
    engine.TIMELINE_FILE = Path(tmp) / "timeline.json"
    records = records or [
        {"id": "t-old", "date": (date.today() - timedelta(days=30)).isoformat(),
         "contact": "c_cold", "type": "message", "summary": "上次聊了项目进展"},
        {"id": "t-recent", "date": (date.today() - timedelta(days=2)).isoformat(),
         "contact": "c_warm", "type": "message", "summary": "刚吃过饭"},
        {"id": "t-outcome", "date": "2026-07-01", "contact": "c_anchored",
         "type": "outcome", "summary": "经引荐认识XX", "goal": "事业"},
    ]
    with open(engine.TIMELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)


def _make_todos(tmp, records=None):
    """写入测试 todos。"""
    engine.TODOS_FILE = Path(tmp) / "todos.json"
    records = records or [
        {"id": "td1", "contact": "c_todo", "task": "跟进项目", "status": "pending", "created": "2026-07-01"},
        {"id": "td2", "contact": "c_cold", "task": "已完成的事", "status": "completed", "created": "2026-06-01"},
    ]
    with open(engine.TODOS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)


class TestOutcomeIO(unittest.TestCase):
    """outcome 读写（SPEC v4 §20）"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_tl = engine.TIMELINE_FILE
        self.orig_c = engine.CONTACTS_FILE
        _make_contacts(self.tmp)
        _make_timeline(self.tmp)

    def tearDown(self):
        engine.TIMELINE_FILE = self.orig_tl
        engine.CONTACTS_FILE = self.orig_c
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_outcome_creates_record(self):
        rec = add_outcome("c_cold", "测试成果", goal="事业")
        self.assertEqual(rec["type"], "outcome")
        self.assertEqual(rec["goal"], "事业")
        self.assertEqual(rec["contact"], "c_cold")
        self.assertIn("id", rec)
        self.assertIn("date", rec)

    def test_add_outcome_default_today(self):
        rec = add_outcome("c_cold", "x")
        self.assertEqual(rec["date"], date.today().isoformat())

    def test_add_outcome_custom_date(self):
        rec = add_outcome("c_cold", "x", date_str="2026-06-01")
        self.assertEqual(rec["date"], "2026-06-01")

    def test_list_outcomes_filters_type(self):
        add_outcome("c_cold", "新成果")
        outcomes = list_outcomes()
        # 只含 type=outcome，不含 type=message
        self.assertTrue(all(r["type"] == "outcome" for r in outcomes))
        self.assertTrue(len(outcomes) >= 2)  # t-outcome + 新增

    def test_list_outcomes_filter_by_contact(self):
        add_outcome("c_cold", "x")
        result = list_outcomes(contact="c_cold")
        self.assertTrue(all(r["contact"] == "c_cold" for r in result))

    def test_list_outcomes_filter_by_goal(self):
        add_outcome("c_cold", "x", goal="投资")
        result = list_outcomes(goal="投资")
        self.assertTrue(all(r.get("goal") == "投资" for r in result))

    def test_list_outcomes_filter_by_year(self):
        result = list_outcomes(year=2026)
        self.assertTrue(all(r["date"].startswith("2026") for r in result))

    def test_list_outcomes_sorted_desc(self):
        add_outcome("c_cold", "newer", date_str="2026-07-10")
        result = list_outcomes()
        dates = [r["date"] for r in result]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_list_outcomes_limit(self):
        result = list_outcomes(limit=1)
        self.assertLessEqual(len(result), 1)


class TestOutcomeStats(unittest.TestCase):
    """outcome 统计"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_tl = engine.TIMELINE_FILE
        self.orig_c = engine.CONTACTS_FILE
        _make_contacts(self.tmp)
        _make_timeline(self.tmp, [
            {"id": "o1", "date": "2026-07-01", "contact": "c1", "type": "outcome", "summary": "a", "goal": "事业"},
            {"id": "o2", "date": "2026-07-05", "contact": "c2", "type": "outcome", "summary": "b", "goal": "事业"},
            {"id": "o3", "date": "2026-06-01", "contact": "c1", "type": "outcome", "summary": "c", "goal": "投资"},
            {"id": "o4", "date": "2026-07-10", "contact": "c3", "type": "outcome", "summary": "d"},  # 无 goal
        ])

    def tearDown(self):
        engine.TIMELINE_FILE = self.orig_tl
        engine.CONTACTS_FILE = self.orig_c
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stats_total(self):
        s = outcome_stats(year=2026)
        self.assertEqual(s["total"], 4)

    def test_stats_by_goal(self):
        s = outcome_stats(year=2026)
        self.assertEqual(s["by_goal"].get("事业"), 2)
        self.assertEqual(s["by_goal"].get("投资"), 1)
        self.assertEqual(s["by_goal"].get("未标注"), 1)

    def test_stats_by_contact(self):
        s = outcome_stats(year=2026)
        self.assertEqual(s["by_contact"].get("c1"), 2)

    def test_stats_by_month(self):
        s = outcome_stats(year=2026)
        self.assertEqual(s["by_month"].get("2026-07"), 3)
        self.assertEqual(s["by_month"].get("2026-06"), 1)


class TestAdviseHelpers(unittest.TestCase):
    """advise 辅助函数"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_tl = engine.TIMELINE_FILE
        self.orig_c = engine.CONTACTS_FILE
        self.orig_td = engine.TODOS_FILE
        _make_contacts(self.tmp)
        _make_timeline(self.tmp)
        _make_todos(self.tmp)

    def tearDown(self):
        engine.TIMELINE_FILE = self.orig_tl
        engine.CONTACTS_FILE = self.orig_c
        engine.TODOS_FILE = self.orig_td
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_days_since_last_30_days(self):
        d = _days_since_last({"id": "c_cold"})
        self.assertEqual(d, 30)

    def test_days_since_last_2_days(self):
        d = _days_since_last({"id": "c_warm"})
        self.assertEqual(d, 2)

    def test_days_since_last_never(self):
        d = _days_since_last({"id": "c_bday"})
        self.assertEqual(d, 9999)

    def test_has_pending_todo_true(self):
        has, info = _has_pending_todo({"id": "c_todo"})
        self.assertTrue(has)
        self.assertIsNotNone(info)

    def test_has_pending_todo_false(self):
        has, info = _has_pending_todo({"id": "c_cold"})
        # c_cold 有 completed todo，无 pending
        self.assertFalse(has)


class TestAdviseCandidates(unittest.TestCase):
    """advise_candidates 聚合排序（SPEC v4 §19.1）"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_tl = engine.TIMELINE_FILE
        self.orig_c = engine.CONTACTS_FILE
        self.orig_td = engine.TODOS_FILE
        _make_contacts(self.tmp)
        _make_timeline(self.tmp)
        _make_todos(self.tmp)

    def tearDown(self):
        engine.TIMELINE_FILE = self.orig_tl
        engine.CONTACTS_FILE = self.orig_c
        engine.TODOS_FILE = self.orig_td
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_returns_candidates_with_signals(self):
        result = advise_candidates(top=10, tier="core")
        self.assertTrue(len(result) > 0)
        for c in result:
            self.assertIn("signals", c)
            self.assertIn("score", c)
            self.assertIn("contact", c)
            self.assertTrue(len(c["signals"]) > 0)

    def test_self_excluded(self):
        result = advise_candidates(top=50, tier="core")
        ids = [c["contact"]["id"] for c in result]
        self.assertNotIn("c_self", ids)

    def test_reserve_excluded_by_default(self):
        result = advise_candidates(top=50, tier="core")
        ids = [c["contact"]["id"] for c in result]
        self.assertNotIn("c_reserve", ids)

    def test_cold_contact_high_score(self):
        """30天未联系应得高分"""
        result = advise_candidates(top=50, tier="core")
        cold = next((c for c in result if c["contact"]["id"] == "c_cold"), None)
        self.assertIsNotNone(cold, "c_cold 应在候选中")
        self.assertTrue(any("未联系" in s for s in cold["signals"]))

    def test_warm_contact_lower_score(self):
        """刚联系2天的应降权"""
        result = advise_candidates(top=50, tier="core")
        warm = next((c for c in result if c["contact"]["id"] == "c_warm"), None)
        if warm:
            cold = next((c for c in result if c["contact"]["id"] == "c_cold"), None)
            if cold:
                self.assertGreaterEqual(cold["score"], warm["score"])

    def test_anchored_gets_bonus(self):
        """有 leverage 锚定的应加分"""
        result = advise_candidates(top=50, tier="core")
        anchored = next((c for c in result if c["contact"]["id"] == "c_anchored"), None)
        if anchored:
            self.assertTrue(any("锚定" in s for s in anchored["signals"]))

    def test_todo_gets_bonus(self):
        """有 pending 待办的应加分"""
        result = advise_candidates(top=50, tier="core")
        todo_c = next((c for c in result if c["contact"]["id"] == "c_todo"), None)
        if todo_c:
            self.assertTrue(any("待办" in s for s in todo_c["signals"]))

    def test_top_limit(self):
        result = advise_candidates(top=2, tier="core")
        self.assertLessEqual(len(result), 2)

    def test_sorted_by_score_desc(self):
        result = advise_candidates(top=50, tier="core")
        scores = [c["score"] for c in result]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestDraftAdvise(unittest.TestCase):
    """draft_advise 三元组生成"""

    def test_returns_who_why_what(self):
        candidate = {
            "contact": {"id": "x", "name": "测试人", "relation": "同行", "tags": ["金融科技"]},
            "signals": ["21天未联系🔴", "锚定[事业]"],
            "score": 50,
            "days_since": 21,
            "last_interaction": "上次聊了项目",
            "leverage": {"goals": ["事业"], "how": "AI提案", "direction": "互惠", "confirmed": "2026-07-10"},
            "has_birthday": False,
            "birthday_info": None,
            "has_todo": False,
            "todo_info": None,
        }
        r = draft_advise(candidate)
        self.assertEqual(r["who"], "测试人")
        self.assertIn("why", r)
        self.assertIn("what", r)
        self.assertTrue(len(r["why"]) > 0)
        self.assertTrue(len(r["what"]) > 0)

    def test_rule_based_what_birthday(self):
        candidate = {
            "contact": {"name": "x"}, "has_birthday": True,
            "birthday_info": {"date": "07-15"}, "has_todo": False,
            "todo_info": None, "leverage": None,
            "last_interaction": "", "days_since": 10,
        }
        what = _rule_based_what(candidate)
        self.assertIn("生日", what)

    def test_rule_based_what_todo(self):
        candidate = {
            "contact": {"name": "x"}, "has_birthday": False,
            "has_todo": True, "todo_info": {"task": "跟进项目"},
            "leverage": None, "last_interaction": "", "days_since": 10,
        }
        what = _rule_based_what(candidate)
        self.assertIn("跟进", what)

    def test_rule_based_what_leverage(self):
        candidate = {
            "contact": {"name": "x"}, "has_birthday": False,
            "has_todo": False, "todo_info": None,
            "leverage": {"goals": ["事业"], "how": "AI提案", "confirmed": "2026-07-10"},
            "last_interaction": "", "days_since": 10,
        }
        what = _rule_based_what(candidate)
        self.assertIn("事业", what)

    def test_rule_based_what_last_interaction(self):
        candidate = {
            "contact": {"name": "x"}, "has_birthday": False,
            "has_todo": False, "todo_info": None, "leverage": None,
            "last_interaction": "上次聊了项目进展", "days_since": 15,
        }
        what = _rule_based_what(candidate)
        self.assertIn("上次", what)

    def test_rule_based_what_cold_fallback(self):
        candidate = {
            "contact": {"name": "x"}, "has_birthday": False,
            "has_todo": False, "todo_info": None, "leverage": None,
            "last_interaction": "", "days_since": 25,
        }
        what = _rule_based_what(candidate)
        self.assertIn("没联系", what)


class TestGenerateAdviseReport(unittest.TestCase):
    """generate_advise_report 整合"""

    def test_report_top_n(self):
        candidates = [
            {"contact": {"id": "a", "name": "甲"}, "signals": ["s1"], "score": 10,
             "days_since": 20, "last_interaction": "", "leverage": None,
             "has_birthday": False, "birthday_info": None, "has_todo": False, "todo_info": None},
            {"contact": {"id": "b", "name": "乙"}, "signals": ["s2"], "score": 8,
             "days_since": 15, "last_interaction": "", "leverage": None,
             "has_birthday": False, "birthday_info": None, "has_todo": False, "todo_info": None},
        ]
        report = generate_advise_report(candidates, top=1)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["who"], "甲")


if __name__ == "__main__":
    unittest.main(verbosity=2)
