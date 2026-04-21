"""
core/tools.py — RAZ Tool Registry
This is how modern AI bots work: define Python functions as JSON schemas,
pass them to the LLM, and let the model call them with real arguments.
The model CANNOT hallucinate — it gets real output or it admits failure.

How it works:
1. TOOL_SCHEMAS list is sent to OpenAI with every request
2. OpenAI decides when a tool is needed and returns tool_call instead of text
3. dispatch_tool() executes the real Python function
4. Result is fed back to OpenAI, which then writes its final response
5. This loops until OpenAI is done (finish_reason == "stop")
"""

import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAZ_FILES_DIR = os.path.join(
    "C:\\Users\\Ry\\OneDrive\\Floater ShareDrive\\Anon\\RAZ\\Raziel\\Raziel\\Secret Brain",
    "RAZ-Files"
)

# ─────────────────────────────────────────────────────────────
# TOOL SCHEMAS  (sent to OpenAI/Groq as the `tools` parameter)
# ─────────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run any PowerShell command on Ryan's Windows PC and get real output. "
                "Use this for: creating files/folders, installing packages, opening programs, "
                "running scripts, checking system state, or any shell operation. "
                "Always use this instead of pretending to do something."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "PowerShell 5.1 command to execute on Ryan's machine"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text contents of any file on disk. Returns the file content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute Windows path to the file"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or create a file on disk. Creates parent directories automatically. "
                "Use for saving notes, credentials, plans, code, configs, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute Windows path to write the file to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write into the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders inside a directory on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute Windows path to the directory"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_browser",
            "description": "Open a URL in Ryan's default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to open (must start with http:// or https://)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_proton_email",
            "description": (
                "Log into an existing ProtonMail account and send an email using a real browser. "
                "Opens a visible Chrome window so Ryan can solve any captcha if needed. "
                "Returns actual success/failure — never pretends."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "ProtonMail username (without @proton.me)"
                    },
                    "password": {
                        "type": "string",
                        "description": "ProtonMail account password"
                    },
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body text"
                    }
                },
                "required": ["username", "password", "to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save an important fact to RAZ's permanent memory database so it's remembered "
                "across all future sessions. Use for: credentials, account info, decisions, "
                "settings, contact info, anything Ryan might ask about later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Category like credentials, accounts, contacts, settings, notes"
                    },
                    "key": {
                        "type": "string",
                        "description": "Short identifier for this fact"
                    },
                    "value": {
                        "type": "string",
                        "description": "The value to remember"
                    }
                },
                "required": ["category", "key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory",
            "description": "Retrieve facts stored in RAZ's memory database. Optionally filter by category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Category to filter by (optional — leave blank to get all)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Get real-time CPU, RAM, disk, and GPU stats for Ryan's PC.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": (
                "Save a note, document, or text file to Ryan's RAZ-Files folder inside Secret Brain. "
                "Use for: saving credentials after account creation, writing plans, storing reports, "
                "keeping important information Ryan will need later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename with extension, e.g. 'proton_account.txt' or 'plan.md'"
                    },
                    "content": {
                        "type": "string",
                        "description": "Full text content to write to the file"
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_page",
            "description": (
                "Open a URL in a real browser, optionally fill in form fields and click buttons. "
                "Use for web automation, logging into sites, filling out signup forms, etc. "
                "Returns what happened including screenshots paths. "
                "Set keep_open=true with profile='discord' or profile='proton' to keep persistent sessions logged in."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to"
                    },
                    "keep_open": {
                        "type": "boolean",
                        "description": "If true, uses persistent profile and keeps browser open so login sessions persist"
                    },
                    "profile": {
                        "type": "string",
                        "description": "Persistent profile name, e.g. 'discord' or 'proton'"
                    },
                    "actions": {
                        "type": "array",
                        "description": "List of actions to perform on the page",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["fill", "click", "wait", "screenshot", "get_text"]
                                },
                                "selector": {"type": "string"},
                                "value":    {"type": "string"},
                                "ms":       {"type": "integer"}
                            },
                            "required": ["type"]
                        }
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_page",
            "description": (
                "Load a web page and return its full structure: all input fields, buttons, iframes, "
                "and visible text. Use this BEFORE trying to fill any form so you know exactly "
                "what selectors to use. Essential for ProtonMail and any form-heavy page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to scan"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "proton_signup",
            "description": (
                "Create a new ProtonMail account. Handles the username iframe that blocks normal "
                "automation. Returns credentials if successful so they can be saved to memory. "
                "NOTE: ProtonMail may show a captcha — if it does, the browser window stays open "
                "so Ryan can solve it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Desired username (without @proton.me)"
                    },
                    "password": {
                        "type": "string",
                        "description": "Password — must be 8+ chars with uppercase, number, and symbol like P@ss1word!"
                    }
                },
                "required": ["username", "password"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "proton_full_flow",
            "description": (
                "Auto-generate credentials, create a ProtonMail account, log in, and send an email "
                "to the specified address — all in one browser session. This is the preferred way to "
                "fulfill 'create a ProtonMail and email me' requests. Returns the generated credentials."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to_addr": {
                        "type": "string",
                        "description": "Email address to send the confirmation email to"
                    }
                },
                "required": ["to_addr"]
            }
        }
    },
]


# ─────────────────────────────────────────────────────────────
# DISPATCHER  — executes tools by name, returns string result
# ─────────────────────────────────────────────────────────────

def dispatch_tool(name: str, args: dict) -> str:
    """Execute a named tool with given args. Always returns a string result."""
    try:
        if name == "run_shell":
            return _run_shell(args.get("command", ""))
        elif name == "read_file":
            return _read_file(args.get("path", ""))
        elif name == "write_file":
            return _write_file(args.get("path", ""), args.get("content", ""))
        elif name == "list_directory":
            return _list_directory(args.get("path", ""))
        elif name == "open_browser":
            return _open_browser(args.get("url", ""))
        elif name == "send_proton_email":
            return _send_proton_email(args)
        elif name == "save_memory":
            return _save_memory(args)
        elif name == "get_memory":
            return _get_memory(args.get("category", ""))
        elif name == "get_system_stats":
            return _get_system_stats()
        elif name == "create_note":
            return _create_note(args.get("filename", "note.txt"), args.get("content", ""))
        elif name == "browse_page":
            return _browse_page(
                args.get("url", ""),
                args.get("actions", []),
                args.get("keep_open", False),
                args.get("profile", ""),
            )
        elif name == "scan_page":
            return _scan_page(args.get("url", ""))
        elif name == "proton_signup":
            return _proton_signup(args.get("username", ""), args.get("password", ""))
        elif name == "proton_full_flow":
            return _proton_full_flow(args.get("to_addr", ""))
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool '{name}' crashed: {type(e).__name__}: {e}"


# ─────────────────────────────────────────────────────────────
# TOOL IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────

def _run_shell(command: str) -> str:
    from core.system_control import run_command
    result = run_command(command)
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    rc = result.get("returncode", -1)
    if rc == 0:
        return stdout or "(command completed, no output)"
    else:
        return f"Exit {rc}\nstdout: {stdout}\nstderr: {stderr}"


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(60000)
        return content if content else "(empty file)"
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Cannot read file: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written: {path} ({len(content):,} chars)"
    except Exception as e:
        return f"Cannot write file: {e}"


def _list_directory(path: str) -> str:
    try:
        entries = os.listdir(path)
        lines = [f"{path} ({len(entries)} items):"]
        for name in sorted(entries)[:100]:
            full = os.path.join(path, name)
            kind = "DIR " if os.path.isdir(full) else "FILE"
            try:
                size = os.path.getsize(full)
                size_str = f"{size:,} B"
            except Exception:
                size_str = "?"
            lines.append(f"  [{kind}] {name}  ({size_str})")
        return "\n".join(lines)
    except FileNotFoundError:
        return f"Directory not found: {path}"
    except Exception as e:
        return f"Cannot list directory: {e}"


def _open_browser(url: str) -> str:
    from core.system_control import open_url
    result = open_url(url)
    return result.get("stdout") or f"Browser opened: {url}"


def _send_proton_email(args: dict) -> str:
    from core.browser_agent import send_proton_email
    result = send_proton_email(
        username=args.get("username", ""),
        password=args.get("password", ""),
        to=args.get("to", ""),
        subject=args.get("subject", ""),
        body=args.get("body", ""),
    )
    lines = ["SUCCESS: Email sent" if result["ok"] else "FAILED: Email not sent"]
    lines += result.get("log", [])
    if result.get("error"):
        lines.append(f"Error: {result['error']}")
    return "\n".join(lines)


def _save_memory(args: dict) -> str:
    sys.path.insert(0, BASE_DIR)
    import core.memory_engine as mem
    mem.save_fact(
        args.get("category", "general"),
        args.get("key", "untitled"),
        args.get("value", ""),
        source="raz-tool"
    )
    return f"Saved to memory: [{args.get('category')}] {args.get('key')} = {args.get('value')}"


def _get_memory(category: str = "") -> str:
    import core.memory_engine as mem
    facts = mem.get_facts(category) if category else mem.get_facts()
    if not facts:
        return "No facts found in memory."
    lines = [f"[{f['category']}] {f['key']}: {f['value']}" for f in facts[:60]]
    return "\n".join(lines)


def _get_system_stats() -> str:
    from core.system_control import get_system_snapshot, format_snapshot_summary
    snap = get_system_snapshot()
    return format_snapshot_summary(snap)


def _create_note(filename: str, content: str) -> str:
    os.makedirs(RAZ_FILES_DIR, exist_ok=True)
    # Sanitize filename
    safe = "".join(c for c in filename if c not in r'\/:*?"<>|')
    if not safe:
        safe = "note.txt"
    path = os.path.join(RAZ_FILES_DIR, safe)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Note saved: {path} ({len(content):,} chars)"
    except Exception as e:
        return f"Cannot create note: {e}"


def _browse_page(url: str, actions: list, keep_open: bool = False, profile: str = "") -> str:
    from core.browser_agent import browse_and_fill
    if not actions:
        actions = [{"type": "screenshot"}]

    # If model omits persistent flags, default Discord sessions to persistent Edge profile.
    norm_url = (url or "").lower()
    resolved_keep_open = bool(keep_open)
    resolved_profile = (profile or "").strip()
    if "discord.com" in norm_url and not resolved_keep_open and not resolved_profile:
        resolved_keep_open = True
        resolved_profile = "discord"

    result = browse_and_fill(
        url,
        actions,
        headless=False,
        keep_open=resolved_keep_open,
        profile_name=resolved_profile,
    )
    lines = [f"Browser: {'OK' if result['ok'] else 'ERROR'}", f"URL: {url}"]
    lines += result.get("log", [])
    if result.get("error"):
        lines.append(f"Error: {result['error']}")
    return "\n".join(lines)


def _scan_page(url: str) -> str:
    from core.browser_agent import scan_page
    result = scan_page(url)
    if not result.get("ok"):
        return f"Scan failed: {result.get('error')}"
    lines = [
        f"PAGE SCAN: {result.get('title')}",
        f"URL: {result.get('url')}",
        f"Screenshot: {result.get('screenshot')}",
        "",
        f"IFRAMES ({len(result.get('iframes', []))}):",
    ]
    for fr in result.get("iframes", []):
        lines.append(f"  src={fr.get('src')}")
    lines.append("")
    lines.append(f"INPUTS ({len(result.get('inputs', []))}):")
    for inp in result.get("inputs", []):
        if inp.get("type") == "hidden":
            continue
        in_iframe = " [IN IFRAME]" if inp.get("in_iframe") else ""
        lines.append(
            f"  type={inp.get('type','text'):10} "
            f"name={inp.get('name',''):20} "
            f"id={inp.get('id',''):20} "
            f"placeholder={inp.get('placeholder',''):25}"
            f"{in_iframe}"
        )
    lines.append("")
    lines.append(f"BUTTONS ({len(result.get('buttons', []))}):")
    for btn in result.get("buttons", [])[:20]:
        if btn.get("text"):
            lines.append(f"  [{btn.get('type','button')}] {btn.get('text')}")
    lines.append("")
    lines.append("VISIBLE TEXT (first 800 chars):")
    lines.append((result.get("visible_text") or "")[:800])
    return "\n".join(lines)


def _proton_signup(username: str, password: str) -> str:
    from core.browser_agent import proton_signup
    result = proton_signup(username, password)
    lines = ["PROTON SIGNUP: " + ("SUCCESS" if result["ok"] else "FAILED")]
    lines += result.get("log", [])
    if result.get("error"):
        lines.append(f"Error: {result['error']}")
    creds = result.get("credentials", {})
    if creds:
        lines.append(f"Credentials: {creds.get('email')} / {creds.get('password')}")
    return "\n".join(lines)


def _proton_full_flow(to_addr: str) -> str:
    from core.browser_agent import proton_full_flow
    result = proton_full_flow(to_addr)
    lines = ["PROTON FULL FLOW: " + ("SUCCESS" if result["ok"] else "FAILED")]
    lines += result.get("log", [])
    if result.get("error"):
        lines.append(f"Error: {result['error']}")
    creds = result.get("credentials", {})
    if creds:
        lines.append(f"")
        lines.append(f"CREDENTIALS TO SAVE:")
        lines.append(f"  Email:    {creds.get('email')}")
        lines.append(f"  Username: {creds.get('username')}")
        lines.append(f"  Password: {creds.get('password')}")
    return "\n".join(lines)

