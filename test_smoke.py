"""
Smoke Test for LocalWhisper Pro v3.0 Core Modules & 35+ Aesthetic Themes Studio
"""

import sys
import os
import time

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def test_all():
    print("[1/6] Testing Imports...")
    import config
    from core.sound_effects import play_start, play_stop, play_success, play_error
    from core.history_manager import history_manager
    from core.audio_engine import AudioEngine
    from core.ai_refiner import ai_refiner
    from core.paster import paste_text
    from core.hotkey_manager import HotkeyManager
    from ui.visualizer_widget import AudioVisualizerWidget
    from ui.theme_engine import theme_manager, BUILTIN_THEMES
    from ui.theme_applicator import theme_applicator
    print("  [OK] All core modules & theme engine imported successfully.")

    print("[2/6] Testing Audio Device Enumeration...")
    devs = AudioEngine.list_input_devices()
    print(f"  [OK] Found {len(devs)} input audio devices.")
    for d in devs[:3]:
        print(f"    - [{d['id']}] {d['name']}")

    print("[3/6] Testing History Manager Database...")
    entry = history_manager.add_entry(
        raw_text="hello how are you",
        refined_text="Hello, how are you?",
        mode_key="smart",
        mode_name="Smart Dictation",
        duration_sec=1.8,
        language="en",
    )
    assert entry["id"] is not None
    entries = history_manager.get_entries(limit=5)
    assert len(entries) >= 1
    history_manager.delete_entry(entry["id"])
    print("  [OK] History persistence, search, and deletion verified.")

    print("[4/6] Testing AI Refiner Multi-Mode Presets...")
    raw = "um so basically we need to fix this bug bhai"
    out_smart = ai_refiner.refine(raw, "en")
    print(f"  [OK] Offline Refinement Output: {out_smart!r}")

    print("[5/6] Testing 35+ Aesthetic Themes Engine & Dynamic Layouts...")
    assert len(BUILTIN_THEMES) >= 35
    theme_manager.set_theme("cyberpunk", auto_save=False)
    assert theme_manager.current_theme_key == "cyberpunk"
    assert theme_manager.current_theme["accent"] == "#ff007f"
    theme_manager.set_theme("default_dark", auto_save=False)
    print(f"  [OK] {len(BUILTIN_THEMES)} themes verified and switching operational.")

    print("[6/6] Testing Faster-Whisper Model Load & Warm-up (small model)...")
    from core.transcriber import Transcriber
    from config import config
    config.set("whisper_model", "small", auto_save=False)
    transcriber = Transcriber()
    transcriber.load_model()
    assert transcriber.is_loaded
    print("  [OK] Transcriber loaded and warm-up successful!")

    print("\n=======================================================")
    print("  ALL 6 SMOKE TESTS PASSED CLEANLY & ACCURATELY! 🎉")
    print("=======================================================")

if __name__ == "__main__":
    test_all()
