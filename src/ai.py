"""AI 拟稿模块 - Social-CLI v3.0

v3.0 升级：
- 优先使用 LLM 抽象层（HTTP API，可独立运行）
- 失败时降级到 subprocess 调用 `claude` 命令（兼容旧行为）
- 公开函数签名保持不变，向后兼容所有调用方

调用优先级：
1. LLMClient.complete_with_retry() — 走 HTTP API
2. subprocess `claude --print` — 兜底（v2 兼容）
3. 返回友好错误字符串 — 最终 fallback
"""
import json
import subprocess
import sys
import yaml
from pathlib import Path
from typing import Optional

PROJECT = Path(__file__).resolve().parent.parent

# ── 配置加载 ──

def _load_ai_config():
    """从 config.yaml 读取AI和拟稿配置。"""
    config_paths = [
        PROJECT / "config" / "config.local.yaml",
        PROJECT / "config" / "config.yaml",
    ]
    for cp in config_paths:
        if cp.exists():
            with open(cp, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return cfg.get("ai", {}) or {}
    return {}

_AI_CONFIG = _load_ai_config()


# ── 调用实现 ──

def _call_via_llm_client(prompt: str, timeout: int = 30) -> Optional[str]:
    """通过 LLM 抽象层调用（v3 新增）。

    返回 None 表示调用失败，由调用方决定降级策略。
    """
    try:
        from llm import get_client, LLMError
    except ImportError:
        return None

    try:
        client = get_client()
        result = client.complete_with_retry(
            prompt,
            max_retries=1,  # 已重试1次了
        )
        return result
    except LLMError:
        return None  # 由调用方降级到 subprocess


def _call_via_subprocess(prompt: str, timeout: int = 30) -> Optional[str]:
    """通过 subprocess 调用 `claude --print`（v2 兼容路径）。

    仅在 LLMClient 不可用时降级。
    """
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _call_llm(prompt: str, timeout: int = 30) -> str:
    """统一调用入口：优先 LLMClient，降级 subprocess。

    Args:
        prompt: 完整提示词
        timeout: subprocess 路径的超时（LLMClient 用自己的配置）

    Returns:
        模型返回的原始文本。若两条路径都失败，返回空字符串。
    """
    # 路径1：LLM Client（v3）
    result = _call_via_llm_client(prompt, timeout)
    if result is not None:
        return result

    # 路径2：subprocess 兜底（v2 兼容）
    result = _call_via_subprocess(prompt, timeout)
    if result is not None:
        return result

    return ""  # 双路径都失败


# ── 公开 API（保持 v2 签名） ──

def draft_message(contact_name, context_summary, tone=None):
    """Generate a WeChat message draft using AI.

    Args:
        contact_name: 联系人名称
        context_summary: 最近互动摘要
        tone: 语气（亲切/正式/简洁），如不传则从配置读取默认值

    Returns:
        拟稿文本（字符串）。失败时返回 "（AI拟稿失败: ...）" 格式提示。
    """
    # 从配置读取默认语气
    if tone is None:
        tone = _AI_CONFIG.get("draft", {}).get("default_tone", "亲切")

    max_len = _AI_CONFIG.get("draft", {}).get("max_length", 80)
    signature = _AI_CONFIG.get("draft", {}).get("signature", "")

    tone_guide = {
        "正式": "语气正式、专业，用'您'，适合商务正式场合",
        "亲切": "语气亲切自然，像朋友之间聊天，用'你'",
        "简洁": "直接说重点，不超过30字，适合熟人",
    }
    guide = tone_guide.get(tone, tone_guide["亲切"])

    prompt = f"""你是一个社交关系AI助手。根据以下信息，生成一条微信消息草稿。

联系人：{contact_name}
最近互动摘要：{context_summary}
语气要求：{guide}
消息长度：不超过{max_len}字

要求：
1. 只输出消息文本本身，不要加引号、不要加说明
2. 不要称呼自己为AI
3. 消息要自然，像是本人写的
4. 如果是跟进事项，语气不要太急
5. 不要在消息中使用对方全名——直接写内容即可。如果必须称呼，用尊称（如x总/x老师/x兄）。
{f'6. 消息末尾可加上签名：{signature}' if signature else ''}"""

    text = _call_llm(prompt, timeout=30)
    if not text:
        return "（AI拟稿失败: LLM Client 和 subprocess 均不可用）"

    # 清理常见包裹字符（前缀/后缀的引号、标记词）
    text = text.strip()
    for prefix in ['"', "'", "「", "「", "消息：", "草稿："]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    for suffix in ['"', "'", "」", "」"]:
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    return text.strip()


def generate_reminder(contact_name, days_since, context_summary):
    """Generate a reminder message for why to contact someone.

    Returns:
        提醒文本。失败时返回简单降级字符串。
    """
    prompt = f"""你是一个社交关系AI助手。生成一条提醒消息，告诉用户为什么应该联系以下联系人：

联系人：{contact_name}
最近一次联系：{days_since}天前
最近互动摘要：{context_summary}

生成一条简短的提醒（30字以内），格式如："14天没联系了，上次聊到XX，建议打个招呼。" """

    text = _call_llm(prompt, timeout=15)
    if not text:
        # 降级：与 v2 行为一致
        return f"{days_since}天没联系{contact_name}了"
    return text.strip()