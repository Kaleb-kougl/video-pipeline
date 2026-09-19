# Documentation

What each file here is for, and which ones describe the code as it is now versus
the code as it was.

## Start here

| File | What it is |
|---|---|
| **[architecture.md](architecture.md)** | How the system is put together, stage by stage, with a per-stage table saying plainly which stages work and which are scaffolding. **This is the authority on current state** — if any other file disagrees with it, it is right and the other file is stale. |
| **[cli.md](cli.md)** | Every command registered in `main.py`, with arguments and flags. |

## Running it

| File | What it is |
|---|---|
| **[runbook.md](runbook.md)** | Normal operating procedures: one episode, a season batch, exactly what `--resume` guarantees, how to read `stats --run <id>` and the telemetry stage table, and what the offline demo does and does not exercise. |
| **[troubleshooting.md](troubleshooting.md)** | The failure modes that have actually happened, as symptom → cause → action. `WebSearchUnavailable` versus "found nothing", missing ChromaDB extras, a dead `.venv`, ffmpeg, quota exhaustion, unimplemented platform export, hanging tests. |
| **[operations.md](operations.md)** | What a run costs in API calls per episode, what `core/telemetry.py` does and does not measure, why no price table ships, and how to supply one. |
| **[data-model.md](data-model.md)** | The SQLite schema table by table: what writes each column and when, the `PRAGMA user_version` migration policy, run identity, and the retention story. |

## Decisions

| File | What it is |
|---|---|
| **[adr/](adr/)** | Six architecture decision records, extracted from the commit messages where the reasoning was argued. Each names its commits and states the cost that was accepted. [ADR 0006](adr/0006-async-unresolved.md) is **open**, not decided. |
| **[releasing.md](releasing.md)** | What the version number means for a project with no consumers, when to bump, the deprecation regime, and why the changelog is hand-written. |

## Quality gates

| File | What it is |
|---|---|
| **[evals.md](evals.md)** | The generation eval: golden set, the seven deterministic metrics, the gate CI runs, and an explicit list of what the rubric does *not* capture. |
| **[telemetry.md](telemetry.md)** | What a run costs in wall clock and tokens, how it is measured, and why no price table ships. |

## Component guides

These are the three survivors of the 23→6 consolidation in `8b23c2c`. All three
were re-audited against the source on 2026-09-19 and carry a note at the top
saying what was wrong.

| File | What it is |
|---|---|
| **[CHARACTER_ANALYSIS_GUIDE.md](CHARACTER_ANALYSIS_GUIDE.md)** | ChromaDB character profiling, relationships and development. Note that every query method requires `show_name`. |
| **[TRANSCRIPT_AGENT_GUIDE.md](TRANSCRIPT_AGENT_GUIDE.md)** | Transcript discovery across three sources, slug generation and quality scoring. |
| **[CONTENT_CACHING_GUIDE.md](CONTENT_CACHING_GUIDE.md)** | The content cache API. **The module has no production call sites** — it is a tested library that is not wired into the pipeline. |

## History — not current state

Both of these describe the past on purpose. Neither should be read as a
description of how the system behaves today.

| File | What it is |
|---|---|
| **[portfolio-refinement.md](portfolio-refinement.md)** | The refactor record: the audit of the tree as imported, a finding-to-commit table, and (Part 3) what is still outstanding. Part 3 is the only forward-looking section, and entries in flight are marked. |
| **[test-baseline.md](test-baseline.md)** | A snapshot of the test suite *before* the refactor — 184 collected, 33 failed. Kept because the starting point is not recoverable from `git log`. **For current numbers run `make test`**, not this file. |

## Conventions

- Every claim about the past is checkable with `git show <sha>`.
- Every claim about the present is checkable by running the command next to it.
- A number that could not be measured is reported as unavailable with a reason,
  never as a plausible default — see
  [ADR 0005](adr/0005-measure-never-estimate.md).
