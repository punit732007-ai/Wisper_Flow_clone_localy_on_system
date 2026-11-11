"""
LocalWhisper Pro — Master Test Suite Runner & E2E Test Suite Consolidation
Consolidates and executes all automated unit, integration, and adversarial stress tests across:
- Milestone 1: 35+ Aesthetic Themes Studio, Glassmorphism, Liquid Glass, HUD Specular Highlights
- Milestone 2: Other / Custom OpenAI-compatible Model Provider, Settings UI, Connectivity Check, Inference Fallbacks
- Milestone 1 & 2 Adversarial Stress & Concurrency Test Suites
- Graceful isolation and skipping of optional ML dependencies (e.g. numpy, sounddevice) when running in lightweight environments.
"""

import sys
import os
import time
import unittest
from pathlib import Path

# Ensure UTF-8 stdout & stderr encoding on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ─── 1. Core Milestone Test Imports (Always Available) ───────────────────────
from tests.test_themes import TestThemeEngine
from tests.test_custom_provider import (
    TestCustomProviderConfig,
    TestCustomBackendStatus,
    TestCustomProviderInference,
    TestCustomProviderSettingsUI,
)
from tests.test_m1_adversarial_stress import TestM1AdversarialStress
from tests.test_m2_adversarial_stress import TestM2AdversarialStress

# ─── 2. Optional ML Wheel / Audio Buffer Test Probing ────────────────────────
OPTIONAL_ML_TESTS = []
OPTIONAL_ML_SKIPPED_REASON = None

try:
    import numpy
    import sounddevice
    from tests.test_v3_requirements import (
        TestLanguageRestrictionR1,
        TestDictationModePromptsR2,
        TestMicrophoneSubsystemR3,
        TestWhisperModelDropdownR4,
        TestNoRegressionAndConcurrencyR5,
        TestBoundaryAndCornerCases,
        TestCrossFeatureCombinations,
        TestRealWorldScenarios,
    )
    OPTIONAL_ML_TESTS = [
        ("Tier 1: R1 Language Support Restriction", TestLanguageRestrictionR1),
        ("Tier 1: R2 Dictation Mode Prompts Overhaul", TestDictationModePromptsR2),
        ("Tier 1: R3 Microphone Subsystem & Refresh", TestMicrophoneSubsystemR3),
        ("Tier 1: R4 Whisper Model Dropdown", TestWhisperModelDropdownR4),
        ("Tier 1: R5 No Regression & Concurrency Guard", TestNoRegressionAndConcurrencyR5),
        ("Tier 2: Boundary & Corner Cases", TestBoundaryAndCornerCases),
        ("Tier 3: Cross-Feature Combinations", TestCrossFeatureCombinations),
        ("Tier 4: Real-World Scenarios", TestRealWorldScenarios),
    ]
except ImportError as exc:
    OPTIONAL_ML_SKIPPED_REASON = f"Optional ML packages not installed in environment ({exc})"


# ─── 3. Test Registry Definition ─────────────────────────────────────────────
ACTIVE_TEST_CLASSES = [
    ("M1: 35+ Aesthetic Themes Studio & Custom Palettes", TestThemeEngine),
    ("M2: Custom Provider Config & Persistence", TestCustomProviderConfig),
    ("M2: Custom Provider Connectivity & Auth Verification", TestCustomBackendStatus),
    ("M2: Custom Provider Inference & Fallback Engine", TestCustomProviderInference),
    ("M2: Custom Provider Settings UI & In-Memory Staging", TestCustomProviderSettingsUI),
    ("M1: HUD Concurrency & Animation Adversarial Stress", TestM1AdversarialStress),
    ("M2: Custom Provider Hostile Adversarial Stress", TestM2AdversarialStress),
]

ALL_TEST_CLASSES = ACTIVE_TEST_CLASSES + OPTIONAL_ML_TESTS


def load_tests(loader, standard_tests, pattern):
    """Standard unittest load_tests protocol for discovery and test runner integration."""
    suite = unittest.TestSuite()
    for _, cls in ALL_TEST_CLASSES:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    return suite


def run_full_test_suite() -> bool:
    """Execute the entire consolidated test suite and return True if all tests pass."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    print("\n" + "=" * 78)
    print("  LOCALWHISPER PRO — CONSOLIDATED MASTER TEST RUNNER")
    print("=" * 78)

    if OPTIONAL_ML_SKIPPED_REASON:
        print(f"  ℹ️  Notice: {OPTIONAL_ML_SKIPPED_REASON}")
        print("     Legacy ASR audio buffer tests (Tiers 1-4) safely isolated.")
        print("     Active suites (Themes, Custom Provider, Adversarial Stress) running.")
        print("-" * 78)

    total_tests = 0
    passed_count = 0
    failed_count = 0
    error_count = 0

    t_start = time.perf_counter()

    for category_name, cls in ALL_TEST_CLASSES:
        sub_suite = loader.loadTestsFromTestCase(cls)
        count = sub_suite.countTestCases()
        total_tests += count
        print(f"\n▶ [{category_name}] ({count} test cases)")

        runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
        result = runner.run(sub_suite)

        import gc
        gc.collect()
        time.sleep(0.05)

        sub_failures = len(result.failures)
        sub_errors = len(result.errors)
        sub_passed = count - sub_failures - sub_errors

        passed_count += sub_passed
        failed_count += sub_failures
        error_count += sub_errors

        status_tag = "✅ PASS" if (sub_failures == 0 and sub_errors == 0) else "❌ FAIL"
        print(f"  Summary: {sub_passed}/{count} Passed {status_tag}")
        if sub_failures > 0:
            for failure in result.failures:
                print(f"    - Failure in {failure[0]}: {failure[1].splitlines()[-1]}")
        if sub_errors > 0:
            for err in result.errors:
                print(f"    - Error in {err[0]}: {err[1].splitlines()[-1]}")

    elapsed = time.perf_counter() - t_start

    print("\n" + "=" * 78)
    print("  MASTER TEST SUITE EXECUTION SUMMARY")
    print("=" * 78)
    print(f"  Total Test Cases : {total_tests}")
    print(f"  Passed           : {passed_count}")
    print(f"  Failures         : {failed_count}")
    print(f"  Errors           : {error_count}")
    print(f"  Time Elapsed     : {elapsed:.2f}s")
    print("=" * 78)

    if failed_count == 0 and error_count == 0:
        print(f"  🎉 ALL {total_tests} TEST CASES PASSED WITH 100% SUCCESS RATE!\n")
        return True
    else:
        print(f"  ⚠️  {failed_count + error_count} TESTS FAILED. Gaps identified.\n")
        return False


if __name__ == "__main__":
    success = run_full_test_suite()
    sys.exit(0 if success else 1)
