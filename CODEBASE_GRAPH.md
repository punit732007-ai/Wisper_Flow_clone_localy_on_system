# 🗺️ LocalWhisper — Codebase Graph

> **Quick Re-orientation File** — Read this first before touching any code.  
> Last updated: 2026-06-20

---

## 📌 Project Summary

**LocalWhisper** is a fully local, privacy-first **voice-to-text tool** for Windows.  
It captures microphone audio → transcribes with Whisper → refines with Ollama LLM → pastes at cursor.  
Language focus: **Hindi (Devanagari) + English + Hinglish** for user "Punit".

**Run with:** `run.bat` (auto-activates venv) or `python main.py` (if venv already active)  
**Hotkey:** `Ctrl+Space` to toggle recording from any application  

---

## 🏗️ Architecture — Data Flow

```
[Microphone]
     │  sounddevice InputStream (16kHz, float32, mono)
     ▼
[AudioCapture]  ──────────── audio_capture.py
     │  np.ndarray (1-D float32 samples)
     ▼
[Transcriber]   ──────────── transcriber.py
      │  faster-whisper (CTranslate2 backend)
      │  Model: auto ("small" CPU / "medium" GPU), auto-detect language
     │  Returns: (raw_text: str, language: str)
     ▼
[LLMRefiner]    ──────────── llm_refiner.py
     │  Ollama HTTP API → qwen3:8b
      │  Fixes misheard words, keeps same language
     │  Falls back to raw_text if Ollama unavailable
     │  Returns: refined_text: str
     ▼
[Paster]        ──────────── paster.py
     │  pyperclip.copy() → pyautogui.hotkey("ctrl","v")
     │  Restores original clipboard after 0.4s
     ▼
[Any Focused App — Notepad / Chrome / VS Code / etc.]
```

**UI runs in parallel (main thread):**
```
[FloatingUI]  ─── floating_ui.py
     │  tkinter pill-shaped window, always-on-top
     │  WS_EX_NOACTIVATE (never steals focus!)
     │  States: loading → ready → recording → processing
     │  Draggable, right-click → Quit
     │  Calls: on_toggle() / on_quit() callbacks
```

---

## 📁 File-by-File Reference

### [`main.py`](file:///d:/localwisper/main.py) — Orchestrator / Entry Point
| Item | Detail |
|---|---|
| Class | `LocalWhisper` |
| Role | Wires all modules together; owns the pipeline |
| Key methods | `start()`, `_load_models()`, `_ptt_pressed()`, `_ptt_released()`, `_toggle_recording()`, `_start_recording()`, `_stop_and_process()`, `_process_audio()`, `_shutdown()` |
| Threading | Model loading → background thread. Audio processing → background thread. UI → main thread only. |
| Hotkey | `keyboard.add_hotkey(GLOBAL_HOTKEY)` → PTT (push-to-talk) model |
| PTT logic | `_ptt_pressed()` starts recording on key-down; `_ptt_released()` stops on physical key-up (avoids auto-repeat issues) |
| Important note | **`transcriber` MUST be imported first** (monkey-patches broken `av` module before anything else) |

---

### [`config.py`](file:///d:/localwisper/config.py) — All Tunable Constants
| Constant | Value | Notes |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `"small"` (CPU) / `"medium"` (GPU) | Auto-selected based on device |
| `WHISPER_DEVICE` | Auto-detected | `_detect_device()` tries CUDA first, falls back to CPU |
| `WHISPER_COMPUTE_TYPE` | `"float16"` (GPU) / `"int8"` (CPU) | Auto-selected |
| `WHISPER_BEAM_SIZE` | `1` (CPU) / `3` (GPU) | Greedy decoding on CPU for speed |
| `WHISPER_VAD_FILTER` | `True` | Silero VAD skips silent segments |
| `WHISPER_LANGUAGE` | `None` | Auto-detect language (Hindi, English, Hinglish) |
| `WHISPER_INITIAL_PROMPT` | Bilingual (English + Hindi) | Helps Whisper handle code-switching |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server |
| `OLLAMA_MODEL` | `"qwen3:8b"` | LLM for refinement |
| `OLLAMA_TIMEOUT` | `30s` | Reduced for faster fallback |
| `REFINEMENT_SYSTEM_PROMPT` | See file | Multilingual: keeps same language, no translation |
| `AUDIO_SAMPLE_RATE` | `16000` | Whisper requirement |
| `SILENCE_THRESHOLD` | `0.015` | RMS below = silence |
| `SILENCE_DURATION` | `1.8s` | Auto-stop after this silence |
| `MIN_RECORDING_DURATION` | `0.5s` | Too-short recordings are discarded |
| `GLOBAL_HOTKEY` | `"ctrl+space"` | Change here if conflicts arise |
| `BUTTON_WIDTH/HEIGHT` | `164 × 50` px | Pill button dimensions |
| `TRANSPARENT_COLOR` | `"#f0abcd"` | Unlikely pink used for window transparency trick |
| `ANIMATION_FPS` | `30` | UI animation frame rate |

---

### [`audio_capture.py`](file:///d:/localwisper/audio_capture.py) — Microphone Recording
| Item | Detail |
|---|---|
| Class | `AudioCapture` |
| Backend | `sounddevice.InputStream` |
| Key methods | `start(on_silence_stop=None)` — opens stream; `stop()` → returns `np.ndarray` |
| Property | `is_recording: bool` |
| Buffer | List of `np.ndarray` chunks, protected by `threading.Lock` |
| Silence detection | Hook exists (`on_silence_stop` param) but **currently unused** — PTT (push-to-talk) handles stop |
| Audio format | `float32`, mono, 16kHz, 100ms blocks |

---

### [`transcriber.py`](file:///d:/localwisper/transcriber.py) — Whisper STT
| Item | Detail |
|---|---|
| Class | `Transcriber` |
| Backend | `faster-whisper` (CTranslate2) |
| Critical hack | **Top of file monkey-patches `av` module** with fake stubs to prevent import errors (PyAV is broken/missing). This is why `transcriber` must be imported first in `main.py`. |
| `load_model()` | Loads WhisperModel; if CUDA → runs warm-up dummy transcription; auto-falls back to CPU on cuBLAS failure |
| `transcribe(audio)` | Returns `(full_text: str, detected_lang: str)`; consumes generator inside try/except for CUDA crash safety |
| Property | `is_loaded: bool` |
| GPU fallback | On-the-fly fallback: if cuBLAS crashes mid-transcription, re-creates model on CPU and retries |

---

### [`llm_refiner.py`](file:///d:/localwisper/llm_refiner.py) — Ollama LLM Post-Processor
| Item | Detail |
|---|---|
| Class | `LLMRefiner` |
| Endpoint | `POST http://localhost:11434/api/chat` (non-streaming) |
| `check_availability()` | GETs `/api/tags`, checks if `qwen3:8b` is in the list |
| `refine(raw_text, lang)` | Sends system prompt + raw text; strips `<think>…</think>` from qwen3 output |
| Fallback | Returns `raw_text` unchanged if Ollama unavailable, timeout, or non-200 |
| Settings | `temperature=0.1`, `num_predict=512` |
| `/no_think` | Appended to user prompt to suppress qwen3 reasoning blocks |

---

### [`floating_ui.py`](file:///d:/localwisper/floating_ui.py) — Always-On-Top Pill Button
| Item | Detail |
|---|---|
| Class | `FloatingUI` |
| Backend | `tkinter` + Windows API (`ctypes`) |
| Key trick | `WS_EX_NOACTIVATE` + `WS_EX_TOOLWINDOW` flags → clicking button **never steals focus** from target app |
| Position | Bottom-left, above taskbar (`SPI_GETWORKAREA`) |
| States | `loading` (blue pulse), `ready` (green dot, no pulse), `recording` (red pulse fast), `processing` (orange pulse) |
| Animation | `_tick()` — sine-wave driven color lerp at 30 FPS via `root.after()` |
| Drag | `<ButtonPress>` + `<B1-Motion>` + `<ButtonRelease>` — distinguishes drag (>4px) from click |
| Thread safety | `schedule(func, *args)` → `root.after(0, func, *args)` to run on main thread |
| Context menu | Right-click → "Quit" |
| Key methods | `set_state(state)`, `schedule(func, *args)`, `run()` |

---

### [`paster.py`](file:///d:/localwisper/paster.py) — Paste at Cursor
| Item | Detail |
|---|---|
| Function | `paste_at_cursor(text: str)` |
| Mechanism | `pyperclip.copy(text)` → 40ms sleep → `pyautogui.hotkey("ctrl", "v")` |
| Clipboard restore | Saves old clipboard, restores it after 0.4s in daemon thread |
| Safety flags | `pyautogui.FAILSAFE = False`, `pyautogui.PAUSE = 0.03` |

---

## 🔗 Module Dependency Graph

```
main.py
  ├── transcriber.py   (imported FIRST — monkey-patches av)
  │     ├── faster_whisper
  │     └── config.py
  ├── config.py        (no local deps — standalone)
  ├── audio_capture.py
  │     ├── sounddevice
  │     ├── numpy
  │     └── config.py
  ├── llm_refiner.py
  │     ├── requests
  │     └── config.py
  ├── paster.py
  │     ├── pyperclip
  │     └── pyautogui
  └── floating_ui.py
        ├── tkinter (stdlib)
        ├── ctypes  (stdlib)
        └── config.py
```

---

## 📦 Dependencies (`requirements.txt`)

| Package | Purpose |
|---|---|
| `faster-whisper >= 1.1.0` | Core STT — Whisper via CTranslate2 |
| `sounddevice >= 0.5.0` | Microphone capture |
| `numpy >= 1.26.0` | Audio buffer manipulation |
| `pyautogui >= 0.9.54` | Simulate Ctrl+V keypress |
| `pyperclip >= 1.9.0` | Cross-platform clipboard |
| `requests >= 2.32.0` | HTTP calls to Ollama API |
| `keyboard >= 0.13.5` | Global hotkey registration |
| `ctranslate2` | (transitive via faster-whisper) — used in config.py for device detection |

**NOT in requirements but needed:**
- `ollama` server running locally (`ollama serve` + `ollama pull qwen3:8b`)
- Python `tkinter` (stdlib, included with Python on Windows)

---

## 🔄 State Machine (UI States)

```
        ┌─────────────────────────────────────────┐
        │              loading                    │  (startup, model loading)
        │           [blue pulse]                  │
        └──────────────┬──────────────────────────┘
                       │ model loaded OK
                       ▼
        ┌─────────────────────────────────────────┐
   ┌──► │               ready                     │  (idle, waiting for input)
   │    │           [green dot]                   │
   │    └──────────────┬──────────────────────────┘
   │                   │ Ctrl+Space / click
   │                   ▼
   │    ┌─────────────────────────────────────────┐
   │    │            recording                    │  (mic active)
   │    │           [red fast pulse]              │
   │    └──────────────┬──────────────────────────┘
   │                   │ Ctrl+Space / click / silence
   │                   ▼
   │    ┌─────────────────────────────────────────┐
   └────│           processing                    │  (transcribe + refine + paste)
        │         [orange pulse]                  │
        └─────────────────────────────────────────┘
```

---

## ⚠️ Known Design Decisions & Gotchas

| # | Gotcha | Detail |
|---|---|---|
| 1 | **`av` monkey-patch** | `transcriber.py` must be the FIRST import in `main.py`. It stubs out PyAV (broken on this system). Never reorder imports in `main.py`. |
| 2 | **Auto CUDA detection** | `config._detect_device()` tries CUDA first via `ctranslate2.get_supported_compute_types()`, falls back to CPU. Model size and beam size auto-adjust per device. |
| 3 | **PTT not VAD** | `AudioCapture` has an `on_silence_stop` hook but it's NOT wired up. Stop is triggered by key release only. |
| 4 | **`WS_EX_NOACTIVATE` is critical** | Without it, clicking the pill button would steal focus and paste into the wrong window. Don't remove the ctypes window style hack. |
| 5 | **Auto language detect** | `WHISPER_LANGUAGE = None` — Whisper auto-detects Hindi/English/Hinglish. Bilingual initial prompt helps. |
| 6 | **`/no_think`** | Appended to every Ollama prompt to suppress qwen3's reasoning mode. qwen3 still sometimes emits `<think>` tags — regex strips them in `llm_refiner.py`. |
| 7 | **Clipboard restore** | `paster.py` backs up and restores the clipboard. This breaks for image/binary clipboard content (only text survives). |
| 8 | **`run.bat`** | One-click launcher that auto-activates venv. Use this instead of manually typing two commands. |

---

## 🚀 Quick Start Checklist

```bash
# Option A: One-click (recommended)
.\run.bat

# Option B: Manual
.\venv\Scripts\activate
python main.py

# Optional: Start Ollama for LLM refinement
ollama serve          # in a separate terminal
ollama pull qwen3:8b  # first time only
```

---

## 🐛 Troubleshooting Quick Reference

| Symptom | Fix |
|---|---|
| Whisper model fails to load | Already on CPU — check `venv` is active and `faster-whisper` installed |
| `Ctrl+Space` not working | Run `main.py` as Administrator |
| Ollama timeout | Increase `OLLAMA_TIMEOUT` in `config.py` or ensure `ollama serve` is running |
| No audio captured | Check default mic in Windows Sound Settings |
| Output is English instead of Hindi | Verify `WHISPER_LANGUAGE = "hi"` in `config.py` |
| `<think>` tags in output | Already handled by regex in `llm_refiner.py` — check if model changed |

---

*This file is the single source of truth for re-orienting to this codebase. Update it whenever major changes are made.*
