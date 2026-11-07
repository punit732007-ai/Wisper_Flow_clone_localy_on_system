"""
LocalWhisper Pro — Theme & Customization Window
Interactive theme gallery, custom theme palette creator, HUD layout picker,
and wallpaper customization manager.
"""

import os
import shutil
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from config import config, APP_DIR
from ui.theme_engine import theme_manager, BUILTIN_THEMES
from ui.theme_applicator import theme_applicator

WALLPAPERS_DIR = APP_DIR / "wallpapers"
WALLPAPERS_DIR.mkdir(parents=True, exist_ok=True)


class ThemeWindow:
    """Comprehensive Theme Gallery & App Customization Dialog."""

    def __init__(self, parent_root: tk.Tk, on_theme_changed: Optional[Callable[[], None]] = None):
        self.parent = parent_root
        self.on_theme_changed = on_theme_changed
        self.win: Optional[tk.Toplevel] = None
        self._thumbnail_img = None
        self._custom_color_vars: Dict[str, tk.StringVar] = {}
        self._custom_color_buttons: Dict[str, tk.Button] = {}
        self._filter_category = "All"

    def show(self) -> None:
        """Open or focus the Theme & Customization window."""
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return

        theme = theme_manager.current_theme

        self.win = tk.Toplevel(self.parent)
        self.win.title("LocalWhisper Pro — Themes & Customization")
        self.win.geometry("980x680")
        self.win.minsize(860, 580)
        self.win.configure(bg=theme["bg_primary"])

        # Top Banner
        top_bar = tk.Frame(self.win, bg=theme["bg_secondary"], padx=18, pady=14)
        top_bar.pack(fill="x")

        title_lbl = tk.Label(
            top_bar,
            text="🎨 Themes & Appearance Studio",
            bg=theme["bg_secondary"],
            fg=theme["fg_primary"],
            font=(theme.get("font_family", "Segoe UI"), 14, "bold"),
        )
        title_lbl.pack(side="left")

        self.active_badge_lbl = tk.Label(
            top_bar,
            text=f"Active Theme: {theme.get('name', 'Default Dark')}",
            bg=theme["bg_tertiary"],
            fg=theme["accent"],
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            padx=10,
            pady=4,
        )
        self.active_badge_lbl.pack(side="right")

        # Main Split Layout: Left Navigation / Right Content
        main_paned = tk.Frame(self.win, bg=theme["bg_primary"])
        main_paned.pack(fill="both", expand=True, padx=12, pady=10)

        # Left Sidebar (Categories)
        sidebar = tk.Frame(main_paned, bg=theme["bg_secondary"], width=210, padx=8, pady=10)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        cat_lbl = tk.Label(
            sidebar,
            text="CATEGORIES",
            bg=theme["bg_secondary"],
            fg=theme["fg_secondary"],
            font=(theme.get("font_family", "Segoe UI"), 8, "bold"),
            anchor="w",
        )
        cat_lbl.pack(fill="x", pady=(4, 8), padx=6)

        self.categories = [
            ("All", "🌟 All Themes (35+)"),
            ("Design & Art", "🏛️ Design & Art"),
            ("Lifestyle & Culture", "🌿 Lifestyle & Culture"),
            ("Tech & Futurism", "🚀 Tech & Futurism"),
            ("Retro & Nostalgia", "🕹️ Retro & Nostalgia"),
            ("Modern UI", "📱 Modern UI"),
            ("Glass & Special", "✨ Glass & Special"),
            ("Custom Theme", "🛠️ Custom Palette"),
            ("App Layout & Wallpaper", "🖼️ Layout & Wallpaper"),
        ]

        self.category_buttons = {}
        for cat_key, cat_label in self.categories:
            btn = tk.Button(
                sidebar,
                text=cat_label,
                bg=theme["bg_tertiary"] if cat_key == self._filter_category else theme["bg_secondary"],
                fg=theme["accent"] if cat_key == self._filter_category else theme["fg_primary"],
                activebackground=theme["bg_tertiary"],
                activeforeground=theme["accent"],
                font=(theme.get("font_family", "Segoe UI"), 9),
                anchor="w",
                padx=10,
                pady=6,
                relief="flat",
                command=lambda k=cat_key: self._on_select_category(k),
            )
            btn.pack(fill="x", pady=2)
            self.category_buttons[cat_key] = btn

        # Right Content Container
        self.content_container = tk.Frame(main_paned, bg=theme["bg_primary"])
        self.content_container.pack(side="right", fill="both", expand=True)

        # Bottom Action Bar
        bottom_bar = tk.Frame(self.win, bg=theme["bg_secondary"], height=48, padx=16, pady=8)
        bottom_bar.pack(fill="x", side="bottom")

        status_lbl = tk.Label(
            bottom_bar,
            text="💡 Tip: Selected theme is saved automatically and applied immediately to the Floating HUD.",
            bg=theme["bg_secondary"],
            fg=theme["fg_secondary"],
            font=(theme.get("font_family", "Segoe UI"), 8),
        )
        status_lbl.pack(side="left")

        close_btn = tk.Button(
            bottom_bar,
            text="Done / Close",
            bg=theme["accent"],
            fg=theme.get("accent_fg", "#11111b"),
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            padx=18,
            pady=4,
            relief="flat",
            command=self.win.destroy,
        )
        close_btn.pack(side="right")

        # Initial Render of Active Category
        self._render_active_view()

    # ─────────────────────────────────────────────────────────────────────────
    # Category Routing & View Switcher
    # ─────────────────────────────────────────────────────────────────────────

    def _on_select_category(self, cat_key: str) -> None:
        self._filter_category = cat_key
        theme = theme_manager.current_theme

        # Update sidebar button highlights
        for k, btn in self.category_buttons.items():
            if k == cat_key:
                btn.configure(bg=theme["bg_tertiary"], fg=theme["accent"], font=(theme.get("font_family", "Segoe UI"), 9, "bold"))
            else:
                btn.configure(bg=theme["bg_secondary"], fg=theme["fg_primary"], font=(theme.get("font_family", "Segoe UI"), 9))

        self._render_active_view()

    def _render_active_view(self) -> None:
        """Render either the gallery grid, custom theme editor, or layout customizer."""
        for child in self.content_container.winfo_children():
            child.destroy()

        if self._filter_category == "Custom Theme":
            self._render_custom_theme_editor()
        elif self._filter_category == "App Layout & Wallpaper":
            self._render_layout_wallpaper_editor()
        else:
            self._render_theme_gallery()

    # ─────────────────────────────────────────────────────────────────────────
    # View 1: Theme Gallery Grid
    # ─────────────────────────────────────────────────────────────────────────

    def _render_theme_gallery(self) -> None:
        theme = theme_manager.current_theme

        # Search / Count Header
        header_frame = tk.Frame(self.content_container, bg=theme["bg_primary"])
        header_frame.pack(fill="x", pady=(0, 8))

        all_themes = theme_manager.all_themes
        filtered_keys = []

        if self._filter_category == "All":
            filtered_keys = list(all_themes.keys())
        else:
            filtered_keys = [k for k, t in all_themes.items() if t.get("category") == self._filter_category]

        count_lbl = tk.Label(
            header_frame,
            text=f"Showing {len(filtered_keys)} Theme(s) — Click 'Apply' to instantly preview",
            bg=theme["bg_primary"],
            fg=theme["fg_secondary"],
            font=(theme.get("font_family", "Segoe UI"), 9),
        )
        count_lbl.pack(side="left")

        # Scrollable Canvas
        canvas_frame = tk.Frame(self.content_container, bg=theme["bg_primary"])
        canvas_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_frame, bg=theme["bg_primary"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=theme["bg_primary"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel binding
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Grid of Theme Cards: 2 or 3 cards per row
        cols = 2
        for i, key in enumerate(filtered_keys):
            th = all_themes[key]
            row = i // cols
            col = i % cols
            self._build_theme_card(scrollable_frame, key, th, row, col)

    def _build_theme_card(self, parent: tk.Frame, key: str, th: Dict[str, Any], row: int, col: int) -> None:
        current_active = (key == theme_manager.current_theme_key)
        app_th = theme_manager.current_theme

        card_border = app_th["accent"] if current_active else app_th["border"]
        card_bg = app_th["bg_secondary"]

        card = tk.Frame(
            parent,
            bg=card_bg,
            highlightbackground=card_border,
            highlightthickness=2 if current_active else 1,
            padx=12,
            pady=10,
        )
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        # Card Title Row
        title_row = tk.Frame(card, bg=card_bg)
        title_row.pack(fill="x", pady=(0, 4))

        name_text = th.get("name", key)
        if current_active:
            name_text = "✓ " + name_text

        name_lbl = tk.Label(
            title_row,
            text=name_text,
            bg=card_bg,
            fg=app_th["accent"] if current_active else app_th["fg_primary"],
            font=(app_th.get("font_family", "Segoe UI"), 10, "bold"),
            anchor="w",
        )
        name_lbl.pack(side="left")

        cat_badge = tk.Label(
            title_row,
            text=th.get("category", ""),
            bg=app_th["bg_tertiary"],
            fg=app_th["fg_secondary"],
            font=(app_th.get("font_family", "Segoe UI"), 7),
            padx=6,
            pady=1,
        )
        cat_badge.pack(side="right")

        # Color Palette Swatches Preview (5 distinct colored rectangles)
        swatch_frame = tk.Frame(card, bg=card_bg, height=22)
        swatch_frame.pack(fill="x", pady=(4, 6))

        palette = [
            ("BG", th.get("bg_primary", "#000000")),
            ("Panel", th.get("bg_secondary", "#222222")),
            ("Accent", th.get("accent", "#89b4fa")),
            ("Text", th.get("fg_primary", "#ffffff")),
            ("Status", th.get("success", "#52b788")),
            ("Alert", th.get("error", "#ff5555")),
        ]

        for _, color_hex in palette:
            color_box = tk.Frame(swatch_frame, bg=color_hex, width=28, height=18, highlightbackground=app_th["border"], highlightthickness=1)
            color_box.pack(side="left", padx=2, fill="y", expand=True)

        # Description
        desc_lbl = tk.Label(
            card,
            text=th.get("description", ""),
            bg=card_bg,
            fg=app_th["fg_secondary"],
            font=(app_th.get("font_family", "Segoe UI"), 8),
            wraplength=340,
            justify="left",
            anchor="w",
        )
        desc_lbl.pack(fill="x", pady=(2, 8))

        # Bottom Apply Button
        btn_text = "Active Theme" if current_active else "Apply Theme"
        btn_bg = app_th["accent"] if current_active else app_th["bg_tertiary"]
        btn_fg = app_th.get("accent_fg", "#11111b") if current_active else app_th["fg_primary"]

        apply_btn = tk.Button(
            card,
            text=btn_text,
            bg=btn_bg,
            fg=btn_fg,
            activebackground=app_th["accent_hover"],
            activeforeground=app_th.get("accent_fg", "#11111b"),
            font=(app_th.get("font_family", "Segoe UI"), 8, "bold" if current_active else "normal"),
            relief="flat",
            padx=12,
            pady=3,
            command=lambda k=key: self._apply_theme(k),
        )
        apply_btn.pack(anchor="e")

    def _apply_theme(self, theme_key: str) -> None:
        """Switch theme immediately and refresh UI."""
        theme_manager.set_theme(theme_key)
        theme_applicator.apply_current_theme()

        theme = theme_manager.current_theme
        if self.win and self.win.winfo_exists():
            self.win.configure(bg=theme["bg_primary"])
            if hasattr(self, "active_badge_lbl"):
                self.active_badge_lbl.configure(
                    text=f"Active Theme: {theme.get('name', theme_key)}",
                    bg=theme["bg_tertiary"],
                    fg=theme["accent"],
                )

        if self.on_theme_changed:
            self.on_theme_changed()

        self._render_active_view()

    # ─────────────────────────────────────────────────────────────────────────
    # View 2: Custom Theme Palette Creator
    # ─────────────────────────────────────────────────────────────────────────

    def _render_custom_theme_editor(self) -> None:
        theme = theme_manager.current_theme
        curr_custom = theme_manager.all_themes.get("custom", theme)

        container = tk.Frame(self.content_container, bg=theme["bg_primary"], padx=8, pady=4)
        container.pack(fill="both", expand=True)

        header = tk.Label(
            container,
            text="🛠️ Custom Color Palette Designer",
            bg=theme["bg_primary"],
            fg=theme["accent"],
            font=(theme.get("font_family", "Segoe UI"), 12, "bold"),
            anchor="w",
        )
        header.pack(fill="x", pady=(0, 4))

        sub_desc = tk.Label(
            container,
            text="Pick custom colors for your application. Click on any color button to open the system color chooser.",
            bg=theme["bg_primary"],
            fg=theme["fg_secondary"],
            font=(theme.get("font_family", "Segoe UI"), 8),
            anchor="w",
        )
        sub_desc.pack(fill="x", pady=(0, 10))

        # Color Editor Groups
        color_groups = [
            ("Window & Panels", [
                ("bg_primary", "Window Background"),
                ("bg_secondary", "Secondary Panels / Sidebar"),
                ("bg_tertiary", "Cards / Input Fields"),
                ("border", "Border & Divider Outlines"),
            ]),
            ("Typography & Accents", [
                ("fg_primary", "Primary Text Color"),
                ("fg_secondary", "Muted / Secondary Text"),
                ("accent", "Accent Buttons & Highlights"),
                ("accent_hover", "Accent Hover State"),
            ]),
            ("Floating HUD States", [
                ("hud_bg", "HUD Pill Background"),
                ("hud_border", "HUD Pill Border Outline"),
                ("hud_dot_ready", "Ready Status Indicator"),
                ("hud_dot_recording", "Recording Mic Indicator"),
                ("hud_dot_processing", "Processing / AI Indicator"),
                ("hud_dot_success", "Success / Pasted Indicator"),
            ]),
        ]

        self._custom_color_vars = {}
        self._custom_color_buttons = {}

        panes_frame = tk.Frame(container, bg=theme["bg_primary"])
        panes_frame.pack(fill="both", expand=True)

        for col_idx, (group_title, fields) in enumerate(color_groups):
            grp_frame = tk.LabelFrame(
                panes_frame,
                text=f" {group_title} ",
                bg=theme["bg_secondary"],
                fg=theme["accent"],
                font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
                padx=10,
                pady=10,
            )
            grp_frame.pack(side="left", fill="both", expand=True, padx=4)

            for key, label_text in fields:
                field_row = tk.Frame(grp_frame, bg=theme["bg_secondary"])
                field_row.pack(fill="x", pady=4)

                val = curr_custom.get(key, theme.get(key, "#89b4fa"))
                var = tk.StringVar(value=val)
                self._custom_color_vars[key] = var

                lbl = tk.Label(
                    field_row,
                    text=label_text,
                    bg=theme["bg_secondary"],
                    fg=theme["fg_primary"],
                    font=(theme.get("font_family", "Segoe UI"), 8),
                    anchor="w",
                )
                lbl.pack(anchor="w")

                sub_row = tk.Frame(field_row, bg=theme["bg_secondary"])
                sub_row.pack(fill="x", pady=(2, 0))

                # Color swatch button
                btn = tk.Button(
                    sub_row,
                    bg=val,
                    width=4,
                    height=1,
                    relief="solid",
                    borderwidth=1,
                    command=lambda k=key: self._pick_color(k),
                )
                btn.pack(side="left", padx=(0, 6))
                self._custom_color_buttons[key] = btn

                # Hex Entry
                entry = tk.Entry(
                    sub_row,
                    textvariable=var,
                    bg=theme["bg_tertiary"],
                    fg=theme["fg_primary"],
                    insertbackground=theme["fg_primary"],
                    font=(theme.get("font_family", "Consolas"), 8),
                    width=10,
                )
                entry.pack(side="left")

        # Bottom Buttons
        btn_bar = tk.Frame(container, bg=theme["bg_primary"])
        btn_bar.pack(fill="x", pady=(14, 0))

        save_btn = tk.Button(
            btn_bar,
            text="💾 Save & Apply Custom Theme",
            bg=theme["accent"],
            fg=theme.get("accent_fg", "#11111b"),
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            padx=16,
            pady=6,
            relief="flat",
            command=self._save_custom_theme,
        )
        save_btn.pack(side="right")

        reset_btn = tk.Button(
            btn_bar,
            text="↺ Reset to Mocha Defaults",
            bg=theme["bg_secondary"],
            fg=theme["fg_secondary"],
            font=(theme.get("font_family", "Segoe UI"), 8),
            padx=12,
            pady=6,
            relief="flat",
            command=self._reset_custom_to_default,
        )
        reset_btn.pack(side="left")

    def _pick_color(self, key: str) -> None:
        """Open system color chooser dialog."""
        curr_hex = self._custom_color_vars[key].get()
        chosen = colorchooser.askcolor(color=curr_hex, title=f"Choose Color for {key}")
        if chosen and chosen[1]:
            new_hex = chosen[1]
            self._custom_color_vars[key].set(new_hex)
            if key in self._custom_color_buttons:
                self._custom_color_buttons[key].configure(bg=new_hex)

    def _save_custom_theme(self) -> None:
        """Extract all chosen colors and activate custom theme."""
        overrides = {}
        for key, var in self._custom_color_vars.items():
            hex_val = var.get().strip()
            if hex_val.startswith("#") and (len(hex_val) == 7 or len(hex_val) == 4):
                overrides[key] = hex_val

        theme_manager.set_custom_theme(overrides)
        theme_applicator.apply_current_theme()

        if self.on_theme_changed:
            self.on_theme_changed()

        messagebox.showinfo("Custom Theme", "Your custom theme has been saved and applied successfully!")
        self._apply_theme("custom")

    def _reset_custom_to_default(self) -> None:
        """Reset custom values back to default dark palette."""
        def_dark = BUILTIN_THEMES["default_dark"]
        for key, var in self._custom_color_vars.items():
            if key in def_dark:
                var.set(def_dark[key])
                if key in self._custom_color_buttons:
                    self._custom_color_buttons[key].configure(bg=def_dark[key])

    # ─────────────────────────────────────────────────────────────────────────
    # View 3: App Layout & Wallpaper Customization
    # ─────────────────────────────────────────────────────────────────────────

    def _render_layout_wallpaper_editor(self) -> None:
        theme = theme_manager.current_theme

        container = tk.Frame(self.content_container, bg=theme["bg_primary"], padx=8, pady=4)
        container.pack(fill="both", expand=True)

        header = tk.Label(
            container,
            text="🖼️ App Layout & Wallpaper Studio",
            bg=theme["bg_primary"],
            fg=theme["accent"],
            font=(theme.get("font_family", "Segoe UI"), 12, "bold"),
            anchor="w",
        )
        header.pack(fill="x", pady=(0, 10))

        # Section 1: HUD Layout Picker
        layout_box = tk.LabelFrame(
            container,
            text=" 📐 Floating HUD Layout Style ",
            bg=theme["bg_secondary"],
            fg=theme["accent"],
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            padx=14,
            pady=12,
        )
        layout_box.pack(fill="x", pady=(0, 12))

        self.layout_var = tk.StringVar(value=config.get("hud_layout", "compact_pill"))

        layouts = [
            ("compact_pill", "Compact Pill (270×48) — Sleek curved capsule with visualizer bars"),
            ("classic_bar", "Classic Dock Bar (320×42) — Horizontal dock with sharp pill corners"),
            ("expanded_card", "Expanded Island (300×64) — Larger pill with full mode badge & waveform"),
            ("minimal_dot", "Minimal Dot (180×38) — Ultra-small distraction-free indicator"),
        ]

        for val, lbl_text in layouts:
            r = tk.Radiobutton(
                layout_box,
                text=lbl_text,
                variable=self.layout_var,
                value=val,
                bg=theme["bg_secondary"],
                fg=theme["fg_primary"],
                selectcolor=theme["bg_tertiary"],
                activebackground=theme["bg_secondary"],
                font=(theme.get("font_family", "Segoe UI"), 9),
                command=self._on_layout_selected,
            )
            r.pack(anchor="w", pady=3)

        # Section 2: Custom Wallpaper
        wp_box = tk.LabelFrame(
            container,
            text=" 🌄 Custom App Wallpaper ",
            bg=theme["bg_secondary"],
            fg=theme["accent"],
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            padx=14,
            pady=12,
        )
        wp_box.pack(fill="x", pady=(0, 12))

        wp_row = tk.Frame(wp_box, bg=theme["bg_secondary"])
        wp_row.pack(fill="x")

        # Thumbnail canvas preview
        self.wp_canvas = tk.Canvas(
            wp_row,
            width=120,
            height=70,
            bg=theme["bg_tertiary"],
            highlightbackground=theme["border"],
            highlightthickness=1,
        )
        self.wp_canvas.pack(side="left", padx=(0, 14))

        wp_actions = tk.Frame(wp_row, bg=theme["bg_secondary"])
        wp_actions.pack(side="left", fill="both", expand=True)

        current_wp = config.get("wallpaper_path", "")
        self.wp_path_lbl = tk.Label(
            wp_actions,
            text=f"Current: {Path(current_wp).name if current_wp else 'None (Clean solid background)'}",
            bg=theme["bg_secondary"],
            fg=theme["fg_primary"],
            font=(theme.get("font_family", "Segoe UI"), 8),
            anchor="w",
        )
        self.wp_path_lbl.pack(fill="x", pady=(0, 6))

        btn_wp_frame = tk.Frame(wp_actions, bg=theme["bg_secondary"])
        btn_wp_frame.pack(fill="x")

        choose_wp_btn = tk.Button(
            btn_wp_frame,
            text="📁 Select Image File...",
            bg=theme["accent"],
            fg=theme.get("accent_fg", "#11111b"),
            font=(theme.get("font_family", "Segoe UI"), 8, "bold"),
            padx=10,
            pady=3,
            relief="flat",
            command=self._choose_wallpaper_file,
        )
        choose_wp_btn.pack(side="left", padx=(0, 8))

        clear_wp_btn = tk.Button(
            btn_wp_frame,
            text="Remove Wallpaper",
            bg=theme["bg_tertiary"],
            fg=theme["fg_secondary"],
            font=(theme.get("font_family", "Segoe UI"), 8),
            padx=10,
            pady=3,
            relief="flat",
            command=self._clear_wallpaper,
        )
        clear_wp_btn.pack(side="left")

        # Update thumbnail preview
        self._update_wp_thumbnail(current_wp)

        # Section 3: Font Family & HUD Sizing
        font_box = tk.LabelFrame(
            container,
            text=" 🔤 Font Family & HUD Scale ",
            bg=theme["bg_secondary"],
            fg=theme["accent"],
            font=(theme.get("font_family", "Segoe UI"), 9, "bold"),
            padx=14,
            pady=12,
        )
        font_box.pack(fill="x")

        f_row = tk.Frame(font_box, bg=theme["bg_secondary"])
        f_row.pack(fill="x", pady=2)

        tk.Label(
            f_row,
            text="Typography Font:",
            bg=theme["bg_secondary"],
            fg=theme["fg_primary"],
            font=(theme.get("font_family", "Segoe UI"), 9),
        ).pack(side="left", padx=(0, 8))

        self.font_var = tk.StringVar(value=config.get("font_family", "Segoe UI"))
        font_combo = ttk.Combobox(
            f_row,
            textvariable=self.font_var,
            values=["Segoe UI", "Cascadia Code", "Consolas", "Roboto", "Helvetica", "Arial", "Georgia", "Courier New", "Impact"],
            state="readonly",
            width=20,
        )
        font_combo.pack(side="left", padx=(0, 20))
        font_combo.bind("<<ComboboxSelected>>", self._on_font_changed)

    def _on_layout_selected(self) -> None:
        """Update and persist chosen HUD layout mode."""
        chosen = self.layout_var.get()
        config.set("hud_layout", chosen)
        # Apply layout dynamically to HUD if active
        if theme_applicator._hud and hasattr(theme_applicator._hud, "set_layout"):
            theme_applicator._hud.set_layout(chosen)

    def _choose_wallpaper_file(self) -> None:
        """Pick image file, copy to wallpaper cache, and apply."""
        file_path = filedialog.askopenfilename(
            title="Select Custom Wallpaper Image",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif"),
                ("All Files", "*.*"),
            ],
        )
        if not file_path:
            return

        try:
            dest_file = WALLPAPERS_DIR / Path(file_path).name
            shutil.copy2(file_path, dest_file)
            saved_path = str(dest_file)

            config.set("wallpaper_path", saved_path)
            # Update custom theme or active theme wallpaper path
            theme_manager.current_theme["wallpaper_path"] = saved_path

            self.wp_path_lbl.configure(text=f"Current: {Path(saved_path).name}")
            self._update_wp_thumbnail(saved_path)

            theme_applicator.apply_current_theme()
            messagebox.showinfo("Wallpaper Applied", "Wallpaper has been successfully updated and applied!")
        except Exception as e:
            messagebox.showerror("Wallpaper Error", f"Failed to load image: {e}")

    def _clear_wallpaper(self) -> None:
        """Remove active wallpaper and revert to solid theme background."""
        config.set("wallpaper_path", "")
        theme_manager.current_theme["wallpaper_path"] = ""
        self.wp_path_lbl.configure(text="Current: None (Clean solid background)")
        self._update_wp_thumbnail("")
        theme_applicator.apply_current_theme()

    def _update_wp_thumbnail(self, img_path: str) -> None:
        """Render a small preview of the wallpaper in the canvas."""
        self.wp_canvas.delete("all")
        if not img_path or not os.path.exists(img_path) or Image is None or ImageTk is None:
            self.wp_canvas.create_text(60, 35, text="No Wallpaper", fill="#888888", font=("Segoe UI", 7))
            return

        try:
            pil_img = Image.open(img_path)
            pil_img.thumbnail((120, 70), Image.LANCZOS)
            self._thumbnail_img = ImageTk.PhotoImage(pil_img)
            self.wp_canvas.create_image(60, 35, image=self._thumbnail_img)
        except Exception:
            self.wp_canvas.create_text(60, 35, text="Preview Error", fill="#ff5555", font=("Segoe UI", 7))

    def _on_font_changed(self, event=None) -> None:
        """Update system font family across theme."""
        font_name = self.font_var.get()
        config.set("font_family", font_name)
        theme_manager.current_theme["font_family"] = font_name
        theme_applicator.apply_current_theme()
