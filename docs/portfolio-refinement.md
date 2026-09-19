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

### Correctness

- **`main.py:356` falls back to a hardcoded 12 episodes** when discovery returns
  nothing. This is the sibling of the bug `2971e15` fixed in the discovery agent;
  that commit did not touch `main.py`, so the invented season length survives at
  the call site.
- **Three test modules pass under pytest but fail as scripts** —
  `tests/test_agents_fixed.py`, `test_season_processing.py`,
  `test_transcript_source_agent.py`. Each has an `if __name__ == "__main__"` block
  and a `sys.path` bootstrap that earns them an `E402` exclusion in
  `pyproject.toml`. *(Being fixed concurrently — check `git log` before trusting
  this entry.)*
- **Two `FOLLOW-UP` ignores in `pyproject.toml`.** The `E402` per-file ignores go
  away once the project is always installed. More seriously,
  `core.metadata_schemas` and `core.visual_coherence_manager` sit behind
  `ignore_errors = true` hiding five real type errors — `create()` overrides that
  violate the base signature, a `cv2.kmeans` overload mismatch, and an `Optional`
  str used as a dict key. These need fixes, not annotations.
- **The eval is not wired into anything.** `docs/evals.md` says offline mode is
  "what CI runs", but `.github/workflows/ci.yml` has no eval step and there is no
  `make eval` target. The gate exists in the harness and nothing invokes it.
- **The Dockerfile has never been built.** It says so in its own header. Derived
  from a dependency set that was proven by building a clean venv, but unverified;
  the stated image size is an estimate.
- **The eval fixtures are hand-authored, not real captures.** `--mode live
  --record` exists and has not been run; until it is, the golden set describes
  outputs a model might plausibly produce rather than ones it did.

### Structure

- **`main.py` is 2,265 lines and unsplit.** It absorbed the old
  `main_refactored.py` and has grown since. Splitting it was deliberately
  deferred until there was a suite; there is one now.
- **Module-level moviepy imports** in `main.py` and
  `agents/workflow_orchestrator.py` mean "instantiable in a test" still requires
  import-level surgery.
- **The media-render seam is patched, not injected.** `e49717c` made every agent
  collaborator injectable, but `create_images` / `mp4_file_enhanced` /
  `wave_file` are still module-level function calls that tests monkeypatch. That
  is the last seam, and the one the demo depends on.
- **The async decision is still unmade.** 27 `async def`s in
  `agents/`+`core/` coexist with blocking `requests.get` and `time.sleep`. This is
  a batch CLI; the recommendation stands — drop async rather than complete it.
- **60 `except Exception` handlers** across `agents/`+`core/`+`utils/`. Not all
  are wrong, but every one at an agent boundary should catch something specific or
  re-raise a domain error.
- **`tenacity==9.1.2` is pinned in both dependency files and imported nowhere**,
  while three hand-rolled backoff loops remain. Low reviewer signal; cheap.
- **`docs/CHARACTER_ANALYSIS_GUIDE.md`, `CONTENT_CACHING_GUIDE.md` and
  `TRANSCRIPT_AGENT_GUIDE.md`** are the three survivors of the 23 and predate the
  consolidation. They have not been audited against the current code.

### Staff-level gaps

These are what separates a clean senior portfolio piece from a staff one. The
eval harness (`37614a1`) closed the largest of them; these remain:

- **Cost and latency budgets.** Tokens per video, p50/p95 wall clock, quota
  behaviour. *(In progress — `core/telemetry.py` and orchestrator changes exist
  in the working tree but are uncommitted as of `93079d6`; check `git log`.)*
- **Failure semantics.** A season batch is long-running, expensive and partially
  failing. Is it idempotent? Resumable? Does a crash at scene 7 of 12 cost the
  run? SQLite is present but used as a log, not a state machine.
- **Observability.** `LANGSMITH_API_KEY` appears in `.env.example` and nothing
  reads it.
- **ADRs.** There are none. The interesting ones are already written in commit
  messages — async, the `core.*` typing beachhead, record/replay evals, deleting
  `ParallelImageGenerator` rather than fixing it — and want extracting.
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
