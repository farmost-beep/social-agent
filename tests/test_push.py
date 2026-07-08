"""push 模块 + social send 命令单元测试 (v3.1)"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestPushCore(unittest.TestCase):
    """social_cli/push.py 核心测试"""

    def setUp(self):
        # 保存原始环境
        self._project_root = Path(__file__).resolve().parent.parent

    def test_find_contact_weixin_id_exact(self):
        """精确匹配联系人微信 ID"""
        from social_cli.push import find_contact_weixin_id

        with patch("social_cli.push.CONTACTS_FILE", self._make_contacts([
            {"name": "张三", "platforms": {"weixin": "wxid_zhangsan"}, "strength": 3},
            {"name": "李四", "platforms": {"weixin": "wxid_lisi"}, "strength": 2},
        ])):
            self.assertEqual(find_contact_weixin_id("张三"), "wxid_zhangsan")
            self.assertEqual(find_contact_weixin_id("李四"), "wxid_lisi")

    def test_find_contact_weixin_id_fuzzy(self):
        """模糊匹配联系人"""
        from social_cli.push import find_contact_weixin_id

        with patch("social_cli.push.CONTACTS_FILE", self._make_contacts([
            {"name": "许封 (xu_feng)", "platforms": {"weixin": "wxid_xf"}, "strength": 5},
        ])):
            self.assertEqual(find_contact_weixin_id("许封"), "wxid_xf")

    def test_find_contact_weixin_id_not_found(self):
        """找不到时返回 None"""
        from social_cli.push import find_contact_weixin_id

        with patch("social_cli.push.CONTACTS_FILE", self._make_contacts([])):
            self.assertIsNone(find_contact_weixin_id("不存在的人"))

    def test_find_contact_file_missing(self):
        """contacts.json 不存在时返回 None"""
        from social_cli.push import find_contact_weixin_id

        with patch("social_cli.push.CONTACTS_FILE",
                   Path("/nonexistent/path/contacts.json")):
            self.assertIsNone(find_contact_weixin_id("张三"))

    def _make_contacts(self, contacts):
        """创建临时 contacts.json 的路径"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(contacts, tmp, ensure_ascii=False)
        tmp.close()
        return Path(tmp.name)

    def test_push_to_wechat_success(self):
        """push_to_wechat 成功调用 osascript"""
        from social_cli.push import push_to_wechat

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "✓ 消息已发送到：测试"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            with patch("social_cli.push._write_timeline"):  # 不写文件
                result = push_to_wechat("测试", "你好")
        self.assertTrue(result["success"])

    def test_push_to_wechat_failure(self):
        """push_to_wechat 失败时返回错误"""
        from social_cli.push import push_to_wechat

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "execution error: -1719"

        with patch("subprocess.run", return_value=mock_result):
            result = push_to_wechat("测试", "你好")
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_throttle(self):
        """节流控制"""
        from social_cli.push import push_to_wechat, _last_send_time

        # 重置计时器
        import social_cli.push as push_mod
        push_mod._last_send_time = 0.0

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch("social_cli.push._write_timeline"):
                with patch("social_cli.push.time.sleep") as mock_sleep:
                    push_to_wechat("测试", "消息1")
                    # 第一次不 sleep
                    push_to_wechat("测试", "消息2")
                    # 第二次应该 sleep
                    self.assertGreater(mock_sleep.call_count, 0)

    def test_check_available_all_ok(self):
        """check_available 全部通过"""
        from social_cli.push import check_available

        with patch("social_cli.push.APPLESCRIPT",
                   Path("/tmp/send_to_wechat.applescript")):
            # 模拟文件存在
            with patch.object(Path, "exists", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    result = check_available()
                    # 至少 osascript 命令检测通过
                    self.assertIn("checks", result)

    def test_push_message_truncated_at_500(self):
        """超长消息被截断到 500 字符"""
        from social_cli.push import push_to_wechat
        long_msg = "x" * 1000

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "✓"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("social_cli.push._write_timeline"):
                push_to_wechat("测试", long_msg)
            # 检查传给 subprocess 的消息被截断
            cmd = mock_run.call_args[0][0]
            msg_arg = cmd[2]
            self.assertLessEqual(len(msg_arg), 500)


class TestSendCommand(unittest.TestCase):
    """CLI send 命令测试"""

    def test_send_help(self):
        """send --help 显示使用信息"""
        from social_cli.cli import build_parser
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["send", "--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_send_requires_contact(self):
        """send 缺 -c 报错"""
        from social_cli.cli import main
        with self.assertRaises(SystemExit):
            main(["send", "-m", "msg", "--confirm"])

    def test_send_requires_message(self):
        """send 缺 -m 报错"""
        from social_cli.cli import main
        with self.assertRaises(SystemExit):
            main(["send", "-c", "张三", "--confirm"])

    @patch("social_cli.push.push_to_wechat")
    def test_send_success(self, mock_push):
        """send 成功路径（带 --confirm）"""
        from social_cli.cli import main
        mock_push.return_value = {"success": True}
        result = main(["send", "-c", "文件传输助手", "-m", "你好", "--confirm"])
        self.assertEqual(result, 0)

    @patch("social_cli.push.push_to_wechat")
    def test_send_failure(self, mock_push):
        """send 失败路径（带 --confirm）"""
        from social_cli.cli import main
        mock_push.return_value = {"success": False, "error": "测试错误"}
        result = main(["send", "-c", "张三", "-m", "你好", "--confirm"])
        self.assertNotEqual(result, 0)

    def test_send_requires_confirm(self):
        """send 缺 --confirm 只预览不发送"""
        from social_cli.cli import main
        with patch("social_cli.push.push_to_wechat") as mock_push:
            result = main(["send", "-c", "张三", "-m", "test"])
            self.assertNotEqual(result, 0)
            mock_push.assert_not_called()  # 没被调用

    def test_send_check_help(self):
        """send-check --help"""
        from social_cli.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["send-check", "张三"])
        self.assertEqual(args.command, "send-check")
        self.assertEqual(args.contact, "张三")


if __name__ == "__main__":
    unittest.main(verbosity=2)