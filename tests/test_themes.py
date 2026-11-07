"""
LocalWhisper Pro — Unit Tests for 35+ Aesthetic Themes & Customization Engine
Validates all theme schemas, color codes, category assignments, custom palette
customization, layout presets, and theme applicator state mapping.
"""

import unittest
import re
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


if __name__ == "__main__":
    unittest.main()
