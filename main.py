"""
LocalWhisper Pro v3.0 — Main Entrypoint & Coordinator
Orchestrates Audio Capture, Faster-Whisper GPU Inference, Multi-Mode AI Refiner,
Direct Win32/Clipboard Pasting, Real-time HUD Visualizer, Settings, and System Tray.
"""

import sys

# Force UTF-8 encoding for Windows terminals to prevent UnicodeEncodeError crashes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import threading
from typing import Optional

from config import config
from core.audio_engine import AudioEngine
from core.transcriber import Transcriber
from core.ai_refiner import ai_refiner
from core.paster import paste_text
from core.history_manager import history_manager
from core.sound_effects import play_start, play_stop, play_success, play_error
from core.hotkey_manager import HotkeyManager
from ui.floating_hud import FloatingHUD
from ui.settings_window import SettingsWindow
from ui.history_window import HistoryWindow
from ui.tray_icon import SystemTray


class LocalWhisperApp:
    """Master application coordinator."""

    def __init__(self):
        self.audio = AudioEngine()
        self.transcriber = Transcriber()
        self.is_processing = False
        self._shutdown_event = threading.Event()

        # UI Windows
        self.hud = FloatingHUD(
            on_toggle_recording=self.toggle_recording,
            on_cycle_mode=self.cycle_mode,
            on_open_settings=self.open_settings,
            on_open_history=self.open_history,
            on_quit=self.shutdown,
        )

        self.settings_win = SettingsWindow(
            parent_root=self.hud.root,
            on_settings_changed=self.reload_settings,
        )

        self.history_win = HistoryWindow(
            parent_root=self.hud.root,
        )

        self.tray = SystemTray(
            on_toggle_hud=self._toggle_hud_visibility,
            on_open_settings=self.open_settings,
            on_open_history=self.open_history,
            on_cycle_mode=self.cycle_mode,
            on_quit=self.shutdown,
        )

        self.hotkeys = HotkeyManager(
            on_start_record=self.start_recording,
            on_stop_record=self.stop_and_process,
            on_toggle_record=self.toggle_recording,
            on_cycle_mode=self.cycle_mode,
            on_cancel_record=self.cancel_recording,
        )

    # ── Startup & Initialization ─────────────────────────────────

    def run(self) -> None:
        """Initialize background workers and start UI event loop."""
        print("[LocalWhisper Pro] Starting v3.0...")

        # 1. Start global hotkeys
        self.hotkeys.start()

        # 2. Start system tray
        self.tray.start()

        # 3. Load Whisper model and check AI backend in parallel background threads
        threading.Thread(target=self._init_models, daemon=True, name="model-loader").start()

        # 4. Start Tkinter event loop (blocks main thread)
        self.hud.run()

    def _init_models(self) -> None:
        """Load Whisper and AI refiner in background."""
        t0 = time.perf_counter()
        try:
            self.transcriber.load_model()
            ai_refiner.check_backend_status()
            elapsed = time.perf_counter() - t0
            print(f"[LocalWhisper Pro] All systems initialized in {elapsed:.1f}s — Ready!")
            self.hud.schedule(self.hud.set_state, "ready")
        except Exception as exc:
            print(f"[LocalWhisper Pro] Initialization error: {exc}")
            play_error()
            self.hud.schedule(self.hud.set_state, "error")

    # ── Recording Control ─────────────────────────────────────────

    def start_recording(self) -> None:
        """Begin audio capture."""
        if self.is_processing or self.audio.is_recording:
            return

        if not self.transcriber.is_loaded and self.transcriber.is_loading:
            print("[Main] Whisper model is still loading, please wait...")
            return

        try:
            play_start()
            self.hud.schedule(self.hud.set_state, "recording")
            self.audio.start(
                on_level=self._on_audio_level,
                on_silence_stop=self._on_vad_silence,
            )
            print("[Main] Recording started...")
        except Exception as e:
            print(f"[Main] Failed to start recording: {e}")
            play_error()
            self.hud.schedule(self.hud.set_state, "error")
            # Auto-revert HUD back to ready state after 1.5 seconds
            def _revert_ready():
                time.sleep(1.5)
                self.hud.schedule(self.hud.set_state, "ready")
            threading.Thread(target=_revert_ready, daemon=True, name="hud-error-revert").start()

    def stop_and_process(self) -> None:
        """Stop audio capture and process through transcription & AI pipeline."""
        if not self.audio.is_recording or self.is_processing:
            return

        self.is_processing = True
        play_stop()
        self.hud.schedule(self.hud.set_state, "processing")

        # Capture audio buffer
        audio_data = self.audio.stop()
        duration_sec = len(audio_data) / config.get("sample_rate", 16000)
        print(f"[Main] Recording captured: {duration_sec:.2f}s ({len(audio_data)} samples)")

        # Run pipeline in worker thread to prevent UI freezing
        threading.Thread(
            target=self._pipeline_worker,
            args=(audio_data, duration_sec),
            daemon=True,
            name="pipeline-worker",
        ).start()

    def cancel_recording(self) -> None:
        """Discard current recording without processing."""
        if self.audio.is_recording:
            self.audio.stop()
            play_error()
            print("[Main] Recording cancelled.")
            self.hud.schedule(self.hud.set_state, "ready")

    def toggle_recording(self) -> None:
        """Toggle between recording and processing states."""
        if self.audio.is_recording:
            self.stop_and_process()
        else:
            self.start_recording()

    def _on_vad_silence(self) -> None:
        """Triggered automatically by AudioEngine when silence duration is reached in VAD mode."""
        print("[Main] VAD silence detected — auto-stopping recording...")
        self.stop_and_process()

    def _on_audio_level(self, rms: float, bands: list) -> None:
        """Forward audio levels to HUD visualizer widget."""
        self.hud.update_audio_levels(rms, bands)

    # ── Pipeline Worker ───────────────────────────────────────────

    def _pipeline_worker(self, audio_data, duration_sec: float) -> None:
        """Background pipeline: Transcribe -> AI Refine -> Paste -> History Record."""
        try:
            min_dur = config.get("min_recording_duration", 0.4)
            if duration_sec < min_dur or len(audio_data) == 0:
                print(f"[Pipeline] Audio duration ({duration_sec:.2f}s) below threshold ({min_dur}s) — skipping.")
                return

            t0 = time.perf_counter()

            # Step 1: Faster-Whisper Inference
            raw_text, lang, prob = self.transcriber.transcribe(audio_data)
            if not raw_text.strip():
                print("[Pipeline] No speech detected in audio.")
                return

            whisper_time = time.perf_counter() - t0

            # Step 2: AI Multi-Mode Refinement
            mode_info = config.current_mode_info
            mode_key = config.get("current_mode", "smart")
            t_refine = time.perf_counter()

            refined_text = ai_refiner.refine(raw_text, lang)
            refine_time = time.perf_counter() - t_refine

            total_time = time.perf_counter() - t0
            # Safe print: encode to ascii with replace to avoid UnicodeEncodeError on cp1252 terminals
            safe_text = refined_text.encode("ascii", errors="replace").decode("ascii")
            print(
                f"[Pipeline] Whisper: {whisper_time:.2f}s | Refine: {refine_time:.2f}s | Total: {total_time:.2f}s\n"
                f"           Result: {safe_text}"
            )

            # Step 3: Paste at Active Cursor
            paste_text(refined_text)
            play_success()

            # Step 4: Record into History
            history_manager.add_entry(
                raw_text=raw_text,
                refined_text=refined_text,
                mode_key=mode_key,
                mode_name=mode_info.get("name", "Smart Dictation"),
                duration_sec=duration_sec,
                language=lang,
                model_name=config.get("whisper_model", "medium"),
            )

            # Flash success state
            self.hud.schedule(self.hud.set_state, "success")
            time.sleep(1.2)

        except Exception as exc:
            print(f"[Pipeline] Error during processing: {exc}")
            play_error()
            self.hud.schedule(self.hud.set_state, "error")
            time.sleep(1.5)

        finally:
            self.is_processing = False
            self.hud.schedule(self.hud.set_state, "ready")

    # ── UI Actions & Navigation ───────────────────────────────────

    def cycle_mode(self) -> None:
        """Cycle to next dictation mode."""
        new_mode = config.cycle_next_mode()
        mode_info = config.current_mode_info
        self.hud.schedule(self.hud._apply_state_style)
        print(f"[Main] Switched to mode: {mode_info.get('name', new_mode)} ({mode_info.get('badge', '')})")

    def open_settings(self) -> None:
        """Open the graphical settings dialog."""
        self.hud.schedule(self.settings_win.show)

    def open_history(self) -> None:
        """Open the transcript history drawer."""
        self.hud.schedule(self.history_win.show)

    def reload_settings(self) -> None:
        """Apply dynamic configuration changes without restart."""
        print("[Main] Reloading updated configuration...")
        self.hotkeys.rebind()
        # Reload whisper model if changed
        threading.Thread(target=lambda: self.transcriber.load_model(force=False), daemon=True).start()

    def _toggle_hud_visibility(self) -> None:
        """Show or hide the floating HUD from system tray."""
        if self.hud.root.winfo_viewable():
            self.hud.schedule(self.hud.hide)
        else:
            self.hud.schedule(self.hud.show)

    def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        print("[LocalWhisper Pro] Shutting down...")
        self.hotkeys.stop()
        self.tray.stop()
        if self.audio.is_recording:
            self.audio.stop()
        try:
            self.hud.root.quit()
            self.hud.root.destroy()
        except Exception:
            pass
        import os
        os._exit(0)


def main():
    app = LocalWhisperApp()
    app.run()


if __name__ == "__main__":
    main()
