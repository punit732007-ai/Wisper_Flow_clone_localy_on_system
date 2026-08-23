"""
LocalWhisper Pro — Sound Effects Engine
Provides subtle, non-intrusive audio cues for recording start, stop, success, and error.
Uses winsound on Windows without needing external asset files.
"""

import sys
import threading
from config import config


def _play_tone(frequency: int, duration_ms: int):
    """Play a synthesized audio tone in a background thread."""
    if not config.get("sound_effects", True):
        return

    def _worker():
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(frequency, duration_ms)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="audio-cue").start()


def play_start():
    """Crisp rising tone for recording start."""
    def _worker():
        if not config.get("sound_effects", True):
            return
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(880, 70)   # A5
                winsound.Beep(1174, 90)  # D6
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()


def play_stop():
    """Soft tone indicating recording finished."""
    def _worker():
        if not config.get("sound_effects", True):
            return
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(987, 80)   # B5
                winsound.Beep(784, 70)   # G5
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()


def play_success():
    """Pleasant chime for successful transcription and paste."""
    def _worker():
        if not config.get("sound_effects", True):
            return
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(1046, 60)  # C6
                winsound.Beep(1318, 90)  # E6
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()


def play_error():
    """Low alert tone for error."""
    def _worker():
        if not config.get("sound_effects", True):
            return
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(440, 150)  # A4
                winsound.Beep(330, 200)  # E4
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()
