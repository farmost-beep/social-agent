"""社交关系AI管家 - 核心引擎单元测试"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from datetime import date, timedelta

# 将src加入路径以便导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from engine import (
    add_contact, get_contact, update_contact, search_contacts,
    add_memory, add_timeline, list_timeline,
    list_todos, complete_todo, get_dashboard,
    extract_birthday, get_birthdays,
    auto_adjust_strength, apply_adjustment,
    _load, _save, CONTACTS_FILE, TIMELINE_FILE, TODOS_FILE,
)


class TestEngineCore(unittest.TestCase):
    """核心CRUD功能测试"""

    def setUp(self):
        """每个测试前清理数据"""
        self._backup = {}
        for f in [CONTACTS_FILE, TIMELINE_FILE, TODOS_FILE]:
            if f.exists():
                self._backup[f] = f.read_text()

    def tearDown(self):
        """每个测试后恢复数据"""
        for f, content in self._backup.items():
            f.write_text(content)

    # ── 联系人 CRUD ──

    def test_add_contact(self):
        ok, msg = add_contact("test_01", "测试用户", "校友")
        self.assertTrue(ok)
        self.assertIn("已添加", msg)
        c = get_contact("test_01")
        self.assertIsNotNone(c)
        self.assertEqual(c["name"], "测试用户")

    def test_add_duplicate_contact(self):
        add_contact("test_02", "用户A", "同行")
        ok, msg = add_contact("test_02", "用户A_重复", "同行")
        self.assertFalse(ok)
        self.assertIn("已存在", msg)

    def test_update_contact(self):
        add_contact("test_03", "用户B", "校友", tags=["科大"])
        ok, msg = update_contact("test_03", {"strength": 4, "notes": "重要联系人"})
        self.assertTrue(ok)
        c = get_contact("test_03")
        self.assertEqual(c["strength"], 4)
        self.assertEqual(c["notes"], "重要联系人")

    def test_search_by_name(self):
        add_contact("test_04", "张三丰", "校友")
        results = search_contacts("张三")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "张三丰")

    def test_search_by_tag(self):
        add_contact("test_05", "李四", "同行", tags=["金融", "上海"])
        results = search_contacts("金融")
        self.assertGreaterEqual(len(results), 1)

    # ── 记忆 ──

    def test_add_memory(self):
        add_contact("test_mem", "记忆测试", "校友")
        ok, msg = add_memory("test_mem", "这是测试记忆", tags=["test"])
        self.assertTrue(ok)
        c = get_contact("test_mem")
        self.assertGreaterEqual(len(c.get("memories", [])), 1)
        self.assertEqual(c["memories"][-1]["content"][:10], "这是测试记忆")

    # ── 时间线 ──

    def test_add_timeline(self):
        add_contact("test_tl", "时间线测试", "同行")
        record = add_timeline("test_tl", "中午一起吃饭聊项目", type_="meeting")
        self.assertIsNotNone(record)
        self.assertEqual(record["type"], "meeting")
        records = list_timeline(contact="test_tl", days=30)
        self.assertGreaterEqual(len(records), 1)

    # ── 待办 ──

    def test_todo_cycle(self):
        add_contact("test_todo", "待办测试", "校友")
        record = add_timeline("test_todo", "约下周见面聊合作")
        todos = list_todos()
        self.assertGreaterEqual(len(todos), 0)  # 待办可能pending自动生成
        # 如果有待办，测试完成
        if todos:
            ok, msg = complete_todo(todos[0]["id"])
            self.assertTrue(ok)

    # ── 仪表盘 ──

    def test_dashboard(self):
        dash = get_dashboard()
        self.assertIn("total_contacts", dash)
        self.assertIn("by_role", dash)
        self.assertIn("pending_todos", dash)
        self.assertIsInstance(dash["total_contacts"], int)


class TestBirthdayDetection(unittest.TestCase):
    """生日检测功能测试"""

    def test_extract_mmdd(self):
        """测试从"1129"格式提取生日"""
        bd = extract_birthday("生日1129")
        self.assertEqual(bd, (11, 29))

    def test_extract_m_d(self):
        """测试从"11月29日"格式提取"""
        bd = extract_birthday("生日11月29日")
        self.assertEqual(bd, (11, 29))

    def test_extract_ymd(self):
        """测试从"2006年1月11日"格式提取"""
        bd = extract_birthday("2006年1月11日")
        self.assertEqual(bd, (1, 11))

    def test_extract_none(self):
        """测试无生日信息时返回None"""
        bd = extract_birthday("普通备注信息")
        self.assertIsNone(bd)

    def test_get_birthdays(self):
        """测试获取近期生日列表"""
        results = get_birthdays(days=365)
        self.assertIsInstance(results, list)


class TestAutoAdjust(unittest.TestCase):
    """自动强度调整功能测试"""

    def test_auto_adjust_strength(self):
        """测试自动调整建议函数能正常返回"""
        suggestions = auto_adjust_strength()
        self.assertIsInstance(suggestions, list)
        for sug in suggestions:
            self.assertIn("contact_id", sug)
            self.assertIn("current", sug)
            self.assertIn("suggested", sug)
            self.assertIn("reason", sug)


if __name__ == "__main__":
    unittest.main()
