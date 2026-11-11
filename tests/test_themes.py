"""
LocalWhisper Pro — Unit Tests for 35+ Aesthetic Themes & Customization Engine
Validates all theme schemas, color codes, category assignments, custom palette
customization, layout presets, and theme applicator state mapping.
"""

import unittest
import re
from unittest.mock import patch
from config import config
from ui.theme_engine import theme_manager, BUILTIN_THEMES
from ui.theme_applicator import theme_applicator, _build_hud_states
from ui.floating_hud import HUD_LAYOUTS

HEX_COLOR_PATTERN = re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3}|[A-Fa-f0-9]{8})$")


class TestThemeEngine(unittest.TestCase):
    """Test suite for ThemeEngine and theme definitions."""

    REQUIRED_KEYS = [
        "name", "category", "description",
        "bg_primary", "bg_secondary", "bg_tertiary",
        "fg_primary", "fg_secondary", "fg_accent",
        "accent", "accent_hover", "accent_fg",
        "success", "warning", "error", "info",
        "hud_bg", "hud_border", "hud_dot_ready",
        "hud_dot_recording", "hud_dot_processing",
        "hud_dot_success", "hud_dot_error",
        "border", "separator",
    ]

    REQUIRED_THEMES = [
        "default_dark",
        "minimalism",
        "maximalism",
        "brutalism",
        "cottagecore",
        "dark_academia",
        "industrial",
        "corporate_memphis",
        "solarpunk",
        "glitch_core",
        "bauhaus",
        "swiss_design",
        "art_deco",
        "art_nouveau",
        "pop_art",
        "psychedelic",
        "mid_century_modern",
        "victorian",
        "vaporwave",
        "synthwave_outrun",
        "y2k_aesthetic",
        "retro_futurism",
        "pixel_art_8bit",
        "steampunk",
        "cyberpunk",
        "acid_graphics",
        "flat_design",
        "material_design",
        "neo_brutalism",
        "skeuomorphism",
        "dark_mode",
        "minimalist_ui",
        "complexion_reduction",
        "glassmorphism",
        "liquid_glass",
    ]

    def test_all_required_themes_exist(self):
        """Ensure all 34 user-requested themes plus default_dark are registered."""
        all_themes = theme_manager.all_themes
        for th_key in self.REQUIRED_THEMES:
            self.assertIn(
                th_key, all_themes,
                f"Theme '{th_key}' is missing from theme_manager"
            )

    def test_theme_color_keys_validity(self):
        """Ensure all themes have required keys and valid hex colors."""
        for th_key, th in BUILTIN_THEMES.items():
            for req_key in self.REQUIRED_KEYS:
                self.assertIn(req_key, th, f"Theme '{th_key}' missing key '{req_key}'")

            # Check that color properties match hex color format
            color_keys = [
                "bg_primary", "bg_secondary", "bg_tertiary",
                "fg_primary", "fg_secondary", "fg_accent",
                "accent", "accent_hover", "accent_fg",
                "success", "warning", "error", "info",
                "hud_bg", "hud_border", "hud_dot_ready",
                "hud_dot_recording", "hud_dot_processing",
                "hud_dot_success", "hud_dot_error",
                "border", "separator",
            ]
            for ck in color_keys:
                val = th[ck]
                self.assertTrue(
                    HEX_COLOR_PATTERN.match(val),
                    f"Invalid hex color '{val}' for theme '{th_key}', key '{ck}'"
                )

    def test_theme_switching(self):
        """Test switching active theme updates current_theme and persists."""
        theme_manager.set_theme("cyberpunk", auto_save=False)
        self.assertEqual(theme_manager.current_theme_key, "cyberpunk")
        self.assertEqual(theme_manager.current_theme["accent"], "#ff007f")

        theme_manager.set_theme("vaporwave", auto_save=False)
        self.assertEqual(theme_manager.current_theme_key, "vaporwave")
        self.assertEqual(theme_manager.current_theme["accent"], "#01cdfe")

        # Reset to default
        theme_manager.set_theme("default_dark", auto_save=False)
        self.assertEqual(theme_manager.current_theme_key, "default_dark")

    def test_custom_theme_authoring(self):
        """Test user custom theme overrides."""
        custom_palette = {
            "accent": "#ff1122",
            "bg_primary": "#010203",
            "hud_bg": "#102030",
        }
        theme_manager.set_custom_theme(custom_palette, auto_save=False)
        self.assertEqual(theme_manager.current_theme_key, "custom")
        self.assertEqual(theme_manager.current_theme["accent"], "#ff1122")
        self.assertEqual(theme_manager.current_theme["bg_primary"], "#010203")
        self.assertEqual(theme_manager.current_theme["hud_bg"], "#102030")

    def test_hud_states_builder(self):
        """Test that HUD states dictionary is generated correctly from theme."""
        th = BUILTIN_THEMES["cyberpunk"]
        states = _build_hud_states(th)
        self.assertIn("ready", states)
        self.assertIn("recording", states)
        self.assertIn("processing", states)
        self.assertIn("success", states)
        self.assertIn("error", states)

        self.assertEqual(states["ready"]["dot_color"], th["hud_dot_ready"])
        self.assertEqual(states["recording"]["dot_color"], th["hud_dot_recording"])
        self.assertEqual(states["processing"]["dot_color"], th["hud_dot_processing"])

    def test_hud_layouts_presets(self):
        """Test that all HUD layout styles have valid dimensions."""
        expected_layouts = ["compact_pill", "classic_bar", "expanded_card", "minimal_dot"]
        for lay in expected_layouts:
            self.assertIn(lay, HUD_LAYOUTS)
            cfg = HUD_LAYOUTS[lay]
            self.assertGreater(cfg["width"], 150)
            self.assertGreater(cfg["height"], 30)
            self.assertGreater(cfg["radius"], 0)

    def test_theme_callbacks(self):
        """Test that callbacks are invoked when theme changes."""
        called = []

        def _on_change():
            called.append(True)

        theme_manager.register_callback(_on_change)
        theme_manager.set_theme("solarpunk", auto_save=False)
        self.assertTrue(len(called) > 0, "Theme callback was not invoked")

    def test_glassmorphic_palettes_and_specular(self):
        """Validate curated frosted glass palettes and specular highlight values."""
        for th_key in ["glassmorphism", "liquid_glass"]:
            self.assertIn(th_key, BUILTIN_THEMES)
            th = BUILTIN_THEMES[th_key]
            for req_key in self.REQUIRED_KEYS:
                self.assertIn(req_key, th, f"Theme '{th_key}' missing required key '{req_key}'")
            self.assertIn("hud_specular", th)
            self.assertTrue(
                HEX_COLOR_PATTERN.match(th["hud_specular"]),
                f"Invalid specular hex '{th['hud_specular']}' in '{th_key}'"
            )

        glass = BUILTIN_THEMES["glassmorphism"]
        self.assertEqual(glass["bg_primary"], "#0b111e")
        self.assertEqual(glass["bg_secondary"], "#111d2e")
        self.assertEqual(glass["hud_bg"], "#0f1a2c")
        self.assertEqual(glass["hud_border"], "#38bdf8")
        self.assertEqual(glass["hud_specular"], "#bae6fd")
        self.assertEqual(glass["hud_badge_bg"], "#1c2d44")
        self.assertEqual(glass["hud_badge_fg"], "#f0f8ff")
        self.assertEqual(glass["accent"], "#38bdf8")

        liquid = BUILTIN_THEMES["liquid_glass"]
        self.assertEqual(liquid["bg_primary"], "#02161e")
        self.assertEqual(liquid["bg_secondary"], "#062734")
        self.assertEqual(liquid["hud_bg"], "#04202b")
        self.assertEqual(liquid["hud_border"], "#06b6d4")
        self.assertEqual(liquid["hud_specular"], "#a5f3fc")
        self.assertEqual(liquid["hud_badge_bg"], "#08384a")
        self.assertEqual(liquid["hud_badge_fg"], "#e0fdf4")
        self.assertEqual(liquid["accent"], "#00f2fe")

        # Test specular highlight in _build_hud_states
        states_glass = _build_hud_states(glass)
        for st_name in ["loading", "ready", "recording", "processing", "success", "error"]:
            self.assertIn("specular", states_glass[st_name])
        self.assertEqual(states_glass["ready"]["specular"], glass["hud_specular"])

    def test_hud_transparency_invariants(self):
        """Ensure FloatingHUD adheres to Windows Tkinter transparency invariants."""
        from ui.floating_hud import FloatingHUD, TRANSPARENT_COLOR
        from pathlib import Path

        self.assertEqual(TRANSPARENT_COLOR, "#f0abcd")

        # Verify source code constraint: no wm_attributes("-alpha") on self.root
        hud_src_path = Path(__file__).resolve().parent.parent / "ui" / "floating_hud.py"
        with open(hud_src_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn('"-alpha"', src, "FloatingHUD must not set -alpha to avoid DWM black boxes")
        self.assertNotIn("'-alpha'", src, "FloatingHUD must not set -alpha to avoid DWM black boxes")

        # Verify runtime window attributes
        hud = FloatingHUD()
        try:
            self.assertEqual(str(hud.root.wm_attributes("-transparentcolor")), TRANSPARENT_COLOR)
            # Ensure -alpha is not combined with -transparentcolor
            alpha_val = float(hud.root.wm_attributes("-alpha"))
            self.assertAlmostEqual(alpha_val, 1.0, places=2)
        finally:
            hud.root.destroy()

    def test_hud_canvas_item_reuse_across_theme_switches(self):
        """Ensure HUD reuses canvas items via coords/itemconfig without deletion leaks."""
        from ui.floating_hud import FloatingHUD

        hud = FloatingHUD()
        theme_applicator.register_hud(hud)
        try:
            self.assertTrue(hasattr(hud, "pill_specular_id"))
            initial_items = sorted(hud.canvas.find_all())
            self.assertIn(hud.pill_specular_id, initial_items)
            self.assertIn(hud.pill_bg_id, initial_items)

            # Switch to Glassmorphism
            theme_manager.set_theme("glassmorphism", auto_save=False)
            items_after_glass = sorted(hud.canvas.find_all())
            self.assertEqual(initial_items, items_after_glass, "Canvas items modified/recreated during theme switch")
            self.assertEqual(hud.canvas.itemcget(hud.pill_specular_id, "fill"), "#bae6fd")

            # Switch to Liquid Glass
            theme_manager.set_theme("liquid_glass", auto_save=False)
            items_after_liquid = sorted(hud.canvas.find_all())
            self.assertEqual(initial_items, items_after_liquid, "Canvas items modified/recreated during theme switch")
            self.assertEqual(hud.canvas.itemcget(hud.pill_specular_id, "fill"), "#a5f3fc")

            # Test layout switching coords reuse without saving to disk
            with patch.object(config, "save"):
                for lay in ["compact_pill", "classic_bar", "expanded_card", "minimal_dot"]:
                    hud.set_layout(lay)
                    self.assertEqual(sorted(hud.canvas.find_all()), initial_items, f"Item leak in layout {lay}")
                    coords = hud.canvas.coords(hud.pill_specular_id)
                    self.assertEqual(len(coords), 4)
                    self.assertLess(coords[0], coords[2])
                    self.assertEqual(coords[1], 3.0)
                    self.assertEqual(coords[3], 3.0)
        finally:
            theme_applicator.register_hud(None)
            hud.root.destroy()
            theme_manager.set_theme("default_dark", auto_save=False)

    def test_visualizer_state_color_synchronization(self):
        """Ensure AudioVisualizerWidget synchronizes with active theme dot color across states on theme switch."""
        from ui.floating_hud import FloatingHUD
        from ui.visualizer_widget import AudioVisualizerWidget

        hud = FloatingHUD()
        theme_applicator.register_hud(hud)
        try:
            glass = BUILTIN_THEMES["glassmorphism"]
            liquid = BUILTIN_THEMES["liquid_glass"]

            state_key_map = {
                "ready": "hud_dot_ready",
                "recording": "hud_dot_recording",
                "processing": "hud_dot_processing",
                "success": "hud_dot_success",
                "error": "hud_dot_error",
            }

            for state, dot_key in state_key_map.items():
                hud.set_state(state)

                # Switch to Glassmorphism while in this state
                theme_manager.set_theme("glassmorphism", auto_save=False)
                self.assertEqual(
                    hud.visualizer.color,
                    glass[dot_key],
                    f"Glassmorphism visualizer color desync in state '{state}' (expected {glass[dot_key]}, got {hud.visualizer.color})"
                )

                # Switch to Liquid Glass while in this state
                theme_manager.set_theme("liquid_glass", auto_save=False)
                self.assertEqual(
                    hud.visualizer.color,
                    liquid[dot_key],
                    f"Liquid Glass visualizer color desync in state '{state}' (expected {liquid[dot_key]}, got {hud.visualizer.color})"
                )

            # Test standalone AudioVisualizerWidget fallback for error state
            vis = AudioVisualizerWidget(hud.canvas, 0, 0)
            vis.set_state("error")
            self.assertEqual(vis.color, "#ff4d6d", "Visualizer error fallback must be error red '#ff4d6d'")
        finally:
            theme_applicator.register_hud(None)
            hud.root.destroy()
            theme_manager.set_theme("default_dark", auto_save=False)

    def test_specular_highlight_state_preservation_on_theme_switch(self):
        """Ensure switching theme while in active states (e.g. recording) preserves the active state's specular highlight color."""
        from ui.floating_hud import FloatingHUD

        hud = FloatingHUD()
        theme_applicator.register_hud(hud)
        try:
            # Set HUD to recording state
            hud.set_state("recording")

            # Switch to Glassmorphism while in recording state
            theme_manager.set_theme("glassmorphism", auto_save=False)
            expected_glass_spec = theme_applicator.get_hud_states()["recording"]["specular"]
            actual_glass_spec = hud.canvas.itemcget(hud.pill_specular_id, "fill")
            self.assertEqual(
                actual_glass_spec,
                expected_glass_spec,
                f"Recording specular clobbered on Glassmorphism switch: expected {expected_glass_spec}, got {actual_glass_spec}"
            )

            # Switch to Liquid Glass while in recording state
            theme_manager.set_theme("liquid_glass", auto_save=False)
            expected_liquid_spec = theme_applicator.get_hud_states()["recording"]["specular"]
            actual_liquid_spec = hud.canvas.itemcget(hud.pill_specular_id, "fill")
            self.assertEqual(
                actual_liquid_spec,
                expected_liquid_spec,
                f"Recording specular clobbered on Liquid Glass switch: expected {expected_liquid_spec}, got {actual_liquid_spec}"
            )

            # Also verify in error state
            hud.set_state("error")
            theme_manager.set_theme("glassmorphism", auto_save=False)
            expected_err_spec = theme_applicator.get_hud_states()["error"]["specular"]
            actual_err_spec = hud.canvas.itemcget(hud.pill_specular_id, "fill")
            self.assertEqual(
                actual_err_spec,
                expected_err_spec,
                f"Error specular clobbered on Glassmorphism switch: expected {expected_err_spec}, got {actual_err_spec}"
            )
        finally:
            theme_applicator.register_hud(None)
            hud.root.destroy()
            theme_manager.set_theme("default_dark", auto_save=False)


if __name__ == "__main__":
    unittest.main()
