"""LLM 抽象层单元测试

测试覆盖：
1. 抽象类不可实例化
2. 异常体系
3. ClaudeClient/OpenAIClient 实例化（mock）
4. HTTP 错误映射（401/429/500/超时）
5. 响应解析（成功/失败）
6. 重试机制
7. Router 配置驱动
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 将src加入路径以便导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from llm import (
    LLMClient, LLMError, LLMAuthError, LLMRateLimitError,
    LLMTimeoutError, LLMResponseError, ClaudeClient, OpenAIClient,
    get_client, reset_client, list_providers,
)


# ── 1. 抽象类与异常体系 ──

class TestAbstractAndExceptions(unittest.TestCase):

    def test_cannot_instantiate_abstract(self):
        """抽象类不可直接实例化"""
        with self.assertRaises(TypeError):
            LLMClient()

    def test_exception_hierarchy(self):
        """异常类继承关系正确"""
        self.assertTrue(issubclass(LLMAuthError, LLMError))
        self.assertTrue(issubclass(LLMRateLimitError, LLMError))
        self.assertTrue(issubclass(LLMTimeoutError, LLMError))
        self.assertTrue(issubclass(LLMResponseError, LLMError))

    def test_exception_status_code(self):
        """异常可携带 status_code"""
        err = LLMAuthError("test", status_code=401)
        self.assertEqual(err.status_code, 401)
        self.assertIn("test", str(err))


# ── 2. ClaudeClient 实例化与配置 ──

class TestClaudeClientInit(unittest.TestCase):

    def setUp(self):
        # 清除可能的环境变量（包括 v3.0.3 新增的 AUTH_TOKEN fallback）
        self._saved_env = {}
        for k in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                  "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL"]:
            if k in os.environ:
                self._saved_env[k] = os.environ.pop(k)

    def tearDown(self):
        for k, v in self._saved_env.items():
            os.environ[k] = v

    def test_init_with_api_key(self):
        """显式传入 api_key"""
        client = ClaudeClient(api_key="sk-ant-test")
        self.assertEqual(client.api_key, "sk-ant-test")
        self.assertEqual(client.model, "claude-sonnet-4-6")
        self.assertEqual(client.base_url, "https://api.anthropic.com")

    def test_init_with_env(self):
        """从环境变量读取"""
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-from-env"
        os.environ["ANTHROPIC_MODEL"] = "claude-opus-4-8"
        client = ClaudeClient()
        self.assertEqual(client.api_key, "sk-ant-from-env")
        self.assertEqual(client.model, "claude-opus-4-8")

    def test_init_without_key_raises(self):
        """无 api_key 应抛出 LLMAuthError"""
        with self.assertRaises(LLMAuthError):
            ClaudeClient()

    def test_custom_base_url(self):
        """支持自定义 base_url（用于代理）"""
        client = ClaudeClient(api_key="sk-test", base_url="https://proxy.example.com")
        self.assertEqual(client.base_url, "https://proxy.example.com")


# ── 3. ClaudeClient HTTP 调用（mock httpx） ──

class TestClaudeClientCall(unittest.TestCase):

    def setUp(self):
        self.client = ClaudeClient(api_key="sk-ant-test")

    def _mock_response(self, status_code, json_data=None, text=""):
        """构造 mock httpx.Response"""
        resp = MagicMock()
        resp.status_code = status_code
        if json_data is not None:
            resp.json.return_value = json_data
            resp.text = json.dumps(json_data)
        else:
            resp.json.side_effect = json.JSONDecodeError("err", "x", 0)
            resp.text = text
        return resp

    def _success_response(self, text="你好"):
        return self._mock_response(200, {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
        })

    @patch("llm.claude.httpx.Client")
    def test_complete_success(self, mock_client_cls):
        """成功调用"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._success_response("测试响应")
        mock_client_cls.return_value = mock_client

        result = self.client.complete("hello")
        self.assertEqual(result, "测试响应")

    @patch("llm.claude.httpx.Client")
    def test_complete_with_system(self, mock_client_cls):
        """system 参数被正确传递"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._success_response("ok")
        mock_client_cls.return_value = mock_client

        self.client.complete("user prompt", system="you are helpful")
        # 检查请求体
        call_args = mock_client.post.call_args
        body = call_args.kwargs["json"]
        self.assertEqual(body["system"], "you are helpful")
        self.assertEqual(body["messages"][0]["content"], "user prompt")

    @patch("llm.claude.httpx.Client")
    def test_401_raises_auth_error(self, mock_client_cls):
        """401 → LLMAuthError"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._mock_response(401, text="invalid api key")
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMAuthError) as ctx:
            self.client.complete("hi")
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("llm.claude.httpx.Client")
    def test_429_raises_rate_limit(self, mock_client_cls):
        """429 → LLMRateLimitError"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._mock_response(429, text="rate limited")
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMRateLimitError):
            self.client.complete("hi")

    @patch("llm.claude.httpx.Client")
    def test_500_raises_response_error(self, mock_client_cls):
        """500 → LLMResponseError（可重试）"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._mock_response(500, text="server error")
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMResponseError):
            self.client.complete("hi")

    @patch("llm.claude.httpx.Client")
    def test_timeout_raises_timeout_error(self, mock_client_cls):
        """超时 → LLMTimeoutError"""
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMTimeoutError):
            self.client.complete("hi")

    @patch("llm.claude.httpx.Client")
    def test_invalid_json_raises_response_error(self, mock_client_cls):
        """响应非 JSON → LLMResponseError"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._mock_response(200, json_data=None, text="<html>")
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMResponseError):
            self.client.complete("hi")

    @patch("llm.claude.httpx.Client")
    def test_missing_content_raises_response_error(self, mock_client_cls):
        """响应缺 content → LLMResponseError"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = self._mock_response(200, {"error": "no content"})
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMResponseError):
            self.client.complete("hi")


# ── 4. 重试机制 ──

class TestRetry(unittest.TestCase):

    def setUp(self):
        self.client = ClaudeClient(api_key="sk-ant-test")

    @patch("time.sleep")  # 加速测试（base.py 局部导入 time）
    @patch("llm.claude.httpx.Client")
    def test_retry_on_rate_limit(self, mock_client_cls, mock_sleep):
        """速率限制应重试"""
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        # 前两次429，第三次成功
        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {"content": [{"type": "text", "text": "终于成功"}]}

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.text = "rate limited"

        mock_client.post.side_effect = [rate_limited, rate_limited, success]
        mock_client_cls.return_value = mock_client

        result = self.client.complete_with_retry("hi", max_retries=2)
        self.assertEqual(result, "终于成功")
        self.assertEqual(mock_client.post.call_count, 3)
        # 验证有 sleep 退避
        self.assertGreater(mock_sleep.call_count, 0)

    @patch("llm.claude.httpx.Client")
    def test_no_retry_on_auth_error(self, mock_client_cls):
        """认证错误不应重试"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        auth_err = MagicMock()
        auth_err.status_code = 401
        auth_err.text = "bad key"
        mock_client.post.return_value = auth_err
        mock_client_cls.return_value = mock_client

        with self.assertRaises(LLMAuthError):
            self.client.complete_with_retry("hi", max_retries=3)
        # 只调用一次，不重试
        self.assertEqual(mock_client.post.call_count, 1)


# ── 5. OpenAIClient 关键测试（精简版） ──

class TestOpenAIClient(unittest.TestCase):

    def setUp(self):
        for k in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]:
            os.environ.pop(k, None)

    def test_init_with_base_url(self):
        """支持 MiniMax 等通过 base_url 切换"""
        client = OpenAIClient(
            api_key="sk-test",
            base_url="https://api.minimaxi.com/v1",
            model="MiniMax-Text-01",
        )
        self.assertEqual(client.base_url, "https://api.minimaxi.com/v1")
        self.assertEqual(client.model, "MiniMax-Text-01")

    def test_no_key_raises(self):
        with self.assertRaises(LLMAuthError):
            OpenAIClient()

    @patch("llm.openai.httpx.Client")
    def test_complete_success(self, mock_client_cls):
        """成功调用 + 响应解析"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": "openai回复"}}]
        }
        mock_client.post.return_value = resp
        mock_client_cls.return_value = mock_client

        client = OpenAIClient(api_key="sk-test")
        result = client.complete("hi")
        self.assertEqual(result, "openai回复")


# ── 6. Router ──

class TestRouter(unittest.TestCase):

    def setUp(self):
        reset_client()
        self._saved_env = {}
        for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_ENGINE"]:
            if k in os.environ:
                self._saved_env[k] = os.environ.pop(k)

    def tearDown(self):
        reset_client()
        for k, v in self._saved_env.items():
            os.environ[k] = v

    def test_list_providers(self):
        """至少注册了 claude 和 openai"""
        providers = list_providers()
        self.assertIn("claude", providers)
        self.assertIn("openai", providers)

    @patch("llm.router._load_llm_config")
    def test_router_returns_claude_by_default(self, mock_config):
        """默认配置 → ClaudeClient"""
        mock_config.return_value = {"engine": "claude", "api_key": "sk-test"}
        client = get_client()
        self.assertIsInstance(client, ClaudeClient)

    @patch("llm.router._load_llm_config")
    def test_router_returns_openai_when_configured(self, mock_config):
        """配置 openai → OpenAIClient"""
        mock_config.return_value = {"engine": "openai", "api_key": "sk-test"}
        client = get_client()
        self.assertIsInstance(client, OpenAIClient)

    @patch("llm.router._load_llm_config")
    def test_router_unknown_engine_raises(self, mock_config):
        """未知 engine 报错"""
        mock_config.return_value = {"engine": "unknown_model"}
        with self.assertRaises(LLMAuthError):
            get_client()

    def test_router_is_singleton(self):
        """get_client 返回单例"""
        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        with patch("llm.router._load_llm_config") as mock_config:
            mock_config.return_value = {}
            c1 = get_client()
            c2 = get_client()
            self.assertIs(c1, c2)


if __name__ == "__main__":
    unittest.main(verbosity=2)