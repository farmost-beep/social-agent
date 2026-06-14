"""Push module - sends messages via existing WeChat bridge."""
import json, subprocess, sys
from pathlib import Path

SCRIPTS_DIR = Path.home() / "claude" / "scripts"
WECHAT_IDS_FILE = Path(__file__).resolve().parent.parent / "data" / "wechat_ids.json"

def _load_wechat_ids():
    """Load WeChat user ID mappings."""
    if not WECHAT_IDS_FILE.exists():
        return {}
    with open(WECHAT_IDS_FILE) as f:
        return json.load(f)

def _save_wechat_ids(mapping):
    """Save WeChat user ID mappings."""
    with open(WECHAT_IDS_FILE, 'w') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

def get_wechat_id(contact_name):
    """Look up a contact's internal WeChat user ID by name."""
    mapping = _load_wechat_ids()
    return mapping.get(contact_name)

def set_wechat_id(contact_name, wxid):
    """Save a contact's internal WeChat user ID."""
    mapping = _load_wechat_ids()
    mapping[contact_name] = wxid
    _save_wechat_ids(mapping)

def push_to_wechat(title, content, to_wxid=None):
    """Send a notification/message to WeChat via the bridge API.

    Args:
        title: Message title
        content: Message text body
        to_wxid: If set, target WeChat user ID (only works through daemon WebSocket)
    """
    script = SCRIPTS_DIR / "wechat_push.py"
    if not script.exists():
        return False, "wechat_push.py not found"
    try:
        args = ["python3", str(script)]
        if to_wxid:
            args += ["--to-wxid", to_wxid]
        args += [title, content]
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "推送超时"
    except Exception as e:
        return False, str(e)

def send_message(contact_name, text, platform="weixin"):
    """Send a draft message preview to the user's WeChat.

    If the contact has a known WeChat user ID, sends directly to them.
    Otherwise, sends a notification to the user (self).
    """
    wxid = get_wechat_id(contact_name)
    if wxid:
        return push_to_wechat("", text, to_wxid=wxid)
    return push_to_wechat("", text)
