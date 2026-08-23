"""
LocalWhisper Pro — Paster & Universal Typing Engine
Supports both high-speed clipboard pasting (Ctrl+V) and direct Windows SendInput
Unicode typing for applications that disallow clipboard pasting.
"""

import sys
import time
import threading
import ctypes
from typing import Optional
import pyperclip
import pyautogui
from config import config

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02

# ─── Windows SendInput Native Structures ──────────────────────────
if sys.platform == "win32":
    from ctypes import wintypes

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT_UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _anonymous_ = ("_union",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("_union", _INPUT_UNION),
        ]

    _user32 = ctypes.windll.user32
    _SendInput = _user32.SendInput
    _SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    _SendInput.restype = wintypes.UINT


def type_unicode_direct(text: str) -> None:
    """Directly type Unicode characters into the active window using Win32 SendInput."""
    if not text or sys.platform != "win32":
        return

    # Windows handles UTF-16 code units for SendInput Unicode
    utf16_bytes = text.encode("utf-16le")
    code_units = [
        int.from_bytes(utf16_bytes[i : i + 2], "little")
        for i in range(0, len(utf16_bytes), 2)
    ]

    inputs = []
    for unit in code_units:
        # Key down
        inp_down = INPUT(type=INPUT_KEYBOARD)
        inp_down.ki.wVk = 0
        inp_down.ki.wScan = unit
        inp_down.ki.dwFlags = KEYEVENTF_UNICODE
        inputs.append(inp_down)

        # Key up
        inp_up = INPUT(type=INPUT_KEYBOARD)
        inp_up.ki.wVk = 0
        inp_up.ki.wScan = unit
        inp_up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        inputs.append(inp_up)

    n_inputs = len(inputs)
    input_array = (INPUT * n_inputs)(*inputs)
    _SendInput(n_inputs, input_array, ctypes.sizeof(INPUT))


def paste_via_clipboard(text: str) -> None:
    """Copy text to clipboard, simulate Ctrl+V, and restore previous clipboard."""
    if not text:
        return

    old_clipboard = ""
    restore_enabled = config.get("restore_clipboard", True)
    if restore_enabled:
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            pass

    # Copy new text
    pyperclip.copy(text)
    time.sleep(0.04)

    # Trigger paste
    pyautogui.hotkey("ctrl", "v")

    # Restore old clipboard asynchronously
    if restore_enabled and old_clipboard:
        delay = config.get("clipboard_restore_delay", 0.4)

        def _restore():
            time.sleep(delay)
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass

        threading.Thread(target=_restore, daemon=True).start()


def type_unicode_pynput(text: str) -> None:
    from pynput.keyboard import Controller
    keyboard = Controller()
    keyboard.type(text)

def paste_text(text: str) -> None:
    """Universal paste dispatcher honoring user settings."""
    if not text or not text.strip():
        return

    # If the user is physically holding Ctrl, Shift, or Alt, it might combine with the typed text.
    # However, blindly calling keyUp("alt") on Windows triggers the application menu bar,
    # which can cause typed characters to trigger menu shortcuts (like Alt, F, X to close app).
    # We will only release Ctrl and Shift to be safe, using pynput.
    try:
        from pynput.keyboard import Controller, Key
        kb = Controller()
        kb.release(Key.ctrl)
        kb.release(Key.ctrl_l)
        kb.release(Key.ctrl_r)
        kb.release(Key.shift)
    except Exception:
        pass

    # Handle trailing space option
    if config.get("add_trailing_space", True) and not text.endswith((" ", "\n", "\t")):
        text = text + " "

    # Use pynput for highly reliable direct typing across all apps
    # This completely bypasses the OS clipboard and Windows Clipboard History (Win+V)
    type_unicode_pynput(text)
    print(f"[Paster] Typed {len(text)} characters (pynput) OK")
