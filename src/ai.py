"""AI drafting module for Social Relationship AI Agent."""
import json, subprocess, sys, yaml
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# ── 加载配置 ──

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

def draft_message(contact_name, context_summary, tone=None):
    """Generate a WeChat message draft using AI.

    Args:
        contact_name: 联系人名称
        context_summary: 最近互动摘要
        tone: 语气（亲切/正式/简洁），如不传则从配置读取默认值
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

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT),
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            for prefix in ['"', "'", "「", "「", "消息：", "草稿："]:
                if text.startswith(prefix):
                    text = text[len(prefix):]
            for suffix in ['"', "'", "」", "」"]:
                if text.endswith(suffix):
                    text = text[:-len(suffix)]
            return text.strip()
        return f"（AI拟稿失败: {result.stderr[:100]}）"
    except subprocess.TimeoutExpired:
        return "（AI拟稿超时，请重试）"
    except FileNotFoundError:
        return "（未找到claude命令，请确认Claude Code已安装）"
    except Exception as e:
        return f"（AI拟稿异常: {str(e)[:50]}）"


def generate_reminder(contact_name, days_since, context_summary):
    """Generate a reminder message for why to contact someone."""
    prompt = f"""你是一个社交关系AI助手。生成一条提醒消息，告诉用户为什么应该联系以下联系人：

联系人：{contact_name}
最近一次联系：{days_since}天前
最近互动摘要：{context_summary}

生成一条简短的提醒（30字以内），格式如："14天没联系了，上次聊到XX，建议打个招呼。" """

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"{days_since}天没联系{contact_name}了"
    except:
        return f"{days_since}天没联系{contact_name}了"
