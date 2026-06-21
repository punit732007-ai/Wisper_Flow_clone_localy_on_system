"""
LocalWhisper — Transcriber
Speech-to-text using faster-whisper (CTranslate2 backend).

We bypass the `av` audio decoder entirely by feeding raw numpy arrays
directly to the model, since our audio comes from sounddevice (already
16 kHz float32).
"""

import io
import os
import time
import numpy as np

# Monkey-patch: prevent faster_whisper from importing the broken `av` module.
# We never use file-based audio decoding, so this is safe.
import sys
import types

# Create a fake 'av' module so faster_whisper can import without error
_fake_av = types.ModuleType("av")
_fake_av.__path__ = []
_fake_av_audio = types.ModuleType("av.audio")
_fake_av_container = types.ModuleType("av.container")
_fake_av_codec = types.ModuleType("av.codec")

# Add minimal stubs that faster_whisper.audio might reference
class _FakeAudioFrame:
    pass

class _FakeAudioCodecContext:
    pass

class _FakeContainer:
    pass

_fake_av_audio.AudioFrame = _FakeAudioFrame
_fake_av_audio.AudioCodecContext = _FakeAudioCodecContext
_fake_av_container.Container = _FakeContainer

sys.modules.setdefault("av", _fake_av)
sys.modules.setdefault("av.audio", _fake_av_audio)
sys.modules.setdefault("av.audio.frame", _fake_av_audio)
sys.modules.setdefault("av.audio.codeccontext", _fake_av_audio)
sys.modules.setdefault("av.container", _fake_av_container)
sys.modules.setdefault("av.container.core", _fake_av_container)
sys.modules.setdefault("av.codec", _fake_av_codec)
sys.modules.setdefault("av.codec.codec", _fake_av_codec)
sys.modules.setdefault("av.codec.context", _fake_av_codec)
sys.modules.setdefault("av.codec.hwaccel", _fake_av_codec)
sys.modules.setdefault("av.video", types.ModuleType("av.video"))
sys.modules.setdefault("av.video.frame", types.ModuleType("av.video.frame"))
sys.modules.setdefault("av.frame", types.ModuleType("av.frame"))

for mod_name in list(sys.modules):
    if mod_name.startswith("av."):
        sys.modules[mod_name].__path__ = []
        sys.modules[mod_name].__spec__ = None

from faster_whisper import WhisperModel
from config import (
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    WHISPER_BEAM_SIZE, WHISPER_VAD_FILTER, WHISPER_INITIAL_PROMPT,
    WHISPER_LANGUAGE,
    CACHE_DIR, WARMUP_CACHE_FILE, WARMUP_CACHE_MAX_AGE,
)


def _is_warmup_cached() -> bool:
    """Check if we have a recent warm-up cache marker.

    If the warm-up was done within the last WARMUP_CACHE_MAX_AGE seconds
    (default 24h), we can skip the expensive dummy transcription on startup.
    """
    try:
        if os.path.exists(WARMUP_CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(WARMUP_CACHE_FILE)
            if cache_age < WARMUP_CACHE_MAX_AGE:
                # Also verify the cached device matches current device
                with open(WARMUP_CACHE_FILE, "r") as f:
                    cached_device = f.read().strip()
                if cached_device == WHISPER_DEVICE:
                    return True
    except Exception:
        pass
    return False


def _mark_warmup_done():
    """Write a cache marker to skip warm-up next time."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(WARMUP_CACHE_FILE, "w") as f:
            f.write(WHISPER_DEVICE)
    except Exception:
        pass


def _clear_warmup_cache():
    """Clear the warm-up cache (e.g., after a CUDA fallback)."""
    try:
        if os.path.exists(WARMUP_CACHE_FILE):
            os.remove(WARMUP_CACHE_FILE)
    except Exception:
        pass


class Transcriber:
    """Wraps faster-whisper for local speech recognition."""

    def __init__(self):
        self._model: WhisperModel | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        """Load the Whisper model into memory.  Call once, ideally in a
        background thread so the UI stays responsive."""
        t0 = time.perf_counter()

        print(f"[Transcriber] Loading whisper model '{WHISPER_MODEL_SIZE}' "
              f"on {WHISPER_DEVICE} ({WHISPER_COMPUTE_TYPE})...")
        self._model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

        # Run a dummy transcription to force CUDA/cuBLAS lazy loading and warm up the model
        # SKIP if we have a recent warm-up cache (saves ~3-5 seconds)
        if WHISPER_DEVICE == "cuda":
            if _is_warmup_cached():
                elapsed = time.perf_counter() - t0
                print(f"[Transcriber] Warm-up cached — skipping dummy transcription")
                print(f"[Transcriber] Model loaded OK ({elapsed:.1f}s)")
                return

            print("[Transcriber] Running CUDA warm-up...")
            # Use random noise instead of zeros so CTranslate2 actually performs matrix ops
            dummy_audio = np.random.randn(16000).astype(np.float32) * 0.1
            try:
                # MUST set vad_filter=False here, otherwise the VAD skips the zeros
                # and the core Whisper model (and cuBLAS) is never actually executed!
                list(self._model.transcribe(dummy_audio, vad_filter=False, language=WHISPER_LANGUAGE))
                _mark_warmup_done()
                elapsed = time.perf_counter() - t0
                print(f"[Transcriber] Model loaded OK ({elapsed:.1f}s)")
            except Exception as e:
                err_msg = str(e).lower()
                if "cublas" in err_msg or "cuda" in err_msg or "cudnn" in err_msg or "library" in err_msg:
                    print(f"[Transcriber] CUDA warm-up failed: {e}")
                    print("[Transcriber] Falling back to CPU (int8)...")
                    _clear_warmup_cache()
                    self._model = WhisperModel(
                        WHISPER_MODEL_SIZE,
                        device="cpu",
                        compute_type="int8",
                    )
                    # Warm up the CPU model as well
                    list(self._model.transcribe(dummy_audio, vad_filter=False, language=WHISPER_LANGUAGE))
                    _mark_warmup_done()
                    elapsed = time.perf_counter() - t0
                    print(f"[Transcriber] Model loaded OK — CPU fallback ({elapsed:.1f}s)")
                else:
                    raise e
        else:
            elapsed = time.perf_counter() - t0
            print(f"[Transcriber] Model loaded OK ({elapsed:.1f}s)")

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        """Transcribe a 16 kHz float32 audio array.

        Returns
        -------
        (text, language) — e.g. ("hello bhai kaise ho", "hi")
        """
        if self._model is None:
            raise RuntimeError("Model not loaded — call load_model() first.")

        try:
            segments, info = self._model.transcribe(
                audio,
                beam_size=WHISPER_BEAM_SIZE,
                vad_filter=WHISPER_VAD_FILTER,
                initial_prompt=WHISPER_INITIAL_PROMPT,
                language=WHISPER_LANGUAGE,
            )
            
            # Consume the generator HERE inside the try block to trigger cuBLAS
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)
                
            detected_lang = info.language if info.language else "en"
                
        except Exception as e:
            err_msg = str(e).lower()
            if "cublas" in err_msg or "cuda" in err_msg or "cudnn" in err_msg or "library" in err_msg:
                print(f"[Transcriber] CUDA crashed during transcribe: {e}")
                print("[Transcriber] On-the-fly fallback to CPU (int8)...")
                _clear_warmup_cache()
                self._model = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device="cpu",
                    compute_type="int8",
                )
                segments, info = self._model.transcribe(
                    audio,
                    beam_size=WHISPER_BEAM_SIZE,
                    vad_filter=WHISPER_VAD_FILTER,
                    initial_prompt=WHISPER_INITIAL_PROMPT,
                    language=WHISPER_LANGUAGE,
                )
                
                # Consume the fallback generator
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text)
                    
                detected_lang = info.language if info.language else "en"
            else:
                raise e

        full_text = " ".join(text_parts).strip()

        print(f"[Transcriber] lang={detected_lang}  "
              f"prob={info.language_probability:.2f}  text={full_text!r}")
        return full_text, detected_lang
