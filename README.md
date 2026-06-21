# 🎙️ LocalWhisper v2.0 — Voice-to-Text, Locally

> Press **Ctrl+Space**, speak, release — text appears at your cursor. No cloud, no API keys, 100% local.

LocalWhisper is a lightweight, privacy-first voice typing tool for Windows. It uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for real-time speech recognition and optionally [Ollama](https://ollama.com/) for AI-powered text cleanup — all running locally on your machine.

---

## ✨ What's New in v2.0

| Feature | Description |
|---------|-------------|
| 🔧 **Crash-Free Startup** | No more first-run errors — CUDA DLL preloading with retry logic |
| ⚡ **Faster Loading** | Warm-up caching skips redundant model initialization (saves ~3-5s) |
| 🔄 **Parallel Init** | Whisper + Ollama load simultaneously instead of sequentially |
| 🖥️ **System Tray** | Minimize to tray — app runs in background, hotkey still works |
| 🌐 **Universal Command** | Type `localwhisper` from any terminal, anywhere |
| 📦 **One-Click Install** | Run `install.bat` once — you're set forever |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** with pip
- **Windows 10/11**
- **CUDA Toolkit 12.x** (optional, for GPU acceleration — falls back to CPU automatically)
- **Ollama** (optional, for text cleanup — works without it)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/punit732007-ai/Wisper_Flow_clone_localy_on_system.git
cd Wisper_Flow_clone_localy_on_system

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install universal command (one-time)
install.bat
```

### Usage

**Option 1 — Universal command** (after running `install.bat`):
```bash
# From ANY terminal, anywhere:
localwhisper
```

**Option 2 — Direct run:**
```bash
# From the project folder:
.\run.bat
```

---

## 🎯 How It Works

1. **Press & hold** `Ctrl+Space` → recording starts (button turns red)
2. **Speak** naturally in English, Hindi, or Hinglish
3. **Release** `Ctrl+Space` → processing begins (button turns orange)
4. Text is **automatically pasted** at your cursor position

### System Tray
- **Right-click** the floating button → "Minimize to Tray"
- App continues running in background — **hotkey still works!**
- Click the **green tray icon** → "Show/Hide" to restore the button

---

## 📁 Project Structure

```
localwisper/
├── main.py            # Entry point — orchestrates the pipeline
├── config.py          # All settings — device detection, model config
├── transcriber.py     # Whisper model loading + transcription
├── llm_refiner.py     # Ollama LLM post-processing
├── audio_capture.py   # Microphone recording with sounddevice
├── floating_ui.py     # Floating button UI + system tray
├── paster.py          # Clipboard paste at cursor
├── run.bat            # Quick launcher (from project dir)
├── install.bat        # Universal command installer
├── requirements.txt   # Python dependencies
└── .gitignore
```

---

## ⚙️ Configuration

All settings are in [`config.py`](config.py):

| Setting | Default | Description |
|---------|---------|-------------|
| `WHISPER_MODEL_SIZE` | `medium` (GPU) / `small` (CPU) | Whisper model size |
| `WHISPER_LANGUAGE` | `None` (auto-detect) | Force a specific language |
| `OLLAMA_MODEL` | `qwen3:8b` | Ollama model for text cleanup |
| `GLOBAL_HOTKEY` | `ctrl+space` | Push-to-talk hotkey |
| `WARMUP_CACHE_MAX_AGE` | `86400` (24h) | How long to cache warm-up |

---

## 🛠️ Tech Stack

- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** — CTranslate2 backend for fast inference
- **[Ollama](https://ollama.com/)** — Local LLM for transcription cleanup
- **[sounddevice](https://python-sounddevice.readthedocs.io/)** — Low-latency audio capture
- **[pystray](https://github.com/moses-palmer/pystray)** — System tray icon
- **[tkinter](https://docs.python.org/3/library/tkinter.html)** — Floating UI with animated states

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| **v2.0** | June 2026 | Crash-free startup, warm-up caching, parallel init, system tray, universal command |
| **v1.0** | June 2026 | Initial release — Whisper + Ollama + floating UI + push-to-talk |

---

## 📄 License

This project is for personal use. Feel free to fork and modify!

---

*Built with ❤️ by Punit*
