# LocalWhisper Pro — Workspace Rules

## Tkinter Thread Safety on Windows
- **NEVER** call `root.after()`, `widget.config()`, `canvas.create_*()`, or any Tkinter method from a background thread. Use a `queue.Queue` drained in the main thread's animation tick loop (`_tick()`) instead.
- All cross-thread UI updates MUST go through `hud.schedule(func, *args)` which enqueues to the queue — never directly invoking Tkinter methods.

## Windows Transparency
- When using `overrideredirect(True)` windows on Windows, use ONLY `-transparentcolor` with a unique chroma key color (e.g., `#f0abcd`). Do NOT combine `-alpha` with `-transparentcolor` — this causes DWM to render a black rectangle.

## Shutdown & Lifecycle
- System tray `stop()` must NEVER call `on_quit` (which triggers app `shutdown()`). The quit menu item should call a separate `_trigger_quit()` method.
- `shutdown()` must call `root.quit()` then `root.destroy()` then `os._exit(0)` to ensure full process cleanup on Windows.

## Canvas Performance
- Reuse canvas items via `canvas.coords()` and `canvas.itemconfig()`. Never use `canvas.delete("all")` + recreate in animation loops — this causes GC pressure and event queue starvation.

## Language Support
- This project supports only **English** and **Hindi/Hinglish**. All Whisper config, mode prompts, and UI language options should reflect this.

## Architecture
- The app uses: Python 3.11, Tkinter (no customtkinter), faster-whisper (CTranslate2), sounddevice, pynput, pystray, Pillow.
- GPU: NVIDIA RTX 4060 (8GB VRAM), CUDA float16 supported.
- Config stored at `~/.localwhisper/settings.json`. History at `~/.localwhisper/history.json`.
