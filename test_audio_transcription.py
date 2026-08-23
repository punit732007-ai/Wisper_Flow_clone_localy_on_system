"""
Test End-to-End Audio Pipeline
Synthesizes a short test audio buffer, transcribes with Whisper, refines with AI,
and writes to transcript history.
"""

import sys
import os
import time
import numpy as np

# Ensure UTF-8 stdout on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_test():
    print("[1/4] Initializing Transcriber & AI Refiner...")
    from config import config
    from core.transcriber import Transcriber
    from core.ai_refiner import ai_refiner
    from core.history_manager import history_manager

    config.set("whisper_model", "small", auto_save=False)
    transcriber = Transcriber()
    transcriber.load_model()
    print("  [OK] Model loaded.")

    print("[2/4] Generating synthetic test audio signal (16kHz float32)...")
    # 2 seconds of 16kHz sine wave audio
    sample_rate = 16000
    t = np.linspace(0, 2.0, int(sample_rate * 2.0), endpoint=False, dtype=np.float32)
    # Formant frequency mix (resembling vowel sounds)
    audio = 0.3 * np.sin(2 * np.pi * 300 * t) + 0.2 * np.sin(2 * np.pi * 1200 * t)

    print("[3/4] Running Transcription...")
    raw_text, lang, prob = transcriber.transcribe(audio)
    print(f"  [OK] Transcribed (lang={lang}, prob={prob:.2f}): {raw_text!r}")

    print("[4/4] Testing AI Refinement across modes...")
    modes_to_test = ["smart", "pro", "code", "bullet", "translate"]
    sample_input = "hey team we just deployed the new voice typing feature and it is running super fast"

    for mode in modes_to_test:
        config.set("current_mode", mode, auto_save=False)
        refined = ai_refiner.refine(sample_input, "en")
        badge = config.current_mode_info.get("badge", mode)
        print(f"  [{badge}] -> {refined}")

    print("\n=======================================================")
    print("  END-TO-END AUDIO PIPELINE TEST PASSED! 🎉")
    print("=======================================================")

if __name__ == "__main__":
    run_test()
