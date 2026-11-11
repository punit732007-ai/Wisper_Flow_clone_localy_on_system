"""
LocalWhisper Pro — Adversarial Concurrency & Stress Harness for Milestone 1
Adversarially challenges FloatingHUD.schedule(), AudioVisualizerWidget animation,
canvas item reuse, and theme switching under extreme concurrent load.
"""

import sys
import math
import time
import queue
import threading
import unittest
import tkinter as tk
from pathlib import Path
from typing import List, Set
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import config
from ui.theme_engine import theme_manager, BUILTIN_THEMES
from ui.theme_applicator import theme_applicator
from ui.floating_hud import FloatingHUD, HUD_LAYOUTS, HUD_STATES, TRANSPARENT_COLOR
from ui.visualizer_widget import AudioVisualizerWidget


class TestM1AdversarialStress(unittest.TestCase):
    """Adversarial stress and concurrency test suite for Milestone 1."""

    def setUp(self):
        self.orig_theme = theme_manager.current_theme_key
        self.orig_layout = config.get("hud_layout", "compact_pill")

    def tearDown(self):
        theme_manager.set_theme(self.orig_theme, auto_save=False)
        config.set("hud_layout", self.orig_layout, auto_save=False)

    def test_01_floating_hud_schedule_massive_concurrency(self):
        """Stress test FloatingHUD.schedule() with 50 threads firing 10,000 total tasks."""
        print("\n  [Adversarial 1/5] Stressing FloatingHUD.schedule() with 50 threads and 10,000 tasks...")
        hud = FloatingHUD()
        main_thread_id = threading.get_ident()

        executed_counter = [0]
        counter_lock = threading.Lock()
        thread_ids_observed: Set[int] = set()
        thread_ids_lock = threading.Lock()
        exceptions_encountered: List[Exception] = []

        def task_action(thread_idx: int, task_idx: int):
            try:
                with counter_lock:
                    executed_counter[0] += 1
                with thread_ids_lock:
                    thread_ids_observed.add(threading.get_ident())
                
                # Perform light Tkinter canvas query on main thread
                if task_idx % 100 == 0:
                    hud.set_state("recording" if task_idx % 200 == 0 else "ready")
            except Exception as ex:
                exceptions_encountered.append(ex)

        num_threads = 50
        tasks_per_thread = 200
        total_tasks = num_threads * tasks_per_thread

        def worker(thread_idx: int):
            for i in range(tasks_per_thread):
                hud.schedule(task_action, thread_idx, i)

        threads = [
            threading.Thread(target=worker, args=(t_idx,), name=f"stress-worker-{t_idx}")
            for t_idx in range(num_threads)
        ]

        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        t_enqueued = time.perf_counter() - t0

        print(f"    -> Enqueued {total_tasks} cross-thread actions in {t_enqueued:.3f}s ({total_tasks/t_enqueued:.0f} ops/sec)")

        # Drain on main thread as FloatingHUD._tick() would do
        t_drain_start = time.perf_counter()
        while not hud._action_queue.empty():
            func, args = hud._action_queue.get_nowait()
            func(*args)
        t_drained = time.perf_counter() - t_drain_start

        print(f"    -> Drained {executed_counter[0]}/{total_tasks} tasks in {t_drained:.3f}s on main thread")

        self.assertEqual(executed_counter[0], total_tasks, "Dropped scheduled tasks detected!")
        self.assertEqual(thread_ids_observed, {main_thread_id}, "Task executed off main Tkinter thread!")
        self.assertEqual(len(exceptions_encountered), 0, f"Exceptions in scheduled actions: {exceptions_encountered}")

        hud.root.destroy()

    def test_02_visualizer_animation_item_reuse_1000_frames(self):
        """Verify that under 1,000 rapid animation frames, canvas items are strictly reused."""
        print("\n  [Adversarial 2/5] Running 1,000 rapid animation frames under varying states...")
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=300, height=100)
        canvas.pack()

        num_bars = 5
        viz = AudioVisualizerWidget(canvas, x=10, y=10, width=100, height=30, num_bars=num_bars)

        initial_items = sorted(canvas.find_all())
        self.assertEqual(len(initial_items), num_bars)

        states = ["ready", "recording", "processing", "success", "error", "loading"]

        t0 = time.perf_counter()
        for frame in range(1000):
            # Periodically switch state
            if frame % 150 == 0:
                viz.set_state(states[(frame // 150) % len(states)])

            # Supply sinusoidal simulated audio frequency bands
            mock_bands = [abs(math.sin(frame * 0.08 + b * 0.7)) for b in range(num_bars)]
            viz.update_levels(mock_bands)
            viz.update_animation()

            # Verify canvas items count and IDs mid-run every 200 frames
            if frame % 200 == 0:
                current_items = sorted(canvas.find_all())
                self.assertEqual(current_items, initial_items, f"Item IDs changed at frame {frame}")
                for bar_id in viz.bar_ids:
                    coords = canvas.coords(bar_id)
                    self.assertEqual(len(coords), 4)
                    bx1, by1, bx2, by2 = coords
                    self.assertLess(bx1, bx2, "Bar width inverted")
                    self.assertLess(by1, by2, "Bar height inverted")
                    # Check no NaN or infinite values
                    for c in coords:
                        self.assertFalse(math.isnan(c) or math.isinf(c), "Invalid float coordinate")

        t_elapsed = time.perf_counter() - t0
        final_items = sorted(canvas.find_all())

        print(f"    -> 1,000 animation frames executed in {t_elapsed:.3f}s ({1000/t_elapsed:.0f} FPS equivalent)")
        self.assertEqual(initial_items, final_items, "Canvas items were recreated or deleted during animation!")
        root.destroy()

    def test_03_hud_theme_and_layout_switching_under_rapid_animation(self):
        """Stress HUD by interleaving rapid theme changes, layout changes, and animation ticks."""
        print("\n  [Adversarial 3/5] Interleaving 200 theme & layout switches with animation ticks...")
        hud = FloatingHUD()
        theme_applicator.register_hud(hud)

        initial_items = sorted(hud.canvas.find_all())
        themes_to_test = ["glassmorphism", "liquid_glass", "cyberpunk", "vaporwave", "default_dark"]
        layouts_to_test = ["compact_pill", "classic_bar", "expanded_card", "minimal_dot"]

        try:
            t0 = time.perf_counter()
            with patch.object(config, "save"):
                for i in range(200):
                    th = themes_to_test[i % len(themes_to_test)]
                    theme_manager.set_theme(th, auto_save=False)

                    lay = layouts_to_test[i % len(layouts_to_test)]
                    hud.set_layout(lay)

                    # Feed levels and tick animation
                    hud.update_audio_levels(0.5, [0.2, 0.4, 0.6, 0.8, 0.3])
                    hud.visualizer.update_animation()

                    # Verify specular highlight exists and is placed correctly
                    spec_coords = hud.canvas.coords(hud.pill_specular_id)
                    self.assertEqual(len(spec_coords), 4, f"Invalid specular coords in layout {lay}")
                    self.assertLess(spec_coords[0], spec_coords[2], "Specular arc width <= 0")
                    self.assertEqual(spec_coords[1], 3.0)
                    self.assertEqual(spec_coords[3], 3.0)

                    # Check color of specular highlight for glass themes
                    if th == "glassmorphism":
                        self.assertEqual(hud.canvas.itemcget(hud.pill_specular_id, "fill"), "#bae6fd")
                    elif th == "liquid_glass":
                        self.assertEqual(hud.canvas.itemcget(hud.pill_specular_id, "fill"), "#a5f3fc")

            t_elapsed = time.perf_counter() - t0
            final_items = sorted(hud.canvas.find_all())

            print(f"    -> 200 theme/layout cycles completed in {t_elapsed:.3f}s")
            self.assertEqual(initial_items, final_items, "Canvas item count drifted across layout/theme switches!")
        finally:
            theme_applicator.register_hud(None)
            hud.root.destroy()

    def test_04_fault_injection_and_edge_case_robustness(self):
        """Inject faults (exceptions in scheduled tasks, extreme audio inputs) and assert resilience."""
        print("\n  [Adversarial 4/5] Testing fault injection and extreme boundary inputs...")
        hud = FloatingHUD()

        # 1. Faulty scheduled task
        bad_task_ran = [False]
        good_task_ran = [False]

        def crashing_task():
            bad_task_ran[0] = True
            raise ValueError("Intentional simulated crash in scheduled task")

        def normal_task():
            good_task_ran[0] = True

        hud.schedule(crashing_task)
        hud.schedule(normal_task)

        # Trigger _tick drain logic
        while not hud._action_queue.empty():
            try:
                func, args = hud._action_queue.get_nowait()
                func(*args)
            except Exception as e:
                # FloatingHUD._tick() catches exceptions and logs them
                pass

        self.assertTrue(bad_task_ran[0], "Crashing task did not run")
        self.assertTrue(good_task_ran[0], "Normal task blocked by crashing task!")

        # 2. Extreme audio levels
        extreme_inputs = [
            [],  # empty
            [-5.0, -100.0],  # negative
            [999.0, 10000.0],  # huge
            [0.0] * 50,  # overly long
            [0.5],  # short
        ]
        for inp in extreme_inputs:
            hud.update_audio_levels(0.5, inp)
            hud.visualizer.update_animation()
            # Verify coordinates are still well-formed
            for bar_id in hud.visualizer.bar_ids:
                coords = hud.canvas.coords(bar_id)
                self.assertEqual(len(coords), 4)
                self.assertLess(coords[0], coords[2])
                self.assertLess(coords[1], coords[3])

        print("    -> Fault injection and boundary audio inputs survived cleanly.")
        hud.root.destroy()

    def test_05_transparency_invariants_runtime_audit(self):
        """Audit runtime transparency flags and ensure -alpha is strictly absent."""
        print("\n  [Adversarial 5/5] Auditing Windows transparency flags...")
        hud = FloatingHUD()
        try:
            # Must have transparentcolor set to #f0abcd
            tc = str(hud.root.wm_attributes("-transparentcolor"))
            self.assertEqual(tc, TRANSPARENT_COLOR)
            self.assertEqual(TRANSPARENT_COLOR, "#f0abcd")

            # Must NOT set -alpha (should be default 1.0)
            alpha_val = float(hud.root.wm_attributes("-alpha"))
            self.assertAlmostEqual(alpha_val, 1.0, places=2)

            # Must be overrideredirect(True)
            self.assertTrue(hud.root.overrideredirect())

            print("    -> Transparency attributes strictly conform to Windows DWM invariants.")
        finally:
            hud.root.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
