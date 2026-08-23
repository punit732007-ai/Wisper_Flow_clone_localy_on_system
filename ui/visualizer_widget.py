"""
LocalWhisper Pro — Visualizer Widget
High-performance Canvas-based audio waveform / equalizer bar visualizer with smooth lerp animation.
Reuses canvas items for maximum performance and zero garbage collection overhead.
"""

import math
import tkinter as tk
from typing import List


class AudioVisualizerWidget:
    """Draws animated multi-band equalizer bars responding to live mic levels."""

    def __init__(self, canvas: tk.Canvas, x: int, y: int, width: int = 50, height: int = 24, num_bars: int = 5):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.num_bars = num_bars

        # State
        self.target_levels: List[float] = [0.1] * num_bars
        self.current_levels: List[float] = [0.1] * num_bars
        self.color = "#ff4d6d"
        self.state = "ready"
        self.anim_phase = 0.0

        # Create persistent canvas rectangles for each bar
        self.bar_ids: List[int] = []
        bar_spacing = 3
        total_spacing = bar_spacing * (self.num_bars - 1)
        bar_width = max(2, (self.width - total_spacing) // self.num_bars)
        center_y = self.y + (self.height // 2)

        for i in range(self.num_bars):
            bx1 = self.x + i * (bar_width + bar_spacing)
            by1 = center_y - 2
            bx2 = bx1 + bar_width
            by2 = center_y + 2
            bar_id = self.canvas.create_rectangle(
                bx1, by1, bx2, by2,
                fill=self.color,
                outline="",
            )
            self.bar_ids.append(bar_id)

    def set_state(self, state: str) -> None:
        """Update visualizer color according to HUD state."""
        self.state = state
        if state == "recording":
            self.color = "#ff4d6d"
        elif state == "processing":
            self.color = "#ffb703"
        elif state == "success":
            self.color = "#52b788"
        elif state == "ready":
            self.color = "#52b788"
        elif state == "loading":
            self.color = "#00b4d8"
        else:
            self.color = "#8d99ae"

        for bar_id in self.bar_ids:
            self.canvas.itemconfig(bar_id, fill=self.color)

    def update_levels(self, bands: List[float]) -> None:
        """Receive live frequency band levels (0.0 to 1.0) from AudioEngine."""
        if len(bands) >= self.num_bars:
            self.target_levels = [min(1.0, max(0.08, float(b))) for b in bands[: self.num_bars]]
        else:
            self.target_levels = [min(1.0, max(0.08, float(b))) for b in bands] + [0.1] * (self.num_bars - len(bands))

    def update_animation(self) -> None:
        """Perform interpolation step for smooth visual motion."""
        self.anim_phase += 0.12
        if self.anim_phase > 2 * math.pi:
            self.anim_phase -= 2 * math.pi

        if self.state == "processing":
            for i in range(self.num_bars):
                wave = (math.sin(self.anim_phase * 2.5 + i * 0.8) + 1) / 2
                self.target_levels[i] = 0.15 + wave * 0.7

        elif self.state in ("idle", "ready", "loading"):
            for i in range(self.num_bars):
                breath = (math.sin(self.anim_phase + i * 0.6) + 1) / 2
                self.target_levels[i] = 0.1 + breath * 0.12

        # Smooth linear interpolation (lerp) toward target
        for i in range(self.num_bars):
            self.current_levels[i] += (self.target_levels[i] - self.current_levels[i]) * 0.4

        # Update bar heights on canvas
        bar_spacing = 3
        total_spacing = bar_spacing * (self.num_bars - 1)
        bar_width = max(2, (self.width - total_spacing) // self.num_bars)
        min_bar_height = 4
        center_y = self.y + (self.height // 2)

        for i, bar_id in enumerate(self.bar_ids):
            lvl = self.current_levels[i]
            bar_h = max(min_bar_height, int(self.height * lvl))
            bx1 = self.x + i * (bar_width + bar_spacing)
            by1 = center_y - (bar_h // 2)
            bx2 = bx1 + bar_width
            by2 = center_y + (bar_h // 2)
            self.canvas.coords(bar_id, bx1, by1, bx2, by2)
