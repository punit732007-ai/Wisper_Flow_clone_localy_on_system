"""
LocalWhisper Pro — Theme Applicator
Applies the current theme from ThemeManager to all registered Tkinter windows
(FloatingHUD, SettingsWindow, HistoryWindow) and configures global ttk styles.

Thread-safety: all public methods must be called on the Tkinter main thread.
For cross-thread use, enqueue via ``hud.schedule(theme_applicator.apply_current_theme)``.
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional

try:
    from PIL import Image, ImageTk
except ImportError:  # Pillow not installed — wallpaper support disabled
    Image = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]

from ui.theme_engine import theme_manager

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HUD state dict builder
# ---------------------------------------------------------------------------

def _build_hud_states(theme: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Generate the full HUD_STATES mapping from a theme dict."""
    specular_ready = theme.get("hud_specular", theme.get("hud_border", "#ffffff"))
    return {
        "loading": {
            "text": "Loading...",
            "dot_color": theme["info"],
            "bg": theme["hud_bg"],
            "border": theme["info"],
            "specular": theme.get("hud_specular", theme["info"]),
        },
        "ready": {
            "text": "Ready",
            "dot_color": theme["hud_dot_ready"],
            "bg": theme["hud_bg"],
            "border": theme["hud_border"],
            "specular": specular_ready,
        },
        "recording": {
            "text": "Listening...",
            "dot_color": theme["hud_dot_recording"],
            "bg": theme.get("hud_bg_recording", theme["hud_bg"]),
            "border": theme["hud_dot_recording"],
            "specular": theme.get("hud_specular_recording", theme["hud_dot_recording"]),
        },
        "processing": {
            "text": "Refining...",
            "dot_color": theme["hud_dot_processing"],
            "bg": theme.get("hud_bg_processing", theme["hud_bg"]),
            "border": theme["hud_dot_processing"],
            "specular": theme.get("hud_specular_processing", theme["hud_dot_processing"]),
        },
        "success": {
            "text": "Pasted!",
            "dot_color": theme["hud_dot_success"],
            "bg": theme.get("hud_bg_success", theme["hud_bg"]),
            "border": theme["hud_dot_success"],
            "specular": theme.get("hud_specular_success", theme["hud_dot_success"]),
        },
        "error": {
            "text": "Error",
            "dot_color": theme["hud_dot_error"],
            "bg": theme.get("hud_bg_error", theme["hud_bg"]),
            "border": theme["hud_dot_error"],
            "specular": theme.get("hud_specular_error", theme["hud_dot_error"]),
        },
    }


# ---------------------------------------------------------------------------
# Visualizer state→color mapping helper
# ---------------------------------------------------------------------------

_VIS_STATE_KEY = {
    "recording": "hud_dot_recording",
    "processing": "hud_dot_processing",
    "success": "hud_dot_success",
    "ready": "hud_dot_ready",
    "loading": "info",
    "error": "hud_dot_error",
}


# ---------------------------------------------------------------------------
# ThemeApplicator
# ---------------------------------------------------------------------------

class ThemeApplicator:
    """Applies the current theme to all registered Tkinter windows and widgets."""

    def __init__(self) -> None:
        self._hud: Any = None          # FloatingHUD
        self._settings_win: Any = None  # SettingsWindow
        self._history_win: Any = None   # HistoryWindow
        self._root: Optional[tk.Tk] = None

        # Wallpaper PhotoImage references kept alive to avoid GC
        self._wallpaper_images: Dict[int, Any] = {}

        # Register ourselves so we are called on every theme switch.
        theme_manager.register_callback(self.apply_current_theme)

    # -- Registration -------------------------------------------------------

    def register_hud(self, hud: Any) -> None:
        """Register the :class:`FloatingHUD` instance."""
        self._hud = hud

    def register_settings(self, settings_win: Any) -> None:
        """Register the :class:`SettingsWindow` instance."""
        self._settings_win = settings_win

    def register_history(self, history_win: Any) -> None:
        """Register the :class:`HistoryWindow` instance."""
        self._history_win = history_win

    def register_root(self, root: tk.Tk) -> None:
        """Register the application root window (used for ttk Style scope)."""
        self._root = root

    # -- Public API ---------------------------------------------------------

    def apply_current_theme(self) -> None:
        """Apply the current theme to **all** registered windows."""
        theme = theme_manager.current_theme
        if not theme:
            return
        self._apply_ttk_styles(theme)
        self._apply_to_hud(theme)
        self._apply_to_settings(theme)
        self._apply_to_history(theme)
        self._apply_wallpaper(theme)

    def get_hud_states(self, theme: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
        """Return the HUD_STATES dict derived from *theme* (or the current theme)."""
        if theme is None:
            theme = theme_manager.current_theme
        return _build_hud_states(theme)

    # -- TTK styles ---------------------------------------------------------

    def _apply_ttk_styles(self, theme: Dict[str, Any]) -> None:
        """Configure global ttk styles to match *theme*."""
        try:
            style = ttk.Style()
            font_family = theme.get("font_family", "Segoe UI")

            style.configure(
                "TNotebook",
                background=theme["bg_primary"],
                borderwidth=0,
            )
            style.configure(
                "TNotebook.Tab",
                background=theme["bg_secondary"],
                foreground=theme["fg_primary"],
                padding=[12, 6],
                font=(font_family, 9, "bold"),
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", theme["bg_tertiary"])],
                foreground=[("selected", theme["accent"])],
            )
            style.configure(
                "TFrame",
                background=theme["bg_primary"],
            )
            style.configure(
                "TLabel",
                background=theme["bg_primary"],
                foreground=theme["fg_primary"],
                font=(font_family, 9),
            )
            style.configure(
                "Header.TLabel",
                background=theme["bg_primary"],
                foreground=theme["accent"],
                font=(font_family, 11, "bold"),
            )
            style.configure(
                "TCombobox",
                fieldbackground=theme["bg_secondary"],
                background=theme["bg_tertiary"],
                foreground=theme["fg_primary"],
                arrowcolor=theme["fg_secondary"],
            )
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", theme["bg_secondary"])],
                foreground=[("readonly", theme["fg_primary"])],
            )
        except Exception:
            log.debug("ttk style update skipped", exc_info=True)

    # -- HUD ----------------------------------------------------------------

    def _apply_to_hud(self, theme: Dict[str, Any]) -> None:
        """Update the FloatingHUD canvas colours and its module-level HUD_STATES."""
        hud = self._hud
        if hud is None:
            return
        try:
            canvas: tk.Canvas = hud.canvas
            if not canvas.winfo_exists():
                return
        except (AttributeError, tk.TclError):
            return

        # ── Update the module-level HUD_STATES dict in floating_hud ──
        try:
            import ui.floating_hud as _fhud_mod
            new_states = _build_hud_states(theme)
            _fhud_mod.HUD_STATES.update(new_states)
        except Exception:
            log.debug("Could not patch floating_hud.HUD_STATES", exc_info=True)

        # ── Re-apply current visual state so the HUD picks up new colours ──
        try:
            hud._apply_state_style()
        except Exception:
            log.debug("HUD _apply_state_style failed", exc_info=True)

        # ── Badge background / foreground ──
        try:
            canvas.itemconfig(
                hud.badge_bg_id,
                fill=theme.get("hud_badge_bg", theme["bg_tertiary"]),
                outline=theme.get("border", theme["bg_tertiary"]),
            )
            canvas.itemconfig(
                hud.badge_txt_id,
                fill=theme.get("hud_badge_fg", theme["fg_primary"]),
            )
        except (AttributeError, tk.TclError):
            pass

        # ── Icon buttons (settings gear, history scroll) ──
        try:
            canvas.itemconfig(hud.settings_btn_id, fill=theme["fg_secondary"])
        except (AttributeError, tk.TclError):
            pass
        try:
            canvas.itemconfig(hud.history_btn_id, fill=theme["fg_secondary"])
        except (AttributeError, tk.TclError):
            pass

        # ── Context menu ──
        try:
            hud._context_menu.configure(
                bg=theme["bg_secondary"],
                fg=theme["fg_primary"],
                activebackground=theme["bg_tertiary"],
                activeforeground=theme.get("accent_fg", "#ffffff"),
            )
        except (AttributeError, tk.TclError):
            pass

        # ── Specular highlight ──
        try:
            if hasattr(hud, "pill_specular_id"):
                st = _build_hud_states(theme).get(getattr(hud, "_state", "ready"), {})
                specular = st.get("specular") or theme.get("hud_specular", theme.get("hud_border", "#ffffff"))
                canvas.itemconfig(hud.pill_specular_id, fill=specular)
        except (AttributeError, tk.TclError):
            pass

        # ── Visualizer bar colour ──
        try:
            vis = hud.visualizer
            key = _VIS_STATE_KEY.get(vis.state, "fg_secondary")
            new_color = theme.get(key, vis.color)
            vis.set_state(vis.state, custom_color=new_color)
        except (AttributeError, tk.TclError):
            pass

    # -- Settings window ----------------------------------------------------

    def _apply_to_settings(self, theme: Dict[str, Any]) -> None:
        """Re-colour the SettingsWindow's tk (non-ttk) widgets."""
        sw = self._settings_win
        if sw is None:
            return
        try:
            win = sw.win
            if win is None or not win.winfo_exists():
                return
        except (AttributeError, tk.TclError):
            return

        bg_primary = theme["bg_primary"]
        bg_secondary = theme["bg_secondary"]
        fg_primary = theme["fg_primary"]
        fg_secondary = theme["fg_secondary"]
        accent = theme["accent"]

        try:
            win.configure(bg=bg_primary)
        except tk.TclError:
            pass

        # Walk all descendants and re-colour known widget types.
        self._recolor_widget_tree(win, theme)

    # -- History window -----------------------------------------------------

    def _apply_to_history(self, theme: Dict[str, Any]) -> None:
        """Re-colour the HistoryWindow's tk widgets."""
        hw = self._history_win
        if hw is None:
            return
        try:
            win = hw.win
            if win is None or not win.winfo_exists():
                return
        except (AttributeError, tk.TclError):
            return

        try:
            win.configure(bg=theme["bg_primary"])
        except tk.TclError:
            pass

        self._recolor_widget_tree(win, theme)

    # -- Generic widget-tree re-colouring -----------------------------------

    def _recolor_widget_tree(self, parent: tk.Widget, theme: Dict[str, Any]) -> None:
        """Recursively walk *parent*'s widget tree and apply theme colours.

        Only touches native ``tk.*`` widgets; ``ttk.*`` widgets are governed by
        the ttk Style configured in :meth:`_apply_ttk_styles`.
        """
        bg_primary = theme["bg_primary"]
        bg_secondary = theme["bg_secondary"]
        bg_tertiary = theme["bg_tertiary"]
        fg_primary = theme["fg_primary"]
        fg_secondary = theme["fg_secondary"]
        accent = theme["accent"]
        accent_hover = theme["accent_hover"]
        accent_fg = theme.get("accent_fg", "#ffffff")
        font_family = theme.get("font_family", "Segoe UI")

        try:
            children = parent.winfo_children()
        except tk.TclError:
            return

        for w in children:
            cls_name = w.winfo_class()
            try:
                # Skip ttk widgets — they use Style objects.
                if isinstance(w, (ttk.Frame, ttk.Label, ttk.Notebook,
                                  ttk.Combobox, ttk.Scrollbar)):
                    # Recurse into ttk containers (e.g. TFrame children).
                    self._recolor_widget_tree(w, theme)
                    continue

                if cls_name == "Frame":
                    cur_bg = str(w.cget("bg"))
                    # Distinguish "primary" vs "secondary" frames heuristically
                    # by their existing bg lightness.  Frames that were set to
                    # the secondary palette colour (#181825) stay secondary.
                    if cur_bg.lower() in ("#181825", bg_secondary.lower()):
                        w.configure(bg=bg_secondary)
                    else:
                        w.configure(bg=bg_primary)

                elif cls_name == "Label":
                    cur_bg = str(w.cget("bg"))
                    if cur_bg.lower() in ("#181825", bg_secondary.lower()):
                        w.configure(bg=bg_secondary, fg=fg_secondary)
                    else:
                        w.configure(bg=bg_primary, fg=fg_primary)

                elif cls_name == "Button":
                    cur_bg = str(w.cget("bg"))
                    # Accent-styled buttons (e.g. "Save & Apply", "Copy Text")
                    if cur_bg.lower() in ("#89b4fa", accent.lower()):
                        w.configure(
                            bg=accent,
                            fg=accent_fg,
                            activebackground=accent_hover,
                            activeforeground=accent_fg,
                        )
                    else:
                        w.configure(
                            bg=bg_tertiary,
                            fg=fg_primary,
                            activebackground=theme.get("separator", bg_tertiary),
                            activeforeground=fg_primary,
                        )

                elif cls_name == "Entry":
                    w.configure(
                        bg=bg_secondary,
                        fg=fg_primary,
                        insertbackground=fg_primary,
                    )

                elif cls_name == "Text":
                    w.configure(
                        bg=bg_secondary,
                        fg=fg_primary,
                        insertbackground=fg_primary,
                    )

                elif cls_name == "Listbox":
                    w.configure(
                        bg=bg_secondary,
                        fg=fg_primary,
                        selectbackground=bg_tertiary,
                        selectforeground=accent,
                    )

                elif cls_name == "Radiobutton":
                    w.configure(
                        bg=bg_primary,
                        fg=fg_primary,
                        selectcolor=bg_tertiary,
                        activebackground=bg_primary,
                    )

                elif cls_name == "Checkbutton":
                    w.configure(
                        bg=bg_primary,
                        fg=fg_primary,
                        selectcolor=bg_tertiary,
                    )

                elif cls_name == "Labelframe":
                    w.configure(
                        bg=bg_primary,
                        fg=accent,
                    )

                elif cls_name == "Canvas":
                    # Skip the HUD canvas (transparent); only touch regular canvases
                    cur_bg = str(w.cget("bg"))
                    if cur_bg.lower() != "#f0abcd":
                        w.configure(bg=bg_secondary)

                elif cls_name == "Menu":
                    w.configure(
                        bg=bg_secondary,
                        fg=fg_primary,
                        activebackground=bg_tertiary,
                        activeforeground=accent_fg,
                    )

                elif cls_name == "Panedwindow":
                    w.configure(bg=bg_primary)

            except tk.TclError:
                # Widget may have been destroyed mid-iteration or option
                # is unsupported on this platform; skip silently.
                pass

            # Recurse into children
            self._recolor_widget_tree(w, theme)

    # -- Wallpaper ----------------------------------------------------------

    def _apply_wallpaper(self, theme: Dict[str, Any]) -> None:
        """Set or remove a tiled/stretched background image on Toplevel windows.

        The image path comes from ``theme["wallpaper_path"]``.  If the key is
        empty or the file cannot be loaded (or Pillow is missing), any existing
        wallpaper is removed gracefully.
        """
        wallpaper_path = theme.get("wallpaper_path", "")

        # Collect Toplevel windows that should receive a wallpaper.
        targets: list[tk.Toplevel] = []
        if self._settings_win is not None:
            try:
                win = self._settings_win.win
                if win is not None and win.winfo_exists():
                    targets.append(win)
            except (AttributeError, tk.TclError):
                pass
        if self._history_win is not None:
            try:
                win = self._history_win.win
                if win is not None and win.winfo_exists():
                    targets.append(win)
            except (AttributeError, tk.TclError):
                pass

        if not wallpaper_path or Image is None or ImageTk is None:
            # Remove existing wallpaper labels
            self._remove_wallpapers(targets)
            return

        # Try to load the image once, then tile onto each target.
        try:
            img = Image.open(wallpaper_path)
        except Exception:
            log.debug("Could not load wallpaper from %s", wallpaper_path, exc_info=True)
            self._remove_wallpapers(targets)
            return

        for win in targets:
            try:
                w = win.winfo_width()
                h = win.winfo_height()
                if w < 2 or h < 2:
                    continue

                resized = img.resize((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(resized)

                # Re-use or create the wallpaper label
                wid = id(win)
                tag = "_theme_wallpaper"
                wp_lbl: Optional[tk.Label] = getattr(win, tag, None)
                if wp_lbl is not None and wp_lbl.winfo_exists():
                    wp_lbl.configure(image=photo)
                else:
                    wp_lbl = tk.Label(win, image=photo, borderwidth=0)
                    wp_lbl.place(x=0, y=0, relwidth=1.0, relheight=1.0)
                    wp_lbl.lower()  # send behind all other widgets
                    setattr(win, tag, wp_lbl)

                # Keep a strong reference to prevent GC of PhotoImage
                self._wallpaper_images[wid] = photo
            except Exception:
                log.debug("Wallpaper apply failed for %s", win, exc_info=True)

    def _remove_wallpapers(self, targets: list) -> None:
        """Destroy wallpaper labels and release PhotoImage references."""
        tag = "_theme_wallpaper"
        for win in targets:
            try:
                wp_lbl = getattr(win, tag, None)
                if wp_lbl is not None and wp_lbl.winfo_exists():
                    wp_lbl.destroy()
                setattr(win, tag, None)
                wid = id(win)
                self._wallpaper_images.pop(wid, None)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
theme_applicator = ThemeApplicator()
