"""
LocalWhisper — Audio Capture
Records microphone audio with automatic silence detection.
"""

import threading
import time
import numpy as np
import sounddevice as sd
from config import (
    AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_BLOCK_MS,
    SILENCE_THRESHOLD, SILENCE_DURATION, MIN_RECORDING_DURATION,
)


class AudioCapture:
    """Records audio from the default microphone with silence-based auto-stop."""

    def __init__(self):
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._is_recording = False

        # Silence detection state (removed for Push-to-Talk)
        self._on_silence_stop: callable = None

    # ── Public API ────────────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self, on_silence_stop: callable = None) -> None:
        """Begin recording. Optionally call *on_silence_stop* when silence
        is detected after the user has spoken."""
        with self._lock:
            self._buffer = []
        self._on_silence_stop = on_silence_stop
        self._is_recording = True

        block_size = int(AUDIO_SAMPLE_RATE * AUDIO_BLOCK_MS / 1000)
        self._stream = sd.InputStream(
            samplerate=AUDIO_SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            dtype="float32",
            blocksize=block_size,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return the captured audio as a 1-D float32 array."""
        self._is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if self._buffer:
                audio = np.concatenate(self._buffer, axis=0).flatten()
            else:
                audio = np.array([], dtype=np.float32)
            self._buffer = []
        return audio

    # ── Internal ──────────────────────────────────────────────────

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info, status) -> None:
        """Called by sounddevice for every audio block."""
        if not self._is_recording:
            return

        # Store audio
        with self._lock:
            self._buffer.append(indata.copy())
