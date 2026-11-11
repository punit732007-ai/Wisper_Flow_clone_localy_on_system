"""
LocalWhisper Pro — Sound Effects Engine
Provides smooth native Windows system chimes or completely silent operation.
Completely eliminates harsh PC speaker/buzzer beeps.
"""

import sys
import threading
from config import config


def _play_native_chime(sound_type: int = 0):
    """Play a gentle native Windows chime if sound effects are enabled."""
    if not config.get("sound_effects", False):
        return

    def _worker():
        try:
            if sys.platform == "win32":
                import winsound
                # MessageBeep uses smooth Windows OS audio device events (not PC motherboard buzzer)
                winsound.MessageBeep(sound_type)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="audio-cue").start()


def play_start():
    """Silent by default during recording start."""
    pass


def play_stop():
    """Silent by default when recording ends."""
    pass


def play_success():
    """Subtle Windows chime for success (only if user explicitly enables sound in settings)."""
    if config.get("sound_effects", False):
        _play_native_chime(0)  # MB_OK


def play_error():
    """Subtle Windows alert for errors (only if user explicitly enables sound in settings)."""
    if config.get("sound_effects", False):
        _play_native_chime(0x00000010)  # MB_ICONHAND
