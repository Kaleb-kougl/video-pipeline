# Test baseline

Recorded before any refactoring, on a rebuilt environment. This is the reference
point for judging whether later changes improve or regress the suite.

## Environment

The `.venv` checked into this repo is dead — `pyvenv.cfg` records creation at
`/Users/kkougl/Desktop/Personal/htmlParser` and contains no `python` binary.

A working environment requires **Python 3.11 or 3.12**:
- 3.9 / 3.10 fail on `numpy==2.3.2`
- 3.14 fails on `torch==2.7.1` (no wheels)

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
pytest
```

Install resolves cleanly: 143 packages, ~1.1 GB, ~26 seconds.

## Baseline results (2026-09-18)

184 tests collected, 0 collection errors.

| Outcome | Count |
|---|---|
| Passed | 131 |
| Failed | 33 |
| Errored | 0 |
| Skipped | 2 |
| Hung (never reported) | ~18 |

## Failures by root cause

1. **Live-network hangs — 7 files, ~18 tests.** `test_agents_fixed.py`,
   `test_complete_discovery.py`, `test_complex_shows.py`, `test_fandom_search.py`,
   `test_season_processing.py`, `test_transcript_agent.py`,
   `test_video_length_integration.py` perform real Fandom scraping and Google API
   calls, and exceed 150s. Running the full suite in one process hangs indefinitely.
   These now require the `network` marker to run (see `pyproject.toml`).

2. **Product bug — 26 failures, one root cause.**
   `AttributeError: 'ParallelImageGenerator' object has no attribute 'generate_image'`,
   raised from `core/content_cache.py:446`. The class defines
   `generate_single_image` / `generate_images_parallel`; nothing named
   `generate_image` exists. The two sides were never integrated.

3. **Test-harness bug — 2 failures.** `tests/test_cli_video_length.py` shells out to
   a hardcoded `'python3'` instead of `sys.executable`, escaping the venv.

4. **README drift — 4 failures.** `tests/test_documentation.py` asserts the README
   contains strings that no longer exist.

5. **Non-deterministic assertion — 1 failure.**
   `tests/unit/test_platform_adaptation.py::test_platform_hook_generation` asserts on
   LLM-ish keyword content.

6. **Segfault at teardown — 1 file.** `tests/test_metadata_validation.py` passes all 9
   tests, then exits SIGSEGV — a torch/chromadb native teardown interaction.

## Known gaps

- No `conftest.py` anywhere; no shared fixtures.
- `tests/unit/` and `tests/integration/` lack `__init__.py`.
- `tests/e2e/` and `tests/performance/` are empty directories.
- `pytest`, `pytest-asyncio`, and `pytest-timeout` were absent from all three
  dependency files; without `pytest-asyncio` the suite aborts at collection.
