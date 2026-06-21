"""
LocalWhisper — Floating UI
Always-on-top pill-shaped button with animated state transitions.
Uses WS_EX_NOACTIVATE so clicking the button does NOT steal focus
from the target application — Ctrl+V pastes in the right place.
"""

import tkinter as tk
import ctypes
import ctypes.wintypes
import math
import time
import threading
from config import (
    BUTTON_WIDTH, BUTTON_HEIGHT, BUTTON_RADIUS,
    BUTTON_PADDING, TRANSPARENT_COLOR, ANIMATION_FPS,
)

# — Optional system-tray dependencies —
try:
    import pystray
    from PIL import Image, ImageDraw
    _PYSTRAY_AVAILABLE = True
except ImportError:
    _PYSTRAY_AVAILABLE = False

# — Windows API constants —
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE  = 0x08000000
WS_EX_TOOLWINDOW  = 0x00000080
WS_EX_APPWINDOW   = 0x00040000
SPI_GETWORKAREA    = 0x0030
_user32 = ctypes.windll.user32


def _get_work_area() -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of the desktop work area
    (screen minus taskbar)."""
    rect = ctypes.wintypes.RECT()
    _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def _set_no_activate(root: tk.Tk) -> None:
    """Prevent the tkinter window from stealing focus on click."""
    root.update_idletasks()
    hwnd = _user32.GetParent(root.winfo_id())
    style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


# ── State definitions ─────────────────────────────────────────────
STATES = {
    "loading": {
        "label":      "\u25cc  Loading...",
        "dot":        "#4a9eff",
        "bg":         (30,  30,  48),
        "bg_pulse":   (40,  40,  68),
        "fg":         "#7799cc",
        "pulse_spd":  0.045,
    },
    "ready": {
        "label":      "\u25cf  Ready",
        "dot":        "#50fa7b",
        "bg":         (30,  30,  46),
        "bg_pulse":   (30,  30,  46),   # no pulse
        "fg":         "#a0aec0",
        "pulse_spd":  0,
    },
    "recording": {
        "label":      "\u25cf  Recording",
        "dot":        "#ff5555",
        "bg":         (55,  20,  30),
        "bg_pulse":   (85,  25,  35),
        "fg":         "#ff9999",
        "pulse_spd":  0.09,
    },
    "processing": {
        "label":      "\u25c9  Processing",
        "dot":        "#ffb86c",
        "bg":         (48,  38,  18),
        "bg_pulse":   (68,  50,  22),
        "fg":         "#ffd699",
        "pulse_spd":  0.06,
    },
}


def _lerp_color(c1: tuple, c2: tuple, t: float) -> str:
    """Linearly interpolate between two RGB tuples → hex string."""
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


# ══════════════════════════════════════════════════════════════════
class FloatingUI:
    """A borderless, always-on-top pill button anchored to the bottom-left."""

    def __init__(self, on_toggle=None, on_quit=None):
        self.on_toggle = on_toggle
        self.on_quit   = on_quit

        # ── state ────────────────────────────────────────────────
        self._state = "loading"
        self._phase = 0.0                 # animation phase (0‒2π)
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False
        self._click_origin = (0, 0)

        # ── system tray ──────────────────────────────────────────
        self._tray = None
        self._tray_available = _PYSTRAY_AVAILABLE

        # ── root window ──────────────────────────────────────────
        self.root = tk.Tk()
        self.root.withdraw()              # hide while we configure
        self.root.title("LocalWhisper")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.96)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.configure(bg=TRANSPARENT_COLOR)

        # ── position (bottom-left, above taskbar) ────────────────
        _, _, _, work_bottom = _get_work_area()
        x = BUTTON_PADDING
        y = work_bottom - BUTTON_HEIGHT - BUTTON_PADDING
        self.root.geometry(f"{BUTTON_WIDTH}x{BUTTON_HEIGHT}+{x}+{y}")

        # ── canvas ───────────────────────────────────────────────
        self.canvas = tk.Canvas(
            self.root,
            width=BUTTON_WIDTH,
            height=BUTTON_HEIGHT,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # ── bindings ─────────────────────────────────────────────
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",        self._on_motion)
        self.canvas.bind("<ButtonRelease-1>",  self._on_release)
        self.canvas.bind("<Button-3>",         self._on_right_click)

        # ── context menu ─────────────────────────────────────────
        self._menu = tk.Menu(self.root, tearoff=0,
                             bg="#1e1e2e", fg="#a0aec0",
                             activebackground="#44447a",
                             activeforeground="#ffffff",
                             font=("Segoe UI", 10))
        if self._tray_available:
            self._menu.add_command(label="  Minimize to Tray  ",
                                   command=self._minimize_to_tray)
        self._menu.add_command(label="  Quit  ", command=self._quit)

        # ── show & configure ─────────────────────────────────────
        self.root.deiconify()
        _set_no_activate(self.root)
        self._draw()
        self._tick()

    # ── public ────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Thread-safe state change — schedule on the main thread."""
        if state in STATES:
            self._state = state
            self._phase = 0.0
            self._draw()

    def schedule(self, func, *args) -> None:
        """Schedule *func* to run on the tkinter main thread."""
        self.root.after(0, func, *args)

    def run(self) -> None:
        """Start the tkinter main loop (blocks)."""
        self._setup_tray()
        self.root.mainloop()

    # ── system tray ───────────────────────────────────────────────

    @staticmethod
    def _create_tray_icon() -> "Image.Image":
        """Create a 64×64 tray icon programmatically (green circle on
        dark background) — no external image file required."""
        size = 64
        img = Image.new("RGBA", (size, size), (30, 30, 46, 255))
        draw = ImageDraw.Draw(img)
        margin = 12
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=(80, 250, 123, 255),
        )
        return img

    def _setup_tray(self) -> None:
        """Create and start the pystray system-tray icon in a daemon thread."""
        if not self._tray_available:
            return

        icon_image = self._create_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Show/Hide",
                             lambda icon, item: self.root.after(
                                 0, self._toggle_visibility)),
            pystray.MenuItem("Quit",
                             lambda icon, item: self.root.after(
                                 0, self._quit)),
        )
        self._tray = pystray.Icon("LocalWhisper", icon_image,
                                  "LocalWhisper", menu)

        tray_thread = threading.Thread(target=self._tray.run, daemon=True)
        tray_thread.start()

    def _toggle_visibility(self) -> None:
        """Show the floating button if hidden, hide it if visible."""
        if self.root.winfo_viewable():
            self.root.withdraw()
        else:
            self.root.deiconify()

    def _minimize_to_tray(self) -> None:
        """Hide the floating button to the system tray."""
        self.root.withdraw()

    # ── drawing ───────────────────────────────────────────────────

    def _draw(self) -> None:
        self.canvas.delete("all")
        s = STATES[self._state]

        # Pulse factor (0‒1, driven by sine wave)
        t = (math.sin(self._phase) + 1) / 2 if s["pulse_spd"] else 0
        bg_hex = _lerp_color(s["bg"], s["bg_pulse"], t)

        # Brighter border based on pulse
        border_rgb = tuple(min(255, c + 22) for c in s["bg_pulse"])
        border_hex = _lerp_color(s["bg"], border_rgb, 0.5 + t * 0.5)

        # Rounded-rectangle background
        self._rounded_rect(
            2, 2, BUTTON_WIDTH - 2, BUTTON_HEIGHT - 2,
            BUTTON_RADIUS, fill=bg_hex, outline=border_hex, width=1.5,
        )

        # Status text
        self.canvas.create_text(
            BUTTON_WIDTH // 2, BUTTON_HEIGHT // 2,
            text=s["label"],
            fill=s["fg"],
            font=("Segoe UI Semibold", 11),
            anchor="center",
        )

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw) -> int:
        """Draw a rounded rectangle on the canvas."""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2,     y1,
            x2,     y1 + r,
            x2,     y2 - r,
            x2,     y2,
            x2 - r, y2,
            x1 + r, y2,
            x1,     y2,
            x1,     y2 - r,
            x1,     y1 + r,
            x1,     y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kw)

    # ── animation loop ────────────────────────────────────────────

    def _tick(self) -> None:
        s = STATES[self._state]
        if s["pulse_spd"]:
            self._phase += s["pulse_spd"]
            if self._phase > 2 * math.pi:
                self._phase -= 2 * math.pi
            self._draw()
        interval = max(16, int(1000 / ANIMATION_FPS))
        self.root.after(interval, self._tick)

    # ── mouse handlers ────────────────────────────────────────────

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
        if self._is_dragging:
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{x}+{y}")

    def _on_release(self, event) -> None:
        if not self._is_dragging:
            # It was a click, not a drag
            if self.on_toggle:
                self.on_toggle()

    def _on_right_click(self, event) -> None:
        self._menu.tk_popup(event.x_root, event.y_root)

    def _quit(self) -> None:
        if self._tray is not None:
            self._tray.stop()
        if self.on_quit:
            self.on_quit()
        self.root.destroy()
