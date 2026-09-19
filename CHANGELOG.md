# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
What a version number means for a project with no downstream consumers, and how
a release is cut, are in [docs/releasing.md](docs/releasing.md).

Entries are written by hand from the commit history. Every commit message in
this repository states what changed and why it was wrong before; a generator
would reproduce the subject lines and throw away the reasoning, which is the
part worth keeping.

## [Unreleased]

Nothing yet.

## [3.0.0] - 2026-09-19

Thirty-two commits reworking a codebase that claimed more than it did. The same
defect kept recurring in different costumes: a component that reported success
without doing the work — exporters that wrote no file, a coherence scorer that
never executed, quality gates that computed a score and dropped it, regression
suites that could not fail, a README advertising six commands that were never
registered. This release deletes those, fixes the ones worth keeping, and puts
automated checks in front of the claims that remain.

Major, not minor: public surface was deleted with no deprecation path, several
commands behave differently, and the SQLite schema now migrates on open.

The first honest test baseline was 131 passed / 33 failed / roughly 18 hanging
the runner. It is now 372 passed, 2 skipped, 20 network-marked and deselected
by default.

### Removed

Everything in this section is breaking for anything importing the package.

- **`ParallelImageGenerator`** (513 lines). Zero production call sites, and
  broken at the one integration point that would have used it: it never defined
  the `generate_image(prompt)` method `core/content_cache.py` calls. That single
  mismatch produced 26 of the 33 baseline test failures. It also carried the
  worst pattern in the repository — production code branching on whether it was
  running under test. The caller now documents the protocol it requires and
  raises a descriptive `TypeError` rather than an implicit `AttributeError`.
- **Four transcript source checkers** — MyAnimeList, AniDB, Anime News Network
  and Crunchyroll. Each was a comment followed by `return None  # Placeholder`,
  wired into the discovery fan-out, so a caller could not distinguish "checked,
  found nothing" from "never checked". Deleted rather than stubbed further; an
  `UNSEARCHED_SOURCES` constant and the completion log now name the gap.
- **Two of the three entry points.** `main_refactored.py` became `main.py`; the
  2,344-line self-deprecated monolith and `scripts/main copy.py` are gone, and
  the `anime-generator` console script points at the survivor.
- **Three methods defined twice on the CLI facade** (`analyze_episode_quality`,
  `discover_show_episodes`, `generate_content_summary`). Python kept the second
  of each pair; the unreachable first halves called agent methods that do not
  exist, so removing them is behaviour-preserving.
- **The `BaseMetadata` create-override relationship.** A genuine Liskov
  violation: the base advertised three arguments and both subclasses demanded
  more, so no caller holding a base instance could ever use it. Each concrete
  class now has its own named constructor and shares the common step.
- **Dead discovery configuration.** `known_source_patterns` advertised
  `community_sites` and `streaming_platforms` that the search step never
  iterated. The domains were not discarded — they now back the source analyser,
  which previously hardcoded its own copies.
- **Non-code deletions**: the empty `tests/performance/` directory (there is no
  benchmarking here, and claiming otherwise was one of the removed README
  claims), two root scratch scripts, and seventeen documentation files of
  process exhaust — retrospectives about having reorganised the repository,
  plans for work that never shipped, and two zero-byte files.

### Changed

- **Platform export no longer records fabricated successes.** *Breaking.* The
  four exporters returned a hardcoded `{'success': True, 'file_size': <literal>}`
  with the comment "simulate the export process" — no ffmpeg, no file — and the
  pipeline wrote that dict into the database as a completed export. `export_video()`
  now keeps the real work and raises `NotImplementedError` naming what real
  export would require. The caller degrades instead of lying: it logs the skip,
  records `success=False` with `status='skipped_not_implemented'`, and stores the
  format actually produced alongside the one requested.
- **Discovery no longer returns another show's transcript.** *Breaking.* The
  legacy URL fallback interpolated any requested show's season and episode into
  a URL hardcoded to one series, and the result validated and was returned under
  the requested show's name — silent data corruption rather than a crash. The
  fallback is now gated on an explicit legacy-show check, so shows that used to
  "find" a URL now correctly find none. Finding none is the honest answer.
- **Season lengths are probed, not invented.** *Breaking.* Unknown shows were
  walked to a magic 25 episodes, and the season length was then taken from the
  length of that invented list. Discovery now probes from episode 1, stops after
  three consecutive misses, discards trailing misses, keeps interior gaps, caps
  at 60 probes, and records `episode_count_source` and `season_coverage` on every
  result. The hardcoded fallback of 12 episodes in the CLI is now an error:
  discovery returning nothing is not evidence that the season is empty.
- **Web search is opt-in and fails loudly.** *Breaking.* Scraping Google's HTML
  is blocked or rate-limited in practice, so this leg failed in the field while
  appearing to work. It is now off by default and raises `WebSearchUnavailable`
  on request errors, non-200, captcha and block markers, redirects and zero
  parseable links — the parser cannot tell "no results" from "the markup
  changed". The error text states that unavailable is not the same as searched
  and found nothing.
- **`--target-minutes` now changes the output.** *Breaking.* It built an adaptive
  prompt, discarded it, and delegated to a method hardcoding a five-minute
  structure. Season summaries now honour the requested length, so generated
  content differs from previous runs.
- **The database migrates on open.** *Breaking.* `PRAGMA user_version` 0 → 1,
  additive, applied on every manager construction. `episodes.status` becomes a
  real state machine (`pending` / `in_progress` / `succeeded` / `failed`) with
  `attempts`, `last_error`, `run_id` and `completed_at`; `save_episode` changes
  from `INSERT OR REPLACE` — which deleted and re-inserted the row, resetting
  state and `created_at` — to an upsert; `runs` and `run_telemetry` tables are
  new. Legacy rows deliberately stay `pending`: the column was never written, so
  it carries no evidence that the media exists.
- **Python 3.11 or 3.12 is required** (was `>=3.9`). *Breaking.* The pinned numpy
  needs 3.11 and torch publishes no 3.14 wheels, so the old floor could not have
  installed.
- **The orchestrator takes its collaborators by injection.** Thirteen
  keyword-only parameters, each defaulting to exactly the construction it always
  did, so no existing call site changes meaning. Previously the CLI built a
  database manager and then constructed the orchestrator with no arguments,
  which built a second one at a different path plus duplicate copies of six
  agents — two databases and two agent sets per process.
- **Toolchain.** ruff replaces black, flake8 and isort; mypy is scoped strictly
  to `core.*` against a lenient global default, because the previous
  `disallow_untyped_defs` config would have failed on 47 functions the moment
  anything ran it.

### Added

- **`make demo` renders a real MP4 offline, with no API key.** It drives the
  real orchestrator and fakes only four external boundaries — HTTP, the chat
  model, the ChromaDB-backed character agent, and TTS — so parsing, persistence,
  prompt enrichment, frame rendering and the full ffmpeg encode are genuine.
  Offline is enforced, not promised: sockets to non-loopback addresses raise.
  A slim `requirements-demo.txt` avoids the 1.1 GB ML stack.
- **An eval harness for the generation prompt**, scoring five golden cases on
  seven deterministic metrics with no LLM judge in the gated score, plus a
  contract check asserting the production prompt still issues what the rubric
  grades. `make eval` and `make eval-live` exist and CI runs the gate, so a
  prompt change that regresses the score fails the build.
- **Cost and latency measurement.** Per-stage wall-clock and per-call token
  usage, a stage table, an optional JSON artifact, and complete inertness when
  `ANIME_TELEMETRY=0`. Eleven stage timers at real call boundaries.
- **Resumable season batches.** `--resume` continues a provably identical run
  rather than a lookalike. Only a recorded success is skipped; `in_progress` is
  retried, because a killed process leaves no evidence of how far it got.
- **CI, pre-commit and a Makefile**: a dependency-free lint job, a test matrix on
  3.11 and 3.12, a separate documentation job, and install/test/lint/format/
  typecheck/eval/demo targets that bootstrap their own environment and name the
  missing tool when one is absent.
- **Three runtime-checkable protocols** for the seams that have two real
  implementations today, and a retry helper built on the `tenacity` dependency
  that had been pinned everywhere and imported nowhere.
- **Documentation that fails the build when it drifts.** Fenced Python examples
  are validated against real signatures, documented symbols must exist, the eval
  scorecard is compared to the committed baseline, and "CI runs X" claims are
  checked against the workflow. Alongside it: six ADRs, a runbook, a
  troubleshooting guide, operations and data-model references, `CONTRIBUTING`,
  `SECURITY`, `SUPPORT`, `CODE_OF_CONDUCT`, issue and PR templates, `CODEOWNERS`,
  `LICENSE` and `.env.example`.
- **A real test suite.** Shared fixtures, a `network` marker so a bare `pytest`
  terminates, and an end-to-end test driving the orchestrator with only external
  boundaries faked.

### Fixed

- **Visual coherence did nothing at all.** Image generation returned a path to a
  file it never created; the scorer then read that path, got `None`, and raised
  into the orchestrator's broad handler, so every scene on every run silently
  took the fallback and 314 lines of consistency scoring never executed once in
  production. The prompt-building half is now public and wired in, so generated
  images genuinely carry coherence enrichment; generation is an injected
  callable that raises rather than fabricating a path.
- **A `None` dictionary key silently pooled unrelated episodes.** An absent
  episode id is a perfectly valid key, so every context without one shared a
  single bucket of style templates and colour palettes: the first image set "the"
  palette and every later image from an unrelated episode was scored against it,
  producing a plausible number rather than an error.
- **Character identity was a field that lied.** The canonical name echoed its
  input and aliases were always empty. Surface-form canonicalization now merges
  variants and populates aliases. Two bugs fell out of that work: colliding
  cleaned names overwrote each other and dropped dialogue, and the
  stage-direction filter compared upper-case constants to title-case names, so
  it had never matched and "Narrator" and "Flashback" were being treated as
  characters.
- **Four media bugs**, all hidden by a local import shadowing the module import:
  the silent-audio fallback allocated the whole buffer at once (roughly 576 MB
  for a long transcript), the sample rate was not forwarded so a non-default rate
  drifted video timing, and the fallback did not create its parent directory.
- **Retry never ran** for the most common failure: the fetch helper returns
  `None` rather than raising, and the loop's `break` sat outside the success
  branch, so an unreachable URL reported "max retries exceeded" after exactly one
  attempt.
- **Character-store write failures were swallowed**, so analysis handed back
  profiles that never reached the database and every later query reported "no
  data" instead of "the writes failed". Eleven blanket handlers narrowed; three
  kept broad on purpose and upgraded so the traceback survives.
- **ChromaDB was never actually optional.** The CLI caught the import error and
  passed `None` on, and the orchestrator's `None` branch reconstructed the agent
  uncaught — so without the vector extras every subcommand died at construction.
  Three guards now degrade to a stated reason naming `requirements-vector.txt`.
- **`process-season` could never process episode 1** (a config lookup called with
  three arguments where it takes two), and run identifiers collided within a
  second, silently re-opening an earlier run and inheriting its identity.
- **The `summarize` command produced nothing.** It called a content-agent method
  that does not exist, raised into a broad `except`, and returned `None`.
- **Quality gates that never gated.** Three sites computed a validation score and
  dropped it. Measuring the score showed it was meaningless at those call sites —
  realistic good content scores 0.60 against a critical 0.70 gate, so enabling it
  would have aborted every run — so the dead calls were removed with the reason
  recorded at each site rather than a threshold invented to make them pass.
  Deduplication was also applied after critical issues had already been derived
  from the undeduplicated list.
- **A test that failed roughly one run in six**: hook selection used `hash()` on a
  string under a comment claiming determinism, and string hashing is seeded per
  process. Now a CRC.
- **The offline eval was not offline.** `.env` set LangSmith tracing, LangChain
  reads it at import time, and the "offline" run opened connections to a third
  party — caught by the harness's own socket guard. Tracing is now disabled
  before the harness is imported and the key is dropped as a second barrier.
- **Environment gaps that made the suite unrunnable**: pytest, pytest-asyncio and
  pytest-timeout were missing from all three dependency files, and seven network-
  scraping test files hung the runner indefinitely.

### Known gaps

Recorded because they are the kind of thing a changelog usually hides:

- Platform export raises `NotImplementedError` by design. It is scaffolding, not
  a feature.
- The eval's grounding metric is entity overlap, not entailment, so a summary
  that inverts every relationship can still score well.
- The content cache has no production caller, so every scene is still generated
  from scratch.
- `processing_logs` is never written, so the "recent activity" view is
  structurally always empty.
- No live paid run has ever been recorded, so there are no real cost figures,
  and image and speech spend is not instrumented at all.

## [2.1.0] - 2025-08-18

Entries below this line predate the format above and are kept as written, with
one correction noted.

### 🔧 Critical Bug Fixes

#### ChromaDB Array Boolean Evaluation Fixes
- **Fixed**: "The truth value of an array with more than one element is ambiguous" errors
- **Affected Files**: 
  - `agents/character_analysis_agent.py`
  - `scripts/migrate_metadata.py` 
  - `utils/vector_search.py`
  - `agents/quality_agents/metadata_quality_agent.py`
- **Impact**: Character analysis now works correctly without crashing
- **Details**: Replaced direct numpy array boolean evaluation with explicit length and None checks

#### Google AI Client API Updates
- **Fixed**: Updated from deprecated `google-generativeai` to `google-genai` SDK
- **Affected Files**:
  - `media/media_utils.py`
  - `requirements.txt`
  - `README.md`
  - `docs/README_MODULAR.md`
- **Changes**:
  - `genai.Client()` → `genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))`
  - `generate_content()` → `generate_images()` for image generation
  - Updated model names: `imagen-3.0-generate-002`
  - Added proper configuration classes: `GenerateImagesConfig`
- **Impact**: Image and audio generation now work with current Google AI SDK

#### File Path Consistency
- **Fixed**: Consistent path construction between image generation and video creation
- **Impact**: Videos now properly find generated images, preventing missing file errors

#### Season Analysis Retrieval
- **Fixed**: Season episode data retrieval works without array errors
- **Impact**: Season summary creation now completes successfully

### 📦 Dependencies Updated

#### New Dependencies Added
- `opencv-python>=4.8.0` - Required for Phase 2 visual coherence features
- `psutil>=5.8.0` - Required for Phase 2 adaptive quality management
- `google-genai>=0.8.0` - New unified Google AI SDK

#### Dependencies Removed
- `google-generativeai==0.8.5` - Deprecated, replaced by google-genai

### 🧪 Testing Infrastructure

#### New Regression Test Suite
- **Added**: Comprehensive regression test suite (`tests/test_regression_suite.py`)
- **Coverage**:
  - ChromaDB array boolean evaluation fixes (`tests/test_chromadb_array_fixes.py`)
  - Google AI client initialization fixes (`tests/test_google_ai_client_fixes.py`)
  - File path consistency validation (`tests/test_file_path_consistency.py`)
  - Character season analysis validation (`tests/test_character_season_analysis.py`)
- **Documentation**: Complete test documentation (`REGRESSION_TESTS.md`)

### 🎯 Phase 2 Validation
- **Confirmed**: All Phase 2 features working correctly with fixes
- **Components Validated**:
  - Visual Coherence Manager
  - Adaptive Quality Manager  
  - Intelligent Format Adapter
  - Episode Character Enhancer
- **Integration**: Full workflow orchestrator integration confirmed

### 📝 Documentation Updates
- **Updated**: README.md with correct Google AI SDK usage
- **Updated**: requirements.txt with new dependencies
- **Updated**: docs/README_MODULAR.md with current dependency information
- **Added**: REGRESSION_TESTS.md comprehensive testing guide

### ✅ Validation Results
- **End-to-End Testing**: ✅ PASSED
- **Phase 2 Integration**: ✅ PASSED  
- **Character Analysis**: ✅ WORKING (previously broken)
- **Season Summary Creation**: ✅ FUNCTIONAL
- **Regression Test Suite**: ✅ 100% SUCCESS RATE

> **Correction, 2026-09-19.** The last claim was false when written. Three of
> the four suites listed above kept their real checks inside a `__main__`
> harness that pytest never collected, and a fourth returned a boolean instead
> of asserting, so a failing result passed. All six of their checks failed when
> finally run. Fixed in 3.0.0; the claim is left in place because deleting it
> would hide why the checks in 3.0.0 exist.

## [2.0.0] - Phase 2 Quality Enhancement

- Added advanced AI-powered quality improvements
- Character analysis integration
- Visual coherence management
- Adaptive quality settings
- Intelligent platform adaptation

## [1.0.0] - Initial Release

- Basic anime video generation pipeline
- Transcript discovery and processing
- AI content generation
- Video compilation and export
