"""
LocalWhisper Pro — Audio Engine
Low-latency microphone capture, device enumeration, live RMS/spectrum stream
for UI visualizer bars, and silence detection.
"""

import time
import threading
from typing import List, Dict, Any, Optional, Callable, Tuple
import numpy as np
import sounddevice as sd
from config import config


class AudioEngine:
    """Manages audio capture and live visualizer stream."""

    def __init__(self):
        self._buffer: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._on_level: Optional[Callable[[float, List[float]], None]] = None
        self._on_silence_stop: Optional[Callable[[], None]] = None

        # Silence detection state
        self._silence_start_time: Optional[float] = None
        self._has_spoken = False
        self._recording_start_time = 0.0

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    # ── Device Enumeration ────────────────────────────────────────

    @staticmethod
    def list_input_devices(force_refresh: bool = False) -> List[Dict[str, Any]]:
        """List all available microphone input devices."""
        devices = []
        try:
            if force_refresh:
                try:
                    sd._terminate()
                    sd._initialize()
                except Exception as reinit_err:
                    print(f"[AudioEngine] Warning during PortAudio re-init: {reinit_err}")

            default_in = sd.default.device[0]
            hostapis = sd.query_hostapis()
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    api_idx = dev.get("hostapi", 0)
                    api_name = hostapis[api_idx]["name"] if api_idx < len(hostapis) else ""
                    is_def = (idx == default_in and default_in >= 0)
                    devices.append({
                        "id": idx,
                        "name": f"{dev['name']} ({api_name})",
                        "raw_name": dev.get("name", ""),
                        "hostapi": api_name,
                        "channels": dev["max_input_channels"],
                        "default_samplerate": dev.get("default_samplerate", 16000),
                        "is_default": is_def,
                    })
        except Exception as e:
            print(f"[AudioEngine] Failed to query devices: {e}")
        return devices

    # ── Recording Control ─────────────────────────────────────────

    def start(
        self,
        on_level: Optional[Callable[[float, List[float]], None]] = None,
        on_silence_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        """Start capturing audio from selected microphone."""
        if self._is_recording:
            return

        with self._lock:
            self._buffer.clear()

        self._on_level = on_level
        self._on_silence_stop = on_silence_stop
        self._is_recording = True
        self._silence_start_time = None
        self._has_spoken = False
        self._recording_start_time = time.perf_counter()

        sample_rate = config.get("sample_rate", 16000)
        device_id = config.get("mic_device_id", None)
        block_size = int(sample_rate * 0.05)  # 50ms chunks (20 updates/sec for smooth visualizer)

        try:
            self._stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
                device=device_id,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            print(f"[AudioEngine] Failed to open audio stream on device {device_id}: {exc}")
            # Try falling back to default system device
            try:
                self._stream = sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=block_size,
                    device=None,
                    callback=self._audio_callback,
                )
                self._stream.start()
                # Successfully fell back to default device — update config to match reality
                try:
                    def_id = sd.default.device[0]
                    if def_id is not None and def_id >= 0:
                        dev_info = sd.query_devices(def_id)
                        config.set("mic_device_id", def_id)
                        config.set("mic_device_name", dev_info.get("name", "Default Microphone"))
                        config.save()
                        print(f"[AudioEngine] Fallback active: Updated config to [{def_id}] {dev_info.get('name')}")
                except Exception as cfg_err:
                    print(f"[AudioEngine] Could not update config after fallback: {cfg_err}")
            except Exception as e2:
                self._is_recording = False
                if self._stream is not None:
                    try:
                        self._stream.close()
                    except Exception:
                        pass
                    self._stream = None
                raise RuntimeError(f"Could not open microphone: {e2}")

    def stop(self) -> np.ndarray:
        """Stop recording and return captured audio as 1-D float32 numpy array."""
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
            self._buffer.clear()

        return audio

    # ── Internal Callback ─────────────────────────────────────────

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """Audio stream callback running in background audio thread."""
        if not self._is_recording:
            return

        # Store audio chunk
        with self._lock:
            self._buffer.append(indata.copy())

        # Compute Root Mean Square (RMS) energy
        rms = float(np.sqrt(np.mean(indata**2)))

        # Compute multi-band spectrum for visualizer bars (5 bands)
        # Using quick FFT approximation for live waveform visualizer
        fft_data = np.abs(np.fft.rfft(indata.flatten()))
        bands = []
        if len(fft_data) >= 5:
            splits = np.array_split(fft_data, 5)
            for split in splits:
                band_energy = float(np.mean(split)) * 8.0
                bands.append(min(1.0, max(0.05, band_energy)))
        else:
            bands = [min(1.0, rms * 15.0)] * 5

        # Send live volume levels to UI
        if self._on_level:
            try:
                self._on_level(rms, bands)
            except Exception:
                pass

        # VAD & Silence Auto-Stop
        rec_mode = config.get("recording_mode", "push_to_talk")
        if rec_mode in ("vad", "toggle") and self._on_silence_stop is not None:
            threshold = config.get("silence_threshold", 0.015)
            silence_limit = config.get("silence_duration", 1.8)
            now = time.perf_counter()

            if rms >= threshold:
                self._has_spoken = True
                self._silence_start_time = None
            elif self._has_spoken:
                if self._silence_start_time is None:
                    self._silence_start_time = now
                elif (now - self._silence_start_time) >= silence_limit:
                    # Silence exceeded — auto-stop
                    self._on_silence_stop()
