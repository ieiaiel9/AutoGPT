"""
RAZ Core - Captcha Agent
Scaffold for 2Captcha / Anti-Captcha automated solving integration.
Used by browser_agent.py when a captcha is detected during web automation.

Configure in config.json / secure storage:
  twocaptcha_api_key: "your_2captcha_key_here"

2Captcha pricing: https://2captcha.com/pay
"""

import os
import time
import json
import urllib.request
import urllib.parse
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from system.config_loader import load_config
    from system.secure_secrets import get_secret
except Exception:
    load_config = dict
    get_secret = lambda k: None


def _get_api_key() -> str:
    """Return the 2Captcha API key from secure storage or config."""
    key = get_secret("twocaptcha_api_key") or ""
    if not key:
        try:
            cfg = load_config()
            key = cfg.get("twocaptcha_api_key", "") or ""
        except Exception:
            pass
    return key.strip()


def solve_image_captcha(image_path: str, timeout: int = 120) -> str | None:
    """
    Submit an image captcha to 2Captcha and return the solved text.
    Returns None on failure.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
    except Exception as e:
        print(f"[CaptchaAgent] Could not read image: {e}")
        return None

    import base64
    b64 = base64.b64encode(image_data).decode()

    # Submit captcha
    submit_url = "https://2captcha.com/in.php"
    payload = urllib.parse.urlencode({
        "key": api_key,
        "method": "base64",
        "body": b64,
        "json": 1,
    }).encode()

    try:
        req = urllib.request.Request(submit_url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[CaptchaAgent] Submit failed: {e}")
        return None

    if data.get("status") != 1:
        print(f"[CaptchaAgent] Submit error: {data.get('error_text', data)}")
        return None

    captcha_id = data["request"]

    # Poll for result
    result_url = f"https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1"
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        try:
            with urllib.request.urlopen(result_url, timeout=10) as resp:
                result = json.loads(resp.read())
        except Exception:
            continue
        if result.get("status") == 1:
            return result["request"]
        if result.get("request") != "CAPCHA_NOT_READY":
            print(f"[CaptchaAgent] Error: {result.get('request')}")
            return None

    print("[CaptchaAgent] Timed out waiting for captcha solution.")
    return None


def solve_recaptcha_v2(site_key: str, page_url: str, timeout: int = 180) -> str | None:
    """
    Solve a reCAPTCHA v2 challenge via 2Captcha.
    Returns the g-recaptcha-response token.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    submit_url = "https://2captcha.com/in.php"
    payload = urllib.parse.urlencode({
        "key": api_key,
        "method": "userrecaptcha",
        "googlekey": site_key,
        "pageurl": page_url,
        "json": 1,
    }).encode()

    try:
        req = urllib.request.Request(submit_url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[CaptchaAgent] reCAPTCHA submit failed: {e}")
        return None

    if data.get("status") != 1:
        print(f"[CaptchaAgent] reCAPTCHA error: {data.get('error_text', data)}")
        return None

    captcha_id = data["request"]
    result_url = f"https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1"

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(7)
        try:
            with urllib.request.urlopen(result_url, timeout=10) as resp:
                result = json.loads(resp.read())
        except Exception:
            continue
        if result.get("status") == 1:
            return result["request"]
        if result.get("request") != "CAPCHA_NOT_READY":
            return None

    return None


def get_balance() -> str:
    """Check 2Captcha account balance."""
    api_key = _get_api_key()
    if not api_key:
        return "No 2Captcha API key configured. Set twocaptcha_api_key in config."
    try:
        url = f"https://2captcha.com/res.php?key={api_key}&action=getbalance&json=1"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("status") == 1:
            return f"2Captcha balance: ${data['request']}"
        return f"Balance check failed: {data.get('error_text', data)}"
    except Exception as e:
        return f"Balance check error: {e}"
