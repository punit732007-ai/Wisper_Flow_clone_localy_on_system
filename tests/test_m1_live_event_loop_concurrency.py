"""
Adversarial test: FloatingHUD live Tkinter event loop concurrency stress test.
Simulates real-world conditions where background threads hammer schedule()
WHILE the Tkinter event loop is actively running and ticking.
"""

import sys
import time
import queue
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.floating_hud import FloatingHUD
from ui.theme_engine import theme_manager


class TestLiveEventLoopConcurrency(unittest.TestCase):

    def test_concurrent_scheduling_during_live_mainloop_ticks(self):
        print("\n  [Live Mainloop Concurrency] Hammering schedule() while Tkinter _tick() is active...")
        hud = FloatingHUD()

        num_threads = 10
        stop_event = threading.Event()
        tasks_sent = [0] * num_threads
        tasks_executed = [0]
        counter_lock = threading.Lock()
        thread_ids_observed = set()
        thread_ids_lock = threading.Lock()
        worker_errors = []

        main_thread_id = threading.get_ident()

        def background_worker(thread_idx: int):
            try:
                states = ["ready", "recording", "processing", "success", "error"]
                levels = [0.1, 0.3, 0.7, 0.9, 0.4]
                call_idx = 0
                while not stop_event.is_set():
                    st = states[call_idx % len(states)]
                    
                    def ui_action(t_idx, c_idx, state_val):
                        with counter_lock:
                            tasks_executed[0] += 1
                        with thread_ids_lock:
                            thread_ids_observed.add(threading.get_ident())
                        if c_idx % 20 == 0:
                            hud.set_state(state_val)
                            hud.update_audio_levels(0.5, levels)

                    hud.schedule(ui_action, thread_idx, call_idx, st)
                    tasks_sent[thread_idx] += 1
                    call_idx += 1
                    time.sleep(0.001)  # 1ms burst rate
            except Exception as e:
                worker_errors.append((thread_idx, e))

        workers = [
            threading.Thread(target=background_worker, args=(i,), name=f"live-worker-{i}")
            for i in range(num_threads)
        ]

        for w in workers:
            w.start()

        # Run Tkinter event loop on main thread for 1.5 seconds
        t_start = time.perf_counter()
        while time.perf_counter() - t_start < 1.5:
            hud.root.update()
            time.sleep(0.01)

        # Signal workers to stop and wait for join
        stop_event.set()
        for w in workers:
            w.join(timeout=2.0)

        total_sent = sum(tasks_sent)
        print(f"    -> Workers sent {total_sent} total calls during live loop.")

        # Allow remaining queue to drain
        drain_start = time.perf_counter()
        while not hud._action_queue.empty() and time.perf_counter() - drain_start < 3.0:
            hud.root.update()
            time.sleep(0.01)

        print(f"    -> Drained: {tasks_executed[0]}/{total_sent} tasks executed on main loop.")

        self.assertEqual(len(worker_errors), 0, f"Worker thread errors: {worker_errors}")
        self.assertEqual(thread_ids_observed, {main_thread_id}, "Cross-thread execution detected on Tkinter widgets!")
        self.assertEqual(tasks_executed[0], total_sent, "Some queued actions were dropped or lost!")

        # Verify canvas integrity
        self.assertTrue(hud.canvas.winfo_exists())
        self.assertIn(hud.pill_specular_id, hud.canvas.find_all())

        hud.root.destroy()


if __name__ == "__main__":
    unittest.main()
