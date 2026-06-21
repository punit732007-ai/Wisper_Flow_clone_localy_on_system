"""
LocalWhisper — Main Entry Point
Ties together: UI → Audio → Whisper → LLM → Paste

Usage:
    python main.py
"""

# IMPORTANT: import transcriber FIRST — it monkey-patches the broken `av` module
# before anything else can trigger a real import of `av`.
from transcriber import Transcriber

import sys
import time
import threading
import keyboard  # global hotkey

from config import GLOBAL_HOTKEY, AUDIO_SAMPLE_RATE, MIN_RECORDING_DURATION
from audio_capture import AudioCapture
from llm_refiner import LLMRefiner
from paster import paste_at_cursor
from floating_ui import FloatingUI


class LocalWhisper:
    """Orchestrates the full voice-to-text pipeline."""

    def __init__(self):
        self.audio = AudioCapture()
        self.transcriber = Transcriber()
        self.refiner = LLMRefiner()
        self.ui: FloatingUI | None = None
        self._processing = False
        self._last_hotkey_time = 0.0
        self._start_time = time.perf_counter()

    # ── Startup ───────────────────────────────────────────────────

    def start(self) -> None:
        """Create UI, register hotkey, load models, and run."""
        # Build the floating button (must be on the main thread)
        self.ui = FloatingUI(
            on_toggle=self._toggle_recording,
            on_quit=self._shutdown,
        )

        # Register global hotkey (Ctrl+Space)
        try:
            keyboard.add_hotkey(
                GLOBAL_HOTKEY,
                self._ptt_pressed,
                suppress=True,       # consume the key so apps don't see it
            )
            # Listen for release of the keys involved in the hotkey
            parts = GLOBAL_HOTKEY.split('+')
            for part in parts:
                keyboard.on_release_key(part.strip(), self._ptt_released)
            print(f"[Main] Global hotkey registered: {GLOBAL_HOTKEY}")
        except Exception as exc:
            print(f"[Main] Could not register hotkey: {exc}")

        # Load Whisper model + check Ollama in PARALLEL background threads
        threading.Thread(target=self._load_whisper, daemon=True, name="whisper-loader").start()
        threading.Thread(target=self._check_ollama, daemon=True, name="ollama-checker").start()

        print("[Main] LocalWhisper started -- waiting for input...")
        self.ui.run()  # blocks (tkinter main loop)

    # ── Model Loading (Parallel) ─────────────────────────────────

    def _load_whisper(self) -> None:
        """Load Whisper model (runs in background thread)."""
        try:
            self.transcriber.load_model()
        except Exception as exc:
            print(f"[Main] FAILED to load Whisper model: {exc}")

        # Model ready — update UI on the main thread
        self.ui.schedule(self.ui.set_state, "ready")
        elapsed = time.perf_counter() - self._start_time
        print(f"[Main] All models loaded -- ready to record OK ({elapsed:.1f}s total)")

    def _check_ollama(self) -> None:
        """Check Ollama availability (runs in parallel with Whisper loading)."""
        self.refiner.check_availability()

    # ── Recording Toggle ──────────────────────────────────────────

    def _ptt_pressed(self) -> None:
        """Triggered on hotkey down."""
        # Auto-repeat might fire this multiple times while held. That's perfectly fine.
        if self._processing or not self.transcriber.is_loaded:
            return
            
        if not self.audio.is_recording:
            self.ui.schedule(self._start_recording)

    def _ptt_released(self, event) -> None:
        """Triggered on hotkey release (hardware KeyUp event)."""
        # Since this ONLY fires when you physically let go of the keys,
        # we can safely stop recording without worrying about lag or auto-repeat!
        if self.audio.is_recording:
            self.ui.schedule(self._stop_and_process)

    def _toggle_recording(self) -> None:
        """Toggle between recording and idle."""
        if self._processing:
            return  # ignore while processing

        if not self.transcriber.is_loaded:
            print("[Main] Model still loading -- please wait")
            return

        if self.audio.is_recording:
            self._stop_and_process()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        """Begin capturing audio."""
        self.ui.set_state("recording")
        self.audio.start()
        print("[Main] Recording started...")

    def _stop_and_process(self) -> None:
        """Stop recording and kick off the transcription pipeline."""
        if not self.audio.is_recording and not self._processing:
            return
        if self._processing:
            return

        self._processing = True
        self.ui.set_state("processing")

        # Grab the audio buffer
        audio_data = self.audio.stop()
        print(f"[Main] Recording stopped -- {len(audio_data)} samples "
              f"({len(audio_data)/AUDIO_SAMPLE_RATE:.1f}s)")

        # Process in a background thread so the UI stays alive
        threading.Thread(
            target=self._process_audio,
            args=(audio_data,),
            daemon=True,
        ).start()

    # ── Processing Pipeline ───────────────────────────────────────

    def _process_audio(self, audio_data) -> None:
        """Transcribe → refine → paste.  Runs in a worker thread."""
        try:
            duration = len(audio_data) / AUDIO_SAMPLE_RATE
            if duration < MIN_RECORDING_DURATION:
                print("[Main] Recording too short -- skipping")
                return

            # Step 1: Whisper transcription
            raw_text, lang = self.transcriber.transcribe(audio_data)
            if not raw_text.strip():
                print("[Main] Empty transcription -- skipping")
                return

            # Step 2: LLM refinement
            refined_text = self.refiner.refine(raw_text, lang)

            # Step 3: Paste at cursor
            paste_at_cursor(refined_text)

        except Exception as exc:
            print(f"[Main] FAILED processing error: {exc}")
        finally:
            self._processing = False
            self.ui.schedule(self.ui.set_state, "ready")

    # ── Shutdown ──────────────────────────────────────────────────

    def _shutdown(self) -> None:
        """Clean up on exit."""
        print("[Main] Shutting down...")
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self.audio.is_recording:
            self.audio.stop()


# ══════════════════════════════════════════════════════════════════

def main():
    app = LocalWhisper()
    app.start()


if __name__ == "__main__":
    main()
