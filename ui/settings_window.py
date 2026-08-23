"""
LocalWhisper Pro — Settings Window
Comprehensive multi-tab graphical settings interface for audio, models, AI backends,
dictation modes, hotkeys, and typing options.
"""

import re
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, List, Dict, Any, Tuple
from config import config, DEFAULT_DICTATION_MODES
from core.audio_engine import AudioEngine
from core.ai_refiner import ai_refiner


# ── Model Options & Mappings (R4) ─────────────────────────────

WHISPER_MODEL_OPTIONS: List[Tuple[str, str]] = [
    ("tiny", "tiny (39M) — Fastest"),
    ("base", "base (74M) — Fast"),
    ("small", "small (244M) — Balanced"),
    ("medium", "medium (769M) — Accurate"),
    ("large-v3", "large-v3 (1.5GB) — Best Quality"),
    ("distil-large-v3", "distil-large-v3 (756M) — Fast+Quality"),
]

MODEL_ID_TO_LABEL: Dict[str, str] = {model_id: label for model_id, label in WHISPER_MODEL_OPTIONS}
MODEL_LABEL_TO_ID: Dict[str, str] = {label: model_id for model_id, label in WHISPER_MODEL_OPTIONS}


# ── Language Options & Mappings (R1) ──────────────────────────

WHISPER_LANG_OPTIONS: List[Tuple[Optional[str], str]] = [
    (None, "Auto-detect (English/Hindi)"),
    ("en", "en (English)"),
    ("hi", "hi (Hindi)"),
]

LANG_CODE_TO_LABEL: Dict[Optional[str], str] = {code: label for code, label in WHISPER_LANG_OPTIONS}
LANG_LABEL_TO_CODE: Dict[str, Optional[str]] = {label: code for code, label in WHISPER_LANG_OPTIONS}


class SettingsWindow:
    """Settings dialog with categorized configuration tabs."""

    def __init__(self, parent_root: tk.Tk, on_settings_changed: Optional[Callable[[], None]] = None):
        self.parent = parent_root
        self.on_settings_changed = on_settings_changed
        self.win: Optional[tk.Toplevel] = None
        self._test_stream = None
        self._test_active = False
        self._device_map: Dict[str, Dict[str, Any]] = {}

    def show(self) -> None:
        """Create or bring settings window to focus."""
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return

        self.win = tk.Toplevel(self.parent)
        self.win.title("LocalWhisper Pro — Settings")
        self.win.geometry("640x540")
        self.win.minsize(580, 480)
        self.win.configure(bg="#1e1e2e")

        # Set modern dark styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TNotebook",
            background="#1e1e2e",
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background="#181825",
            foreground="#cdd6f4",
            padding=[12, 6],
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#313244")],
            foreground=[("selected", "#89b4fa")],
        )
        style.configure(
            "TFrame",
            background="#1e1e2e",
        )
        style.configure(
            "TLabel",
            background="#1e1e2e",
            foreground="#cdd6f4",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Header.TLabel",
            background="#1e1e2e",
            foreground="#89b4fa",
            font=("Segoe UI", 11, "bold"),
        )

        # Tab Notebook
        notebook = ttk.Notebook(self.win)
        notebook.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        # Build Tabs
        self._build_audio_tab(notebook)
        self._build_whisper_tab(notebook)
        self._build_ai_tab(notebook)
        self._build_modes_tab(notebook)
        self._build_hotkeys_tab(notebook)

        # Bottom Action Bar
        bottom_bar = tk.Frame(self.win, bg="#181825", height=48)
        bottom_bar.pack(fill="x", side="bottom", padx=0, pady=0)

        status_lbl = tk.Label(
            bottom_bar,
            text="Settings saved to ~/.localwhisper/settings.json",
            bg="#181825",
            fg="#6c7086",
            font=("Segoe UI", 8),
        )
        status_lbl.pack(side="left", padx=12, pady=10)

        save_btn = tk.Button(
            bottom_bar,
            text="Save & Apply",
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            activeforeground="#11111b",
            font=("Segoe UI Semibold", 9),
            padx=16,
            pady=4,
            relief="flat",
            command=self._save_all,
        )
        save_btn.pack(side="right", padx=12, pady=8)

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Tab 1: Audio & Microphone ─────────────────────────────────

    def _build_audio_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🎙️ Microphone")

        content = tk.Frame(frame, bg="#1e1e2e", padx=16, pady=16)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Microphone Device", style="Header.TLabel").pack(anchor="w", pady=(0, 4))

        # Device selection row with Combobox and Refresh button
        dev_row = tk.Frame(content, bg="#1e1e2e")
        dev_row.pack(fill="x", pady=(0, 2))

        self.mic_var = tk.StringVar()
        self.mic_combo = ttk.Combobox(dev_row, textvariable=self.mic_var, state="readonly", width=46)
        self.mic_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.refresh_btn = tk.Button(
            dev_row,
            text="🔄 Refresh",
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            padx=10,
            pady=2,
            relief="flat",
            command=self._on_refresh_devices,
        )
        self.refresh_btn.pack(side="right")

        self.mic_status_lbl = tk.Label(
            content,
            text="",
            bg="#1e1e2e",
            fg="#a6adc8",
            font=("Segoe UI", 8),
        )
        self.mic_status_lbl.pack(anchor="w", pady=(0, 12))

        # Live Volume Meter Test setup first so test_btn exists before _refresh_devices
        ttk.Label(content, text="Microphone Volume Test", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        meter_frame = tk.Frame(content, bg="#181825", padx=8, pady=8)
        meter_frame.pack(fill="x", pady=(0, 16))

        self.meter_canvas = tk.Canvas(meter_frame, bg="#11111b", height=14, highlightthickness=0)
        self.meter_canvas.pack(fill="x", side="left", expand=True, padx=(0, 8))

        self.test_btn = tk.Button(
            meter_frame, text="Test Mic", bg="#313244", fg="#cdd6f4",
            activebackground="#45475a", font=("Segoe UI", 8),
            command=self._toggle_mic_test,
        )
        self.test_btn.pack(side="right")

        # Populate devices
        self._refresh_devices(force=False)

        # Recording Mode
        ttk.Label(content, text="Recording Trigger Mode", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.rec_mode_var = tk.StringVar(value=config.get("recording_mode", "push_to_talk"))

        r1 = tk.Radiobutton(
            content, text="Push-to-Talk (Hold Hotkey to Speak, Release to Paste)",
            variable=self.rec_mode_var, value="push_to_talk",
            bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", activebackground="#1e1e2e", font=("Segoe UI", 9),
        )
        r1.pack(anchor="w", pady=2)

        r2 = tk.Radiobutton(
            content, text="Toggle Mode (Press Hotkey once to Start, Press again to Stop)",
            variable=self.rec_mode_var, value="toggle",
            bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", activebackground="#1e1e2e", font=("Segoe UI", 9),
        )
        r2.pack(anchor="w", pady=2)

        r3 = tk.Radiobutton(
            content, text="Hands-Free VAD (Start with Hotkey, Auto-stops after silence)",
            variable=self.rec_mode_var, value="vad",
            bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", activebackground="#1e1e2e", font=("Segoe UI", 9),
        )
        r3.pack(anchor="w", pady=(2, 16))

    def _on_refresh_devices(self) -> None:
        """Handle Refresh Devices button click."""
        self._refresh_devices(force=True)

    def _refresh_devices(self, force: bool = False) -> None:
        """Enumerate audio devices, update combobox, and select appropriate device."""
        devices = AudioEngine.list_input_devices(force_refresh=force)
        self._device_map = {}
        labels: List[str] = []

        if not devices:
            no_mic_msg = "⚠️ No Microphone Detected"
            self.mic_combo["values"] = [no_mic_msg]
            self.mic_var.set(no_mic_msg)
            if hasattr(self, "mic_status_lbl"):
                self.mic_status_lbl.config(
                    text="⚠️ No input devices found. Connect a microphone and click Refresh.",
                    fg="#ff5555",
                )
            if hasattr(self, "test_btn"):
                self.test_btn.config(state="disabled")
            return

        if hasattr(self, "test_btn"):
            self.test_btn.config(state="normal")

        curr_saved_id = config.get("mic_device_id", None)
        selected_label = None
        default_label = None

        for d in devices:
            star = "⭐ " if d.get("is_default") else "   "
            label = f"{star}[{d['id']}] {d['name']}"
            labels.append(label)
            self._device_map[label] = d

            if d.get("is_default"):
                default_label = label

            if curr_saved_id is not None and d["id"] == curr_saved_id:
                selected_label = label

        self.mic_combo["values"] = labels

        # Select saved device, or default device, or first item
        target_label = selected_label or default_label or (labels[0] if labels else "")
        self.mic_var.set(target_label)
        if hasattr(self, "mic_status_lbl"):
            self.mic_status_lbl.config(
                text=f"✓ Found {len(devices)} input device(s). ⭐ = Default Device",
                fg="#52b788",
            )

    # ── Tab 2: Whisper Engine ─────────────────────────────────────

    def _build_whisper_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="⚡ Whisper Model")

        content = tk.Frame(frame, bg="#1e1e2e", padx=16, pady=16)
        content.pack(fill="both", expand=True)

        # Model Selector
        ttk.Label(content, text="Whisper Model (Size & Speed)", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        model_labels = [label for _, label in WHISPER_MODEL_OPTIONS]
        curr_model = config.get("whisper_model", "medium")
        initial_model_label = MODEL_ID_TO_LABEL.get(curr_model, MODEL_ID_TO_LABEL.get("medium", "medium (769M) — Accurate"))

        self.model_var = tk.StringVar(value=initial_model_label)
        model_combo = ttk.Combobox(content, textvariable=self.model_var, values=model_labels, state="readonly", width=42)
        model_combo.pack(anchor="w", pady=(0, 8))

        # Hardware Recommendation Box
        note_frame = tk.Frame(content, bg="#181825", padx=10, pady=8)
        note_frame.pack(fill="x", pady=(0, 12))

        note_text = (
            "💡 Hardware Recommendation:\n"
            "• GPU (CUDA float16): Recommended for 'medium', 'large-v3', and 'distil-large-v3' (requires 4GB–8GB VRAM).\n"
            "• CPU (int8): Best paired with 'tiny', 'base', or 'small' for low latency and zero stutter."
        )
        tk.Label(
            note_frame,
            text=note_text,
            bg="#181825",
            fg="#a6adc8",
            font=("Segoe UI", 8),
            justify="left",
            anchor="w",
        ).pack(fill="x")

        # Device & Compute
        ttk.Label(content, text="Acceleration Device", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        dev_frame = tk.Frame(content, bg="#1e1e2e")
        dev_frame.pack(anchor="w", pady=(0, 12))

        self.whisper_dev_var = tk.StringVar(value=config.get("whisper_device", "cuda"))
        tk.Radiobutton(
            dev_frame, text="GPU (CUDA float16)", variable=self.whisper_dev_var, value="cuda",
            bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 12))
        tk.Radiobutton(
            dev_frame, text="CPU (int8)", variable=self.whisper_dev_var, value="cpu",
            bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Segoe UI", 9),
        ).pack(side="left")

        # Language
        ttk.Label(content, text="Speech Language", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        lang_labels = [label for _, label in WHISPER_LANG_OPTIONS]
        curr_lang = config.get("whisper_language", None)
        initial_lang_label = LANG_CODE_TO_LABEL.get(curr_lang, "Auto-detect (English/Hindi)")

        self.lang_var = tk.StringVar(value=initial_lang_label)
        lang_combo = ttk.Combobox(content, textvariable=self.lang_var, values=lang_labels, state="readonly", width=36)
        lang_combo.pack(anchor="w", pady=(0, 12))

        # Initial Prompt (Vocabulary / Slang / Code-switching)
        ttk.Label(content, text="Initial Prompt (Custom vocabulary / names / Hinglish guide)", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.init_prompt_txt = tk.Text(content, height=3, bg="#181825", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Segoe UI", 9))
        self.init_prompt_txt.pack(fill="x", pady=(0, 4))
        self.init_prompt_txt.insert("1.0", config.get("whisper_initial_prompt", ""))

    # ── Tab 3: AI Refiner & Providers ─────────────────────────────

    def _build_ai_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🧠 AI Refiners")

        content = tk.Frame(frame, bg="#1e1e2e", padx=16, pady=16)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="AI Backend Provider", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        
        self.ai_backend_var = tk.StringVar(value=config.get("ai_backend", "ollama"))
        backends = [
            ("ollama", "Local Ollama (100% Offline & Private)"),
            ("groq", "Groq Cloud (Free Ultra-Fast 500+ tokens/sec)"),
            ("openai", "OpenAI / OpenRouter API"),
            ("gemini", "Google Gemini API"),
            ("none", "None (Direct Fast Whisper Paste)"),
        ]
        for val, label in backends:
            tk.Radiobutton(
                content, text=label, variable=self.ai_backend_var, value=val,
                bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Segoe UI", 9),
            ).pack(anchor="w", pady=1)

        # Ollama Model & URL
        ollama_frame = tk.LabelFrame(content, text="Ollama Settings", bg="#1e1e2e", fg="#89b4fa", padx=8, pady=6)
        ollama_frame.pack(fill="x", pady=(8, 4))

        tk.Label(ollama_frame, text="Model:", bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.ollama_model_var = tk.StringVar(value=config.get("ollama_model", "qwen3:8b"))
        ollama_models = ["qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "llama3.1:8b", "phi3:mini", "gemma2:2b", "gemma2:9b", "qwen3:8b"]
        ttk.Combobox(ollama_frame, textvariable=self.ollama_model_var, values=ollama_models, width=22).grid(row=0, column=1, padx=6, sticky="w")

        # Groq API Key
        groq_frame = tk.LabelFrame(content, text="Cloud API Keys", bg="#1e1e2e", fg="#89b4fa", padx=8, pady=6)
        groq_frame.pack(fill="x", pady=(6, 8))

        tk.Label(groq_frame, text="Groq Key:", bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.groq_key_var = tk.StringVar(value=config.get("groq_api_key", ""))
        tk.Entry(groq_frame, textvariable=self.groq_key_var, show="•", bg="#181825", fg="#cdd6f4", width=36).grid(row=0, column=1, padx=6, pady=2, sticky="w")

        tk.Label(groq_frame, text="OpenAI Key:", bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        self.openai_key_var = tk.StringVar(value=config.get("openai_api_key", ""))
        tk.Entry(groq_frame, textvariable=self.openai_key_var, show="•", bg="#181825", fg="#cdd6f4", width=36).grid(row=1, column=1, padx=6, pady=2, sticky="w")

        # Test Backend Button
        test_frame = tk.Frame(content, bg="#1e1e2e")
        test_frame.pack(fill="x", pady=4)

        self.backend_status_lbl = tk.Label(test_frame, text="Status: Ready to test", bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI", 9))
        self.backend_status_lbl.pack(side="left")

        tk.Button(
            test_frame, text="Test Connection", bg="#313244", fg="#cdd6f4",
            activebackground="#45475a", font=("Segoe UI", 8),
            command=self._test_backend_connection,
        ).pack(side="right")

    # ── Tab 4: Dictation Modes Editor ─────────────────────────────

    def _build_modes_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="✍️ Mode Prompts")

        content = tk.Frame(frame, bg="#1e1e2e", padx=16, pady=16)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Select Mode to Edit", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        
        modes = config.all_modes
        mode_keys = list(modes.keys())
        self.selected_mode_key = tk.StringVar(value=config.get("current_mode", "smart"))

        mode_picker = ttk.Combobox(
            content, textvariable=self.selected_mode_key,
            values=[f"{k} — {modes[k].get('name', k)}" for k in mode_keys],
            state="readonly", width=40,
        )
        mode_picker.pack(anchor="w", pady=(0, 8))
        mode_picker.bind("<<ComboboxSelected>>", self._on_mode_selected_in_editor)

        ttk.Label(content, text="System Prompt for Mode:", style="Header.TLabel").pack(anchor="w", pady=(4, 2))
        self.mode_prompt_txt = tk.Text(content, height=10, bg="#181825", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Segoe UI", 9))
        self.mode_prompt_txt.pack(fill="both", expand=True, pady=(0, 8))

        # Populate prompt text
        curr_key = self.selected_mode_key.get().split(" — ")[0].strip()
        self.mode_prompt_txt.insert("1.0", modes.get(curr_key, {}).get("prompt", ""))

    def _on_mode_selected_in_editor(self, event=None) -> None:
        raw = self.selected_mode_key.get()
        key = raw.split(" — ")[0].strip() if " — " in raw else raw.strip()
        modes = config.all_modes
        self.mode_prompt_txt.delete("1.0", "end")
        self.mode_prompt_txt.insert("1.0", modes.get(key, {}).get("prompt", ""))

    # ── Tab 5: Hotkeys & Typing ───────────────────────────────────

    def _build_hotkeys_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="⌨️ Hotkey & Paste")

        content = tk.Frame(frame, bg="#1e1e2e", padx=16, pady=16)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Global Dictation Hotkey", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.hotkey_var = tk.StringVar(value=config.get("hotkey", "ctrl+space"))
        tk.Entry(content, textvariable=self.hotkey_var, bg="#181825", fg="#cdd6f4", font=("Segoe UI", 10), width=24).pack(anchor="w", pady=(0, 16))



        # Checkboxes
        ttk.Label(content, text="Preferences", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.sound_var = tk.BooleanVar(value=config.get("sound_effects", True))
        tk.Checkbutton(
            content, text="Play audio chimes on recording start & stop",
            variable=self.sound_var, bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Segoe UI", 9),
        ).pack(anchor="w", pady=2)

        self.space_var = tk.BooleanVar(value=config.get("add_trailing_space", True))
        tk.Checkbutton(
            content, text="Add trailing space after pasted text",
            variable=self.space_var, bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244", font=("Segoe UI", 9),
        ).pack(anchor="w", pady=2)

    # ── Actions & Helpers ─────────────────────────────────────────

    def _get_selected_device(self) -> Tuple[Optional[int], str]:
        """Safely extract device ID and name from current selection."""
        cur_val = self.mic_var.get().strip()
        if hasattr(self, "_device_map") and cur_val in self._device_map:
            d = self._device_map[cur_val]
            return d["id"], d["name"]

        # Regex fallback: extract integer inside brackets [id] or before colon id:
        m = re.search(r'\[(\d+)\]', cur_val) or re.search(r'(\d+):', cur_val)
        if m:
            dev_id = int(m.group(1))
            name = cur_val.split("]", 1)[-1].strip() if "]" in cur_val else cur_val
            return dev_id, name

        return None, "Default Microphone"

    def _toggle_mic_test(self) -> None:
        if self._test_active:
            self._test_active = False
            self.test_btn.config(text="Test Mic", bg="#313244")
            self.meter_canvas.delete("all")
        else:
            self._test_active = True
            self.test_btn.config(text="Stop Test", bg="#ff5555")
            dev_id, _ = self._get_selected_device()
            threading.Thread(target=self._run_mic_test, args=(dev_id,), daemon=True).start()

    def _run_mic_test(self, dev_id: Optional[int]) -> None:
        import sounddevice as sd
        import numpy as np

        def _cb(indata, frames, time_info, status):
            if not self._test_active:
                return
            rms = float(np.sqrt(np.mean(indata**2)))
            level = min(1.0, rms * 15.0)
            if self.win and self.win.winfo_exists():
                self.win.after(0, self._draw_meter, level)

        try:
            with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=800, device=dev_id, callback=_cb):
                while self._test_active:
                    time.sleep(0.05)
        except Exception as e:
            print(f"[Settings] Mic test failed: {e}")
            self._test_active = False
            if self.win and self.win.winfo_exists():
                self.win.after(0, self._on_mic_test_failed, str(e))

    def _on_mic_test_failed(self, err_msg: str) -> None:
        if hasattr(self, "test_btn") and self.test_btn.winfo_exists():
            self.test_btn.config(text="Test Mic", bg="#313244")
        if hasattr(self, "meter_canvas") and self.meter_canvas.winfo_exists():
            self.meter_canvas.delete("all")
        if hasattr(self, "mic_status_lbl") and self.mic_status_lbl.winfo_exists():
            self.mic_status_lbl.config(
                text=f"⚠️ Mic test error: {err_msg}",
                fg="#ff5555",
            )

    def _draw_meter(self, level: float) -> None:
        if not self.win or not self.win.winfo_exists():
            return
        self.meter_canvas.delete("all")
        w = self.meter_canvas.winfo_width()
        fill_w = int(w * level)
        color = "#52b788" if level < 0.7 else "#ffb703" if level < 0.9 else "#ff5555"
        self.meter_canvas.create_rectangle(0, 0, fill_w, 14, fill=color, outline="")

    def _test_backend_connection(self) -> None:
        self.backend_status_lbl.config(text="Checking backend...", fg="#ffb703")

        def _worker():
            ok, msg = ai_refiner.check_backend_status()
            color = "#52b788" if ok else "#ff5555"
            if self.win and self.win.winfo_exists():
                self.win.after(0, lambda: self.backend_status_lbl.config(text=f"Status: {msg}", fg=color))

        threading.Thread(target=_worker, daemon=True).start()

    def _save_all(self) -> None:
        # Mic Device
        dev_id, dev_name = self._get_selected_device()
        config.set("mic_device_id", dev_id)
        config.set("mic_device_name", dev_name)

        # Recording Mode
        config.set("recording_mode", self.rec_mode_var.get())

        # Whisper Settings
        raw_model_val = self.model_var.get().strip()
        saved_model_id = MODEL_LABEL_TO_ID.get(raw_model_val, raw_model_val.split(" ")[0].strip())
        config.set("whisper_model", saved_model_id)

        config.set("whisper_device", self.whisper_dev_var.get())
        config.set("whisper_compute_type", "float16" if self.whisper_dev_var.get() == "cuda" else "int8")

        # Language mapping: None, "en", "hi"
        raw_lang = self.lang_var.get().strip()
        saved_lang = LANG_LABEL_TO_CODE.get(raw_lang, None if "Auto-detect" in raw_lang else raw_lang.split(" ")[0].strip())
        config.set("whisper_language", saved_lang)

        config.set("whisper_initial_prompt", self.init_prompt_txt.get("1.0", "end").strip())

        # AI Backend
        config.set("ai_backend", self.ai_backend_var.get())
        config.set("ollama_model", self.ollama_model_var.get().strip())
        config.set("groq_api_key", self.groq_key_var.get().strip())
        config.set("openai_api_key", self.openai_key_var.get().strip())

        # Mode prompt edit
        raw_mode = self.selected_mode_key.get()
        key = raw_mode.split(" — ")[0].strip() if " — " in raw_mode else raw_mode.strip()
        modes = config.all_modes
        if key in modes:
            modes[key]["prompt"] = self.mode_prompt_txt.get("1.0", "end").strip()
            config.set("dictation_modes", modes)

        # Hotkeys & Preferences
        config.set("hotkey", self.hotkey_var.get().strip().lower())

        config.set("sound_effects", self.sound_var.get())
        config.set("add_trailing_space", self.space_var.get())

        config.save()
        messagebox.showinfo("LocalWhisper Pro", "Settings applied successfully!")

        if self.on_settings_changed:
            self.on_settings_changed()

    def _on_close(self) -> None:
        self._test_active = False
        if self.win:
            self.win.destroy()
            self.win = None
