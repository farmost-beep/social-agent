"""Push module - sends messages via existing WeChat bridge."""
import subprocess, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"

def push_to_wechat(title, content):
    """Send a notification/message to WeChat via the bridge API."""
    script = SCRIPTS_DIR / "wechat_push.py"
    if not script.exists():
        return False, "wechat_push.py not found"
    try:
        result = subprocess.run(
            ["python3", str(script), title, content],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "推送超时"
    except Exception as e:
        return False, str(e)

def send_message(contact_name, text, platform="weixin"):
    """Send a draft message preview to the user's WeChat."""
    return push_to_wechat("", text)
