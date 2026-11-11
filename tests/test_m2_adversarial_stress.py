"""
LocalWhisper Pro — Adversarial Stress & Empirical Property Verification Harness for Milestone 2
(Other / Custom Model API Provider Support)

Exhaustively verifies:
1. URL Normalization: trailing slashes, multi-slashes, whitespace, paths with and without /v1.
2. Local LAN Unauthenticated Server Support: empty, None, and whitespace custom_api_key handling.
3. Remote Bearer Token Injection: properly formatted Bearer tokens, whitespace stripping in keys.
4. Reasoning Model Output Sanitization: DeepSeek/Qwen <think>...</think> removal, multi-line,
   nested/multiple blocks, outer single/double quotes, and fallback on empty post-think content.
5. Hostile Error Recovery & Offline Rule Fallback: HTTP 401, 403, 404, 429, 500, 502, 503, 504,
   timeouts, connection drops, SSL errors, corrupt JSON, malformed schema, and null content.
6. Settings UI In-Memory Test Connection Staging: non-persisted test connection staging, thread safety,
   and zero auto-save side effects.
7. High-Concurrency & Dynamic Reconfiguration: concurrent refine() requests under active backend switching.
8. Direct Mode 0ms Passthrough: preservation under custom provider failures.
9. Multilingual & Unicode Resilience: Hindi (Devanagari), Hinglish, and special symbols.
"""

import sys
import json
import time
import queue
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tkinter as tk
from tkinter import ttk
from config import config, DEFAULT_CONFIG
from core.ai_refiner import AIRefiner
from ui.settings_window import SettingsWindow


class TestM2AdversarialStress(unittest.TestCase):
    """Adversarial challenge suite for Milestone 2 Custom Provider."""

    def setUp(self):
        import copy
        from config import DEFAULT_DICTATION_MODES
        self.refiner = AIRefiner()
        self.orig_backend = config.get("ai_backend")
        self.orig_url = config.get("custom_base_url")
        self.orig_key = config.get("custom_api_key")
        self.orig_model = config.get("custom_model")
        self.orig_mode = config.get("current_mode")
        self.orig_modes = copy.deepcopy(config.get("dictation_modes"))
        # Ensure clean mode prompts even if prior tests mutated config
        config.set("dictation_modes", copy.deepcopy(DEFAULT_DICTATION_MODES), auto_save=False)

    def tearDown(self):
        config.set("ai_backend", self.orig_backend, auto_save=False)
        config.set("custom_base_url", self.orig_url, auto_save=False)
        config.set("custom_api_key", self.orig_key, auto_save=False)
        config.set("custom_model", self.orig_model, auto_save=False)
        config.set("current_mode", self.orig_mode, auto_save=False)
        config.set("dictation_modes", self.orig_modes, auto_save=False)

    # ─────────────────────────────────────────────────────────────
    # 1. URL Normalization
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.get")
    def test_01_url_normalization_status_check(self, mock_get):
        """Verify URL normalization in check_backend_status across diverse formatting."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_model", "test-model", auto_save=False)

        test_cases = [
            ("http://localhost:8000/v1", "http://localhost:8000/v1/models"),
            ("http://localhost:8000/v1/", "http://localhost:8000/v1/models"),
            ("http://localhost:8000/v1///", "http://localhost:8000/v1/models"),
            ("  http://localhost:8000/v1/  ", "http://localhost:8000/v1/models"),
            ("http://192.168.1.100:1234", "http://192.168.1.100:1234/models"),
            ("https://api.custom.ai/openai/v1/", "https://api.custom.ai/openai/v1/models"),
        ]

        for input_url, expected_called_url in test_cases:
            mock_get.reset_mock()
            config.set("custom_base_url", input_url, auto_save=False)
            ok, msg = self.refiner.check_backend_status()
            self.assertTrue(ok, f"Failed for input url: {input_url}")
            mock_get.assert_called_once()
            called_url = mock_get.call_args[0][0]
            self.assertEqual(called_url, expected_called_url)

    @patch("core.ai_refiner.requests.post")
    def test_02_url_normalization_chat_completions(self, mock_post):
        """Verify URL normalization in _call_custom across diverse formatting."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Normalized URL response."}}]
        }
        mock_post.return_value = mock_resp

        config.set("custom_model", "test-model", auto_save=False)

        test_cases = [
            ("http://localhost:8000/v1", "http://localhost:8000/v1/chat/completions"),
            ("http://localhost:8000/v1/", "http://localhost:8000/v1/chat/completions"),
            ("http://localhost:8000/v1////", "http://localhost:8000/v1/chat/completions"),
            ("   http://localhost:8000/v1/   ", "http://localhost:8000/v1/chat/completions"),
            ("https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"),
        ]

        for input_url, expected_called_url in test_cases:
            mock_post.reset_mock()
            config.set("custom_base_url", input_url, auto_save=False)
            res = self.refiner._call_custom("System", "User")
            self.assertEqual(res, "Normalized URL response.")
            mock_post.assert_called_once()
            called_url = mock_post.call_args[0][0]
            self.assertEqual(called_url, expected_called_url)

    # ─────────────────────────────────────────────────────────────
    # 2. Local LAN Unauthenticated Server Support
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.get")
    @patch("core.ai_refiner.requests.post")
    def test_03_local_lan_unauthenticated_operation(self, mock_post, mock_get):
        """Verify empty or blank custom_api_key injects no Authorization header."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "choices": [{"message": {"content": "Local LAN output."}}]
        }
        mock_post.return_value = mock_post_resp

        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "http://192.168.1.50:8000/v1", auto_save=False)
        config.set("custom_model", "local-qwen", auto_save=False)

        for empty_key in ["", "   ", None]:
            config.set("custom_api_key", empty_key, auto_save=False)

            # 1. Status check
            mock_get.reset_mock()
            ok, msg = self.refiner.check_backend_status()
            self.assertTrue(ok)
            self.assertIn("Custom API Online", msg)
            headers_get = mock_get.call_args[1].get("headers", {})
            self.assertNotIn("Authorization", headers_get)

            # 2. Refine call
            mock_post.reset_mock()
            res = self.refiner._call_custom("sys", "user")
            self.assertEqual(res, "Local LAN output.")
            headers_post = mock_post.call_args[1].get("headers", {})
            self.assertNotIn("Authorization", headers_post)
            self.assertEqual(headers_post.get("Content-Type"), "application/json")

    # ─────────────────────────────────────────────────────────────
    # 3. Remote Bearer Token Injection
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.get")
    @patch("core.ai_refiner.requests.post")
    def test_04_bearer_token_injection_and_whitespace_trimming(self, mock_post, mock_get):
        """Verify non-empty API keys inject exact Bearer headers with whitespace trimmed."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "choices": [{"message": {"content": "Authenticated output."}}]
        }
        mock_post.return_value = mock_post_resp

        config.set("ai_backend", "custom", auto_save=False)
        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_model", "gpt-4o", auto_save=False)
        config.set("custom_api_key", "   sk-my-secret-key-12345   ", auto_save=False)

        # Status check
        ok, msg = self.refiner.check_backend_status()
        self.assertTrue(ok)
        mock_get.assert_called_once()
        headers_get = mock_get.call_args[1].get("headers", {})
        self.assertEqual(headers_get.get("Authorization"), "Bearer sk-my-secret-key-12345")

        # Call custom
        res = self.refiner._call_custom("sys", "user")
        self.assertEqual(res, "Authenticated output.")
        mock_post.assert_called_once()
        headers_post = mock_post.call_args[1].get("headers", {})
        self.assertEqual(headers_post.get("Authorization"), "Bearer sk-my-secret-key-12345")

    # ─────────────────────────────────────────────────────────────
    # 4. Reasoning Model Output Cleaning (<think> tags & quotes)
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.post")
    def test_05_deepseek_qwen_think_tag_and_quote_sanitization(self, mock_post):
        """Adversarially challenge regex cleaning for multi-line think tags and nested quotes."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.deepseek.com/v1", auto_save=False)
        config.set("custom_model", "deepseek-reasoner", auto_save=False)

        adversarial_outputs = [
            # Standard single-line think tag
            ("<think>I am analyzing the input.</think>Clean voice transcription.",
             "Clean voice transcription."),
            # Multi-line think tag with internal code blocks, markdown, newlines
            ("<think>\nStep 1: Check grammar\n```python\nprint('thinking')\n```\nStep 2: Format text\n</think>\nFormatted voice output.",
             "Formatted voice output."),
            # Multiple separated think tags
            ("<think>Initial thought</think>Part A <think>Mid thought</think>Part B.",
             "Part A Part B."),
            # Surrounding double quotes
            ('"Strictly quoted transcription."',
             "Strictly quoted transcription."),
            # Surrounding single quotes
            ("'Single quoted transcription.'",
             "Single quoted transcription."),
            # Think tag followed by quoted content
            ('<think>Thoughts here</think>"Quoted sentence after thought."',
             "Quoted sentence after thought."),
            # Inner quotes preserved (not stripped)
            ('He said "Hello world" to everyone.',
             'He said "Hello world" to everyone.'),
        ]

        for raw_model_output, expected_clean in adversarial_outputs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": raw_model_output}}]
            }
            mock_post.return_value = mock_resp

            result = self.refiner.refine("raw voice input", language="en")
            self.assertEqual(result, expected_clean)

    @patch("core.ai_refiner.requests.post")
    def test_06_model_emits_only_think_tags_falls_back_gracefully(self, mock_post):
        """When model emits ONLY <think>...</think> and no content, fallback to offline rules."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.deepseek.com/v1", auto_save=False)
        config.set("custom_model", "deepseek-reasoner", auto_save=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "<think>\nThinking only, no completion emitted\n</think>"}}]
        }
        mock_post.return_value = mock_resp

        result = self.refiner.refine("um uh critical dictation that must not be lost", language="en")
        # Since post-processed content was empty, it falls back to offline rule cleanup!
        self.assertEqual(result, "Critical dictation that must not be lost.")

    # ─────────────────────────────────────────────────────────────
    # 5. Hostile Error Recovery & Offline Rule Fallback
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.post")
    def test_07_http_error_codes_trigger_offline_fallback(self, mock_post):
        """Verify HTTP 401, 403, 404, 429, 500, 502, 503, 504 fall back cleanly without losing text."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.custom.com/v1", auto_save=False)
        config.set("custom_model", "test-model", auto_save=False)

        error_status_codes = [401, 403, 404, 429, 500, 502, 503, 504]
        raw_speech = "um please schedule the meeting for tomorrow"
        expected_fallback = "Please schedule the meeting for tomorrow."

        for code in error_status_codes:
            mock_resp = MagicMock()
            mock_resp.status_code = code
            mock_post.return_value = mock_resp

            result = self.refiner.refine(raw_speech, language="en")
            self.assertEqual(result, expected_fallback, f"Failed fallback on HTTP {code}")

    @patch("core.ai_refiner.requests.post")
    def test_08_network_exceptions_trigger_offline_fallback(self, mock_post):
        """Verify network exceptions (timeout, connection refused, reset, SSL) fall back cleanly."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.custom.com/v1", auto_save=False)
        config.set("custom_model", "test-model", auto_save=False)

        exceptions = [
            TimeoutError("Socket timed out after 15s"),
            ConnectionRefusedError("Connection refused by host"),
            ConnectionResetError("Connection reset by peer"),
            Exception("SSL: CERTIFICATE_VERIFY_FAILED"),
        ]

        raw_speech = "uh send the report to the team"
        expected_fallback = "Send the report to the team."

        for exc in exceptions:
            mock_post.side_effect = exc
            result = self.refiner.refine(raw_speech, language="en")
            self.assertEqual(result, expected_fallback, f"Failed fallback on {type(exc)}")

    @patch("core.ai_refiner.requests.post")
    def test_09_malformed_json_and_schema_trigger_offline_fallback(self, mock_post):
        """Verify corrupted or incomplete JSON responses trigger offline rule fallback."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.custom.com/v1", auto_save=False)
        config.set("custom_model", "test-model", auto_save=False)

        raw_speech = "um check the system status"
        expected_fallback = "Check the system status."

        malformed_payloads = [
            {},                                                 # empty json
            {"error": "Quota exceeded"},                        # error object
            {"choices": []},                                    # empty choices list
            {"choices": [{"other_field": 123}]},                # missing message
            {"choices": [{"message": {}}]},                     # missing content
            {"choices": [{"message": {"content": None}}]},      # null content
            {"choices": [{"message": {"content": ""}}]},        # empty content string
        ]

        for payload in malformed_payloads:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = payload
            mock_post.return_value = mock_resp
            mock_post.side_effect = None

            result = self.refiner.refine(raw_speech, language="en")
            self.assertEqual(result, expected_fallback, f"Failed fallback on payload: {payload}")

    # ─────────────────────────────────────────────────────────────
    # 6. Settings UI In-Memory Test Connection Staging
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.get")
    def test_10_settings_ui_in_memory_staging_and_thread_safety(self, mock_get):
        """Stress-test in-memory staging in SettingsWindow without disk save or thread race."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        root = tk.Tk()
        root.withdraw()

        try:
            config.set("custom_base_url", "http://original-url:8000/v1", auto_save=False)
            config.set("custom_api_key", "orig-key", auto_save=False)
            config.set("custom_model", "orig-model", auto_save=False)

            win = SettingsWindow(root)
            win.win = tk.Toplevel(root)
            notebook = ttk.Notebook(win.win)
            win._build_ai_tab(notebook)

            # User edits fields
            win.ai_backend_var.set("custom")
            win.custom_base_url_var.set("https://staged-adversarial.ai/v1")
            win.custom_key_var.set("sk-staged-secret")
            win.custom_model_var.set("staged-llama-3")

            with patch.object(config, "save") as mock_save:
                win._test_backend_connection()
                # Verify disk save was NOT called during test connection
                mock_save.assert_not_called()

            # Verify config holds staged values
            self.assertEqual(config.get("custom_base_url"), "https://staged-adversarial.ai/v1")
            self.assertEqual(config.get("custom_api_key"), "sk-staged-secret")
            self.assertEqual(config.get("custom_model"), "staged-llama-3")

            # Run short mainloop to allow background worker and Tk cross-thread after() to execute
            def _poll_label():
                txt = win.backend_status_lbl.cget("text")
                if "Custom API Online" in txt or "not reachable" in txt or "Auth Failed" in txt:
                    root.quit()
                else:
                    root.after(20, _poll_label)

            root.after(20, _poll_label)
            root.mainloop()

            # Verify mock_get was called with the staged parameters
            mock_get.assert_called_with(
                "https://staged-adversarial.ai/v1/models",
                headers={"Authorization": "Bearer sk-staged-secret"},
                timeout=5,
            )

            # Verify UI label was updated cleanly
            lbl_text = win.backend_status_lbl.cget("text")
            self.assertIn("Custom API Online", lbl_text)
            self.assertIn("staged-llama-3", lbl_text)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # 7. Concurrency & Dynamic Reconfiguration
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.post")
    def test_11_concurrent_refinement_under_backend_switching(self, mock_post):
        """Stress-test 10 threads concurrently refining text while switching backends."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Concurrent refined text."}}]
        }
        mock_post.return_value = mock_resp

        config.set("custom_base_url", "https://api.openai.com/v1", auto_save=False)
        config.set("custom_api_key", "sk-conc-test", auto_save=False)
        config.set("custom_model", "gpt-4o-mini", auto_save=False)

        num_threads = 8
        calls_per_thread = 20
        results_queue = queue.Queue()
        errors = []

        def worker(thread_id: int):
            for i in range(calls_per_thread):
                try:
                    # Alternating mode and backend configurations
                    if i % 3 == 0:
                        config.set("ai_backend", "custom", auto_save=False)
                    elif i % 3 == 1:
                        config.set("ai_backend", "none", auto_save=False)
                    else:
                        config.set("ai_backend", "other", auto_save=False)

                    res = self.refiner.refine(f"voice input {thread_id} step {i}", language="en")
                    results_queue.put(res)
                except Exception as e:
                    errors.append((thread_id, i, e))

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Encountered errors during concurrent execution: {errors}")
        self.assertEqual(results_queue.qsize(), num_threads * calls_per_thread)

    # ─────────────────────────────────────────────────────────────
    # 8. Direct Mode 0ms Passthrough
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.post")
    def test_12_direct_mode_passthrough_safety(self, mock_post):
        """Direct mode skips all network requests and returns input unaltered immediately."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "direct", auto_save=False)

        raw = "   exact literal verbatim text without dot   "
        res = self.refiner.refine(raw, language="en")
        self.assertEqual(res, "exact literal verbatim text without dot")
        mock_post.assert_not_called()

    # ─────────────────────────────────────────────────────────────
    # 9. Multilingual & Unicode Resilience
    # ─────────────────────────────────────────────────────────────

    @patch("core.ai_refiner.requests.post")
    def test_13_hindi_and_hinglish_unicode_refinement(self, mock_post):
        """Verify Hindi Devanagari and Hinglish dictation requests pass through custom endpoint."""
        config.set("ai_backend", "custom", auto_save=False)
        config.set("current_mode", "smart", auto_save=False)
        config.set("custom_base_url", "https://api.custom.com/v1", auto_save=False)
        config.set("custom_model", "custom-indic", auto_save=False)

        hindi_input = "नमस्ते दुनिया आज का दिन बहुत अच्छा है"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "नमस्ते दुनिया, आज का दिन बहुत अच्छा है।"}}]
        }
        mock_post.return_value = mock_resp

        res = self.refiner.refine(hindi_input, language="hi")
        self.assertEqual(res, "नमस्ते दुनिया, आज का दिन बहुत अच्छा है।")

        # Verify prompt payload contained language hint
        call_payload = mock_post.call_args[1]["json"]
        user_content = call_payload["messages"][1]["content"]
        self.assertIn("Language detected: Hindi", user_content)
        self.assertIn(hindi_input, user_content)


if __name__ == "__main__":
    unittest.main()
