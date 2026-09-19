# Test baseline — a historical snapshot (2026-09-18, commit `584a358`)

> **This document describes the repository as it was *before* the refactor, and
> nothing in it describes the code today.** Every problem recorded below has
> since been fixed. It is kept because the starting point is not recoverable from
> `git log` — the commits show what was repaired, not what was broken — and
> because a "33 failed" number is what makes the later ones mean something.
>
> **For current numbers**, do not read this file. Run `make test`, or read the
> test matrix in `.github/workflows/ci.yml`, which runs on every push against
> Python 3.11 and 3.12. The most recent figure recorded in a commit message is
> **298 passed** at `c262fff`; the suite is under active change, so the command
> is the authority, not that number.
>
> For how the whole refactor unfolded, see
> [portfolio-refinement.md](portfolio-refinement.md). For the system as it stands
> now, see [architecture.md](architecture.md).

Everything below is written in the past tense as of `584a358`.

## Environment (as it was)

The `.venv` checked into the repo was dead — `pyvenv.cfg` recorded creation at
`/Users/kkougl/Desktop/Personal/htmlParser` and contained no `python` binary.

A working environment required **Python 3.11 or 3.12** (still true):
- 3.9 / 3.10 fail on `numpy==2.3.2`
- 3.14 fails on `torch==2.7.1` (no wheels)

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
pytest
```

Install resolved cleanly: 143 packages, ~1.1 GB, ~26 seconds.

## Baseline results (2026-09-18, `584a358`)

184 tests collected, 0 collection errors. **These are the pre-refactor numbers.**

| Outcome | Count |
|---|---|
| Passed | 131 |
| Failed | 33 |
| Errored | 0 |
| Skipped | 2 |
| Hung (never reported) | ~18 |

## Failures by root cause (all since resolved)

Each entry describes the state at `584a358`; the commit that closed it is named
in **bold** at the end.

1. **Live-network hangs — 7 files, ~18 tests.** `test_agents_fixed.py`,
   `test_complete_discovery.py`, `test_complex_shows.py`, `test_fandom_search.py`,
   `test_season_processing.py`, `test_transcript_agent.py`,
   `test_video_length_integration.py` perform real Fandom scraping and Google API
   calls, and exceeded 150s. Running the full suite in one process hung
   indefinitely. **Closed by `7c93c3b`** — these now require the `network` marker
   and are deselected by default (see `pyproject.toml`).

2. **Product bug — 26 failures, one root cause.**
   `AttributeError: 'ParallelImageGenerator' object has no attribute 'generate_image'`,
   raised from `core/content_cache.py:446`. The class defines
   `generate_single_image` / `generate_images_parallel`; nothing named
   `generate_image` existed. The two sides were never integrated.
   **Closed by `7116567`**, which deleted the class outright rather than
   implementing the missing method — see
   [ADR 0004](adr/0004-delete-rather-than-repair.md).

3. **Test-harness bug — 2 failures.** `tests/test_cli_video_length.py` shelled out
   to a hardcoded `'python3'` instead of `sys.executable`, escaping the venv.
   **Closed by `9ca8783`.**

4. **README drift — 4 failures.** `tests/test_documentation.py` asserted the
   README contained strings that no longer existed. **Closed by `7116567`**,
   which rewrote the four tests to assert real content.

5. **Non-deterministic assertion — 1 failure.**
   `tests/unit/test_platform_adaptation.py::test_platform_hook_generation` asserted
   on LLM-ish keyword content.

6. **Segfault at teardown — 1 file.** `tests/test_metadata_validation.py` passed all
   9 tests, then exited SIGSEGV — a torch/chromadb native teardown interaction.

Items 5 and 6 are the "3 pre-existing failures" `7116567` recorded as still
outstanding. No later commit message claims them, and they were not re-run while
this reframing was written — **check `make test` rather than assuming either
way.**

## Known gaps at the time (all closed)

These were the structural gaps at `584a358`. `7c93c3b` added `tests/conftest.py`
and the `network` marker; `tests/unit/`, `tests/integration/` and `tests/e2e/`
now all have `__init__.py` and real test modules, and pytest and its plugins are
declared. Kept as the record of where the suite started:

- No `conftest.py` anywhere; no shared fixtures.
- `tests/unit/` and `tests/integration/` lack `__init__.py`.
- `tests/e2e/` and `tests/performance/` are empty directories.
- `pytest`, `pytest-asyncio`, and `pytest-timeout` were absent from all three
  dependency files; without `pytest-asyncio` the suite aborts at collection.
