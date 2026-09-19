# Refactor record: the audit, what shipped, what is left

This is the history of the refactor, not a description of the system.
**[architecture.md](architecture.md) describes the code as it is today** — if the
two ever disagree, architecture.md is right and this file is stale.

Part 1 is the audit of the tree as it was imported, kept as a record because the
reasoning is the point. Part 2 maps each finding to the commit that closed it.
Part 3 is the only forward-looking section: what is still broken or missing.

Every claim about the past is checkable with `git show <sha>`; every claim about
the present is checkable by running the command next to it.

---

## Part 1 — The audit (`5877d72`, the tree as imported)

### 1. The code overstated what it did, and the tests were green because of it

`core/visual_coherence_manager.py:568` — `_generate_with_ai`, the leaf of the
606-line visual coherence subsystem — returned
`f"/generated/consistent_image_{hash(enhanced_prompt) % 10000}.png"`: a path to a
file that was never created. At the only call site
(`agents/workflow_orchestrator.py:259`) the return value was assigned to
`consistent_image_path` and then discarded; the next line appended
`scene.get('enhanced_prompt', scene['prompt'])` instead. The retry loop and
`_update_reference_data` (which `cv2.imread`s the fabricated path) were inert.

All four tests in `tests/unit/test_visual_coherence.py` patched
`_generate_with_ai` — they mocked the one function that was never implemented and
asserted against the mock. Meanwhile `README.md:18` and `README.md:99` claimed a
**"60% improvement in visual consistency"** that no mechanism could produce.

Second instance, `agents/parallel_image_generator.py:163`:

<!-- docs-check: skip - a two-line excerpt of a deleted function's body, quoted as evidence -->

```python
# Check if it's a mock (has return_value attribute)
if hasattr(self.ai_client.models.generate_content, "return_value"):
```

Production code branching on whether it was under test. Third instance: the
platform exporters recorded successful exports in the database for video files
they never wrote.

This reordered the whole plan. A reviewer finds these in ten minutes, and after
that stops trusting the other 18,000 lines. No amount of CI, typing or dependency
injection repairs it, so integrity work went first.

### 2. Nothing here ran

The checked-in `.venv` recorded creation under a different home directory and had
no `python` binary. A clean install was broken independently:
`core/visual_coherence_manager.py:10` did a module-level `import cv2`, and opencv
appeared **zero times** in `pyproject.toml`, while
`agents/workflow_orchestrator.py` imported `VisualCoherenceManager` at module
level — so `pip install -e .` produced a package whose orchestrator raised
`ImportError` on import. `requires-python` said `>=3.9` while `numpy==2.3.2`
needs 3.11+.

### 3. Two of everything, and no way to tell which was real

`main.py` (2,344 lines) was self-described DEPRECATED and called `sys.exit(1)` if
run; `main_refactored.py` (2,035 lines) was the live entry point;
`scripts/main copy.py` was a third. `[project.scripts]` pointed at
`main_refactored:main`. `main_refactored.py:62` built a `DatabaseManager`, then
line 81 called `WorkflowOrchestrator()` with no arguments, which built a **second**
one at its own hardcoded path along with duplicate copies of six agents.
`requirements.txt`, `pyproject.toml` and `requirements-vector.txt` disagreed on
three packages. 23 markdown files under `docs/`, a 1,432-line README with zero
images for a project whose entire output is video.

### 4. No history, no gate, no seams

Not a git repository. `pyproject.toml` configured black, isort and mypy with
`disallow_untyped_defs = true` and nothing ran any of them. Zero
`Protocol`/`ABC`/`abstractmethod` across the 12,304 lines of
`agents/`+`core/`+`utils/`; 64 `except Exception` handlers; 30 `async def`s
coexisting with blocking `requests.get` and `time.sleep` in request paths.

And the staff-level omission: a nondeterministic LLM pipeline with **no golden
set, no rubric, and no way to detect that a prompt change made the output worse.**

---

## Part 2 — What shipped

| Finding | Resolved by |
|---|---|
| No version control | `5877d72` — imported as-is, so every later deletion is bisectable |
| Fabricated "60%" / "50%" README claims | `21f2eae` |
| Dead env, missing opencv, wrong `requires-python` | `584a358` (baseline recorded in [test-baseline.md](test-baseline.md)) |
| Exporters recording successes for files never written | `bf53dd6` — they now `raise NotImplementedError` honestly |
| Visual coherence stub | `36a2792` — `_generate_with_ai` delegates to an injected generator or raises |
| Mock-detection branch in production code | `7116567` — `ParallelImageGenerator` deleted outright (dead and broken) |
| 23 docs files | `8b23c2c` → 6 (8 today: `cli.md`, `evals.md` came later) |
| Three entry points | `9ca8783` — one `main.py`; `main copy.py` and the old monolith deleted |
| Script-style tests, flaky hash, unmarked network tests | `7c93c3b` — `conftest.py`, `network` marker |
| 1,305-line README | `af19935` → 181 lines, CLI reference moved to [cli.md](cli.md) |
| Nothing ran the linters | `438a58c` — CI, ruff, `mypy core`, pre-commit, Makefile |
| Four latent bugs found by static analysis | `14f3404` |
| Nothing a reviewer could run | `0e58b08` — `make demo` renders a real MP4 offline, no API key |
| No quality gate on generation | `37614a1` — eval harness, rubric, committed baseline ([evals.md](evals.md)) |
| Wrong-show transcripts, phantom coverage, character identity | `d2ac52b` |
| Last declared lint exclusion | `b1670ec` |
| Invented season lengths, silently-failing web search | `2971e15`, `93079d6` |
| Orchestrator's 11 self-constructed collaborators | `e49717c` — all injectable, constructible with no network/key/DB |

Verify with `make lint`, `make typecheck`, `make test`, `make demo`,
`python evals/run_eval.py`.

---

## Part 3 — What is still outstanding

*Last verified 2026-09-19, at `c262fff`. Entries marked **[in flight]** are being
changed in the working tree right now by concurrent work and were uncommitted
when this was written — re-run `git log --oneline` and `git status` before
trusting them either way.*

### Correctness

- ~~**`main.py:356` falls back to a hardcoded 12 episodes.**~~ **[in flight]**
  Fixed in the working tree: the call site now returns a `ProcessingResult`
  failure whose message states explicitly that discovery returning nothing is
  *not* evidence that the season is empty. Uncommitted as of `c262fff`.
- ~~**Three test modules pass under pytest but fail as scripts.**~~ Closed by
  `5b4d4df`, which promoted the `__main__` harnesses in
  `tests/test_agents_fixed.py`, `test_season_processing.py` and
  `test_transcript_source_agent.py` to real test functions — 3 vacuous tests
  became 19 real ones, and four genuine bugs in `media/media_utils.py` fell out
  of the work.
- **Two `FOLLOW-UP` ignores in `pyproject.toml`.** The `E402` per-file ignores go
  away once the project is always installed. More seriously,
  `core.metadata_schemas` and `core.visual_coherence_manager` sit behind
  `ignore_errors = true` hiding five real type errors — `create()` overrides that
  violate the base signature, a `cv2.kmeans` overload mismatch, and an `Optional`
  str used as a dict key. These need fixes, not annotations.
- ~~**The eval is not wired into anything.**~~ Closed by `cb5c640`: `make eval`
  and `make eval-live` exist, and CI runs the gate after the test suite, so a
  prompt change that regresses the score now fails the build. The same commit
  found that "offline" mode was opening connections to `api.smith.langchain.com`
  because `.env` set `LANGSMITH_TRACING` and LangChain read it at import time.
  See [ADR 0001](adr/0001-deterministic-eval-rubric.md).
- **The Dockerfile has never been built.** It says so in its own header. Derived
  from a dependency set that was proven by building a clean venv, but unverified;
  the stated image size is an estimate.
- **The eval fixtures are hand-authored, not real captures.** `--mode live
  --record` exists and has not been run; until it is, the golden set describes
  outputs a model might plausibly produce rather than ones it did.

### Structure

- **`main.py` is unsplit and still growing** — 2,265 lines when this was written,
  **2,484** as of 2026-09-19 and changing **[in flight]**. It absorbed the old
  `main_refactored.py`. Splitting it was deliberately deferred until there was a
  suite; there is one now, and the file has grown by ~220 lines since.
- **Module-level moviepy imports** in `main.py` and
  `agents/workflow_orchestrator.py` mean "instantiable in a test" still requires
  import-level surgery.
- **The media-render seam is patched, not injected.** `e49717c` made every agent
  collaborator injectable, but `create_images` / `mp4_file_enhanced` /
  `wave_file` are still module-level function calls that tests monkeypatch. That
  is the last seam, and the one the demo depends on.
- **The async decision is still unmade.** 27 `async def`s in `agents/`+`core/`
  (re-counted 2026-09-19, still 27) coexist with blocking `requests.get` and
  `time.sleep`. Now written up as
  [ADR 0006](adr/0006-async-unresolved.md), explicitly **proposed/open**: the
  recommendation is still to drop async, and the ADR records why that decision
  should wait until a season run has actually been measured.
- **56 `except Exception` handlers** across `agents/`+`core/`+`utils/` (was 60;
  re-counted 2026-09-19). Not all are wrong, but every one at an agent boundary
  should catch something specific or re-raise a domain error. **[in flight]** — a
  new `core/exceptions.py` is untracked in the working tree.
- ~~**`tenacity==9.1.2` is pinned and imported nowhere.**~~ **[in flight]** A new
  untracked `utils/retry.py` now imports it. Uncommitted as of `c262fff`; the
  hand-rolled backoff loops have not all been migrated.
- ~~**The three surviving guides have not been audited.**~~ Audited 2026-09-19
  against the current source. All three called APIs that do not exist or have
  different signatures — see the audit notes at the top of each. The three
  ChromaDB query methods require `show_name`, `_chunk_transcript` and
  `_cleanup_expired_entries` were never defined, `ProcessingResult` is a Pydantic
  model and was being subscripted, and `find_episode_transcript`'s
  `use_discovery` parameter is never read.
  `CONTENT_CACHING_GUIDE.md` was cut from ~700 lines to ~175 and should probably
  be deleted outright: `core/content_cache.py` has **zero production call
  sites**, and the guide's closing line claimed it was "integrated into the main
  video generation pipeline".

### Staff-level gaps

These are what separates a clean senior portfolio piece from a staff one. The
eval harness (`37614a1`) closed the largest of them; these remain:

- ~~**Cost and latency budgets.**~~ Landed in `c262fff`. `core/telemetry.py`
  records per-stage wall clock and per-call token usage across all three entry
  points, and is inert under `ANIME_TELEMETRY=0`. Deliberately **no price table
  ships**: the model this orchestrator hardcodes is no longer listed on the
  pricing page, so cost is `null` with a stated reason rather than an invented
  constant — [ADR 0005](adr/0005-measure-never-estimate.md),
  [telemetry.md](telemetry.md). Still missing: a `run_telemetry` table, so there
  is no cross-run p50/p95 yet.
- **Failure semantics.** A season batch is long-running, expensive and partially
  failing. Is it idempotent? Resumable? Does a crash at scene 7 of 12 cost the
  run? SQLite is present but used as a log, not a state machine. **[in flight]** —
  the working tree has run ids, `EpisodeOutcome`/`EpisodeStatus`, an
  `is_episode_complete` resume check and a new
  `tests/integration/test_season_resume.py`, all uncommitted as of `c262fff`.
- **Observability.** `LANGSMITH_API_KEY` is still not read by the application.
  The only code that touches it is `evals/run_eval.py`, which *removes* it from
  the environment so the offline eval cannot phone home (`cb5c640`). Tracing a
  live run remains unwired.
- ~~**ADRs. There are none.**~~ Six now exist in [adr/](adr/), extracted from the
  commit messages where the reasoning was originally argued: the eval rubric,
  additive DI, the `core.*` typing beachhead, delete-rather-than-repair,
  measure-never-estimate, and async as an explicitly open question.
- **The legal question.** Scraping fandom transcripts to generate derivative
  anime video. "I hadn't thought about it" is a real ding in an interview.
- **Naming.** Ten classes called `*Agent` that are sequential method calls — no
  tool loop, no planner, no autonomy — are a pipeline. Calling them stages would
  read as more sophisticated, not less.

### Blocked on the owner

- **Rotate `GOOGLE_API_KEY` and `LANGSMITH_API_KEY`.** `.env` is and always was
  gitignored, so this is precautionary rather than an active leak — but the keys
  predate the audit and have not been rotated.
- **Decide what to do with 88 MB of generated show output.** `My Hero Academia/`
  is gitignored and has never been committed. It is the only real end-to-end
  output in existence and the only plausible source for the README demo GIF,
  which is still a placeholder.

---

## Part 4 — Where the original plan was wrong

Kept because a plan that is never marked wrong was never really tested.

- **"The only reference to `main.py` is a print string at
  `tests/test_transcript_agent.py:219`."** The line number was right and the
  conclusion (it was dead) held, but it was not the only reference:
  `docs/TRANSCRIPT_AGENT_GUIDE.md:52` and `:81` instructed readers to
  `from main import TranscriptDiscoveryAgent`, and `scripts/migrate_structure.py`
  referenced it four times. The deletion was safe; the survey behind it was not
  thorough.
- **"~19,500 lines of application code."** The actual figure at `5877d72` was
  18,323 across `agents/`, `core/`, `utils/`, `media/`, `config/`, `validation/`
  and both entry points. Overstated by about 6%.
- **"Phase 3: ~2 days. Phase 5: ~5–8 days, and optional."** Tests and dependency
  injection both landed, and the estimates were not the binding constraint —
  the correctness fixes found *while* writing tests were. Four separate fix
  commits (`14f3404`, `d2ac52b`, `2971e15`, `bf53dd6`) came out of work that was
  nominally about coverage.
- **"Rename the directory to `anime-video-generator`."** Never done. The repo is
  still `htmlParser`, which is the first thing a reviewer sees.
