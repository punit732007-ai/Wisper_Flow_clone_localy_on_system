<div align="center">
  <h1>🎙️ LocalWhisper Pro</h1>
  <p><b>An ultra-fast, locally-run AI Dictation Assistant with a Glassmorphic HUD and Multi-Mode AI Refiner.</b></p>
</div>

---

## 📖 Overview

**LocalWhisper Pro** is an advanced desktop speech-to-text application designed for developers, executives, and power users. It sits quietly in your system tray and overlays a beautiful, non-intrusive floating HUD on your screen. 

Using **faster-whisper** for lightning-fast local transcription and a powerful **multi-backend AI Refiner** (Ollama, Groq, OpenAI, Gemini), it accurately captures your speech, cleans it up perfectly according to your context, and types it directly into whatever app you are using—without polluting your clipboard history.

### ✨ Key Features

- **Glassmorphic Floating HUD**: A gorgeous, non-focus-stealing widget that features a real-time audio visualizer to let you know it's listening.
- **Multi-Mode AI Processing**: Switch instantly between modes to suit your workflow:
  - ✍️ **Smart Dictation**: Cleans up stutters and filler words while preserving your natural tone.
  - ⚡ **Direct Raw**: Instant, zero-latency transcription with no AI modification.
  - 💼 **Professional Email**: Transforms casual voice notes into crisp, executive business language.
  - 💻 **Code & Tech**: Formats spoken technical terms into proper code syntax (camelCase, snake_case, terminal commands).
  - 🌐 **Translate to English**: Flawlessly translates spoken Hindi/Hinglish directly into fluent English.
  - 📝 **Bullet Summary**: Condenses rambling voice notes into sharp, actionable bullet points.
- **Robust Typing Engine**: Uses direct hardware-level typing (`pynput` / `SendInput`) to type text directly where your cursor is blinking—completely bypassing the OS clipboard (`Win+V`) for maximum privacy and reliability.
- **Hindi & Hinglish Support**: Tuned to perfectly understand and preserve code-switched Hindi and English without forcing unwanted translations.
- **Customizable Triggers**: Supports Push-to-Talk, Toggle, and Hands-Free Voice Activity Detection (VAD) with global hotkeys.
- **100% Local Capable**: Can run completely offline using local Whisper models and local Ollama language models.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **NVIDIA GPU** (Recommended for CUDA acceleration) or a fast modern CPU.
- **Ollama** (Optional, for offline AI refinement).

### Installation

1. Clone this repository:
   ```cmd
   git clone https://github.com/punit732007-ai/Wisper_Flow_clone_localy_on_system.git
   cd Wisper_Flow_clone_localy_on_system
   ```

2. Run the automated installer to set up the virtual environment and install dependencies:
   ```cmd
   install.bat
   ```

3. Launch the application:
   ```cmd
   run.bat
   ```

---

## ⚙️ How to Use

1. **Start the App**: Double click `run.bat`. A small glassmorphic pill (the HUD) will appear on your screen, and an icon will be added to your system tray.
2. **Dictate**: Press and hold the global hotkey (Default: `Ctrl + Space`) and start speaking. 
3. **Release & Type**: Release the hotkey. The HUD will show "Processing...", and within a second, your perfectly refined text will type itself out exactly where your cursor is blinking.
4. **Change Modes**: Right-click the HUD (or use the system tray menu) to switch dictation modes instantly depending on what you are typing.
5. **Settings**: Click the gear icon ⚙️ on the HUD to access settings, where you can change the AI provider, Whisper model size, microphone, and hotkeys.

---

## 🔒 Privacy & Architecture

- **No Clipboard Pollution**: The app simulates physical keystrokes, ensuring your dictated passwords, emails, and code never end up in your Windows Clipboard History.
- **Local History**: A secure local history of your transcriptions is saved to `~/.localwhisper/history.json` and can be accessed via the History drawer (📜).
- **Data Safety**: `.gitignore` is pre-configured to ensure your personal `settings.json`, `history.json`, API keys, and virtual environments are never accidentally pushed to GitHub.

---

## 🛠️ Tech Stack

- **Transcription**: `faster-whisper` (CTranslate2)
- **GUI**: `Tkinter` (Custom-drawn Glassmorphism)
- **AI Pipelines**: `requests` interacting with Ollama, Groq, OpenAI, and Gemini APIs.
- **Audio & Input Control**: `sounddevice`, `pynput`, `pyautogui`

---
*Built for speed, accuracy, and seamless native integration.*
