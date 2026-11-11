"""
LocalWhisper Pro — Floating HUD
Ultra-modern glassmorphic floating pill widget with real-time audio visualizer,
clickable mode badge, dynamic theme engine integration, multiple layout presets,
non-focus-stealing Windows flags, and quick settings & themes access.
"""

import sys
import math
import time
import queue
import tkinter as tk
from typing import Callable, Optional, Tuple, Dict, Any
import ctypes

from config import config
from ui.visualizer_widget import AudioVisualizerWidget
from ui.theme_engine import theme_manager

# ─── Windows Native API Constants ─────────────────────────────────
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SPI_GETWORKAREA = 0x0030
_user32 = ctypes.windll.user32 if sys.platform == "win32" else None

TRANSPARENT_COLOR = "#f0abcd"

# Layout Presets
HUD_LAYOUTS = {
    "compact_pill": {
        "width": 270,
        "height": 48,
        "radius": 22,
        "dot_x": 18,
        "vis_x": 30,
        "vis_y": 12,
        "vis_w": 48,
        "vis_h": 24,
        "badge_x1": 90,
        "badge_y1": 10,
        "badge_x2": 206,
        "badge_y2": 38,
        "badge_r": 12,
        "badge_txt_x": 148,
        "settings_x": 224,
        "history_x": 248,
    },
    "classic_bar": {
        "width": 320,
        "height": 42,
        "radius": 10,
        "dot_x": 16,
        "vis_x": 28,
        "vis_y": 10,
        "vis_w": 52,
        "vis_h": 22,
        "badge_x1": 90,
        "badge_y1": 7,
        "badge_x2": 236,
        "badge_y2": 35,
        "badge_r": 8,
        "badge_txt_x": 163,
        "settings_x": 262,
        "history_x": 292,
    },
    "expanded_card": {
        "width": 310,
        "height": 64,
        "radius": 22,
        "dot_x": 20,
        "vis_x": 34,
        "vis_y": 18,
        "vis_w": 54,
        "vis_h": 28,
        "badge_x1": 100,
        "badge_y1": 14,
        "badge_x2": 230,
        "badge_y2": 50,
        "badge_r": 14,
        "badge_txt_x": 165,
        "settings_x": 255,
        "history_x": 282,
    },
    "minimal_dot": {
        "width": 200,
        "height": 38,
        "radius": 18,
        "dot_x": 14,
        "vis_x": 24,
        "vis_y": 10,
        "vis_w": 34,
        "vis_h": 18,
        "badge_x1": 66,
        "badge_y1": 6,
        "badge_x2": 158,
        "badge_y2": 32,
        "badge_r": 10,
        "badge_txt_x": 112,
        "settings_x": 178,
        "history_x": -100,  # Hidden in minimal dot mode
    },
}

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
        "specular": "#90e0ef",
    },
    "ready": {
        "text": "Ready",
        "dot_color": "#52b788",
        "bg": "#141624",
        "border": "#2e3450",
        "specular": "#4a5578",
    },
    "recording": {
        "text": "Listening...",
        "dot_color": "#ff4d6d",
        "bg": "#26121a",
        "border": "#ff4d6d",
        "specular": "#ff85a1",
    },
    "processing": {
        "text": "Refining...",
        "dot_color": "#ffb703",
        "bg": "#221c10",
        "border": "#ffb703",
        "specular": "#ffd166",
    },
    "success": {
        "text": "Pasted!",
        "dot_color": "#70e000",
        "bg": "#122418",
        "border": "#70e000",
        "specular": "#9ef01a",
    },
    "error": {
        "text": "Error",
        "dot_color": "#e63946",
        "bg": "#261012",
        "border": "#e63946",
        "specular": "#f28482",
    },
}


class FloatingHUD:
    """Always-on-top draggable floating pill HUD with dynamic themes and layouts."""

    def __init__(
        self,
        on_toggle_recording: Optional[Callable[[], None]] = None,
        on_cycle_mode: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_open_history: Optional[Callable[[], None]] = None,
        on_open_themes: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        self.on_toggle_recording = on_toggle_recording
        self.on_cycle_mode = on_cycle_mode
        self.on_open_settings = on_open_settings
        self.on_open_history = on_open_history
        self.on_open_themes = on_open_themes
        self.on_quit = on_quit

        self._state = "loading"
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._click_origin = (0, 0)
        self._action_queue: queue.Queue = queue.Queue()

        self._current_layout = config.get("hud_layout", "compact_pill")
        layout_cfg = HUD_LAYOUTS.get(self._current_layout, HUD_LAYOUTS["compact_pill"])
        self._width = layout_cfg["width"]
        self._height = layout_cfg["height"]

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
            x = (work_right - self._width) // 2
            y = work_bottom - self._height - 24
        self.root.geometry(f"{self._width}x{self._height}+{x}+{y}")

        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self._width,
            height=self._height,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Build Static Canvas Items
        theme = theme_manager.current_theme
        r = layout_cfg["radius"]
        pill_pts = self._make_rounded_pill_points(2, 2, self._width - 2, self._height - 2, r)
        self.pill_bg_id = self.canvas.create_polygon(
            pill_pts, smooth=True, fill=theme["hud_bg"], outline=theme["hud_border"], width=1.5
        )

        # Specular Highlight Arc (dual-layer overhead frosted glass reflection)
        spec_col = theme.get("hud_specular", theme.get("hud_border", "#ffffff"))
        spec_x1 = r + 2
        spec_x2 = max(spec_x1 + 1, self._width - r - 2)
        self.pill_specular_id = self.canvas.create_line(
            spec_x1, 3,
            spec_x2, 3,
            fill=spec_col,
            width=1.5,
            capstyle="round",
        )

        # Status Dot
        dot_x, dot_y = layout_cfg["dot_x"], self._height // 2
        dot_r = 4
        self.dot_id = self.canvas.create_oval(
            dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r,
            fill=theme["info"], outline="",
        )

        # Visualizer Widget (bouncing bars)
        self.visualizer = AudioVisualizerWidget(
            self.canvas,
            x=layout_cfg["vis_x"],
            y=layout_cfg["vis_y"],
            width=layout_cfg["vis_w"],
            height=layout_cfg["vis_h"],
            num_bars=5,
        )

        # Mode Badge Pill (center-right)
        badge_pts = self._make_rounded_pill_points(
            layout_cfg["badge_x1"], layout_cfg["badge_y1"],
            layout_cfg["badge_x2"], layout_cfg["badge_y2"],
            layout_cfg["badge_r"]
        )
        self.badge_bg_id = self.canvas.create_polygon(
            badge_pts, smooth=True,
            fill=theme.get("hud_badge_bg", theme["bg_tertiary"]),
            outline=theme.get("border", theme["bg_tertiary"]),
            width=1,
            tags="mode_button",
        )
        mode_info = config.current_mode_info
        badge_text = mode_info.get("badge", "✍️ Smart")
        self.badge_txt_id = self.canvas.create_text(
            layout_cfg["badge_txt_x"], self._height // 2,
            text=badge_text,
            fill=theme.get("hud_badge_fg", theme["fg_primary"]),
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            anchor="center",
            tags="mode_button",
        )

        # Quick Settings Icon Button (gear)
        self.settings_btn_id = self.canvas.create_text(
            layout_cfg["settings_x"], self._height // 2,
            text="⚙",
            fill=theme["fg_secondary"],
            font=("Segoe UI", 12),
            tags="settings_button",
        )

        # Quick History Icon Button (scroll)
        self.history_btn_id = self.canvas.create_text(
            layout_cfg["history_x"], self._height // 2,
            text="📜",
            fill=theme["fg_secondary"],
            font=("Segoe UI", 11),
            tags="history_button",
        )

        # Context Menu
        self._context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=theme["bg_secondary"],
            fg=theme["fg_primary"],
            activebackground=theme["bg_tertiary"],
            activeforeground=theme.get("accent_fg", "#ffffff"),
            font=(theme.get("font_family", "Segoe UI"), 10),
        )
        self._context_menu.add_command(label="  🎨 Themes & Customization...  ", command=self._trigger_themes)
        self._context_menu.add_command(label="  ⚙️ Settings...  ", command=self._trigger_settings)
        self._context_menu.add_command(label="  📜 History...  ", command=self._trigger_history)
        self._context_menu.add_command(label="  🔄 Switch Mode  ", command=self._trigger_cycle_mode)

        # Layout Presets Submenu
        layout_submenu = tk.Menu(
            self._context_menu,
            tearoff=0,
            bg=theme["bg_secondary"],
            fg=theme["fg_primary"],
            activebackground=theme["bg_tertiary"],
            activeforeground=theme.get("accent_fg", "#ffffff"),
            font=(theme.get("font_family", "Segoe UI"), 9),
        )
        layout_submenu.add_command(label="Compact Pill (Default)", command=lambda: self.set_layout("compact_pill"))
        layout_submenu.add_command(label="Classic Dock Bar", command=lambda: self.set_layout("classic_bar"))
        layout_submenu.add_command(label="Expanded Island", command=lambda: self.set_layout("expanded_card"))
        layout_submenu.add_command(label="Minimal Dot", command=lambda: self.set_layout("minimal_dot"))
        self._context_menu.add_cascade(label="  📐 Layout Style  ", menu=layout_submenu)

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
            st = HUD_STATES[state]
            self.visualizer.set_state(state, custom_color=st.get("dot_color"))
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

    def set_layout(self, layout_name: str) -> None:
        """Dynamically switch HUD layout geometry and update canvas coords."""
        if layout_name not in HUD_LAYOUTS:
            return
        self._current_layout = layout_name
        config.set("hud_layout", layout_name)
        cfg = HUD_LAYOUTS[layout_name]

        self._width = cfg["width"]
        self._height = cfg["height"]
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()

        self.root.geometry(f"{self._width}x{self._height}+{cur_x}+{cur_y}")
        self.canvas.config(width=self._width, height=self._height)

        # Reposition Pill Polygon
        pill_pts = self._make_rounded_pill_points(2, 2, self._width - 2, self._height - 2, cfg["radius"])
        self.canvas.coords(self.pill_bg_id, *pill_pts)

        # Reposition Specular Highlight Arc
        r = cfg["radius"]
        spec_x1 = r + 2
        spec_x2 = max(spec_x1 + 1, self._width - r - 2)
        self.canvas.coords(self.pill_specular_id, spec_x1, 3, spec_x2, 3)

        # Reposition Status Dot
        dot_x, dot_y = cfg["dot_x"], self._height // 2
        dot_r = 4
        self.canvas.coords(self.dot_id, dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r)

        # Reposition Visualizer
        self.visualizer.reposition(cfg["vis_x"], cfg["vis_y"], cfg["vis_w"], cfg["vis_h"])

        # Reposition Mode Badge
        badge_pts = self._make_rounded_pill_points(
            cfg["badge_x1"], cfg["badge_y1"],
            cfg["badge_x2"], cfg["badge_y2"],
            cfg["badge_r"]
        )
        self.canvas.coords(self.badge_bg_id, *badge_pts)
        self.canvas.coords(self.badge_txt_id, cfg["badge_txt_x"], self._height // 2)

        # Reposition Icon Buttons
        self.canvas.coords(self.settings_btn_id, cfg["settings_x"], self._height // 2)
        self.canvas.coords(self.history_btn_id, cfg["history_x"], self._height // 2)

    # ── Internal Styling & Animation ──────────────────────────────

    def _apply_state_style(self) -> None:
        theme = theme_manager.current_theme
        st = HUD_STATES.get(self._state, HUD_STATES["ready"])

        self.canvas.itemconfig(self.pill_bg_id, fill=st["bg"], outline=st["border"])
        specular_color = st.get("specular") or theme.get("hud_specular", theme.get("hud_border", "#ffffff"))
        self.canvas.itemconfig(self.pill_specular_id, fill=specular_color)
        self.canvas.itemconfig(self.dot_id, fill=st["dot_color"])

        # Synchronize visualizer bar color with active state
        self.visualizer.set_state(self._state, custom_color=st.get("dot_color"))

        # Update badge text and colors
        mode_info = config.current_mode_info
        badge_text = mode_info.get("badge", "✍️ Smart")
        self.canvas.itemconfig(
            self.badge_txt_id,
            text=badge_text,
            fill=theme.get("hud_badge_fg", theme["fg_primary"]),
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
        )
        self.canvas.itemconfig(
            self.badge_bg_id,
            fill=theme.get("hud_badge_bg", theme["bg_tertiary"]),
            outline=theme.get("border", theme["bg_tertiary"]),
        )
        self.canvas.itemconfig(self.settings_btn_id, fill=theme["fg_secondary"])
        self.canvas.itemconfig(self.history_btn_id, fill=theme["fg_secondary"])

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

    def _trigger_themes(self) -> None:
        if self.on_open_themes:
            self.on_open_themes()

    def _trigger_history(self) -> None:
        if self.on_open_history:
            self.on_open_history()

    def _trigger_quit(self) -> None:
        if self.on_quit:
            self.on_quit()
        self.root.destroy()
