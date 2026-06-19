"""AI-driven batch enrichment for contact profiles.

v2.5.0 P0 — 批量画像补全管道

Uses AI to infer contact attributes (role, tags, industry) from available signals.
Implements conservative write rules per SPEC §8.2:
- Confidence 8-10: write relation + tags + notes
- Confidence 5-7:  append notes only
- Confidence 1-4:  skip entirely

外部网络信源（--web）：
- 通过 DuckDuckGo HTML 搜索获取联系人公开信息
- 搜索结果注入 AI 提示词作为额外上下文
- 提升高价值联系人的补全准确率
"""
import json, subprocess, sys, time
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent
ENRICHMENT_LOG = PROJECT / "data" / "enrichment_log.json"

# ── 外部网络信源 ──

_WEB_SEARCH_CACHE = {}  # query → results, 避免同一批次重复搜索


def search_web(name, context="", contact=None):
    """搜索联系人的公开网络信息。

    使用 DuckDuckGo HTML 搜索（免费，无需 API Key）。
    结果通过同名检测后才保留，防止张三的搜索结果被误用到同名的另一个人。

    Args:
        name: 联系人姓名
        context: 额外的搜索上下文（如公司、职位等）
        contact: 联系人 dict（用于同名检测，不传则跳过检测）

    Returns:
        str: 格式化后的搜索结果摘要，或空字符串
    """
    query = f"{name} {context}" if context else name
    query = query.strip()[:80]

    # 缓存命中
    if query in _WEB_SEARCH_CACHE:
        return _WEB_SEARCH_CACHE[query]

    # 无有效上下文 → 无法做同名验证 → 跳过网络搜索
    if not context and contact:
        keywords = _extract_keywords(contact)
        if not keywords:
            _WEB_SEARCH_CACHE[query] = ""
            return ""

    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=8,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        raw_items = []
        for r in soup.select(".result")[:5]:  # 取前 5 条用于过滤
            title_el = r.select_one(".result__title a")
            snippet_el = r.select_one(".result__snippet")
            if title_el:
                raw_items.append({
                    "title": title_el.get_text(strip=True),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })

        # ── 同名检测 ──
        contact_keywords = _extract_keywords(contact) if contact else set()
        passed = []
        for item in raw_items:
            if contact_keywords:
                if _is_same_person(name, item["title"], item["snippet"], contact_keywords):
                    passed.append(item)
            else:
                # 没有身份关键词：仅保留标题含全名的结果
                if name.lower() in (item["title"] + " " + item["snippet"]).lower():
                    passed.append(item)

        # 没有通过任何结果 → 返回空
        if not passed:
            _WEB_SEARCH_CACHE[query] = ""
            return ""

        # 格式化为文本
        snippets = [f"· {item['title']}\n  {item['snippet']}" for item in passed[:3]]
        result = "\n\n".join(snippets)
        _WEB_SEARCH_CACHE[query] = result
        return result
    except Exception:
        return ""


def _make_search_context(contact):
    """从联系人数据中提取搜索上下文关键词。"""
    parts = []
    # 从 tags 中提取有信息量的标签
    for t in contact.get("tags", []):
        t = t.strip()
        if t and t not in ("角色x1", "角色x2", "角色x3", "微信通讯录"):
            parts.append(t)
    # 从 notes 中提取
    raw = contact.get("notes")
    if isinstance(raw, list):
        notes = " ".join(raw)[:60] if raw else ""
    else:
        notes = str(raw or "")[:60]
    if notes:
        parts.append(notes)
    # 从 relation 提取
    rel = contact.get("relation") or contact.get("role") or ""
    if rel and rel not in ("其他", "校友"):
        parts.append(rel)
    return " ".join(parts[:5])[:60]


def _extract_keywords(contact):
    """从联系人数据中提取可校验的身份关键词，用于同名检测。

    Returns:
        set: 关键词集合（公司/学校/行业/组织等）
    """
    keywords = set()
    for t in contact.get("tags", []):
        t = t.strip()
        # 过滤无信息量的标签
        if t and t not in ("角色x1", "角色x2", "角色x3", "微信通讯录",
                          "Oustc", "0ustc", "1dc", "2dc"):
            keywords.add(t.lower())

    raw = contact.get("notes")
    if isinstance(raw, list):
        notes_text = " ".join(raw) if raw else ""
    else:
        notes_text = str(raw or "")
    # 从备注中提取潜在的组织/公司关键词（中文2-6字词组）
    import re
    orgs = re.findall(r'[一-鿿]{2,6}(?:公司|银行|大学|学院|资本|投资|证券|基金|科技|集团|合伙|律师)', notes_text)
    keywords.update(o.lower() for o in orgs)

    rel = contact.get("relation") or contact.get("role") or ""
    if rel and rel not in ("其他", "校友"):
        keywords.add(rel.lower())

    return keywords


def _is_same_person(name, title, snippet, contact_keywords):
    """检测搜索结果是否指向同一个联系人。

    策略：
    - 强匹配：标题含姓名 且 摘要含 ≥1 个身份关键词 → 可信
    - 弱匹配：标题含姓名 且 摘要不含关键词 → 无足够证据，弃用
    - 跨人匹配：摘要含关键词但标题不含姓名 → 大概率同名不同人，弃用

    Args:
        name: 联系人姓名
        title: 搜索结果标题
        snippet: 搜索结果摘要
        contact_keywords: 联系人身份关键词集合

    Returns:
        bool: 是否通过同名检测
    """
    text = (title + " " + snippet).lower()

    # 搜索结果必须包含姓名（基本过滤）
    name_in_text = name.lower() in text
    if not name_in_text:
        return False

    # 无身份关键词 → 无法验证 → 保守处理，弃用
    if not contact_keywords:
        return False

    # 检查身份关键词是否出现在结果中
    matched = sum(1 for kw in contact_keywords if kw in text)

    # 至少命中 1 个关键词才通过
    return matched >= 1


# ── 提示词模板 ──

_ENRICH_PROMPT = """你是社交关系分析专家。根据以下信息，推断这个人的社交角色分类。

联系人姓名：{name}
已有备注：{notes}
已有标签：{tags}
已有记忆：{memories}
所属群组：{groups}
{web_context}
请推断以下信息，以 JSON 格式返回，不要有任何其他文字：

1. relation（角色分类）：从以下选项中选择最合适的一个——"同行"（同行业/同单位）、"校友"（同校校友）、"合作"（业务/项目合作）、"家人"、"其他"
2. sub_relation（子分类）：更具体的分类（如"银行/量化/创业/学术/医疗/法律/政府"），自由文本，没有把握就填空字符串
3. suggested_tags（建议标签）：数组，建议为该联系人添加的标签（每条2-4字），如["金融","银行","上海","科大"]
4. notes_append（备注补全）：一句话总结推断结果，不超过20字，如"推测为银行同业，上海地区"
5. confidence（置信度1-10）：推理把握程度。8-10=强证据（有明确的行业/职位/学校线索），5-7=中等（有部分线索可推断），1-4=弱（仅有姓名）

JSON格式：
{{"relation": "同行", "sub_relation": "银行", "suggested_tags": ["金融","银行"], "notes_append": "推测为银行同业，上海地区", "confidence": 7}}"""


def build_enrich_prompt(contact, web_context=""):
    """构建单个联系人的 AI 推理提示词。

    Args:
        contact: 联系人 dict
        web_context: 可选的外部网络搜索结果摘要

    Returns:
        str: AI 提示词
    """
    name = contact.get("name", "?")
    tags = "、".join(contact.get("tags", [])) or "（无）"
    raw = contact.get("notes")
    if isinstance(raw, list):
        notes = " ".join(raw) if raw else "（无）"
    else:
        notes = str(raw or "") or "（无）"
    memories_list = contact.get("memories", [])
    memos = "；".join(m.get("content", "")[:80] for m in memories_list[:3]) or "（无）"
    groups = "、".join(contact.get("_groups", [])) or "（未知）"
    web_section = f"\n网络公开信息（搜索结果）：\n{web_context}\n" if web_context else ""
    web_section = web_section[:500]  # 限制网络信息长度

    return _ENRICH_PROMPT.format(
        name=name[:20],
        notes=notes[:200],
        tags=tags[:100],
        memories=memos[:300],
        groups=groups[:100],
        web_context=web_section,
    )


def parse_enrich_response(text):
    """解析 AI 返回的 JSON 推理结果。

    Returns:
        dict 包含 relation / sub_relation / suggested_tags / notes_append / confidence
        解析失败则返回 None
    """
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        result = json.loads(text[start:end])

        # 校验必需字段
        for field in ("relation", "confidence"):
            if field not in result:
                return None

        # 默认值
        result.setdefault("sub_relation", "")
        result.setdefault("suggested_tags", [])
        result.setdefault("notes_append", "")

        # 规范化置信度
        result["confidence"] = max(1, min(10, int(result.get("confidence", 5))))

        # 规范化角色分类
        valid = ("同行", "校友", "合作", "家人", "其他")
        if result["relation"] not in valid:
            result["relation"] = "其他"

        # tags 必须为 list
        if not isinstance(result["suggested_tags"], list):
            result["suggested_tags"] = [str(result["suggested_tags"])]

        return result
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def _call_ai(prompt, timeout=25):
    """调用 Claude CLI 执行推理。"""
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _log_enrichment(contact_id, contact_name, actions):
    """追加一条补全日志到 enrichment_log.json。"""
    log = []
    if ENRICHMENT_LOG.exists():
        try:
            with open(ENRICHMENT_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (json.JSONDecodeError, Exception):
            log = []

    log.append({
        "date": datetime.now().isoformat(),
        "contact_id": contact_id,
        "contact_name": contact_name,
        "actions": actions,
    })

    # 只保留最近 2000 条
    if len(log) > 2000:
        log = log[-2000:]

    ENRICHMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ENRICHMENT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def enrich_contact(contact, dry_run=False, use_web=False):
    """对单个联系人执行 AI 画像补全。

    Args:
        contact: 联系人 dict
        dry_run: 仅预览不写入
        use_web: 是否使用外部网络搜索增强上下文

    Returns:
        dict 补全结果，包含 status / confidence / actions 等字段
    """
    # 推迟导入避免循环依赖
    from engine import update_contact

    name = contact.get("name", "?")
    contact_id = contact.get("id", "")

    if not contact_id:
        return {"status": "error", "error": "missing contact_id"}

    # ── 外部网络信源 ──
    web_context = ""
    if use_web:
        ctx_keywords = _make_search_context(contact)
        web_context = search_web(name, ctx_keywords, contact=contact)
        if web_context:
            time.sleep(0.3)  # 速率限制：300ms 间隔

    # ── 调用 AI ──
    prompt = build_enrich_prompt(contact, web_context=web_context)
    response = _call_ai(prompt)
    if not response:
        return {
            "contact_id": contact_id, "name": name,
            "status": "error", "error": "AI 调用失败或超时",
        }

    result = parse_enrich_response(response)
    if not result:
        return {
            "contact_id": contact_id, "name": name,
            "status": "error", "error": "AI 响应解析失败",
            "_raw": response[:200],
        }

    confidence = result["confidence"]

    # ── Dry-run 模式 ──
    if dry_run:
        ret = {
            "contact_id": contact_id,
            "name": name,
            "status": "dry_run",
            "confidence": confidence,
            "relation": result["relation"],
            "sub_relation": result["sub_relation"],
            "suggested_tags": result["suggested_tags"],
            "notes_append": result["notes_append"],
        }
        if use_web:
            ret["web_found"] = bool(web_context)
        return ret

    actions = []

    # ── 应用补全（按置信度分级） ──
    if confidence >= 8:
        # 高置信度：写入 relation + tags + notes
        updates = {}

        # relation：不覆盖已有值
        existing_rel = (contact.get("relation") or contact.get("role") or "")
        if existing_rel and existing_rel != "其他":
            actions.append({
                "field": "relation", "from": existing_rel, "to": existing_rel,
                "skipped": "already set", "confidence": confidence,
            })
        else:
            updates["relation"] = result["relation"]
            actions.append({
                "field": "relation", "from": existing_rel or None,
                "to": result["relation"], "confidence": confidence,
            })

        # sub_relation
        if result.get("sub_relation"):
            updates["sub_relation"] = result["sub_relation"]
            actions.append({
                "field": "sub_relation", "to": result["sub_relation"],
                "confidence": confidence,
            })

        # tags：只追加不覆写
        existing_tags = set(contact.get("tags", []))
        new_tags = [t for t in result.get("suggested_tags", [])
                    if t and t not in existing_tags]
        if new_tags:
            updates["tags"] = new_tags
            actions.append({
                "field": "tags", "appended": new_tags,
                "confidence": confidence,
            })

        # notes：追加，加 [AI补全] 前缀
        notes_append = result.get("notes_append", "").strip()
        if notes_append:
            prefix = "[AI补全] "
            raw_existing = contact.get("notes")
            if isinstance(raw_existing, list):
                existing_notes = " ".join(raw_existing) if raw_existing else ""
            else:
                existing_notes = str(raw_existing or "")
            if prefix not in existing_notes:
                updates["notes"] = (existing_notes + "\n" + prefix + notes_append).strip()
                actions.append({
                    "field": "notes", "appended": prefix + notes_append,
                    "confidence": confidence,
                })

        if not updates:
            _mark_enriched(contact_id)
            return {
                "contact_id": contact_id, "name": name,
                "status": "no_update", "confidence": confidence,
                "reason": "all fields already have values",
            }

        # 执行写入
        ok, msg = update_contact(contact_id, updates)
        if ok:
            _mark_enriched(contact_id)
            _log_enrichment(contact_id, name, actions)
            return {
                "contact_id": contact_id, "name": name,
                "status": "enriched", "confidence": confidence,
                "actions": actions,
            }
        else:
            return {
                "contact_id": contact_id, "name": name,
                "status": "error", "error": msg,
            }

    elif confidence >= 5:
        # 中置信度：仅追加 notes
        notes_append = result.get("notes_append", "").strip()
        if not notes_append:
            return {
                "contact_id": contact_id, "name": name,
                "status": "skipped", "confidence": confidence,
                "reason": "no notes_append provided",
            }

        prefix = "[AI补全] "
        raw_existing = contact.get("notes")
        if isinstance(raw_existing, list):
            existing_notes = " ".join(raw_existing) if raw_existing else ""
        else:
            existing_notes = str(raw_existing or "")
        if prefix in existing_notes:
            _mark_enriched(contact_id)
            return {
                "contact_id": contact_id, "name": name,
                "status": "no_update", "confidence": confidence,
                "reason": "already has AI note",
            }

        updates = {"notes": (existing_notes + "\n" + prefix + notes_append).strip()}
        ok, msg = update_contact(contact_id, updates)
        if ok:
            _mark_enriched(contact_id)
            _log_enrichment(contact_id, name, [{
                "field": "notes", "appended": prefix + notes_append,
                "confidence": confidence,
            }])
            return {
                "contact_id": contact_id, "name": name,
                "status": "enriched_light", "confidence": confidence,
                "actions": [{"field": "notes", "appended": prefix + notes_append}],
            }
        else:
            return {
                "contact_id": contact_id, "name": name,
                "status": "error", "error": msg,
            }

    else:
        # 低置信度：跳过，但仍标记为已处理（避免重复调用 AI 判同样结果）
        _mark_enriched(contact_id)
        return {
            "contact_id": contact_id, "name": name,
            "status": "skipped", "confidence": confidence,
            "reason": "confidence too low",
        }


def _mark_enriched(contact_id):
    """标记联系人补全版本（_enrich_version += 1）。"""
    from engine import _load, _save, CONTACTS_FILE
    contacts = _load(CONTACTS_FILE)
    for c in contacts:
        if c["id"] == contact_id:
            c["_enrich_version"] = c.get("_enrich_version", 0) + 1
            _save(CONTACTS_FILE, contacts)
            return True
    return False


def count_from_log():
    """从补全日志中回读统计数据：按置信度区间的人数。"""
    if not ENRICHMENT_LOG.exists():
        return {"high": 0, "medium": 0, "low": 0}
    try:
        with open(ENRICHMENT_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        return {"high": 0, "medium": 0, "low": 0}

    high = medium = low = 0
    for entry in log:
        actions = entry.get("actions", [])
        if not actions:
            continue
        conf = actions[0].get("confidence", 0) if isinstance(actions[0], dict) else 0
        if conf >= 8:
            high += 1
        elif conf >= 5:
            medium += 1
        else:
            low += 1
    return {"high": high, "medium": medium, "low": low}
