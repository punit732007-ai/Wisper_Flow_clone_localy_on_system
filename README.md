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

## 🚀 Installation & Setup Guide

### Step 1: Download the App
1. Go to the [Releases page](../../releases) on the right side of this repository.
2. Download the `LocalWhisper_Pro_v3.1_Windows.zip` file.
3. Extract the ZIP file anywhere on your computer (e.g., your Desktop).
4. Inside the extracted folder, double-click **`LocalWhisper Pro.exe`** to run the app. No Python installation required!

### Step 2: Install Ollama (For Local AI Processing)
LocalWhisper uses **Ollama** to refine your transcribed text locally and securely without needing an internet connection.

1. Download Ollama from their official website: **[ollama.com/download](https://ollama.com/download)**
2. Install the Windows application.
3. Open your Command Prompt (cmd) or PowerShell and run the following command to download a fast, smart language model (Llama 3 is highly recommended):
   ```cmd
   ollama run llama3.1:8b
   ```
   *Note: This will download the model (about 4.7GB). You can close the terminal once it says "success".*

### Step 3: Configure LocalWhisper Pro
1. Once **LocalWhisper Pro** is running, click the **Gear Icon ⚙️** on the floating glass HUD to open Settings.
2. Go to the **"🧠 AI Refiner"** tab.
3. Under **Provider**, select `ollama`.
4. In the **Ollama Model** dropdown, select `llama3.1:8b` (or whichever model you downloaded).
5. Click **💾 Save Settings**.

---

## ⚙️ How to Use

1. **Dictate**: Press and hold the global hotkey (Default: `Ctrl + Space`) and start speaking. 
2. **Release & Type**: Release the hotkey. The HUD will show "Processing...", and within a second, your perfectly refined text will type itself out exactly where your cursor is blinking.
3. **Change Modes**: Right-click the HUD (or use the system tray menu) to switch dictation modes instantly depending on what you are typing.
4. **Cloud AI (Optional)**: If you don't want to use Ollama, you can go to Settings and enter an API key for **Groq**, **OpenAI**, or **Gemini** for ultra-fast cloud processing instead.

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
