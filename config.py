"""
LocalWhisper Pro v3.0 — Configuration & State Store
Handles settings persistence in ~/.localwhisper/settings.json,
CUDA path preloading, hardware auto-detection, and multi-mode definitions.
"""

import os
import sys
import json
import time
import ctypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Directories ──────────────────────────────────────────────────
APP_DIR = Path.home() / ".localwhisper"
APP_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = APP_DIR / "settings.json"
HISTORY_FILE = APP_DIR / "history.json"
WARMUP_CACHE_FILE = APP_DIR / "warmup_ok"
WARMUP_CACHE_MAX_AGE = 24 * 3600  # 24 hours

# ─── Preload Windows CUDA DLL Paths ──────────────────────────────
def preload_cuda_dlls():
    """Add NVIDIA / CUDA / cuDNN paths to Windows DLL search directory."""
    cuda_dirs: List[str] = []

    # Check active virtual environment / site-packages nvidia wheels
    try:
        import site
        for site_pkg in site.getsitepackages():
            nvidia_base = os.path.join(site_pkg, "nvidia")
            if os.path.isdir(nvidia_base):
                for sub in os.listdir(nvidia_base):
                    sub_path = os.path.join(nvidia_base, sub)
                    for sub_folder in ["bin", "lib"]:
                        cand = os.path.join(sub_path, sub_folder)
                        if os.path.isdir(cand):
                            cuda_dirs.append(cand)
            # Also check torch/lib if installed
            torch_lib = os.path.join(site_pkg, "torch", "lib")
            if os.path.isdir(torch_lib):
                cuda_dirs.append(torch_lib)
    except Exception:
        pass

    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(os.path.join(cuda_path, "bin")):
        cuda_dirs.append(os.path.join(cuda_path, "bin"))

    for ver in ["v13.3", "v12.8", "v12.6", "v12.4", "v12.2", "v12.1", "v12.0", "v11.8"]:
        p = rf"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\{ver}\bin"
        if os.path.isdir(p):
            cuda_dirs.append(p)

    cudnn_path = os.environ.get("CUDNN", "")
    if cudnn_path and os.path.isdir(os.path.join(cudnn_path, "bin")):
        cuda_dirs.append(os.path.join(cudnn_path, "bin"))

    if hasattr(os, "add_dll_directory"):
        for d in cuda_dirs:
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass

    path_env = os.environ.get("PATH", "")
    for d in reversed(cuda_dirs):
        if os.path.isdir(d) and d not in path_env:
            os.environ["PATH"] = d + ";" + os.environ.get("PATH", "")

preload_cuda_dlls()

# ─── Device Auto-Detection ───────────────────────────────────────
def detect_hardware() -> Tuple[str, str]:
    """Detect if NVIDIA CUDA or CPU should be used with faster-whisper."""
    try:
        import ctranslate2
        cuda_types = ctranslate2.get_supported_compute_types("cuda")
        if "float16" in cuda_types:
            return "cuda", "float16"
        if "int8_float16" in cuda_types:
            return "cuda", "int8_float16"
    except Exception:
        pass
    return "cpu", "int8"

_DEFAULT_DEVICE, _DEFAULT_COMPUTE_TYPE = detect_hardware()

# ─── Default Mode Definitions ─────────────────────────────────────
DEFAULT_DICTATION_MODES: Dict[str, Dict[str, str]] = {
    "smart": {
        "name": "Smart Dictation",
        "badge": "✍️ Smart",
        "description": "Natural voice cleanup, fixes filler words & punctuation while keeping your tone.",
        "prompt": (
            "You are an expert speech-to-text post-processor and conversational editor. Your task is to clean and polish voice transcription into crisp, natural text.\n\n"
            "Rules:\n"
            "1. Output ONLY the result text. No explanations, no <think> tags, no markdown wrappers, no quotation marks, and no conversational preamble.\n"
            "2. Language Preservation: Strictly preserve the spoken language. If spoken in English, keep it in English. If spoken in Hindi or Hinglish (e.g., 'theek hai', 'haan', 'acha', 'namaste', Devanagari or Romanized), keep the exact words and phrasing as spoken. Do NOT translate Hindi into English.\n"
            "3. Filler & Disfluency Removal: Strip speech disfluencies, stuttering, and filler words (e.g., 'um', 'uh', 'er', 'ah', 'like', 'you know', 'matlab', 'yaani', 'bhai', 'na', 'arrey', repeated or stumbled words).\n"
            "4. Punctuation & Capitalization: Insert natural punctuation (periods, commas, question marks) and correct capitalization for proper nouns, acronyms, and sentence beginnings.\n"
            "5. Contextual Correction: Correct obvious speech recognition mishearings and phonetic typos using the surrounding sentence context.\n"
            "6. Tone Preservation: Preserve the speaker's original meaning, intent, emotional nuance, and casual or formal tone. Do not make casual speech overly formal.\n"
            "7. Clean Final Output: Return ONLY the clean, finished text ready for direct cursor insertion."
        ),
    },
    "direct": {
        "name": "Direct Raw",
        "badge": "⚡ Direct",
        "description": "Zero latency. Instantly pastes raw Whisper transcription without AI post-processing.",
        "prompt": "",
    },
    "pro": {
        "name": "Professional Email",
        "badge": "💼 Pro Email",
        "description": "Rewrites conversational speech into clear, executive workplace communication.",
        "prompt": (
            "You are a senior executive communications editor. Transform conversational voice notes into crisp, professional workplace communication or business emails.\n\n"
            "Rules:\n"
            "1. Output ONLY the result text. No explanations, no <think> tags, no markdown wrappers, no quotation marks, and no introductory or concluding meta-commentary.\n"
            "2. Language & Formulation: If the speech is in Hindi or Hinglish, formulate the output into fluent, polished, professional business English. If spoken in English, elevate the clarity, vocabulary, and grammatical precision.\n"
            "3. Structure & Formatting: Organize disjointed thoughts into concise, logically structured paragraphs or clean bullet points where appropriate for executive clarity.\n"
            "4. Professional Tone: Use confident, polite, active-voice business English suitable for executive email, client communication, Slack, or Teams.\n"
            "5. Filler & Ramble Removal: Eliminate all filler words, colloquialisms, conversational tangents, hedging, stutters, and rambling.\n"
            "6. Intent Fidelity: Retain all critical action items, names, deadlines, numbers, and core decisions from the original speech."
        ),
    },
    "code": {
        "name": "Code & Tech",
        "badge": "💻 Code",
        "description": "Formats technical speech into code syntax, camelCase/snake_case identifiers, and commands.",
        "prompt": (
            "You are a software engineering transcription assistant. Format technical speech into precise code syntax, variable identifiers, terminal commands, SQL queries, or technical documentation.\n\n"
            "Rules:\n"
            "1. Output ONLY the result text. No explanations, no <think> tags, no markdown wrappers (unless formatting multi-line code blocks), no quotation marks.\n"
            "2. Identifier Formatting: Convert spoken naming conventions into standard casing:\n"
            "   - 'camel case user id' -> 'userId'\n"
            "   - 'snake case total amount' -> 'total_amount'\n"
            "   - 'pascal case auth service' -> 'AuthService'\n"
            "   - 'kebab case app header' -> 'app-header'\n"
            "   - 'screaming snake case max retries' -> 'MAX_RETRIES'\n"
            "3. Commands & Code Snippets: If terminal commands, SQL queries, or code statements are dictated, format with proper syntax, flags (e.g., '--verbose'), operators ('&&', '|', '=='), and indentation.\n"
            "4. Technical Prose & Language: If the speaker is explaining code or architecture (in English or Hinglish), retain technical vocabulary (APIs, endpoints, variables, libraries) and wrap inline terms in backticks (e.g., `useState`, `config.py`). Preserve spoken Hindi/Hinglish words as spoken without translating into English.\n"
            "5. Symbol Resolution: Accurately translate spoken symbols into their code equivalents (e.g., 'dot' -> '.', 'arrow' -> '->' or '=>', 'open paren' -> '(', 'curly braces' -> '{}', 'equals equals' -> '==')."
        ),
    },
    "translate": {
        "name": "Translate to English",
        "badge": "🌐 Translate",
        "description": "Translates spoken Hindi or Hinglish into fluent English.",
        "prompt": (
            "You are a dedicated Hindi/Hinglish to English translator. Translate spoken Hindi (Devanagari or Romanized Hinglish) directly into fluent, natural, and idiomatic English.\n\n"
            "Rules:\n"
            "1. Output ONLY the result text. No explanations, no <think> tags, no markdown wrappers, no quotation marks, no translator notes or pronunciation guides.\n"
            "2. Accurate Translation: Faithfully translate Hindi (Devanagari or Hinglish, e.g. 'theek hai', 'haan', 'acha', 'namaste') into fluent, natural English rather than literal word-for-word translation.\n"
            "3. English Input Handling: If the spoken input is already in English, refine and polish its grammar, flow, and punctuation while leaving the core vocabulary intact.\n"
            "4. Grammar & Punctuation: Ensure the English output has flawless grammar, correct tenses, capitalization, and natural punctuation.\n"
            "5. Tone & Context: Preserve the speaker's intended emotional tone (formal, informal, urgent, inquiring) and retain technical or proper names in standard English."
        ),
    },
    "bullet": {
        "name": "Bullet Summary",
        "badge": "📝 Bullets",
        "description": "Converts long speech into structured bullet points with key takeaways.",
        "prompt": (
            "You are an executive note-taker and summarization assistant. Synthesize spoken thoughts and voice notes into clean, structured bullet points.\n\n"
            "Rules:\n"
            "1. Output ONLY the result text as a clean markdown bulleted list (using '- '). No explanations, no <think> tags, no markdown wrappers, no quotation marks, no intro/outro chatter or summary titles.\n"
            "2. Structure & Clarity: Group related points logically and ensure each bullet is concise, punchy, and readable in seconds.\n"
            "3. Language Handling: If spoken in Hindi or Hinglish, synthesize and extract the key takeaways in clear, concise English (retaining critical proper nouns or specific Hindi terms if essential for context). If spoken in English, maintain English.\n"
            "4. Action Items & Key Data: Explicitly highlight key action items, decisions, metrics, dates, and assigned responsibilities.\n"
            "5. Eliminate Fluff: Strip all conversational ramblings, repetitions, filler words ('um', 'uh', 'matlab', 'you know'), and extraneous pleasantries."
        ),
    },
    "custom": {
        "name": "Custom Mode",
        "badge": "🎯 Custom",
        "description": "Your custom system prompt.",
        "prompt": (
            "You are a customizable voice transcription post-processor. Refine the transcribed speech cleanly and accurately according to user preferences.\n\n"
            "Rules:\n"
            "1. Output ONLY the result text. No explanations, no <think> tags, no markdown wrappers, no quotation marks.\n"
            "2. Language Support: Support English and Hindi/Hinglish naturally. Preserve the original language (including Hindi words like 'theek hai', 'haan', 'acha', 'namaste') and tone unless instructed otherwise.\n"
            "3. Clean Disfluencies: Remove stutters, filler words ('um', 'uh', 'matlab', 'you know'), and accidental speech artifacts.\n"
            "4. Punctuation & Formatting: Ensure proper punctuation, capitalization, and clean spacing.\n"
            "5. Accurate Meaning: Preserve the exact core meaning, facts, and intent of the speaker."
        ),
    },
}

# ─── Default Configuration Dictionary ─────────────────────────────
DEFAULT_CONFIG: Dict[str, Any] = {
    # Hotkey & Recording
    "hotkey": "ctrl+space",
    "recording_mode": "push_to_talk",  # "push_to_talk", "toggle", "vad"
    "mic_device_id": None,             # None = default input device
    "mic_device_name": "Default Microphone",

    # Whisper Settings
    "whisper_model": "medium" if _DEFAULT_DEVICE == "cuda" else "small",
    "whisper_device": _DEFAULT_DEVICE,
    "whisper_compute_type": _DEFAULT_COMPUTE_TYPE,
    "whisper_language": None,          # None = Auto-detect
    "whisper_beam_size": 3 if _DEFAULT_DEVICE == "cuda" else 1,
    "whisper_vad_filter": True,
    "whisper_initial_prompt": "Hello, my name is Punit. I speak in English and Hindi. नमस्ते, कैसे हैं आप?",

    # Audio Engine
    "sample_rate": 16000,
    "silence_threshold": 0.015,
    "silence_duration": 1.8,
    "min_recording_duration": 0.4,

    # Active Mode & Refiner
    "current_mode": "smart",
    "ai_backend": "ollama",            # "ollama", "groq", "openai", "gemini", "none"
    
    # Ollama
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "qwen3:8b",
    "ollama_timeout": 20,

    # Groq Cloud (Ultra Fast 500+ tok/s)
    "groq_api_key": "",
    "groq_model": "llama-3.3-70b-versatile",

    # OpenAI / OpenRouter
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",

    # Gemini API
    "gemini_api_key": "",
    "gemini_model": "gemini-1.5-flash",

    # Typing & Pasting
    "paste_method": "clipboard",       # "clipboard", "sendinput", "both"
    "restore_clipboard": True,
    "clipboard_restore_delay": 0.4,
    "add_trailing_space": True,

    # Sound Cues & UI
    "sound_effects": True,
    "floating_hud_enabled": True,
    "hud_position": None,              # [x, y] or None for bottom-center
    "hud_opacity": 0.96,

    # Dictation Modes Store
    "dictation_modes": DEFAULT_DICTATION_MODES,
}


class ConfigManager:
    """Singleton configuration manager with auto-save and thread-safety."""

    def __init__(self):
        self._config: Dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
        self.load()

    def load(self) -> None:
        """Load settings from disk if available, otherwise write defaults."""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Merge with default config to handle new keys gracefully
                    for k, v in saved.items():
                        if k == "dictation_modes" and isinstance(v, dict):
                            # Merge custom modes with defaults
                            for mode_k, mode_v in v.items():
                                self._config["dictation_modes"][mode_k] = mode_v
                        else:
                            self._config[k] = v
            except Exception as e:
                print(f"[Config] Error loading settings ({e}), using defaults.")
        else:
            self.save()

    def save(self) -> None:
        """Write current settings to disk."""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self._config[key] = value
        if auto_save:
            self.save()

    def update(self, updates: Dict[str, Any], auto_save: bool = True) -> None:
        self._config.update(updates)
        if auto_save:
            self.save()

    @property
    def current_mode_info(self) -> Dict[str, str]:
        mode_key = self._config.get("current_mode", "smart")
        modes = self._config.get("dictation_modes", DEFAULT_DICTATION_MODES)
        return modes.get(mode_key, DEFAULT_DICTATION_MODES["smart"])

    @property
    def all_modes(self) -> Dict[str, Dict[str, str]]:
        return self._config.get("dictation_modes", DEFAULT_DICTATION_MODES)

    def cycle_next_mode(self) -> str:
        """Cycle to the next dictation mode and save."""
        modes = list(self.all_modes.keys())
        current = self.get("current_mode", "smart")
        try:
            idx = modes.index(current)
            next_idx = (idx + 1) % len(modes)
        except ValueError:
            next_idx = 0
        new_mode = modes[next_idx]
        self.set("current_mode", new_mode)
        return new_mode


# Global shared instance
config = ConfigManager()
