"""
RAZ Core - Browser Agent
Reliable browser automation with recovery strategies.

Capabilities:
- scan_page(url): inspect inputs/buttons/iframes before acting
- browse_and_fill(url, actions): generic browser automation with iframe fallback
- proton_signup(username, password): Proton signup with iframe-aware username fill
- send_proton_email(...): login and send email with compose/send fallbacks
- proton_full_flow(to_addr): generate creds, signup, login, send in one flow
"""

import os
import re
import sys
import random
import string
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", "")
PROTON_PROFILE_DIR = (
    os.path.join(_LOCAL_APPDATA, "RAZ-Core", "browser_profiles", "proton")
    if _LOCAL_APPDATA
    else os.path.join(BASE_DIR, "memory", "browser_profiles", "proton")
)
BROWSER_PROFILES_DIR = (
    os.path.join(_LOCAL_APPDATA, "RAZ-Core", "browser_profiles")
    if _LOCAL_APPDATA
    else os.path.join(BASE_DIR, "memory", "browser_profiles")
)


def _default_headless() -> bool:
    """Headless by default so background tests do not interrupt Ryan's active work."""
    val = os.environ.get("RAZ_BROWSER_HEADLESS", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


def _ensure_playwright():
    """Install playwright + chromium if missing."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True, None
    except ImportError:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "playwright"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.check_call(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, None
        except Exception as e:
            return False, str(e)


def _shot(page, name: str) -> str:
    d = os.path.join(BASE_DIR, "assets", "screenshots")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    try:
        page.screenshot(path=path)
    except Exception:
        pass
    return path


def _selector_variants(sel: str) -> list:
    variants = []
    if sel.startswith("#"):
        k = sel[1:]
        variants += [
            f"input[id='{k}']",
            f"input[name='{k}']",
            f"input[placeholder*='{k}' i]",
            f"input[autocomplete*='{k}' i]",
        ]
    if "username" in sel.lower() or "email" in sel.lower():
        variants += [
            "input[id='username']",
            "input[name='username']",
            "input[id='email']",
            "input[name='email']",
            "input[autocomplete='username']",
            "input[type='text']",
            "input[type='email']",
        ]
    if "password" in sel.lower():
        variants += ["input[type='password']"]
    return variants


def _fill_in_any_frame(page, selectors: list, value: str, log: list, label: str) -> bool:
    def _try_fill_with_fallback(ctx_obj, selector: str, where: str) -> bool:
        try:
            loc = ctx_obj.locator(selector).first
            if loc.count() == 0:
                return False

            # Try native fill first.
            try:
                loc.fill(value, timeout=3000)
                log.append(f"Filled {label} in {where} via {selector}")
                return True
            except Exception:
                pass

            # Fallback for React/Discord-style inputs.
            try:
                loc.click(timeout=2000)
            except Exception:
                return False

            try:
                ctx_obj.keyboard.press("Control+A")
            except Exception:
                pass

            try:
                ctx_obj.keyboard.insert_text(value)
                log.append(f"Typed {label} in {where} via {selector}")
                return True
            except Exception:
                pass

            # Last-resort JS assignment with events.
            try:
                ok = ctx_obj.evaluate(
                    """({sel, val}) => {
                        const el = document.querySelector(sel);
                        if (!el) return false;
                        el.focus();
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }""",
                    {"sel": selector, "val": value},
                )
                if ok:
                    log.append(f"JS-filled {label} in {where} via {selector}")
                    return True
            except Exception:
                pass

            return False
        except Exception:
            return False

    # Main frame first
    for s in selectors:
        for try_s in [s] + _selector_variants(s):
            if _try_fill_with_fallback(page, try_s, "main frame"):
                return True

    # Then all child frames (critical for Proton username field)
    for fr in page.frames:
        if fr == page.main_frame:
            continue
        for s in selectors:
            for try_s in [s] + _selector_variants(s):
                if _try_fill_with_fallback(fr, try_s, f"iframe ({fr.url[:80]})"):
                    return True

    log.append(f"WARN: Could not fill {label} in any frame")
    return False


def _composer_ready(page) -> bool:
    selectors = "[data-testid='composer:to'], input[placeholder='To'], input[aria-label*='To' i]"
    try:
        if page.locator(selectors).count() > 0:
            return True
    except Exception:
        pass
    for fr in page.frames:
        if fr == page.main_frame:
            continue
        try:
            if fr.locator(selectors).count() > 0:
                return True
        except Exception:
            pass
    return False


def _mailbox_ready(page) -> bool:
    try:
        url = page.url.lower()
    except Exception:
        url = ""

    # Must not be on Proton login/selector states.
    if "/login" in url or "#selector=" in url:
        return False

    # Real mailbox pages usually include /u/<n>/... or inbox/mail views.
    if "/u/" in url or "/inbox" in url or ("mail.proton.me" in url and "/mail" in url):
        return True

    # UI fallback: if compose button exists, mailbox is usable.
    try:
        if page.locator("[data-testid='sidebar:compose'], button[data-testid*='compose']").count() > 0:
            return True
    except Exception:
        pass

    return False


def _fill_message_body_in_context(ctx_obj, body_text: str) -> bool:
    """Try to fill Proton compose body in a page/frame context."""
    selectors = [
        "[data-testid='composer:body'] [contenteditable='true']",
        "[data-testid='composer:body']",
        "div[role='textbox'][contenteditable='true']",
        "div[role='textbox']",
        "div[aria-label*='message' i][contenteditable='true']",
        "div[data-testid*='editor'][contenteditable='true']",
        "[contenteditable='true']",
        ".rooster",
        ".ql-editor",
    ]

    for sel in selectors:
        try:
            loc = ctx_obj.locator(sel)
            count = loc.count()
            for i in range(count):
                cand = loc.nth(i)
                try:
                    if not cand.is_visible():
                        continue
                except Exception:
                    continue

                try:
                    cand.click(timeout=2000)
                except Exception:
                    continue

                # Replace existing draft body content predictably.
                try:
                    ctx_obj.keyboard.press("Control+A")
                except Exception:
                    pass
                try:
                    ctx_obj.keyboard.insert_text(body_text)
                    return True
                except Exception:
                    pass
        except Exception:
            pass

    # Last-resort JS: fill first visible editable in this context.
    try:
        ok = ctx_obj.evaluate(
            """(text) => {
                const candidates = Array.from(document.querySelectorAll(
                  "[data-testid='composer:body'] [contenteditable='true'], " +
                  "div[role='textbox'][contenteditable='true'], " +
                  "[contenteditable='true']"
                ));
                const visible = candidates.find(el => {
                  const r = el.getBoundingClientRect();
                  return r.width > 80 && r.height > 40 && el.offsetParent !== null;
                });
                if (!visible) return false;
                visible.focus();
                visible.innerHTML = "";
                visible.textContent = text;
                visible.dispatchEvent(new Event('input', { bubbles: true }));
                visible.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""",
            body_text,
        )
        return bool(ok)
    except Exception:
        return False


def _resolve_proton_account_selector(page, login_user: str, log: list) -> bool:
    """If Proton lands on account selector/login bridge, pick the matching account tile."""
    url = ""
    try:
        url = page.url.lower()
    except Exception:
        pass
    if ("/login" not in url) and ("selector=" not in url):
        return False

    user_local = (login_user or "").split("@")[0]
    candidates = [login_user, user_local, "Continue", "Open"]
    for label in candidates:
        if not label:
            continue
        for act in [
            lambda: page.get_by_text(label, exact=False).first.click(timeout=2500),
            lambda: page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first.click(timeout=2500),
            lambda: page.get_by_role("link", name=re.compile(re.escape(label), re.I)).first.click(timeout=2500),
        ]:
            try:
                act()
                page.wait_for_timeout(1200)
                log.append(f"Clicked selector item: {label}")
                return True
            except Exception:
                pass
    return False


def _wait_for_manual_state(page, seconds: int, predicate, log: list, wait_msg: str, done_msg: str) -> bool:
    log.append(wait_msg)
    for _ in range(seconds):
        try:
            if predicate():
                log.append(done_msg)
                return True
        except Exception:
            pass
        page.wait_for_timeout(1000)
    return False


def _hold_visible_browser(page, log: list, reason: str, seconds: int = 180):
    log.append(f"Holding browser open for {seconds}s: {reason}")
    try:
        _shot(page, "proton_hold_state.png")
    except Exception:
        pass
    try:
        page.wait_for_timeout(seconds * 1000)
    except Exception:
        pass


def _get_or_create_page(context):
    pages = context.pages
    if pages:
        return pages[0]
    return context.new_page()


def _launch_visible_context(pw, user_data_dir: str, slow_mo: int = 110):
    profile_dirs = [
        user_data_dir,
        os.path.join(BASE_DIR, "memory", "browser_profiles", "proton_fallback"),
    ]
    launch_attempts = [
        {"channel": "msedge", "label": "Microsoft Edge"},
        {"channel": "chrome", "label": "Google Chrome"},
        {"channel": None, "label": "Playwright Chromium"},
    ]
    errors = []
    for pdir in profile_dirs:
        os.makedirs(pdir, exist_ok=True)
        for attempt in launch_attempts:
            kwargs = {
                "user_data_dir": pdir,
                "headless": False,
                "slow_mo": slow_mo,
                "viewport": {"width": 1280, "height": 900},
            }
            if attempt["channel"]:
                kwargs["channel"] = attempt["channel"]
            try:
                ctx = pw.chromium.launch_persistent_context(**kwargs)
                return ctx, f"{attempt['label']} [{pdir}]"
            except Exception as e:
                errors.append(f"{attempt['label']} [{pdir}]: {e}")
    raise RuntimeError("Could not launch any supported browser: " + " | ".join(errors))


def scan_page(url: str) -> dict:
    ok, err = _ensure_playwright()
    if not ok:
        return {"ok": False, "error": f"Playwright not available: {err}"}

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=_default_headless())
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2500)

            title = page.title()
            final_url = page.url
            shot = _shot(page, "scan_page.png")

            iframes = []
            for fr in page.frames:
                if fr != page.main_frame:
                    iframes.append({"src": fr.url[:160], "name": fr.name})

            inputs = page.evaluate(
                """() => Array.from(document.querySelectorAll('input, textarea, select')).map(el => ({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    autocomplete: el.autocomplete || '',
                    in_iframe: false
                }))"""
            )

            for fr in page.frames:
                if fr == page.main_frame:
                    continue
                try:
                    fr_inputs = fr.evaluate(
                        """() => Array.from(document.querySelectorAll('input, textarea, select')).map(el => ({
                            tag: el.tagName,
                            type: el.type || '',
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            autocomplete: el.autocomplete || '',
                            in_iframe: true
                        }))"""
                    )
                    inputs.extend(fr_inputs)
                except Exception:
                    pass

            buttons = page.evaluate(
                """() => Array.from(document.querySelectorAll('button, input[type=submit], a[role=button]')).map(el => ({
                    text: (el.innerText || el.value || '').trim().slice(0, 80),
                    id: el.id || '',
                    type: el.type || ''
                }))"""
            )

            visible_text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 2000) : ''")
            browser.close()
            return {
                "ok": True,
                "title": title,
                "url": final_url,
                "inputs": inputs,
                "buttons": buttons[:40],
                "iframes": iframes,
                "visible_text": visible_text,
                "screenshot": shot,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def browse_and_fill(url: str, actions: list, headless: bool = False, keep_open: bool = False, profile_name: str = "") -> dict:
    ok, err = _ensure_playwright()
    if not ok:
        return {"ok": False, "log": [], "error": f"Playwright install failed: {err}", "screenshot": None}

    log = []
    shot_path = None

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = None
            context_label = "ephemeral"

            if keep_open or profile_name:
                p_name = (profile_name or "default").strip().lower() or "default"
                user_data_dir = os.path.join(BROWSER_PROFILES_DIR, p_name)
                try:
                    ctx, context_label = _launch_visible_context(pw, user_data_dir, slow_mo=80)
                except Exception:
                    # Fallback: non-persistent context if profile launch fails.
                    launch_kwargs = {"headless": headless}
                    if not headless:
                        launch_kwargs["channel"] = "msedge"
                    try:
                        browser = pw.chromium.launch(**launch_kwargs)
                    except Exception:
                        browser = pw.chromium.launch(headless=headless)
                    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            else:
                launch_kwargs = {"headless": headless}
                if not headless:
                    launch_kwargs["channel"] = "msedge"
                try:
                    browser = pw.chromium.launch(**launch_kwargs)
                except Exception:
                    browser = pw.chromium.launch(headless=headless)
                ctx = browser.new_context(viewport={"width": 1280, "height": 900})

            page = _get_or_create_page(ctx)
            log.append(f"Browser session: {context_label}")

            log.append(f"Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            log.append(f"Page loaded: {page.title()}")

            for action in actions:
                t = action.get("type", "")

                if t == "wait":
                    ms = int(action.get("ms", 1000))
                    page.wait_for_timeout(ms)
                    log.append(f"Waited {ms}ms")

                elif t == "wait_url":
                    contains = action.get("contains", "")
                    try:
                        page.wait_for_url(f"**{contains}**", timeout=15000)
                        log.append(f"URL contains '{contains}'")
                    except Exception:
                        log.append(f"WARN: URL did not contain '{contains}', current={page.url[:100]}")

                elif t == "screenshot":
                    shot_path = _shot(page, "browser_shot.png")
                    log.append(f"Screenshot saved: {shot_path}")

                elif t in ("fill", "fill_frame"):
                    sel = action.get("selector", "")
                    val = action.get("value", "")
                    if not sel:
                        log.append("WARN: fill missing selector")
                        continue
                    if t == "fill_frame":
                        filled = _fill_in_any_frame(page, [sel], val, log, sel)
                    else:
                        filled = _fill_in_any_frame(page, [sel], val, log, sel)
                    if not filled:
                        log.append(f"WARN: Could not fill '{sel}'")

                elif t == "click":
                    sel = action.get("selector", "")
                    clicked = False
                    if not sel:
                        log.append("WARN: click missing selector")
                        continue
                    try:
                        page.locator(sel).first.click(timeout=6000)
                        clicked = True
                        log.append(f"Clicked '{sel}'")
                    except Exception:
                        pass
                    if not clicked:
                        try:
                            page.get_by_role("button", name=re.compile(sel, re.I)).first.click(timeout=5000)
                            clicked = True
                            log.append(f"Clicked button text match '{sel}'")
                        except Exception:
                            pass
                    if not clicked:
                        try:
                            page.get_by_text(sel).first.click(timeout=5000)
                            clicked = True
                            log.append(f"Clicked text '{sel}'")
                        except Exception:
                            log.append(f"WARN: Could not click '{sel}'")
                    page.wait_for_timeout(400)

                elif t == "keyboard":
                    key = action.get("key", "Enter")
                    page.keyboard.press(key)
                    log.append(f"Key press: {key}")

                elif t == "get_text":
                    sel = action.get("selector", "")
                    try:
                        text = page.locator(sel).first.text_content(timeout=5000)
                        log.append(f"TEXT[{sel}]: {text}")
                    except Exception:
                        log.append(f"WARN: Could not get text from '{sel}'")

                elif t == "select":
                    sel = action.get("selector", "")
                    val = action.get("value", "")
                    try:
                        page.locator(sel).select_option(val, timeout=5000)
                        log.append(f"Selected '{val}' in '{sel}'")
                    except Exception as e:
                        log.append(f"WARN: Could not select in '{sel}': {e}")

            shot_path = _shot(page, "browser_final.png")
            log.append(f"Final screenshot: {shot_path}")
            if keep_open:
                log.append("Keeping browser open for persistent session.")
                _hold_visible_browser(page, log, "persistent keep_open requested", seconds=300)
            if browser:
                browser.close()
            else:
                ctx.close()
            return {"ok": True, "log": log, "error": None, "screenshot": shot_path}
    except Exception as e:
        return {"ok": False, "log": log, "error": str(e), "screenshot": shot_path}


def proton_signup(username: str, password: str, display_name: str = "") -> dict:
    ok, err = _ensure_playwright()
    if not ok:
        return {"ok": False, "log": [], "error": f"Playwright not available: {err}"}

    log = []
    creds = {"username": username, "password": password, "email": f"{username}@proton.me"}

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=_default_headless(), slow_mo=90)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()

            page.goto("https://account.proton.me/signup", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)
            log.append(f"Page loaded: {page.title()}")
            _shot(page, "proton_signup_01.png")

            # Select free plan if needed.
            for act in [
                lambda: page.get_by_role("button", name=re.compile(r"free", re.I)).first.click(timeout=4000),
                lambda: page.get_by_text("Use your current email instead").first.click(timeout=3000),
            ]:
                try:
                    act()
                    page.wait_for_timeout(1200)
                    break
                except Exception:
                    pass

            # Username may be in iframe.
            _fill_in_any_frame(
                page,
                ["#username", "#email", "input[name='username']", "input[autocomplete='username']"],
                username,
                log,
                "username",
            )

            # Fallback strategy: force-set all visible username/email-like inputs
            # and dispatch input/change events in case framework blocks .fill().
            try:
                page.evaluate(
                    """(val) => {
                        const sels = [
                            'input#username',
                            'input#email',
                            "input[name='username']",
                            "input[name='email']",
                            "input[autocomplete='username']",
                            "input[type='text']",
                            "input[type='email']"
                        ];
                        for (const s of sels) {
                            document.querySelectorAll(s).forEach(el => {
                                if (el && el.offsetParent !== null) {
                                    el.value = val;
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            });
                        }
                    }""",
                    username,
                )
                log.append("Applied JS fallback fill for username fields in main frame")
            except Exception:
                pass

            # Fill password and confirm where available.
            pwd_filled = False
            try:
                pwd_locs = page.locator("input[type='password']")
                count = pwd_locs.count()
                if count > 0:
                    pwd_locs.nth(0).fill(password, timeout=4000)
                    pwd_filled = True
                    log.append("Filled password[0]")
                if count > 1:
                    pwd_locs.nth(1).fill(password, timeout=4000)
                    log.append("Filled password[1] (confirm)")
                if count == 1:
                    # Some Proton variants reveal confirm field after first input.
                    page.wait_for_timeout(900)
                    pwd_locs2 = page.locator("input[type='password']")
                    count2 = pwd_locs2.count()
                    if count2 > 1:
                        pwd_locs2.nth(1).fill(password, timeout=4000)
                        log.append("Filled password[1] after reveal")
            except Exception as e:
                log.append(f"WARN: Password fill issue: {e}")

            if not pwd_filled:
                browser.close()
                return {"ok": False, "log": log, "error": "Could not fill password field", "credentials": creds}

            _shot(page, "proton_signup_02_filled.png")

            # Submit
            submitted = False
            for act in [
                lambda: page.get_by_role("button", name=re.compile(r"start using|create|continue|next", re.I)).first.click(timeout=7000),
                lambda: page.locator("button[type='submit']").first.click(timeout=7000),
            ]:
                try:
                    act()
                    submitted = True
                    log.append("Clicked submit")
                    break
                except Exception:
                    pass

            if not submitted:
                _shot(page, "proton_signup_submit_fail.png")
                browser.close()
                return {"ok": False, "log": log, "error": "Could not find submit button", "credentials": creds}

            page.wait_for_timeout(6000)
            _shot(page, "proton_signup_03_after_submit.png")
            url = page.url
            log.append(f"Post-submit URL: {url}")

            text = ""
            try:
                text = page.evaluate("document.body.innerText").lower()
            except Exception:
                pass

            # Collect inline form errors for debugging/recovery.
            try:
                errs = page.evaluate(
                    """() => Array.from(document.querySelectorAll('[role="alert"], .error, [class*="error"], [data-testid*="error"]'))
                           .map(e => (e.innerText || '').trim())
                           .filter(Boolean)
                           .slice(0, 8)"""
                )
                if errs:
                    for e in errs:
                        log.append(f"FORM ERROR: {e[:180]}")
            except Exception:
                pass

            # Log username field values to verify what actually got entered.
            try:
                vals = page.evaluate(
                    """() => Array.from(document.querySelectorAll('input#username,input#email,input[name="username"],input[name="email"]'))
                           .map(e => ({id:e.id||'',name:e.name||'',value:e.value||'',visible:e.offsetParent!==null}))"""
                )
                if vals:
                    log.append(f"Username field values (main): {vals}")
            except Exception:
                pass

            if "captcha" in text or "verify" in text and "human" in text:
                browser.close()
                return {"ok": False, "log": log, "error": "Captcha or human verification required", "credentials": creds}

            if "already" in text or "taken" in text or "unavailable" in text:
                browser.close()
                return {"ok": False, "log": log, "error": "Username unavailable", "credentials": creds}

            if "signup" in url.lower() and not ("mail" in url.lower() or "onboarding" in url.lower()):
                browser.close()
                return {"ok": False, "log": log, "error": "Still on signup page, account not confirmed", "credentials": creds}

            browser.close()
            return {"ok": True, "log": log, "error": None, "credentials": creds}
    except Exception as e:
        return {"ok": False, "log": log, "error": str(e), "credentials": creds}


def send_proton_email(username: str, password: str, to: str, subject: str, body: str) -> dict:
    ok, err = _ensure_playwright()
    if not ok:
        return {"ok": False, "log": [], "error": f"Playwright not available: {err}"}

    log = []
    login_user = username if "@" in (username or "") else f"{username}@proton.me"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            # Persist the Proton session so Ryan does not have to re-login every run.
            ctx, browser_label = _launch_visible_context(pw, PROTON_PROFILE_DIR, slow_mo=110)
            page = _get_or_create_page(ctx)
            log.append(f"Browser: {browser_label}")

            page.goto("https://mail.proton.me/u/0/inbox", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2500)
            log.append(f"Page: {page.title()}")
            _shot(page, "proton_login_01.png")

            # If session is not active, try one direct fill in Edge, then fall back to manual login.
            on_login = False
            try:
                on_login = page.locator("input[type='password']").count() > 0
            except Exception:
                pass

            if on_login:
                _fill_in_any_frame(
                    page,
                    ["#username", "input[name='username']", "input[autocomplete='username']", "input[type='email']"],
                    login_user,
                    log,
                    "username",
                )
                page.wait_for_timeout(300)
                try:
                    pwd_loc = page.locator("input[type='password']").first
                    if pwd_loc.count() > 0:
                        pwd_loc.fill(password, timeout=5000)
                        log.append("Filled password")
                except Exception as e:
                    log.append(f"WARN: Could not fill password automatically: {e}")

                for act in [
                    lambda: page.get_by_role("button", name=re.compile(r"sign in|log in", re.I)).first.click(timeout=4000),
                    lambda: page.locator("button[type='submit']").first.click(timeout=4000),
                ]:
                    try:
                        act()
                        log.append("Clicked sign in")
                        page.wait_for_timeout(1200)
                        break
                    except Exception:
                        pass

                _wait_for_manual_state(
                    page,
                    300,
                    lambda: _mailbox_ready(page) and page.locator("input[type='password']").count() == 0,
                    log,
                    "Proton login required. Complete it manually in the open browser window; waiting up to 300s...",
                    "Persistent Proton session ready",
                )

            if not _mailbox_ready(page):
                _resolve_proton_account_selector(page, login_user, log)
                _wait_for_manual_state(
                    page,
                    120,
                    lambda: _mailbox_ready(page),
                    log,
                    "Resolving Proton account selector/login bridge...",
                    "Mailbox ready after selector",
                )

            if not _mailbox_ready(page):
                try:
                    page.goto("https://mail.proton.me/u/0/inbox", wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(2500)
                    log.append("Loaded Proton inbox from persistent profile")
                except Exception:
                    pass

            _shot(page, "proton_login_02.png")
            log.append(f"URL after login: {page.url}")

            # If the sign-in form is still visible, auth did not complete.
            try:
                still_login = (
                    page.locator("input[type='password']").count() > 0
                    and page.locator("button[type='submit'], button:has-text('Sign in')").count() > 0
                )
            except Exception:
                still_login = False
            if still_login:
                login_text = ""
                try:
                    login_text = page.evaluate("document.body.innerText").lower()
                except Exception:
                    pass
                if "incorrect" in login_text or "invalid" in login_text or "wrong" in login_text:
                    _shot(page, "proton_login_invalid_credentials.png")
                    _hold_visible_browser(page, log, "invalid credentials screen", seconds=120)
                    ctx.close()
                    return {"ok": False, "log": log, "error": "Incorrect Proton username/password"}

                # Keep the visible window up for manual completion (2FA/challenge/session prompts).
                _wait_for_manual_state(
                    page,
                    180,
                    lambda: (
                        not (
                            page.locator("input[type='password']").count() > 0
                            and page.locator("button[type='submit'], button:has-text('Sign in')").count() > 0
                        ) and ("mail.proton.me" in page.url.lower() or "/mail" in page.url.lower())
                    ),
                    log,
                    "Login needs manual completion; waiting up to 180s for inbox...",
                    "Manual login complete; continuing automation",
                )

                try:
                    still_login = (
                        page.locator("input[type='password']").count() > 0
                        and page.locator("button[type='submit'], button:has-text('Sign in')").count() > 0
                    )
                except Exception:
                    still_login = False

            if still_login:
                _shot(page, "proton_login_still_signin.png")
                _hold_visible_browser(page, log, "login screen still open", seconds=180)
                ctx.close()
                return {"ok": False, "log": log, "error": "Still on sign-in page after login attempt (check credentials or session challenge)"}

            if (not _mailbox_ready(page)) or "login" in page.url.lower() or "signin" in page.url.lower():
                body_txt = ""
                try:
                    body_txt = page.evaluate("document.body.innerText").lower()
                except Exception:
                    pass
                if "captcha" in body_txt:
                    _hold_visible_browser(page, log, "captcha or challenge screen", seconds=180)
                    ctx.close()
                    return {"ok": False, "log": log, "error": "Login blocked by captcha"}
                if "incorrect" in body_txt or "invalid" in body_txt:
                    _hold_visible_browser(page, log, "incorrect credential screen", seconds=120)
                    ctx.close()
                    return {"ok": False, "log": log, "error": "Incorrect username or password"}
                _hold_visible_browser(page, log, "login did not complete", seconds=180)
                ctx.close()
                return {"ok": False, "log": log, "error": "Login did not complete"}

            compose_open = False
            for act in [
                lambda: page.locator("[data-testid='sidebar:compose']").click(timeout=9000),
                lambda: page.locator("button[data-testid*='compose']").first.click(timeout=9000),
                lambda: page.get_by_role("button", name=re.compile(r"new message|compose", re.I)).first.click(timeout=9000),
                lambda: page.keyboard.press("N"),
                lambda: page.keyboard.press("c"),
            ]:
                try:
                    act()
                    page.wait_for_timeout(2000)
                    if _composer_ready(page):
                        compose_open = True
                        log.append("Composer opened")
                        break
                except Exception:
                    pass

            if not compose_open:
                _shot(page, "proton_compose_fail.png")
                compose_open = _wait_for_manual_state(
                    page,
                    180,
                    lambda: _composer_ready(page),
                    log,
                    "Composer not detected; waiting up to 180s for manual open...",
                    "Composer opened manually; resuming automation",
                )
                if not compose_open:
                    _hold_visible_browser(page, log, "compose did not open", seconds=180)
                    ctx.close()
                    return {"ok": False, "log": log, "error": "Could not open composer"}

            # To
            to_ok = False
            for s in ["[data-testid='composer:to']", "input[placeholder='To']", "input[id*='to']"]:
                try:
                    page.locator(s).first.fill(to, timeout=5000)
                    page.keyboard.press("Enter")
                    to_ok = True
                    log.append(f"Filled To: {to}")
                    break
                except Exception:
                    pass
            if not to_ok:
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    for s in ["[data-testid='composer:to']", "input[placeholder='To']", "input[id*='to']", "input[aria-label*='To' i]"]:
                        try:
                            fr.locator(s).first.fill(to, timeout=3000)
                            page.keyboard.press("Enter")
                            to_ok = True
                            log.append(f"Filled To in iframe: {to}")
                            break
                        except Exception:
                            pass
                    if to_ok:
                        break
            if not to_ok:
                _hold_visible_browser(page, log, "recipient field not found", seconds=180)
                ctx.close()
                return {"ok": False, "log": log, "error": "Could not fill recipient field"}

            # Subject
            sub_ok = False
            for s in ["[data-testid='composer:subject']", "input[placeholder='Subject']", "input[id*='subject']"]:
                try:
                    page.locator(s).first.fill(subject, timeout=5000)
                    sub_ok = True
                    log.append("Filled subject")
                    break
                except Exception:
                    pass
            if not sub_ok:
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    for s in ["[data-testid='composer:subject']", "input[placeholder='Subject']", "input[id*='subject']", "input[aria-label*='Subject' i]"]:
                        try:
                            fr.locator(s).first.fill(subject, timeout=3000)
                            sub_ok = True
                            log.append("Filled subject in iframe")
                            break
                        except Exception:
                            pass
                    if sub_ok:
                        break
            if not sub_ok:
                _hold_visible_browser(page, log, "subject field not found", seconds=180)
                ctx.close()
                return {"ok": False, "log": log, "error": "Could not fill subject"}

            # Body
            body_ok = False
            try:
                body_ok = _fill_message_body_in_context(page, body)
                if body_ok:
                    log.append("Filled body")
            except Exception:
                body_ok = False
            if not body_ok:
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    try:
                        if _fill_message_body_in_context(fr, body):
                            body_ok = True
                            log.append("Filled body in iframe")
                    except Exception:
                        pass
                    if body_ok:
                        break
            if not body_ok:
                _hold_visible_browser(page, log, "body editor not found", seconds=180)
                ctx.close()
                return {"ok": False, "log": log, "error": "Could not fill body"}

            _shot(page, "proton_before_send.png")

            sent = False
            for act in [
                lambda: page.locator("[data-testid='composer:send-button']").click(timeout=7000),
                lambda: page.get_by_role("button", name=re.compile(r"^send$", re.I)).first.click(timeout=7000),
                lambda: page.locator("button[title='Send']").first.click(timeout=7000),
            ]:
                try:
                    act()
                    sent = True
                    log.append("Clicked Send")
                    break
                except Exception:
                    pass

            if not sent:
                _shot(page, "proton_send_fail.png")
                _hold_visible_browser(page, log, "send button not clicked", seconds=180)
                ctx.close()
                return {"ok": False, "log": log, "error": "Could not click send"}

            page.wait_for_timeout(4000)
            _shot(page, "proton_after_send.png")

            confirm_text = ""
            try:
                confirm_text = page.evaluate("document.body.innerText").lower()
            except Exception:
                pass

            if "sent" in confirm_text or page.locator("[data-testid='composer:to'], input[placeholder='To']").count() == 0:
                _hold_visible_browser(page, log, "email sent confirmation", seconds=30)
                ctx.close()
                return {"ok": True, "log": log + ["Confirmed send"], "error": None}

            _hold_visible_browser(page, log, "send not confirmed", seconds=180)
            ctx.close()
            return {"ok": False, "log": log, "error": "Send not confirmed"}

    except Exception as e:
        return {"ok": False, "log": log, "error": str(e)}


def proton_full_flow(to_addr: str) -> dict:
    log = []
    last_error = "Unknown"
    last_creds = None

    for attempt in range(1, 4):
        username = (
            random.choice(["core", "nano", "iron", "swift", "prime"]) 
            + random.choice(["node", "wolf", "pulse", "arc"]) 
            + str(random.randint(100, 999))
        )
        password = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(string.ascii_letters + string.digits, k=9))
        )
        creds = {"username": username, "password": password, "email": f"{username}@proton.me"}
        last_creds = creds
        log.append(f"Attempt {attempt}/3 generated: {creds['email']} / {password}")

        signup = proton_signup(username, password)
        log.extend(signup.get("log", []))
        if not signup.get("ok"):
            last_error = f"Signup failed: {signup.get('error')}"
            log.append(last_error)
            # Retry on dynamic anti-bot/username issues.
            continue

        send = send_proton_email(
            username=username,
            password=password,
            to=to_addr,
            subject=f"RAZ check-in from {creds['email']}",
            body=(
                "Yo Ryan,\n\n"
                "RAZ here. I created this Proton account and sent this email autonomously.\n"
                "This confirms the browser automation pipeline is live.\n\n"
                "- RAZ"
            ),
        )
        log.extend(send.get("log", []))

        if not send.get("ok"):
            last_error = f"Send failed: {send.get('error')}"
            log.append(last_error)
            continue

        return {
            "ok": True,
            "log": log + ["End-to-end flow complete"],
            "error": None,
            "credentials": creds,
        }

    return {
        "ok": False,
        "log": log,
        "error": last_error,
        "credentials": last_creds or {},
    }
