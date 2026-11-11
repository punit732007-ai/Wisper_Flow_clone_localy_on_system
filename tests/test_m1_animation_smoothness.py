"""
Empirical Verification of Animation Smoothness and Zero Canvas Allocations/Deletions.
Intercepts Tkinter Canvas methods to verify that during 500 frames of visualizer.update_animation(),
exactly 0 creations and 0 deletions occur, and bar heights interpolate smoothly.
"""

import sys
import math
import unittest
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.visualizer_widget import AudioVisualizerWidget


class TestAnimationSmoothnessAndCanvasPurity(unittest.TestCase):

    def test_zero_allocations_and_smooth_coordinates_500_frames(self):
        print("\n  [Canvas Purity & Smoothness] Auditing 500 frames of update_animation()...")
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=300, height=100)
        canvas.pack()

        num_bars = 5
        viz = AudioVisualizerWidget(canvas, x=20, y=20, width=80, height=24, num_bars=num_bars)

        # Track canvas method invocations
        create_calls = {"rect": 0, "line": 0, "poly": 0, "text": 0, "oval": 0}
        delete_calls = [0]
        coords_calls = [0]
        itemconfig_calls = [0]

        orig_create_rect = canvas.create_rectangle
        orig_delete = canvas.delete
        orig_coords = canvas.coords
        orig_itemconfig = canvas.itemconfig

        def tracking_create_rect(*args, **kwargs):
            create_calls["rect"] += 1
            return orig_create_rect(*args, **kwargs)

        def tracking_delete(*args, **kwargs):
            delete_calls[0] += 1
            return orig_delete(*args, **kwargs)

        def tracking_coords(*args, **kwargs):
            coords_calls[0] += 1
            return orig_coords(*args, **kwargs)

        def tracking_itemconfig(*args, **kwargs):
            itemconfig_calls[0] += 1
            return orig_itemconfig(*args, **kwargs)

        canvas.create_rectangle = tracking_create_rect
        canvas.delete = tracking_delete
        canvas.coords = tracking_coords
        canvas.itemconfig = tracking_itemconfig

        initial_item_ids = set(canvas.find_all())
        self.assertEqual(len(initial_item_ids), num_bars)

        # Record coordinate trajectories for each bar over 500 frames
        trajectories = {bar_id: [] for bar_id in viz.bar_ids}

        for frame in range(500):
            # Dynamic excitation with oscillating frequency bands
            mock_bands = [
                0.2 + 0.6 * (math.sin(frame * 0.05 + b * 1.2) ** 2)
                for b in range(num_bars)
            ]
            viz.update_levels(mock_bands)
            viz.update_animation()

            for bar_id in viz.bar_ids:
                c = orig_coords(bar_id)
                self.assertEqual(len(c), 4)
                bx1, by1, bx2, by2 = c
                height = by2 - by1
                width = bx2 - bx1
                # Invariants:
                self.assertGreaterEqual(height, 4, "Height violated min_bar_height=4")
                self.assertLessEqual(height, viz.height, "Height exceeded widget container")
                self.assertGreater(width, 0, "Bar width must be positive")
                trajectories[bar_id].append((bx1, by1, bx2, by2, height))

        # Check canvas item allocations and deletions during animation
        self.assertEqual(delete_calls[0], 0, f"canvas.delete was called {delete_calls[0]} times during animation!")
        self.assertEqual(sum(create_calls.values()), 0, f"New canvas items created during animation: {create_calls}")
        self.assertEqual(coords_calls[0], 500 * num_bars, "Expected exactly 1 coords() call per bar per frame")

        final_item_ids = set(canvas.find_all())
        self.assertEqual(initial_item_ids, final_item_ids, "Canvas item set mutated during animation loop!")

        # Verify lerp smoothness: height deltas between consecutive frames must be bounded by lerp factor
        # Since lerp is 0.4 and max level delta is <= 1.0 * height (24), step delta <= 24 * 0.4 = 9.6 + headroom
        max_observed_step_delta = 0
        for bar_id, samples in trajectories.items():
            for i in range(1, len(samples)):
                h_prev = samples[i - 1][4]
                h_curr = samples[i][4]
                delta = abs(h_curr - h_prev)
                if delta > max_observed_step_delta:
                    max_observed_step_delta = delta
                self.assertLessEqual(delta, 10, f"Discontinuous height jump detected: {delta}px between frames")

        print(f"    -> 500 frames verified: 0 allocations, 0 deletions, {coords_calls[0]} coords updates.")
        print(f"    -> Max observed frame-to-frame delta: {max_observed_step_delta}px (smooth lerp interpolation verified).")

        root.destroy()


if __name__ == "__main__":
    unittest.main()
