"""social-cli push 模块 - 推送 v3.1

核心功能：
1. [首选] wechat-claude-code 桥接发送（iLink API，可靠）
2. [备用] AppleScript 控制 Mac 微信（UI 自动化，半可靠）
3. 节流控制（1 条/5 秒，避免风控）
4. 发送后回写 timeline
5. 检查联系人是否 wxid

用法：
    push_to_wechat("许封", "好久没联系，最近怎么样？")
"""
from __future__ import annotations
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ── 路径 ──

def _get_home_dir():
    """获取 social-agent 主目录（与 engine.py 同逻辑）"""
    env = os.environ.get("SOCIAL_AGENT_HOME")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    pkg_root = Path(__file__).resolve().parent.parent
    if (pkg_root / "config").is_dir():
        return pkg_root
    # PyPI 安装：config/ 在 src/ 内
    import importlib.util
    spec = importlib.util.find_spec("src")
    if spec and spec.origin:
        src_dir = Path(spec.origin).resolve().parent
        if (src_dir / "config").is_dir():
            return src_dir
    user_dir = Path.home() / ".social-agent"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

_HOME = _get_home_dir()
APPLESCRIPT = _HOME / "bin" / "send_to_wechat.applescript"
DATA_DIR = _HOME / "data"
CONTACTS_FILE = DATA_DIR / "contacts.json"
TIMELINE_FILE = DATA_DIR / "timeline.json"

# ── 节流控制 ──

_last_send_time: float = 0.0
_MIN_INTERVAL = 5.0  # 最少 5 秒间隔（微信风控规避）


def _throttle():
    """节流：保证两次发送间隔 >= _MIN_INTERVAL 秒"""
    global _last_send_time
    elapsed = time.time() - _last_send_time
    if elapsed < _MIN_INTERVAL:
        wait = _MIN_INTERVAL - elapsed
        time.sleep(wait)
    _last_send_time = time.time()


# ── 桥接路径 ──

def _push_via_bridge(contact_name: str, message: str) -> Optional[dict]:
    """通过 wechat-claude-code 桥接发送（优先路径）

    桥接守护进程通过 iLink API 发送，比 AppleScript 可靠 100 倍。
    需要联系人配置了 wxid。
    """
    # 1. 查找联系人 wxid
    wid = find_contact_weixin_id(contact_name)
    if not wid:
        return None  # 无 wxid，回退 AppleScript

    # 2. 调用 send_via_bridge.mjs
    bridge_script = _HOME / "scripts" / "send_via_bridge.mjs"
    if not bridge_script.exists():
        # 也试试 ~/claude/scripts/（wechat-claude-code 桥接默认位置）
        bridge_script = Path.home() / "claude" / "scripts" / "send_via_bridge.mjs"
    if not bridge_script.exists():
        return None

    try:
        result = subprocess.run(
            ["node", str(bridge_script), wid, message[:500]],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and "成功" in result.stdout:
            _write_timeline(contact_name, message)
            return {"success": True, "output": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr.strip() or "桥接发送失败"}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {"success": False, "error": str(e)}


# ── AppleScript 备用路径 ──

def _push_via_applescript(contact_name: str, message: str) -> dict:
    """通过 AppleScript 控制 Mac 微信（备用，半可靠）"""
    if not APPLESCRIPT.exists():
        return {"success": False, "error": f"AppleScript 文件不存在: {APPLESCRIPT}"}

    safe_contact = contact_name.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')
    cmd = ["osascript", str(APPLESCRIPT), safe_contact, safe_message[:500]]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            _write_timeline(contact_name, message)
            return {"success": True, "output": result.stdout.strip()}
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            return {"success": False, "error": error_msg}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "osascript 超时（30s）"}
    except FileNotFoundError:
        return {"success": False, "error": "osascript 命令不存在"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 统一入口 ──

def push_to_wechat(contact_name: str, message: str) -> dict:
    """发送消息到微信（统一入口）

    优先级：
    1. 桥接（有 wxid 时）— 最可靠
    2. AppleScript（无 wxid 时）— 半可靠

    Args:
        contact_name: 联系人名称
        message: 消息文本

    Returns:
        {"success": True} 或 {"success": False, "error": "..."}
    """
    _throttle()

    # 路径 1：桥接（优先）
    bridge_result = _push_via_bridge(contact_name, message)
    if bridge_result is not None:
        return bridge_result

    # 路径 2：AppleScript（备用）
    return _push_via_applescript(contact_name, message)


# ── 联系人查找 ──

def find_contact_weixin_id(name: str) -> Optional[str]:
    """从 contacts.json 查找联系人的微信 ID

    搜索优先级：name 精确匹配 → name 模糊匹配 → weixin_id 匹配
    """
    if not CONTACTS_FILE.exists():
        return None
    try:
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            contacts = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(contacts, list):
        return None

    # 1. 精确匹配 name
    for c in contacts:
        if c.get("name", "").strip() == name:
            wid = c.get("platforms", {}).get("weixin", "") or c.get("weixin_id", "")
            if wid:
                return wid

    # 2. 模糊匹配（name 含关键词）
    for c in contacts:
        if name in c.get("name", ""):
            wid = c.get("platforms", {}).get("weixin", "") or c.get("weixin_id", "")
            if wid:
                return wid

    return None


# ── 时间线回写 ──

def _write_timeline(contact_name: str, message: str):
    """发送成功后，把"已发送消息"写入 timeline"""
    if not TIMELINE_FILE.exists():
        return

    try:
        with open(TIMELINE_FILE, "r", encoding="utf-8") as f:
            timeline = json.load(f)
    except (json.JSONDecodeError, OSError):
        timeline = []

    from datetime import date
    entry = {
        "id": f"push-{int(time.time())}",
        "date": date.today().isoformat(),
        "contact": contact_name,
        "type": "message",
        "summary": f"[AI推送] {message[:60]}",
        "source": "social-cli-push",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    timeline.append(entry)
    with open(TIMELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)


# ── 健康检查 ──

def check_available() -> dict:
    """验证 AppleScript 推送是否可用"""
    checks = []

    # 1. osascript 命令存在
    if subprocess.run(["which", "osascript"], capture_output=True).returncode == 0:
        checks.append({"check": "osascript 命令", "status": "✅"})
    else:
        checks.append({"check": "osascript 命令", "status": "❌"})

    # 2. AppleScript 文件存在
    if APPLESCRIPT.exists():
        checks.append({"check": "send_to_wechat.applescript", "status": "✅"})
    else:
        checks.append({"check": "send_to_wechat.applescript", "status": "❌"})

    # 3. contacts.json 存在
    if CONTACTS_FILE.exists():
        try:
            with open(CONTACTS_FILE) as f:
                contacts = json.load(f)
            checks.append({"check": f"contacts.json ({len(contacts)} 联系人)", "status": "✅"})
        except:
            checks.append({"check": "contacts.json", "status": "❌ 解析失败"})
    else:
        checks.append({"check": "contacts.json", "status": "❌ 不存在"})

    # 4. WeChat 进程是否存在
    try:
        r = subprocess.run(
            ["pgrep", "-x", "WeChat"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            checks.append({"check": "微信进程运行中", "status": "✅"})
        else:
            checks.append({"check": "微信进程运行中", "status": "❌ 未运行"})
    except:
        checks.append({"check": "微信进程运行中", "status": "⚠️ 无法检测"})

    return {"available": all(c["status"] == "✅" for c in checks), "checks": checks}