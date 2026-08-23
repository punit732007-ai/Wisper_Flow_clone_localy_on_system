import ast
import gc
import os
import sys
import time
import queue
import threading
import unittest
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import config
from core.audio_engine import AudioEngine
from core.hotkey_manager import HotkeyManager
from core.history_manager import HistoryManager
from core.ai_refiner import AIRefiner
from core.paster import paste_text
from ui.visualizer_widget import AudioVisualizerWidget
from ui.floating_hud import FloatingHUD, HUD_STATES, TRANSPARENT_COLOR


class TestConcurrencyAndThreadSafetyStress(unittest.TestCase):

    def setUp(self):
        self.orig_mode = config.get('current_mode')
        self.orig_rec_mode = config.get('recording_mode')
        self.orig_hotkey = config.get('hotkey')
        config.set('hotkey', 'ctrl+space', auto_save=False)

    def tearDown(self):
        config.set('current_mode', self.orig_mode, auto_save=False)
        config.set('recording_mode', self.orig_rec_mode, auto_save=False)
        config.set('hotkey', self.orig_hotkey, auto_save=False)

    def test_01_floating_hud_schedule_massive_concurrency(self):
        print('\n  [Stress 1/8] Launching 50 worker threads sending 5,000 tasks to FloatingHUD.schedule()...')
        hud = FloatingHUD()
        main_thread_id = threading.get_ident()

        executed_counter = [0]
        counter_lock = threading.Lock()
        thread_ids_observed = set()
        thread_ids_lock = threading.Lock()

        def sample_ui_action(val):
            with counter_lock:
                executed_counter[0] += 1
            with thread_ids_lock:
                thread_ids_observed.add(threading.get_ident())

        num_threads = 50
        calls_per_thread = 100
        total_expected = num_threads * calls_per_thread

        def worker(thread_idx):
            for i in range(calls_per_thread):
                hud.schedule(sample_ui_action, f't{thread_idx}_call{i}')

        threads = [threading.Thread(target=worker, args=(t_idx,), name=f'stress-worker-{t_idx}') for t_idx in range(num_threads)]

        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        t_enqueue = time.perf_counter() - t0
        print(f'    Enqueued {total_expected} cross-thread actions in {t_enqueue:.3f}s ({total_expected / t_enqueue:.0f} ops/sec)')

        t_drain_start = time.perf_counter()
        while not hud._action_queue.empty():
            func, args = hud._action_queue.get_nowait()
            func(*args)
        t_drain = time.perf_counter() - t_drain_start

        print(f'    Drained {executed_counter[0]}/{total_expected} actions in {t_drain:.3f}s on main thread')

        self.assertEqual(executed_counter[0], total_expected)
        self.assertEqual(thread_ids_observed, {main_thread_id})
        hud.root.destroy()

    def test_02_visualizer_canvas_item_reuse_zero_leaks_10k_ticks(self):
        print('\n  [Stress 2/8] Running 10,000 visualizer animation & level ticks on Tkinter Canvas...')
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=300, height=100)
        canvas.pack()

        num_bars = 5
        viz = AudioVisualizerWidget(canvas, x=10, y=10, width=100, height=30, num_bars=num_bars)

        initial_items = list(canvas.find_all())
        self.assertEqual(len(initial_items), num_bars)

        states = ['ready', 'recording', 'processing', 'success', 'error']
        t0 = time.perf_counter()
        for i in range(10000):
            if i % 2000 == 0:
                viz.set_state(states[(i // 2000) % len(states)])
            mock_bands = [abs(np.sin(i * 0.05 + b)) for b in range(num_bars)]
            viz.update_levels(mock_bands)
            viz.update_animation()

        t_elapsed = time.perf_counter() - t0
        final_items = list(canvas.find_all())

        print(f'    10,000 visualizer frames rendered in {t_elapsed:.3f}s ({10000 / t_elapsed:.0f} FPS equivalent)')
        self.assertEqual(initial_items, final_items)
        self.assertEqual(len(final_items), num_bars)
        root.destroy()

    def test_03_hotkey_manager_rapid_lifecycle_100_cycles(self):
        print('\n  [Stress 3/8] Stress testing HotkeyManager rapid start/stop/rebind across 100 iterations...')
        start_count = [0]
        stop_count = [0]
        toggle_count = [0]

        hm = HotkeyManager(
            on_start_record=lambda: start_count.__setitem__(0, start_count[0] + 1),
            on_stop_record=lambda: stop_count.__setitem__(0, stop_count[0] + 1),
            on_toggle_record=lambda: toggle_count.__setitem__(0, toggle_count[0] + 1),
        )

        from pynput import keyboard
        ctrl_key = keyboard.Key.ctrl_l
        space_key = keyboard.Key.space

        t0 = time.perf_counter()
        for i in range(100):
            config.set('recording_mode', 'push_to_talk', auto_save=False)
            config.set('hotkey', 'ctrl+space', auto_save=False)
            hm.start()
            hm._handle_press(ctrl_key)
            hm._handle_press(space_key)
            self.assertTrue(hm._is_recording_active)
            self.assertEqual(start_count[0], i + 1)

            hm._handle_release(space_key)
            hm._handle_release(ctrl_key)
            self.assertFalse(hm._is_recording_active)
            self.assertEqual(stop_count[0], i + 1)

            config.set('recording_mode', 'toggle', auto_save=False)
            hm.rebind()
            hm._handle_press(ctrl_key)
            hm._handle_press(space_key)
            self.assertTrue(hm._is_recording_active)
            hm._handle_release(space_key)
            hm._handle_release(ctrl_key)

            hm._handle_press(ctrl_key)
            hm._handle_press(space_key)
            self.assertFalse(hm._is_recording_active)
            hm._handle_release(space_key)
            hm._handle_release(ctrl_key)
            hm.stop()

        t_elapsed = time.perf_counter() - t0
        print(f'    100 complete start/stop/rebind cycles completed successfully in {t_elapsed:.3f}s')
        self.assertFalse(hm._is_recording_active)
        self.assertIsNone(hm._listener)

    def test_04_audio_engine_rapid_lifecycle_and_fallback_50_cycles(self):
        print('\n  [Stress 4/8] Stress testing AudioEngine start/stop and device fallbacks across 50 cycles...')
        engine = AudioEngine()

        def mock_stream_factory(**kwargs):
            dev = kwargs.get('device')
            if dev == 999:
                raise RuntimeError('Simulated Device Disconnect')
            stream_mock = MagicMock()
            return stream_mock

        t0 = time.perf_counter()
        with patch('sounddevice.InputStream', side_effect=mock_stream_factory), \
             patch('sounddevice.default') as mock_default, \
             patch('sounddevice.query_devices') as mock_query:
            
            mock_default.device = [0, 0]
            mock_query.return_value = {'name': 'Fallback Microphone'}

            for i in range(50):
                if i % 2 == 0:
                    config.set('mic_device_id', None, auto_save=False)
                else:
                    config.set('mic_device_id', 999, auto_save=False)

                engine.start()
                self.assertTrue(engine.is_recording)

                for _ in range(5):
                    chunk = np.random.uniform(-0.1, 0.1, (800, 1)).astype(np.float32)
                    engine._audio_callback(chunk, 800, None, None)

                audio = engine.stop()
                self.assertFalse(engine.is_recording)
                self.assertEqual(len(audio), 4000)

        t_elapsed = time.perf_counter() - t0
        print(f'    50 AudioEngine start/stop/fallback cycles completed in {t_elapsed:.3f}s')

    def test_05_multi_threaded_state_mutations_and_history_logging(self):
        print('\n  [Stress 5/8] Multi-threaded concurrent mode cycling & history recording from 20 threads...')
        hm = HistoryManager()
        hm._entries = []

        num_threads = 20
        iterations_per_thread = 50
        errors = []

        def worker(thread_idx):
            try:
                for i in range(iterations_per_thread):
                    mode_key = config.cycle_next_mode()
                    mode_info = config.current_mode_info

                    hm.add_entry(
                        raw_text=f'thread {thread_idx} message {i}',
                        refined_text=f'Thread {thread_idx} Message {i}.',
                        mode_key=mode_key,
                        mode_name=mode_info.get('name', mode_key),
                        duration_sec=1.0,
                        language='en',
                        model_name='small',
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t_idx,)) for t_idx in range(num_threads)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        t_elapsed = time.perf_counter() - t0
        print(f'    1,000 multi-threaded operations completed in {t_elapsed:.3f}s (Errors: {len(errors)})')

        self.assertEqual(len(errors), 0)
        # HistoryManager limits history entries to 500 items max
        self.assertEqual(len(hm.get_entries(limit=2000)), min(500, num_threads * iterations_per_thread))

    def test_06_static_ast_tkinter_thread_safety_audit(self):
        print('\n  [Stress 6/8] Performing AST Static Analysis for Tkinter cross-thread violations...')
        violations = []

        core_dir = PROJECT_ROOT / 'core'
        for py_file in core_dir.glob('*.py'):
            if py_file.name == '__init__.py':
                continue
            with open(py_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if 'tkinter' in name.name:
                            violations.append(f'{py_file.name}: Direct import of {name.name} in core module')
                elif isinstance(node, ast.ImportFrom):
                    if node.module and 'tkinter' in node.module:
                        violations.append(f'{py_file.name}: Direct import from {node.module} in core module')

        hud_file = PROJECT_ROOT / 'ui' / 'floating_hud.py'
        with open(hud_file, 'r', encoding='utf-8') as f:
            hud_code = f.read()

        self.assertIn('self._action_queue', hud_code)
        self.assertIn('self._action_queue.put', hud_code)
        self.assertIn('while not self._action_queue.empty():', hud_code)
        self.assertIn('-transparentcolor', hud_code)
        self.assertNotIn('-alpha', hud_code)

        print(f'    Static AST Audit complete. Core isolation violations found: {len(violations)}')
        self.assertEqual(len(violations), 0)

    def test_07_paster_cross_thread_dispatch_stress(self):
        print('\n  [Stress 7/8] Stress-testing paste_text cross-thread invocation (50 calls)...')
        with patch('core.paster.paste_via_clipboard') as mock_clip:
            threads = []
            for i in range(50):
                t = threading.Thread(target=paste_text, args=(f'test phrase {i}',))
                threads.append(t)
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(mock_clip.call_count, 50)
            print(f'    50 concurrent paste requests dispatched cleanly without lock contention.')

    def test_08_end_to_end_simulated_pipeline_concurrency(self):
        print('\n  [Stress 8/8] Stress-testing 10 simultaneous end-to-end transcription pipelines...')
        from core.transcriber import Transcriber
        transcriber = Transcriber()
        mock_model = MagicMock()
        mock_seg = MagicMock(text='simulated voice transcript')
        mock_info = MagicMock(language='en', language_probability=0.99)
        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        transcriber._model = mock_model

        refiner = AIRefiner()
        hud = FloatingHUD()

        pipeline_errors = []
        def run_simulated_pipeline(idx):
            try:
                # 1. Transcribe
                raw, lang, prob = transcriber.transcribe(np.zeros(16000, dtype=np.float32))
                # 2. Refine
                ref = refiner.refine(raw, lang)
                # 3. Schedule HUD state
                hud.schedule(hud.set_state, 'processing')
                hud.schedule(hud.set_state, 'success')
            except Exception as e:
                pipeline_errors.append(e)

        threads = [threading.Thread(target=run_simulated_pipeline, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Drain HUD queue
        while not hud._action_queue.empty():
            func, args = hud._action_queue.get_nowait()
            func(*args)

        hud.root.destroy()
        print(f'    10 parallel pipelines completed with {len(pipeline_errors)} errors.')
        self.assertEqual(len(pipeline_errors), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)