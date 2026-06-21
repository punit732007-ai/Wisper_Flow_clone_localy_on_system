"""
LocalWhisper — Paster
Pastes text at the current cursor position in any application
by copying to clipboard and simulating Ctrl+V.
"""

import time
import pyperclip
import pyautogui

# Disable the fail-safe (moving mouse to corner kills the script)
# — we don't want our background tool to crash unexpectedly.
pyautogui.FAILSAFE = False
# Speed up pyautogui pauses
pyautogui.PAUSE = 0.03


def paste_at_cursor(text: str) -> None:
    """Copy *text* to the clipboard, paste it with Ctrl+V, then
    restore the original clipboard contents."""
    if not text or not text.strip():
        return

    # Backup the current clipboard (best-effort — images etc. won't survive)
    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    # Copy the new text
    pyperclip.copy(text)
    time.sleep(0.04)  # tiny delay for clipboard sync

    # Simulate Ctrl+V
    pyautogui.hotkey("ctrl", "v")

    # Restore the old clipboard after a short delay
    def _restore():
        time.sleep(0.4)
        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass

    import threading
    threading.Thread(target=_restore, daemon=True).start()

    print(f"[Paster] Pasted {len(text)} chars OK")
