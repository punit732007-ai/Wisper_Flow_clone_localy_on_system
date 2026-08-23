"""
LocalWhisper Pro v3.0 — Unified Test Suite Runner & Requirement Verification
Executes all automated tests across Requirements R1-R5 and Tiers 1-4,
displaying structured coverage metrics and results.
"""

import sys
import os
import time
import unittest
from pathlib import Path

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def run_full_test_suite() -> bool:
    """Execute the entire test suite and return True if all tests pass."""
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
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    test_classes = [
        ("Tier 1: R1 Language Support Restriction", TestLanguageRestrictionR1),
        ("Tier 1: R2 Dictation Mode Prompts Overhaul", TestDictationModePromptsR2),
        ("Tier 1: R3 Microphone Subsystem & Refresh", TestMicrophoneSubsystemR3),
        ("Tier 1: R4 Whisper Model Dropdown", TestWhisperModelDropdownR4),
        ("Tier 1: R5 No Regression & Concurrency Guard", TestNoRegressionAndConcurrencyR5),
        ("Tier 2: Boundary & Corner Cases", TestBoundaryAndCornerCases),
        ("Tier 3: Cross-Feature Combinations", TestCrossFeatureCombinations),
        ("Tier 4: Real-World Scenarios", TestRealWorldScenarios),
    ]

    print("\n" + "=" * 70)
    print("  LOCALWHISPER PRO v3.0 — AUTOMATED TEST SUITE EXECUTION")
    print("=" * 70)

    total_tests = 0
    passed_count = 0
    failed_count = 0
    error_count = 0

    t_start = time.perf_counter()

    for category_name, cls in test_classes:
        sub_suite = loader.loadTestsFromTestCase(cls)
        count = sub_suite.countTestCases()
        total_tests += count
        print(f"\n▶ [{category_name}] ({count} test cases)")

        runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
        result = runner.run(sub_suite)

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

    print("\n" + "=" * 70)
    print("  TEST SUITE EXECUTION SUMMARY")
    print("=" * 70)
    print(f"  Total Test Cases : {total_tests}")
    print(f"  Passed           : {passed_count}")
    print(f"  Failures         : {failed_count}")
    print(f"  Errors           : {error_count}")
    print(f"  Time Elapsed     : {elapsed:.2f}s")
    print("=" * 70)

    if failed_count == 0 and error_count == 0:
        print("  🎉 ALL TEST CASES PASSED WITH 100% SUCCESS RATE!\n")
        return True
    else:
        print(f"  ⚠️ {failed_count + error_count} TESTS FAILED. Gaps identified.\n")
        return False


if __name__ == "__main__":
    success = run_full_test_suite()
    sys.exit(0 if success else 1)
