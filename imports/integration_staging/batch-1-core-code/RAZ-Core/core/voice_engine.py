"""
RAZ Voice Engine
Free local voice pipeline:
- STT: faster-whisper
- TTS: piper.exe when available, else pyttsx3 fallback
"""

import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
    from scipy.io.wavfile import write as wav_write
except Exception:
    sd = None
    wav_write = None

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


_MODEL: Optional["WhisperModel"] = None
_TTS_ENGINE = None


def _get_env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
        return value if value > 0 else default
    except Exception:
        return default


def _get_env_float(name: str, default: float) -> float:
    try:
        value = float(str(os.environ.get(name, default)).strip())
        return value if value > 0 else default
    except Exception:
        return default


def _get_voice_model_name() -> str:
    """
    Faster presets:
    - tiny: fastest, lowest accuracy
    - base: fast with better accuracy (default)
    - small: slower, higher accuracy
    """
    model = (os.environ.get("RAZ_VOICE_MODEL", "base") or "base").strip().lower()
    return model if model in {"tiny", "base", "small", "medium"} else "base"


def _get_record_seconds() -> int:
    # Lower default from 6s to 4s for better conversational responsiveness.
    return _get_env_int("RAZ_VOICE_RECORD_SECONDS", 4)


def _get_beam_size() -> int:
    # Beam 1 is significantly faster for realtime conversation.
    return _get_env_int("RAZ_VOICE_BEAM_SIZE", 1)


def _get_tts_rate() -> int:
    return _get_env_int("RAZ_TTS_RATE", 185)


def _get_preferred_voice_device() -> str:
    """
    Voice defaults to CPU for reliability on machines without full CUDA runtime.
    Set RAZ_VOICE_DEVICE=auto or cuda to opt into GPU attempts.
    """
    return (os.environ.get("RAZ_VOICE_DEVICE", "cpu") or "cpu").strip().lower()


def _ensure_whisper_model() -> "WhisperModel":
    global _MODEL
    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed")
    if _MODEL is None:
        # Small model is a practical default for local realtime use.
        # Default to CPU for robust startup; user can override with RAZ_VOICE_DEVICE.
        preferred_device = _get_preferred_voice_device()
        model_name = _get_voice_model_name()
        try:
            _MODEL = WhisperModel(model_name, device=preferred_device, compute_type="int8")
        except Exception as e:
            msg = str(e).lower()
            if "cublas" in msg or "cuda" in msg or "cudnn" in msg:
                print("RAZ VOICE: CUDA runtime not available, falling back to CPU model.")
                _MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")
            else:
                raise
    return _MODEL


def _record_wav(seconds: int = 6, sample_rate: int = 16000) -> str:
    if sd is None or wav_write is None:
        raise RuntimeError("sounddevice/scipy are not installed")

    print(f"RAZ VOICE: Listening for {seconds}s...")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()

    path = os.path.join(tempfile.gettempdir(), f"raz_voice_{int(time.time() * 1000)}.wav")
    pcm = np.int16(np.clip(audio, -1.0, 1.0) * 32767)
    wav_write(path, sample_rate, pcm)
    return path


def _transcribe(path: str) -> str:
    global _MODEL
    model = _ensure_whisper_model()
    beam_size = _get_beam_size()
    try:
        segments, _info = model.transcribe(
            path,
            beam_size=beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
        )
    except Exception as e:
        msg = str(e).lower()
        if "cublas" in msg or "cuda" in msg or "cudnn" in msg:
            print("RAZ VOICE: CUDA error during transcription, retrying on CPU.")
            _MODEL = WhisperModel(_get_voice_model_name(), device="cpu", compute_type="int8")
            segments, _info = _MODEL.transcribe(
                path,
                beam_size=beam_size,
                vad_filter=True,
                condition_on_previous_text=False,
            )
        else:
            raise
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text


def _speak_with_piper(text: str) -> bool:
    piper = shutil.which("piper") or shutil.which("piper.exe")
    if not piper:
        return False

    # Caller can set a specific model path via env var.
    model_path = os.environ.get("PIPER_MODEL_PATH", "")
    if not model_path or not os.path.exists(model_path):
        return False

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as out:
        out_path = out.name

    cmd = [piper, "-m", model_path, "-f", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    proc.communicate(input=text)

    if proc.returncode != 0:
        return False

    # Play through default system player
    os.startfile(out_path)
    return True


def _speak_with_pyttsx3(text: str) -> bool:
    global _TTS_ENGINE
    if pyttsx3 is None:
        return False
    if _TTS_ENGINE is None:
        _TTS_ENGINE = pyttsx3.init()
        _TTS_ENGINE.setProperty("rate", _get_tts_rate())

        # Optional voice preference by name hint, e.g. RAZ_TTS_VOICE_HINT=zira
        hint = (os.environ.get("RAZ_TTS_VOICE_HINT", "") or "").strip().lower()
        if hint:
            try:
                for v in _TTS_ENGINE.getProperty("voices"):
                    if hint in str(v.name).lower() or hint in str(v.id).lower():
                        _TTS_ENGINE.setProperty("voice", v.id)
                        break
            except Exception:
                pass

    _TTS_ENGINE.say(text)
    _TTS_ENGINE.runAndWait()
    return True


def speak_text(text: str) -> None:
    if _speak_with_piper(text):
        return
    if _speak_with_pyttsx3(text):
        return
    print("RAZ VOICE: No TTS backend available (install piper or pyttsx3).")


def run_voice_once(raz_chat) -> str:
    wav = _record_wav(seconds=_get_record_seconds())
    try:
        user_text = _transcribe(wav)
    finally:
        try:
            os.remove(wav)
        except Exception:
            pass

    if not user_text:
        return "RAZ: I did not catch that. Try /voice once again."

    print(f"YOU (voice): {user_text}")
    response = raz_chat.chat(user_text)
    speak_text(response)
    return f"RAZ VOICE captured: {user_text}\nRAZ: {response}"


def run_voice_loop(raz_chat) -> str:
    print("RAZ VOICE loop started. Press Ctrl+C to stop.")
    try:
        while True:
            result = run_voice_once(raz_chat)
            print(result)
    except KeyboardInterrupt:
        pass
    return "RAZ: Voice loop stopped."
