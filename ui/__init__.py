"""
LocalWhisper Pro UI Package
"""

from ui.theme_engine import theme_manager, BUILTIN_THEMES
from ui.theme_applicator import theme_applicator

__all__ = [
    "theme_manager",
    "theme_applicator",
    "BUILTIN_THEMES",
]
