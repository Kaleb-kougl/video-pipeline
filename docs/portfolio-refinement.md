# Portfolio Refinement Plan

Revised after three independent reviews (fact-check, hiring-manager, execution-feasibility).
Every empirical claim below was verified by running a command, not by reading code.

Goal: a repo a staff-level reviewer opens, trusts, and can run in one command.

---

## The finding that reorders everything

**The code overstates what it does, and the tests are green because of it.**

`core/visual_coherence_manager.py:568` — `_generate_with_ai`, the leaf of the entire
606-line visual coherence subsystem:

```python
# This would integrate with the existing image generation system
# For now, return a mock path that tests can work with
return f"/generated/consistent_image_{hash(enhanced_prompt) % 10000}.png"
```

It returns a path to a file that is never created. At the only call site,
`agents/workflow_orchestrator.py:259`, the return value is assigned to
`consistent_image_path` and then **discarded** — the next line appends
`scene.get('enhanced_prompt', scene['prompt'])` instead. `create_images()` then runs on the
plain prompts. The retry loop and `_update_reference_data` (which `cv2.imread`s the
fabricated path) are both inert.

All four tests in `tests/unit/test_visual_coherence.py` (lines 224, 446, 496, 611)
`patch.object(..., "_generate_with_ai")` — they mock the one function that was never
implemented and assert against the mock.

And `README.md:18` and `README.md:99` claim **"60% improvement in visual consistency."**
There is no mechanism that could produce that number.

Second instance, `agents/parallel_image_generator.py:163`:

```python
# Check if it's a mock (has return_value attribute)
if hasattr(self.ai_client.models.generate_content, "return_value"):
```

Production code branching on whether it is under test.

A reviewer finds both of these in ten minutes, and after that stops trusting the other
19,000 lines. **No amount of CI, typing, or dependency injection repairs this.** Integrity
work comes first, and it is Phase 0.

## The second finding: nothing here runs

`.venv/pyvenv.cfg` records creation at `/Users/kkougl/Desktop/Personal/htmlParser` — a
different home directory — and `.venv/bin/python` does not exist. The checked-in
environment is dead.

Worse, a clean install is broken: `core/visual_coherence_manager.py:10` does a module-level
`import cv2`, and **opencv appears zero times in `pyproject.toml`**.
`agents/workflow_orchestrator.py:15` imports `VisualCoherenceManager` at module level, so
`pip install -e .` yields a package whose orchestrator raises `ImportError` on import.
Additionally `requires-python = ">=3.9"` while `numpy==2.3.2` requires ≥3.11.

---

## Phase 0 — Truth and a baseline (~1 day, blocking)

1. **Rebuild the environment and run the suite.** `uv venv` on 3.11/3.12,
   `uv pip install -r requirements.txt`, `pytest`. Record exactly what passes. Multi-GB
   install (torch, chromadb, sentence-transformers, moviepy); budget half a day and expect
   failures. Until this is done, nobody — including this document — knows what works.
2. **Audit every capability claim in the README against something reproducible.** Delete
   the "60% visual consistency" and "50% memory reduction" claims unless you can regenerate
   them. Then: implement, delete, or explicitly label every stub. `_generate_with_ai` is
   the known one; the audit is looking for its siblings.
3. **Delete `parallel_image_generator.py:163`'s mock-detection branch.** Inject a fake
   client in tests instead. This is the single most damaging twelve lines in the repo.
4. **Rotate `GOOGLE_API_KEY` and `LANGSMITH_API_KEY`** in `.env`. It *is* gitignored, so
   this is precautionary, not an active leak. Add a committed `.env.example`.
5. **Fix the `.gitignore` doc-deletion bug BEFORE the first commit.** These patterns —
   `*_PLAN.md`, `*_SUMMARY.md`, `*_GUIDE.md`, `*_IMPLEMENTATION*.md` — currently exclude
   **15 of the 23 `.md` files under `docs/`**, including all of `docs/implementation-plans/`
   and `docs/summaries/`. Remove the patterns; delete the process-exhaust docs deliberately
   instead. Add the six root show directories, `htmlcov/`, `.coverage`, `.benchmarks/`,
   `*.log`, `.venv/`.
6. **`git init` and commit the tree AS-IS.** Then delete junk in subsequent commits.
   Committing a pre-cleaned tree makes every later deletion unrecoverable and unbisectable.
   (`My Hero Academia/` alone is 88 MB — purge it in commit 2, not before commit 1.)
7. **Rename the directory** to `anime-video-generator`.

---

## Phase 1 — One of everything (~0.5 day)

Delete `main.py` (2,344 lines, self-described DEPRECATED, `sys.exit(1)` if run — genuinely
dead; the only reference is inside a print string at `tests/test_transcript_agent.py:219`).
Delete `scripts/main copy.py`. Rename `main_refactored.py` → `main.py` and update
`[project.scripts]`, which still points at `main_refactored:main`, plus the 20+ README
invocations.

**Do not split the 2,035-line main.py yet** — that is not 0.5 day of *safe* work without a
suite.

Delete process exhaust: `docs/CLEANUP_SUMMARY.md`, `RESTRUCTURING_SUMMARY.md`,
`REPOSITORY_ORGANIZATION_COMPLETE.md`, `AI_AGENT_EXECUTION_PROMPT.md`,
`docs/AI_AGENT_PHASE2_IMPLEMENTATION_PROMPT.md`. Merge `PROJECT_STRUCTURE.md` +
`DIRECTORY_STRUCTURE.md` + `README_MODULAR.md` into one `docs/architecture.md`.

Fix `pyproject.toml`: `your-username` placeholder URLs, author "Anime Video Generator Team"
(put your name on it), `requires-python` → `>=3.11`. Add a LICENSE file — MIT is claimed
with no license present.

**Reconcile dependencies to one source.** `requirements.txt` and `pyproject.toml` disagree
today: `google-genai>=0.8.0` vs `google-generativeai==0.8.5`; `opencv-python` and `psutil`
appear only in the txt (and opencv is a hard import). A third file,
`requirements-vector.txt`, already exists with its own conflicting ranges
(`chromadb>=0.4.0` vs the pinned `==1.0.15`).

---

## Phase 2 — README and narrative (~0.5 day, highest payoff per hour)

Deliberately before the refactor: the README can be made *truthful* now, and truth is the
thing that's broken. 1,432 lines → ~150.

1. **What it does, in two sentences, above the fold — with a GIF.** The README contains
   **zero images** (`![` never appears) for a project whose entire output is video.
2. **A Mermaid pipeline diagram.** Transcript discovery → content analysis → character
   enrichment → image generation → render → platform export.
3. **Engineering notes** — 3–4 real problems with real numbers: why image generation was
   parallelized and the measured speedup, what content caching saves, what ChromaDB bought
   over naive retrieval. Only numbers that survived the Phase 0 audit.
4. Move the ~279 lines of CLI reference to `docs/cli.md`.
5. Delete the status theater: "🎉 Status: Production Ready" (line 22), the eight `(NEW!)`
   headings, "Recent Updates (August 2025)". Confident work doesn't announce itself.

Defer `docs/architecture.md` and the ADRs until after Phase 4, or you'll write them twice.

---

## Phase 3 — Tests, which do NOT require the refactor (~2 days)

Correcting the previous draft: this does not depend on dependency injection.
`tests/unit/` already contains **3,396 lines of real pytest** against `adaptive_quality`,
`visual_coherence`, `platform_adaptation`, and `content_cache` — the exact modules
previously listed as "newly target". Run them first and see what passes.

- **Do not delete the 17 script-style test files yet.** They are the only executable
  description of `discovery_agent.py` (765 lines), `transcript_source_agent.py` (681),
  `transcript_agent.py` (735), and `character_analysis_agent.py` (1,778) — none of which
  have a `tests/unit/` counterpart. Run them, harvest the real assertions, *then* delete.
- Add `conftest.py` with a fake LLM, in-memory DB, and canned transcript fixtures.
- Extend coverage of the pure domain logic: `core/intelligent_format_adapter.py`, the
  timing-ratio validators in `config/settings.py:54-59`.
- Fill `tests/e2e/` with one fully-faked pipeline run, or delete it. `tests/e2e/` and
  `tests/performance/` are both currently empty directories — promises the repo doesn't keep.

---

## Phase 4 — CI and a runnable demo (~2–3 days)

`pyproject.toml` configures black (line-length 100), isort, and mypy with
`disallow_untyped_defs = true`, and **nothing runs any of them**.

1. **CI**: ruff + pytest on the subset that passes, Python 3.11/3.12. Badge it.
2. **mypy: scope it to `core.*` from the start.** Corrected figure: by AST,
   the shipped packages have **338 functions, 295 with return annotations — 43 missing, and
   47 that would fail `disallow_untyped_defs`**. (The previous draft said "212 of 337, ~125
   failing"; that came from a line-regex that missed this codebase's many multi-line
   signatures, and overstated the work ~3x.) 47 is a day, not a week — but scope it anyway
   and widen later.
3. **Dockerfile + `make demo`** producing a real video from fixtures with a fake LLM and no
   API key. Note `tests/fixtures/images/` and `videos/` are empty; you'll need real ones.
4. **Move the ML stack to `[project.optional-dependencies] vector`** — but reconcile with
   the existing `requirements-vector.txt` rather than adding a fourth dependency source,
   and verify the optional path actually works. It currently doesn't:
   `character_analysis_agent.py:18-31` guards chromadb behind `CHROMA_AVAILABLE`, while
   `main_refactored.py:84-88` wraps `CharacterAnalysisAgent()` in `except ImportError` that
   can never fire, because the class is imported at module top.
5. **Keep the `==` pins. Generate a lockfile *from* them** (`uv lock`); un-pin one package
   at a time after the suite is green. Loosening to `>=` with no passing tests would resolve
   untested LangChain minors — and `init_chat_model` / `with_structured_output` are exactly
   what breaks across 0.3.x.

---

## Phase 5 — Architecture: seams (~5–8 days, and optional)

Do this only with a real time budget. **Half-done is strictly worse than not started**: three
Protocols and one injected agent alongside nine self-constructing ones reads worse than one
honest god object.

The problem is larger than the previous draft stated. `agents/workflow_orchestrator.py:38-79`
constructs **eleven collaborators** plus a DB and a model — not eight. And
`main_refactored.py:62` builds a `DatabaseManager` from `settings.database_path`, then line
81 calls `WorkflowOrchestrator()` with no arguments, which builds a **second** one at its
own hardcoded `db_path="data/databases/video_generator.db"`, along with duplicate copies of
six agents. DI here means untangling that duplication, not adding parameters. Every agent
also imports `media.media_utils` (moviepy) at module level, so "instantiable in a test"
requires import-level surgery too.

- Zero `Protocol`/`ABC`/`abstractmethod` exist across `agents/core/utils` (12,304 lines).
  Add protocols where a second implementation genuinely exists — the fake LLM and fake
  renderer from Phase 4 — not as a checkbox.
- **Drop async rather than completing it.** 30 `async def`s in `agents/`+`core/` coexist
  with blocking `requests.get` (5 surviving call sites) and `time.sleep` in request paths
  (`transcript_source_agent.py:215,509`, `discovery_agent.py:206,289,760`). This is a batch
  CLI; only `parallel_image_generator.py` benefits, and a thread pool covers it. Completing
  the async migration *and* DI simultaneously is the classic stall.
- Narrow the blanket handlers: **64** `except Exception` handlers in `agents/core/utils`
  (112 across all application code). Not all — but every one at an agent boundary should
  catch something specific or re-raise a domain error.
- Replace three hand-rolled backoff loops (`transcript_agent.py:385-391`,
  `parallel_image_generator.py:244`, `discovery_agent.py:289`) with `tenacity`, already a
  declared and entirely unused dependency. Low priority: near-zero reviewer signal.

---

## What separates senior from staff here

The plan above, fully executed, produces a clean senior portfolio piece. It is a hygiene
plan, and hygiene is not what staff is assessed on. Missing entirely, from both the plan and
the repo:

- **An eval harness.** This is a nondeterministic LLM pipeline with no golden set, no
  rubric, and no way to detect that a prompt change made output worse. That is the first
  question a staff engineer asks about a system like this, and Phase 3 tests only the
  deterministic parts.
- **Cost and latency budgets.** Tokens per video, p50/p95 wall clock, quota behavior.
- **Failure semantics.** A season batch is long-running, expensive, and partially failing.
  Is it idempotent? Resumable? Does a crash at scene 7 of 12 cost the run? SQLite is present
  but used as a log, not a state machine.
- **Observability.** A `LANGSMITH_API_KEY` sits in `.env` and nothing uses it.
- **A documented decision you'd now make differently.**
- **The legal question**: scraping fandom transcripts to generate derivative anime video.
  "I hadn't thought about it" is a real ding in an interview.

One further note worth acting on: ten classes named `*Agent` that are sequential method
calls — no tool loop, no planner, no autonomy — are a pipeline, not agents. Renaming them
"stages" would read as more sophisticated, not less.

---

## If you only have one weekend

1. Rebuild env, run pytest, record what passes. (~half a day; may consume the morning.)
2. Rotate both API keys. (10 min)
3. Fix the four `.gitignore` doc patterns; `git init`; commit as-is; second commit deletes
   the 88 MB of generated output and the junk files.
4. Delete `main.py` / `main copy.py` / the process-exhaust docs; rename
   `main_refactored.py`; fix `[project.scripts]`, author, URLs; add LICENSE.
   **Do not split main.py.** (~1.5 h)
5. Kill the mock-detection branch at `parallel_image_generator.py:163` and either delete
   the visual-coherence subsystem or label it unimplemented — and remove the "60%" claim
   from the README either way. (~1 h)
6. README → ~150 lines + GIF + Mermaid diagram + engineering notes; CLI to `docs/cli.md`.
   (~4 h, highest payoff in the document.)
7. CI: ruff + pytest on the passing subset. No mypy gate. Badge it. (~2 h)

Skip Phase 5 entirely, plus Docker, mypy, un-pinning, and ADRs.

---

## The decision to make before anything else

~19,500 lines of application code across ten agent modules and five manager classes is
surface area a reviewer can question and you must defend. The right cut is not
"fewer agents" — it's **one spine that is genuinely real end to end, everything else
deleted or moved behind an honest "not implemented" boundary.** Breadth defended well beats
depth; breadth with a decorative subsystem and a fabricated metric beats nothing.

Make this call at step 0, because it determines what you delete in step 4.
