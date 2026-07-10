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


# ── 目标锚定建议 (SPEC v4 §18) ──

def suggest_leverage(contact, goals, timeline_summary="", directions=None):
    """为联系人生成 leverage 锚定建议。

    Args:
        contact: 联系人 dict（含 name/tags/relation/notes 等）
        goals: 可选目标维度列表（来自 goals.yaml）
        timeline_summary: 最近互动摘要（可空）
        directions: 可选 direction 枚举列表

    Returns:
        dict: {"goals": [...], "how": "...", "direction": "..."}
        LLM 失败时降级为基于 tags/relation 的规则建议。
    """
    if directions is None:
        directions = ["我求于他", "他求于我", "互惠"]

    name = contact.get("name", contact.get("id", "?"))
    relation = contact.get("relation", contact.get("role", ""))
    sub = contact.get("sub_relation", "")
    tags = contact.get("tags", [])
    notes = contact.get("notes", "")
    if isinstance(notes, list):
        notes = " ".join(str(n) for n in notes)
    company = contact.get("company", "")
    title = contact.get("title", "")

    prompt = f"""你是社交关系经营参谋。基于以下联系人信息，建议该联系人撬动用户哪些人生目标维度，以及具体撬动方式。

用户的人生目标维度（从中选 1-3 个）：{", ".join(goals)}
direction 枚举（三选一）：{", ".join(directions)}

联系人：{name}
关系：{relation} / {sub}
公司/职位：{company} / {title}
标签：{", ".join(tags) if tags else "无"}
备注：{notes[:200] if notes else "无"}
最近互动：{timeline_summary or "无"}

只输出一行 JSON，格式：
{{"goals": ["维度1"], "how": "一句话具体撬动方式", "direction": "互惠"}}

要求：
1. goals 必须从给定维度中选，1-3 个
2. how 一句话、具体、可执行（不要空话如"多联系"）
3. direction 三选一
4. 只输出 JSON，不要其他文字"""

    text = _call_llm(prompt, timeout=20)
    if text:
        suggestion = _parse_leverage_json(text, goals, directions)
        if suggestion:
            return suggestion

    # 降级：基于 tags/relation 的规则推断
    return _rule_based_leverage(contact, goals, directions)


def _parse_leverage_json(text, valid_goals, valid_directions):
    """从 LLM 输出解析 leverage JSON，校验字段。失败返回 None。"""
    import re as _re
    # 提取第一个 {...} 块
    m = _re.search(r"\{[^{}]*\}", text, _re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    goals = data.get("goals")
    how = data.get("how")
    direction = data.get("direction")
    if not isinstance(goals, list) or not goals or not how or direction not in valid_directions:
        return None
    # 过滤非法目标维度
    goals = [g for g in goals if g in valid_goals]
    if not goals:
        return None
    return {"goals": goals, "how": str(how).strip()[:120], "direction": direction}


def _rule_based_leverage(contact, goals, directions):
    """规则降级：基于 tags/relation 推断 leverage。"""
    tags = set(t.lower() for t in contact.get("tags", []))
    relation = contact.get("relation", contact.get("role", "")).lower()
    sub = contact.get("sub_relation", "").lower()
    notes = str(contact.get("notes", "")).lower()
    name = contact.get("name", contact.get("id", "?"))

    inferred_goals = []
    # 事业：同行/创业/项目/金融科技/客户
    if any(k in tags for k in ("同行", "创业", "合作", "项目", "金融科技", "客户")) \
       or relation in ("同行", "合作", "创业") \
       or any(k in sub for k in ("银行", "金融", "科技", "证券")):
        if "事业" in goals:
            inferred_goals.append("事业")
    # 投资：投资/股票/理财
    if any(k in tags for k in ("投资", "股票", "理财", "a股", "港股")) or "投资" in notes:
        if "投资" in goals:
            inferred_goals.append("投资")
    # AI能力：ai/技术/科技
    if any(k in tags for k in ("ai", "技术", "科技", "llm", "python")) or "ai" in notes:
        if "AI能力" in goals:
            inferred_goals.append("AI能力")
    # 知识：校友/学习/读书
    if any(k in tags for k in ("校友", "读书", "学习")) or relation == "校友":
        if "知识" in goals:
            inferred_goals.append("知识")
    # 家庭：家人
    if relation in ("family", "家人") or "家人" in tags:
        if "家庭" in goals:
            inferred_goals.append("家庭")

    if not inferred_goals:
        # 兜底：默认事业（多数职场关系）
        if "事业" in goals:
            inferred_goals = ["事业"]
        else:
            inferred_goals = [goals[0]] if goals else []

    # direction 推断：家人=互惠，客户/合作=我求于他，其余=互惠
    if relation in ("family", "家人"):
        direction = "互惠"
    elif any(k in tags for k in ("客户", "合作")) or relation == "合作":
        direction = "我求于他"
    else:
        direction = "互惠"
    if direction not in directions:
        direction = directions[0]

    how = f"基于 {relation or '关系'} 维度的{inferred_goals[0]}资源互换"
    return {"goals": inferred_goals, "how": how, "direction": direction}


# ── 建议引擎 (SPEC v4 §19) ──

def draft_advise(candidate):
    """把单个候选转成"联系谁+为什么+聊什么"三元组建议。

    Args:
        candidate: advise_candidates() 返回的 dict
            含 contact/signals/score/days_since/last_interaction/leverage/has_birthday/has_todo

    Returns:
        dict: {"who": str, "why": str, "what": str, "score": int}
        LLM 失败时降级为基于信号的规则拼接。
    """
    contact = candidate["contact"]
    name = contact.get("name", contact.get("id", "?"))
    signals = candidate.get("signals", [])
    last_interaction = candidate.get("last_interaction", "")
    leverage = candidate.get("leverage")
    has_birthday = candidate.get("has_birthday")
    birthday_info = candidate.get("birthday_info") or {}
    has_todo = candidate.get("has_todo")
    todo_info = candidate.get("todo_info") or {}
    days_since = candidate.get("days_since", 9999)

    # ── why: 信号拼接（规则，不用 LLM） ──
    why = "；".join(signals) if signals else "常规维护"

    # ── what: LLM 生成"聊什么" ──
    leverage_str = ""
    if leverage and leverage.get("confirmed"):
        leverage_str = f"目标锚定: {','.join(leverage.get('goals', []))} — {leverage.get('how', '')}"

    todo_str = ""
    if has_todo and todo_info:
        todo_str = f"有待办: {todo_info.get('task', todo_info.get('content', ''))}"

    bday_str = ""
    if has_birthday and birthday_info:
        bday_str = f"即将生日: {birthday_info.get('date', '?')}"

    prompt = f"""你是社交关系经营参谋。基于以下信号，为用户生成一条具体的"聊什么"建议（一句话，可执行）。

联系人：{name}
关系：{contact.get('relation', '')} / {contact.get('sub_relation', '')}
上次互动：{last_interaction or '无'}（{days_since}天前）
信号：{'; '.join(signals) if signals else '无'}
{leverage_str}
{bday_str}
{todo_str}

要求：
1. 只输出一句话，告诉用户"跟这个人聊什么"
2. 具体、可执行（不要"打个招呼"这种空话）
3. 基于上次互动内容跟进，或基于锚定目标推进
4. 不超过 50 字"""

    text = _call_llm(prompt, timeout=15)
    if text:
        what = text.strip().strip('"').strip('「').strip('」')
        if what:
            return {"who": name, "why": why, "what": what, "score": candidate.get("score", 0)}

    # 降级：规则拼接"聊什么"
    what = _rule_based_what(candidate)
    return {"who": name, "why": why, "what": what, "score": candidate.get("score", 0)}


def _rule_based_what(candidate):
    """规则降级：基于信号拼接"聊什么"。"""
    contact = candidate["contact"]
    name = contact.get("name", "?")
    last_interaction = candidate.get("last_interaction", "")
    has_birthday = candidate.get("has_birthday")
    has_todo = candidate.get("has_todo")
    todo_info = candidate.get("todo_info") or {}
    leverage = candidate.get("leverage")
    days_since = candidate.get("days_since", 9999)

    if has_birthday:
        return f"准备生日祝福，提前一天发送"
    if has_todo and todo_info:
        task = todo_info.get("task", todo_info.get("content", ""))
        return f"跟进待办: {task[:40]}"
    if leverage and leverage.get("confirmed"):
        return f"围绕{leverage.get('goals', ['事业'])[0]}推进: {leverage.get('how', '日常经营')[:40]}"
    if last_interaction:
        return f"跟进上次话题: {last_interaction[:40]}"
    if days_since >= 21:
        return f"太久没联系，发个近况问候"
    return f"日常问候，分享近期动态"


def generate_advise_report(candidates, top=5):
    """生成本周经营简报（SPEC v4 §19.2）。

    Args:
        candidates: advise_candidates() 返回的列表
        top: 取前 N 条（SPEC §19.2: 3-5 封顶）

    Returns:
        list of {"who", "why", "what", "score"} 三元组
    """
    report = []
    for c in candidates[:top]:
        report.append(draft_advise(c))
    return report