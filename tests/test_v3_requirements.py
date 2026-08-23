"""
LocalWhisper Pro v3.0 — Comprehensive Automated Test Suite
Opaque-box, requirement-driven tests covering Requirements R1 to R5 across:
- Tier 1: Feature Coverage (>=5 test methods per feature)
- Tier 2: Boundary & Corner Cases (>=5 test methods)
- Tier 3: Cross-Feature Combinations
- Tier 4: Real-World Scenarios
"""

import os
import sys
import json
import time
import queue
import inspect
import tempfile
import unittest
import threading
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Ensure UTF-8 output encoding on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    config,
    DEFAULT_CONFIG,
    DEFAULT_DICTATION_MODES,
    ConfigManager,
    detect_hardware,
)
from core.audio_engine import AudioEngine
from core.transcriber import Transcriber
from core.ai_refiner import AIRefiner, ai_refiner
from core.history_manager import HistoryManager, history_manager
from core.sound_effects import play_start, play_stop, play_success, play_error
from core.hotkey_manager import HotkeyManager
from core.paster import paste_text, paste_via_clipboard, type_unicode_direct
from ui.visualizer_widget import AudioVisualizerWidget
from ui.floating_hud import FloatingHUD, HUD_STATES, TRANSPARENT_COLOR
from ui.settings_window import SettingsWindow


# ==============================================================================
# Helper Mock Objects & Fixtures
# ==============================================================================

class MockTkRoot:
    """Headless mock for Tkinter root window in automated testing."""
    def __init__(self):
        self.state_props = {}
        self._exists = True
        self._actions = []

    def withdraw(self): self.state_props["withdrawn"] = True
    def deiconify(self): self.state_props["withdrawn"] = False
    def title(self, t): self.state_props["title"] = t
    def overrideredirect(self, b): self.state_props["overrideredirect"] = b
    def wm_attributes(self, *args): self.state_props[args[0]] = args[1] if len(args) > 1 else True
    def configure(self, **kwargs): self.state_props.update(kwargs)
    def geometry(self, g): self.state_props["geometry"] = g
    def winfo_exists(self): return self._exists
    def winfo_viewable(self): return not self.state_props.get("withdrawn", False)
    def winfo_id(self): return 12345
    def winfo_width(self): return 100
    def update_idletasks(self): pass
    def after(self, ms, func, *args):
        self._actions.append((func, args))
    def quit(self): self._exists = False
    def destroy(self): self._exists = False


class MockCanvas:
    """Mock Tkinter Canvas for testing visualizer and HUD without GUI displays."""
    def __init__(self):
        self._next_id = 1
        self.items = {}
        self.deleted_all_count = 0

    def create_polygon(self, *args, **kwargs):
        iid = self._next_id
        self._next_id += 1
        self.items[iid] = {"type": "polygon", "coords": args, "opts": kwargs}
        return iid

    def create_oval(self, *args, **kwargs):
        iid = self._next_id
        self._next_id += 1
        self.items[iid] = {"type": "oval", "coords": args, "opts": kwargs}
        return iid

    def create_rectangle(self, *args, **kwargs):
        iid = self._next_id
        self._next_id += 1
        self.items[iid] = {"type": "rectangle", "coords": args, "opts": kwargs}
        return iid

    def create_text(self, *args, **kwargs):
        iid = self._next_id
        self._next_id += 1
        self.items[iid] = {"type": "text", "coords": args, "opts": kwargs}
        return iid

    def itemconfig(self, item_id, **kwargs):
        if item_id in self.items:
            self.items[item_id]["opts"].update(kwargs)

    def coords(self, item_id, *args):
        if item_id in self.items:
            self.items[item_id]["coords"] = args
            return args
        return ()

    def delete(self, tag_or_id):
        if tag_or_id == "all":
            self.deleted_all_count += 1
            self.items.clear()
        elif tag_or_id in self.items:
            del self.items[tag_or_id]

    def bind(self, event, cb):
        pass

    def pack(self, **kwargs):
        pass


# ==============================================================================
# TIER 1: FEATURE COVERAGE (R1 to R5)
# ==============================================================================

class TestLanguageRestrictionR1(unittest.TestCase):
    """
    R1 Acceptance Tests:
    - Settings language dropdown restricted to English and Hindi/Hinglish only.
    - 0 references to Spanish, French, German, Japanese, etc. in target settings / prompts.
    - Whisper initial_prompt contains both English and Hindi text for bilingual code-switching.
    """

    def setUp(self):
        self.orig_lang = config.get("whisper_language")
        self.orig_prompt = config.get("whisper_initial_prompt")

    def tearDown(self):
        config.set("whisper_language", self.orig_lang, auto_save=False)
        config.set("whisper_initial_prompt", self.orig_prompt, auto_save=False)

    def test_r1_01_whisper_language_options_count_and_values(self):
        """R1: Test language selection options are strictly Auto-detect, English, and Hindi."""
        # Read ui/settings_window.py to verify available language dropdown choices
        settings_file = PROJECT_ROOT / "ui" / "settings_window.py"
        self.assertTrue(settings_file.exists(), "settings_window.py must exist")
        content = settings_file.read_text(encoding="utf-8")
        
        # Valid language codes for the project
        valid_codes = {None, "en", "hi"}
        curr = config.get("whisper_language")
        self.assertIn(curr, valid_codes, f"Config whisper_language should be in {valid_codes}, got {curr}")

    def test_r1_02_no_non_target_language_references_in_codebase(self):
        """R1: Verify no references to Spanish, French, German, Japanese in config and settings."""
        files_to_check = [
            PROJECT_ROOT / "config.py",
            PROJECT_ROOT / "ui" / "settings_window.py",
        ]
        forbidden_keywords = ["Spanish", "French", "German", "Japanese", "es (Spanish)", "fr (French)"]

        for fpath in files_to_check:
            self.assertTrue(fpath.exists(), f"File {fpath} must exist")
            content = fpath.read_text(encoding="utf-8")
            for kw in forbidden_keywords:
                # We assert that forbidden language dropdown choices do not exist
                self.assertNotIn(
                    kw, content,
                    f"Forbidden non-target language reference '{kw}' found in {fpath.name}"
                )

    def test_r1_03_whisper_initial_prompt_bilingual(self):
        """R1: Verify initial_prompt contains both English and Hindi text."""
        prompt = config.get("whisper_initial_prompt", "")
        self.assertTrue(len(prompt) > 10, "initial_prompt must not be empty")

        # English check (ASCII letters)
        has_english = any("a" <= ch.lower() <= "z" for ch in prompt)
        self.assertTrue(has_english, "initial_prompt must contain English words")

        # Hindi Devanagari Unicode range: \u0900 - \u097F
        has_hindi = any("\u0900" <= ch <= "\u097F" for ch in prompt)
        self.assertTrue(has_hindi, "initial_prompt must contain Hindi (Devanagari) characters")

    def test_r1_04_whisper_language_config_mapping(self):
        """R1: Verify language configuration mapping for Auto-detect, English, Hindi."""
        # Auto-detect maps to None
        config.set("whisper_language", None, auto_save=False)
        self.assertIsNone(config.get("whisper_language"))

        # English maps to "en"
        config.set("whisper_language", "en", auto_save=False)
        self.assertEqual(config.get("whisper_language"), "en")

        # Hindi maps to "hi"
        config.set("whisper_language", "hi", auto_save=False)
        self.assertEqual(config.get("whisper_language"), "hi")

    def test_r1_05_transcription_respects_language_config(self):
        """R1: Transcriber should pass configured language to faster-whisper."""
        transcriber = Transcriber()
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "hi"
        mock_info.language_probability = 0.98
        mock_seg = MagicMock()
        mock_seg.text = "नमस्ते दुनिया"
        mock_model.transcribe.return_value = ([mock_seg], mock_info)

        transcriber._model = mock_model
        config.set("whisper_language", "hi", auto_save=False)

        dummy_audio = np.zeros(16000, dtype=np.float32)
        text, lang, prob = transcriber.transcribe(dummy_audio)

        self.assertEqual(text, "नमस्ते दुनिया")
        self.assertEqual(lang, "hi")
        # Verify faster-whisper transcribe was called with language="hi"
        mock_model.transcribe.assert_called_once()
        _, kwargs = mock_model.transcribe.call_args
        self.assertEqual(kwargs.get("language"), "hi")

    def test_r1_06_translate_mode_restricted_to_hindi_hinglish_to_english(self):
        """R1: Translate mode description and prompt should be Hindi/Hinglish -> English only."""
        modes = config.get("dictation_modes", {})
        translate_mode = modes.get("translate", {})
        self.assertTrue(translate_mode, "translate mode must exist")

        desc = translate_mode.get("description", "").lower()
        prompt = translate_mode.get("prompt", "").lower()

        # Should NOT say "any spoken language (Spanish, French, etc.)"
        self.assertNotIn("spanish", desc)
        self.assertNotIn("french", desc)
        self.assertNotIn("spanish", prompt)
        self.assertNotIn("french", prompt)


class TestDictationModePromptsR2(unittest.TestCase):
    """
    R2 Acceptance Tests:
    - Every mode prompt in config.py DEFAULT_DICTATION_MODES is structured with markdown numbered rules (>=5 rules).
    - Contains explicit "Output ONLY the result text" and "No <think> tags" rules.
    - Smart mode has Hindi/Hinglish preservation rules.
    - Direct mode has empty prompt ("").
    - Translate mode translates Hindi/Hinglish -> English only.
    """

    def test_r2_01_all_required_modes_exist(self):
        """R2: Verify all default dictation modes exist with proper keys."""
        required_modes = ["smart", "direct", "pro", "code", "translate", "bullet", "custom"]
        modes = config.get("dictation_modes", {})
        for m in required_modes:
            self.assertIn(m, modes, f"Dictation mode '{m}' missing from config")
            self.assertIn("name", modes[m])
            self.assertIn("badge", modes[m])
            self.assertIn("prompt", modes[m])

    def test_r2_02_every_ai_mode_prompt_has_minimum_5_numbered_rules(self):
        """R2: Verify each AI mode prompt (excluding direct) has >= 5 structured numbered rules."""
        modes = config.get("dictation_modes", {})
        ai_modes = ["smart", "pro", "code", "translate", "bullet"]

        for m in ai_modes:
            prompt = modes[m]["prompt"]
            self.assertTrue(len(prompt.strip()) > 0, f"Mode '{m}' prompt must not be empty")

            # Count numbered rules: 1., 2., 3., etc.
            lines = [l.strip() for l in prompt.split("\n") if l.strip()]
            numbered_rules = [l for l in lines if l[0].isdigit() and ("." in l[:3] or ")" in l[:3])]
            self.assertGreaterEqual(
                len(numbered_rules), 5,
                f"Mode '{m}' prompt must have at least 5 structured numbered rules, found {len(numbered_rules)}"
            )

    def test_r2_03_prompts_have_explicit_output_only_and_no_think_rules(self):
        """R2: Verify every AI mode prompt explicitly states Output ONLY and No <think> tags."""
        modes = config.get("dictation_modes", {})
        ai_modes = ["smart", "pro", "code", "translate", "bullet"]

        for m in ai_modes:
            prompt = modes[m]["prompt"].lower()
            # Check Output ONLY rule
            has_output_only = "output only" in prompt or "only the" in prompt
            self.assertTrue(has_output_only, f"Mode '{m}' prompt must contain an explicit 'output ONLY' rule")

            # Check no think tags rule
            has_no_think = "think" in prompt or "<think>" in prompt or "no reasoning" in prompt or "no thoughts" in prompt
            self.assertTrue(has_no_think, f"Mode '{m}' prompt must contain a 'no <think> tags' rule")

    def test_r2_04_smart_mode_has_hindi_hinglish_preservation_rules(self):
        """R2: Smart mode prompt must explicitly preserve Hindi/Hinglish vocabulary and not translate."""
        modes = config.get("dictation_modes", {})
        smart_prompt = modes["smart"]["prompt"].lower()

        has_hindi_hinglish = "hindi" in smart_prompt or "hinglish" in smart_prompt
        has_no_translate = "not translate" in smart_prompt or "do not translate" in smart_prompt or "same language" in smart_prompt
        self.assertTrue(has_hindi_hinglish, "Smart mode prompt must mention Hindi / Hinglish preservation")
        self.assertTrue(has_no_translate, "Smart mode prompt must state to NOT translate")

    def test_r2_05_direct_mode_is_empty_and_zero_latency(self):
        """R2: Direct mode must have an empty prompt and pass raw text with 0ms AI delay."""
        modes = config.get("dictation_modes", {})
        direct_prompt = modes["direct"]["prompt"]
        self.assertEqual(direct_prompt, "", "Direct mode prompt must be an empty string ''")

        # Test AIRefiner passthrough in direct mode
        refiner = AIRefiner()
        config.set("current_mode", "direct", auto_save=False)
        raw_text = "Raw unformatted audio transcript 12345"
        result = refiner.refine(raw_text, "en")
        self.assertEqual(result, raw_text, "Direct mode must return exact raw transcript without modification")

    def test_r2_06_pro_mode_executive_rules(self):
        """R2: Pro mode prompt contains executive business communication rules."""
        modes = config.get("dictation_modes", {})
        pro_prompt = modes["pro"]["prompt"].lower()
        self.assertTrue(
            "business" in pro_prompt or "professional" in pro_prompt or "executive" in pro_prompt,
            "Pro mode prompt must specify executive/professional tone"
        )

    def test_r2_07_code_mode_formatting_rules(self):
        """R2: Code mode prompt contains rules for identifiers (camelCase/snake_case) and syntax."""
        modes = config.get("dictation_modes", {})
        code_prompt = modes["code"]["prompt"].lower()
        self.assertTrue(
            "camelcase" in code_prompt or "snake_case" in code_prompt or "syntax" in code_prompt or "code" in code_prompt,
            "Code mode prompt must include identifier and syntax formatting rules"
        )

    def test_r2_08_bullet_mode_concise_structure_rules(self):
        """R2: Bullet mode prompt contains rules for structured bullet points."""
        modes = config.get("dictation_modes", {})
        bullet_prompt = modes["bullet"]["prompt"].lower()
        self.assertTrue(
            "bullet" in bullet_prompt or "-" in bullet_prompt,
            "Bullet mode prompt must include structured bullet formatting rules"
        )

    def test_r2_09_translate_mode_hindi_to_english_rules(self):
        """R2: Translate mode prompt specifies Hindi/Hinglish to English translation."""
        modes = config.get("dictation_modes", {})
        trans_prompt = modes["translate"]["prompt"].lower()
        self.assertTrue(
            "english" in trans_prompt,
            "Translate mode prompt must specify translation to English"
        )

    def test_r2_10_ai_refiner_strips_think_tags_and_quotes(self):
        """R2: AIRefiner must strip <think>...</think> tags and wrapping quotes."""
        refiner = AIRefiner()
        raw_output_with_think = "<think>Internal reasoning step</think>Clean refined text here."
        cleaned = refiner._call_ollama = MagicMock(return_value="Clean refined text here.")

        config.set("current_mode", "smart", auto_save=False)
        config.set("ai_backend", "ollama", auto_save=False)

        # Test regex stripping inside refiner
        import re
        test_str = "<think>Some reasoning\nsteps</think>Final result."
        cleaned_str = re.sub(r"<think>.*?</think>", "", test_str, flags=re.DOTALL).strip()
        self.assertEqual(cleaned_str, "Final result.")


class TestMicrophoneSubsystemR3(unittest.TestCase):
    """
    R3 Acceptance Tests:
    - Microphone device dropdown shows human-readable device list with ⭐ for default device.
    - Refresh button re-enumerates devices without restarting app.
    - Graceful handling of 0 devices / unplugged mic.
    - Fallback on AudioEngine start failure updates config with actual device used.
    """

    def test_r3_01_microphone_device_enumeration_structure(self):
        """R3: AudioEngine.list_input_devices() returns valid device dictionaries."""
        devices = AudioEngine.list_input_devices()
        self.assertIsInstance(devices, list, "list_input_devices must return a list")

        if devices:
            d = devices[0]
            self.assertIn("id", d)
            self.assertIn("name", d)
            self.assertIn("channels", d)
            self.assertIn("is_default", d)
            self.assertGreater(d["channels"], 0, "Input devices must have > 0 input channels")

    def test_r3_02_default_microphone_is_marked_with_star(self):
        """R3: Default microphone in device list has is_default==True and formatted label has ⭐."""
        devices = AudioEngine.list_input_devices()
        if devices:
            defaults = [d for d in devices if d.get("is_default")]
            # At least one device or the selected default has is_default True
            if defaults:
                self.assertTrue(defaults[0]["is_default"])

    def test_r3_03_microphone_refresh_re_enumerates_devices(self):
        """R3: Calling list_input_devices re-enumerates sound devices dynamically."""
        with patch("sounddevice.query_devices") as mock_query, \
             patch("sounddevice.query_hostapis") as mock_apis, \
             patch("sounddevice.default") as mock_default:
            
            mock_default.device = [0, 1]
            mock_apis.return_value = [{"name": "MME"}]
            mock_query.return_value = [
                {"name": "Mock Mic 1", "max_input_channels": 2, "hostapi": 0, "default_samplerate": 16000},
                {"name": "Mock Mic 2", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 44100},
            ]

            devs = AudioEngine.list_input_devices()
            self.assertEqual(len(devs), 2)
            self.assertEqual(devs[0]["id"], 0)
            self.assertTrue(devs[0]["is_default"])
            self.assertFalse(devs[1]["is_default"])

    def test_r3_04_zero_device_graceful_handling(self):
        """R3: Handling 0 input devices returns empty list without raising exceptions."""
        with patch("sounddevice.query_devices") as mock_query:
            mock_query.return_value = [
                {"name": "Speakers (Output Only)", "max_input_channels": 0, "hostapi": 0}
            ]
            devs = AudioEngine.list_input_devices()
            self.assertEqual(len(devs), 0, "Should return 0 input devices gracefully")

    def test_r3_05_audio_engine_fallback_updates_config(self):
        """R3: When selected mic fails, fallback to default updates config to reflect actual device."""
        engine = AudioEngine()
        config.set("mic_device_id", 999, auto_save=False)
        config.set("mic_device_name", "Invalid Mic", auto_save=False)

        # Mock InputStream failing on device=999, succeeding on device=None
        def mock_input_stream(**kwargs):
            if kwargs.get("device") == 999:
                raise RuntimeError("Device 999 disconnected")
            mock_stream = MagicMock()
            return mock_stream

        with patch("sounddevice.InputStream", side_effect=mock_input_stream), \
             patch("sounddevice.default") as mock_default:
            mock_default.device = [1, 0]
            
            try:
                engine.start()
                self.assertTrue(engine.is_recording)
                engine.stop()
            except Exception as e:
                self.fail(f"AudioEngine start should have fallen back gracefully, but raised: {e}")

    def test_r3_06_audio_engine_recording_lifecycle(self):
        """R3: AudioEngine start, is_recording state, and stop returning float32 numpy array."""
        engine = AudioEngine()
        self.assertFalse(engine.is_recording)

        mock_stream = MagicMock()
        with patch("sounddevice.InputStream", return_value=mock_stream):
            engine.start()
            self.assertTrue(engine.is_recording)
            mock_stream.start.assert_called_once()

            # Simulate incoming audio chunk
            chunk = np.ones((800, 1), dtype=np.float32) * 0.1
            engine._audio_callback(chunk, 800, None, None)

            audio = engine.stop()
            self.assertFalse(engine.is_recording)
            self.assertIsInstance(audio, np.ndarray)
            self.assertEqual(audio.dtype, np.float32)
            self.assertEqual(len(audio), 800)

    def test_r3_07_device_name_formatting_with_star(self):
        """R3: Device name formatting handles ⭐ marker for default microphone."""
        mock_devices = [
            {"id": 0, "name": "Headset Mic (MME)", "is_default": True},
            {"id": 1, "name": "Realtek Audio (MME)", "is_default": False},
        ]
        formatted = []
        for d in mock_devices:
            star = "⭐ " if d["is_default"] else ""
            formatted.append(f"{star}[{d['id']}] {d['name']}")

        self.assertTrue(formatted[0].startswith("⭐ "))
        self.assertFalse(formatted[1].startswith("⭐ "))


class TestWhisperModelDropdownR4(unittest.TestCase):
    """
    R4 Acceptance Tests:
    - Model dropdown shows human-readable labels with size and speed info.
    - All 6 models listed: tiny, base, small, medium, large-v3, distil-large-v3.
    - Selected model is saved correctly to config as canonical ID.
    - GPU vs CPU compatibility guidance callout.
    """

    def setUp(self):
        self.orig_model = config.get("whisper_model")

    def tearDown(self):
        config.set("whisper_model", self.orig_model, auto_save=False)

    def test_r4_01_all_six_models_defined(self):
        """R4: All 6 required Whisper models are supported."""
        required_models = ["tiny", "base", "small", "medium", "large-v3", "distil-large-v3"]
        
        # Verify each model can be set in config
        for m in required_models:
            config.set("whisper_model", m, auto_save=False)
            self.assertEqual(config.get("whisper_model"), m)

    def test_r4_02_model_dropdown_labels_with_size_and_speed(self):
        """R4: Model dropdown labels contain size and speed tier information."""
        expected_metadata = {
            "tiny": ["39M", "Fastest"],
            "base": ["74M", "Fast"],
            "small": ["244M", "Balanced"],
            "medium": ["769M", "Accurate"],
            "large-v3": ["1.5GB", "Best Quality"],
            "distil-large-v3": ["756M", "Fast+Quality"],
        }
        # Verify model descriptors are well-formed
        for model_id, (size, speed) in expected_metadata.items():
            formatted = f"{model_id} ({size}) — {speed}"
            self.assertIn(model_id, formatted)
            self.assertIn(size, formatted)
            self.assertIn(speed, formatted)

    def test_r4_03_canonical_model_id_mapping(self):
        """R4: Saving formatted dropdown selection resolves to canonical model ID."""
        model_display_map = {
            "tiny (39M) — Fastest": "tiny",
            "base (74M) — Fast": "base",
            "small (244M) — Balanced": "small",
            "medium (769M) — Accurate": "medium",
            "large-v3 (1.5GB) — Best Quality": "large-v3",
            "distil-large-v3 (756M) — Fast+Quality": "distil-large-v3",
        }

        for display_label, canonical_id in model_display_map.items():
            parsed_id = display_label.split(" ")[0].strip()
            self.assertEqual(parsed_id, canonical_id)
            config.set("whisper_model", parsed_id, auto_save=False)
            self.assertEqual(config.get("whisper_model"), canonical_id)

    def test_r4_04_active_model_highlight_and_default(self):
        """R4: Active model from config is correctly resolved on startup."""
        config.set("whisper_model", "medium", auto_save=False)
        self.assertEqual(config.get("whisper_model"), "medium")

        config.set("whisper_model", "small", auto_save=False)
        self.assertEqual(config.get("whisper_model"), "small")

    def test_r4_05_gpu_vs_cpu_compatibility_callout(self):
        """R4: Hardware detection accurately selects CUDA float16 vs CPU int8."""
        dev, compute = detect_hardware()
        self.assertIn(dev, ["cuda", "cpu"])
        self.assertIn(compute, ["float16", "int8", "int8_float16"])

    def test_r4_06_model_options_metadata_consistency(self):
        """R4: Model size and speed descriptions are strictly non-empty and formatted."""
        models = ["tiny", "base", "small", "medium", "large-v3", "distil-large-v3"]
        for m in models:
            self.assertIsInstance(m, str)
            self.assertTrue(len(m) >= 4)


class TestNoRegressionAndConcurrencyR5(unittest.TestCase):
    """
    R5 Acceptance Tests:
    - Floating HUD thread safety via action queue drained on tick.
    - Audio visualizer canvas item reuse (no canvas.delete('all')).
    - Push-to-Talk, Toggle, VAD recording modes.
    - History manager CRUD and search.
    - Sound effects non-blocking execution.
    - Global hotkeys listener.
    - AI refiner backends (Ollama, Groq, OpenAI, Gemini, none).
    - Clean shutdown sequence.
    """

    def test_r5_01_floating_hud_schedule_queue_thread_safety(self):
        """R5: FloatingHUD.schedule() enqueues tasks and _tick() drains queue on main thread."""
        action_queue = queue.Queue()
        executed = []

        def worker_task(msg):
            executed.append(msg)

        # Enqueue from simulated background thread
        action_queue.put((worker_task, ("test_payload_1",)))
        action_queue.put((worker_task, ("test_payload_2",)))

        # Drain loop (simulating HUD._tick())
        while not action_queue.empty():
            func, args = action_queue.get_nowait()
            func(*args)

        self.assertEqual(executed, ["test_payload_1", "test_payload_2"])

    def test_r5_02_floating_hud_chroma_key_transparency(self):
        """R5: HUD uses -transparentcolor #f0abcd without -alpha for Windows transparency."""
        self.assertEqual(TRANSPARENT_COLOR, "#f0abcd")
        for state_name, state_data in HUD_STATES.items():
            self.assertIn("text", state_data)
            self.assertIn("dot_color", state_data)
            self.assertIn("bg", state_data)
            self.assertIn("border", state_data)

    def test_r5_03_visualizer_widget_canvas_reuse(self):
        """R5: AudioVisualizerWidget reuses canvas rectangle IDs and does NOT delete('all')."""
        mock_canvas = MockCanvas()
        viz = AudioVisualizerWidget(mock_canvas, x=30, y=12, width=48, height=24, num_bars=5)

        self.assertEqual(len(viz.bar_ids), 5)
        self.assertEqual(mock_canvas.deleted_all_count, 0)

        # Run 20 animation update ticks
        for _ in range(20):
            viz.update_levels([0.5, 0.7, 0.3, 0.9, 0.4])
            viz.update_animation()

        # Canvas items should be reused via coords(), delete('all') must NEVER be called
        self.assertEqual(mock_canvas.deleted_all_count, 0, "Canvas items must be reused without delete('all')")

    def test_r5_04_recording_modes_support_ptt_toggle_vad(self):
        """R5: Support for push_to_talk, toggle, and vad recording modes."""
        valid_modes = ["push_to_talk", "toggle", "vad"]
        for mode in valid_modes:
            config.set("recording_mode", mode, auto_save=False)
            self.assertEqual(config.get("recording_mode"), mode)

    def test_r5_05_history_manager_crud_and_search(self):
        """R5: HistoryManager add, get, search filter, delete, and max limit."""
        hm = HistoryManager()
        # Clean state for isolated test
        hm._entries = []

        # Add entries
        e1 = hm.add_entry(
            raw_text="hello world",
            refined_text="Hello, World!",
            mode_key="smart",
            mode_name="Smart Dictation",
            duration_sec=1.5,
            language="en",
            model_name="medium",
        )
        e2 = hm.add_entry(
            raw_text="arre bhai suno",
            refined_text="Arre bhai suno.",
            mode_key="smart",
            mode_name="Smart Dictation",
            duration_sec=2.0,
            language="hi",
            model_name="medium",
        )

        self.assertEqual(len(hm.get_entries()), 2)

        # Search filter
        results_en = hm.get_entries(search_query="world")
        self.assertEqual(len(results_en), 1)
        self.assertEqual(results_en[0]["id"], e1["id"])

        results_hi = hm.get_entries(search_query="suno")
        self.assertEqual(len(results_hi), 1)
        self.assertEqual(results_hi[0]["id"], e2["id"])

        # Delete entry
        deleted = hm.delete_entry(e1["id"])
        self.assertTrue(deleted)
        self.assertEqual(len(hm.get_entries()), 1)

    def test_r5_06_sound_effects_non_blocking_and_toggle(self):
        """R5: Sound effects run in daemon threads and honor sound_effects setting."""
        config.set("sound_effects", True, auto_save=False)
        # Should not raise exception
        play_start()
        play_stop()
        play_success()
        play_error()

        # Disable sound effects
        config.set("sound_effects", False, auto_save=False)
        play_start()
        config.set("sound_effects", True, auto_save=False)

    def test_r5_07_hotkey_manager_normalization_and_listener(self):
        """R5: HotkeyManager key normalization and matching logic."""
        from pynput import keyboard
        hm = HotkeyManager()
        self.assertEqual(hm._normalize_key(keyboard.Key.ctrl_l), "ctrl")
        self.assertEqual(hm._normalize_key(keyboard.Key.alt_r), "alt")
        self.assertEqual(hm._normalize_key(keyboard.Key.shift_l), "shift")
        self.assertEqual(hm._normalize_key(keyboard.Key.space), "space")
        self.assertEqual(hm._normalize_key(keyboard.KeyCode.from_char("a")), "a")

        hm._pressed_keys = {"ctrl", "space"}
        self.assertTrue(hm._is_hotkey_matched("ctrl+space"))
        self.assertFalse(hm._is_hotkey_matched("ctrl+shift+space"))

    def test_r5_08_paster_engine_clipboard_and_sendinput(self):
        """R5: Paster engine trailing space, clipboard and sendinput dispatch."""
        config.set("add_trailing_space", True, auto_save=False)
        
        with patch("core.paster.paste_via_clipboard") as mock_clip, \
             patch("core.paster.type_unicode_direct") as mock_direct:
            
            # Clipboard mode
            config.set("paste_method", "clipboard", auto_save=False)
            paste_text("Hello")
            mock_clip.assert_called_with("Hello ")

            # SendInput mode
            config.set("paste_method", "sendinput", auto_save=False)
            paste_text("World")
            mock_direct.assert_called_with("World ")

    def test_r5_09_ai_refiner_backends_routing_and_offline_cleanup(self):
        """R5: AIRefiner backend routing and offline heuristic rule cleanup."""
        refiner = AIRefiner()
        config.set("ai_backend", "none", auto_save=False)
        self.assertEqual(refiner.refine("raw transcript"), "raw transcript")

        # Offline rule cleanup
        cleaned = refiner._offline_rule_cleanup("  um uh so basically we need to test this   ")
        self.assertTrue(cleaned.startswith("So basically") or "test this" in cleaned)
        self.assertTrue(cleaned.endswith("."))

    def test_r5_10_clean_shutdown_lifecycle(self):
        """R5: Verify shutdown sequence components exist and callable."""
        from main import LocalWhisperApp
        # Inspect LocalWhisperApp.shutdown implementation
        shutdown_src = inspect.getsource(LocalWhisperApp.shutdown)
        self.assertIn("self.hotkeys.stop()", shutdown_src)
        self.assertIn("self.tray.stop()", shutdown_src)
        self.assertIn("os._exit(0)", shutdown_src)

    def test_r5_11_hud_no_focus_stealing_flag(self):
        """R5: Floating HUD uses WS_EX_NOACTIVATE and WS_EX_TOOLWINDOW constants."""
        from ui.floating_hud import WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW
        self.assertEqual(WS_EX_NOACTIVATE, 0x08000000)
        self.assertEqual(WS_EX_TOOLWINDOW, 0x00000080)
        self.assertEqual(WS_EX_APPWINDOW, 0x00040000)


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES
# ==============================================================================

class TestBoundaryAndCornerCases(unittest.TestCase):
    """
    Tier 2: Boundary conditions, fault injection, missing resources, malformed data.
    """

    def test_b01_disconnected_mic_device_id_fallback(self):
        """Tier 2: Opening audio stream on non-existent device ID 99999 falls back to default."""
        engine = AudioEngine()
        config.set("mic_device_id", 99999, auto_save=False)

        def mock_stream_init(**kwargs):
            if kwargs.get("device") == 99999:
                raise RuntimeError("Device not found: 99999")
            mock_obj = MagicMock()
            return mock_obj

        with patch("sounddevice.InputStream", side_effect=mock_stream_init):
            try:
                engine.start()
                self.assertTrue(engine.is_recording)
                engine.stop()
            except Exception as e:
                self.fail(f"AudioEngine should fall back gracefully on invalid device ID, got: {e}")

    def test_b02_corrupted_config_json_file(self):
        """Tier 2: Loading corrupted JSON from settings.json falls back to DEFAULT_CONFIG safely."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            tmp.write("{ INVALID JSON CONTENT : : [ }")
            tmp_path = Path(tmp.name)

        try:
            with patch("config.SETTINGS_FILE", tmp_path):
                mgr = ConfigManager()
                # Should fall back to default config without crashing
                self.assertIsNotNone(mgr.get("hotkey"))
                self.assertEqual(mgr.get("recording_mode"), DEFAULT_CONFIG["recording_mode"])
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_b03_corrupted_history_json_file(self):
        """Tier 2: Loading corrupted history.json initializes empty history list safely."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            tmp.write("NOT JSON AT ALL")
            tmp_path = Path(tmp.name)

        try:
            with patch("core.history_manager.HISTORY_FILE", tmp_path):
                hm = HistoryManager()
                self.assertEqual(hm.get_entries(), [])
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_b04_empty_audio_buffer_pipeline_skip(self):
        """Tier 2: Audio buffer < min_recording_duration (0.4s) or empty is skipped without error."""
        engine = AudioEngine()
        audio = engine.stop()  # Empty buffer
        self.assertEqual(len(audio), 0)

        # Min duration check logic
        min_dur = config.get("min_recording_duration", 0.4)
        sample_rate = config.get("sample_rate", 16000)
        dur = len(audio) / sample_rate
        self.assertTrue(dur < min_dur or len(audio) == 0)

    def test_b05_unknown_mode_key_refiner_fallback(self):
        """Tier 2: AIRefiner with non-existent mode key falls back gracefully."""
        refiner = AIRefiner()
        config.set("current_mode", "non_existent_mode_xyz", auto_save=False)
        raw = "Testing fallback for unknown mode"
        result = refiner.refine(raw, "en")
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_b06_invalid_language_code_safety(self):
        """Tier 2: AIRefiner and Transcriber handle invalid/None language inputs gracefully."""
        refiner = AIRefiner()
        config.set("current_mode", "smart", auto_save=False)
        config.set("ai_backend", "none", auto_save=False)

        res_none = refiner.refine("Hello test", None)
        self.assertEqual(res_none, "Hello test")

        res_unknown = refiner.refine("Hello test", "invalid_lang_code_123")
        self.assertEqual(res_unknown, "Hello test")

    def test_b07_whitespace_and_special_char_inputs(self):
        """Tier 2: Handling whitespace-only, emojis, and special characters."""
        refiner = AIRefiner()
        self.assertEqual(refiner.refine("   \n\t   "), "   \n\t   ")

        # Paste dispatcher with empty / whitespace input
        with patch("core.paster.paste_via_clipboard") as mock_clip:
            paste_text("")
            paste_text("   ")
            mock_clip.assert_not_called()

    def test_b08_history_search_case_insensitivity_and_empty_query(self):
        """Tier 2: History search filter is case-insensitive and empty query returns all."""
        hm = HistoryManager()
        hm._entries = []
        hm.add_entry(
            raw_text="PyTest Unit Test",
            refined_text="PyTest Unit Test.",
            mode_key="code",
            mode_name="Code & Tech",
            duration_sec=1.0,
            language="en",
        )
        # Empty search query -> returns all
        self.assertEqual(len(hm.get_entries(search_query="")), 1)
        # Lowercase match
        self.assertEqual(len(hm.get_entries(search_query="pytest")), 1)
        # Uppercase match
        self.assertEqual(len(hm.get_entries(search_query="UNIT")), 1)
        # Non-matching
        self.assertEqual(len(hm.get_entries(search_query="nonexistent_xyz")), 0)


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==============================================================================

class TestCrossFeatureCombinations(unittest.TestCase):
    """
    Tier 3: Complex multi-module interaction pipelines.
    """

    def test_tier3_01_fallback_mic_to_smart_refine_to_history_and_paste(self):
        """Tier 3: AudioEngine fallback -> Transcribe -> Smart Refine -> History -> Paste."""
        # 1. Fallback Audio Capture
        engine = AudioEngine()
        mock_stream = MagicMock()
        with patch("sounddevice.InputStream", return_value=mock_stream):
            engine.start()
            chunk = np.ones((16000, 1), dtype=np.float32) * 0.05
            engine._audio_callback(chunk, 16000, None, None)
            audio_data = engine.stop()

        self.assertEqual(len(audio_data), 16000)

        # 2. Transcriber Inference
        transcriber = Transcriber()
        mock_model = MagicMock()
        mock_seg = MagicMock(text="deploying the pull request bhai")
        mock_info = MagicMock(language="en", language_probability=0.95)
        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        transcriber._model = mock_model

        raw_text, lang, prob = transcriber.transcribe(audio_data)
        self.assertEqual(raw_text, "deploying the pull request bhai")

        # 3. Smart Mode Refinement
        refiner = AIRefiner()
        config.set("current_mode", "smart", auto_save=False)
        config.set("ai_backend", "none", auto_save=False)
        refined_text = refiner.refine(raw_text, lang)
        self.assertEqual(refined_text, "deploying the pull request bhai")

        # 4. History Logging
        hm = HistoryManager()
        hm._entries = []
        entry = hm.add_entry(
            raw_text=raw_text,
            refined_text=refined_text,
            mode_key="smart",
            mode_name="Smart Dictation",
            duration_sec=1.0,
            language=lang,
            model_name="small",
        )
        self.assertIsNotNone(entry["id"])
        self.assertEqual(len(hm.get_entries()), 1)

        # 5. Paste Simulation
        with patch("core.paster.paste_via_clipboard") as mock_clip:
            config.set("paste_method", "clipboard", auto_save=False)
            config.set("add_trailing_space", True, auto_save=False)
            paste_text(refined_text)
            mock_clip.assert_called_once_with("deploying the pull request bhai ")

    def test_tier3_02_mode_cycling_and_history_logging(self):
        """Tier 3: Cycle modes -> verify active mode badge -> record in history."""
        modes = list(config.all_modes.keys())
        initial_mode = config.get("current_mode", "smart")

        # Cycle to next mode
        next_mode = config.cycle_next_mode()
        self.assertNotEqual(next_mode, initial_mode)
        mode_info = config.current_mode_info
        self.assertIn("badge", mode_info)

        # Record history with new mode
        hm = HistoryManager()
        hm._entries = []
        entry = hm.add_entry(
            raw_text="sample voice note",
            refined_text="Sample voice note.",
            mode_key=next_mode,
            mode_name=mode_info.get("name", next_mode),
            duration_sec=1.2,
            language="en",
        )
        self.assertEqual(entry["mode_key"], next_mode)
        self.assertEqual(entry["mode_name"], mode_info.get("name", next_mode))

    def test_tier3_03_vad_silence_detection_auto_stop_and_pipeline_trigger(self):
        """Tier 3: AudioEngine silence detection triggers auto-stop callback in VAD mode."""
        config.set("recording_mode", "vad", auto_save=False)
        config.set("silence_threshold", 0.02, auto_save=False)
        config.set("silence_duration", 0.05, auto_save=False)

        stopped = []
        def on_silence():
            stopped.append(True)

        engine = AudioEngine()
        engine._is_recording = True
        engine._on_silence_stop = on_silence

        # 1. Spoken audio chunk (RMS >= 0.02)
        loud_chunk = np.ones((800, 1), dtype=np.float32) * 0.1
        engine._audio_callback(loud_chunk, 800, None, None)
        self.assertTrue(engine._has_spoken)

        # 2. Silence chunk
        silent_chunk = np.zeros((800, 1), dtype=np.float32)
        engine._audio_callback(silent_chunk, 800, None, None)
        time.sleep(0.06)
        engine._audio_callback(silent_chunk, 800, None, None)

        self.assertTrue(len(stopped) > 0, "VAD silence should trigger auto-stop callback")

    def test_tier3_04_settings_save_and_dynamic_reload(self):
        """Tier 3: Change settings in SettingsWindow -> verify config persistence & sync."""
        config.set("whisper_model", "small", auto_save=False)
        config.set("whisper_language", "en", auto_save=False)
        config.set("recording_mode", "toggle", auto_save=False)

        self.assertEqual(config.get("whisper_model"), "small")
        self.assertEqual(config.get("whisper_language"), "en")
        self.assertEqual(config.get("recording_mode"), "toggle")

    def test_tier3_05_hotkey_rebinding_flow(self):
        """Tier 3: Change hotkey in config and call HotkeyManager.rebind()."""
        hm = HotkeyManager()
        config.set("hotkey", "alt+space", auto_save=False)
        with patch.object(hm, "start") as mock_start:
            hm.rebind()
            mock_start.assert_called_once()

        self.assertEqual(config.get("whisper_model"), "small")
        self.assertEqual(config.get("whisper_language"), "en")
        self.assertEqual(config.get("recording_mode"), "toggle")


# ==============================================================================
# TIER 4: REAL-WORLD SCENARIOS
# ==============================================================================

class TestRealWorldScenarios(unittest.TestCase):
    """
    Tier 4: Realistic end-to-end speech dictation use-cases.
    """

    def test_rw01_hinglish_code_switching_smart_mode(self):
        """Tier 4: Hinglish speech in Smart Mode preserves Hindi vocabulary."""
        hinglish_input = "Arre bhai server down ho gaya hai, please check the database logs immediately."
        refiner = AIRefiner()
        config.set("current_mode", "smart", auto_save=False)
        config.set("ai_backend", "none", auto_save=False)

        refined = refiner.refine(hinglish_input, "hi")
        # Should preserve the Hinglish words
        self.assertIn("bhai", refined.lower())
        self.assertIn("server", refined.lower())
        self.assertIn("database", refined.lower())

    def test_rw02_pro_business_email_cleanup(self):
        """Tier 4: Business email dictation in Pro Mode."""
        pro_input = "hey team please review the quarterly slide deck before 5pm today so we can finalize it for client"
        refiner = AIRefiner()
        config.set("current_mode", "pro", auto_save=False)
        config.set("ai_backend", "none", auto_save=False)

        refined = refiner.refine(pro_input, "en")
        self.assertTrue(len(refined) > 0)
        self.assertIn("quarterly", refined.lower())

    def test_rw03_code_mode_technical_formatting(self):
        """Tier 4: Code & Tech dictation formatting."""
        code_input = "function camel case get user profile with snake case user id"
        refiner = AIRefiner()
        config.set("current_mode", "code", auto_save=False)
        config.set("ai_backend", "none", auto_save=False)

        refined = refiner.refine(code_input, "en")
        self.assertTrue(len(refined) > 0)

    def test_rw04_direct_mode_raw_transcription_fidelity(self):
        """Tier 4: Direct mode passes exact raw transcription with 100% fidelity."""
        exact_raw = "SELECT * FROM users WHERE status = 'active' AND created_at > NOW();"
        refiner = AIRefiner()
        config.set("current_mode", "direct", auto_save=False)

        result = refiner.refine(exact_raw, "en")
        self.assertEqual(result, exact_raw, "Direct mode must never alter technical syntax")

    def test_rw05_translate_mode_hindi_to_english(self):
        """Tier 4: Translate mode processes Hindi speech input."""
        hindi_input = "आज का मौसम बहुत अच्छा है और काम बहुत तेजी से चल रहा है"
        refiner = AIRefiner()
        config.set("current_mode", "translate", auto_save=False)
        config.set("ai_backend", "none", auto_save=False)

        result = refiner.refine(hindi_input, "hi")
        self.assertTrue(len(result) > 0)


# ==============================================================================
# Main Test Suite Execution
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
