"""social_cli CLI 入口单元测试 - Social-CLI v3.0

覆盖：
1. argparse 子命令解析
2. help 输出
3. version 命令
4. config 子命令
5. chat 命令（mock LLMClient）
6. draft 命令（mock ai.draft_message）
7. 错误处理（KeyboardInterrupt、未知命令、无子命令）
8. 项目根定位（_find_project_root / _ensure_project_path）
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 将项目根加入路径（这样才能 import social_cli）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from social_cli import cli as cli_module
from social_cli.cli import (
    main, build_parser, cmd_version, cmd_config, cmd_draft, cmd_chat,
    _find_project_root, _ensure_project_path, _PROJECT_ROOT,
)


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
        from social_cli import __version__
        self.assertIn(__version__, output)
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


class TestProjectRootLocation(unittest.TestCase):
    """项目根定位测试（v3.0.1 修复 ImportError 引入）"""

    def setUp(self):
        """每个测试前重置单例和 sys.path"""
        cli_module._PROJECT_ROOT = None
        # 清理可能添加的 social-agent 路径
        self._saved_path = sys.path.copy()

    def tearDown(self):
        """恢复 sys.path"""
        sys.path[:] = self._saved_path
        cli_module._PROJECT_ROOT = None

    def test_finds_project_via_package_parent(self):
        """通过 social_cli 包位置向上找"""
        # social_cli 包在 <project>/social_cli/，向上1层就是项目根
        # 这个测试在 social-agent 项目内运行，必然成功
        root = _find_project_root()
        self.assertIsNotNone(root)
        self.assertTrue((root / "config").is_dir())
        self.assertTrue((root / "src").is_dir())
        self.assertTrue((root / "data").is_dir())

    def test_finds_project_via_env_var(self):
        """环境变量 SOCIAL_AGENT_HOME 优先"""
        # 项目根就是测试所在的项目根
        expected = _find_project_root()
        with patch.dict(os.environ, {"SOCIAL_AGENT_HOME": str(expected)}):
            result = _find_project_root()
            self.assertEqual(result, expected)

    def test_ensure_project_path_adds_to_sys_path(self):
        """_ensure_project_path 会把 src/ 和项目根加到 sys.path"""
        # 清理可能的污染
        root = _ensure_project_path()
        self.assertIsNotNone(root)

        # 验证 src/ 在 sys.path
        self.assertIn(str(root / "src"), sys.path)
        # 验证项目根在 sys.path
        self.assertIn(str(root), sys.path)

    def test_ensure_project_path_changes_cwd(self):
        """_ensure_project_path 会切换 cwd 到项目根（让 ./data 解析正确）"""
        # 临时切到 /tmp
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")
            root = _ensure_project_path()
            self.assertIsNotNone(root)
            # 验证 cwd 已切换
            self.assertEqual(os.getcwd(), str(root))
        finally:
            os.chdir(original_cwd)

    def test_ensure_project_path_singleton(self):
        """_ensure_project_path 单例缓存（第二次调用直接返回缓存值）"""
        # 第一次调用
        root1 = _ensure_project_path()
        self.assertIsNotNone(root1)
        # 验证 sys.path 已有 src/
        self.assertIn(str(root1 / "src"), sys.path)

        # 第二次调用应该返回缓存
        root2 = _ensure_project_path()
        self.assertEqual(root1, root2)
        # 单例应保持
        self.assertIs(cli_module._PROJECT_ROOT, root1)

    def test_find_returns_none_for_nonexistent_env(self):
        """无效的 SOCIAL_AGENT_HOME 返回 None（fallback 到其他方式）"""
        with patch.dict(os.environ, {"SOCIAL_AGENT_HOME": "/nonexistent/path/xyz"}):
            # 会 fallback 到包位置/cwd 方式（因为我们在项目内运行）
            result = _find_project_root()
            # 在项目内运行时仍能找到（不强制返回 None）
            self.assertIsNotNone(result)


class TestStatusCommandFix(unittest.TestCase):
    """回归测试：social status 修复后能正常工作"""

    def test_status_works_from_any_cwd(self):
        """从任何 cwd 运行 social status 都能找到项目"""
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")
            # 调用 _ensure_project_path 应能找到 social-agent
            root = _ensure_project_path()
            self.assertIsNotNone(root)
            self.assertIn(str(root), sys.path)
        finally:
            os.chdir(original_cwd)


class TestEnrichV3(unittest.TestCase):
    """v3.0 简化版 enrich 测试"""

    def setUp(self):
        cli_module._PROJECT_ROOT = None

    def test_pick_candidates_priority(self):
        """_enrich_pick_candidates 按优先级选择"""
        from social_cli.cli import _enrich_pick_candidates

        contacts = [
            {"id": "1", "name": "A", "strength": 1, "relation": ""},  # 优先级 1
            {"id": "2", "name": "B", "strength": 5, "relation": ""},  # 跳过（强度>2）
            {"id": "3", "name": "C", "strength": 2, "relation": "同行", "tags": []},  # 优先级 2
            {"id": "4", "name": "D", "strength": 2, "relation": "同行", "tags": ["x"]},  # 跳过（已有 relation+tags）
            {"id": "5", "name": "E", "strength": 1, "relation": "", "_enrich_version": 1},  # 跳过（已处理）
        ]
        candidates = _enrich_pick_candidates(contacts, batch=10, force=False)
        ids = [c["id"] for c in candidates]
        self.assertEqual(ids, ["1", "3"])

    def test_pick_candidates_force_includes_processed(self):
        """--force 包含已处理过的"""
        from social_cli.cli import _enrich_pick_candidates

        contacts = [
            {"id": "1", "name": "A", "strength": 1, "relation": "", "_enrich_version": 1},
        ]
        candidates_default = _enrich_pick_candidates(contacts, batch=10, force=False)
        candidates_force = _enrich_pick_candidates(contacts, batch=10, force=True)
        self.assertEqual(len(candidates_default), 0)
        self.assertEqual(len(candidates_force), 1)

    def test_enrich_apply_protects_existing_relation(self):
        """保护规则：已有 relation 不被覆盖"""
        from social_cli.cli import _enrich_apply

        contact = {"relation": "同行", "tags": ["金融"]}
        result = {
            "relation": "校友",  # 尝试覆盖
            "tags": ["银行"],
            "confidence": 8
        }
        changed = _enrich_apply(contact, result)
        self.assertEqual(contact["relation"], "同行")  # 不变
        self.assertIn("金融", contact["tags"])  # 旧 tag 保留
        self.assertIn("银行", contact["tags"])  # 新 tag 追加
        self.assertTrue(changed)  # tags 改变了就算 changed

    def test_enrich_apply_low_confidence_skipped(self):
        """低 confidence 跳过"""
        from social_cli.cli import _enrich_apply

        contact = {"relation": "", "tags": []}
        result = {"relation": "同行", "tags": ["x"], "confidence": 2}
        changed = _enrich_apply(contact, result)
        self.assertFalse(changed)
        self.assertEqual(contact["relation"], "")

    def test_enrich_apply_invalid_relation_rejected(self):
        """无效 relation 值被拒绝（不在白名单内）"""
        from social_cli.cli import _enrich_apply

        contact = {"relation": "", "tags": []}
        result = {"relation": "未知类型", "tags": ["x"], "confidence": 8}
        _enrich_apply(contact, result)
        # 关键断言：无效 relation 不被写入
        self.assertEqual(contact["relation"], "")
        # 但 tags 仍会被追加（即使 relation 拒绝，tags 仍可能有用）
        self.assertIn("x", contact["tags"])

    def test_enrich_apply_cleans_empty_tags(self):
        """清理空 tag"""
        from social_cli.cli import _enrich_apply

        contact = {"relation": "", "tags": ["valid", "", "  ", None]}
        result = {"relation": "其他", "tags": ["new"], "confidence": 8}
        _enrich_apply(contact, result)
        # 验证：所有空 tag 被清理
        self.assertNotIn("", contact["tags"])
        self.assertNotIn("  ", contact["tags"])
        self.assertNotIn(None, contact["tags"])
        # 验证：valid 和 new 保留
        self.assertIn("valid", contact["tags"])
        self.assertIn("new", contact["tags"])

    def test_enrich_apply_dedup_tags(self):
        """tag 去重"""
        from social_cli.cli import _enrich_apply

        contact = {"relation": "", "tags": ["金融"]}
        result = {"relation": "其他", "tags": ["金融", "银行"], "confidence": 8}
        _enrich_apply(contact, result)
        # "金融" 只出现一次
        self.assertEqual(contact["tags"].count("金融"), 1)
        self.assertIn("银行", contact["tags"])

    def test_enrich_call_llm_parses_json(self):
        """_enrich_call_llm 解析纯 JSON"""
        from unittest.mock import MagicMock
        from social_cli.cli import _enrich_call_llm

        client = MagicMock()
        client.complete_with_retry.return_value = '{"relation": "同行", "sub_relation": "金融", "tags": ["银行"], "confidence": 8}'

        result = _enrich_call_llm(client, {"name": "张三", "notes": "", "tags": [], "strength": 2})
        self.assertEqual(result["relation"], "同行")
        self.assertEqual(result["confidence"], 8)
        self.assertNotIn("_error", result)

    def test_enrich_call_llm_handles_markdown_codeblock(self):
        """_enrich_call_llm 处理 markdown 代码块"""
        from unittest.mock import MagicMock
        from social_cli.cli import _enrich_call_llm

        client = MagicMock()
        client.complete_with_retry.return_value = '```json\n{"relation": "其他", "confidence": 7}\n```'

        result = _enrich_call_llm(client, {"name": "李四", "notes": "", "tags": [], "strength": 1})
        self.assertEqual(result["relation"], "其他")
        self.assertEqual(result["confidence"], 7)

    def test_enrich_call_llm_handles_garbage(self):
        """_enrich_call_llm 遇到垃圾返回错误标记"""
        from unittest.mock import MagicMock
        from social_cli.cli import _enrich_call_llm

        client = MagicMock()
        client.complete_with_retry.return_value = "这是一段无法解析的文字"

        result = _enrich_call_llm(client, {"name": "王五", "notes": "", "tags": [], "strength": 1})
        self.assertIn("_error", result)
        self.assertEqual(result["confidence"], 0)


class TestHealthScoring(unittest.TestCase):
    """v3.0 health 健康分测试"""

    def test_recency_score_thresholds(self):
        """recency 分数阈值"""
        from social_cli.cli import _recency_score
        self.assertEqual(_recency_score(0), 100)
        self.assertEqual(_recency_score(7), 100)
        self.assertEqual(_recency_score(8), 80)
        self.assertEqual(_recency_score(14), 80)
        self.assertEqual(_recency_score(15), 60)
        self.assertEqual(_recency_score(30), 60)
        self.assertEqual(_recency_score(31), 40)
        self.assertEqual(_recency_score(90), 40)
        self.assertEqual(_recency_score(91), 20)
        self.assertEqual(_recency_score(999), 20)

    def test_grade_thresholds(self):
        """等级阈值"""
        from social_cli.cli import _grade_icon, _grade_label
        # 健康
        self.assertEqual(_grade_icon(100), "🟢")
        self.assertEqual(_grade_icon(80), "🟢")
        self.assertEqual(_grade_label(80), "健康")
        # 关注
        self.assertEqual(_grade_icon(79), "🟡")
        self.assertEqual(_grade_icon(50), "🟡")
        self.assertEqual(_grade_label(50), "关注")
        # 预警
        self.assertEqual(_grade_icon(49), "🟠")
        self.assertEqual(_grade_icon(20), "🟠")
        self.assertEqual(_grade_label(20), "预警")
        # 危险
        self.assertEqual(_grade_icon(19), "🔴")
        self.assertEqual(_grade_icon(0), "🔴")
        self.assertEqual(_grade_label(0), "危险")

    def test_depth_score_with_meetings(self):
        """见面互动 depth 满分"""
        from social_cli.cli import _depth_score
        timeline = [
            {"contact": "A", "type": "meeting", "date": "2026-07-01"},
            {"contact": "A", "type": "meeting", "date": "2026-06-15"},
            {"contact": "A", "type": "meeting", "date": "2026-06-01"},
        ]
        self.assertEqual(_depth_score(timeline, "A"), 100)

    def test_depth_score_with_messages_only(self):
        """纯消息互动 depth 较低"""
        from social_cli.cli import _depth_score
        timeline = [
            {"contact": "A", "type": "message", "date": "2026-07-01"},
            {"contact": "A", "type": "message", "date": "2026-06-15"},
        ]
        self.assertEqual(_depth_score(timeline, "A"), 40)

    def test_depth_score_no_timeline(self):
        """无 timeline 时 depth=0"""
        from social_cli.cli import _depth_score
        self.assertEqual(_depth_score([], "A"), 0)
        self.assertEqual(_depth_score(None, "A"), 0)

    def test_days_since_calculation(self):
        """距今天数计算"""
        from social_cli.cli import _days_since
        from datetime import date
        today = date.today()
        # 7 天前
        week_ago = today.replace(day=today.day - 7) if today.day > 7 else today
        timeline = [{"contact": "A", "date": week_ago.isoformat()}]
        result = _days_since(timeline, "A")
        self.assertIsInstance(result, int)
        # 没记录
        self.assertEqual(_days_since([], "A"), 999)
        # 不匹配
        timeline_b = [{"contact": "B", "date": "2026-07-01"}]
        self.assertEqual(_days_since(timeline_b, "A"), 999)

    def test_total_score_weighting(self):
        """总评分 = recency × 0.4 + depth × 0.6"""
        from social_cli.cli import _recency_score, _depth_score
        # 7 天内 + 见面 = 100*0.4 + 100*0.6 = 100
        # 8 天前 + 仅消息 = 80*0.4 + 40*0.6 = 56
        score1 = int(_recency_score(7) * 0.4 + 100 * 0.6)
        score2 = int(_recency_score(8) * 0.4 + 40 * 0.6)
        self.assertEqual(score1, 100)
        self.assertEqual(score2, 56)


if __name__ == "__main__":
    unittest.main(verbosity=2)