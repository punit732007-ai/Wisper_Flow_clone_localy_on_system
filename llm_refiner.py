"""
LocalWhisper — LLM Refiner
Post-processes Whisper output with a local Ollama LLM for better accuracy.
"""

import re
import requests
from config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT,
    REFINEMENT_SYSTEM_PROMPT,
)


class LLMRefiner:
    """Uses a local Ollama model to clean up transcription errors."""

    def __init__(self):
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        return self._available is True

    def check_availability(self) -> bool:
        """Ping Ollama to see if it's running and the model is loaded."""
        try:
            resp = requests.get(
                f"{OLLAMA_BASE_URL}/api/tags", timeout=3
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                names = [m.get("name", "") for m in models]
                # Check if our model (or a prefix of it) is available
                found = any(
                    OLLAMA_MODEL in n or n.startswith(OLLAMA_MODEL.split(":")[0])
                    for n in names
                )
                self._available = found
                if found:
                    print(f"[LLMRefiner] Ollama ready -- model '{OLLAMA_MODEL}' found OK")
                else:
                    print(f"[LLMRefiner] Model '{OLLAMA_MODEL}' not found. "
                          f"Available: {names}")
            else:
                self._available = False
        except Exception as exc:
            print(f"[LLMRefiner] Ollama not reachable: {exc}")
            self._available = False
        return self._available

    def refine(self, raw_text: str, detected_language: str) -> str:
        """Send the raw transcription to the LLM for correction.

        Falls back to *raw_text* if the LLM is unavailable or too slow.
        """
        if not raw_text.strip():
            return raw_text

        if not self._available:
            return raw_text

        lang_label = {
            "hi": "Hindi",
            "en": "English",
        }.get(detected_language, detected_language)

        user_prompt = (
            f"Detected language: {lang_label}\n"
            f"Raw transcription:\n{raw_text}\n\n/no_think"
        )

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": REFINEMENT_SYSTEM_PROMPT},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 512,
                    },
                },
                timeout=OLLAMA_TIMEOUT,
            )

            if resp.status_code == 200:
                result = resp.json()
                content = result.get("message", {}).get("content", "").strip()
                # Strip any residual <think>…</think> tags from qwen3
                content = re.sub(
                    r"<think>.*?</think>", "", content, flags=re.DOTALL
                ).strip()
                if content:
                    print(f"[LLMRefiner] Refined: {content!r}")
                    return content

            print(f"[LLMRefiner] Non-200 or empty -- using raw text")
            return raw_text

        except requests.exceptions.Timeout:
            print("[LLMRefiner] Timeout -- using raw text")
            return raw_text
        except Exception as exc:
            print(f"[LLMRefiner] Error: {exc} -- using raw text")
            return raw_text
