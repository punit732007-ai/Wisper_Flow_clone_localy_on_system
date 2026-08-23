"""
LocalWhisper Pro — Floating HUD
Ultra-modern glassmorphic floating pill widget with real-time audio visualizer,
clickable mode badge, non-focus-stealing Windows flags, and quick settings access.
"""

import sys
import math
import time
import tkinter as tk
from typing import Callable, Optional, Tuple, Dict, Any
import ctypes
from config import config
from ui.visualizer_widget import AudioVisualizerWidget

# ─── Windows Native API Constants ─────────────────────────────────
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SPI_GETWORKAREA = 0x0030
_user32 = ctypes.windll.user32 if sys.platform == "win32" else None

TRANSPARENT_COLOR = "#f0abcd"

HUD_WIDTH = 270
HUD_HEIGHT = 48
HUD_RADIUS = 22


def get_desktop_workarea() -> Tuple[int, int, int, int]:
    """Get desktop boundaries excluding Windows taskbar."""
    if sys.platform == "win32" and _user32:
        from ctypes import wintypes
        rect = wintypes.RECT()
        _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, 1920, 1080


def set_no_activate(root: tk.Tk) -> None:
    """Set window style so clicking does NOT steal focus from active applications."""
    if sys.platform == "win32" and _user32:
        try:
            root.update_idletasks()
            hwnd = root.winfo_id()
            style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass


HUD_STATES = {
    "loading": {
        "text": "Loading...",
        "dot_color": "#00b4d8",
        "bg": "#141624",
        "border": "#00b4d8",
    },
    "ready": {
        "text": "Ready",
        "dot_color": "#52b788",
        "bg": "#141624",
        "border": "#2e3450",
    },
    "recording": {
        "text": "Listening...",
        "dot_color": "#ff4d6d",
        "bg": "#26121a",
        "border": "#ff4d6d",
    },
    "processing": {
        "text": "Refining...",
        "dot_color": "#ffb703",
        "bg": "#221c10",
        "border": "#ffb703",
    },
    "success": {
        "text": "Pasted!",
        "dot_color": "#70e000",
        "bg": "#122418",
        "border": "#70e000",
    },
    "error": {
        "text": "Error",
        "dot_color": "#e63946",
        "bg": "#261012",
        "border": "#e63946",
    },
}


import queue

class FloatingHUD:
    """Always-on-top draggable floating pill HUD."""

    def __init__(
        self,
        on_toggle_recording: Optional[Callable[[], None]] = None,
        on_cycle_mode: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_open_history: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        self.on_toggle_recording = on_toggle_recording
        self.on_cycle_mode = on_cycle_mode
        self.on_open_settings = on_open_settings
        self.on_open_history = on_open_history
        self.on_quit = on_quit

        self._state = "loading"
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._click_origin = (0, 0)
        self._action_queue: queue.Queue = queue.Queue()

        # Create Root Window
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("LocalWhisper Pro")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.configure(bg=TRANSPARENT_COLOR)

        # Position (bottom-center of screen by default)
        _, _, work_right, work_bottom = get_desktop_workarea()
        saved_pos = config.get("hud_position", None)
        if saved_pos and len(saved_pos) == 2:
            x, y = saved_pos
        else:
            x = (work_right - HUD_WIDTH) // 2
            y = work_bottom - HUD_HEIGHT - 24
        self.root.geometry(f"{HUD_WIDTH}x{HUD_HEIGHT}+{x}+{y}")

        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=HUD_WIDTH,
            height=HUD_HEIGHT,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Build Static Canvas Items
        r = HUD_RADIUS
        pill_pts = self._make_rounded_pill_points(2, 2, HUD_WIDTH - 2, HUD_HEIGHT - 2, r)
        self.pill_bg_id = self.canvas.create_polygon(
            pill_pts, smooth=True, fill="#141624", outline="#2e3450", width=1.5
        )

        # Status Dot
        dot_x, dot_y = 18, HUD_HEIGHT // 2
        dot_r = 4
        self.dot_id = self.canvas.create_oval(
            dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r,
            fill="#00b4d8", outline="",
        )

        # Visualizer Widget (bouncing bars)
        self.visualizer = AudioVisualizerWidget(
            self.canvas,
            x=30,
            y=12,
            width=48,
            height=24,
            num_bars=5,
        )

        # Mode Badge Pill (center-right)
        badge_pts = self._make_rounded_pill_points(90, 10, 206, HUD_HEIGHT - 10, 12)
        self.badge_bg_id = self.canvas.create_polygon(
            badge_pts, smooth=True, fill="#2c2e43", outline="#3e4260", width=1,
            tags="mode_button",
        )
        mode_info = config.current_mode_info
        badge_text = mode_info.get("badge", "✍️ Smart")
        self.badge_txt_id = self.canvas.create_text(
            148, HUD_HEIGHT // 2,
            text=badge_text,
            fill="#e0e6ed",
            font=("Segoe UI Semibold", 9),
            anchor="center",
            tags="mode_button",
        )

        # Quick Settings Icon Button (gear)
        self.settings_btn_id = self.canvas.create_text(
            224, HUD_HEIGHT // 2,
            text="⚙",
            fill="#8d99ae",
            font=("Segoe UI", 12),
            tags="settings_button",
        )

        # Quick History Icon Button (scroll)
        self.history_btn_id = self.canvas.create_text(
            248, HUD_HEIGHT // 2,
            text="📜",
            fill="#8d99ae",
            font=("Segoe UI", 11),
            tags="history_button",
        )

        # Context Menu
        self._context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#181926",
            fg="#cad3f5",
            activebackground="#363a4f",
            activeforeground="#ffffff",
            font=("Segoe UI", 10),
        )
        self._context_menu.add_command(label="  ⚙️ Settings...  ", command=self._trigger_settings)
        self._context_menu.add_command(label="  📜 History...  ", command=self._trigger_history)
        self._context_menu.add_command(label="  🔄 Switch Mode  ", command=self._trigger_cycle_mode)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="  🔽 Minimize to Tray  ", command=self.minimize_to_tray)
        self._context_menu.add_command(label="  ❌ Quit LocalWhisper  ", command=self._trigger_quit)

        # Mouse Bindings
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)

        self.root.deiconify()
        set_no_activate(self.root)
        self._apply_state_style()
        self._tick()

    # ── Public Methods ────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Set HUD visual state (ready, recording, processing, success, error)."""
        if state in HUD_STATES:
            self._state = state
            self.visualizer.set_state(state)
            self._apply_state_style()

    def update_audio_levels(self, rms: float, bands: list) -> None:
        """Feed live mic levels into the visualizer."""
        self.visualizer.update_levels(bands)

    def schedule(self, func, *args) -> None:
        """Thread-safe invocation on Tkinter main loop via queue."""
        self._action_queue.put((func, args))

    def show(self) -> None:
        self.root.deiconify()

    def hide(self) -> None:
        self.root.withdraw()

    def minimize_to_tray(self) -> None:
        self.root.withdraw()

    def run(self) -> None:
        self.root.mainloop()

    # ── Internal Styling & Animation ──────────────────────────────

    def _apply_state_style(self) -> None:
        st = HUD_STATES.get(self._state, HUD_STATES["ready"])
        self.canvas.itemconfig(self.pill_bg_id, fill=st["bg"], outline=st["border"])
        self.canvas.itemconfig(self.dot_id, fill=st["dot_color"])
        # Update badge text
        mode_info = config.current_mode_info
        badge_text = mode_info.get("badge", "✍️ Smart")
        self.canvas.itemconfig(self.badge_txt_id, text=badge_text)

    def _make_rounded_pill_points(self, x1, y1, x2, y2, r) -> list:
        return [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]

    def _tick(self) -> None:
        try:
            # Drain action queue safely on Tkinter main thread
            while not self._action_queue.empty():
                try:
                    func, args = self._action_queue.get_nowait()
                    func(*args)
                except Exception as e:
                    print(f"[HUD] Error in scheduled task: {e}")

            if not self.root.winfo_exists():
                return

            self.visualizer.update_animation()
            self.root.after(25, self._tick)
        except Exception:
            pass

    # ── Mouse Interaction ─────────────────────────────────────────

    def _on_press(self, event) -> None:
        self._click_origin = (event.x_root, event.y_root)
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._is_dragging = False

    def _on_motion(self, event) -> None:
        dx = abs(event.x_root - self._click_origin[0])
        dy = abs(event.y_root - self._click_origin[1])
        if dx > 4 or dy > 4:
            self._is_dragging = True
            new_x = self.root.winfo_x() + (event.x - self._drag_start_x)
            new_y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{new_x}+{new_y}")

    def _on_release(self, event) -> None:
        if self._is_dragging:
            config.set("hud_position", [self.root.winfo_x(), self.root.winfo_y()])
            return

        clicked_tags = self.canvas.gettags(self.canvas.find_withtag("current"))

        if "mode_button" in clicked_tags:
            self._trigger_cycle_mode()
        elif "settings_button" in clicked_tags:
            self._trigger_settings()
        elif "history_button" in clicked_tags:
            self._trigger_history()
        else:
            if self.on_toggle_recording:
                self.on_toggle_recording()

    def _on_right_click(self, event) -> None:
        self._context_menu.tk_popup(event.x_root, event.y_root)

    def _trigger_cycle_mode(self) -> None:
        new_mode = config.cycle_next_mode()
        self._apply_state_style()
        if self.on_cycle_mode:
            self.on_cycle_mode()

    def _trigger_settings(self) -> None:
        if self.on_open_settings:
            self.on_open_settings()

    def _trigger_history(self) -> None:
        if self.on_open_history:
            self.on_open_history()

    def _trigger_quit(self) -> None:
        if self.on_quit:
            self.on_quit()
        self.root.destroy()
