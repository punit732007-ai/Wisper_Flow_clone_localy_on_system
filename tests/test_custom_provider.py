"""
LocalWhisper Pro — Unit Tests for Other / Custom Model API Provider (Milestone 2)

Verifies:
1. Config keys and JSON serialization/deserialization for custom provider.
2. AIRefiner.check_backend_status() across 200 OK, empty credentials, 401/403 Auth errors,
   other HTTP reachability codes, and network exceptions.
3. AIRefiner._call_custom() payload structure, bearer token headers, think-tag stripping,
   quote stripping, and HTTP/network error fallbacks.
4. AIRefiner.refine() dispatching and fallback behavior.
5. SettingsWindow UI variable initialization, in-memory test staging, and persistence binding.
"""

import sys
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tkinter as tk
from tkinter import ttk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safely import core.audio_engine, only mock if optional audio dependencies are missing
try:
    import core.audio_engine
except Exception:
    if "core.audio_engine" not in sys.modules:
        sys.modules["core.audio_engine"] = MagicMock()

from config import DEFAULT_CONFIG, ConfigManager, config
from core.ai_refiner import AIRefiner
from ui.settings_window import SettingsWindow


class TestCustomProviderConfig(unittest.TestCase):
    """Test configuration defaults, accessors, and serialization for custom provider."""

    def test_default_config_keys(self):
        """Verify DEFAULT_CONFIG has custom provider keys with expected defaults."""
        self.assertIn("custom_base_url", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["custom_base_url"], "https://api.openai.com/v1")
        self.assertIn("custom_api_key", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["custom_api_key"], "")
        self.assertIn("custom_model", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["custom_model"], "gpt-4o-mini")

    def test_config_get_and_set(self):
        """Verify setting and getting custom provider settings."""
        orig_backend = config.get("ai_backend")
        orig_url = config.get("custom_base_url")
        orig_key = config.get("custom_api_key")
        orig_model = config.get("custom_model")

        try:
            config.set("ai_backend", "custom", auto_save=False)
            config.set("custom_base_url", "http://localhost:8000/v1", auto_save=False)
            config.set("custom_api_key", "sk-test-12345", auto_save=False)
            config.set("custom_model", "deepseek-ai/DeepSeek-V3", auto_save=False)

            self.assertEqual(config.get("ai_backend"), "custom")
            self.assertEqual(config.get("custom_base_url"), "http://localhost:8000/v1")
            self.assertEqual(config.get("custom_api_key"), "sk-test-12345")
            self.assertEqual(config.get("custom_model"), "deepseek-ai/DeepSeek-V3")
        finally:
            config.set("ai_backend", orig_backend, auto_save=False)
            config.set("custom_base_url", orig_url, auto_save=False)
            config.set("custom_api_key", orig_key, auto_save=False)
            config.set("custom_model", orig_model, auto_save=False)

    def test_config_serialization_deserialization(self):
        """Verify saving to and loading from a JSON settings file preserves custom provider keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "settings.json"
            test_data = {
                "ai_backend": "custom",
                "custom_base_url": "https://api.mistral.ai/v1",
                "custom_api_key": "secret-mistral-key",
                "custom_model": "mistral-large-latest",
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(test_data, f)

            with patch("config.SETTINGS_FILE", tmp_path):
                mgr = ConfigManager()
                self.assertEqual(mgr.get("ai_backend"), "custom")
                self.assertEqual(mgr.get("custom_base_url"), "https://api.mistral.ai/v1")
                self.assertEqual(mgr.get("custom_api_key"), "secret-mistral-key")
                self.assertEqual(mgr.get("custom_model"), "mistral-large-latest")


class TestCustomBackendStatus(unittest.TestCase):
    """Test AIRefiner.check_backend_status() for custom and other provider modes."""

    def setUp(self):
        self.refiner = AIRefiner()
        self.orig_backend = config.get("ai_backend")
        self.orig_url = config.get("custom_base_url")
        self.orig_key = config.get("custom_api_key")
        self.orig_model = config.get("custom_model")

    def tearDown(self):
        config.set("ai_backend", self.orig_backend, auto_save=False)
        config.set("custom_base_url", self.orig_url, auto_save=False)
        config.set("custom_api_key", self.orig_key, auto_save=False)
        config.set("custom_model", self.orig_model, auto_save=False)

    def test_status_missing_base_url(self):
        """Return False if custom_base_url is empty."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "", auto_save=False)
        config.set("custom_model", "gpt-4o-mini", auto_save=False)

        ok, msg = self.refiner.check_backend_status()
        self.assertFalse(ok)
        self.assertIn("Base URL not set", msg)

    def test_status_missing_model(self):
        """Return False if custom_model is empty."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_model", "", auto_save=False)

        ok, msg = self.refiner.check_backend_status()
        self.assertFalse(ok)
        self.assertIn("Model name not set", msg)

    @patch("core.ai_refiner.requests.get")
    def test_status_success_200_with_bearer_token(self, mock_get):
        """Return True with online message and pass Authorization header when key is provided."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "https://api.openai.com/v1/", auto_save=False)
        config.set("custom_api_key", "sk-valid-key", auto_save=False)
        config.set("custom_model", "gpt-4o", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        ok, msg = self.refiner.check_backend_status()
        self.assertTrue(ok)
        self.assertIn("Custom API Online", msg)
        self.assertIn("gpt-4o", msg)

        # Verify endpoint and header
        mock_get.assert_called_once_with(
            "https://api.openai.com/v1/models",
            headers={"Authorization": "Bearer sk-valid-key"},
            timeout=5,
        )

    @patch("core.ai_refiner.requests.get")
    def test_status_success_200_without_bearer_token(self, mock_get):
        """Empty API key is accepted and omits Authorization header (for local LAN servers)."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "http://192.168.1.100:1234/v1", auto_save=False)
        config.set("custom_api_key", "", auto_save=False)
        config.set("custom_model", "local-model", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        ok, msg = self.refiner.check_backend_status()
        self.assertTrue(ok)
        self.assertIn("Custom API Online", msg)

        mock_get.assert_called_once_with(
            "http://192.168.1.100:1234/v1/models",
            headers={},
            timeout=5,
        )

    @patch("core.ai_refiner.requests.get")
    def test_status_auth_failure_401(self, mock_get):
        """Return False on HTTP 401 Unauthorized."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-invalid", auto_save=False)
        config.set("custom_model", "gpt-4o", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        ok, msg = self.refiner.check_backend_status()
        self.assertFalse(ok)
        self.assertIn("Auth Failed (HTTP 401)", msg)

    @patch("core.ai_refiner.requests.get")
    def test_status_auth_failure_403(self, mock_get):
        """Return False on HTTP 403 Forbidden."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-no-perms", auto_save=False)
        config.set("custom_model", "gpt-4o", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        ok, msg = self.refiner.check_backend_status()
        self.assertFalse(ok)
        self.assertIn("Auth Failed (HTTP 403)", msg)

    @patch("core.ai_refiner.requests.get")
    def test_status_reachable_other_code(self, mock_get):
        """Return True with Reachable message on non-auth HTTP response (e.g. 404)."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "http://localhost:5000/v1", auto_save=False)
        config.set("custom_model", "custom-model", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        ok, msg = self.refiner.check_backend_status()
        self.assertTrue(ok)
        self.assertIn("Custom API Reachable (HTTP 404)", msg)

    @patch("core.ai_refiner.requests.get")
    def test_status_network_exception(self, mock_get):
        """Return False when request raises connection error or timeout."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "http://127.0.0.1:9999/v1", auto_save=False)
        config.set("custom_model", "test-model", auto_save=False)

        mock_get.side_effect = ConnectionRefusedError("Connection refused")

        ok, msg = self.refiner.check_backend_status()
        self.assertFalse(ok)
        self.assertIn("Custom API not reachable:", msg)

    @patch("core.ai_refiner.requests.get")
    def test_status_backend_alias_other(self, mock_get):
        """Verify 'other' backend alias routes to custom provider status check."""
        config.set("ai_backend", "other", auto_save=False)
        config.set("custom_base_url", "https://api.groq.com/openai/v1", auto_save=False)
        config.set("custom_api_key", "gsk-123", auto_save=False)
        config.set("custom_model", "llama-3.3-70b", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        ok, msg = self.refiner.check_backend_status()
        self.assertTrue(ok)
        self.assertIn("Custom API Online", msg)


class TestCustomProviderInference(unittest.TestCase):
    """Test AIRefiner._call_custom() and refine() integration."""

    def setUp(self):
        self.refiner = AIRefiner()
        self.orig_backend = config.get("ai_backend")
        self.orig_url = config.get("custom_base_url")
        self.orig_key = config.get("custom_api_key")
        self.orig_model = config.get("custom_model")
        self.orig_mode = config.get("current_mode")
        config.set("current_mode", "smart", auto_save=False)

    def tearDown(self):
        config.set("ai_backend", self.orig_backend, auto_save=False)
        config.set("custom_base_url", self.orig_url, auto_save=False)
        config.set("custom_api_key", self.orig_key, auto_save=False)
        config.set("custom_model", self.orig_model, auto_save=False)
        config.set("current_mode", self.orig_mode, auto_save=False)

    @patch("core.ai_refiner.requests.post")
    def test_call_custom_payload_structure(self, mock_post):
        """Verify _call_custom sends standard OpenAI chat completions payload and headers."""
        config.set("custom_base_url", "https://api.openai.com/v1/", auto_save=False)
        config.set("custom_api_key", "sk-inference-key", auto_save=False)
        config.set("custom_model", "gpt-4o-mini", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Clean refined transcription."}}]
        }
        mock_post.return_value = mock_resp

        res = self.refiner._call_custom("System instructions", "User voice input")
        self.assertEqual(res, "Clean refined transcription.")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-inference-key")
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(kwargs["timeout"], 15)

        payload = kwargs["json"]
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["temperature"], 0.1)
        self.assertEqual(payload["max_tokens"], 512)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "System instructions"},
                {"role": "user", "content": "User voice input"},
            ],
        )

    @patch("core.ai_refiner.requests.post")
    def test_call_custom_no_key_omits_authorization(self, mock_post):
        """Verify _call_custom omits Authorization header when api_key is empty."""
        config.set("custom_base_url", "http://localhost:11434/v1", auto_save=False)
        config.set("custom_api_key", "", auto_save=False)
        config.set("custom_model", "qwen2.5:7b", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Local output."}}]
        }
        mock_post.return_value = mock_resp

        res = self.refiner._call_custom("System", "User")
        self.assertEqual(res, "Local output.")

        _, kwargs = mock_post.call_args
        self.assertNotIn("Authorization", kwargs["headers"])

    @patch("core.ai_refiner.requests.post")
    def test_call_custom_strips_think_tags(self, mock_post):
        """Verify _call_custom strips DeepSeek reasoning <think>...</think> tags."""
        config.set("custom_base_url", "https://api.deepseek.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-ds-key", auto_save=False)
        config.set("custom_model", "deepseek-reasoner", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>\nAnalyzing the prompt\nGrammar correction\n</think>Hello world, this is final text."
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = self.refiner._call_custom("System", "User")
        self.assertEqual(res, "Hello world, this is final text.")

    @patch("core.ai_refiner.requests.post")
    def test_call_custom_strips_enclosing_quotes(self, mock_post):
        """Verify _call_custom strips surrounding double or single quotation marks."""
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-test", auto_save=False)
        config.set("custom_model", "gpt-4o-mini", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '"Quoted response from model."'}}]
        }
        mock_post.return_value = mock_resp

        res = self.refiner._call_custom("System", "User")
        self.assertEqual(res, "Quoted response from model.")

    @patch("core.ai_refiner.requests.post")
    def test_call_custom_http_error_returns_none(self, mock_post):
        """Verify _call_custom returns None on HTTP 500 error."""
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-test", auto_save=False)
        config.set("custom_model", "gpt-4o-mini", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        res = self.refiner._call_custom("System", "User")
        self.assertIsNone(res)

    @patch("core.ai_refiner.requests.post")
    def test_call_custom_network_error_returns_none(self, mock_post):
        """Verify _call_custom returns None when request raises an exception."""
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-test", auto_save=False)
        config.set("custom_model", "gpt-4o-mini", auto_save=False)

        mock_post.side_effect = TimeoutError("Request timed out")

        res = self.refiner._call_custom("System", "User")
        self.assertIsNone(res)

    @patch("core.ai_refiner.requests.post")
    def test_refine_dispatches_to_custom(self, mock_post):
        """Verify refine() dispatches to custom backend when ai_backend is 'custom'."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.custom.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-custom", auto_save=False)
        config.set("custom_model", "custom-model", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Refined output from custom API."}}]
        }
        mock_post.return_value = mock_resp

        result = self.refiner.refine("raw voice dictation text", language="en")
        self.assertEqual(result, "Refined output from custom API.")

    @patch("core.ai_refiner.requests.post")
    def test_refine_custom_error_falls_back_to_offline_cleanup(self, mock_post):
        """Verify refine() falls back to _offline_rule_cleanup when custom backend fails."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.custom.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-custom", auto_save=False)
        config.set("custom_model", "custom-model", auto_save=False)

        mock_post.side_effect = ConnectionError("Connection dropped")

        result = self.refiner.refine("um uh hello world this is testing", language="en")
        # Offline rule cleanup removes "um" and "uh", capitalizes, and appends a period
        self.assertEqual(result, "Hello world this is testing.")

    def test_refine_direct_mode_passthrough(self):
        """Direct mode skips AI backend completely even when custom backend is configured."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "direct", auto_save=False)

        raw = "um uh exact unformatted text"
        result = self.refiner.refine(raw, language="en")
        self.assertEqual(result, raw)


class TestCustomProviderSettingsUI(unittest.TestCase):
    """Test SettingsWindow UI variable initialization, staging, and save persistence."""

    def setUp(self):
        import copy
        self.root = tk.Tk()
        self.root.withdraw()
        self.orig_backend = config.get("ai_backend")
        self.orig_url = config.get("custom_base_url")
        self.orig_key = config.get("custom_api_key")
        self.orig_model = config.get("custom_model")
        self.orig_modes = copy.deepcopy(config.get("dictation_modes"))

    def tearDown(self):
        import copy
        config.set("ai_backend", self.orig_backend, auto_save=False)
        config.set("custom_base_url", self.orig_url, auto_save=False)
        config.set("custom_api_key", self.orig_key, auto_save=False)
        config.set("custom_model", self.orig_model, auto_save=False)
        config.set("dictation_modes", copy.deepcopy(self.orig_modes), auto_save=False)
        try:
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass
        import gc
        gc.collect()

    def test_settings_window_custom_variables_initialized(self):
        """Verify custom_base_url_var, custom_key_var, and custom_model_var are initialized in SettingsWindow."""
        config.set("custom_base_url", "https://my-endpoint.org/v1", auto_save=False)
        config.set("custom_api_key", "sk-init-test", auto_save=False)
        config.set("custom_model", "llama-3-8b", auto_save=False)

        win = SettingsWindow(self.root)
        notebook = ttk.Notebook(self.root)
        win._build_ai_tab(notebook)

        self.assertTrue(hasattr(win, "custom_base_url_var"))
        self.assertEqual(win.custom_base_url_var.get(), "https://my-endpoint.org/v1")

        self.assertTrue(hasattr(win, "custom_key_var"))
        self.assertEqual(win.custom_key_var.get(), "sk-init-test")

        self.assertTrue(hasattr(win, "custom_model_var"))
        self.assertEqual(win.custom_model_var.get(), "llama-3-8b")

    @patch("ui.settings_window.messagebox.showinfo")
    def test_settings_window_save_persists_custom_values(self, mock_msgbox):
        """Verify _save_all persists modified custom provider entries to config."""
        win = SettingsWindow(self.root)
        notebook = ttk.Notebook(self.root)
        win._build_ai_tab(notebook)

        # Mutate UI variables
        win.ai_backend_var.set("custom")
        win.custom_base_url_var.set("https://custom-host.com/v1")
        win.custom_key_var.set("sk-updated-key")
        win.custom_model_var.set("mistral-small")

        # Provide dummy vars for other tabs touched by _save_all
        win.model_var = tk.StringVar(value="small")
        win.whisper_dev_var = tk.StringVar(value="cpu")
        win.lang_var = tk.StringVar(value="en (English)")
        win.init_prompt_txt = tk.Text(self.root)
        win.init_prompt_txt.insert("1.0", "Hello, my name is Punit. I speak in English and Hindi. नमस्ते, कैसे हैं आप?")
        win.rec_mode_var = tk.StringVar(value="push_to_talk")
        win.selected_mode_key = tk.StringVar(value="smart")
        win.mode_prompt_txt = tk.Text(self.root)
        from config import DEFAULT_DICTATION_MODES
        win.mode_prompt_txt.insert("1.0", DEFAULT_DICTATION_MODES["smart"]["prompt"])
        win.hotkey_var = tk.StringVar(value="ctrl+space")
        win.sound_var = tk.BooleanVar(value=True)
        win.space_var = tk.BooleanVar(value=True)
        win._get_selected_device = lambda: (None, "Default Microphone")

        with patch.object(config, "save") as mock_save:
            win._save_all()
            mock_save.assert_called()

        self.assertEqual(config.get("ai_backend"), "custom")
        self.assertEqual(config.get("custom_base_url"), "https://custom-host.com/v1")
        self.assertEqual(config.get("custom_api_key"), "sk-updated-key")
        self.assertEqual(config.get("custom_model"), "mistral-small")

    @patch("core.ai_refiner.requests.get")
    def test_settings_window_test_connection_stages_in_memory_values(self, mock_get):
        """Verify _test_backend_connection stages newly typed values before running status check."""
        import time

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        config.set("custom_base_url", "https://old-url.com/v1", auto_save=False)
        config.set("custom_api_key", "old-key", auto_save=False)
        config.set("custom_model", "old-model", auto_save=False)

        win = SettingsWindow(self.root)
        win.win = tk.Toplevel(self.root)
        notebook = ttk.Notebook(win.win)
        win._build_ai_tab(notebook)

        # User types new values into fields without clicking Save & Apply
        win.ai_backend_var.set("custom")
        win.custom_base_url_var.set("https://new-staged-url.com/v1")
        win.custom_key_var.set("new-staged-key")
        win.custom_model_var.set("new-staged-model")

        worker_threads = []
        orig_thread_init = threading.Thread.__init__

        def _track_thread(thr, *args, **kwargs):
            orig_thread_init(thr, *args, **kwargs)
            worker_threads.append(thr)

        with patch.object(threading.Thread, "__init__", _track_thread):
            win._test_backend_connection()

        # Config should immediately reflect staged values without auto-saving to disk
        self.assertEqual(config.get("custom_base_url"), "https://new-staged-url.com/v1")
        self.assertEqual(config.get("custom_api_key"), "new-staged-key")
        self.assertEqual(config.get("custom_model"), "new-staged-model")

        # Run short mainloop to allow background worker and Tk cross-thread after() to execute
        def _poll_label():
            txt = win.backend_status_lbl.cget("text")
            if "Custom API Online" in txt or "not reachable" in txt or "Auth Failed" in txt:
                self.root.quit()
            else:
                self.root.after(20, _poll_label)

        self.root.after(20, _poll_label)
        self.root.mainloop()

        for t in worker_threads:
            t.join(timeout=2.0)

        mock_get.assert_called_with(
            "https://new-staged-url.com/v1/models",
            headers={"Authorization": "Bearer new-staged-key"},
            timeout=5,
        )


if __name__ == "__main__":
    unittest.main()
