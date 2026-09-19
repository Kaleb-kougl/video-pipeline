#!/usr/bin/env python3
"""
Entry point for the generation eval.

    python evals/run_eval.py                       # offline, gated, what CI runs
    python evals/run_eval.py --mode live --record  # real Gemini, re-record fixtures
    python evals/run_eval.py --mode live --judge   # add the advisory LLM-judge signal

See docs/evals.md for what is measured, why, and what it does not capture.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _silence_langsmith_tracing() -> None:
    """Stop LangChain shipping traces to LangSmith during an offline run.

    .env sets LANGSMITH_TRACING, and LangChain picks it up on import, so an
    "offline" eval was opening connections to api.smith.langchain.com. The
    harness's own socket guard caught it and reported it as a stub bug, which
    is what it was: offline has to mean offline, and a gate that phones a third
    party is neither reproducible nor safe to run in CI.

    This must run before the harness imports LangChain, because the tracer is
    configured at import time. Live mode is left alone -- tracing a real run is
    a legitimate thing to want.
    """
    for var in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING"):
        os.environ[var] = "false"
    # Belt and braces: without an endpoint or key the tracer cannot post even
    # if some other code path re-enables the flag.
    os.environ.pop("LANGSMITH_API_KEY", None)
    os.environ.pop("LANGCHAIN_API_KEY", None)


def main() -> int:
    # The project is not necessarily pip-installed (the demo and main.py do the
    # same bootstrap), so put the repo root on the path before importing either
    # the harness or the production packages it drives.
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    if "live" not in sys.argv:
        _silence_langsmith_tracing()

    from evals.harness import run_cli

    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
