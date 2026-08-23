"""
LocalWhisper Pro — System Tray Icon
Background tray icon with menu actions for showing/hiding HUD, opening Settings,
browsing History, and cycling Dictation Modes.
"""

import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray
from config import config


class SystemTray:
    """Manages the Windows taskbar notification area icon."""

    def __init__(
        self,
        on_toggle_hud: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_open_history: Optional[Callable[[], None]] = None,
        on_cycle_mode: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        self.on_toggle_hud = on_toggle_hud
        self.on_open_settings = on_open_settings
        self.on_open_history = on_open_history
        self.on_cycle_mode = on_cycle_mode
        self.on_quit = on_quit

        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _create_icon_image() -> Image.Image:
        """Draw a 64x64 glowing violet-blue gradient circle icon."""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer dark ring
        draw.ellipse([4, 4, size - 4, size - 4], fill=(24, 25, 38, 255), outline=(137, 180, 250, 255), width=2)
        # Inner glowing core
        draw.ellipse([16, 16, size - 16, size - 16], fill=(137, 180, 250, 255))
        return img

    def start(self) -> None:
        """Start the system tray icon in a daemon thread."""
        img = self._create_icon_image()

        def _get_mode_label(item):
            mode = config.current_mode_info.get("name", "Smart Dictation")
            return f"Mode: {mode}"

        menu = pystray.Menu(
            pystray.MenuItem("Show/Hide HUD", lambda icon, item: self._safe_call(self.on_toggle_hud), default=True),
            pystray.MenuItem(_get_mode_label, lambda icon, item: self._safe_call(self.on_cycle_mode)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Settings...", lambda icon, item: self._safe_call(self.on_open_settings)),
            pystray.MenuItem("📜 History...", lambda icon, item: self._safe_call(self.on_open_history)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quit", lambda icon, item: self._trigger_quit()),
        )

        self._icon = pystray.Icon("LocalWhisper Pro", img, "LocalWhisper Pro", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="system-tray")
        self._thread.start()

    def _trigger_quit(self) -> None:
        """Trigger application quit from tray."""
        if self.on_quit:
            self._safe_call(self.on_quit)

    def _safe_call(self, callback: Optional[Callable[[], None]]) -> None:
        if callback:
            try:
                callback()
            except Exception as e:
                print(f"[Tray] Callback error: {e}")

    def stop(self) -> None:
        """Stop tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
