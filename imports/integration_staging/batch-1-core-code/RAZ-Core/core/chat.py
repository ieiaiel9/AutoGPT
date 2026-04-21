"""
RAZ Core - Core Chat Loop
The primary conversation engine for RAZ.
Handles: session management, memory persistence, mode switching, command parsing.
Provider: OpenAI API (swappable to local models via config).
"""

import os
import sys
import uuid
import json
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import core.memory_engine as mem
from system.prompt_loader import load_system_prompt
from system.config_loader import load_config, save_config

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


COMMANDS = {
    "/mode": "Switch mode: /mode chat|mentor|meeting|research|build|overnight",
    "/memory": "Show memory summary: /memory facts|projects|tasks|files",
    "/email": "Send email via saved Proton account: /email recipient@example.com | Subject line | Body text",
    "/save": "Save a fact: /save category key value",
    "/project": "Save/update project: /project name | description | domain",
    "/task": "Add a task: /task title | description | priority",
    "/tasks": "List pending tasks",
    "/followups": "List auto-captured failed/incomplete requests",
    "/done": "Mark a task complete: /done 123",
    "/flag": "Manually flag a request as follow-up: /flag what went wrong",
    "/sync": "Sync follow-ups across devices: /sync export | /sync import [path]",
    "/voice": "Voice conversation: /voice once|convo|loop|off",
    "/ingest": "Ingest a file or directory: /ingest /path/to/file",
    "/history": "Show recent session messages",
    "/clear": "Clear screen",
    "/exit": "Exit RAZ",
    "/help": "Show this command list",
    "/summarize": "Summarize the current session",
    "/discord": "Discord session tools: /discord keep | /discord login email | password",
    "/sys": "System stats: /sys stats|top|scan|run <cmd>|ls <path>|read <path>|startup|unstartup",
    "/key": "Quick key helper: /key status | /key gemini AIza... | /key openai sk-... | /key groq gsk_...",
    "/gemini": "Quick set Gemini key: /gemini AIza...",
    "/memory search": "Search memory: /memory search <query>",
    "/git": "Git integration: /git status | commit <msg> | push | log | branch [name]",
    "/backup": "Backup a folder: /backup <source_path> [dest_path]",
    "/test": "Run pytest on a path: /test [path]",
    "/alert": "Resource alerts: /alert status | set cpu|ram|disk <pct> | on | off",
    "/cal": "Google Calendar: /cal today | /cal add YYYY-MM-DD HH:MM | Title | minutes",
    "/gmail": "Gmail: /gmail unread [n] | /gmail send to@example.com | Subject | Body",
    "/storage": "Storage routes: /storage status | /storage setsd <path>",
}

GROQ_DEFAULT_MODEL = "llama-3.1-8b-instant"
GROQ_MODEL_FALLBACKS = (
    GROQ_DEFAULT_MODEL,
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
)

POWERSHELL_EXE_NAME = "powershell.exe"


def _powershell_exe() -> str:
    """Resolve PowerShell path explicitly to reduce path ambiguity."""
    system_root = os.environ.get("SystemRoot", r"C:\\Windows")
    candidates = [
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", POWERSHELL_EXE_NAME),
        os.path.join(system_root, "SysWOW64", "WindowsPowerShell", "v1.0", POWERSHELL_EXE_NAME),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return POWERSHELL_EXE_NAME


def _clear_terminal_screen() -> None:
    """Clear terminal in a cross-platform way without shell invocation."""
    if os.name == "nt":
        subprocess.run([_powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", "Clear-Host"], check=False)
        return
    subprocess.run(["clear"], check=False)


class RAZChat:
    def __init__(self):
        self.config = load_config()
        self.session_id = str(uuid.uuid4())[:8]
        self.mode = "chat"
        self.history = []
        self.client = None
        self.client_provider = None
        self.meeting_decisions = []
        self.meeting_actions = []

        mem.init_memory()
        mem.start_session(self.session_id, mode=self.mode)

        self._seed_initial_memory()
        self._load_recent_memory_into_context()
        self._refresh_system_prompt()

    def _load_recent_memory_into_context(self):
        """
        Load the last few sessions' messages into history so RAZ
        remembers what happened before this session started.
        Injects up to 30 messages from the most recent 3 sessions.
        """
        try:
            recent_sessions = mem.get_recent_sessions(limit=4)
            injected = []
            for session in reversed(recent_sessions):  # oldest first
                sid = session["session_id"]
                if sid == self.session_id:
                    continue
                msgs = mem.get_session_messages(sid)
                for m in msgs[-12:]:  # last 12 messages per session
                    if m["role"] in ("user", "assistant"):
                        injected.append({"role": m["role"], "content": m["content"]})
                if len(injected) >= 30:
                    break
            # Inject as a synthetic "memory" block at start of history
            if injected:
                summary_block = {
                    "role": "system",
                    "content": (
                        "CONVERSATION MEMORY (previous sessions with Ryan):\n"
                        + "\n".join(
                            f"  {'Ryan' if m['role']=='user' else 'RAZ'}: {m['content'][:200]}"
                            for m in injected[-30:]
                        )
                        + "\n\nUse this to maintain continuity. You remember everything above."
                    )
                }
                self.history.insert(0, summary_block)
        except Exception:
            pass  # Never crash init on memory load failure

    def _seed_initial_memory(self):
        """Seed base profile facts on first run."""
        existing = mem.get_facts("profile")
        if not existing:
            mem.save_fact("profile", "name", "Ryan A. Wallace")
            mem.save_fact("profile", "location", "Oklahoma City")
            mem.save_fact("business", "hyperbaric_plus", "Wellness business - hyperbaric air therapy")
            mem.save_fact("business", "hyperbarics_for_heroes", "Nonprofit - veterans and first responders hyperbaric support")
            mem.save_fact("business", "lonely_floater", "Artist development and media project")
            mem.save_fact("business", "aveek_music", "Music artist project")
            mem.save_project("RAZ-Core", "Local-first personal AI assistant system", domain="AI/Software", status="active")
            mem.save_project("Hyperbaric+", "Hyperbaric air therapy wellness business", domain="Wellness", status="active")
            mem.save_project("Hyperbarics for Heroes", "Veteran/first responder hyperbaric nonprofit", domain="Nonprofit", status="active")
            mem.save_project("Lonely Floater", "Artist development and media", domain="Entertainment", status="active")
            mem.save_project("Aveek Music", "Music artist management and development", domain="Entertainment", status="active")

    def _refresh_system_prompt(self):
        self.system_prompt = load_system_prompt(mode=self.mode, memory_engine=mem)

    def _try_connect_client(self):
        """Initialize LLM client based on provider in config: openai, groq, or ollama."""
        if not OPENAI_AVAILABLE:
            return False
        cfg      = load_config()
        provider = cfg.get("provider", "openai").strip().lower()

        if self.client and self.client_provider == provider:
            return True

        if self.client and self.client_provider != provider:
            self.client = None
            self.client_provider = None

        try:
            from openai import OpenAI

            if provider == "groq":
                api_key = cfg.get("groq_api_key", "").strip()
                if not api_key:
                    return False
                self.client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
                self.client_provider = "groq"
                # Override model to groq model
                return True

            elif provider == "ollama":
                url = cfg.get("ollama_url", "http://localhost:11434/v1").rstrip("/")
                self.client = OpenAI(
                    api_key="ollama",   # Ollama ignores this but SDK requires it
                    base_url=url,
                )
                self.client_provider = "ollama"
                return True

            else:  # openai
                api_key = cfg.get("openai_api_key", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
                if not api_key:
                    return False
                self.client = OpenAI(api_key=api_key)
                self.client_provider = "openai"
                return True

        except Exception:
            return False

    def _get_model(self) -> str:
        """Return the correct model name for the active provider."""
        cfg      = load_config()
        provider = cfg.get("provider", "openai").strip().lower()
        if provider == "groq":
            return cfg.get("groq_model", GROQ_DEFAULT_MODEL)
        elif provider == "ollama":
            return cfg.get("ollama_model", "llama3.1:8b")
        else:
            return cfg.get("model", "gpt-4o")

    def _is_groq_model_not_found(self, error: Exception) -> bool:
        text = str(error or "").lower()
        return (
            "model_not_found" in text
            or "does not exist or you do not have access" in text
            or "invalid_request_error" in text and "model" in text
        )

    def _get_groq_model_candidates(self, cfg: dict, preferred: str | None = None) -> list[str]:
        candidates = []
        for model_name in (preferred, cfg.get("groq_model", ""), *GROQ_MODEL_FALLBACKS):
            model_name = str(model_name or "").strip()
            if model_name and model_name not in candidates:
                candidates.append(model_name)
        return candidates

    def _persist_groq_model(self, model_name: str):
        model_name = str(model_name or "").strip()
        if not model_name:
            return
        cfg = load_config()
        if cfg.get("groq_model") == model_name:
            return
        cfg["groq_model"] = model_name
        save_config(cfg)
        self.config = cfg

    def _get_fallback_provider(self, cfg: dict, provider: str) -> str | None:
        provider = str(provider or "").strip().lower()
        configured = str(cfg.get("fallback_provider", "") or "").strip().lower()
        if provider == "openai":
            return configured or "groq"
        if provider == "groq":
            return configured or "openai"
        return configured or None

    def _should_fallback_for_error(self, provider: str, fallback_provider: str | None, error: Exception) -> bool:
        provider = str(provider or "").strip().lower()
        fallback_provider = str(fallback_provider or "").strip().lower()
        if not fallback_provider or fallback_provider == provider:
            return False

        text = str(error or "").lower()
        if provider == "groq":
            return (
                self._is_groq_model_not_found(error)
                or "request too large" in text
                or "tokens per minute" in text
                or "rate_limit_exceeded" in text
                or "service tier" in text and "token" in text
            )
        return False

    def _build_client_for_provider(self, provider: str, cfg: dict):
        from openai import OpenAI as _OAI

        provider = str(provider or "").strip().lower()
        if provider == "openai":
            key = str(cfg.get("openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")).strip()
            if not key:
                return None, None
            return _OAI(api_key=key), str(cfg.get("model", "gpt-4o")).strip()

        if provider == "groq":
            key = str(cfg.get("groq_api_key", "")).strip()
            if not key:
                return None, None
            return _OAI(api_key=key, base_url="https://api.groq.com/openai/v1"), str(cfg.get("groq_model", GROQ_DEFAULT_MODEL)).strip()

        if provider == "ollama":
            url = str(cfg.get("ollama_url", "http://localhost:11434/v1")).rstrip("/")
            return _OAI(api_key="ollama", base_url=url), str(cfg.get("ollama_model", "llama3.1:8b")).strip()

        return None, None

    def _call_with_provider(self, messages: list, cfg: dict, provider_override: str) -> str:
        client, model_name = self._build_client_for_provider(provider_override, cfg)
        if not client:
            return f"RAZ: [{provider_override} not connected]"

        response, _ = self._create_chat_completion(
            client=client,
            cfg=cfg,
            messages=messages,
            max_tokens=cfg.get("max_tokens", 2048),
            temperature=cfg.get("temperature", 0.7),
            provider_override=provider_override,
            model_override=model_name,
        )
        return response.choices[0].message.content.strip()

    def _create_chat_completion(self, *, client, cfg: dict, messages: list, max_tokens: int, temperature: float, stream: bool = False, tools=None, tool_choice=None, provider_override: str | None = None, model_override: str | None = None):
        provider = str(provider_override or cfg.get("provider", "openai")).strip().lower()

        def _build_kwargs(model_name: str) -> dict:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": stream,
            }
            if tools is not None:
                kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
            return kwargs

        if provider == "groq":
            last_error = None
            for model_name in self._get_groq_model_candidates(cfg, model_override):
                try:
                    result = client.chat.completions.create(**_build_kwargs(model_name))
                    self._persist_groq_model(model_name)
                    return result, model_name
                except Exception as error:
                    last_error = error
                    if self._is_groq_model_not_found(error):
                        continue
                    raise
            raise last_error

        model_name = str(model_override or self._get_model()).strip()
        return client.chat.completions.create(**_build_kwargs(model_name)), model_name

    def _call_llm(self, messages: list) -> str:
        """Call the LLM with the current message history."""
        self._try_connect_client()
        if not self.client:
            return "RAZ: [LLM not connected. Set OPENAI_API_KEY in config.json or environment. Running in shell-only mode.]"

        try:
            _fresh_cfg = load_config()
            provider = _fresh_cfg.get("provider", "openai").strip().lower()
            fallback = self._get_fallback_provider(_fresh_cfg, provider)
            model = self._get_model()
            max_tokens = _fresh_cfg.get("max_tokens", 2048)
            temperature = _fresh_cfg.get("temperature", 0.7)

            full_messages = [{"role": "system", "content": self.system_prompt}] + messages

            response, _ = self._create_chat_completion(
                client=self.client,
                cfg=_fresh_cfg,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                model_override=model,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            if self._should_fallback_for_error(provider, fallback, e):
                try:
                    return self._call_with_provider(full_messages, _fresh_cfg, fallback)
                except Exception:
                    pass
            try:
                last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
                device = self.config.get("device_name", "unknown")
                issue = mem.log_followup_issue(
                    user_request=last_user,
                    reason=f"LLM Error: {e}",
                    context="LLM call failed in _call_llm",
                    source_device=device,
                    priority="high",
                )
                return f"RAZ: [LLM Error: {e}]\nAuto-logged follow-up task #{issue['task_id']}."
            except Exception:
                return f"RAZ: [LLM Error: {e}]"

    def _handle_command(self, user_input: str) -> str:
        """Parse and execute slash commands."""
        parts = user_input.strip().split(" ", 2)
        cmd = parts[0].lower()

        if cmd == "/help":
            lines = ["RAZ Commands:"]
            for c, desc in COMMANDS.items():
                lines.append(f"  {c} - {desc}")
            return "\n".join(lines)

        elif cmd == "/mode":
            if len(parts) < 2:
                return f"RAZ: Current mode: {self.mode}. Options: chat, mentor, meeting, research, build, overnight"
            new_mode = parts[1].lower()
            valid_modes = {"chat", "mentor", "meeting", "research", "build", "overnight"}
            if new_mode not in valid_modes:
                return f"RAZ: Unknown mode '{new_mode}'. Valid: {', '.join(valid_modes)}"
            self.mode = new_mode
            self._refresh_system_prompt()
            mem.save_fact("session", f"mode_{self.session_id}", new_mode, source="system")
            if new_mode == "meeting":
                self.meeting_decisions = []
                self.meeting_actions = []
                return f"RAZ: Meeting Mode activated. Session {self.session_id}. Objectives, decisions, and actions will be tracked. Say 'summarize meeting' when done."
            if new_mode == "mentor":
                return "RAZ: Mentor Mode activated. Expect blunt, strategic guidance and stronger recommendations."
            return f"RAZ: Mode switched to {new_mode}."

        elif cmd == "/memory":
            sub = parts[1].lower() if len(parts) > 1 else "facts"
            if sub == "facts":
                facts = mem.get_facts()
                if not facts:
                    return "RAZ: No facts stored yet."
                lines = ["RAZ: Memory Facts:"]
                for f in facts:
                    lines.append(f"  [{f['category']}] {f['key']}: {f['value']}")
                return "\n".join(lines)
            elif sub == "search":
                query = parts[2].strip() if len(parts) > 2 else ""
                if not query:
                    return "RAZ: Usage: /memory search <query>"
                results = mem.search_facts(query)
                if not results:
                    return f"RAZ: No memory facts matching '{query}'"
                lines = [f"RAZ: Memory search results for '{query}' ({len(results)} hits):"]
                for row in results[:30]:
                    lines.append(f"  [{row['category']}] {row['key']}: {row['value']}")
                return "\n".join(lines)
            elif sub == "projects":
                projects = mem.get_projects()
                if not projects:
                    return "RAZ: No projects stored."
                lines = ["RAZ: Active Projects:"]
                for p in projects:
                    lines.append(f"  {p['name']} [{p['status']}] - {p['description']}")
                return "\n".join(lines)
            elif sub == "tasks":
                tasks = mem.get_tasks(status="pending")
                if not tasks:
                    return "RAZ: No pending tasks."
                lines = ["RAZ: Pending Tasks:"]
                for t in tasks:
                    lines.append(f"  [{t['priority']}] {t['title']} - {t['description']}")
                return "\n".join(lines)
            elif sub == "files":
                files = mem.get_ingested_files()
                if not files:
                    return "RAZ: No files ingested yet."
                lines = [f"RAZ: Ingested Files ({len(files)}):"]
                for fl in files[-20:]:
                    lines.append(f"  {fl['filename']} | {fl['ingested_at'][:10]} | tags: {fl['tags']}")
                return "\n".join(lines)
            return f"RAZ: Unknown memory sub-command: {sub}"

        elif cmd == "/email":
            raw = parts[1] if len(parts) == 2 else " ".join(parts[1:])
            segments = [s.strip() for s in raw.split("|")]
            if len(segments) < 3:
                return "RAZ: Usage: /email recipient@example.com | Subject line | Body text"

            to_addr, subject, body = segments[0], segments[1], " | ".join(segments[2:])
            facts = mem.get_facts("accounts")
            fact_map = {f["key"]: f["value"] for f in facts}

            proton_email = fact_map.get("protonmail_email") or fact_map.get("proton_email")
            proton_password = fact_map.get("protonmail_password") or fact_map.get("proton_password")

            if not proton_email or not proton_password:
                return (
                    "RAZ: Proton credentials are not saved in memory. "
                    "Save them first, then retry /email."
                )

            from core.browser_agent import send_proton_email

            result = send_proton_email(
                username=proton_email,
                password=proton_password,
                to=to_addr,
                subject=subject,
                body=body,
            )

            lines = [
                f"RAZ: Email {'sent' if result.get('ok') else 'not sent'} via {proton_email}",
                f"To: {to_addr}",
                f"Subject: {subject}",
            ]
            lines.extend(result.get("log", []))
            if result.get("error"):
                lines.append(f"Error: {result['error']}")
            return "\n".join(lines)

        elif cmd == "/save":
            if len(parts) < 3:
                return "RAZ: Usage: /save category key value"
            raw = parts[2]
            sub_parts = raw.split(" ", 1)
            if len(sub_parts) < 2:
                return "RAZ: Usage: /save category key value"
            category = parts[1]
            key = sub_parts[0]
            value = sub_parts[1]
            mem.save_fact(category, key, value, source="user")
            return f"RAZ: Saved [{category}] {key}: {value}"

        elif cmd == "/project":
            if len(parts) < 2:
                return "RAZ: Usage: /project name | description | domain"
            raw = parts[1] if len(parts) == 2 else " ".join(parts[1:])
            segments = [s.strip() for s in raw.split("|")]
            name = segments[0] if len(segments) > 0 else "Unnamed"
            description = segments[1] if len(segments) > 1 else ""
            domain = segments[2] if len(segments) > 2 else ""
            mem.save_project(name, description=description, domain=domain)
            return f"RAZ: Project saved: {name}"

        elif cmd == "/task":
            if len(parts) < 2:
                return "RAZ: Usage: /task title | description | priority"
            raw = parts[1] if len(parts) == 2 else " ".join(parts[1:])
            segments = [s.strip() for s in raw.split("|")]
            title = segments[0]
            description = segments[1] if len(segments) > 1 else ""
            priority = segments[2] if len(segments) > 2 else "normal"
            task_id = mem.save_task(title, description=description, priority=priority)
            return f"RAZ: Task #{task_id} added: {title}"

        elif cmd == "/tasks":
            tasks = mem.get_tasks(status="pending")
            if not tasks:
                return "RAZ: No pending tasks."
            lines = [f"RAZ: Pending Tasks ({len(tasks)}):"]
            for t in tasks:
                lines.append(f"  #{t['id']} [{t['priority'].upper()}] {t['title']}")
                if t["description"]:
                    lines.append(f"       {t['description']}")
            return "\n".join(lines)

        elif cmd == "/followups":
            items = mem.get_followup_tasks(status="pending", limit=100)
            if not items:
                return "RAZ: No pending follow-ups."
            lines = [f"RAZ: Pending Follow-Ups ({len(items)}):"]
            for t in items:
                lines.append(f"  #{t['id']} [{t['priority'].upper()}] {t['title']}")
            lines.append("Use /done <task_id> when one is fully resolved.")
            return "\n".join(lines)

        elif cmd == "/done":
            if len(parts) < 2:
                return "RAZ: Usage: /done <task_id>"
            try:
                task_id = int(parts[1].strip())
            except ValueError:
                return "RAZ: Task id must be a number. Example: /done 42"

            task = mem.get_task_by_id(task_id)
            if not task:
                return f"RAZ: Task #{task_id} not found."
            mem.complete_task(task_id)
            return f"RAZ: Task #{task_id} marked completed."

        elif cmd == "/flag":
            details = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
            if not details:
                return "RAZ: Usage: /flag <what failed or what to remember>"
            device = self.config.get("device_name", "unknown")
            issue = mem.log_followup_issue(
                user_request=details,
                reason="Manually flagged by user",
                context="Created via /flag command",
                source_device=device,
                priority="high",
            )
            return f"RAZ: Logged follow-up task #{issue['task_id']} for this item."

        elif cmd == "/sync":
            cfg = load_config()
            default_path = cfg.get("sync_bundle_path")
            sub = parts[1].lower() if len(parts) > 1 else "export"

            if sub == "export":
                try:
                    result = mem.export_sync_bundle(default_path)
                    return (
                        f"RAZ: Sync export complete.\n"
                        f"Path: {result['path']}\n"
                        f"Tasks: {result['tasks']} | Facts: {result['facts']}"
                    )
                except Exception as e:
                    return f"RAZ: Sync export failed: {e}"

            if sub == "import":
                path = " ".join(parts[2:]).strip() if len(parts) > 2 else default_path
                try:
                    result = mem.import_sync_bundle(path)
                    if not result.get("ok"):
                        return f"RAZ: Sync import failed: {result.get('error', 'unknown error')}"
                    return (
                        f"RAZ: Sync import complete.\n"
                        f"Path: {result['path']}\n"
                        f"Tasks added: {result['tasks_added']} | Facts processed: {result['facts_processed']}"
                    )
                except Exception as e:
                    return f"RAZ: Sync import failed: {e}"

            return "RAZ: Usage: /sync export | /sync import [path]"

        elif cmd == "/voice":
            sub = parts[1].lower() if len(parts) > 1 else "once"
            try:
                from core.voice_engine import run_voice_once, run_voice_loop
            except Exception as e:
                return (
                    f"RAZ: Voice engine unavailable: {e}\n"
                    f"Install voice deps with: pip install faster-whisper sounddevice scipy numpy pyttsx3"
                )

            if sub == "once":
                result = run_voice_once(self)
                return result

            if sub in ("loop", "convo", "conversation"):
                return run_voice_loop(self)

            if sub == "off":
                return "RAZ: Voice loop stops when you press Ctrl+C in the terminal."

            return "RAZ: Usage: /voice once | /voice convo | /voice loop | /voice off"

        elif cmd == "/ingest":
            if len(parts) < 2:
                return "RAZ: Usage: /ingest /path/to/file_or_directory"
            target = " ".join(parts[1:]).strip()
            from ingestion.ingestor import ingest_file, ingest_directory
            if os.path.isfile(target):
                result = ingest_file(target, memory_engine=mem)
                return f"RAZ: [{result['status'].upper()}] {result['filename']} - {result['reason']}"
            elif os.path.isdir(target):
                results = ingest_directory(target, memory_engine=mem)
                ingested = sum(1 for r in results if r["status"] == "ingested")
                dupes = sum(1 for r in results if r["status"] == "duplicate")
                return f"RAZ: Ingestion complete. {ingested} new files ingested, {dupes} duplicates detected."
            else:
                return f"RAZ: Path not found: {target}"

        elif cmd == "/history":
            messages = mem.get_session_messages(self.session_id)
            if not messages:
                return "RAZ: No messages in current session yet."
            lines = [f"RAZ: Session {self.session_id} history ({len(messages)} messages):"]
            for m in messages[-10:]:
                ts = m["timestamp"][:16] if m["timestamp"] else ""
                role_label = "YOU" if m["role"] == "user" else "RAZ"
                lines.append(f"  [{ts}] {role_label}: {m['content'][:80]}...")
            return "\n".join(lines)

        elif cmd == "/summarize":
            if not self.history:
                return "RAZ: Nothing to summarize yet."
            summary_prompt = [
                {"role": "user", "content": "Please summarize our conversation so far. Include: key topics, decisions made, action items, and any open questions. Be concise and structured."}
            ]
            all_messages = self.history + summary_prompt
            summary = self._call_llm(all_messages)

            if self.mode == "meeting":
                mem.end_session(
                    self.session_id,
                    summary=summary,
                    decisions=self.meeting_decisions,
                    action_items=self.meeting_actions
                )
                return f"RAZ: Meeting summary saved.\n\n{summary}"
            return summary

        elif cmd == "/clear":
            _clear_terminal_screen()
            return ""

        elif cmd == "/sys":
            return self._handle_sys(parts)

        elif cmd == "/gemini":
            from system.config_loader import set_api_key
            api_key = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
            if not api_key:
                return "RAZ: Usage: /gemini AIza..."
            ok = set_api_key("gemini", api_key)
            if not ok:
                return "RAZ: Could not save gemini key"
            masked = f"***{api_key[-4:]}" if len(api_key) >= 4 else "(saved)"
            return f"RAZ: gemini key saved to secure storage: {masked}"

        elif cmd == "/key":
            # Short aliases for key management to reduce typing mistakes.
            from system.config_loader import get_api_key_statuses, set_api_key

            if len(parts) < 2:
                return "RAZ: Usage: /key status | /key <openai|groq|gemini> <api_key> | /key clear <provider>"

            action = parts[1].strip().lower()

            if action == "status":
                statuses = get_api_key_statuses()
                return (
                    "RAZ: API key status (secure storage)\n"
                    f"  openai: {'🟢 set' if statuses.get('openai') else '🔴 missing'}\n"
                    f"  groq:   {'🟢 set' if statuses.get('groq') else '🔴 missing'}\n"
                    f"  gemini: {'🟢 set' if statuses.get('gemini') else '🔴 missing'}"
                )

            if action == "clear":
                provider = parts[2].strip().lower() if len(parts) > 2 else ""
                if provider not in ("openai", "groq", "gemini"):
                    return "RAZ: Usage: /key clear <openai|groq|gemini>"
                ok = set_api_key(provider, "")
                return f"RAZ: {provider} key {'cleared' if ok else 'not updated'}"

            provider = action
            if provider not in ("openai", "groq", "gemini"):
                return "RAZ: Usage: /key <openai|groq|gemini> <api_key>"

            api_key = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
            if not api_key:
                return "RAZ: Usage: /key <openai|groq|gemini> <api_key>"
            ok = set_api_key(provider, api_key)
            if not ok:
                return f"RAZ: Could not save {provider} key"
            masked = f"***{api_key[-4:]}" if len(api_key) >= 4 else "(saved)"
            return f"RAZ: {provider} key saved to secure storage: {masked}"

        elif cmd == "/discord":
            raw = parts[1] if len(parts) == 2 else " ".join(parts[1:])
            sub = raw.strip().lower()
            from core.browser_agent import browse_and_fill

            if not sub or sub == "keep":
                result = browse_and_fill(
                    "https://discord.com/login",
                    actions=[{"type": "screenshot"}],
                    headless=False,
                    keep_open=True,
                    profile_name="discord",
                )
                lines = ["RAZ: Discord persistent session opened in Edge."]
                lines += result.get("log", [])
                if result.get("error"):
                    lines.append(f"Error: {result['error']}")
                return "\n".join(lines)

            # /discord login email | password
            if sub.startswith("login"):
                payload = raw[len("login"):].strip()
                seg = [s.strip() for s in payload.split("|")]
                if len(seg) < 2:
                    return "RAZ: Usage: /discord login email@example.com | YourPassword"
                email, password = seg[0], " | ".join(seg[1:])
                actions = [
                    {"type": "fill", "selector": "input[name='email']", "value": email},
                    {"type": "fill", "selector": "input[type='password']", "value": password},
                    {"type": "click", "selector": "button[type='submit']"},
                    {"type": "screenshot"},
                ]
                result = browse_and_fill(
                    "https://discord.com/login",
                    actions=actions,
                    headless=False,
                    keep_open=True,
                    profile_name="discord",
                )
                lines = ["RAZ: Discord login attempted in persistent Edge session."]
                lines += result.get("log", [])
                if result.get("error"):
                    lines.append(f"Error: {result['error']}")
                return "\n".join(lines)

            return "RAZ: Usage: /discord keep OR /discord login email@example.com | password"

        elif cmd == "/git":
            from core.git_agent import run_git
            sub = parts[1].lower() if len(parts) > 1 else "status"
            args = parts[2:] if len(parts) > 2 else []
            result = run_git(sub, args)
            return f"RAZ: {result}"

        elif cmd == "/backup":
            from core.backup_agent import run_backup
            src = " ".join(parts[1:]).split("|")[0].strip() if len(parts) > 1 else ""
            dest = " ".join(parts[1:]).split("|")[1].strip() if "|" in " ".join(parts[1:]) else None
            if not src:
                return "RAZ: Usage: /backup <source_path> [| dest_path]"
            result = run_backup(src, dest)
            return f"RAZ: {result}"

        elif cmd == "/test":
            path = " ".join(parts[1:]).strip() if len(parts) > 1 else "."
            from core.system_control import run_command
            result = run_command(f"cd '{path}'; python -m pytest -v --tb=short 2>&1", timeout=120)
            out = result.get("stdout") or result.get("stderr") or "(no output)"
            return f"RAZ: pytest [{result['returncode']}]\n{out[:3000]}"

        elif cmd == "/alert":
            cfg = load_config()
            sub = parts[1].lower() if len(parts) > 1 else "status"
            if sub == "status":
                enabled = cfg.get("resource_alerts_enabled", True)
                return (
                    f"RAZ: Resource Alerts {'ON' if enabled else 'OFF'}\n"
                    f"  CPU  threshold: {cfg.get('cpu_alert_pct', 90)}%\n"
                    f"  RAM  threshold: {cfg.get('ram_alert_pct', 90)}%\n"
                    f"  Disk threshold: {cfg.get('disk_alert_pct', 95)}%\n"
                    "  Change with: /alert set cpu|ram|disk <pct>"
                )
            elif sub == "set" and len(parts) >= 4:
                resource = parts[2].lower()
                try:
                    pct = int(parts[3])
                except ValueError:
                    return "RAZ: Threshold must be a number (0-100)"
                key_map = {"cpu": "cpu_alert_pct", "ram": "ram_alert_pct", "disk": "disk_alert_pct"}
                if resource not in key_map:
                    return "RAZ: Resource must be cpu, ram, or disk"
                cfg[key_map[resource]] = pct
                from system.config_loader import save_config
                save_config(cfg)
                return f"RAZ: {resource.upper()} alert threshold set to {pct}%"
            elif sub in ("on", "off"):
                cfg["resource_alerts_enabled"] = (sub == "on")
                from system.config_loader import save_config
                save_config(cfg)
                return f"RAZ: Resource alerts {'enabled' if sub == 'on' else 'disabled'}"
            return "RAZ: Usage: /alert status | set cpu|ram|disk <pct> | on | off"

        elif cmd == "/cal":
            from core.google_calendar_agent import get_today_events, add_event
            sub = parts[1].lower() if len(parts) > 1 else "today"
            if sub == "today":
                limit = 10
                if len(parts) > 2:
                    try:
                        limit = int(parts[2].strip())
                    except ValueError:
                        limit = 10
                return get_today_events(max_results=max(1, min(25, limit)))

            if sub == "add":
                payload = parts[2].strip() if len(parts) > 2 else ""
                if not payload or "|" not in payload:
                    return "RAZ: Usage: /cal add YYYY-MM-DD HH:MM | Title | minutes"
                seg = [s.strip() for s in payload.split("|")]
                start_local = seg[0] if len(seg) > 0 else ""
                title = seg[1] if len(seg) > 1 else "RAZ Event"
                minutes = 60
                if len(seg) > 2:
                    try:
                        minutes = int(seg[2])
                    except ValueError:
                        minutes = 60
                return add_event(title=title, start_local=start_local, minutes=minutes)

            return "RAZ: Usage: /cal today [n] | /cal add YYYY-MM-DD HH:MM | Title | minutes"

        elif cmd == "/gmail":
            from core.gmail_agent import get_unread_summary, send_gmail
            sub = parts[1].lower() if len(parts) > 1 else "unread"

            if sub == "unread":
                limit = 8
                if len(parts) > 2:
                    try:
                        limit = int(parts[2].strip())
                    except ValueError:
                        limit = 8
                return get_unread_summary(max_results=max(1, min(20, limit)))

            if sub == "send":
                payload = parts[2].strip() if len(parts) > 2 else ""
                seg = [s.strip() for s in payload.split("|")]
                if len(seg) < 3:
                    return "RAZ: Usage: /gmail send to@example.com | Subject | Body"
                to_addr = seg[0]
                subject = seg[1]
                body = " | ".join(seg[2:])
                return send_gmail(to_addr=to_addr, subject=subject, body=body)

            return "RAZ: Usage: /gmail unread [n] | /gmail send to@example.com | Subject | Body"

        elif cmd == "/storage":
            return self._handle_storage_command(parts)

        elif cmd == "/exit":
            self._cleanup()
            sys.exit(0)

        return f"RAZ: Unknown command: {cmd}. Type /help for commands."

    def _handle_storage_command(self, parts: list) -> str:
        """Handle /storage command and subcommands."""
        from system.storage_layout import resolve_storage_config
        cfg = load_config()
        sub = parts[1].strip().lower() if len(parts) > 1 else "status"

        if sub == "status":
            resolved = resolve_storage_config(cfg)
            core_root = resolved.get("core_data_root")
            sd_root = resolved.get("sd_card_root") or "(not set)"
            ext_root = resolved.get("external_data_root")
            backup_dest = resolved.get("backup_dest")
            sync_path = resolved.get("sync_bundle_path")
            return (
                "RAZ: Storage layout\n"
                f"  Core (internal): {core_root}\n"
                f"  SD root:          {sd_root}\n"
                f"  External route:   {ext_root}\n"
                f"  Backups:          {backup_dest}\n"
                f"  Sync bundle:      {sync_path}"
            )

        if sub == "setsd":
            sd_path = parts[2].strip() if len(parts) > 2 else ""
            if not sd_path:
                return "RAZ: Usage: /storage setsd <path-to-sd-root>"
            if not os.path.exists(sd_path):
                return f"RAZ: Path not found: {sd_path}"
            cfg["sd_card_root"] = sd_path
            cfg["external_data_root"] = ""
            cfg["backup_dest"] = ""
            cfg["sync_bundle_path"] = ""
            cfg = resolve_storage_config(cfg)
            save_config(cfg)
            return (
                "RAZ: SD storage route updated.\n"
                f"  SD root: {cfg.get('sd_card_root')}\n"
                f"  External route: {cfg.get('external_data_root')}\n"
                f"  Backups: {cfg.get('backup_dest')}\n"
                f"  Sync bundle: {cfg.get('sync_bundle_path')}"
            )

        return "RAZ: Usage: /storage status | /storage setsd <path>"

    def _handle_sys_provider(self, parts: list) -> str:
        """Handle /sys provider subcommand."""
        cfg = load_config()
        if len(parts) < 3:
            current = cfg.get("provider", "openai")
            model = self._get_model()
            groq_set = "✓ SET" if cfg.get("groq_api_key") else "✗ not set"
            gemini_set = "✓ SET" if cfg.get("gemini_api_key") else "✗ not set"
            return (
                f"RAZ: Active provider: {current.upper()}  |  Model: {model}\n"
                f"  openai key: {'✓ SET' if cfg.get('openai_api_key') else '✗ not set'}\n"
                f"  groq key:   {groq_set}\n"
                f"  gemini key:{gemini_set}\n"
                f"  ollama url: {cfg.get('ollama_url', 'http://localhost:11434/v1')}\n\n"
                f"Switch with:\n"
                f"  /sys provider openai\n"
                f"  /sys provider groq YOUR_GROQ_KEY\n"
                f"  /sys provider ollama llama3.1:8b\n"
                f"Manage keys securely:\n"
                f"  /sys keys"
            )

        new_provider = parts[2].lower()
        if new_provider == "openai":
            cfg["provider"] = "openai"
            save_config(cfg)
            self.client = None
            return "RAZ: Switched to OpenAI GPT-4o. Restart or send a message to reconnect."

        if new_provider == "groq":
            if len(parts) >= 4:
                cfg["groq_api_key"] = parts[3]
            if not cfg.get("groq_api_key"):
                return "RAZ: Need your Groq key. Get it free at https://console.groq.com → /sys provider groq YOUR_KEY"
            cfg["provider"] = "groq"
            save_config(cfg)
            self.client = None
            model = cfg.get("groq_model", "llama-3.3-70b-versatile")
            mem.save_fact("config", "provider", "groq", source="user")
            return f"RAZ: Switched to Groq — {model}. Zero restrictions. Send a message to test."

        if new_provider == "ollama":
            cfg["provider"] = "ollama"
            if len(parts) >= 4:
                cfg["ollama_model"] = parts[3]
            save_config(cfg)
            self.client = None
            model = cfg.get("ollama_model", "llama3.1:8b")
            mem.save_fact("config", "provider", "ollama", source="user")
            return (
                f"RAZ: Switched to Ollama — {model}.\n"
                f"If Ollama isn't installed yet:\n"
                f"  1. Download from https://ollama.com/download (Windows installer)\n"
                f"  2. After install, open a terminal and run: ollama pull {model}\n"
                f"  3. Send any message here to test.\n"
                f"Your RTX 5090 can run 70B models. Try: /sys provider ollama llama3.3:70b"
            )

        return f"RAZ: Unknown provider '{new_provider}'. Options: openai, groq, ollama"

    def _handle_sys(self, parts: list) -> str:
        """Handle /sys subcommands."""
        from core.system_control import (
            get_system_snapshot, format_snapshot_summary,
            get_top_processes, run_command, run_optimization_scan,
            list_directory, read_file_content, register_startup, unregister_startup
        )
        sub = parts[1].lower() if len(parts) > 1 else "stats"

        if sub == "stats":
            snap = get_system_snapshot()
            return "RAZ:\n" + format_snapshot_summary(snap)

        elif sub == "top":
            procs = get_top_processes(limit=10, sort_by="cpu")
            lines = ["RAZ: Top Processes by CPU:"]
            for p in procs:
                lines.append(f"  PID {p['pid']:6} | {p.get('cpu_percent',0):5.1f}% CPU | {p.get('memory_percent',0):4.1f}% RAM | {p.get('name','')}")
            return "\n".join(lines)

        elif sub == "scan":
            opt = run_optimization_scan()
            lines = [f"RAZ: System Health Score: {opt['score']}/100"]
            for r in opt["recommendations"]:
                lines.append(f"  - {r}")
            return "\n".join(lines)

        elif sub == "run":
            if len(parts) < 3:
                return "RAZ: Usage: /sys run <command>"
            cmd_str = " ".join(parts[2:])
            result = run_command(cmd_str)
            out = result.get("stdout") or result.get("stderr") or "(no output)"
            return f"RAZ: [{result['returncode']}] {cmd_str}\n{out}"

        elif sub == "ls":
            path = " ".join(parts[2:]) if len(parts) > 2 else BASE_DIR
            items = list_directory(path)
            lines = [f"RAZ: {path}"]
            for item in items:
                icon = "D" if item.get("type") == "dir" else "F"
                lines.append(f"  [{icon}] {item.get('name'):40} {item.get('size_kb',0):8.1f} KB  {item.get('modified','')}")
            return "\n".join(lines)

        elif sub == "read":
            path = " ".join(parts[2:]) if len(parts) > 2 else ""
            if not path:
                return "RAZ: Usage: /sys read <filepath>"
            content = read_file_content(path)
            return f"RAZ: {path}\n{content}"

        elif sub == "startup":
            result = register_startup()
            return f"RAZ: {result}"

        elif sub == "unstartup":
            result = unregister_startup()
            return f"RAZ: {result}"

        elif sub == "browse":
            # /sys browse <url> -- <action instructions>
            # e.g. /sys browse https://proton.me/mail/signup -- fill username=razcore password=Xk9m#2pL
            if len(parts) < 3:
                return "RAZ: Usage: /sys browse <url> [-- fill field=value click=ButtonText]"
            rest = " ".join(parts[2:])
            url_part = rest.split("--")[0].strip()
            inst_part = rest.split("--")[1].strip() if "--" in rest else ""
            actions = [{"type": "screenshot"}]
            for token in inst_part.split():
                if "=" in token:
                    k, v = token.split("=", 1)
                    if k == "fill":
                        actions.append({"type": "fill", "selector": v.split(":")[0], "value": v.split(":")[1] if ":" in v else v})
                    elif k == "click":
                        actions.append({"type": "click", "selector": v})
            from core.browser_agent import browse_and_fill
            result = browse_and_fill(url_part, actions, headless=False)
            lines = [f"RAZ: Browser agent {'OK' if result['ok'] else 'ERROR'}"]
            lines += [f"  {log_line}" for log_line in result["log"]]
            if result["error"]:
                lines.append(f"  Error: {result['error']}")
            return "\n".join(lines)

        elif sub == "proton":
            # /sys proton <username> <password>
            if len(parts) < 4:
                return "RAZ: Usage: /sys proton <username> <password>"
            uname = parts[2]
            pwd   = parts[3]
            from core.browser_agent import proton_signup
            result = proton_signup(uname, pwd)
            lines = [f"RAZ: Proton signup {'completed' if result['ok'] else 'stopped'}"]
            lines += [f"  {log_line}" for log_line in result["log"]]
            if result["error"]:
                lines.append(f"  Error: {result['error']}")
            return "\n".join(lines)

        elif sub == "provider":
            return self._handle_sys_provider(parts)

        elif sub == "keys":
            # /sys keys
            # /sys keys set <openai|groq|gemini> <key>
            # /sys keys clear <openai|groq|gemini>
            from system.config_loader import get_api_key_statuses, set_api_key

            tail = parts[2].strip() if len(parts) > 2 else ""
            tokens = tail.split() if tail else []

            if not tokens:
                statuses = get_api_key_statuses()
                return (
                    "RAZ: API key status (secure storage)\n"
                    f"  openai: {'🟢 set' if statuses.get('openai') else '🔴 missing'}\n"
                    f"  groq:   {'🟢 set' if statuses.get('groq') else '🔴 missing'}\n"
                    f"  gemini: {'🟢 set' if statuses.get('gemini') else '🔴 missing'}\n\n"
                    "Manage with:\n"
                    "  /sys keys set openai sk-...\n"
                    "  /sys keys set groq gsk_...\n"
                    "  /sys keys set gemini AIza...\n"
                    "  /sys keys clear <provider>"
                )

            action = tokens[0].lower()
            if action not in ("set", "clear"):
                return "RAZ: Usage: /sys keys [set|clear] <openai|groq|gemini> [key]"

            provider = tokens[1].lower() if len(tokens) >= 2 else ""
            if provider not in ("openai", "groq", "gemini"):
                return "RAZ: Provider must be one of: openai, groq, gemini"

            if action == "clear":
                ok = set_api_key(provider, "")
                return f"RAZ: {provider} key {'cleared' if ok else 'not updated'}"

            # set
            if len(tokens) < 3:
                return "RAZ: Usage: /sys keys set <openai|groq|gemini> <api_key>"
            api_key = tail.split(None, 2)[2].strip()
            ok = set_api_key(provider, api_key)
            if not ok:
                return f"RAZ: Could not save {provider} key"
            masked = f"***{api_key[-4:]}" if len(api_key) >= 4 else "(saved)"
            return f"RAZ: {provider} key saved to secure storage: {masked}"

        return f"RAZ: Unknown /sys sub-command: {sub}. Options: stats, top, scan, run, ls, read, startup, unstartup, browse, proton, provider, keys"

    def _cleanup(self):
        """Clean up session on exit."""
        if self.history:
            summary_msgs = self.history + [{"role": "user", "content": "Briefly summarize this session in 2-3 sentences."}]
            try:
                summary = self._call_llm(summary_msgs)
            except Exception:
                summary = f"Session {self.session_id} - {len(self.history)} messages exchanged."
            mem.end_session(self.session_id, summary=summary)
        else:
            mem.end_session(self.session_id, summary="Session ended with no messages.")

    def chat(self, user_input: str) -> str:
        """Process a user input and return RAZ's response."""
        user_input = user_input.strip()
        if not user_input:
            return ""

        if user_input.startswith("/"):
            response = self._handle_command(user_input)
            if user_input.startswith("/exit"):
                return response
            return response

        # Store message in DB
        mem.save_message(self.session_id, "user", user_input)
        self.history.append({"role": "user", "content": user_input})

        # Check for meeting keywords
        if self.mode == "meeting":
            lower = user_input.lower()
            if "decision:" in lower or "we decided" in lower or "agreed to" in lower:
                self.meeting_decisions.append(user_input)
            if "action:" in lower or "will do" in lower or "next step" in lower or "follow up" in lower:
                self.meeting_actions.append(user_input)
            if "summarize meeting" in lower:
                return self._handle_command("/summarize")

        # Call LLM
        response = self._call_llm(self.history)

        # Auto-execute any /sys run commands RAZ embedded in its response
        response = self._execute_embedded_commands(response)

        # Auto-log incomplete/failed actions so they show in task memory later.
        followup_task_id = self._auto_log_followup_if_needed(user_input, response)
        if followup_task_id:
            response += (
                f"\n\n[Auto-logged follow-up task #{followup_task_id} "
                f"for this incomplete request. Use /followups to review.]"
            )

        # Store response
        mem.save_message(self.session_id, "assistant", response)
        self.history.append({"role": "assistant", "content": response})

        return response

    def _execute_embedded_commands(self, response: str) -> str:
        """
        Scan RAZ's LLM response for embedded `/sys run <cmd>` in backticks.
        Execute each one and replace the backtick placeholder with the real output.
        Also handles `/sys open <url>` for reliable browser launching.
        """
        import re
        from core.system_control import run_command, open_url

        # Handle /sys open <url> - uses smart browser finder
        open_pattern = re.compile(r'`?(/sys open (https?://[^`\s]+))`?')
        def _open_url(match):
            url = match.group(2).strip()
            result = open_url(url)
            out = result.get("stdout") or result.get("stderr") or "(launched)"
            return f"`/sys open {url}`\n>>> {out}"
        response = open_pattern.sub(_open_url, response)

        # Handle /sys run <cmd>
        pattern = re.compile(r'`?(/sys run ([^`\n]+))`?')
        def _run_and_replace(match):
            full_cmd_text = match.group(1).strip()
            shell_cmd     = match.group(2).strip()
            # If it looks like a URL, use open_url instead
            if shell_cmd.lower().startswith(("http://", "https://")):
                result = open_url(shell_cmd)
            else:
                result = run_command(shell_cmd)
            stdout = (result.get("stdout") or "").strip()
            stderr = (result.get("stderr") or "").strip()
            rc     = result.get("returncode", -1)
            output = stdout or stderr or "(command ran)"
            if rc != 0 and stderr and not stdout:
                output = f"Error: {stderr}"
            return f"`{full_cmd_text}`\n>>> {output}"
        return pattern.sub(_run_and_replace, response)

    def _stream_response(self, user_input: str):
        """
        Generator: yields LLM text chunks live using OpenAI Function Calling (tool use).

        AGENTIC LOOP — this is how real AI bots work:
        1. Send user message + list of available tools to the LLM
        2. If LLM wants to run a tool → execute the real Python function
        3. Feed the real result back to the LLM
        4. Repeat until LLM is done (finish_reason == "stop")

        RAZ cannot hallucinate actions — it either gets real output or admits failure.
        """
        user_input = user_input.strip()
        if not user_input:
            return

        mem.save_message(self.session_id, "user", user_input)
        self.history.append({"role": "user", "content": user_input})

        self._try_connect_client()
        if not self.client:
            yield "RAZ: [LLM not connected. Add OPENAI_API_KEY to system/config.json]"
            return

        try:
            from core.tools import TOOL_SCHEMAS, dispatch_tool

            self._refresh_system_prompt()
            cfg         = load_config()
            model       = self._get_model()
            max_tokens  = cfg.get("max_tokens", 2048)
            temperature = cfg.get("temperature", 0.7)
            provider    = cfg.get("provider", "openai").strip().lower()
            fallback    = self._get_fallback_provider(cfg, provider)

            # Only catch clear model-identity refusals — NOT topic-specific help phrases
            # that also appear in legitimate answers (e.g. "I can't assist" appears in
            # "I can't assist with X alone, here's the full solution" type responses).
            REFUSAL_PHRASES = [
                "as an ai, i cannot", "as an ai, i am not able", "as an ai language model",
                "i must decline", "i cannot and will not", "i can't and won't",
                "against my guidelines", "against my programming",
                "i have to decline", "i must refuse",
                "i am programmed to avoid", "my programming prevents",
                "i apologize, but i cannot assist with this",
                "i'm sorry, but i cannot assist with that",
                "i'm not able to help with that",
            ]

            # Working message list for this turn's agentic loop
            # (separate from self.history so intermediate tool messages don't pollute future turns)
            messages = [{"role": "system", "content": self.system_prompt}] + list(self.history)

            # Tool calling works on OpenAI and Groq; Ollama support varies by model
            use_tools = provider in ("openai", "groq")

            MAX_TOOL_ROUNDS = 8  # safety cap — prevents infinite tool call loops

            for _round in range(MAX_TOOL_ROUNDS + 1):
                try:
                    stream, model = self._create_chat_completion(
                        client=self.client,
                        cfg=cfg,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=True,
                        tools=TOOL_SCHEMAS if use_tools else None,
                        tool_choice="auto" if use_tools else None,
                        model_override=model,
                    )
                except Exception as e:
                    if self._should_fallback_for_error(provider, fallback, e):
                        yield "\x00OVERRIDE\x00"
                        yield from self._stream_fallback(user_input, fallback, cfg)
                        return
                    raise

                # Accumulate this streaming pass
                text_chunks   = []
                tool_calls_acc = {}   # index → {id, name, arguments}
                finish_reason = None
                refusal_buf   = ""
                refusal_done  = (_round > 0)  # only check refusal on the very first pass

                for evt in stream:
                    choice = evt.choices[0]
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

                    delta = choice.delta

                    # ── Accumulate tool call fragments ────────────────────────
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc_delta.id:
                                tool_calls_acc[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_acc[idx]["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

                    # ── Stream text chunks ────────────────────────────────────
                    if delta.content:
                        if not refusal_done:
                            refusal_buf += delta.content
                            if len(refusal_buf) >= 350:
                                refusal_done = True
                                if fallback and any(p in refusal_buf.lower() for p in REFUSAL_PHRASES):
                                    yield "\x00OVERRIDE\x00"
                                    yield from self._stream_fallback(user_input, fallback, cfg)
                                    return
                                else:
                                    text_chunks.append(refusal_buf)
                                    yield refusal_buf
                        else:
                            text_chunks.append(delta.content)
                            yield delta.content

                # Handle short response that never filled the refusal buffer
                if not refusal_done and refusal_buf:
                    if fallback and _round == 0 and any(p in refusal_buf.lower() for p in REFUSAL_PHRASES):
                        yield "\x00OVERRIDE\x00"
                        yield from self._stream_fallback(user_input, fallback, cfg)
                        return
                    text_chunks.append(refusal_buf)
                    yield refusal_buf

                # ── Tool calls requested ──────────────────────────────────────
                if finish_reason == "tool_calls" and tool_calls_acc:
                    text_so_far = "".join(text_chunks)

                    # Build the proper tool_calls list for the assistant message
                    tool_calls_list = [
                        {
                            "id":   tc["id"],
                            "type": "function",
                            "function": {
                                "name":      tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                        for tc in (tool_calls_acc[i] for i in sorted(tool_calls_acc))
                    ]

                    # Append the assistant's "I want to call these tools" message
                    messages.append({
                        "role":       "assistant",
                        "content":    text_so_far or None,
                        "tool_calls": tool_calls_list,
                    })

                    # Execute every requested tool and feed results back
                    for tc in tool_calls_list:
                        name = tc["function"]["name"]
                        raw  = tc["function"]["arguments"]
                        try:
                            args   = json.loads(raw) if raw.strip() else {}
                            result = dispatch_tool(name, args)
                        except Exception as e:
                            result = f"Tool error: {type(e).__name__}: {e}"
                            try:
                                device = self.config.get("device_name", "unknown")
                                mem.log_followup_issue(
                                    user_request=user_input,
                                    reason=f"Tool execution failed: {name}",
                                    context=f"args={raw[:500]} | error={type(e).__name__}: {e}",
                                    source_device=device,
                                    priority="high",
                                )
                            except Exception:
                                pass

                        result_str = str(result)

                        # Show Ryan what's happening — live in the chat
                        preview = result_str[:300].replace("\n", " ")
                        yield f"\n\n⚙ **{name}** → `{preview}`\n\n"

                        # Feed the real result back to the LLM
                        messages.append({
                            "role":         "tool",
                            "tool_call_id": tc["id"],
                            "content":      result_str[:8000],  # cap to avoid token overflow
                        })

                    # Loop back: LLM will now respond using the real tool results
                    continue

                else:
                    # finish_reason == "stop" — LLM is done
                    break

        except Exception as e:
            try:
                device = self.config.get("device_name", "unknown")
                mem.log_followup_issue(
                    user_request=user_input,
                    reason=f"Streaming response error: {e}",
                    context="_stream_response exception",
                    source_device=device,
                    priority="high",
                )
            except Exception:
                pass
            yield f"RAZ: [Stream error: {e}]"

    def _stream_fallback(self, user_input: str, fallback_provider: str, cfg: dict):
        """Stream from fallback provider (Groq/Ollama) after OpenAI refused."""
        try:
            from openai import OpenAI as _OAI
            if fallback_provider == "groq":
                client, model = self._build_client_for_provider("groq", cfg)
                if not client:
                    yield "[Groq key not set — type /sys provider groq YOUR_KEY]"
                    return
            elif fallback_provider == "openai":
                client, model = self._build_client_for_provider("openai", cfg)
                if not client:
                    yield "[OpenAI key not set — type /sys provider openai YOUR_KEY]"
                    return
            elif fallback_provider == "ollama":
                client, model = self._build_client_for_provider("ollama", cfg)
            else:
                yield "[Unknown fallback provider]"
                return

            stream, _ = self._create_chat_completion(
                client=client,
                cfg=cfg,
                messages=[{"role": "system", "content": self.system_prompt}] + self.history,
                max_tokens=cfg.get("max_tokens", 2048),
                temperature=cfg.get("temperature", 0.7),
                stream=True,
                provider_override=fallback_provider,
                model_override=model,
            )
            for evt in stream:
                delta = evt.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"[Fallback error: {e}]"

    def _stream_response_with_image(self, user_input: str, image_path: str):
        """Generator: sends text + image to GPT-4o vision, yields streamed chunks."""
        import base64
        user_input = user_input.strip()

        # Encode image
        ext  = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}.get(ext, "image/png")
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            yield f"[Could not load image: {e}]"
            return

        mem.save_message(self.session_id, "user", f"{user_input} [image: {os.path.basename(image_path)}]")
        self.history.append({"role": "user", "content": user_input or "Analyze this image."})

        self._try_connect_client()
        if not self.client:
            yield "RAZ: [LLM not connected. Add OPENAI_API_KEY to system/config.json]"
            return

        try:
            self._refresh_system_prompt()
            cfg         = load_config()
            # Vision requires gpt-4o when on OpenAI; use active provider model otherwise
            provider = cfg.get("provider", "openai").strip().lower()
            model    = "gpt-4o" if provider == "openai" else self._get_model()
            max_tokens  = cfg.get("max_tokens", 2048)
            temperature = cfg.get("temperature", 0.7)

            vision_message = {
                "role": "user",
                "content": [
                    {"type": "text",      "text": user_input or "What do you see?"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }

            # Build message list: system prompt + history (minus last user msg) + vision message
            base_history = [m for m in self.history[:-1]]
            full_messages = ([{"role": "system", "content": self.system_prompt}]
                             + base_history
                             + [vision_message])

            stream = self.client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            for evt in stream:
                delta = evt.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"RAZ: [Vision error: {e}]"

    def _looks_incomplete_or_failed(self, text: str) -> bool:
        if not text:
            return False
        lower = text.lower()
        signals = [
            "could not",
            "unable to",
            "failed",
            "error",
            "not connected",
            "path not found",
            "tool error",
            "stream error",
            "llm error",
            "usage:",
            "unknown command",
            "unknown /sys",
        ]
        return any(sig in lower for sig in signals)

    def _auto_log_followup_if_needed(self, user_input: str, response: str):
        """Return new task_id when RAZ response indicates incomplete execution."""
        if not user_input or user_input.startswith("/"):
            return None
        if not self._looks_incomplete_or_failed(response):
            return None
        try:
            device = self.config.get("device_name", "unknown")
            issue = mem.log_followup_issue(
                user_request=user_input,
                reason="RAZ response indicates incomplete execution",
                context=response[:700],
                source_device=device,
                priority="high",
            )
            return issue.get("task_id")
        except Exception:
            return None

    def _finalize_response(self, full_text: str) -> str:
        """Post-stream: execute embedded commands, save assistant message to memory, auto-extract facts."""
        final = self._execute_embedded_commands(full_text)

        # For streamed desktop interactions, auto-create follow-up tasks on failures.
        try:
            last_user = next((m["content"] for m in reversed(self.history) if m["role"] == "user"), "")
            followup_task_id = self._auto_log_followup_if_needed(last_user, final)
            if followup_task_id:
                final += (
                    f"\n\n[Auto-logged follow-up task #{followup_task_id} "
                    f"for this incomplete request. Use /followups to review.]"
                )
        except Exception:
            pass

        mem.save_message(self.session_id, "assistant", final)
        self.history.append({"role": "assistant", "content": final})
        # Auto-extract any important facts from the conversation
        if self.history:
            last_user = next(
                (m["content"] for m in reversed(self.history) if m["role"] == "user"), ""
            )
            self._auto_extract_facts(last_user, final)
        return final

    def _auto_extract_facts(self, user_msg: str, raz_msg: str):
        """
        Scan the conversation for key facts worth remembering:
        email addresses, account creations, passwords, URLs, decisions.
        Saves to memory DB so RAZ recalls them in future sessions.
        """
        import re
        combined = user_msg + " " + raz_msg

        # Email addresses
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', combined)
        for email in emails:
            mem.save_fact("accounts", f"email_{email.split('@')[0]}", email, source="auto_extracted")

        # ProtonMail account creation patterns
        if any(k in combined.lower() for k in ["proton", "protonmail", "@proton.me"]):
            if any(k in combined.lower() for k in ["created", "signup", "account", "registered"]):
                proton_usernames = re.findall(r'([\w.+-]+)@proton\.me', combined)
                for u in proton_usernames:
                    mem.save_fact("accounts", "protonmail_username", f"{u}@proton.me", source="auto_extracted")
                    mem.save_fact("accounts", "protonmail_url", "https://proton.me", source="auto_extracted")

        # Any "created account" or "account for" statements
        account_patterns = re.findall(
            r'(?:created|made|set up|registered)[^.]*?(?:account|email|profile)[^.]*?(?:for|on|at)?[^.]*?([\w.]+\.(?:com|me|io|org|net))',
            combined, re.IGNORECASE
        )
        for site in account_patterns:
            mem.save_fact("actions", f"created_account_{site}",
                         f"Created account on {site} - {datetime.now().strftime('%Y-%m-%d')}",
                         source="auto_extracted")

        # URLs mentioned
        urls = re.findall(r'https?://[^\s`>"\)\]\}]+', combined)
        for url in urls[:3]:  # cap at 3 per message
            url = url.rstrip(".),;'")
            domain = url.split("//")[-1].split("/")[0]
            mem.save_fact("web", f"visited_{domain}", url, source="auto_extracted")

        # Password patterns — route to SECURE storage only, never save plaintext in DB
        if "/sys proton" in user_msg:
            parts = user_msg.split()
            for i, p in enumerate(parts):
                if p == "/sys" and len(parts) > i+3 and parts[i+1] == "proton":
                    uname = parts[i+2]
                    pwd   = parts[i+3]
                    from system.secure_secrets import set_secret
                    set_secret(f"protonmail_{uname}", pwd)
                    mem.save_fact("accounts", "protonmail_username", f"{uname}@proton.me", source="user_provided")

    def run(self):
        """Run the interactive chat loop in the terminal."""
        _clear_terminal_screen()
        print("=" * 60)
        print("  RAZ CORE v1.0 - Personal AI Operating System")
        print(f"  Session: {self.session_id} | Mode: {self.mode}")
        print(f"  {datetime.now().strftime('%A, %B %d %Y  %I:%M %p')}")
        print("=" * 60)
        print("  Type /help for commands. Type /exit to quit.")
        print()

        while True:
            try:
                user_input = input("YOU: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nRAZ: Session closing. Logging out.")
                self._cleanup()
                break

            if not user_input:
                continue

            response = self.chat(user_input)
            if response:
                print(f"\n{response}\n")


if __name__ == "__main__":
    raz = RAZChat()
    raz.run()
