"""ai.py 单元测试 - Social-CLI v3.0

覆盖：
1. LLMClient 路径（mock）
2. subprocess 降级路径（mock）
3. 双路径都失败的最终降级
4. prompt 构建正确性
5. 返回文本清理（前缀/后缀包裹）
6. 向后兼容：返回字符串而非抛异常
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ai import draft_message, generate_reminder


class TestDraftMessage(unittest.TestCase):
    """draft_message 主路径测试"""

    @patch("ai._call_via_llm_client")
    def test_draft_success_via_llm_client(self, mock_llm):
        """LLMClient 成功路径"""
        mock_llm.return_value = "张总好久不见，最近项目进展如何？"

        result = draft_message("张三", "上周见过面，聊项目")
        self.assertEqual(result, "张总好久不见，最近项目进展如何？")
        mock_llm.assert_called_once()
        # 验证 prompt 包含关键信息
        prompt_arg = mock_llm.call_args[0][0]
        self.assertIn("张三", prompt_arg)
        self.assertIn("上周见过面", prompt_arg)
        self.assertIn("亲切", prompt_arg)  # 默认语气

    @patch("ai._call_via_llm_client")
    def test_draft_fallback_when_llm_fails(self, mock_llm):
        """LLMClient 失败 → 降级到 subprocess"""
        mock_llm.return_value = None  # LLM 失败
        with patch("ai._call_via_subprocess") as mock_sub:
            mock_sub.return_value = "降级返回的消息"
            result = draft_message("李四", "昨天聊了")
            self.assertEqual(result, "降级返回的消息")

    @patch("ai._call_via_llm_client")
    def test_draft_both_fail_returns_error_string(self, mock_llm):
        """双路径都失败 → 返回错误字符串（不抛异常）"""
        mock_llm.return_value = None
        with patch("ai._call_via_subprocess") as mock_sub:
            mock_sub.return_value = None
            result = draft_message("王五", "上周吃饭")
            self.assertIn("AI拟稿失败", result)
            # 不抛异常是核心契约
            self.assertIsInstance(result, str)

    @patch("ai._call_via_llm_client")
    def test_draft_strips_surrounding_quotes(self, mock_llm):
        """清理前后包裹字符"""
        mock_llm.return_value = '"消息：你好啊"'
        result = draft_message("测试", "无")
        self.assertEqual(result, "你好啊")

    @patch("ai._call_via_llm_client")
    def test_draft_strips_brackets(self, mock_llm):
        """清理中文引号「」"""
        mock_llm.return_value = "「测试内容」"
        result = draft_message("测试", "无")
        self.assertEqual(result, "测试内容")

    @patch("ai._call_via_llm_client")
    def test_draft_preserves_internal_text(self, mock_llm):
        """内部文本不被误删"""
        mock_llm.return_value = "这是「内部」引号"
        # 我们的清理只处理前后，不处理内部
        result = draft_message("测试", "无")
        self.assertIn("「内部」", result)

    @patch("ai._call_via_llm_client")
    def test_draft_custom_tone_in_prompt(self, mock_llm):
        """自定义语气传递到 prompt"""
        mock_llm.return_value = "回复"
        draft_message("测试", "无", tone="正式")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("正式", prompt)
        self.assertIn("您", prompt)  # 正式语气用"您"

    @patch("ai._call_via_llm_client")
    def test_draft_max_length_in_prompt(self, mock_llm):
        """max_length 从配置读到 prompt"""
        mock_llm.return_value = "ok"
        with patch("ai._AI_CONFIG", {"draft": {"max_length": 50, "default_tone": "亲切"}}):
            draft_message("测试", "无")
            prompt = mock_llm.call_args[0][0]
            self.assertIn("50", prompt)


class TestGenerateReminder(unittest.TestCase):
    """generate_reminder 测试"""

    @patch("ai._call_via_llm_client")
    def test_reminder_success(self, mock_llm):
        """LLMClient 成功"""
        mock_llm.return_value = "14天没联系了，上次聊到项目，建议打个招呼。"
        result = generate_reminder("张总", 14, "上次聊项目")
        self.assertEqual(result, "14天没联系了，上次聊到项目，建议打个招呼。")

    @patch("ai._call_via_llm_client")
    def test_reminder_fallback_simple_string(self, mock_llm):
        """失败降级：返回简单字符串（v2 兼容行为）"""
        mock_llm.return_value = None
        with patch("ai._call_via_subprocess") as mock_sub:
            mock_sub.return_value = None
            result = generate_reminder("李四", 30, "无")
            self.assertEqual(result, "30天没联系李四了")

    @patch("ai._call_via_llm_client")
    def test_reminder_prompt_contains_key_info(self, mock_llm):
        """prompt 包含关键信息"""
        mock_llm.return_value = "ok"
        generate_reminder("王五", 21, "上次吃饭")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("王五", prompt)
        self.assertIn("21天", prompt)
        self.assertIn("上次吃饭", prompt)


class TestCallLLMRouting(unittest.TestCase):
    """_call_llm 路径选择测试"""

    @patch("ai._call_via_llm_client")
    def test_llm_client_takes_priority(self, mock_llm):
        """LLMClient 优先"""
        from ai import _call_llm
        mock_llm.return_value = "from-llm"
        result = _call_llm("test prompt")
        self.assertEqual(result, "from-llm")

    @patch("ai._call_via_subprocess")
    @patch("ai._call_via_llm_client")
    def test_subprocess_used_when_llm_returns_none(self, mock_llm, mock_sub):
        """LLM 返回 None → subprocess 兜底"""
        from ai import _call_llm
        mock_llm.return_value = None
        mock_sub.return_value = "from-subprocess"
        result = _call_llm("test prompt")
        self.assertEqual(result, "from-subprocess")

    @patch("ai._call_via_subprocess")
    @patch("ai._call_via_llm_client")
    def test_returns_empty_when_both_fail(self, mock_llm, mock_sub):
        """双路径失败 → 返回空串"""
        from ai import _call_llm
        mock_llm.return_value = None
        mock_sub.return_value = None
        result = _call_llm("test prompt")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)