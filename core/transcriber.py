"""
LocalWhisper Pro — Transcriber
High-speed speech-to-text using faster-whisper (CTranslate2 backend).
Features CUDA hardware auto-acceleration, warm-up caching, and bilingual English/Hindi prompts.
"""

import os
import time
import threading
from typing import Tuple, Optional, List
import numpy as np

# Monkey-patch: bypass pyav if needed
import sys
import types

_fake_av = types.ModuleType("av")
_fake_av.__path__ = []
_fake_av_audio = types.ModuleType("av.audio")
_fake_av_container = types.ModuleType("av.container")
_fake_av_codec = types.ModuleType("av.codec")

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

from faster_whisper import WhisperModel
from config import (
    config,
    WARMUP_CACHE_FILE,
    WARMUP_CACHE_MAX_AGE,
)


def _is_warmup_cached(device: str, model_name: str) -> bool:
    """Check if model warm-up was already cached within 24h."""
    try:
        if WARMUP_CACHE_FILE.exists():
            age = time.time() - os.path.getmtime(WARMUP_CACHE_FILE)
            if age < WARMUP_CACHE_MAX_AGE:
                with open(WARMUP_CACHE_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content == f"{device}:{model_name}":
                    return True
    except Exception:
        pass
    return False


def _mark_warmup_done(device: str, model_name: str):
    """Write warm-up cache marker."""
    try:
        with open(WARMUP_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(f"{device}:{model_name}")
    except Exception:
        pass


def _clear_warmup_cache():
    """Clear warm-up cache marker."""
    try:
        if WARMUP_CACHE_FILE.exists():
            WARMUP_CACHE_FILE.unlink()
    except Exception:
        pass


class Transcriber:
    """CTranslate2 Whisper transcriber with GPU auto-tuning."""

    def __init__(self):
        self._model: Optional[WhisperModel] = None
        self._current_model_name: Optional[str] = None
        self._current_device: Optional[str] = None
        self._lock = threading.Lock()
        self._is_loading = False

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    def load_model(self, force: bool = False) -> None:
        """Load or reload the Whisper model into GPU/CPU memory."""
        with self._lock:
            target_model = config.get("whisper_model", "small")
            target_device = config.get("whisper_device", "cuda")
            target_compute = config.get("whisper_compute_type", "float16")

            if (
                not force
                and self._model is not None
                and self._current_model_name == target_model
                and self._current_device == target_device
            ):
                return

            self._is_loading = True
            t0 = time.perf_counter()
            print(
                f"[Transcriber] Loading model '{target_model}' on {target_device} ({target_compute})..."
            )

            try:
                self._model = WhisperModel(
                    target_model,
                    device=target_device,
                    compute_type=target_compute,
                )
                self._current_model_name = target_model
                self._current_device = target_device

                # CUDA Warm-up execution
                if target_device == "cuda":
                    if _is_warmup_cached(target_device, target_model):
                        elapsed = time.perf_counter() - t0
                        print(f"[Transcriber] Warm-up cached — model ready in {elapsed:.1f}s")
                    else:
                        print("[Transcriber] Performing CUDA warm-up pass...")
                        dummy_audio = np.random.randn(16000).astype(np.float32) * 0.05
                        list(self._model.transcribe(dummy_audio, vad_filter=False))
                        _mark_warmup_done(target_device, target_model)
                        elapsed = time.perf_counter() - t0
                        print(f"[Transcriber] Warm-up complete — ready in {elapsed:.1f}s")
                else:
                    elapsed = time.perf_counter() - t0
                    print(f"[Transcriber] CPU model ready in {elapsed:.1f}s")

            except Exception as e:
                err_msg = str(e).lower()
                if "cublas" in err_msg or "cuda" in err_msg or "cudnn" in err_msg or "library" in err_msg:
                    print(f"[Transcriber] CUDA failed: {e}. Falling back to CPU int8...")
                    _clear_warmup_cache()
                    self._model = WhisperModel(
                        target_model,
                        device="cpu",
                        compute_type="int8",
                    )
                    self._current_model_name = target_model
                    self._current_device = "cpu"
                    config.set("whisper_device", "cpu")
                    config.set("whisper_compute_type", "int8")
                    elapsed = time.perf_counter() - t0
                    print(f"[Transcriber] CPU fallback model ready in {elapsed:.1f}s")
                else:
                    self._is_loading = False
                    raise e

            self._is_loading = False

    def transcribe(self, audio: np.ndarray) -> Tuple[str, str, float]:
        """
        Transcribe 16kHz float32 audio array.
        Returns: (transcribed_text, detected_language, confidence_prob)
        """
        if self._model is None:
            self.load_model()

        if self._model is None:
            raise RuntimeError("Whisper model could not be initialized.")

        beam_size = config.get("whisper_beam_size", 3)
        vad_filter = config.get("whisper_vad_filter", True)
        language = config.get("whisper_language", None)
        initial_prompt = config.get("whisper_initial_prompt", None)

        try:
            segments, info = self._model.transcribe(
                audio,
                beam_size=beam_size,
                vad_filter=vad_filter,
                initial_prompt=initial_prompt,
                language=language,
            )

            text_parts: List[str] = []
            for seg in segments:
                text_parts.append(seg.text)

            full_text = " ".join(text_parts).strip()
            detected_lang = info.language if info and info.language else "en"
            lang_prob = info.language_probability if info else 1.0

            print(f"[Transcriber] lang={detected_lang} ({lang_prob:.2f}): {full_text!r}")
            return full_text, detected_lang, lang_prob

        except Exception as e:
            err_msg = str(e).lower()
            if "cublas" in err_msg or "cuda" in err_msg:
                print(f"[Transcriber] CUDA runtime error ({e}) — switching to CPU fallback...")
                self.load_model(force=True)
                return self.transcribe(audio)
            raise e
