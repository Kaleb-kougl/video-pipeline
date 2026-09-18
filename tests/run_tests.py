#!/usr/bin/env python3
"""
Test runner for the Anime Video Generator test suite.
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_test_file(test_file: str, tests_dir: Path, timeout: int = 300) -> dict:
    """Run a single test file and return results.
    
    Executes a test file as a subprocess and captures its output, timing,
    and exit status to determine test success or failure.
    
    Args:
        test_file (str): Name of the test file to run
        tests_dir (Path): Directory containing test files
        timeout (int, optional): Maximum time to wait for test completion. Defaults to 300.
        
    Returns:
        dict: Test result containing status, duration, output, and error information.
            - status (str): 'passed', 'failed', 'timeout', or 'crashed'
            - duration (float): Test execution time in seconds
            - output (str): Standard output from test execution
            - error (str): Error output or error message
    """
    print(f"\n{'='*60}")
    print(f"Running {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run([
            sys.executable, f"tests/{test_file}"
        ], capture_output=True, text=True, timeout=timeout, cwd=tests_dir.parent)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"✅ {test_file} PASSED ({duration:.1f}s)")
            return {
                "status": "passed",
                "duration": duration,
                "output": result.stdout,
                "error": result.stderr
            }
        else:
            print(f"❌ {test_file} FAILED ({duration:.1f}s)")
            print(f"Error: {result.stderr}")
            return {
                "status": "failed",
                "duration": duration,
                "output": result.stdout,
                "error": result.stderr
            }
    
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_file} TIMEOUT (>{timeout}s)")
        return {
            "status": "timeout",
            "duration": timeout,
            "output": "",
            "error": f"Test timed out after {timeout} seconds"
        }
    
    except Exception as e:
        print(f"💥 {test_file} CRASHED: {e}")
        return {
            "status": "crashed",
            "duration": 0,
            "output": "",
            "error": str(e)
        }

def main():
    """Run all tests and generate summary.
    
    Discovers all test files matching the pattern 'test_*.py' in the tests
    directory, runs each test, and provides comprehensive reporting including
    success rates, timing, and detailed error information.
    
    Returns:
        None
        
    Exit Codes:
        0: Success (>=80% tests pass)
        1: Failure (<80% tests pass)
    """
    print("🧪 Anime Video Generator Test Suite Runner")
    print("=" * 60)
    
    # Get list of test files - since run_tests.py is now in tests/, use current directory
    tests_dir = Path(__file__).parent
    test_files = [f.name for f in tests_dir.glob("test_*.py")]
    
    print(f"Tests directory: {tests_dir}")
    print(f"Looking for test_*.py files...")
    all_files = list(tests_dir.glob("*.py"))
    print(f"All .py files found: {[f.name for f in all_files]}")
    
    if not test_files:
        print("❌ No test files found in tests/ directory")
        print("Available files:")
        for f in tests_dir.iterdir():
            print(f"  {f.name}")
        return
    
    print(f"Found {len(test_files)} test files:")
    for test_file in test_files:
        print(f"  - {test_file}")
    
    # Run tests
    results = {}
    start_time = time.time()
    
    for test_file in test_files:
        results[test_file] = run_test_file(test_file, tests_dir)
    
    total_time = time.time() - start_time
    
    # Generate summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r["status"] == "passed")
    failed = sum(1 for r in results.values() if r["status"] == "failed")
    timeout = sum(1 for r in results.values() if r["status"] == "timeout")
    crashed = sum(1 for r in results.values() if r["status"] == "crashed")
    
    total_tests = len(results)
    success_rate = passed / total_tests if total_tests > 0 else 0
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Timeout: {timeout}")
    print(f"Crashed: {crashed}")
    print(f"Success rate: {success_rate:.1%}")
    print(f"Total time: {total_time:.1f}s")
    
    # Detailed results
    print(f"\nDetailed Results:")
    print("-" * 40)
    
    for test_file, result in results.items():
        status_emoji = {
            "passed": "✅",
            "failed": "❌", 
            "timeout": "⏰",
            "crashed": "💥"
        }
        emoji = status_emoji.get(result["status"], "❓")
        duration = result["duration"]
        
        print(f"{emoji} {test_file:<30} ({duration:.1f}s)")
        
        if result["status"] != "passed" and result["error"]:
            # Show first line of error
            error_line = result["error"].split('\n')[0]
            if len(error_line) > 60:
                error_line = error_line[:57] + "..."
            print(f"    Error: {error_line}")
    
    # Final assessment
    print(f"\n{'='*60}")
    
    if success_rate >= 0.9:
        print("🎉 EXCELLENT - Test suite is healthy!")
    elif success_rate >= 0.8:
        print("✅ GOOD - Most tests passing, minor issues")
    elif success_rate >= 0.6:
        print("⚠️ PARTIAL - Some significant issues to address")
    else:
        print("❌ CRITICAL - Major test failures, needs attention")
    
    print(f"{'='*60}")
    
    # Return appropriate exit code
    if success_rate >= 0.8:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure

if __name__ == "__main__":
    main()
