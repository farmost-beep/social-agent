"""LLM 抽象层 - Social-CLI v3.0

公开API：
- get_client(): 获取 LLM Client 单例（最常用）
- LLMClient: 抽象基类（自定义provider时用）
- 异常类: LLMError / LLMAuthError / LLMRateLimitError / LLMTimeoutError / LLMResponseError
- list_providers(): 列出可用provider
"""
from .base import (
    LLMClient,
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMResponseError,
)
from .claude import ClaudeClient
from .openai import OpenAIClient
from .router import get_client, reset_client, list_providers

__all__ = [
    # 工厂
    "get_client",
    "reset_client",
    "list_providers",
    # 基类
    "LLMClient",
    # 实现
    "ClaudeClient",
    "OpenAIClient",
    # 异常
    "LLMError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMResponseError",
]