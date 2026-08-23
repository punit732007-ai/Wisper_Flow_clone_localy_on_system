"""
LocalWhisper Pro — Hotkey Manager
Ultra-reliable global keyboard listener using pynput for Push-to-Talk, Toggle, and VAD triggers.
Zero hangs, thread-safe start/stop, and dynamic key rebinding.
"""

import threading
from typing import Callable, Optional, Set
from pynput import keyboard
from config import config


class HotkeyManager:
    """Manages global hotkeys using pynput with exact key-up / key-down detection."""

    def __init__(
        self,
        on_start_record: Optional[Callable[[], None]] = None,
        on_stop_record: Optional[Callable[[], None]] = None,
        on_toggle_record: Optional[Callable[[], None]] = None,
        on_cycle_mode: Optional[Callable[[], None]] = None,
        on_cancel_record: Optional[Callable[[], None]] = None,
    ):
        self.on_start_record = on_start_record
        self.on_stop_record = on_stop_record
        self.on_toggle_record = on_toggle_record
        self.on_cycle_mode = on_cycle_mode
        self.on_cancel_record = on_cancel_record

        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: Set[str] = set()
        self._is_recording_active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the global keyboard listener thread."""
        with self._lock:
            self.stop()
            self._pressed_keys.clear()
            self._is_recording_active = False

            hotkey_str = config.get("hotkey", "ctrl+space").strip().lower()
            rec_mode = config.get("recording_mode", "push_to_talk")

            try:
                self._listener = keyboard.Listener(
                    on_press=self._handle_press,
                    on_release=self._handle_release,
                )
                self._listener.daemon = True
                self._listener.start()
                print(f"[HotkeyManager] Global hotkey active: '{hotkey_str}' (Mode: {rec_mode})")
            except Exception as e:
                print(f"[HotkeyManager] Failed to start keyboard listener: {e}")

    def stop(self) -> None:
        """Stop the global keyboard listener cleanly."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._pressed_keys.clear()
        self._is_recording_active = False

    def rebind(self) -> None:
        """Re-read configuration and reload listener."""
        self.start()

    # ── Key Normalization ─────────────────────────────────────────

    @staticmethod
    def _normalize_key(key) -> str:
        """Convert a pynput Key object or KeyCode to a lowercase identifier."""
        if isinstance(key, keyboard.Key):
            name = key.name.lower()
            if name in ("ctrl_l", "ctrl_r"):
                return "ctrl"
            if name in ("alt_l", "alt_r", "alt_gr"):
                return "alt"
            if name in ("shift_l", "shift_r"):
                return "shift"
            if name in ("cmd_l", "cmd_r"):
                return "win"
            return name
        elif isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.lower()
            if key.vk is not None:
                # Handle special virtual key codes if char is None
                if key.vk == 32:
                    return "space"
                return f"vk_{key.vk}"
        return str(key).lower()

    def _is_hotkey_matched(self, hotkey_str: str) -> bool:
        """Check if all keys in the target hotkey string are currently pressed."""
        required = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
        return all(k in self._pressed_keys for k in required)

    # ── Event Handlers ────────────────────────────────────────────

    def _handle_press(self, key) -> None:
        k_str = self._normalize_key(key)
        self._pressed_keys.add(k_str)

        # Cancel on Escape
        if k_str == "esc" and self._is_recording_active:
            self._is_recording_active = False
            if self.on_cancel_record:
                self.on_cancel_record()
            return

        hotkey_str = config.get("hotkey", "ctrl+space").strip().lower()
        rec_mode = config.get("recording_mode", "push_to_talk")

        if self._is_hotkey_matched(hotkey_str):
            if rec_mode == "push_to_talk":
                if not self._is_recording_active:
                    self._is_recording_active = True
                    if self.on_start_record:
                        self.on_start_record()
            else:
                # Toggle / VAD mode
                self._is_recording_active = not self._is_recording_active
                if self.on_toggle_record:
                    self.on_toggle_record()

    def _handle_release(self, key) -> None:
        k_str = self._normalize_key(key)
        self._pressed_keys.discard(k_str)

        rec_mode = config.get("recording_mode", "push_to_talk")
        hotkey_str = config.get("hotkey", "ctrl+space").strip().lower()

        if rec_mode == "push_to_talk" and self._is_recording_active:
            required = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
            # If any key of the hotkey combo was released, stop recording
            if k_str in required or not self._is_hotkey_matched(hotkey_str):
                self._is_recording_active = False
                if self.on_stop_record:
                    self.on_stop_record()
