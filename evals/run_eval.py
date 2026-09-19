#!/usr/bin/env python3
"""
Entry point for the generation eval.

    python evals/run_eval.py                       # offline, gated, what CI runs
    python evals/run_eval.py --mode live --record  # real Gemini, re-record fixtures
    python evals/run_eval.py --mode live --judge   # add the advisory LLM-judge signal

See docs/evals.md for what is measured, why, and what it does not capture.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    # The project is not necessarily pip-installed (the demo and main.py do the
    # same bootstrap), so put the repo root on the path before importing either
    # the harness or the production packages it drives.
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from evals.harness import run_cli

    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
