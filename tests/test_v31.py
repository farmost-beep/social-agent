"""v3.1 地基功能测试：tier 分层 / 晋升提示 / 待办老化 / health 三因子 / remind 时间解析"""
import json, sys, unittest
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import (
    contact_tier, promotion_hint, role_layers, list_contacts,
    list_todos, get_dashboard, STALE_TODO_DAYS,
    _load, _save, CONTACTS_FILE, TODOS_FILE,
)
from social_cli.cli import _layers_score, _health_score, _extract_event_time


class TestTier(unittest.TestCase):
    """双层架构 tier（SPEC v4 §17）"""

    def test_core_tier(self):
        for s in (3, 4, 5):
            self.assertEqual(contact_tier({"strength": s}), "core")

    def test_reserve_tier(self):
        for s in (1, 2):
            self.assertEqual(contact_tier({"strength": s}), "reserve")

    def test_missing_strength_is_reserve(self):
        self.assertEqual(contact_tier({}), "reserve")

    def test_list_contacts_tier_filter(self):
        core = list_contacts(tier="core")
        reserve = list_contacts(tier="reserve")
        total = list_contacts()
        self.assertEqual(len(core) + len(reserve), len(total))
        self.assertTrue(all(c.get("strength", 1) >= 3 for c in core))


class TestPromotionHint(unittest.TestCase):
    """储备池晋升提示（SPEC v4 §17）"""

    def test_reserve_contact_gets_hint(self):
        hint = promotion_hint({"id": "x-01", "name": "张三", "strength": 2})
        self.assertIsNotNone(hint)
        self.assertIn("张三", hint)
        self.assertIn("enrich --contact x-01", hint)

    def test_core_contact_no_hint(self):
        self.assertIsNone(promotion_hint({"id": "x-02", "name": "李四", "strength": 4}))

    def test_self_no_hint(self):
        self.assertIsNone(promotion_hint({"id": "me", "name": "我", "strength": 1, "relation": "self"}))


class TestStaleTodos(unittest.TestCase):
    """待办老化标注（SPEC v4 §17，只标注不取消）"""

    def setUp(self):
        self._backup = TODOS_FILE.read_text() if TODOS_FILE.exists() else None

    def tearDown(self):
        if self._backup is not None:
            TODOS_FILE.write_text(self._backup)

    def test_old_pending_todo_marked_stale(self):
        todos = _load(TODOS_FILE)
        old_date = (date.today() - timedelta(days=STALE_TODO_DAYS + 5)).isoformat()
        todos.append({"id": "todo-stale-test", "contact": "x", "task": "老化测试",
                      "priority": "P1", "status": "pending", "created": old_date})
        _save(TODOS_FILE, todos)
        result = list_todos()
        target = [t for t in result if t["id"] == "todo-stale-test"]
        self.assertEqual(len(target), 1)
        self.assertTrue(target[0].get("stale"))
        self.assertGreaterEqual(target[0].get("stale_days", 0), STALE_TODO_DAYS)

    def test_fresh_todo_not_stale(self):
        todos = _load(TODOS_FILE)
        todos.append({"id": "todo-fresh-test", "contact": "x", "task": "新待办",
                      "priority": "P1", "status": "pending", "created": date.today().isoformat()})
        _save(TODOS_FILE, todos)
        result = list_todos()
        target = [t for t in result if t["id"] == "todo-fresh-test"]
        self.assertEqual(len(target), 1)
        self.assertFalse(target[0].get("stale", False))

    def test_content_field_normalized_to_task(self):
        """字段漂移兼容：content 写入方的待办在读取时归一化出 task"""
        todos = _load(TODOS_FILE)
        todos.append({"id": "todo-content-test", "contact": "x", "content": "用content写的待办",
                      "priority": "P1", "status": "pending", "created": date.today().isoformat()})
        _save(TODOS_FILE, todos)
        result = list_todos()
        target = [t for t in result if t["id"] == "todo-content-test"]
        self.assertEqual(target[0].get("task"), "用content写的待办")
        # 不落盘
        raw = _load(TODOS_FILE)
        raw_target = [t for t in raw if t["id"] == "todo-content-test"]
        self.assertNotIn("task", raw_target[0])

    def test_stale_annotation_not_persisted(self):
        """标注仅在内存中，不落盘"""
        todos = _load(TODOS_FILE)
        old_date = (date.today() - timedelta(days=60)).isoformat()
        todos.append({"id": "todo-nopersist", "contact": "x", "task": "不落盘",
                      "priority": "P1", "status": "pending", "created": old_date})
        _save(TODOS_FILE, todos)
        list_todos()  # 触发标注
        raw = _load(TODOS_FILE)
        target = [t for t in raw if t["id"] == "todo-nopersist"]
        self.assertNotIn("stale", target[0])


class TestDashboardScope(unittest.TestCase):
    """仪表盘冷却检查默认核心圈（SPEC v4 §17）"""

    def test_core_scope_smaller_than_all(self):
        d_core = get_dashboard(scope="core")
        d_all = get_dashboard(scope="all")
        core_cold = len(d_core["cold_relationships"]) + len(d_core["warm_relationships"])
        all_cold = len(d_all["cold_relationships"]) + len(d_all["warm_relationships"])
        self.assertLessEqual(core_cold, all_cold)
        # 总联系人数不受 scope 影响
        self.assertEqual(d_core["total_contacts"], d_all["total_contacts"])

    def test_core_scope_only_core_contacts(self):
        d = get_dashboard(scope="core")
        core_names = {c["name"] for c in list_contacts(tier="core")}
        for entry in d["cold_relationships"] + d["warm_relationships"]:
            self.assertIn(entry["contact"], core_names)


class TestHealthThreeFactor(unittest.TestCase):
    """health 三因子公式（v3.1）"""

    def test_formula(self):
        # recency=100, depth=100, layers=100 → 100
        self.assertEqual(_health_score(100, 100, 100), 100)
        # recency=100, depth=0, layers=0 → 40
        self.assertEqual(_health_score(100, 0, 0), 40)
        # recency=0, depth=100, layers=0 → 30
        self.assertEqual(_health_score(0, 100, 0), 30)
        # recency=0, depth=0, layers=100 → 30
        self.assertEqual(_health_score(0, 0, 100), 30)

    def test_layers_score_mapping(self):
        self.assertEqual(_layers_score({"_layers": ["职层", "校层", "组层"]}), 100)
        self.assertEqual(_layers_score({"_layers": ["职层", "校层"]}), 66)
        self.assertEqual(_layers_score({"_layers": ["职层"]}), 33)
        self.assertEqual(_layers_score({"_layers": []}), 0)

    def test_layers_score_computes_when_missing(self):
        # 无 _layers 字段时按 role_layers 实时计算
        c = {"name": "x", "relation": "校友", "tags": ["民建"], "sub_relation": "", "notes": ""}
        expected = len(role_layers(c))
        score = _layers_score(c)
        self.assertEqual(score, {3: 100, 2: 66, 1: 33, 0: 0}.get(min(expected, 3)))


class TestRoleLayersPure(unittest.TestCase):
    """role_layers 纯函数（不修改联系人）"""

    def test_no_mutation(self):
        c = {"name": "x", "relation": "校友", "tags": ["民建"], "sub_relation": "", "notes": ""}
        before = json.dumps(c, ensure_ascii=False, sort_keys=True)
        layers = role_layers(c)
        self.assertEqual(json.dumps(c, ensure_ascii=False, sort_keys=True), before)
        self.assertIn("校层", layers)
        self.assertIn("组层", layers)


class TestRemindTimeExtraction(unittest.TestCase):
    """remind 时间标注解析（v3.1 提醒调度解耦）"""

    def test_hhmm(self):
        self.assertEqual(_extract_event_time("14:30 和张总开会"), (14, 30))

    def test_chinese_hour(self):
        self.assertEqual(_extract_event_time("下午3点见面"), (15, 0))
        self.assertEqual(_extract_event_time("晚上8点半饭局"), (20, 30))
        self.assertEqual(_extract_event_time("上午9点汇报"), (9, 0))
        self.assertEqual(_extract_event_time("10点电话"), (10, 0))

    def test_no_time(self):
        self.assertIsNone(_extract_event_time("跟进项目进展"))
        self.assertIsNone(_extract_event_time(""))

    def test_invalid_time(self):
        self.assertIsNone(_extract_event_time("重点25点关注"))


if __name__ == "__main__":
    unittest.main()
