"""
LocalWhisper Pro — AI Refiner Engine
Multi-backend post-processor supporting Ollama, Groq (500+ tok/s), OpenAI/OpenRouter,
Gemini API, and offline heuristic rules across all customizable dictation modes.
"""

import re
import time
from typing import Tuple, Optional, Dict, Any
import requests
from config import config


class AIRefiner:
    """Intelligent text post-processor with multi-backend & multi-mode support."""

    def __init__(self):
        self._last_backend_status: Dict[str, Any] = {"ok": False, "msg": "Unchecked"}

    def check_backend_status(self) -> Tuple[bool, str]:
        """Check availability of the currently configured AI backend."""
        backend = config.get("ai_backend", "ollama")

        if backend == "none":
            self._last_backend_status = {"ok": True, "msg": "Direct Fast Mode (AI Disabled)"}
            return True, "Direct Fast Mode (AI Disabled)"

        if backend == "ollama":
            url = config.get("ollama_base_url", "http://localhost:11434")
            target_model = config.get("ollama_model", "qwen3:8b")
            try:
                resp = requests.get(f"{url}/api/tags", timeout=3)
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    found = any(
                        target_model in m or m.startswith(target_model.split(":")[0])
                        for m in models
                    )
                    if found:
                        msg = f"Ollama Online (Model '{target_model}' ready)"
                        self._last_backend_status = {"ok": True, "msg": msg}
                        return True, msg
                    else:
                        msg = f"Ollama Online (Available: {', '.join(models[:3]) or 'None'})"
                        self._last_backend_status = {"ok": False, "msg": msg}
                        return False, msg
                else:
                    msg = f"Ollama HTTP {resp.status_code}"
                    self._last_backend_status = {"ok": False, "msg": msg}
                    return False, msg
            except Exception as e:
                msg = f"Ollama not reachable: {e}"
                self._last_backend_status = {"ok": False, "msg": msg}
                return False, msg

        elif backend == "groq":
            api_key = config.get("groq_api_key", "").strip()
            if not api_key:
                msg = "Groq API key not set"
                self._last_backend_status = {"ok": False, "msg": msg}
                return False, msg
            msg = "Groq Cloud Configured"
            self._last_backend_status = {"ok": True, "msg": msg}
            return True, msg

        elif backend in ("openai", "gemini"):
            key = config.get(f"{backend}_api_key", "").strip()
            if not key:
                msg = f"{backend.title()} API key not set"
                self._last_backend_status = {"ok": False, "msg": msg}
                return False, msg
            msg = f"{backend.title()} Configured"
            self._last_backend_status = {"ok": True, "msg": msg}
            return True, msg

        return False, "Unknown backend"

    def refine(self, raw_text: str, language: str = "en") -> str:
        """
        Refine the transcription based on active dictation mode and selected AI backend.
        Falls back to rule-based cleanup or raw text if backend is offline.
        """
        if not raw_text or not raw_text.strip():
            return raw_text

        mode_info = config.current_mode_info
        mode_key = config.get("current_mode", "smart")
        system_prompt = mode_info.get("prompt", "").strip()

        # Direct Mode has empty prompt -> Instant 0ms passthrough
        if mode_key == "direct" or not system_prompt:
            return raw_text.strip()

        backend = config.get("ai_backend", "ollama")
        if backend == "none":
            return raw_text.strip()

        lang_label = "Hindi" if language == "hi" else ("English" if language == "en" else language)
        user_prompt = (
            f"Language detected: {lang_label}\n"
            f"Raw voice transcription:\n{raw_text}\n\n/no_think"
        )

        try:
            if backend == "ollama":
                refined = self._call_ollama(system_prompt, user_prompt)
            elif backend == "groq":
                refined = self._call_groq(system_prompt, user_prompt)
            elif backend == "openai":
                refined = self._call_openai(system_prompt, user_prompt)
            elif backend == "gemini":
                refined = self._call_gemini(system_prompt, user_prompt)
            else:
                refined = None

            if refined and refined.strip():
                # Clean up reasoning tags if emitted by DeepSeek / reasoning models from any backend
                clean = re.sub(r"<think>.*?</think>", "", refined, flags=re.DOTALL).strip()
                # Remove enclosing matching quotes if model added them
                if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
                    clean = clean[1:-1].strip()
                return clean

        except Exception as exc:
            print(f"[AIRefiner] Backend ({backend}) error: {exc} — using offline rule cleanup")

        # Fallback: Offline local rule cleanup
        return self._offline_rule_cleanup(raw_text)

    # ── Backend Handlers ──────────────────────────────────────────

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        url = config.get("ollama_base_url", "http://localhost:11434")
        model = config.get("ollama_model", "qwen3:8b")
        timeout = config.get("ollama_timeout", 20)

        resp = requests.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512,
                },
            },
            timeout=timeout,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "").strip()
            # Strip reasoning tags from reasoning models
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        return None

    def _call_groq(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        api_key = config.get("groq_api_key", "").strip()
        model = config.get("groq_model", "llama-3.3-70b-versatile")
        if not api_key:
            return None

        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 512,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return None

    def _call_openai(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        api_key = config.get("openai_api_key", "").strip()
        base_url = config.get("openai_base_url", "https://api.openai.com/v1")
        model = config.get("openai_model", "gpt-4o-mini")
        if not api_key:
            return None

        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 512,
            },
            timeout=12,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return None

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        api_key = config.get("gemini_api_key", "").strip()
        model = config.get("gemini_model", "gemini-1.5-flash")
        if not api_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        resp = requests.post(
            url,
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": f"SYSTEM INSTRUCTION:\n{system_prompt}\n\nUSER INPUT:\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
            },
            timeout=12,
        )
        if resp.status_code == 200:
            candidates = resp.json().get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return None

    # ── Offline Rule-Based Fast Cleaner ───────────────────────────

    @staticmethod
    def _offline_rule_cleanup(text: str) -> str:
        """Fast regex and grammar normalization for offline usage."""
        t = text.strip()
        if not t:
            return t

        # Remove duplicate filler words (e.g. "um um", "uh")
        t = re.sub(r"\b(um|uh|er|ah)\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip()

        # Capitalize first letter
        if len(t) > 0:
            t = t[0].upper() + t[1:]

        # Add period at end if no terminal punctuation
        if t and not t[-1] in ".?!":
            t += "."

        return t


ai_refiner = AIRefiner()
