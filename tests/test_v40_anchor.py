"""v4.0 阶段2 目标锚定测试：goals.yaml / leverage 读写 / list_unanchored / anchor_stats / suggest_leverage 降级"""
import json, sys, unittest, tempfile, shutil
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine
from engine import (
    load_goals, set_leverage, get_leverage, list_unanchored, list_anchored,
    anchor_stats, contact_tier,
)
from ai import suggest_leverage, _parse_leverage_json, _rule_based_leverage


class TestLoadGoals(unittest.TestCase):
    """goals.yaml 加载（SPEC v4 §18.1）"""

    def test_default_six_dimensions(self):
        g = load_goals()
        self.assertIn("goals", g)
        self.assertIn("directions", g)
        # 六维必须包含事业（最基础维度）
        self.assertIn("事业", g["goals"])
        # direction 三枚举
        self.assertEqual(set(g["directions"]), {"我求于他", "他求于我", "互惠"})

    def test_goals_file_exists(self):
        """config/goals.yaml 应已创建"""
        p = Path(__file__).resolve().parent.parent / "config" / "goals.yaml"
        self.assertTrue(p.exists(), "config/goals.yaml 不存在")


class TestLeverageIO(unittest.TestCase):
    """leverage 字段读写（SPEC v4 §18.2）"""

    def setUp(self):
        """用临时 contacts.json 避免污染真实数据。"""
        self.tmp = tempfile.mkdtemp()
        self.orig_contacts = engine.CONTACTS_FILE
        engine.CONTACTS_FILE = Path(self.tmp) / "contacts.json"
        # 写入 3 个测试联系人：core 高强度 / core / reserve
        test_contacts = [
            {"id": "core_high", "name": "高强度", "relation": "同行", "strength": 5, "tags": ["金融科技"]},
            {"id": "core_low", "name": "中强度", "relation": "校友", "strength": 3, "tags": ["ustc"]},
            {"id": "reserve", "name": "储备", "relation": "陌生", "strength": 1, "tags": []},
            {"id": "self", "name": "我", "relation": "self", "strength": 5, "tags": []},
        ]
        with open(engine.CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(test_contacts, f, ensure_ascii=False)

    def tearDown(self):
        engine.CONTACTS_FILE = self.orig_contacts
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_set_and_get_leverage(self):
        ok, _ = set_leverage("core_high", ["事业", "AI能力"], "AI+科技金融提案", "互惠", confirmed="2026-07-15")
        self.assertTrue(ok)
        lev = get_leverage("core_high")
        self.assertEqual(lev["goals"], ["事业", "AI能力"])
        self.assertEqual(lev["how"], "AI+科技金融提案")
        self.assertEqual(lev["direction"], "互惠")
        self.assertEqual(lev["confirmed"], "2026-07-15")

    def test_set_leverage_invalid_direction(self):
        ok, msg = set_leverage("core_high", ["事业"], "test", "单向")
        self.assertFalse(ok)
        self.assertIn("非法", msg)

    def test_set_leverage_nonexistent_contact(self):
        ok, msg = set_leverage("不存在", ["事业"], "test", "互惠")
        self.assertFalse(ok)

    def test_get_leverage_none_if_absent(self):
        self.assertIsNone(get_leverage("core_low"))

    def test_unconfirmed_leverage_treated_as_unanchored(self):
        """confirmed 为空的 leverage 视为未锚定（原则二：仅建议未生效）"""
        set_leverage("core_high", ["事业"], "test", "互惠", confirmed=None)
        unanchored = list_unanchored(tier="core")
        ids = [c["id"] for c in unanchored]
        self.assertIn("core_high", ids, "未确认的 leverage 应视为未锚定")


class TestListUnanchored(unittest.TestCase):
    """未锚定列表排序（SPEC v4 §18.3 先高强度）"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = engine.CONTACTS_FILE
        engine.CONTACTS_FILE = Path(self.tmp) / "contacts.json"
        contacts = [
            {"id": "s5", "name": "张五", "strength": 5, "relation": "同行", "tags": []},
            {"id": "s4", "name": "李四", "strength": 4, "relation": "同行", "tags": []},
            {"id": "s3", "name": "王三", "strength": 3, "relation": "同行", "tags": []},
            {"id": "s5_anchored", "name": "已锚", "strength": 5, "relation": "同行", "tags": [],
             "leverage": {"goals": ["事业"], "how": "x", "direction": "互惠", "confirmed": "2026-07-10"}},
            {"id": "s2", "name": "储备", "strength": 2, "relation": "陌生", "tags": []},
            {"id": "self", "name": "我", "strength": 5, "relation": "self", "tags": []},
        ]
        with open(engine.CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(contacts, f, ensure_ascii=False)

    def tearDown(self):
        engine.CONTACTS_FILE = self.orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_order_by_strength_desc(self):
        result = list_unanchored(tier="core")
        ids = [c["id"] for c in result]
        # s5 在前，s4 次之，s3 最后；s5_anchored 已锚定排除；self 排除
        self.assertEqual(ids, ["s5", "s4", "s3"])

    def test_min_strength_filter(self):
        result = list_unanchored(min_strength=4, tier="core")
        ids = [c["id"] for c in result]
        self.assertEqual(ids, ["s5", "s4"])

    def test_limit(self):
        result = list_unanchored(tier="core", limit=2)
        self.assertEqual(len(result), 2)

    def test_self_excluded(self):
        result = list_unanchored(tier="core")
        ids = [c["id"] for c in result]
        self.assertNotIn("self", ids)

    def test_reserve_not_in_core_tier(self):
        result = list_unanchored(tier="core")
        ids = [c["id"] for c in result]
        self.assertNotIn("s2", ids)


class TestAnchorStats(unittest.TestCase):
    """锚定进度统计"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = engine.CONTACTS_FILE
        engine.CONTACTS_FILE = Path(self.tmp) / "contacts.json"
        contacts = [
            {"id": "c1", "name": "已锚1", "strength": 5, "relation": "同行", "tags": [],
             "leverage": {"goals": ["事业", "AI能力"], "how": "x", "direction": "互惠", "confirmed": "2026-07-10"}},
            {"id": "c2", "name": "已锚2", "strength": 4, "relation": "同行", "tags": [],
             "leverage": {"goals": ["投资"], "how": "y", "direction": "我求于他", "confirmed": "2026-07-11"}},
            {"id": "c3", "name": "待锚", "strength": 3, "relation": "同行", "tags": []},
            {"id": "r1", "name": "储备", "strength": 1, "relation": "陌生", "tags": []},
            {"id": "self", "name": "我", "strength": 5, "relation": "self", "tags": []},
        ]
        with open(engine.CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(contacts, f, ensure_ascii=False)

    def tearDown(self):
        engine.CONTACTS_FILE = self.orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stats_counts(self):
        s = anchor_stats()
        # core_total = c1+c2+c3 = 3（self 排除，r1 是 reserve）
        self.assertEqual(s["core_total"], 3)
        self.assertEqual(s["anchored"], 2)
        self.assertEqual(s["pending"], 1)

    def test_stats_by_goal(self):
        s = anchor_stats()
        self.assertEqual(s["by_goal"].get("事业"), 1)
        self.assertEqual(s["by_goal"].get("AI能力"), 1)
        self.assertEqual(s["by_goal"].get("投资"), 1)

    def test_stats_by_direction(self):
        s = anchor_stats()
        self.assertEqual(s["by_direction"].get("互惠"), 1)
        self.assertEqual(s["by_direction"].get("我求于他"), 1)

    def test_stats_self_excluded(self):
        s = anchor_stats()
        # self 不计入 core_total
        self.assertEqual(s["core_total"], 3)


class TestParseLeverageJson(unittest.TestCase):
    """LLM 输出 JSON 解析"""

    def setUp(self):
        self.goals = ["事业", "投资", "家庭", "健康", "AI能力", "知识"]
        self.dirs = ["我求于他", "他求于我", "互惠"]

    def test_valid_json(self):
        text = '{"goals": ["事业", "AI能力"], "how": "AI 提案", "direction": "互惠"}'
        r = _parse_leverage_json(text, self.goals, self.dirs)
        self.assertEqual(r["goals"], ["事业", "AI能力"])
        self.assertEqual(r["direction"], "互惠")

    def test_json_with_surrounding_text(self):
        text = '建议如下：\n{"goals": ["投资"], "how": "组合优化", "direction": "我求于他"}\n以上。'
        r = _parse_leverage_json(text, self.goals, self.dirs)
        self.assertIsNotNone(r)
        self.assertEqual(r["goals"], ["投资"])

    def test_invalid_goal_filtered(self):
        text = '{"goals": ["事业", "不存在维度"], "how": "x", "direction": "互惠"}'
        r = _parse_leverage_json(text, self.goals, self.dirs)
        self.assertEqual(r["goals"], ["事业"])

    def test_all_invalid_goals_returns_none(self):
        text = '{"goals": ["不存在"], "how": "x", "direction": "互惠"}'
        self.assertIsNone(_parse_leverage_json(text, self.goals, self.dirs))

    def test_invalid_direction_returns_none(self):
        text = '{"goals": ["事业"], "how": "x", "direction": "单向"}'
        self.assertIsNone(_parse_leverage_json(text, self.goals, self.dirs))

    def test_malformed_json_returns_none(self):
        text = '这不是 JSON'
        self.assertIsNone(_parse_leverage_json(text, self.goals, self.dirs))

    def test_missing_field_returns_none(self):
        text = '{"goals": ["事业"]}'
        self.assertIsNone(_parse_leverage_json(text, self.goals, self.dirs))


class TestRuleBasedLeverage(unittest.TestCase):
    """规则降级路径（LLM 不可用时）"""

    def setUp(self):
        self.goals = ["事业", "投资", "家庭", "健康", "AI能力", "知识"]
        self.dirs = ["我求于他", "他求于我", "互惠"]

    def test_fintech_tags_infer_事业(self):
        c = {"name": "x", "relation": "同行", "tags": ["金融科技", "客户"], "strength": 4}
        r = _rule_based_leverage(c, self.goals, self.dirs)
        self.assertIn("事业", r["goals"])
        # 客户标签 → 我求于他
        self.assertEqual(r["direction"], "我求于他")

    def test_alumni_infer_知识(self):
        c = {"name": "x", "relation": "校友", "tags": ["ustc"], "strength": 3}
        r = _rule_based_leverage(c, self.goals, self.dirs)
        self.assertIn("知识", r["goals"])

    def test_family_infer_家庭_and_互惠(self):
        c = {"name": "x", "relation": "家人", "tags": [], "strength": 5}
        r = _rule_based_leverage(c, self.goals, self.dirs)
        self.assertIn("家庭", r["goals"])
        self.assertEqual(r["direction"], "互惠")

    def test_ai_tags_infer_AI能力(self):
        c = {"name": "x", "relation": "同行", "tags": ["ai", "技术"], "strength": 4}
        r = _rule_based_leverage(c, self.goals, self.dirs)
        self.assertIn("AI能力", r["goals"])

    def test_fallback_default_事业(self):
        """无任何匹配标签时兜底事业（多数职场关系）"""
        c = {"name": "x", "relation": "同行", "tags": [], "strength": 3}
        r = _rule_based_leverage(c, self.goals, self.dirs)
        self.assertEqual(r["goals"], ["事业"])

    def test_direction_fallback_first(self):
        """非法 direction 兜底取第一个"""
        c = {"name": "x", "relation": "同行", "tags": [], "strength": 3}
        r = _rule_based_leverage(c, self.goals, ["只此一个"])
        self.assertEqual(r["direction"], "只此一个")


class TestSuggestLeverageIntegration(unittest.TestCase):
    """suggest_leverage 整合：LLM 不可用时走规则降级"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig = engine.CONTACTS_FILE
        engine.CONTACTS_FILE = Path(self.tmp) / "contacts.json"
        with open(engine.CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)

    def tearDown(self):
        engine.CONTACTS_FILE = self.orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_returns_dict_with_required_fields(self):
        c = {"name": "测试", "relation": "同行", "tags": ["金融科技"], "strength": 4}
        goals = ["事业", "投资", "家庭", "健康", "AI能力", "知识"]
        r = suggest_leverage(c, goals)
        self.assertIn("goals", r)
        self.assertIn("how", r)
        self.assertIn("direction", r)
        self.assertIsInstance(r["goals"], list)
        self.assertTrue(len(r["goals"]) >= 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
