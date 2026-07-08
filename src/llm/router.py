"""LLM Router - 根据配置自动选择provider

设计：
- 单例工厂：get_client() 每次返回相同实例（避免重复初始化）
- 配置优先级：config.local.yaml > config.yaml > 环境变量
- provider注册表：可扩展，只需在 _PROVIDERS 添加
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Type

import yaml

from .base import LLMClient, LLMAuthError
from .claude import ClaudeClient
from .openai import OpenAIClient


# ── Provider 注册表 ──

_PROVIDERS: Dict[str, Type[LLMClient]] = {
    "claude": ClaudeClient,
    "openai": OpenAIClient,
    # 未来扩展：只需在这里加一行
    # "minimax": MiniMaxClient,
    # "local_ollama": OllamaClient,
}


# ── 单例缓存 ──

_client_instance: Optional[LLMClient] = None


def _find_project_root() -> Optional[Path]:
    """查找项目根目录（含 config/ 目录）"""
    # 从当前文件向上找
    p = Path(__file__).resolve()
    for _ in range(5):  # 最多向上5层
        if (p / "config").is_dir():
            return p
        p = p.parent
    # 也试试当前工作目录
    cwd = Path.cwd()
    if (cwd / "config").is_dir():
        return cwd
    return None


def _load_llm_config() -> dict:
    """从 config.yaml / config.local.yaml 读取 ai 段"""
    root = _find_project_root()
    if root is None:
        return {}

    config_paths = [
        root / "config" / "config.local.yaml",
        root / "config" / "config.yaml",
    ]

    for cp in config_paths:
        if cp.exists():
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    return cfg.get("ai", {}) or {}
            except (yaml.YAMLError, OSError):
                continue

    return {}


def get_client(force_new: bool = False) -> LLMClient:
    """获取 LLM Client 单例

    优先级：
    1. ai.engine 指定（"claude"/"openai"）
    2. 环境变量 LLM_ENGINE
    3. 默认 "claude"

    Args:
        force_new: 强制创建新实例（用于测试或切换配置）

    Returns:
        LLMClient 实例

    Raises:
        LLMAuthError: 无可用provider或认证失败
    """
    global _client_instance

    if _client_instance is not None and not force_new:
        return _client_instance

    config = _load_llm_config()

    # 决定 provider
    engine = (
        config.get("engine")
        or os.environ.get("LLM_ENGINE")
        or "claude"
    )

    if engine not in _PROVIDERS:
        raise LLMAuthError(
            f"未知 LLM engine: '{engine}'。"
            f"可用: {', '.join(_PROVIDERS.keys())}"
        )

    client_cls = _PROVIDERS[engine]

    # 构造客户端参数
    # 注：不同 provider 接受不同参数，这里只传通用参数
    kwargs = {}
    if "model" in config:
        kwargs["model"] = config["model"]
    if "api_key" in config:
        kwargs["api_key"] = config["api_key"]
    if "base_url" in config:
        kwargs["base_url"] = config["base_url"]

    _client_instance = client_cls(**kwargs)
    return _client_instance


def reset_client() -> None:
    """重置单例（测试或切换配置用）"""
    global _client_instance
    _client_instance = None


def list_providers() -> list:
    """列出所有可用 provider（用于CLI提示）"""
    return list(_PROVIDERS.keys())