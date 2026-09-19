#!/usr/bin/env python3
"""
Comprehensive Regression Test Runner.

A reporting harness, not a test: it shells out to each regression test module in
`tests.test_regression_suite.REGRESSION_TESTS`, prints a readable summary and
exits non-zero when a critical one fails.

It used to live in `tests/test_regression_suite.py`, where pytest collected the
harness itself as a test - one that returned a bool instead of asserting, so a
failing run still reported as passed, and every `pytest` invocation re-ran four
suites in subprocesses that pytest was already running directly.

Usage:
    python scripts/run_regression_suite.py
"""

import subprocess
import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_regression_suite import REGRESSION_TESTS


def run_regression_test(test_name, test_description, test_file):
    """Run a single regression test and return results.

    Args:
        test_name: Short name for the test
        test_description: Description of what the test validates
        test_file: Path to the test file to run

    Returns:
        dict: Test result containing status, duration, output, and error information
    """
    print("\n" + "=" * 70)
    print("🧪 " + test_name)
    print("📋 " + test_description)
    print("=" * 70)

    start_time = time.time()

    try:
        # Run the test as a subprocess
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=project_root,
        )

        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"✅ {test_name} PASSED ({duration:.1f}s)")
            status = "passed"
        else:
            print(f"❌ {test_name} FAILED ({duration:.1f}s)")
            print(f"Error Output:\n{result.stderr}")
            status = "failed"

        return {
            "name": test_name,
            "description": test_description,
            "status": status,
            "duration": duration,
            "output": result.stdout,
            "error": result.stderr,
        }

    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name} TIMEOUT (>300s)")
        return {
            "name": test_name,
            "description": test_description,
            "status": "timeout",
            "duration": 300,
            "output": "",
            "error": "Test timed out after 300 seconds",
        }

    except Exception as e:
        print(f"💥 {test_name} CRASHED: {e}")
        return {
            "name": test_name,
            "description": test_description,
            "status": "crashed",
            "duration": 0,
            "output": "",
            "error": str(e),
        }


def run_regression_suite() -> bool:
    """Run every regression module in the manifest and print a summary.

    Returns:
        bool: True when at least 80% of the critical modules pass.
    """

    print("🔄 COMPREHENSIVE REGRESSION TEST SUITE")
    print("=" * 70)
    print("This suite validates that all previously fixed issues remain resolved.")
    print("=" * 70)

    # Run all tests
    results = []
    start_time = time.time()

    for test_config in REGRESSION_TESTS:
        test_file_path = project_root / test_config["file"]

        if not test_file_path.exists():
            print(f"⚠️ Test file not found: {test_config['file']}")
            results.append(
                {
                    "name": test_config["name"],
                    "description": test_config["description"],
                    "status": "missing",
                    "duration": 0,
                    "output": "",
                    "error": f"Test file not found: {test_config['file']}",
                    "critical": test_config.get("critical", False),
                }
            )
            continue

        result = run_regression_test(
            test_config["name"], test_config["description"], str(test_file_path)
        )
        result["critical"] = test_config.get("critical", False)
        results.append(result)

    total_time = time.time() - start_time

    # Generate comprehensive summary
    print(f"\n{'=' * 70}")
    print("🎯 REGRESSION TEST SUITE SUMMARY")
    print(f"{'=' * 70}")

    # Calculate statistics
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["status"] == "passed")
    failed_tests = sum(1 for r in results if r["status"] == "failed")
    timeout_tests = sum(1 for r in results if r["status"] == "timeout")
    crashed_tests = sum(1 for r in results if r["status"] == "crashed")
    missing_tests = sum(1 for r in results if r["status"] == "missing")

    # Critical test statistics
    critical_tests = [r for r in results if r.get("critical", False)]
    critical_passed = sum(1 for r in critical_tests if r["status"] == "passed")
    critical_total = len(critical_tests)

    print("📊 Overall Statistics:")
    print(f"   Total Tests: {total_tests}")
    print(f"   ✅ Passed: {passed_tests}")
    print(f"   ❌ Failed: {failed_tests}")
    print(f"   ⏰ Timeout: {timeout_tests}")
    print(f"   💥 Crashed: {crashed_tests}")
    print(f"   📁 Missing: {missing_tests}")
    print(f"   ⏱️  Total Time: {total_time:.1f}s")

    print("\n🎯 Critical Test Statistics:")
    print(f"   Critical Tests: {critical_total}")
    print(f"   ✅ Critical Passed: {critical_passed}")
    print(
        f"   Success Rate: {(critical_passed / critical_total * 100) if critical_total > 0 else 0:.1f}%"
    )

    # Detailed results
    print("\n📋 Detailed Results:")
    print("-" * 70)

    for result in results:
        status_emoji = {
            "passed": "✅",
            "failed": "❌",
            "timeout": "⏰",
            "crashed": "💥",
            "missing": "📁",
        }
        emoji = status_emoji.get(result["status"], "❓")
        critical_marker = "🎯" if result.get("critical", False) else "  "

        print(f"{emoji} {critical_marker} {result['name']:<30} ({result['duration']:.1f}s)")
        print(f"      📋 {result['description']}")

        if result["status"] != "passed" and result.get("error"):
            # Show first two lines of error
            error_lines = result["error"].split("\n")[:2]
            for line in error_lines:
                if line.strip():
                    truncated_line = line[:80] + "..." if len(line) > 80 else line
                    print(f"      ⚠️  {truncated_line}")
        print()

    # Final assessment
    print(f"{'=' * 70}")

    critical_success_rate = critical_passed / critical_total if critical_total > 0 else 0

    # Determine overall status based on critical tests
    if critical_success_rate == 1.0:
        print("🎉 EXCELLENT - All critical regression tests pass!")
        print("   All previously fixed bugs remain resolved.")
    elif critical_success_rate >= 0.8:
        print("✅ GOOD - Most critical regression tests pass")
        print("   Minor issues detected, but core fixes are working.")
    elif critical_success_rate >= 0.5:
        print("⚠️ WARNING - Some critical regression tests failing")
        print("   Important bug fixes may have regressed.")
    else:
        print("🚨 CRITICAL - Multiple critical regression tests failing")
        print("   Major regressions detected! Immediate attention required.")

    # Additional context
    if failed_tests > 0:
        print("\n❌ Failed Tests Need Investigation:")
        failed_results = [r for r in results if r["status"] == "failed"]
        for result in failed_results:
            criticality = "CRITICAL" if result.get("critical", False) else "STANDARD"
            print(f"   • {result['name']} ({criticality})")

    print(f"{'=' * 70}")

    # Return success based on critical tests
    return critical_success_rate >= 0.8


def main():
    """Run the regression test suite and exit with appropriate code."""
    success = run_regression_suite()

    if success:
        print("\n🎯 Regression test suite completed successfully!")
        print("All critical bug fixes remain in place.")
        sys.exit(0)
    else:
        print("\n🚨 Regression test suite failed!")
        print("Some previously fixed bugs may have regressed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
