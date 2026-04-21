"""
RAZ Core - Desktop App
PySide6 GUI: dark theme, neon red, clean chat interface.
"""

import sys
import os
import socket
import threading
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

TABLET_MODE = str(os.environ.get("RAZ_TABLET_MODE", "0")).strip().lower() in ("1", "true", "yes", "tablet")
APP_NAME = "RAZ Tablet" if TABLET_MODE else "RAZ Core"
APP_SHORTCUT_NAME = "RAZ Tablet.lnk" if TABLET_MODE else "RAZ Core.lnk"
APP_DESCRIPTION = "RAZ Tablet - Touch-optimized Personal AI" if TABLET_MODE else "RAZ Core - Ryan A. Wallace Personal AI"
APP_ICON_FILE = "raz_tablet.ico" if TABLET_MODE else "raz.ico"

# ── Single-instance lock (bind a local socket on a fixed port) ───────────────
_INSTANCE_PORT = 54322 if TABLET_MODE else 54321
_instance_lock_sock = None
_emerge_callback = None  # set by main() after window is created

def acquire_instance_lock() -> bool:
    """
    Try to bind a local socket. If we succeed we're the only instance.
    If binding fails another RAZ is already running — return False.
    """
    global _instance_lock_sock
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", _INSTANCE_PORT))
        s.listen(5)
        _instance_lock_sock = s
        return True
    except OSError:
        return False

def signal_running_instance() -> bool:
    """Connect to the running instance and send RAZ_EMERGE. Returns True if sent."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", _INSTANCE_PORT))
        s.sendall(b"RAZ_EMERGE")
        s.close()
        return True
    except Exception:
        return False

def start_emerge_listener(callback):
    """Background thread: accept connections on lock socket and fire callback on RAZ_EMERGE."""
    global _emerge_callback
    _emerge_callback = callback
    def _loop():
        global _instance_lock_sock
        while _instance_lock_sock:
            try:
                conn, _ = _instance_lock_sock.accept()
                data = conn.recv(64).decode("utf-8", errors="ignore").strip()
                conn.close()
                if data == "RAZ_EMERGE" and _emerge_callback:
                    _emerge_callback()
            except Exception:
                break
    t = threading.Thread(target=_loop, daemon=True)
    t.start()

def get_build_meta_line(version: str) -> str:
    """Return a compact build metadata string for the header/title."""
    build_info_path = os.path.join(BASE_DIR, "system", "build_info.json")
    try:
        import json as _json
        if os.path.exists(build_info_path):
            # PowerShell may emit a UTF-8 BOM; utf-8-sig handles both BOM and non-BOM files.
            with open(build_info_path, "r", encoding="utf-8-sig") as f:
                info = _json.load(f)
            build_version = str(info.get("version") or version)
            build_time = str(info.get("build_time_local") or info.get("build_time_utc") or "unknown")
            return f"Build v{build_version} @ {build_time}"
    except Exception:
        pass
    return f"Build v{version} @ unknown"

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel, QComboBox, QFrame,
    QSizePolicy, QScrollArea, QTabWidget, QMessageBox, QTextBrowser,
    QPlainTextEdit,
    QFileDialog, QCheckBox, QSpinBox, QColorDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon, QImage, QKeySequence, QPixmap

from system.config_loader import load_config, save_config
from system.config_loader import get_api_key_statuses
from system.version_logger import init_version, get_version
import core.memory_engine as mem

# ── Colors ──────────────────────────────────────────────────────────────────
BG_DEEP    = "#000000"
BG_PANEL   = "#040a04"
BG_INPUT   = "#060d06"
NEON_RED   = "#00ff41"   # matrix green is the new red
NEON_DIM   = "#008f11"
TEXT_MAIN  = "#a8ffa8"
TEXT_DIM   = "#3a6b3a"
TEXT_USER  = "#e0ffe0"
BORDER     = "#003300"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_MAIN};
    font-family: 'Consolas', 'Courier New', monospace;
}}
QTextEdit {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: {NEON_DIM};
}}
QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_USER};
    border: 1px solid {NEON_DIM};
    border-radius: 4px;
    padding: 10px 14px;
    font-size: 14px;
}}
QLineEdit:focus {{
    border: 1px solid {NEON_RED};
}}
QPushButton {{
    background-color: {NEON_DIM};
    color: {TEXT_USER};
    border: none;
    border-radius: 4px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {NEON_RED};
}}
QPushButton:disabled {{
    background-color: #2a0020;
    color: {TEXT_DIM};
}}
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
    min-width: 100px;
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    selection-background-color: {NEON_DIM};
    border: 1px solid {BORDER};
}}
QLabel {{
    color: {TEXT_DIM};
    font-size: 11px;
}}
QFrame#divider {{
    background-color: {BORDER};
    max-height: 1px;
}}
QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {NEON_DIM};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

# ── Random neon color generator ─────────────────────────────────────────────
import random
import colorsys

# Kept for any code that still references the name
RAINBOW_COLORS = [
    "#ff0040", "#ff6600", "#ffff00", "#00ff41",
    "#00ffff", "#bf00ff", "#ff00aa", "#ffffff",
]

def _random_neon() -> str:
    """Generate truly unpredictable neon colors - all over the spectrum, wildly varied."""
    # Pick a strategy randomly to ensure real chaos
    strategy = random.randint(0, 5)
    if strategy == 0:
        # Pure saturated random hue
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
    elif strategy == 1:
        # Neon with slight white mix
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, 0.6 + random.random() * 0.4, 1.0)
    elif strategy == 2:
        # Random pastel-neon hybrid
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, 0.4 + random.random() * 0.6, 0.85 + random.random() * 0.15)
    elif strategy == 3:
        # Pure RGB channel blast - one channel maxed, others random
        ch = random.randint(0, 2)
        vals = [random.random() * 0.4, random.random() * 0.4, random.random() * 0.4]
        vals[ch] = 1.0
        r, g, b = vals[0], vals[1], vals[2]
    elif strategy == 4:
        # Two channels maxed
        channels = random.sample([0, 1, 2], 2)
        vals = [random.random() * 0.2, random.random() * 0.2, random.random() * 0.2]
        for c in channels:
            vals[c] = 0.8 + random.random() * 0.2
        r, g, b = vals[0], vals[1], vals[2]
    else:
        # Ultra bright near-white neon
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, 0.2 + random.random() * 0.3, 1.0)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


READABILITY_FONTS = [
    "Segoe UI",
    "Verdana",
    "Tahoma",
    "Arial",
    "Calibri",
    "Trebuchet MS",
    "Georgia",
    "Consolas",
]

FONT_PRESETS = {
    "High Readability": ["Segoe UI", "Verdana", "Tahoma", "Arial", "Calibri"],
    "Executive Clean": ["Calibri", "Segoe UI", "Trebuchet MS", "Arial"],
    "Focus Serif": ["Georgia", "Trebuchet MS", "Verdana", "Segoe UI"],
    "Code Fast": ["Consolas", "Segoe UI", "Verdana", "Tahoma"],
    "Creative Blend": ["Trebuchet MS", "Georgia", "Segoe UI", "Calibri"],
}

# Mood presets for emphasis bounce colors (WARNING / CAUTION / IMPORTANT lines)
# Each entry: (color1, color2, color3)
EMPHASIS_MOODS = {
    "Danger Fire":    ("#ff2200", "#ff6600", "#ffaa00"),
    "Sunset Alert":   ("#ffaa00", "#ff4400", "#ff0055"),
    "Nuclear":        ("#ffff00", "#ff8800", "#ff0000"),
    "Arctic Warning": ("#00eeff", "#00aaff", "#ffffff"),
    "Toxic":          ("#aaff00", "#00ff00", "#ffff00"),
    "Purple Storm":   ("#ff00ff", "#aa00ff", "#ff0088"),
    "Blood Moon":     ("#ff0033", "#cc0066", "#ff3300"),
    "Gold Alert":     ("#ffd700", "#ffaa00", "#ff8800"),
    "Ice Blue":       ("#00ccff", "#0088ff", "#00ffcc"),
    "Custom":         None,
}

COMPREHENSION_TEST_BANK = [
    {
        "passage": (
            "Strategic thinking is not about doing more tasks. It is about choosing "
            "the single move that changes multiple outcomes at once. High performers "
            "protect focus, sequence actions, and remove friction before scaling effort."
        ),
        "questions": [
            {
                "q": "What does the passage say strategic thinking is mainly about?",
                "options": [
                    "Completing many tasks quickly",
                    "Choosing leverage moves",
                    "Working longer hours",
                    "Avoiding all risk",
                ],
                "answer": 1,
            },
            {
                "q": "What do high performers protect first?",
                "options": ["Focus", "Budget", "Tools", "Delegation"],
                "answer": 0,
            },
            {
                "q": "Before scaling effort, they remove what?",
                "options": ["Marketing", "Friction", "Competition", "Meetings"],
                "answer": 1,
            },
        ],
    },
    {
        "passage": (
            "Clear communication improves execution speed. Teams move faster when goals, "
            "owners, and deadlines are explicit. Ambiguity creates rework, while specificity "
            "creates accountability and momentum."
        ),
        "questions": [
            {
                "q": "What improves execution speed according to the passage?",
                "options": ["More meetings", "Clear communication", "Larger teams", "Longer timelines"],
                "answer": 1,
            },
            {
                "q": "Which three items should be explicit?",
                "options": ["Goals, owners, deadlines", "Budget, hiring, legal", "Brand, design, copy", "Features, ads, channels"],
                "answer": 0,
            },
            {
                "q": "Specificity creates what?",
                "options": ["Ambiguity", "Accountability and momentum", "Delay", "Uncertainty"],
                "answer": 1,
            },
        ],
    },
]


def _load_raz_font(size: int = 13) -> "QFont":
    """Download and load Playfair Display. Falls back to Georgia."""
    import urllib.request
    from PySide6.QtGui import QFontDatabase

    font_path = os.path.join(BASE_DIR, "assets", "PlayfairDisplay-Regular.ttf")
    if not os.path.exists(font_path):
        try:
            os.makedirs(os.path.join(BASE_DIR, "assets"), exist_ok=True)
            url = "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/static/PlayfairDisplay-Regular.ttf"
            urllib.request.urlretrieve(url, font_path)
        except Exception:
            font_path = None

    if font_path and os.path.exists(font_path):
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    return QFont(families[0], size)
        except Exception:
            pass

    return QFont("Georgia", size)


class LLMWorker(QThread):
    """Runs LLM call in background — streams tokens live to the UI."""
    partial  = Signal(str)   # each streamed chunk
    finished = Signal(str)   # full processed response
    error    = Signal(str)
    override = Signal()      # emitted when OpenAI refused and Groq took over

    def __init__(self, raz_chat, user_input, image_path=None):
        super().__init__()
        self.raz_chat   = raz_chat
        self.user_input = user_input
        self.image_path = image_path

    def run(self):
        try:
            if self.user_input.startswith("/") and not self.image_path:
                # Slash commands: instant, no streaming
                response = self.raz_chat.chat(self.user_input)
                self.finished.emit(response)
            elif self.image_path:
                # Vision: image + text
                full_text = ""
                for chunk in self.raz_chat._stream_response_with_image(
                    self.user_input or "Analyze this image and describe what you see.",
                    self.image_path
                ):
                    full_text += chunk
                    self.partial.emit(chunk)
                final = self.raz_chat._finalize_response(full_text)
                self.finished.emit(final)
            else:
                # LLM response: stream chunks then finalize
                full_text = ""
                for chunk in self.raz_chat._stream_response(self.user_input):
                    if chunk == "\x00OVERRIDE\x00":
                        self.override.emit()  # signal UI to show badge
                    else:
                        full_text += chunk
                        self.partial.emit(chunk)
                final = self.raz_chat._finalize_response(full_text)
                self.finished.emit(final)
        except Exception as e:
            self.error.emit(str(e))


class SecretBrainWorker(QThread):
    """Runs Secret Brain ingestion + profile build in background."""
    progress = Signal(str)
    finished = Signal(dict)
    error    = Signal(str)

    def __init__(self, force_refresh: bool = False):
        super().__init__()
        self.force_refresh = force_refresh

    def run(self):
        try:
            from core.secret_brain import ingest_secret_brain, build_ryan_profile
            self.progress.emit("Scanning Secret Brain folder...")
            results = ingest_secret_brain(force_refresh=self.force_refresh)
            self.progress.emit("Building profile analysis...")
            profile = build_ryan_profile()
            results["profile"] = profile
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MentorWorker(QThread):
    """Runs an AI mentor question against the Secret Brain profile."""
    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, raz_chat, question: str):
        super().__init__()
        self.raz_chat = raz_chat
        self.question = question

    def run(self):
        try:
            from core.secret_brain import get_profile_summary
            profile_text = get_profile_summary()
            mentor_prompt = (
                "You are acting as RAZ, Ryan's personal mentor and analyst. "
                "You have access to Ryan's complete Secret Brain profile below. "
                "Respond with deep insight, direct guidance, and genuine care. "
                "Be like the best coach Ryan never had. No fluff. Just signal.\n\n"
                f"RYAN'S PROFILE:\n{profile_text}\n\n"
                f"QUESTION: {self.question}"
            )
            response = self.raz_chat.chat(mentor_prompt)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class VoiceConversationWorker(QThread):
    """Continuous voice conversation loop for in-app hands-free mentoring."""
    heard = Signal(str)
    replied = Signal(str)
    status = Signal(str)
    error = Signal(str)
    finished = Signal(str)

    def __init__(self, raz_chat):
        super().__init__()
        self.raz_chat = raz_chat
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            from core.voice_engine import run_voice_once
            self.status.emit("Voice conversation started. Listening continuously...")
            while self._running:
                result = run_voice_once(self.raz_chat)
                if not result:
                    continue
                if result.startswith("RAZ VOICE captured:"):
                    # Expected format:
                    # RAZ VOICE captured: <heard text>
                    # RAZ: <assistant response>
                    heard_text = ""
                    reply_text = result
                    if "\nRAZ: " in result:
                        first, second = result.split("\nRAZ: ", 1)
                        heard_text = first.replace("RAZ VOICE captured:", "").strip()
                        reply_text = second.strip()
                    if heard_text:
                        self.heard.emit(heard_text)
                    if reply_text:
                        self.replied.emit(reply_text)
                else:
                    self.status.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        self.finished.emit("Voice conversation stopped.")


class VoiceOnceWorker(QThread):
    """Single-turn voice capture + response with explicit UI signals."""
    heard = Signal(str)
    replied = Signal(str)
    status = Signal(str)
    error = Signal(str)
    finished = Signal(str)

    def __init__(self, raz_chat):
        super().__init__()
        self.raz_chat = raz_chat

    def run(self):
        try:
            self.status.emit("Listening now... speak naturally.")
            self.status.emit("First run may take longer while voice model initializes.")
            from core.voice_engine import run_voice_once
            result = run_voice_once(self.raz_chat)

            if result and result.startswith("RAZ VOICE captured:") and "\nRAZ: " in result:
                heard_text, reply_text = result.split("\nRAZ: ", 1)
                heard_text = heard_text.replace("RAZ VOICE captured:", "").strip()
                reply_text = reply_text.strip()
                if heard_text:
                    self.heard.emit(heard_text)
                if reply_text:
                    self.replied.emit(reply_text)
            elif result and result.startswith("RAZ:"):
                self.replied.emit(result.replace("RAZ:", "", 1).strip())
            elif result:
                self.status.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        self.finished.emit("Voice turn complete.")


class SelfRepairWorker(QThread):
    """
    RAZ reads its own source code, identifies the bug Ryan described,
    applies patches, and signals the app to restart.
    """
    progress = Signal(str)
    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, raz_chat, description: str):
        super().__init__()
        self.raz_chat    = raz_chat
        self.description = description

    def run(self):
        try:
            self.progress.emit("Reading source files...")
            source_files = self._collect_source()

            self.progress.emit("Asking GPT-4o to diagnose and patch...")
            patches = self._ask_gpt(source_files)

            if not patches:
                self.finished.emit("No patches needed — GPT found nothing to fix.")
                return

            self.progress.emit(f"Applying {len(patches)} patch(es)...")
            applied, errors = self._apply_patches(patches)

            msg = f"Applied {applied} patch(es)"
            if errors:
                msg += f" ({errors} failed)"
            msg += ". Restarting RAZ now."
            self.finished.emit(msg)

        except Exception as e:
            self.error.emit(str(e))

    def _collect_source(self) -> dict:
        """Read all .py files in RAZ-Core, skip venvs and cache."""
        skip_dirs = {"__pycache__", "myenv", "Python", ".git",
                     "node_modules", "python-3.10.11-embed-amd64", ".venv"}
        files = {}
        for root, dirs, fnames in os.walk(BASE_DIR):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in fnames:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    rel   = os.path.relpath(fpath, BASE_DIR).replace("\\", "/")
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            files[rel] = f.read()
                    except Exception:
                        pass
        return files

    def _ask_gpt(self, source_files: dict) -> list:
        """Send all source + description to GPT-4o, get back JSON patches."""
        import json as _json, re as _re

        dump = ""
        for path, content in source_files.items():
            dump += f"\n\n=== FILE: {path} ===\n{content[:6000]}"  # cap per file

        prompt = (
            f'You are RAZ\'s self-repair AI. Ryan reported this problem:\n\n'
            f'  "{self.description}"\n\n'
            f'Here are all source files:\n{dump}\n\n'
            f'Reply with ONLY a valid JSON array of surgical patches. '
            f'Format:\n'
            f'[{{"file": "relative/path.py", "old_code": "EXACT text to replace", "new_code": "replacement"}}]\n'
            f'Be minimal. Only change what is necessary. If nothing needs fixing, return [].'
        )

        if not self.raz_chat or not self.raz_chat.client:
            raise RuntimeError("RAZ not connected to OpenAI.")

        response = self.raz_chat.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
        )
        text = response.choices[0].message.content.strip()
        match = _re.search(r'\[.*\]', text, _re.DOTALL)
        if match:
            try:
                return _json.loads(match.group())
            except Exception:
                return []
        return []

    def _apply_patches(self, patches: list) -> tuple:
        """Apply each patch in-place. Returns (applied_count, error_count)."""
        applied = 0
        errors  = 0
        for patch in patches:
            try:
                fpath = os.path.join(BASE_DIR, patch["file"].replace("/", os.sep))
                if not os.path.exists(fpath):
                    errors += 1
                    continue
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                old = patch["old_code"]
                new = patch["new_code"]
                if old in content:
                    content = content.replace(old, new, 1)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                    applied += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
        return applied, errors


class RAZDesktop(QMainWindow):
    _emerge_signal = Signal()  # emitted from emerge listener thread (thread-safe)

    def __init__(self):
        super().__init__()
        self.app_config = load_config()
        self.raz_chat        = None
        self.worker          = None
        self.connected       = False
        self._stream_started = False
        self._rainbow_pos    = 0
        self._raz_font       = _load_raz_font(13)
        self._pending_image  = None   # path to attached screenshot
        self._repair_worker  = None   # SelfRepairWorker thread
        self._voice_worker   = None   # Continuous voice conversation worker
        self._voice_once_worker = None # Single-turn voice worker
        self._sb_worker = None
        self._mentor_worker = None
        self._response_loading_timer = None
        self._response_loading_tick = 0
        self._emerge_signal.connect(self._show_emerge_dialog)
        self._load_preferences()
        self._init_raz()
        self._build_ui()
        self._sb_restore_cached_state()
        self._welcome()

    def _on_tab_changed(self, index: int):
        """Refresh Secret Brain immediately when its tab is selected."""
        try:
            if self.tabs.tabText(index) == "SECRET BRAIN":
                self._sb_restore_cached_state()
        except Exception:
            pass

    def _sb_restore_cached_state(self):
        """Load cached Secret Brain profile/docs immediately if they already exist."""
        try:
            from core.secret_brain import get_profile_summary
            profile_summary = get_profile_summary()
            lowered = profile_summary.lower()
            if "profile not built yet" not in lowered and "no secret brain data" not in lowered:
                self.sb_profile_display.setPlainText(profile_summary)
                self.sb_status_lbl.setText("SECRET BRAIN  —  Loaded from cache")
            self._sb_refresh_doc_list()
        except Exception:
            pass

    def _load_preferences(self):
        cfg = self.app_config or {}
        self.ui_font_preset = cfg.get("ui_font_preset", "High Readability")
        self.ui_font_family = cfg.get("ui_font_family", "Segoe UI")
        self.ui_primary_color = cfg.get("ui_primary_color", NEON_RED)
        self.ui_text_color = cfg.get("ui_text_color", TEXT_MAIN)
        self.ui_random_colors = bool(cfg.get("ui_random_word_colors", True))
        self.ui_serious_mode = bool(cfg.get("ui_serious_mode", False))
        self.ui_serious_color = cfg.get("ui_serious_color", "#9fffb8")
        self.ui_serious_bold = bool(cfg.get("ui_serious_bold", True))
        self.ui_serious_italic = bool(cfg.get("ui_serious_italic", False))
        # Emphasis bounce colors (WARNING / CAUTION / IMPORTANT lines)
        self.ui_emphasis_mode = bool(cfg.get("ui_emphasis_mode", True))
        self.ui_emphasis_mood = cfg.get("ui_emphasis_mood", "Sunset Alert")
        _mood_colors = EMPHASIS_MOODS.get(self.ui_emphasis_mood)
        self.ui_emphasis_color_1 = cfg.get("ui_emphasis_color_1", _mood_colors[0] if _mood_colors else "#ffaa00")
        self.ui_emphasis_color_2 = cfg.get("ui_emphasis_color_2", _mood_colors[1] if _mood_colors else "#ff4400")
        self.ui_emphasis_color_3 = cfg.get("ui_emphasis_color_3", _mood_colors[2] if _mood_colors else "#ff0055")
        # Resource alert thresholds
        self.cpu_alert_pct = int(cfg.get("cpu_alert_pct", 90))
        self.ram_alert_pct = int(cfg.get("ram_alert_pct", 90))
        self.disk_alert_pct = int(cfg.get("disk_alert_pct", 95))
        self.resource_alerts_enabled = bool(cfg.get("resource_alerts_enabled", True))
        self.comp_benchmark_rounds = int(cfg.get("ui_comp_benchmark_rounds", 3))
        self.comp_history = list(cfg.get("ui_comp_history", []))
        self._comprehension_current = None
        self._comprehension_started_at = None
        self._benchmark_active = False
        self._benchmark_round = 0
        self._benchmark_total = 0
        self._benchmark_results = []

        # Voice preferences map to env vars consumed by voice_engine.
        self.voice_model = cfg.get("voice_model", "base")
        self.voice_record_seconds = int(cfg.get("voice_record_seconds", 4))
        self.voice_beam_size = int(cfg.get("voice_beam_size", 1))
        self.voice_tts_rate = int(cfg.get("voice_tts_rate", 185))
        self._apply_voice_env_settings()

    def _init_raz(self):
        try:
            from core.chat import RAZChat
            self.raz_chat  = RAZChat()
            cfg            = load_config()
            provider = (cfg.get("provider", "openai") or "openai").strip().lower()
            if provider == "openai":
                self.connected = bool(cfg.get("openai_api_key", "").strip())
            elif provider == "groq":
                self.connected = bool(cfg.get("groq_api_key", "").strip())
            elif provider == "ollama":
                self.connected = True
            else:
                self.connected = bool(cfg.get("openai_api_key", "").strip())
        except Exception as e:
            self.connected = False

    def _build_ui(self):
        version = get_version()
        build_meta = get_build_meta_line(version)
        self.setWindowTitle(f"{APP_NAME} v{version}  |  {build_meta}")
        if TABLET_MODE:
            self.setMinimumSize(1024, 720)
            self.resize(1280, 820)
        else:
            self.setMinimumSize(860, 640)
            self.resize(1000, 720)
        self.setStyleSheet(STYLESHEET)
        icon_path = os.path.join(BASE_DIR, "assets", APP_ICON_FILE)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(BASE_DIR, "assets", "raz.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        root    = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # ── Header ────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background-color: {BG_PANEL}; border-bottom: 1px solid {BORDER};")
        h_row  = QHBoxLayout(header)
        h_row.setContentsMargins(18, 0, 18, 0)

        title = QLabel("RAZ")
        title.setStyleSheet(f"color: {NEON_RED}; font-size: 22px; font-weight: bold; font-family: Consolas;")
        sub   = QLabel(f"{APP_NAME} v{version}  |  {build_meta}  |  Ryan A. Wallace")
        sub.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; margin-left: 8px;")

        self.status_dot = QLabel("●")
        self.status_lbl = QLabel("NOT CONNECTED")
        self._update_status_style()

        restart_btn = QPushButton("↺ Restart")
        restart_btn.setFixedWidth(80)
        restart_btn.setToolTip("Restart RAZ Core")
        restart_btn.setStyleSheet(f"background-color: {BG_PANEL}; color: {TEXT_DIM}; border: 1px solid {BORDER}; font-size: 11px; padding: 4px 8px;")
        restart_btn.clicked.connect(self._restart_app)

        h_row.addWidget(title)
        h_row.addWidget(sub)
        h_row.addStretch()
        h_row.addWidget(restart_btn)
        h_row.addWidget(self.status_dot)
        h_row.addWidget(self.status_lbl)
        root.addWidget(header)

        # ── Tabs ──────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG_PANEL}; }}
            QTabBar::tab {{ background: {BG_DEEP}; color: {TEXT_DIM}; padding: 8px 20px; border: 1px solid {BORDER}; }}
            QTabBar::tab:selected {{ background: {BG_PANEL}; color: {NEON_RED}; border-bottom: 2px solid {NEON_RED}; }}
        """)

        # ── Chat Tab ──────────────────────────────────────────────────────
        chat_tab = QWidget()
        body_layout = QVBoxLayout(chat_tab)
        body_layout.setContentsMargins(18, 14, 18, 14)
        body_layout.setSpacing(10)

        # Chat display — QTextBrowser so links are clickable
        self.chat_display = QTextBrowser()
        self.chat_display.setReadOnly(True)
        self.chat_display.setOpenLinks(True)
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setMinimumHeight(380)
        body_layout.addWidget(self.chat_display)

        div = QFrame(); div.setObjectName("divider"); div.setFrameShape(QFrame.HLine)
        body_layout.addWidget(div)

        input_row = QHBoxLayout(); input_row.setSpacing(8)
        self.mode_combo = QComboBox()
        for m in ["chat", "mentor", "meeting", "research", "build"]:
            self.mode_combo.addItem(m)
        self.mode_combo.currentTextChanged.connect(self._on_mode_change)
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Message RAZ...")
        self.input_box.returnPressed.connect(self._send)
        self.input_box.installEventFilter(self)
        # Screenshot attach button
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setFixedWidth(42)
        self.attach_btn.setToolTip("Attach screenshot or image")
        self.attach_btn.setStyleSheet(
            f"background-color: {BG_PANEL}; color: {NEON_RED}; "
            f"border: 1px solid {BORDER}; font-size: 16px; padding: 2px;"
        )
        self.attach_btn.clicked.connect(self._attach_image)
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._send)
        input_row.addWidget(self.mode_combo)
        input_row.addWidget(self.input_box)
        input_row.addWidget(self.attach_btn)
        input_row.addWidget(self.send_btn)
        body_layout.addLayout(input_row)

        # Image indicator row (tiny thumbnail + filename + remove)
        self.image_indicator_row = QWidget()
        image_row = QHBoxLayout(self.image_indicator_row)
        image_row.setContentsMargins(4, 0, 4, 0)
        image_row.setSpacing(6)

        self.image_thumb = QLabel()
        self.image_thumb.setFixedSize(24, 24)
        self.image_thumb.setStyleSheet(f"border: 1px solid {BORDER}; background: {BG_DEEP};")
        image_row.addWidget(self.image_thumb)

        self.image_indicator = QLabel("")
        self.image_indicator.setStyleSheet(
            f"color: {NEON_RED}; font-size: 10px; margin-left: 2px;"
        )
        image_row.addWidget(self.image_indicator)

        self.image_remove_btn = QPushButton("x")
        self.image_remove_btn.setFixedSize(18, 18)
        self.image_remove_btn.setToolTip("Remove attached screenshot")
        self.image_remove_btn.setStyleSheet(
            f"background-color: {BG_PANEL}; color: {TEXT_DIM}; border: 1px solid {BORDER}; "
            f"font-size: 10px; padding: 0px;"
        )
        self.image_remove_btn.clicked.connect(self._clear_image_indicator)
        image_row.addWidget(self.image_remove_btn)
        image_row.addStretch()

        self.image_indicator_row.setVisible(False)
        body_layout.addWidget(self.image_indicator_row)

        self.response_status_lbl = QLabel("")
        self.response_status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; margin-left: 4px;")
        self.response_status_lbl.setVisible(False)
        body_layout.addWidget(self.response_status_lbl)

        # Quick action row
        qa_row = QHBoxLayout()
        qa_row.setSpacing(6)
        for label, cmd in [
            ("Memory", "/memory facts"),
            ("Projects", "/memory projects"),
            ("Tasks", "/tasks"),
            ("Help", "/help"),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(f"background-color: {BG_PANEL}; color: {TEXT_DIM}; border: 1px solid {BORDER}; font-size: 11px; padding: 2px 10px;")
            btn.clicked.connect(lambda checked, c=cmd: self._quick_cmd(c))
            qa_row.addWidget(btn)
        self.mentor_btn = QPushButton("Mentor Mode")
        self.mentor_btn.setFixedHeight(28)
        self.mentor_btn.setToolTip("Switch RAZ into blunt mentor mode")
        self.mentor_btn.setStyleSheet(
            f"background-color: {BG_PANEL}; color: {NEON_RED}; border: 1px solid {NEON_RED}; font-size: 11px; padding: 2px 10px;"
        )
        self.mentor_btn.clicked.connect(lambda: self._set_mode("mentor"))
        qa_row.addWidget(self.mentor_btn)

        self.voice_once_btn = QPushButton("Voice Once")
        self.voice_once_btn.setFixedHeight(28)
        self.voice_once_btn.setToolTip("Capture one voice turn and get one spoken response")
        self.voice_once_btn.setStyleSheet(
            f"background-color: {BG_PANEL}; color: {TEXT_DIM}; border: 1px solid {BORDER}; font-size: 11px; padding: 2px 10px;"
        )
        self.voice_once_btn.clicked.connect(self._run_voice_once)
        qa_row.addWidget(self.voice_once_btn)

        self.voice_convo_btn = QPushButton("Voice Convo ON")
        self.voice_convo_btn.setFixedHeight(28)
        self.voice_convo_btn.setToolTip("Start/stop continuous voice conversation mode")
        self.voice_convo_btn.setStyleSheet(
            f"background-color: {BG_PANEL}; color: {NEON_RED}; border: 1px solid {NEON_RED}; font-size: 11px; padding: 2px 10px;"
        )
        self.voice_convo_btn.clicked.connect(self._toggle_voice_conversation)
        qa_row.addWidget(self.voice_convo_btn)

        # Self-repair button
        self.fix_btn = QPushButton("🔧 Fix It")
        self.fix_btn.setFixedHeight(28)
        self.fix_btn.setToolTip(
            "Self-repair: describe what's broken in the text box, then click Fix It — "
            "RAZ will read its own code, patch the bug, and restart."
        )
        self.fix_btn.setStyleSheet(
            f"background-color: {BG_PANEL}; color: #ff6b00; "
            f"border: 1px solid #aa3300; font-size: 11px; padding: 2px 10px;"
        )
        self.fix_btn.clicked.connect(self._trigger_self_repair)
        qa_row.addWidget(self.fix_btn)
        qa_row.addStretch()

        self.session_lbl = QLabel("")
        self.session_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        qa_row.addWidget(self.session_lbl)
        body_layout.addLayout(qa_row)

        self.tabs.addTab(chat_tab, "CHAT")

        # ── Task Board Tab ───────────────────────────────────────────────
        board_tab = QWidget()
        board_layout = QVBoxLayout(board_tab)
        board_layout.setContentsMargins(18, 14, 18, 14)
        board_layout.setSpacing(10)

        board_title = QLabel("TASK BOARD")
        board_title.setStyleSheet(f"color: {self.ui_primary_color}; font-size: 13px; font-weight: bold;")
        board_layout.addWidget(board_title)

        board_actions = QHBoxLayout()
        self.board_refresh_btn = QPushButton("Refresh")
        self.board_refresh_btn.clicked.connect(self._refresh_task_board)
        self.board_add_input = QLineEdit()
        self.board_add_input.setPlaceholderText("Quick add task title...")
        self.board_add_input.returnPressed.connect(self._board_add_task)
        self.board_add_btn = QPushButton("Add")
        self.board_add_btn.setFixedWidth(70)
        self.board_add_btn.clicked.connect(self._board_add_task)
        board_actions.addWidget(self.board_refresh_btn)
        board_actions.addWidget(self.board_add_input)
        board_actions.addWidget(self.board_add_btn)
        board_layout.addLayout(board_actions)

        done_row = QHBoxLayout()
        self.board_done_input = QLineEdit()
        self.board_done_input.setPlaceholderText("Mark done by id, e.g. 42")
        self.board_done_input.returnPressed.connect(self._board_complete_task)
        self.board_done_btn = QPushButton("Mark Done")
        self.board_done_btn.setFixedWidth(100)
        self.board_done_btn.clicked.connect(self._board_complete_task)
        done_row.addWidget(self.board_done_input)
        done_row.addWidget(self.board_done_btn)
        board_layout.addLayout(done_row)

        board_columns = QHBoxLayout()

        pending_frame = QFrame()
        pending_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        pending_layout = QVBoxLayout(pending_frame)
        pending_layout.setContentsMargins(8, 8, 8, 8)
        pending_layout.addWidget(QLabel("PENDING"))
        self.board_pending_display = QPlainTextEdit()
        self.board_pending_display.setReadOnly(True)
        pending_layout.addWidget(self.board_pending_display)

        followup_frame = QFrame()
        followup_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        followup_layout = QVBoxLayout(followup_frame)
        followup_layout.setContentsMargins(8, 8, 8, 8)
        followup_layout.addWidget(QLabel("FOLLOW-UPS"))
        self.board_followup_display = QPlainTextEdit()
        self.board_followup_display.setReadOnly(True)
        followup_layout.addWidget(self.board_followup_display)

        done_frame = QFrame()
        done_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        done_layout = QVBoxLayout(done_frame)
        done_layout.setContentsMargins(8, 8, 8, 8)
        done_layout.addWidget(QLabel("DONE (RECENT)"))
        self.board_done_display = QPlainTextEdit()
        self.board_done_display.setReadOnly(True)
        done_layout.addWidget(self.board_done_display)

        board_columns.addWidget(pending_frame)
        board_columns.addWidget(followup_frame)
        board_columns.addWidget(done_frame)
        board_layout.addLayout(board_columns)

        self.tabs.addTab(board_tab, "TASK BOARD")

        # ── System Tab ────────────────────────────────────────────────────
        sys_tab = QWidget()
        sys_layout = QVBoxLayout(sys_tab)
        sys_layout.setContentsMargins(18, 14, 18, 14)
        sys_layout.setSpacing(8)

        sys_btn_row = QHBoxLayout(); sys_btn_row.setSpacing(6)
        for label, cmd in [
            ("Stats", "/sys stats"),
            ("Top Processes", "/sys top"),
            ("Health Scan", "/sys scan"),
            ("Key Status", "/sys keys"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(32)
            b.clicked.connect(lambda checked, c=cmd: self._sys_cmd(c))
            sys_btn_row.addWidget(b)

        # Startup toggle button — shows live ON/OFF state
        self._startup_btn = QPushButton()
        self._startup_btn.setFixedHeight(32)
        self._startup_btn.clicked.connect(self._toggle_startup)
        self._update_startup_btn()
        sys_btn_row.addWidget(self._startup_btn)
        sys_btn_row.addStretch()
        sys_layout.addLayout(sys_btn_row)

        self.sys_display = QTextEdit()
        self.sys_display.setReadOnly(True)
        sys_layout.addWidget(self.sys_display)

        run_row = QHBoxLayout(); run_row.setSpacing(8)
        self.sys_input = QLineEdit()
        self.sys_input.setPlaceholderText("Run a command (e.g. dir, ipconfig, tasklist)...")
        self.sys_input.returnPressed.connect(self._run_sys_cmd)
        run_btn = QPushButton("Run")
        run_btn.setFixedWidth(70)
        run_btn.clicked.connect(self._run_sys_cmd)
        run_row.addWidget(self.sys_input)
        run_row.addWidget(run_btn)
        sys_layout.addLayout(run_row)

        self.tabs.addTab(sys_tab, "SYSTEM")

        # ── Settings Tab ─────────────────────────────────────────────────
        settings_tab = QWidget()
        _outer_settings_layout = QVBoxLayout(settings_tab)
        _outer_settings_layout.setContentsMargins(0, 0, 0, 0)
        _outer_settings_layout.setSpacing(0)

        # Scrollable inner area so nothing gets scrunched
        _settings_scroll = QScrollArea()
        _settings_scroll.setWidgetResizable(True)
        _settings_scroll.setFrameShape(QFrame.NoFrame)
        _settings_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        _settings_inner = QWidget()
        settings_layout = QVBoxLayout(_settings_inner)
        settings_layout.setContentsMargins(18, 14, 18, 14)
        settings_layout.setSpacing(12)
        _settings_scroll.setWidget(_settings_inner)
        _outer_settings_layout.addWidget(_settings_scroll)

        settings_title = QLabel("PERSONALIZATION & VOICE SETTINGS")
        settings_title.setStyleSheet(f"color: {self.ui_primary_color}; font-size: 13px; font-weight: bold;")
        settings_layout.addWidget(settings_title)

        # Voice settings block
        voice_frame = QFrame()
        voice_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        voice_layout = QVBoxLayout(voice_frame)
        voice_layout.setContentsMargins(10, 8, 10, 8)
        voice_layout.addWidget(QLabel("VOICE CHAT (ChatGPT-style continuous conversation)"))

        voice_row1 = QHBoxLayout()
        self.settings_voice_start_btn = QPushButton("Start/Stop Voice Conversation")
        self.settings_voice_start_btn.clicked.connect(self._toggle_voice_conversation)
        self.settings_voice_once_btn = QPushButton("Voice Once")
        self.settings_voice_once_btn.clicked.connect(self._run_voice_once)
        voice_row1.addWidget(self.settings_voice_start_btn)
        voice_row1.addWidget(self.settings_voice_once_btn)
        voice_row1.addStretch()
        voice_layout.addLayout(voice_row1)

        voice_row2 = QHBoxLayout()
        self.voice_model_combo = QComboBox()
        for model_name in ["tiny", "base", "small", "medium"]:
            self.voice_model_combo.addItem(model_name)
        self.voice_model_combo.setCurrentText(self.voice_model)

        self.voice_record_spin = QSpinBox()
        self.voice_record_spin.setRange(2, 10)
        self.voice_record_spin.setValue(self.voice_record_seconds)

        self.voice_beam_spin = QSpinBox()
        self.voice_beam_spin.setRange(1, 3)
        self.voice_beam_spin.setValue(self.voice_beam_size)

        self.voice_tts_rate_spin = QSpinBox()
        self.voice_tts_rate_spin.setRange(130, 230)
        self.voice_tts_rate_spin.setValue(self.voice_tts_rate)

        voice_row2.addWidget(QLabel("Model"))
        voice_row2.addWidget(self.voice_model_combo)
        voice_row2.addWidget(QLabel("Listen (s)"))
        voice_row2.addWidget(self.voice_record_spin)
        voice_row2.addWidget(QLabel("Beam"))
        voice_row2.addWidget(self.voice_beam_spin)
        voice_row2.addWidget(QLabel("TTS Rate"))
        voice_row2.addWidget(self.voice_tts_rate_spin)
        voice_row2.addStretch()
        voice_layout.addLayout(voice_row2)
        settings_layout.addWidget(voice_frame)

        # UI personalization block
        ui_frame = QFrame()
        ui_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        ui_layout = QVBoxLayout(ui_frame)
        ui_layout.setContentsMargins(10, 8, 10, 8)
        ui_layout.addWidget(QLabel("READABILITY & COLOR"))

        ui_row1 = QHBoxLayout()
        self.font_preset_combo = QComboBox()
        for preset_name in FONT_PRESETS.keys():
            self.font_preset_combo.addItem(preset_name)
        if self.ui_font_preset in FONT_PRESETS:
            self.font_preset_combo.setCurrentText(self.ui_font_preset)

        self.font_combo = QComboBox()
        self.font_preset_combo.currentTextChanged.connect(self._on_font_preset_changed)
        self._on_font_preset_changed(self.font_preset_combo.currentText())
        if self.ui_font_family:
            idx = self.font_combo.findText(self.ui_font_family)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)

        self.random_colors_check = QCheckBox("Random Assistant Word Colors")
        self.random_colors_check.setChecked(self.ui_random_colors)

        self.pick_primary_btn = QPushButton("Pick Accent Color")
        self.pick_primary_btn.clicked.connect(self._pick_primary_color)
        self.color_preview = QLabel(self.ui_primary_color)
        self.color_preview.setStyleSheet(f"color: {self.ui_primary_color}; font-weight: bold;")

        ui_row1.addWidget(QLabel("Preset"))
        ui_row1.addWidget(self.font_preset_combo)
        ui_row1.addWidget(QLabel("Font"))
        ui_row1.addWidget(self.font_combo)
        ui_row1.addWidget(self.random_colors_check)
        ui_row1.addWidget(self.pick_primary_btn)
        ui_row1.addWidget(self.color_preview)
        ui_row1.addStretch()
        ui_layout.addLayout(ui_row1)

        ui_row2 = QHBoxLayout()
        self.serious_mode_check = QCheckBox("Serious Reading Mode")
        self.serious_mode_check.setChecked(self.ui_serious_mode)
        self.serious_bold_check = QCheckBox("Bold")
        self.serious_bold_check.setChecked(self.ui_serious_bold)
        self.serious_italic_check = QCheckBox("Italic")
        self.serious_italic_check.setChecked(self.ui_serious_italic)
        self.pick_serious_btn = QPushButton("Pick Strategic Color")
        self.pick_serious_btn.clicked.connect(self._pick_serious_color)
        self.serious_color_preview = QLabel(self.ui_serious_color)
        self.serious_color_preview.setStyleSheet(f"color: {self.ui_serious_color}; font-weight: bold;")

        ui_row2.addWidget(self.serious_mode_check)
        ui_row2.addWidget(self.serious_bold_check)
        ui_row2.addWidget(self.serious_italic_check)
        ui_row2.addWidget(self.pick_serious_btn)
        ui_row2.addWidget(self.serious_color_preview)
        ui_row2.addStretch()
        ui_layout.addLayout(ui_row2)

        # Emphasis bounce colors row — mood presets
        ui_row3 = QHBoxLayout()
        self.emphasis_mode_check = QCheckBox("Emphasis Bounce Colors")
        self.emphasis_mode_check.setChecked(self.ui_emphasis_mode)
        self.emphasis_mode_check.setToolTip(
            "Lines starting with WARNING, CAUTION, IMPORTANT, NOTE, CRITICAL, ERROR\n"
            "will cycle through the 3 mood colors below for visual punch."
        )
        self.emphasis_mood_combo = QComboBox()
        for mood_name in EMPHASIS_MOODS.keys():
            self.emphasis_mood_combo.addItem(mood_name)
        # Show current mood (detect by matching colors, default to Custom)
        _cur_mood = getattr(self, "ui_emphasis_mood", "Sunset Alert")
        idx_mood = self.emphasis_mood_combo.findText(_cur_mood)
        self.emphasis_mood_combo.setCurrentIndex(idx_mood if idx_mood >= 0 else 0)
        # Live color swatches
        self.emph_swatch1 = QLabel("  ")
        self.emph_swatch2 = QLabel("  ")
        self.emph_swatch3 = QLabel("  ")
        def _update_emph_swatches():
            c1, c2, c3 = self.ui_emphasis_color_1, self.ui_emphasis_color_2, self.ui_emphasis_color_3
            for sw, c in [(self.emph_swatch1, c1), (self.emph_swatch2, c2), (self.emph_swatch3, c3)]:
                sw.setStyleSheet(f"background: {c}; border: 1px solid #333; min-width:18px; min-height:18px; border-radius:3px;")
        _update_emph_swatches()
        def _on_mood_changed(name):
            colors = EMPHASIS_MOODS.get(name)
            if colors:
                self.ui_emphasis_color_1, self.ui_emphasis_color_2, self.ui_emphasis_color_3 = colors
                self.ui_emphasis_mood = name
                _update_emph_swatches()
        self.emphasis_mood_combo.currentTextChanged.connect(_on_mood_changed)
        # Custom: click any swatch to pick a color
        def _make_swatch_picker(attr, swatch):
            def _pick(event=None, _a=attr, _s=swatch):
                color = QColorDialog.getColor(QColor(getattr(self, _a)), self, "Pick Emphasis Color")
                if color.isValid():
                    setattr(self, _a, color.name())
                    _s.setStyleSheet(f"background: {color.name()}; border: 1px solid #333; min-width:18px; min-height:18px; border-radius:3px;")
                    self.emphasis_mood_combo.setCurrentText("Custom")
                    self.ui_emphasis_mood = "Custom"
            _s = swatch
            _s.mousePressEvent = _pick
        _make_swatch_picker("ui_emphasis_color_1", self.emph_swatch1)
        _make_swatch_picker("ui_emphasis_color_2", self.emph_swatch2)
        _make_swatch_picker("ui_emphasis_color_3", self.emph_swatch3)
        ui_row3.addWidget(self.emphasis_mode_check)
        ui_row3.addWidget(QLabel("Mood"))
        ui_row3.addWidget(self.emphasis_mood_combo)
        ui_row3.addWidget(QLabel("Colors:"))
        ui_row3.addWidget(self.emph_swatch1)
        ui_row3.addWidget(self.emph_swatch2)
        ui_row3.addWidget(self.emph_swatch3)
        ui_row3.addStretch()
        ui_layout.addLayout(ui_row3)

        # Resource alert thresholds row
        ui_row4 = QHBoxLayout()
        self.alerts_check = QCheckBox("Resource Alerts")
        self.alerts_check.setChecked(self.resource_alerts_enabled)
        self.alerts_check.setToolTip("Post chat warnings when CPU/RAM/Disk exceed thresholds.")
        self.cpu_spin = QSpinBox(); self.cpu_spin.setRange(10, 100); self.cpu_spin.setValue(self.cpu_alert_pct); self.cpu_spin.setSuffix("%")
        self.ram_spin = QSpinBox(); self.ram_spin.setRange(10, 100); self.ram_spin.setValue(self.ram_alert_pct); self.ram_spin.setSuffix("%")
        self.disk_spin = QSpinBox(); self.disk_spin.setRange(10, 100); self.disk_spin.setValue(self.disk_alert_pct); self.disk_spin.setSuffix("%")
        ui_row4.addWidget(self.alerts_check)
        ui_row4.addWidget(QLabel("CPU"))
        ui_row4.addWidget(self.cpu_spin)
        ui_row4.addWidget(QLabel("RAM"))
        ui_row4.addWidget(self.ram_spin)
        ui_row4.addWidget(QLabel("Disk"))
        ui_row4.addWidget(self.disk_spin)
        ui_row4.addStretch()
        ui_layout.addLayout(ui_row4)

        settings_actions = QHBoxLayout()
        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.clicked.connect(self._apply_settings)
        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(self._save_settings)
        settings_actions.addWidget(self.apply_settings_btn)
        settings_actions.addWidget(self.save_settings_btn)
        settings_actions.addStretch()
        ui_layout.addLayout(settings_actions)
        settings_layout.addWidget(ui_frame)

        # Comprehension test block
        comp_frame = QFrame()
        comp_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        comp_layout = QVBoxLayout(comp_frame)
        comp_layout.setContentsMargins(10, 8, 10, 8)
        comp_layout.addWidget(QLabel("FONT COMPREHENSION TEST"))

        comp_ab_controls = QHBoxLayout()
        self.comp_font_a_combo = QComboBox()
        self.comp_font_b_combo = QComboBox()
        for font_name in READABILITY_FONTS:
            self.comp_font_a_combo.addItem(font_name)
            self.comp_font_b_combo.addItem(font_name)
        idx_a = self.comp_font_a_combo.findText(self.ui_font_family)
        if idx_a >= 0:
            self.comp_font_a_combo.setCurrentIndex(idx_a)
        self.comp_font_b_combo.setCurrentIndex(0 if self.comp_font_b_combo.count() == 0 else min(1, self.comp_font_b_combo.count() - 1))
        self.comp_ab_preview_btn = QPushButton("Preview A/B")
        self.comp_ab_preview_btn.clicked.connect(self._preview_comparison_fonts)
        comp_ab_controls.addWidget(QLabel("Font A"))
        comp_ab_controls.addWidget(self.comp_font_a_combo)
        comp_ab_controls.addWidget(QLabel("Font B"))
        comp_ab_controls.addWidget(self.comp_font_b_combo)
        comp_ab_controls.addWidget(self.comp_ab_preview_btn)
        comp_ab_controls.addStretch()
        comp_layout.addLayout(comp_ab_controls)

        self.comp_ab_header = QLabel("A/B Compare: same passage rendered in two fonts")
        self.comp_ab_header.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        comp_layout.addWidget(self.comp_ab_header)

        comp_preview_row = QHBoxLayout()
        self.comp_passage_display_a = QPlainTextEdit()
        self.comp_passage_display_a.setReadOnly(True)
        self.comp_passage_display_a.setMaximumHeight(120)
        self.comp_passage_display_b = QPlainTextEdit()
        self.comp_passage_display_b.setReadOnly(True)
        self.comp_passage_display_b.setMaximumHeight(120)
        comp_preview_row.addWidget(self.comp_passage_display_a)
        comp_preview_row.addWidget(self.comp_passage_display_b)
        comp_layout.addLayout(comp_preview_row)

        self.comp_passage_display = QPlainTextEdit()
        self.comp_passage_display.setReadOnly(True)
        self.comp_passage_display.setMaximumHeight(120)
        self.comp_passage_display.setPlainText("Click 'Generate Test' to compare readability across fonts.")
        comp_layout.addWidget(self.comp_passage_display)

        self.comp_q_labels = []
        self.comp_q_combos = []
        for i in range(3):
            q_label = QLabel(f"Q{i + 1}:")
            q_combo = QComboBox()
            q_combo.addItem("Select answer")
            row = QHBoxLayout()
            row.addWidget(q_label)
            row.addWidget(q_combo)
            comp_layout.addLayout(row)
            self.comp_q_labels.append(q_label)
            self.comp_q_combos.append(q_combo)

        comp_bench_row = QHBoxLayout()
        self.comp_rounds_spin = QSpinBox()
        self.comp_rounds_spin.setRange(2, 10)
        self.comp_rounds_spin.setValue(self.comp_benchmark_rounds)
        self.comp_benchmark_btn = QPushButton("Run Benchmark Set")
        self.comp_benchmark_btn.clicked.connect(self._run_benchmark_set)
        self.comp_round_status_lbl = QLabel("Round: --")
        self.comp_round_status_lbl.setStyleSheet(f"color: {TEXT_DIM};")
        comp_bench_row.addWidget(QLabel("Rounds"))
        comp_bench_row.addWidget(self.comp_rounds_spin)
        comp_bench_row.addWidget(self.comp_benchmark_btn)
        comp_bench_row.addWidget(self.comp_round_status_lbl)
        comp_bench_row.addStretch()
        comp_layout.addLayout(comp_bench_row)

        comp_actions = QHBoxLayout()
        self.comp_generate_btn = QPushButton("Generate Test")
        self.comp_generate_btn.clicked.connect(self._run_comprehension_test)
        self.comp_score_btn = QPushButton("Score Test")
        self.comp_score_btn.clicked.connect(self._score_comprehension_test)
        self.comp_result_lbl = QLabel("Score: --")
        self.comp_result_lbl.setStyleSheet(f"color: {self.ui_primary_color}; font-weight: bold;")
        comp_actions.addWidget(self.comp_generate_btn)
        comp_actions.addWidget(self.comp_score_btn)
        comp_actions.addWidget(self.comp_result_lbl)
        comp_actions.addStretch()
        comp_layout.addLayout(comp_actions)

        self.comp_recommend_lbl = QLabel("Recommended setup: run tests to calculate.")
        self.comp_recommend_lbl.setStyleSheet(f"color: {self.ui_primary_color}; font-size: 10px; font-weight: bold;")
        comp_layout.addWidget(self.comp_recommend_lbl)

        comp_recommend_actions = QHBoxLayout()
        self.comp_apply_recommend_btn = QPushButton("Apply Recommended Setup")
        self.comp_apply_recommend_btn.clicked.connect(self._apply_recommended_setup)
        comp_recommend_actions.addWidget(self.comp_apply_recommend_btn)
        comp_recommend_actions.addStretch()
        comp_layout.addLayout(comp_recommend_actions)

        settings_layout.addWidget(comp_frame)
        settings_layout.addStretch()

        self._update_recommendation_label()

        self.tabs.addTab(settings_tab, "SETTINGS")

        # ── Secret Brain Tab ──────────────────────────────────────────────
        sb_tab = QScrollArea()
        sb_tab.setWidgetResizable(True)
        sb_tab.setFrameShape(QFrame.NoFrame)
        sb_tab.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        sb_content = QWidget()
        sb_layout = QVBoxLayout(sb_content)
        sb_layout.setContentsMargins(18, 14, 18, 14)
        sb_layout.setSpacing(10)

        # Header row with status + buttons
        sb_hdr = QHBoxLayout()
        self.sb_status_lbl = QLabel("SECRET BRAIN  —  Loading...")
        self.sb_status_lbl.setStyleSheet(f"color: {NEON_RED}; font-size: 13px; font-weight: bold;")
        sb_hdr.addWidget(self.sb_status_lbl)
        sb_hdr.addStretch()

        self.sb_sync_btn = QPushButton("⟳ Sync Now")
        self.sb_sync_btn.setFixedWidth(110)
        self.sb_sync_btn.setToolTip("Ingest any new files from the Secret Brain folder")
        self.sb_sync_btn.clicked.connect(self._sb_sync)
        sb_hdr.addWidget(self.sb_sync_btn)

        sb_full_btn = QPushButton("Full Rebuild")
        sb_full_btn.setFixedWidth(100)
        sb_full_btn.setStyleSheet(f"background-color: {BG_PANEL}; color: {TEXT_DIM}; border: 1px solid {BORDER}; font-size: 11px;")
        sb_full_btn.setToolTip("Re-ingest everything from scratch")
        sb_full_btn.clicked.connect(lambda: self._sb_sync(force=True))
        sb_hdr.addWidget(sb_full_btn)
        sb_layout.addLayout(sb_hdr)

        # Profile summary display (top/left)
        profile_frame = QFrame()
        profile_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        pf_layout = QVBoxLayout(profile_frame)
        pf_layout.setContentsMargins(10, 8, 10, 8)
        pf_label = QLabel("PROFILE SUMMARY")
        pf_label.setStyleSheet(f"color: {NEON_RED}; font-size: 11px; font-weight: bold;")
        pf_layout.addWidget(pf_label)

        self.sb_profile_display = QPlainTextEdit()
        self.sb_profile_display.setReadOnly(True)
        self.sb_profile_display.setMinimumHeight(220)
        self.sb_profile_display.setMaximumHeight(320)
        self.sb_profile_display.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.sb_profile_display.setPlainText("Run Sync to load profile...")
        pf_layout.addWidget(self.sb_profile_display)
        sb_layout.addWidget(profile_frame)

        # Document library
        doc_frame = QFrame()
        doc_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        doc_layout = QVBoxLayout(doc_frame)
        doc_layout.setContentsMargins(10, 8, 10, 8)
        doc_label = QLabel("DOCUMENT LIBRARY")
        doc_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: bold;")
        doc_layout.addWidget(doc_label)
        self.sb_doc_list = QPlainTextEdit()
        self.sb_doc_list.setReadOnly(True)
        self.sb_doc_list.setMaximumHeight(150)
        self.sb_doc_list.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.sb_doc_list.setPlainText("No documents loaded.")
        doc_layout.addWidget(self.sb_doc_list)
        sb_layout.addWidget(doc_frame)

        # Mentor chat area
        mentor_frame = QFrame()
        mentor_frame.setStyleSheet(f"background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 4px;")
        mentor_layout = QVBoxLayout(mentor_frame)
        mentor_layout.setContentsMargins(10, 8, 10, 8)
        mentor_header_lbl = QLabel("MENTOR CHANNEL  —  Ask RAZ about your data")
        mentor_header_lbl.setStyleSheet(f"color: {NEON_RED}; font-size: 11px; font-weight: bold;")
        mentor_layout.addWidget(mentor_header_lbl)

        self.sb_mentor_display = QPlainTextEdit()
        self.sb_mentor_display.setReadOnly(True)
        self.sb_mentor_display.setMinimumHeight(160)
        self.sb_mentor_display.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.sb_mentor_display.setPlainText(
            "Ask anything grounded in your files:\n"
            "  \"What does my QEEG say about how I learn?\"\n"
            "  \"What does my Human Design tell me about decision making?\"\n"
            "  \"Based on my medical records, what should I focus on?\"\n"
            "  \"Give me my top 3 growth vectors right now.\""
        )
        mentor_layout.addWidget(self.sb_mentor_display)

        mentor_input_row = QHBoxLayout()
        self.sb_input = QLineEdit()
        self.sb_input.setPlaceholderText("Ask RAZ based on your Secret Brain data...")
        self.sb_input.returnPressed.connect(self._sb_ask_mentor)
        self.sb_ask_btn = QPushButton("Ask")
        self.sb_ask_btn.setFixedWidth(70)
        self.sb_ask_btn.clicked.connect(self._sb_ask_mentor)

        # Quick mentor buttons
        for label, q in [
            ("Growth Vectors", "What are my top 3 growth vectors based on all my data?"),
            ("QEEG Insight", "What does my QEEG report say about how I perform and learn best?"),
            ("Strengths Now", "Based on my Gallup and Human Design, what am I built for?"),
            ("Health Focus", "Based on my medical records, what are the most important things I should address?"),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"background-color: {BG_DEEP}; color: {TEXT_DIM}; border: 1px solid {BORDER}; font-size: 10px; padding: 2px 8px;")
            btn.clicked.connect(lambda checked, _q=q: self._sb_quick_ask(_q))
            mentor_layout.addWidget(btn)

        mentor_input_row.addWidget(self.sb_input)
        mentor_input_row.addWidget(self.sb_ask_btn)
        mentor_layout.addLayout(mentor_input_row)
        sb_layout.addWidget(mentor_frame)

        sb_layout.addStretch()
        sb_tab.setWidget(sb_content)
        self.tabs.addTab(sb_tab, "SECRET BRAIN")

        root.addWidget(self.tabs)

        if TABLET_MODE:
            self._apply_tablet_layout()

        self._refresh_task_board()
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Start periodic refresh/alerts and launch-time Secret Brain checks."""
        # Update session label
        if self.raz_chat:
            self.session_lbl.setText(f"session: {self.raz_chat.session_id}")

        # Auto-refresh system stats every 30s
        self._sys_timer = QTimer()
        self._sys_timer.timeout.connect(self._refresh_sys_display)
        self._sys_timer.start(30000)
        self._refresh_sys_display()

        # Resource alert monitor — checks CPU/RAM/Disk every 60s
        self._alert_timer = QTimer()
        self._alert_timer.timeout.connect(self._check_resource_alerts)
        self._alert_timer.start(60000)
        self._last_alert_state: dict = {}

        # Kick off a background check for new Secret Brain files on launch
        QTimer.singleShot(250, self._sb_restore_cached_state)
        QTimer.singleShot(1500, self._sb_check_on_launch)

    def _apply_tablet_layout(self):
        """Increase hit targets and typography for touch-first tablet usage."""
        try:
            for btn in self.findChildren(QPushButton):
                btn.setMinimumHeight(max(btn.minimumHeight(), 42))
                f = btn.font()
                if f.pointSize() < 12:
                    f.setPointSize(12)
                    btn.setFont(f)

            for edit in self.findChildren(QLineEdit):
                edit.setMinimumHeight(max(edit.minimumHeight(), 40))
                f = edit.font()
                if f.pointSize() < 12:
                    f.setPointSize(12)
                    edit.setFont(f)

            for combo in self.findChildren(QComboBox):
                combo.setMinimumHeight(max(combo.minimumHeight(), 38))
                f = combo.font()
                if f.pointSize() < 12:
                    f.setPointSize(12)
                    combo.setFont(f)

            for tabbar in self.findChildren(QTabWidget):
                tabbar.setStyleSheet(tabbar.styleSheet() + " QTabBar::tab { min-height: 42px; min-width: 140px; font-size: 13px; }")
        except Exception:
            pass

    def _check_resource_alerts(self):
        """Periodically check CPU/RAM/Disk against thresholds and post warnings in chat."""
        if not getattr(self, "resource_alerts_enabled", True):
            return
        try:
            from core.system_control import get_system_snapshot
            snap = get_system_snapshot()
            if "error" in snap:
                return
            alerts = []
            cpu = snap.get("cpu", {}).get("usage_pct", 0)
            ram = snap.get("ram", {}).get("usage_pct", 0)
            # Check CPU
            if cpu >= self.cpu_alert_pct and not self._last_alert_state.get("cpu"):
                alerts.append(f"WARNING: CPU at {cpu:.0f}% — threshold {self.cpu_alert_pct}%")
                self._last_alert_state["cpu"] = True
            elif cpu < self.cpu_alert_pct:
                self._last_alert_state["cpu"] = False
            # Check RAM
            if ram >= self.ram_alert_pct and not self._last_alert_state.get("ram"):
                alerts.append(f"WARNING: RAM at {ram:.0f}% — threshold {self.ram_alert_pct}%")
                self._last_alert_state["ram"] = True
            elif ram < self.ram_alert_pct:
                self._last_alert_state["ram"] = False
            # Check disk
            for disk in snap.get("disks", []):
                mp = disk.get("mountpoint", "disk")
                pct = disk.get("usage_pct", 0)
                alert_key = f"disk_{mp}"
                if pct >= self.disk_alert_pct and not self._last_alert_state.get(alert_key):
                    alerts.append(f"WARNING: Disk {mp} at {pct:.0f}% — threshold {self.disk_alert_pct}%")
                    self._last_alert_state[alert_key] = True
                elif pct < self.disk_alert_pct:
                    self._last_alert_state[alert_key] = False
            # Post alerts to chat
            for alert_text in alerts:
                self._insert_raz_header()
                self._append_rainbow_text(alert_text + "\n")
                self._scroll_to_bottom()
        except Exception:
            pass

    def _sb_check_on_launch(self):
        """Check for new/uningested Secret Brain files on startup."""
        try:
            from core.secret_brain import watch_for_new_files, get_profile_summary
            import os
            profile_summary = get_profile_summary()
            if "No Secret Brain data" not in profile_summary:
                self.sb_profile_display.setPlainText(profile_summary)
                self.sb_status_lbl.setText("SECRET BRAIN  —  Loaded from cache")
                self._sb_refresh_doc_list()

            new_files = watch_for_new_files()
            if new_files:
                self.sb_status_lbl.setText(f"SECRET BRAIN  —  {len(new_files)} new file(s) detected — syncing...")
                self._sb_sync()
            elif "No Secret Brain data" in profile_summary:
                # Auto-ingest on first launch if no data exists
                self.sb_status_lbl.setText("SECRET BRAIN  —  First run — auto-ingesting files...")
                self._sb_sync()
        except Exception as e:
            self.sb_status_lbl.setText(f"SECRET BRAIN  —  Error: {e}")

    def _sb_sync(self, force: bool = False):
        """Start ingestion + profile build in background thread."""
        if self._sb_worker and self._sb_worker.isRunning():
            return
        self.sb_sync_btn.setEnabled(False)
        self.sb_status_lbl.setText("SECRET BRAIN  —  Syncing...")
        self._sb_worker = SecretBrainWorker(force_refresh=force)
        self._sb_worker.progress.connect(lambda msg: self.sb_status_lbl.setText(f"SECRET BRAIN  —  {msg}"))
        self._sb_worker.finished.connect(self._sb_on_sync_done)
        self._sb_worker.error.connect(self._sb_on_sync_error)
        self._sb_worker.start()

    def _sb_on_sync_done(self, results: dict):
        self.sb_sync_btn.setEnabled(True)
        totals = results.get("totals", {})
        self.sb_status_lbl.setText(
            f"SECRET BRAIN  —  "
            f"Ingested: {totals.get('ingested', 0)}  |  "
            f"Duplicates: {totals.get('duplicates', 0)}  |  "
            f"Errors: {totals.get('errors', 0)}"
        )
        profile = results.get("profile", {})
        from core.secret_brain import get_profile_summary
        self.sb_profile_display.setPlainText(get_profile_summary())
        self._sb_refresh_doc_list()

    def _sb_on_sync_error(self, err: str):
        self.sb_sync_btn.setEnabled(True)
        self.sb_status_lbl.setText(f"SECRET BRAIN  —  Sync failed: {err}")

    def _sb_refresh_doc_list(self):
        """Refresh the document list display."""
        try:
            files = mem.get_ingested_files()
            sb_files = [f for f in files if "secret_brain" in (f.get("tags") or "")]
            if not sb_files:
                self.sb_doc_list.setPlainText("No Secret Brain documents loaded yet.")
                return
            lines = []
            for f in sb_files:
                tags  = f.get("tags", "[]")
                try:
                    import json as _json
                    tag_list = _json.loads(tags) if isinstance(tags, str) else tags
                    cat = next((t.replace("secret_brain_", "") for t in tag_list if t.startswith("secret_")), "general")
                except Exception:
                    cat = "general"
                size_kb = round((f.get("size_bytes") or 0) / 1024, 1)
                lines.append(f"  [{cat:<22}]  {f['filename']:<50}  {size_kb} KB")
            self.sb_doc_list.setPlainText(f"{len(sb_files)} documents ingested:\n" + "\n".join(lines))
        except Exception as e:
            self.sb_doc_list.setPlainText(f"Error loading document list: {e}")

    def _sb_ask_mentor(self):
        """Send a mentor question via the Secret Brain chat."""
        question = self.sb_input.text().strip()
        if not question:
            return
        self.sb_input.clear()
        self._sb_mentor_ask(question)

    def _sb_quick_ask(self, question: str):
        self._sb_mentor_ask(question)

    def _sb_mentor_ask(self, question: str):
        """Run an AI mentor response using profile data."""
        if not self.raz_chat:
            self.sb_mentor_display.setPlainText("RAZ chat not connected. Check API key.")
            return
        if self._mentor_worker and self._mentor_worker.isRunning():
            return
        self.sb_ask_btn.setEnabled(False)
        self._append_sb_mentor(f"YOU: {question}\n")
        self._mentor_worker = MentorWorker(self.raz_chat, question)
        self._mentor_worker.finished.connect(self._sb_on_mentor_done)
        self._mentor_worker.error.connect(self._sb_on_mentor_error)
        self._mentor_worker.start()

    def _sb_on_mentor_done(self, response: str):
        self.sb_ask_btn.setEnabled(True)
        self._append_sb_mentor(f"RAZ: {response}\n\n{'─'*60}\n")

    def _sb_on_mentor_error(self, err: str):
        self.sb_ask_btn.setEnabled(True)
        self._append_sb_mentor(f"[ERROR] {err}\n")

    def _append_sb_mentor(self, text: str):
        cursor = self.sb_mentor_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        sb = self.sb_mentor_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_startup_btn(self):
        """Set startup button label and color based on current registry state."""
        from core.system_control import is_startup_registered
        registered = is_startup_registered()
        if registered:
            self._startup_btn.setText("Launch at Startup  ON")
            self._startup_btn.setStyleSheet("background-color: #004400; color: #00ff88; border: 1px solid #00ff88;")
        else:
            self._startup_btn.setText("Launch at Startup  OFF")
            self._startup_btn.setStyleSheet("background-color: #2a0000; color: #888888; border: 1px solid #444444;")

    def _toggle_startup(self):
        """Toggle Windows startup registration on/off."""
        from core.system_control import is_startup_registered, register_startup, unregister_startup
        if is_startup_registered():
            msg = unregister_startup()
        else:
            msg = register_startup()
        self._update_startup_btn()
        self.sys_display.setPlainText(msg)

    def _refresh_sys_display(self):
        """Refresh the system tab with current stats."""
        try:
            from core.system_control import get_system_snapshot, format_snapshot_summary
            snap = get_system_snapshot()
            stats_text = format_snapshot_summary(snap)
            keys = get_api_key_statuses()
            keys_text = (
                "\n\n=== API KEY STATUS ===\n"
                f"OpenAI : {'🟢 SET' if keys.get('openai') else '🔴 MISSING'}\n"
                f"Groq   : {'🟢 SET' if keys.get('groq') else '🔴 MISSING'}\n"
                f"Gemini : {'🟢 SET' if keys.get('gemini') else '🔴 MISSING'}\n"
                "\nUse /sys keys to manage secure keys."
            )
            self.sys_display.setPlainText(stats_text + keys_text)
        except Exception as e:
            self.sys_display.setPlainText(f"System stats unavailable: {e}")

    def _refresh_task_board(self):
        """Refresh the TASK BOARD tab from SQLite memory."""
        try:
            pending = [t for t in mem.get_tasks(status="pending") if t.get("project") != "followups"]
            followups = mem.get_followup_tasks(status="pending", limit=100)
            completed = mem.get_tasks(status="completed")

            p_lines = [f"#{t['id']} [{t.get('priority', 'normal').upper()}] {t.get('title', '')}" for t in pending[:150]]
            if not p_lines:
                p_lines = ["No pending tasks."]

            f_lines = [f"#{t['id']} [{t.get('priority', 'high').upper()}] {t.get('title', '')}" for t in followups[:150]]
            if not f_lines:
                f_lines = ["No pending follow-ups."]

            d_lines = [f"#{t['id']} {t.get('title', '')}" for t in completed[-150:]]
            if not d_lines:
                d_lines = ["No completed tasks yet."]

            self.board_pending_display.setPlainText("\n".join(p_lines))
            self.board_followup_display.setPlainText("\n".join(f_lines))
            self.board_done_display.setPlainText("\n".join(d_lines))
        except Exception as e:
            msg = f"Task board unavailable: {e}"
            self.board_pending_display.setPlainText(msg)
            self.board_followup_display.setPlainText(msg)
            self.board_done_display.setPlainText(msg)

    def _board_add_task(self):
        title = self.board_add_input.text().strip()
        if not title:
            return
        task_id = mem.save_task(title=title, description="", priority="normal")
        self.board_add_input.clear()
        self._append_system(f"Task #{task_id} added from Task Board.")
        self._refresh_task_board()

    def _board_complete_task(self):
        raw = self.board_done_input.text().strip()
        if not raw:
            return
        try:
            task_id = int(raw)
        except ValueError:
            self._append_system("Task id must be a number.")
            return
        task = mem.get_task_by_id(task_id)
        if not task:
            self._append_system(f"Task #{task_id} not found.")
            return
        mem.complete_task(task_id)
        self.board_done_input.clear()
        self._append_system(f"Task #{task_id} marked completed from Task Board.")
        self._refresh_task_board()

    def _sys_cmd(self, cmd: str):
        """Run a /sys command and show result in sys display."""
        if not self.raz_chat:
            return
        result = self.raz_chat.chat(cmd)
        self.sys_display.setPlainText(result.replace("RAZ: ", "").replace("RAZ:\n", ""))

    def _run_sys_cmd(self):
        """Run a raw terminal command from the system tab."""
        cmd = self.sys_input.text().strip()
        if not cmd:
            return
        self.sys_input.clear()
        from core.system_control import run_command
        result = run_command(cmd)
        out = result.get("stdout") or result.get("stderr") or "(no output)"
        self.sys_display.setPlainText(f"$ {cmd}\n\n{out}")

    def _pick_primary_color(self):
        color = QColorDialog.getColor(QColor(self.ui_primary_color), self, "Choose Accent Color")
        if color.isValid():
            self.ui_primary_color = color.name()
            self.color_preview.setText(self.ui_primary_color)
            self.color_preview.setStyleSheet(f"color: {self.ui_primary_color}; font-weight: bold;")

    def _pick_serious_color(self):
        color = QColorDialog.getColor(QColor(self.ui_serious_color), self, "Choose Strategic Reading Color")
        if color.isValid():
            self.ui_serious_color = color.name()
            self.serious_color_preview.setText(self.ui_serious_color)
            self.serious_color_preview.setStyleSheet(f"color: {self.ui_serious_color}; font-weight: bold;")

    def _on_font_preset_changed(self, preset_name: str):
        fonts = FONT_PRESETS.get(preset_name, READABILITY_FONTS)
        current = self.font_combo.currentText() if hasattr(self, "font_combo") else ""
        if not hasattr(self, "font_combo"):
            return
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        for font_name in fonts:
            self.font_combo.addItem(font_name)
        if current in fonts:
            self.font_combo.setCurrentText(current)
        elif self.ui_font_family in fonts:
            self.font_combo.setCurrentText(self.ui_font_family)
        elif fonts:
            self.font_combo.setCurrentIndex(0)
        self.font_combo.blockSignals(False)

    def _run_comprehension_test(self):
        self._comprehension_current = random.choice(COMPREHENSION_TEST_BANK)
        self._comprehension_started_at = time.time()
        self.comp_passage_display.setPlainText(self._comprehension_current["passage"])
        self.comp_passage_display_a.setPlainText(self._comprehension_current["passage"])
        self.comp_passage_display_b.setPlainText(self._comprehension_current["passage"])
        self._preview_comparison_fonts()

        for i, q in enumerate(self._comprehension_current["questions"]):
            self.comp_q_labels[i].setText(f"Q{i + 1}: {q['q']}")
            combo = self.comp_q_combos[i]
            combo.clear()
            combo.addItem("Select answer")
            for option in q["options"]:
                combo.addItem(option)

        self.comp_result_lbl.setText("Score: --")
        if self._benchmark_active:
            self.comp_round_status_lbl.setText(f"Round: {self._benchmark_round}/{self._benchmark_total}")
            self._append_system(f"Benchmark round {self._benchmark_round}/{self._benchmark_total} generated.")
        else:
            self.comp_round_status_lbl.setText("Round: single test")
            self._append_system("Comprehension test generated. Read, answer, then click Score Test.")

    def _preview_comparison_fonts(self):
        font_a = self.comp_font_a_combo.currentText().strip() or "Segoe UI"
        font_b = self.comp_font_b_combo.currentText().strip() or "Verdana"
        self.comp_passage_display_a.setFont(QFont(font_a, 11))
        self.comp_passage_display_b.setFont(QFont(font_b, 11))
        self.comp_passage_display_a.setPlaceholderText(f"Preview A ({font_a})")
        self.comp_passage_display_b.setPlaceholderText(f"Preview B ({font_b})")

    def _current_setup_key(self):
        style_bits = []
        if self.ui_serious_mode:
            style_bits.append("serious")
            if self.ui_serious_bold:
                style_bits.append("bold")
            if self.ui_serious_italic:
                style_bits.append("italic")
        else:
            style_bits.append("normal")
        return f"{self.ui_font_family}|{'-'.join(style_bits)}|{self.ui_serious_color}"

    def _record_comprehension_result(self, correct: int, total: int, pct: int, wpm: int):
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "font": self.ui_font_family,
            "preset": self.ui_font_preset,
            "serious_mode": bool(self.ui_serious_mode),
            "serious_bold": bool(self.ui_serious_bold),
            "serious_italic": bool(self.ui_serious_italic),
            "serious_color": self.ui_serious_color,
            "correct": int(correct),
            "total": int(total),
            "pct": int(pct),
            "wpm": int(wpm),
            "setup_key": self._current_setup_key(),
        }
        self.comp_history.append(entry)
        self.comp_history = self.comp_history[-40:]

    def _best_setup_from_history(self):
        if not self.comp_history:
            return None
        grouped = {}
        for row in self.comp_history:
            key = row.get("setup_key") or "unknown"
            bucket = grouped.setdefault(
                key,
                {
                    "pct": 0,
                    "wpm": 0,
                    "n": 0,
                    "font": row.get("font", "Segoe UI"),
                    "preset": row.get("preset", "High Readability"),
                    "serious_mode": bool(row.get("serious_mode", False)),
                    "serious_bold": bool(row.get("serious_bold", True)),
                    "serious_italic": bool(row.get("serious_italic", False)),
                    "serious_color": row.get("serious_color", "#9fffb8"),
                },
            )
            bucket["pct"] += int(row.get("pct", 0))
            bucket["wpm"] += int(row.get("wpm", 0))
            bucket["n"] += 1

        ranked = []
        for key, bucket in grouped.items():
            n = max(1, bucket["n"])
            avg_pct = bucket["pct"] / n
            avg_wpm = bucket["wpm"] / n
            ranked.append(
                (
                    avg_pct,
                    avg_wpm,
                    bucket["n"],
                    key,
                    bucket["font"],
                    bucket["preset"],
                    bucket["serious_mode"],
                    bucket["serious_bold"],
                    bucket["serious_italic"],
                    bucket["serious_color"],
                )
            )
        ranked.sort(reverse=True)
        top = ranked[0]
        return {
            "avg_pct": int(top[0]),
            "avg_wpm": int(top[1]),
            "samples": int(top[2]),
            "setup_key": top[3],
            "font": top[4],
            "preset": top[5],
            "serious_mode": bool(top[6]),
            "serious_bold": bool(top[7]),
            "serious_italic": bool(top[8]),
            "serious_color": str(top[9]),
        }

    def _update_recommendation_label(self):
        best = self._best_setup_from_history()
        if not best:
            self.comp_recommend_lbl.setText("Recommended setup: run tests to calculate.")
            return
        self.comp_recommend_lbl.setText(
            f"Recommended setup: {best['preset']} / {best['font']}  |  "
            f"Accuracy {best['avg_pct']}%  |  Pace {best['avg_wpm']} WPM  |  n={best['samples']}"
        )

    def _apply_recommended_setup(self):
        best = self._best_setup_from_history()
        if not best:
            self._append_system("No recommendation yet. Run and score a few tests first.")
            return

        preset = str(best.get("preset") or "High Readability")
        font = str(best.get("font") or "Segoe UI")

        idx_preset = self.font_preset_combo.findText(preset)
        if idx_preset >= 0:
            self.font_preset_combo.setCurrentIndex(idx_preset)
        self._on_font_preset_changed(self.font_preset_combo.currentText())

        idx_font = self.font_combo.findText(font)
        if idx_font >= 0:
            self.font_combo.setCurrentIndex(idx_font)

        self.serious_mode_check.setChecked(bool(best.get("serious_mode", False)))
        self.serious_bold_check.setChecked(bool(best.get("serious_bold", True)))
        self.serious_italic_check.setChecked(bool(best.get("serious_italic", False)))
        self.ui_serious_color = str(best.get("serious_color") or self.ui_serious_color)
        self.serious_color_preview.setText(self.ui_serious_color)
        self.serious_color_preview.setStyleSheet(f"color: {self.ui_serious_color}; font-weight: bold;")

        self._save_settings()
        self._append_system(
            f"Applied recommended setup: {preset} / {font} "
            f"(accuracy {best['avg_pct']}%, pace {best['avg_wpm']} WPM)."
        )

    def _run_benchmark_set(self):
        self._benchmark_total = int(self.comp_rounds_spin.value())
        self._benchmark_round = 1
        self._benchmark_results = []
        self._benchmark_active = True
        self._append_system(f"Benchmark started: {self._benchmark_total} rounds. Score each round to continue.")
        self._run_comprehension_test()

    def _score_comprehension_test(self):
        if not self._comprehension_current:
            self._append_system("Generate a test first.")
            return

        correct = 0
        total = len(self._comprehension_current["questions"])
        for i, q in enumerate(self._comprehension_current["questions"]):
            selected = self.comp_q_combos[i].currentIndex() - 1
            if selected == int(q["answer"]):
                correct += 1

        elapsed = max(1.0, time.time() - (self._comprehension_started_at or time.time()))
        words = len(self._comprehension_current["passage"].split())
        wpm = int(words / (elapsed / 60.0))
        pct = int((correct / max(1, total)) * 100)
        self._record_comprehension_result(correct, total, pct, wpm)
        self.comp_result_lbl.setText(f"Score: {correct}/{total} ({pct}%) | Pace: ~{wpm} WPM")
        self._append_system(f"Comprehension result: {correct}/{total} ({pct}%), reading pace ~{wpm} WPM.")

        if self._benchmark_active:
            self._benchmark_results.append({"pct": pct, "wpm": wpm})
            if self._benchmark_round < self._benchmark_total:
                self._benchmark_round += 1
                self._run_comprehension_test()
                return

            self._benchmark_active = False
            avg_pct = int(sum(r["pct"] for r in self._benchmark_results) / max(1, len(self._benchmark_results)))
            avg_wpm = int(sum(r["wpm"] for r in self._benchmark_results) / max(1, len(self._benchmark_results)))
            self.comp_round_status_lbl.setText(f"Round: complete ({self._benchmark_total})")
            self.comp_result_lbl.setText(
                f"Benchmark done: avg {avg_pct}% | avg {avg_wpm} WPM over {self._benchmark_total} rounds"
            )
            self._append_system(
                f"Benchmark complete: avg accuracy {avg_pct}%, avg pace {avg_wpm} WPM over {self._benchmark_total} rounds."
            )
            self._save_settings()
            self._append_system("Benchmark results auto-saved.")

        self._update_recommendation_label()

    def _apply_voice_env_settings(self):
        os.environ["RAZ_VOICE_MODEL"] = str(self.voice_model)
        os.environ["RAZ_VOICE_RECORD_SECONDS"] = str(self.voice_record_seconds)
        os.environ["RAZ_VOICE_BEAM_SIZE"] = str(self.voice_beam_size)
        os.environ["RAZ_TTS_RATE"] = str(self.voice_tts_rate)
        try:
            import core.voice_engine as _ve
            _ve._MODEL = None
            _ve._TTS_ENGINE = None
        except Exception:
            pass

    def _apply_settings(self):
        self.ui_font_preset = self.font_preset_combo.currentText().strip() or "High Readability"
        self.ui_font_family = self.font_combo.currentText().strip() or "Segoe UI"
        self.ui_random_colors = self.random_colors_check.isChecked()
        self.ui_serious_mode = self.serious_mode_check.isChecked()
        self.ui_serious_bold = self.serious_bold_check.isChecked()
        self.ui_serious_italic = self.serious_italic_check.isChecked()
        # Emphasis bounce
        self.ui_emphasis_mode = self.emphasis_mode_check.isChecked()
        self.ui_emphasis_mood = self.emphasis_mood_combo.currentText()
        # Alert thresholds
        self.resource_alerts_enabled = self.alerts_check.isChecked()
        self.cpu_alert_pct = self.cpu_spin.value()
        self.ram_alert_pct = self.ram_spin.value()
        self.disk_alert_pct = self.disk_spin.value()
        self._last_alert_state = {}  # reset so re-enabled alerts can fire
        self.comp_benchmark_rounds = int(self.comp_rounds_spin.value())
        self.voice_model = self.voice_model_combo.currentText().strip() or "base"
        self.voice_record_seconds = int(self.voice_record_spin.value())
        self.voice_beam_size = int(self.voice_beam_spin.value())
        self.voice_tts_rate = int(self.voice_tts_rate_spin.value())
        self._apply_voice_env_settings()

        # Apply readability updates live.
        self._raz_font = QFont(self.ui_font_family, 13)
        self.chat_display.setFont(QFont(self.ui_font_family, 12))
        self.input_box.setFont(QFont(self.ui_font_family, 11))
        self.sys_display.setFont(QFont(self.ui_font_family, 11))
        self.sb_profile_display.setFont(QFont(self.ui_font_family, 11))
        self.sb_doc_list.setFont(QFont(self.ui_font_family, 10))
        self.sb_mentor_display.setFont(QFont(self.ui_font_family, 11))
        self.board_pending_display.setFont(QFont(self.ui_font_family, 10))
        self.board_followup_display.setFont(QFont(self.ui_font_family, 10))
        self.board_done_display.setFont(QFont(self.ui_font_family, 10))
        self.comp_passage_display.setFont(QFont(self.ui_font_family, 11))
        self._preview_comparison_fonts()
        self.comp_result_lbl.setStyleSheet(f"color: {self.ui_primary_color}; font-weight: bold;")
        self.comp_recommend_lbl.setStyleSheet(f"color: {self.ui_primary_color}; font-size: 10px; font-weight: bold;")

        self._update_status_style()
        self._append_system("Settings applied. Voice + readability + strategic mode updated.")

    def _save_settings(self):
        self._apply_settings()
        cfg = load_config()
        cfg["ui_font_preset"] = self.ui_font_preset
        cfg["ui_font_family"] = self.ui_font_family
        cfg["ui_primary_color"] = self.ui_primary_color
        cfg["ui_random_word_colors"] = bool(self.ui_random_colors)
        cfg["ui_serious_mode"] = bool(self.ui_serious_mode)
        cfg["ui_serious_color"] = self.ui_serious_color
        cfg["ui_serious_bold"] = bool(self.ui_serious_bold)
        cfg["ui_serious_italic"] = bool(self.ui_serious_italic)
        cfg["ui_emphasis_mode"] = bool(self.ui_emphasis_mode)
        cfg["ui_emphasis_mood"] = self.ui_emphasis_mood
        cfg["ui_emphasis_color_1"] = self.ui_emphasis_color_1
        cfg["ui_emphasis_color_2"] = self.ui_emphasis_color_2
        cfg["ui_emphasis_color_3"] = self.ui_emphasis_color_3
        cfg["resource_alerts_enabled"] = bool(self.resource_alerts_enabled)
        cfg["cpu_alert_pct"] = int(self.cpu_alert_pct)
        cfg["ram_alert_pct"] = int(self.ram_alert_pct)
        cfg["disk_alert_pct"] = int(self.disk_alert_pct)
        cfg["ui_comp_benchmark_rounds"] = int(self.comp_benchmark_rounds)
        cfg["ui_comp_history"] = list(self.comp_history[-40:])
        cfg["voice_model"] = self.voice_model
        cfg["voice_record_seconds"] = int(self.voice_record_seconds)
        cfg["voice_beam_size"] = int(self.voice_beam_size)
        cfg["voice_tts_rate"] = int(self.voice_tts_rate)
        save_config(cfg)
        self._append_system("Settings saved.")

    def _update_status_style(self):
        if self.connected:
            self.status_dot.setStyleSheet(f"color: {self.ui_primary_color}; font-size: 14px;")
            self.status_lbl.setStyleSheet(f"color: {self.ui_primary_color}; font-size: 11px; font-weight: bold;")
            self.status_lbl.setText("ONLINE")
        else:
            self.status_dot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px;")
            self.status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
            self.status_lbl.setText("NO API KEY")

    def _welcome(self):
        version = get_version()
        now     = datetime.now().strftime("%A, %B %d %Y  %I:%M %p")
        state   = "ONLINE" if self.connected else "NO API KEY - set one with /sys keys set <provider> <key>"
        self._append_raz(
            f"RAZ Core v{version} initialized.\n"
            f"{now}\n"
            f"Status: {state}\n\n"
            f"All systems active. Type a message or use the quick buttons below."
        )
        if not self.connected:
            self._append_system(
                "To connect: use secure key storage via /sys keys set openai sk-... or /sys keys set gemini AIza..."
            )

        # Remind Ryan about unresolved failures so nothing gets forgotten.
        try:
            followups = mem.get_followup_tasks(status="pending", limit=5)
            if followups:
                self._append_system(f"Pending follow-ups: {len(followups)} (showing latest 5)")
                for item in followups:
                    self._append_system(f"  #{item['id']} {item['title']}")
                self._append_system("Use /followups to view all and /done <id> to close one.")
        except Exception as e:
            self._append_system(f"Could not load follow-ups on startup: {e}")

        self._refresh_task_board()

    def _on_mode_change(self, mode: str):
        if self.raz_chat:
            self.raz_chat.mode = mode
            self.raz_chat._refresh_system_prompt()
            self._append_system(f"Mode switched to {mode.upper()}")

    def _set_mode(self, mode: str):
        """Programmatically switch mode and keep combo box in sync."""
        index = self.mode_combo.findText(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        else:
            self._on_mode_change(mode)

    def _toggle_voice_conversation(self):
        """Start or stop continuous voice conversation mode in-app."""
        if not self.raz_chat:
            self._append_system("Voice unavailable: RAZ chat not initialized.")
            return

        # Stop existing loop
        if self._voice_worker and self._voice_worker.isRunning():
            self._voice_worker.stop()
            self.voice_convo_btn.setText("Voice Convo ON")
            self._append_system("Stopping voice conversation after current turn...")
            return

        # Force mentor style for spoken deep-thinking workflow.
        self._set_mode("mentor")
        self._voice_worker = VoiceConversationWorker(self.raz_chat)
        self._voice_worker.status.connect(lambda s: self._append_system(f"[voice] {s}"))
        self._voice_worker.heard.connect(lambda t: self._append_user(f"[voice] {t}"))
        self._voice_worker.replied.connect(self._append_raz)
        self._voice_worker.error.connect(lambda e: self._append_system(f"[voice error] {e}"))
        self._voice_worker.finished.connect(lambda _m: self.voice_convo_btn.setText("Voice Convo ON"))
        self._voice_worker.finished.connect(lambda m: self._append_system(f"[voice] {m}"))
        self.voice_convo_btn.setText("Voice Convo OFF")
        self._voice_worker.start()

    def _run_voice_once(self):
        """Run one voice turn with clear status updates in chat."""
        if not self.raz_chat:
            self._append_system("Voice unavailable: RAZ chat not initialized.")
            return

        if self._voice_worker and self._voice_worker.isRunning():
            self._append_system("Voice Convo is active. Stop it before running Voice Once.")
            return

        if self._voice_once_worker and self._voice_once_worker.isRunning():
            return

        self._set_mode("mentor")
        self.voice_once_btn.setEnabled(False)
        self.voice_once_btn.setText("Listening...")

        self._voice_once_worker = VoiceOnceWorker(self.raz_chat)
        self._voice_once_worker.status.connect(lambda s: self._append_system(f"[voice] {s}"))
        self._voice_once_worker.heard.connect(lambda t: self._append_user(f"[voice] {t}"))
        self._voice_once_worker.replied.connect(self._append_raz)
        self._voice_once_worker.error.connect(lambda e: self._append_system(f"[voice error] {e}"))
        self._voice_once_worker.finished.connect(lambda _m: self.voice_once_btn.setEnabled(True))
        self._voice_once_worker.finished.connect(lambda _m: self.voice_once_btn.setText("Voice Once"))
        self._voice_once_worker.finished.connect(lambda m: self._append_system(f"[voice] {m}"))
        self._voice_once_worker.start()

    def _quick_cmd(self, cmd: str):
        self.input_box.setText(cmd)
        self._send()

    def _attach_image(self):
        """Open file picker, store selected image path, show indicator."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach Screenshot or Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All Files (*)"
        )
        if path:
            self._set_pending_image(path)

    def _paste_image_from_clipboard(self):
        """Check clipboard for an image and attach it if found."""
        clipboard = QApplication.clipboard()
        img = clipboard.image()
        if img and not img.isNull():
            # Save clipboard image to a temp file
            import tempfile
            os.makedirs(os.path.join(BASE_DIR, "memory"), exist_ok=True)
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False,
                dir=os.path.join(BASE_DIR, "memory")
            )
            tmp.close()
            img.save(tmp.name, "PNG")
            self._set_pending_image(tmp.name)
            self._append_system("Screenshot pasted from clipboard — ready to send.")
            return True
        return False

    def _set_pending_image(self, path: str):
        self._pending_image = path
        fname = os.path.basename(path)
        self.image_indicator.setText(f"📎 {fname}")
        pix = QPixmap(path)
        if not pix.isNull():
            self.image_thumb.setPixmap(pix.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_thumb.clear()
        self.image_indicator_row.setVisible(True)
        self.input_box.setPlaceholderText("Ask RAZ about this image...")

    def _clear_image_indicator(self):
        self._pending_image = None
        self.image_indicator.setText("")
        self.image_thumb.clear()
        self.image_indicator_row.setVisible(False)
        self.input_box.setPlaceholderText("Message RAZ...")

    def _start_response_loading(self):
        self._response_loading_tick = 0
        self.response_status_lbl.setText("RAZ is thinking")
        self.response_status_lbl.setVisible(True)
        if self._response_loading_timer is None:
            self._response_loading_timer = QTimer(self)
            self._response_loading_timer.setInterval(240)
            self._response_loading_timer.timeout.connect(self._tick_response_loading)
        if not self._response_loading_timer.isActive():
            self._response_loading_timer.start()

    def _tick_response_loading(self):
        phases = [
            "RAZ is thinking",
            "RAZ is mapping context",
            "RAZ is drafting response",
        ]
        base = phases[(self._response_loading_tick // 5) % len(phases)]
        dots = "." * (self._response_loading_tick % 4)
        self.response_status_lbl.setText(f"{base}{dots}")
        self._response_loading_tick += 1

    def _stop_response_loading(self):
        if self._response_loading_timer and self._response_loading_timer.isActive():
            self._response_loading_timer.stop()
        self.response_status_lbl.setVisible(False)
        self.response_status_lbl.setText("")

    def keyPressEvent(self, event):
        """Intercept Ctrl+V — if clipboard has an image, attach it instead of pasting text."""
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            if self._paste_image_from_clipboard():
                return  # consumed
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        """Allow Ctrl+V screenshot paste while focus is in the chat input."""
        try:
            if obj is self.input_box and event.type() == QEvent.KeyPress:
                if event.matches(QKeySequence.Paste) and self._paste_image_from_clipboard():
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _extract_links(self, text: str):
        """Extract markdown and plain URLs and return unique (label, url) pairs."""
        import re as _re
        links = []
        seen = set()

        md_pattern = _re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)')
        for label, url in md_pattern.findall(text or ""):
            clean = url.rstrip(".),;'")
            if clean and clean not in seen:
                links.append((label.strip() or clean, clean))
                seen.add(clean)

        url_pattern = _re.compile(r'https?://[^\s`>"\)\]\}]+')
        for url in url_pattern.findall(text or ""):
            clean = url.rstrip(".),;'")
            if clean and clean not in seen:
                domain = clean.split("//")[-1].split("/")[0]
                links.append((f"Open: {domain}", clean))
                seen.add(clean)

        return links

    def _trigger_self_repair(self):
        """Read current input as bug description; launch SelfRepairWorker."""
        description = self.input_box.text().strip()
        if not description:
            self._append_system(
                "Tell me what's broken in the message box, then click 🔧 Fix It."
            )
            return
        if not self.raz_chat or not self.raz_chat.client:
            self._append_system("No OpenAI connection — can't self-repair without GPT-4o.")
            return
        if self._repair_worker and self._repair_worker.isRunning():
            self._append_system("Self-repair already running...")
            return
        self.input_box.clear()
        self.fix_btn.setEnabled(False)
        self._append_system(f"SELF-REPAIR STARTED → \"{description}\"")
        self._repair_worker = SelfRepairWorker(self.raz_chat, description)
        self._repair_worker.progress.connect(
            lambda msg: self._append_system(f"[repair] {msg}")
        )
        self._repair_worker.finished.connect(self._on_repair_done)
        self._repair_worker.error.connect(self._on_repair_error)
        self._repair_worker.start()

    def _on_repair_done(self, msg: str):
        self.fix_btn.setEnabled(True)
        self._append_system(f"✓ {msg}")
        # Auto-restart after a short delay so user can see the message
        QTimer.singleShot(1800, self._restart_app)

    def _on_repair_error(self, err: str):
        self.fix_btn.setEnabled(True)
        self._append_system(f"[repair error] {err}")

    def _send(self):
        text = self.input_box.text().strip()
        image_path = self._pending_image
        if not text and not image_path:
            return
        self.input_box.clear()
        self._clear_image_indicator()
        self.send_btn.setEnabled(False)
        # Show user message with image tag if attached
        display_text = text or "[image attached]"
        if image_path:
            display_text = f"{display_text}  [📎 {os.path.basename(image_path)}]"
        self._append_user(display_text)

        if not self.raz_chat:
            self._append_raz("RAZ Core failed to initialize. Check the terminal for errors.")
            self.send_btn.setEnabled(True)
            self._stop_response_loading()
            return

        self._stream_started = False
        self._rainbow_pos    = 0
        self._start_response_loading()
        self.worker = LLMWorker(self.raz_chat, text, image_path=image_path)
        self.worker.partial.connect(self._on_raz_chunk)
        self.worker.finished.connect(self._on_response)
        self.worker.error.connect(self._on_error)
        self.worker.override.connect(self._on_override)
        self.worker.finished.connect(lambda: self.send_btn.setEnabled(True))
        self.worker.error.connect(lambda: self.send_btn.setEnabled(True))
        self.worker.finished.connect(lambda: self._stop_response_loading())
        self.worker.error.connect(lambda: self._stop_response_loading())
        self.worker.start()

    def _on_raz_chunk(self, chunk: str):
        """Each streamed token from LLM — rendered live in rainbow Playfair Display."""
        if not self._stream_started:
            self._stream_started = True
            self._stop_response_loading()
            self._insert_raz_header()
        self._append_rainbow_text(chunk)
        self._scroll_to_bottom()

    def _on_response(self, text: str):
        import re as _re
        cfg = load_config()
        provider = cfg.get("provider", "openai").strip().lower()
        # Only reconnect to OpenAI if the active provider is openai — don't override Groq/Ollama
        if provider == "openai" and cfg.get("openai_api_key", "").strip() and not self.connected:
            self.connected = True
            self._update_status_style()
            if self.raz_chat:
                from openai import OpenAI
                self.raz_chat.client = OpenAI(api_key=cfg["openai_api_key"])
        elif provider != "openai" and not self.connected:
            self.connected = True
            self._update_status_style()

        if self._stream_started:
            # Append command output lines (>>> ...) in bright green monospace
            cmd_outputs = _re.findall(r'(>>> .+)', text)
            if cmd_outputs:
                cursor = self.chat_display.textCursor()
                cursor.movePosition(QTextCursor.End)
                fmt = cursor.charFormat()
                fmt.setForeground(QColor("#00ff88"))
                fmt.setFontWeight(QFont.Normal)
                fmt.setFont(QFont("Consolas", 11))
                fmt.setAnchor(False)
                fmt.setFontUnderline(False)
                cursor.setCharFormat(fmt)
                for out in cmd_outputs:
                    cursor.insertText(f"\n{out}")
                self.chat_display.setTextCursor(cursor)

            # Auto-linkify markdown and plain URLs from the final response
            for label, url in self._extract_links(text):
                self._insert_link(f"[ {label} ]", url)

            # Trailing newline
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(TEXT_MAIN))
            fmt.setAnchor(False)
            fmt.setFontUnderline(False)
            cursor.setCharFormat(fmt)
            cursor.insertText("\n")
            self.chat_display.setTextCursor(cursor)
            self._scroll_to_bottom()
            self._stream_started = False
        else:
            # Slash command / instant response — check for URLs and linkify
            self._append_raz(text)
            for label, url in self._extract_links(text):
                self._insert_link(f"[ {label} ]", url)

        self._refresh_task_board()

    def _on_error(self, err: str):
        self._stop_response_loading()
        self._append_system(f"Error: {err}")

    def _on_override(self):
        """OpenAI refused — Groq is now answering. Show orange badge."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor("#ff6b00"))
        fmt.setFontWeight(QFont.Bold)
        fmt.setFont(QFont("Consolas", 10))
        fmt.setAnchor(False)
        fmt.setFontUnderline(False)
        cursor.setCharFormat(fmt)
        cursor.insertText("  \u26a1 guardrail hit \u2014 Groq override  ")
        # Reset
        fmt.setForeground(QColor(TEXT_MAIN))
        fmt.setFontWeight(QFont.Normal)
        cursor.setCharFormat(fmt)
        cursor.insertText("\n")
        self.chat_display.setTextCursor(cursor)
        self._scroll_to_bottom()

    # ── Chat rendering ────────────────────────────────────────────────────

    def _append_user(self, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor(TEXT_USER))
        fmt.setFontWeight(QFont.Bold)
        cursor.setCharFormat(fmt)
        cursor.insertText(f"\nYOU\n")

        fmt.setFontWeight(QFont.Normal)
        fmt.setForeground(QColor("#cccccc"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"{text}\n")

        self._scroll_to_bottom()

    def _append_raz(self, text: str):
        """Full RAZ response with rainbow Playfair Display (non-streaming)."""
        self._rainbow_pos = 0
        self._insert_raz_header()
        self._append_rainbow_text(text + "\n")
        self._scroll_to_bottom()

    def _append_system(self, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor(TEXT_DIM))
        fmt.setFontWeight(QFont.Normal)
        cursor.setCharFormat(fmt)
        cursor.insertText(f"\n[SYSTEM] {text}\n")

        self._scroll_to_bottom()

    def _insert_raz_header(self):
        """Insert 'RAZ' label in neon red. Call once before writing RAZ text."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = cursor.charFormat()
        header_color = self.ui_serious_color if self.ui_serious_mode else self.ui_primary_color
        fmt.setForeground(QColor(header_color))
        fmt.setFontWeight(QFont.Bold)
        fmt.setFont(QFont(self.ui_font_family, 11))
        cursor.setCharFormat(fmt)
        cursor.insertText("\nRAZ\n")
        self.chat_display.setTextCursor(cursor)

    def _append_rainbow_text(self, text: str):
        """Insert text word by word, each word gets a fully random neon color.
        Lines that start with WARNING/CAUTION/IMPORTANT/NOTE/CRITICAL/ERROR
        get emphasis bounce colors cycling through the configured palette.
        """
        import re as _re
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        raz_font = self._raz_font if self._raz_font else QFont(self.ui_font_family, 13)

        # Emphasis trigger keywords — these bounce colors across the WHOLE line
        _EMPHASIS_TRIGGERS = _re.compile(
            r"^(WARNING|CAUTION|IMPORTANT|NOTE|CRITICAL|ERROR|ALERT|!!!|\*\*WARNING|\*\*CAUTION|\*\*IMPORTANT|\*\*NOTE|\*\*CRITICAL|\*\*ERROR)",
            _re.IGNORECASE
        )
        # Build emphasis palette (3 cycling colors)
        _emphasis_palette = [
            getattr(self, "ui_emphasis_color_1", "#ffaa00"),
            getattr(self, "ui_emphasis_color_2", "#ff4400"),
            getattr(self, "ui_emphasis_color_3", "#ff0055"),
        ]
        _emphasis_mode_on = getattr(self, "ui_emphasis_mode", True)

        # Split text into lines to check per-line emphasis triggers
        lines = text.split("\n")
        for line_idx, line in enumerate(lines):
            is_emphasis_line = _emphasis_mode_on and bool(_EMPHASIS_TRIGGERS.match(line.strip()))
            _emph_idx = [0]  # mutable counter for closure

            tokens = _re.split(r"(\s+)", line)
            for token in tokens:
                if not token:
                    continue
                if token.strip():
                    if is_emphasis_line:
                        # Cycle through emphasis palette per-word
                        color = _emphasis_palette[_emph_idx[0] % len(_emphasis_palette)]
                        _emph_idx[0] += 1
                    elif self.ui_serious_mode:
                        color = self.ui_serious_color
                    else:
                        color = _random_neon() if self.ui_random_colors else self.ui_primary_color
                else:
                    color = self.ui_text_color
                fmt = cursor.charFormat()
                fmt.setForeground(QColor(color))
                if (self.ui_serious_mode and self.ui_serious_bold) or is_emphasis_line:
                    fmt.setFontWeight(QFont.Bold)
                else:
                    fmt.setFontWeight(QFont.Normal)
                fmt.setFontItalic(bool(self.ui_serious_mode and self.ui_serious_italic))
                fmt.setFont(raz_font)
                cursor.setCharFormat(fmt)
                cursor.insertText(token)

            # Re-insert the newline between lines (but not after the last)
            if line_idx < len(lines) - 1:
                fmt = cursor.charFormat()
                fmt.setForeground(QColor(self.ui_text_color))
                fmt.setFontWeight(QFont.Normal)
                cursor.setCharFormat(fmt)
                cursor.insertText("\n")

        self.chat_display.setTextCursor(cursor)

    def _scroll_to_bottom(self):
        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _insert_link(self, label: str, url: str, prefix: str = ""):
        """
        Insert a clickable hyperlink into chat_display.
        Rendered as bright green underlined text. Click opens in default browser.
        """
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        if prefix:
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(TEXT_MAIN))
            fmt.setAnchor(False)
            fmt.setFontUnderline(False)
            cursor.setCharFormat(fmt)
            cursor.insertText(prefix)

        link_fmt = cursor.charFormat()
        link_fmt.setForeground(QColor("#00ff88"))
        link_fmt.setFontUnderline(True)
        link_fmt.setAnchor(True)
        link_fmt.setAnchorHref(url)
        link_fmt.setFontWeight(QFont.Bold)
        cursor.setCharFormat(link_fmt)
        cursor.insertText(f" {label} ")

        # Reset format after link
        reset_fmt = cursor.charFormat()
        reset_fmt.setAnchor(False)
        reset_fmt.setFontUnderline(False)
        reset_fmt.setFontWeight(QFont.Normal)
        reset_fmt.setForeground(QColor(TEXT_MAIN))
        cursor.setCharFormat(reset_fmt)
        cursor.insertText("\n")
        self.chat_display.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _show_emerge_dialog(self):
        """Called when a new RAZ instance is trying to start — offer graceful handoff."""
        msg = QMessageBox(self)
        msg.setWindowTitle("RAZ SYSTEM")
        msg.setIcon(QMessageBox.Question)
        msg.setText(
            "\u26a1 RAZ senses another version trying to emerge.\n\n"
            "Would you like me to close this session so the new one can emerge?"
        )
        msg.setInformativeText("Your memory and session will be saved before closing.")
        yes_btn = msg.addButton("Yes — Emerge", QMessageBox.YesRole)
        no_btn  = msg.addButton("Stay on this one", QMessageBox.NoRole)
        msg.setDefaultButton(yes_btn)
        msg.setStyleSheet(
            "QMessageBox { background-color: #08000a; color: #00ff41; font-size: 13px; }"
            "QLabel { color: #00ff41; }"
            "QPushButton { background-color: #0a1a0a; color: #00ff41; border: 1px solid #00ff41; "
            "padding: 6px 18px; font-weight: bold; }"
            "QPushButton:hover { background-color: #00ff41; color: #08000a; }"
        )
        msg.exec()
        if msg.clickedButton() == yes_btn:
            self._restart_app()

    def _restart_app(self):
        """Kill this process and relaunch app.py cleanly."""
        global _instance_lock_sock
        try:
            if _instance_lock_sock:
                _instance_lock_sock.close()
                _instance_lock_sock = None
            if self.raz_chat:
                try:
                    self.raz_chat._cleanup()
                except Exception:
                    pass
        except Exception:
            pass
        import subprocess
        # Pin to venv interpreter when available; fallback to sys.executable
        _venv_py = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
        _interpreter = _venv_py if os.path.exists(_venv_py) else sys.executable
        subprocess.Popen([_interpreter, os.path.abspath(__file__)], cwd=BASE_DIR)
        QApplication.quit()

    def closeEvent(self, event):
        global _instance_lock_sock
        if _instance_lock_sock:
            try:
                _instance_lock_sock.close()
            except Exception:
                pass
            _instance_lock_sock = None
        if self.raz_chat:
            try:
                self.raz_chat._cleanup()
            except Exception:
                pass
        event.accept()


def _ensure_desktop_shortcut():
    """Create/update the RAZ desktop shortcut on every launch. Self-heals if deleted."""
    try:
        import subprocess as _sp
        ps_script = os.path.join(BASE_DIR, "system", "create_shortcut.ps1")
        if not os.path.exists(ps_script):
            return
        venv_python = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
        preferred_python = venv_python if os.path.exists(venv_python) else sys.executable
        icon_path = os.path.join(BASE_DIR, "assets", APP_ICON_FILE)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(BASE_DIR, "assets", "raz.ico")
        if not os.path.exists(icon_path):
            icon_path = sys.executable  # fallback to python icon
        app_target = os.path.join(BASE_DIR, "app_tablet.py" if TABLET_MODE else "app.py")
        _sp.Popen(
            [
                "powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script,
                "-PythonPath", preferred_python,
                "-AppPath",    app_target,
                "-IconPath",   icon_path,
                "-Cwd",        BASE_DIR,
                "-LinkName",   APP_SHORTCUT_NAME,
                "-Description", APP_DESCRIPTION,
            ],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0x08000000),
        )
    except Exception:
        pass  # never block app launch over a shortcut


def main():
    if TABLET_MODE:
        # Keep touch UI readable on high-DPI tablet displays.
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    mem.init_memory()
    init_version("1.0.2")
    _ensure_desktop_shortcut()

    # ── Single instance guard ────────────────────────────────────────────────
    if not acquire_instance_lock():
        # Another instance is running — signal it to offer graceful handoff, then exit silently
        signal_running_instance()
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG_DEEP))
    palette.setColor(QPalette.WindowText, QColor(TEXT_MAIN))
    palette.setColor(QPalette.Base, QColor(BG_PANEL))
    palette.setColor(QPalette.Text, QColor(TEXT_MAIN))
    palette.setColor(QPalette.Button, QColor(BG_PANEL))
    palette.setColor(QPalette.ButtonText, QColor(TEXT_MAIN))
    palette.setColor(QPalette.Highlight, QColor(NEON_RED))
    app.setPalette(palette)

    window = RAZDesktop()
    start_emerge_listener(window._emerge_signal.emit)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
