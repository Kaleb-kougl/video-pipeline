# Contributing

This is a single-maintainer repository. Pull requests are welcome but not
expected; the more useful thing this file does is tell you how to get the
toolchain working, because it has three sharp edges that are not obvious.

Everything below was checked against the repository rather than copied from a
template. If a command here does not work, that is a bug in this file — open an
issue for it.

## The three sharp edges

1. **Python 3.11 or 3.12. Nothing else.** 3.9 and 3.10 fail on the pinned
   `numpy==2.3.2` and `pydantic-core==2.33.2`; 3.14 has no `torch==2.7.1`
   wheels. `pyproject.toml` declares `requires-python = ">=3.11"`, CI runs the
   matrix on 3.11 and 3.12, and the `Makefile`'s venv bootstrap rule refuses
   outright:

   ```
   ERROR: <your python> is <its version>, but the pinned wheels
          (pydantic-core, numpy, opencv) only publish builds for Python 3.11-3.12.
   ```

   That guard sits on the `$(VENV)/bin/python` bootstrap rule — the one `make
   demo`, `make eval` and `make eval-live` depend on — and only fires when there
   is no venv yet. `make install` and `make install-demo` build the venv
   directly and are **not** guarded, so pass `PYTHON=` explicitly if your
   default `python3` is the wrong version:

   ```bash
   make install PYTHON=python3.12
   ```

2. **There are two dependency sets, and the small one cannot run the tests.**
   `requirements.txt` is the full install (~1.1 GB, 143 packages: torch,
   transformers, sentence-transformers, chromadb, scipy, scikit-learn) and is
   the only one carrying `pytest`, `pytest-asyncio` and `pytest-timeout`.
   `requirements-demo.txt` is the slim set (~0.3 GB) that `make demo` and the
   Docker image use.

   If your `.venv` was created by `make demo`, then `make test`, `make lint`,
   `make format` and `make typecheck` will stop with an explicit message naming
   the missing tool and telling you to run `make install`. They no longer fail
   with a bare `No module named ...`.

3. **`uv` is what CI and the README use; the `Makefile` uses `venv` + `pip`.**
   Both work. `uv` is faster and is what `.github/workflows/ci.yml` runs, so
   prefer it for a from-scratch setup:

   ```bash
   uv venv --python 3.12 && source .venv/bin/activate
   uv pip install -r requirements.txt
   uv pip install ruff==0.16.8 mypy==2.3.1 pre-commit && pre-commit install
   ```

   `make install` does the equivalent with stdlib `venv` and `pip`, including
   installing the pre-commit hooks.

## Make targets

Every target below exists in the `Makefile`; `make` on its own prints this list.

| Target | What it does |
|---|---|
| `make install` | Venv + full `requirements.txt` + ruff/mypy/pre-commit + hook install |
| `make install-demo` | Venv + slim `requirements-demo.txt` only |
| `make demo` | Renders a real MP4 offline via `scripts/demo.py`. No API key, no network. Bootstraps a slim venv if none exists |
| `make test` | `pytest` (network suites deselected — see below) |
| `make lint` | `ruff check .` and `ruff format --check .` |
| `make format` | `ruff check --fix .` and `ruff format .` |
| `make typecheck` | `mypy --no-incremental core` |
| `make eval` | Offline generation eval, gated. This is what CI runs |
| `make eval-live` | Same rubric against real Gemini. Needs `GOOGLE_API_KEY` |
| `make docker-demo` | Builds the demo image and runs it into `demo_output/` |
| `make clean-demo` | Deletes `demo_output/` |

`make docker-demo` is the one target that has never been executed — the
`Dockerfile` says so at the top. Its dependency set is proven (a clean venv from
`requirements-demo.txt` renders the demo), the image build is not. Treat a first
build failure there as expected work, not as a regression you caused.

Tool versions are pinned in both the `Makefile` and CI: **ruff 0.16.8**, **mypy
2.3.1**. A different ruff will produce a different diff from `make format`.

## Tests

Run them with `make test`, or `.venv/bin/python -m pytest` directly.

- **The `network` marker.** Eight test modules perform live network I/O and used
  to hang the runner indefinitely. They carry `pytestmark =
  pytest.mark.network`, and `pyproject.toml`'s `addopts` deselects them with
  `-m 'not network'`. A bare `pytest` is therefore correct and terminates. Run
  them deliberately with `pytest -m network`. If you add a test that touches the
  network, mark it — the marker is the only mechanism; there is no path-based
  ignore list any more.
- **A 120-second per-test timeout** is also in `addopts`. A test that trips it
  is almost always one that reached for the network.
- **`asyncio_mode = "auto"`**, so coroutine tests need no decorator.
- **Fixtures live in `tests/conftest.py`** and nothing there is speculative —
  every fixture has a real caller. Before writing a new fake, check for:
  `sample_episode_content`, `sample_character_analysis`, `sample_transcript`,
  `sample_episode_summary`, `fake_chat_model` (stands in for
  `init_chat_model`/Gemini, records every prompt), `temp_db_path`,
  `database_manager`, `image_factory` (writes real PNGs so the OpenCV scoring
  runs for real), `make_generator` and `fake_image_generator`.
- **Never shell out to a bare `python3`.** Use `sys.executable`, as every
  subprocess call in `tests/` and `scripts/` already does. A bare `python3`
  resolves to whatever is on `PATH`, not to the venv the suite is running in,
  which is how a test can pass locally and fail everywhere else.
- **Tests must assert, not return.** pytest ignores a return value, so
  `return False` reports as a pass. `tests/test_regression_suite.py` has an AST
  check for exactly this, because it happened.

## Typing

`mypy` runs over `core` only, with `disallow_untyped_defs = true` scoped to
`core.*` and a lenient global default. This is deliberate — see
[ADR 0003](docs/adr/0003-scoped-typing-beachhead.md). The practical rule:

- **New code in `core/` must be fully annotated.** `make typecheck` will reject
  it otherwise.
- Elsewhere annotations are welcome and unenforced.
- The typed surface is meant to ratchet outward. Widening the strict scope is a
  good PR; adding an `ignore_errors` override to make a check pass is not.

## Linting and formatting

`ruff` replaces black, flake8 and isort across the whole tree, including
`tests/`. Run `make format` before pushing, or install the pre-commit hooks
(`make install` does) and let them do it. `mypy` is deliberately kept out of
pre-commit because it is slow on this tree; CI covers it.

## The eval gate

`make eval` scores the generation prompt offline against a five-case golden set
using seven deterministic metrics. **It runs in CI and it is gated**, so a
prompt change that makes output worse fails the build. The gate fails on any of:

- aggregate below **0.750** (the current baseline is 0.772, recorded in
  `evals/baseline.json`),
- any single case regressing by more than **0.05**,
- the prompt no longer issuing the instructions the rubric grades — a contract
  check, so offline replay cannot quietly become a tautology.

If you touch a prompt, run `make eval` and put the before/after aggregate in
your PR description. If the score legitimately moves, re-record the baseline in
the same commit and say why. Details and the rubric's known blind spots:
[docs/evals.md](docs/evals.md), [ADR 0001](docs/adr/0001-deterministic-eval-rubric.md).

## Documentation

Documentation drift is this repository's defining failure mode — it has been
caught five separate times, each by a human reading the docs rather than by a
check. `tests/test_documentation.py` exists to make some of it mechanical, and
it will fail your PR if:

- the README exceeds 400 lines or loses its quickstart,
- a `docs/...` link in the README points at a file that does not exist,
- the README or `docs/cli.md` mentions a command `main.py` does not register,
- `docs/cli.md` omits a command `main.py` does register.

**If your change alters behaviour, update the docs in the same commit.** The PR
template has a checkbox for this; it is the one item on it that is not routine.

## Standing decisions

Four decisions in [`docs/adr/`](docs/adr/) constrain what a good PR looks like
here. Reading them will save a review round:

- **[0002 — additive dependency injection](docs/adr/0002-additive-dependency-injection.md).**
  Collaborators are keyword-only parameters defaulting to `None`, falling back
  to the construction they always did, with the fallback testing `is not None`
  rather than truthiness. New seams follow that shape, and no call site changes
  meaning. A Protocol gets added when there are real implementations to justify
  it, not in advance.
- **[0004 — delete rather than repair](docs/adr/0004-delete-rather-than-repair.md).**
  Code that silently does nothing gets deleted and the gap made explicit, not
  stubbed. Do not add a placeholder that returns a plausible value; raise, or
  leave it out. A crash is a bug report, a silent no-op is a false claim.
- **[0005 — measure, never estimate](docs/adr/0005-measure-never-estimate.md).**
  Every number reported is an observation. A value that could not be observed is
  reported as unavailable **with the reason**, never as a plausible default.
  This applies to docs as much as to code: do not add a timing, cost or accuracy
  figure you did not measure.
- **[0003 — scoped typing](docs/adr/0003-scoped-typing-beachhead.md).** Config
  that cannot pass is worse than no config. A gate that is on should be green.

[ADR 0006](docs/adr/0006-async-unresolved.md) is **open**: the 27 `async def`s
buy nothing today. Do not add more async without arguing it there.

## Commits and pull requests

- **Conventional commits**, matching the existing history: `feat:`, `fix:`,
  `docs:`, `test:`, `refactor:`, `style:`, `build:`.
- **The body carries the reasoning.** The ADRs in this repo were extracted from
  commit messages, because that is where the argument was made. A commit that
  says *what* changed and not *why* loses the only record of the decision.
- Branch off `main`, keep the PR focused, and make sure `make lint`,
  `make typecheck`, `make test` and `make eval` all pass locally first.

## Reporting things instead

Not every contribution is a patch. A bug report that names the failing command
and pastes the traceback is more useful than a speculative fix, and a note that
a document is wrong is more useful than both — see [SUPPORT.md](SUPPORT.md) for
where things go, and [SECURITY.md](SECURITY.md) if the problem involves
credentials or scraped content.
