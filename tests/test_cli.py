"""social_cli CLI 入口单元测试 - Social-CLI v3.0

覆盖：
1. argparse 子命令解析
2. help 输出
3. version 命令
4. config 子命令
5. chat 命令（mock LLMClient）
6. draft 命令（mock ai.draft_message）
7. 错误处理（KeyboardInterrupt、未知命令、无子命令）
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 将项目根加入路径（这样才能 import social_cli）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from social_cli.cli import main, build_parser, cmd_version, cmd_config, cmd_draft, cmd_chat


class TestArgparse(unittest.TestCase):
    """argparse 框架测试"""

    def test_parser_builds(self):
        """解析器可正常构建"""
        parser = build_parser()
        self.assertIsNotNone(parser)

    def test_no_args_shows_help(self):
        """无参数 → 显示 help，返回 0"""
        with patch("sys.stdout") as mock_stdout:
            result = main([])
            self.assertEqual(result, 0)

    def test_version_command(self):
        """version 命令"""
        result = main(["version"])
        self.assertEqual(result, 0)

    def test_help_long(self):
        """--help"""
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_help_short(self):
        """-h"""
        with self.assertRaises(SystemExit) as ctx:
            main(["-h"])
        self.assertEqual(ctx.exception.code, 0)

    def test_unknown_command(self):
        """未知命令：argparse 调用 sys.exit(2)"""
        with self.assertRaises(SystemExit) as ctx:
            main(["nonexistent_cmd"])
        self.assertEqual(ctx.exception.code, 2)  # argparse 标准退出码

    def test_enrich_with_args(self):
        """enrich 接收参数"""
        # 不实际执行 enrich，只验证参数解析
        parser = build_parser()
        args = parser.parse_args(["enrich", "--batch", "50", "--dry-run", "--web"])
        self.assertEqual(args.command, "enrich")
        self.assertEqual(args.batch, 50)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.web)

    def test_draft_required_message(self):
        """draft 必须有 -m"""
        parser = build_parser()
        # 缺少 -m 应报错
        with self.assertRaises(SystemExit):
            parser.parse_args(["draft"])

    def test_draft_with_tone(self):
        """draft 带 tone 参数"""
        parser = build_parser()
        args = parser.parse_args(["draft", "-m", "test", "--tone", "正式"])
        self.assertEqual(args.tone, "正式")

    def test_health_with_fix(self):
        """health --fix"""
        parser = build_parser()
        args = parser.parse_args(["health", "--fix"])
        self.assertTrue(args.fix)

    def test_config_subcommand(self):
        """config show"""
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        self.assertEqual(args.command, "config")
        self.assertEqual(args.action, "show")

    def test_config_set_with_args(self):
        """config set key value"""
        parser = build_parser()
        args = parser.parse_args(["config", "set", "engine", "openai"])
        self.assertEqual(args.action, "set")
        self.assertEqual(args.key, "engine")
        self.assertEqual(args.value, "openai")


class TestVersion(unittest.TestCase):
    """version 命令测试"""

    def test_version_prints_version(self):
        """version 打印版本号"""
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            result = cmd_version(None)
        output = f.getvalue()

        self.assertEqual(result, 0)
        self.assertIn("3.0.0", output)
        self.assertIn("Python", output)


class TestConfig(unittest.TestCase):
    """config 命令测试"""

    def test_config_providers(self):
        """config providers 列出可用 provider"""
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            result = cmd_config(MagicMock(action="providers"))
        output = f.getvalue()

        self.assertEqual(result, 0)
        self.assertIn("claude", output)
        self.assertIn("openai", output)

    def test_config_set_prompts_env_vars(self):
        """config set 提示用环境变量"""
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            result = cmd_config(MagicMock(action="set", key=None, value=None))
        output = f.getvalue()

        self.assertEqual(result, 0)
        self.assertIn("环境变量", output)
        self.assertIn("ANTHROPIC_API_KEY", output)

    def test_config_show(self):
        """config show 显示当前配置"""
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            result = cmd_config(MagicMock(action="show"))
        output = f.getvalue()

        self.assertEqual(result, 0)
        self.assertIn("providers", output)


class TestChat(unittest.TestCase):
    """chat 命令测试"""

    @patch("src.llm.get_client")
    def test_chat_success(self, mock_get_client):
        """chat 成功调用 LLM"""
        mock_client = MagicMock()
        mock_client.complete.return_value = "你好！"
        mock_get_client.return_value = mock_client

        args = MagicMock(message="你好")
        result = cmd_chat(args)
        self.assertEqual(result, 0)

    def test_chat_no_message(self):
        """chat 无消息报错"""
        args = MagicMock(message=None)
        result = cmd_chat(args)
        self.assertNotEqual(result, 0)


class TestDraft(unittest.TestCase):
    """draft 命令测试"""

    @patch("src.ai.draft_message")
    def test_draft_success(self, mock_draft):
        """draft 成功调用"""
        mock_draft.return_value = "你好啊"
        args = MagicMock(message="上周见过", contact="张三", tone=None)
        result = cmd_draft(args)
        self.assertEqual(result, 0)
        mock_draft.assert_called_once_with(
            contact_name="张三",
            context_summary="上周见过",
            tone=None,
        )

    def test_draft_no_message(self):
        """draft 无消息报错"""
        args = MagicMock(message=None, contact=None, tone=None)
        result = cmd_draft(args)
        self.assertNotEqual(result, 0)


class TestErrorHandling(unittest.TestCase):
    """错误处理测试"""

    def test_keyboard_interrupt(self):
        """Ctrl+C 优雅退出"""
        with patch("social_cli.cli._COMMANDS") as mock_commands:
            mock_commands.get.return_value = MagicMock(side_effect=KeyboardInterrupt)
            result = main(["version"])
            self.assertEqual(result, 130)

    def test_generic_exception(self):
        """通用异常被捕获"""
        with patch("social_cli.cli._COMMANDS") as mock_commands:
            mock_commands.get.return_value = MagicMock(side_effect=RuntimeError("boom"))
            result = main(["version"])
            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)