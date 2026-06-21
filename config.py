"""
LocalWhisper — Configuration
All tunable constants live here.
"""

import os
import sys
import time

# ─── Warm-up Cache Directory ─────────────────────────────────────
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".localwhisper")
os.makedirs(CACHE_DIR, exist_ok=True)
WARMUP_CACHE_FILE = os.path.join(CACHE_DIR, "warmup_ok")
WARMUP_CACHE_MAX_AGE = 24 * 3600  # 24 hours — skip warm-up if recent


# ─── Robust ctranslate2 import with DLL retry ────────────────────
def _import_ctranslate2():
    """Import ctranslate2 with retry logic for Windows DLL caching.

    On first cold boot, Windows may not have cached the CUDA DLL
    search paths yet, causing ctypes.CDLL to fail.  A short retry
    after the first failure gives Windows time to populate the cache.
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            import ctranslate2
            return ctranslate2
        except OSError as exc:
            err = str(exc).lower()
            if attempt < max_retries - 1 and ("dll" in err or "library" in err
                                               or "winerror" in err
                                               or "cublas" in err):
                print(f"[Config] ctranslate2 DLL load failed (attempt {attempt + 1}), "
                      f"retrying in 1s...")
                # Force-add CUDA paths to DLL search directories
                _preload_cuda_paths()
                time.sleep(1)
            else:
                raise
    return None


def _preload_cuda_paths():
    """Add common CUDA DLL directories to the system's DLL search path.

    This helps Windows find cublas64_12.dll and other CUDA libraries
    on the very first import attempt.
    """
    cuda_dirs = []

    # CUDA_PATH environment variable (set by CUDA Toolkit installer)
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path:
        cuda_dirs.append(os.path.join(cuda_path, "bin"))

    # Common CUDA installation paths
    for ver in ["v12.8", "v12.6", "v12.4", "v12.2", "v12.1", "v12.0",
                "v11.8", "v11.7"]:
        path = rf"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\{ver}\bin"
        if os.path.isdir(path):
            cuda_dirs.append(path)

    # cuDNN paths
    cudnn_path = os.environ.get("CUDNN", "")
    if cudnn_path:
        cuda_dirs.append(os.path.join(cudnn_path, "bin"))

    # Add to DLL search paths (Python 3.8+)
    if hasattr(os, "add_dll_directory"):
        for d in cuda_dirs:
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass

    # Also prepend to PATH as a fallback
    path_env = os.environ.get("PATH", "")
    for d in reversed(cuda_dirs):
        if os.path.isdir(d) and d not in path_env:
            os.environ["PATH"] = d + ";" + os.environ.get("PATH", "")


# Pre-load CUDA paths BEFORE any ctranslate2 import attempt
_preload_cuda_paths()

# Now import ctranslate2 with retry
_ct2 = _import_ctranslate2()


def _detect_device() -> tuple[str, str]:
    """Auto-detect the best device: try CUDA first, fall back to CPU."""
    if _ct2 is None:
        print("[Config] ctranslate2 failed to import — using CPU (int8)")
        return "cpu", "int8"

    try:
        cuda_types = _ct2.get_supported_compute_types("cuda")
        if "float16" in cuda_types:
            print("[Config] ✓ CUDA available — using GPU (float16)")
            return "cuda", "float16"
        if "int8_float16" in cuda_types:
            print("[Config] ✓ CUDA available — using GPU (int8_float16)")
            return "cuda", "int8_float16"
    except Exception:
        pass
    print("[Config] CUDA not available — using CPU (int8)")
    return "cpu", "int8"


_DEVICE, _COMPUTE_TYPE = _detect_device()


# ─── Whisper Model ────────────────────────────────────────────────
# Smaller+faster model on CPU; higher quality on GPU
WHISPER_MODEL_SIZE = "small" if _DEVICE == "cpu" else "medium"
WHISPER_DEVICE = _DEVICE
WHISPER_COMPUTE_TYPE = _COMPUTE_TYPE
WHISPER_BEAM_SIZE = 1 if _DEVICE == "cpu" else 3    # greedy on CPU for speed
WHISPER_VAD_FILTER = True              # Silero VAD — skip silent segments
WHISPER_LANGUAGE = None                # None = auto-detect (Hindi, English, Hinglish)

# Multilingual initial prompt helps Whisper handle code-switching
WHISPER_INITIAL_PROMPT = (
    "Hello, my name is Punit. I speak in English and Hindi. "
    "नमस्ते, मेरा नाम पुनीत है।"
)

# ─── Ollama LLM ───────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_TIMEOUT = 30                    # 30s timeout (reduced for faster fallback)

REFINEMENT_SYSTEM_PROMPT = """\
You are a speech-to-text post-processor.
Your ONLY job is to fix transcription errors and output the corrected text.

Rules:
1. Output ONLY the corrected text. No explanations, no quotes, no prefixes, no markdown.
2. Keep the SAME language as the input. Do NOT translate between languages.
3. Fix misheard or garbled words using surrounding context.
4. Add natural punctuation (periods, commas, question marks).
5. Do NOT add or remove content. Only fix errors.
6. Keep it natural - this is casual speech, not formal writing.
7. DO NOT output any <think>, <thought>, or reasoning blocks. Reply directly with the final text.
8. If the transcription already looks correct, return it as-is.\
"""

# ─── Audio Capture ────────────────────────────────────────────────
AUDIO_SAMPLE_RATE = 16000              # Whisper expects 16 kHz
AUDIO_CHANNELS = 1                     # Mono
AUDIO_BLOCK_MS = 100                   # Callback block size in milliseconds
SILENCE_THRESHOLD = 0.015              # RMS below this = silence
SILENCE_DURATION = 1.8                 # Seconds of silence before auto-stop
MIN_RECORDING_DURATION = 0.5           # Minimum recording length (seconds)

# ─── UI ───────────────────────────────────────────────────────────
BUTTON_WIDTH = 164
BUTTON_HEIGHT = 50
BUTTON_RADIUS = 22                     # Corner radius for the pill shape
BUTTON_PADDING = 14                    # Padding from screen edge
TRANSPARENT_COLOR = "#f0abcd"          # Unlikely color used for window transparency
ANIMATION_FPS = 30                     # Animation frame rate

# ─── Global Hotkey ────────────────────────────────────────────────
GLOBAL_HOTKEY = "ctrl+space"
