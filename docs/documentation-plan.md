# Plan: enterprise-grade documentation

Assessed against the repo at commit `7a4696f` (27 commits, 360 tests green).

## Where this starts from

Better than most. Worth knowing before adding anything:

| Signal | State |
|---|---|
| Module docstrings | 43 / 45 |
| Public function docstrings | 176 / 186 |
| Class docstrings | 84 / 85 |
| Docstring style | Google-style, 26 files, zero Sphinx-style — already consistent |
| `docs/` | 17 files, 2,755 lines, with an index and 6 ADRs |
| Doc correctness tests | `tests/test_documentation.py` — link resolution + no invented CLI commands |

The raw material is there. This plan is not about writing more prose.

## The actual problem

**Documentation in this repo rots faster than it is written, and it has been
caught doing so five times in a single refactor:**

1. Three guides documented APIs that raise `TypeError` when executed.
2. `docs/evals.md` claimed offline mode "is what CI runs" — CI had no eval step.
3. `docs/portfolio-refinement.md` went stale twice, the second time within three
   commits of being rewritten.
4. `docs/test-baseline.md` described the pre-refactor world in the present tense.
5. The README's content-caching note described a component with zero callers.

Every one was found by a human or agent *reading* the docs, not by a check. So
the first-order work is **enforcement, not authorship**. Adding a documentation
site on top of prose that nobody verifies just publishes the rot at higher
resolution and gives it a URL.

The ordering below reflects that: make the existing docs unable to lie, then
expand coverage, then publish.

---

## Phase 1 — Make drift fail the build (~1 day)

Extend `tests/test_documentation.py`, which already proves the pattern works: it
catches unresolvable links and CLI commands that don't exist, and it is the
reason six invented commands were found.

1. **Execute the code in the docs.** The three guides shipped examples that raise
   on the first call. Extract fenced `python` blocks from `docs/*.md` and either
   run them against fakes or, at minimum, AST-parse them and assert every
   `obj.method(...)` call matches a real signature via `inspect.signature`. This
   single check would have caught `search_character_moments` missing a required
   positional, `_chunk_transcript()` never existing, and
   `adapt_content_for_platform()` missing `quality_profile`.
2. **Assert documented symbols exist.** Any backticked dotted path in `docs/`
   (`core.content_cache.ContentCache`) must be importable.
3. **Claim tags.** For statements that cannot be mechanically checked, require a
   marker tying them to evidence — `<!-- verified: c262fff -->` — and fail when
   the referenced file has changed since that commit without the tag moving.
   This is the mechanism that would have caught all five drifts above.
4. **Wire into CI** as its own job, so a docs failure is legible and not buried
   in a 360-test run.

## Phase 2 — Governance and contribution surface (~1 day)

Entirely absent today. Each of these is table stakes for a repo anyone else
touches:

- **`CONTRIBUTING.md`** — the toolchain is already unusual enough to need it:
  Python 3.11–3.12 only (3.9/3.10 fail on numpy, 3.14 has no torch wheels), `uv`
  for environment creation, `make test/lint/typecheck/eval/demo`, the `network`
  marker convention, and the rule that `core.*` is strictly typed while the rest
  is not.
- **`SECURITY.md`** — reporting channel, and the standing warnings: `.env` holds
  live credentials, the pipeline scrapes third-party sites, and generated media
  is gitignored rather than licensed.
- **`SUPPORT.md`**, **`CODE_OF_CONDUCT.md`**.
- **`.github/PULL_REQUEST_TEMPLATE.md`** with a docs checkbox, and issue
  templates for bug / feature / docs.
- **`CODEOWNERS`** — even solo, it declares intent and enables review rules.

## Phase 3 — Operational documentation (~2 days)

The largest content gap, and the one that most distinguishes an enterprise repo
from a portfolio one. Nothing currently tells an operator what to do at 3am.

- **`docs/runbook.md`** — how to run a season batch, what `--resume` guarantees
  (only a recorded success is skipped; `in_progress` is retried because a killed
  process leaves no evidence of progress), how to inspect `stats --run <id>`,
  and how to interpret the telemetry stage table.
- **`docs/troubleshooting.md`** — the real failure modes, all of which are now
  known and documented in commit messages: `WebSearchUnavailable` versus "found
  nothing", quota exhaustion, ChromaDB extras missing, ffmpeg absent, a dead
  `.venv` from another machine, Python version mismatches.
- **`docs/operations.md`** — cost and latency expectations from
  `core/telemetry.py`, the fact that no price table ships and why, quota
  behaviour, and what a run costs before you start it.
- **`docs/data-model.md`** — the SQLite schema, `PRAGMA user_version` migration
  policy, what each table means, and the retention story for generated media.
  There is now a real state machine to document.

## Phase 4 — Reference documentation (~2 days)

Only worth doing after Phase 1, because publishing unverified docs scales the
problem.

- **MkDocs + Material + `mkdocstrings`.** Renders the existing 176 docstrings
  into an API reference with no rewriting. Sphinx is the alternative; MkDocs is
  the lighter fit for a Markdown-native repo.
- **Nav by audience**, not by directory: *Use it* (README, CLI, runbook) /
  *Understand it* (architecture, ADRs, data model) / *Extend it* (contributing,
  protocols, testing) / *Assess it* (evals, telemetry, test baseline).
- **`mkdocs build --strict` in CI** so a broken reference fails.
- **Publish to GitHub Pages** on merge to the default branch.
- Pull the three uppercase guides into the generated reference where they
  duplicate docstrings, keeping only the narrative that docstrings cannot carry.

## Phase 5 — Release discipline (~0.5 day)

Two concrete defects to fix first:

- **The version is contradictory.** `pyproject.toml` says `1.0.0`;
  `CHANGELOG.md`'s newest entry is `2.1.0` dated 2025-08-18. Pick one and make
  the other follow.
- **27 commits are missing from the changelog** — everything in this refactor.

Then: adopt Keep a Changelog against semver, generate entries from the
conventional-commit history already in use, tag releases, and add a deprecation
policy (the repo has already deleted public surface — `ParallelImageGenerator`,
four source checkers — with no deprecation path, which is defensible pre-1.0 and
will not be after).

---

## Sequencing

| | Phase | Effort | Why here |
|---|---|---|---|
| 1 | Enforcement | 1 day | Everything else compounds on it |
| 2 | Governance | 1 day | Cheap, entirely absent, table stakes |
| 3 | Operations | 2 days | Largest genuine content gap |
| 4 | Reference site | 2 days | Safe only once Phase 1 holds |
| 5 | Release discipline | 0.5 day | Fixes two live contradictions |

**Roughly 6.5 days.** Phases 1 and 2 are independent and can run in parallel.

## What "enterprise grade" should not mean here

Three things worth explicitly declining, because they are the usual way
documentation programmes fail:

- **Prose volume as a proxy for quality.** This repo already deleted 1,100 lines
  of README and 17 documentation files to become clearer. The 523-line character
  guide is the next candidate for compression, not expansion.
- **Docs describing intent rather than behaviour.** Every removed claim in this
  repo — "60% visual consistency", "production ready", six phantom CLI commands —
  described what someone meant to build.
- **A published site as the goal.** A docs site is a distribution mechanism. If
  Phase 1 is skipped, it distributes the wrong thing faster.

## Audience: decided

**This is a portfolio piece.** Recorded 2026-09-19. That resolves the question
below, and changes two things:

- **Phase 4, the MkDocs reference site, is not being built.** A reviewer
  spending ten minutes reads the README and browses the repo; a generated API
  reference is not where they look. Building it would be work that photographs
  well and changes nothing about how this repo is assessed. The 176 docstrings
  it would render are already good, and they are read in the editor, where they
  are used. Revisit only if this becomes a consumed library.
- **Phase 3 was the right place to spend the effort.** Operational thinking is
  the staff-level signal, and writing the runbook found a bug that made every
  CLI subcommand fail whenever an optional dependency was absent (`541e86a`).

Phases 1, 2, 3 and 5 are done. The original question is kept below for its
reasoning.

## Open question for the owner

Who is the audience? The answer changes Phases 2–4 materially:

- **A portfolio piece** — Phase 3 matters most (operational thinking is the
  staff-level signal), Phase 2 is near-ceremonial, Phase 4 is optional polish.
- **A real multi-contributor project** — Phase 2 becomes urgent and Phase 5
  becomes binding.
- **A published library** — Phase 4 becomes the priority and the API surface
  needs a stability contract it does not currently have.

Phase 1 is worth doing under all three readings.
