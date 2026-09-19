# Runbook

Normal operating procedures. Every command here was run, or read off the source
that implements it, at `d98476a`. For failures see
[troubleshooting.md](troubleshooting.md); for cost and latency see
[operations.md](operations.md); for what the database holds see
[data-model.md](data-model.md).

<!-- verified: 1875ce6 sources: main.py, core/database.py, core/schemas.py, core/telemetry.py, scripts/demo.py, config/settings.py -->

## Before you start

| Check | Command | Expect |
|---|---|---|
| Interpreter | `python -V` | 3.11 or 3.12. Nothing else has wheels — see the guard in `Makefile` |
| Environment | `make install` | Full deps (~1.1 GB). `make install-demo` is the ~0.3 GB subset and is **not** enough to run the CLI |
| Credentials | `cat .env.example` | `GOOGLE_API_KEY` is what the paid path needs |
| Nothing works yet? | `make demo` | Renders an MP4 offline with no key and no network |

`make install-demo` deliberately omits ChromaDB. `python main.py <anything>`
constructs `CharacterAnalysisAgent`, which raises `ImportError` without it — see
[troubleshooting.md](troubleshooting.md#every-cli-command-dies-with-importerror-chromadb-not-available).

## One episode

```bash
python main.py process-episode "My Hero Academia" 1 4 --full
```

Without `--full` the run stops after transcript discovery and persistence. With
`--full` it runs content analysis, character enrichment, image generation, TTS
and the MoviePy encode.

**A single-episode run is not tracked as a run.** `process_episode_by_numbers`
never calls `begin_episode`/`complete_episode`, so nothing is written to `runs`
and the episode row keeps the `pending` default from `save_episode`. Only
`process-season` drives the state machine. Do not read `stats` as a report on
single-episode work.

## A season

```bash
python main.py process-season "My Hero Academia" 1 --start 1 --end 5 --full
```

The season length comes from `EpisodeConfigs.DEFAULT_CONFIGS` in
`config/settings.py`, which knows exactly three shows: *My Hero Academia*,
*Attack on Titan* and *Frieren: Beyond Journey's End*. For anything else
`process_season_batch` returns `None`, prints `No run was started (see the log
for why)`, and writes no `runs` row at all. That is deliberate — the repo used
to invent a season length.

Between episodes the batch sleeps `random.uniform(2, 5)` seconds, but only after
real work. A resume that skips ten episodes does not sleep for a server it never
contacted.

On exit the CLI prints the run id, the per-episode outcome and, when the run did
not finish cleanly, the exact resume command.

## Resume semantics

This is the part worth reading twice. The specification is
`tests/integration/test_season_resume.py`; the implementation is
`AnimeVideoGenerator.process_season_batch` plus `core/database.py`.

```bash
python main.py process-season "My Hero Academia" 1 --full --resume
python main.py process-season "My Hero Academia" 1 --full --resume --run-id <id>
```

**`--resume` reuses a run identity.** It calls `find_resumable_run(show,
season)`, which returns the most recent `runs` row for that show and season
whose status is anything other than `succeeded`, and adopts its `run_id`.
`start_run` then upserts that row: `resumed_count` goes up by one, `error` and
`finished_at` are cleared. Two passes over the same season are one run in the
database, not two that look alike. `--run-id` skips the lookup and implies
`--resume`.

**Only a recorded success is skipped.** `is_episode_complete` returns true for
exactly one value of `episodes.status` — `succeeded` (`_COMPLETED_STATUSES` in
`core/database.py`). Everything else is redone:

| Status | On resume | Why |
|---|---|---|
| `succeeded` | **skipped** — no discovery, no model call, no render, no delay | `completed_at` is set, so the media demonstrably exists |
| `in_progress` | retried | A killed process leaves this behind. It stopped somewhere between starting the episode and recording an outcome, and nothing knows where |
| `failed` | retried | A transcript source being down is not "done". `last_error` says what happened, and it may be transient |
| `pending` | retried | Written by `save_episode` before the state machine existed, or by a legacy row. The column carries no evidence either way |
| unrecognised | retried | `get_episode_status` logs a warning and returns `None` rather than guessing |

**Legacy rows stay `pending` on purpose.** The 0 → 1 migration is additive: it
adds columns and tables and rewrites no row. Backfilling `succeeded` would make
a resume skip work that was never done. See
[data-model.md](data-model.md#migration-policy).

**Without `--resume` nothing is skipped.** A fresh run mints a new `run_id` and
redoes every episode in the range, so a deliberate reprocess is never silently a
no-op (`test_without_resume_the_batch_redoes_everything`).

**`--resume` with nothing to resume is not an error.** It logs that no
unfinished run was found and starts a new one, reporting `resumed=False`.

**A run is never given a terminal status on the way out of a crash.** There is
no `except BaseException` around the episode loop: a Ctrl-C leaves the run at
`running` and the episode at `in_progress`, which is exactly the evidence
`--resume` looks for. Nothing can distinguish a dead run from a live one, so
resuming a batch that is actually still running is the operator's call.

## Inspecting state

```bash
python main.py stats
python main.py stats --run <run_id>
```

`stats` lists up to ten runs whose status is not `succeeded`, so an operator who
has lost the run id of a killed batch can still find it. Real output from a
seeded database whose third episode failed its encode and was then killed:

```
Processing Statistics:
Total episodes: 3
Status counts: {'in_progress': 1, 'succeeded': 2}

Recent activity (last 24h):
  audio_synthesis: completed x3
  character_enrichment: completed x3
  content_extraction: completed x3
  image_generation: completed x3
  persistence: completed x3
  prompt_construction: completed x3
  quality_profile: completed x3
  summarization: completed x3
  video_encode: completed x2
  video_encode: failed x1

Runs that did not finish cleanly:
  My_Hero_Academia_S1_20260919T101144_17039f1e (running) - My Hero Academia season 1
Inspect one with: stats --run <run_id>
```

`Recent activity` is a 24-hour rollup of `processing_logs`, one row per
pipeline stage per attempt, written by the orchestrator from the same `finally`
that prints the telemetry table. It used to be structurally always empty: the
table had no writer anywhere in the repository and the section printed a bare
`[]`. Two things it still does not cover:

- **Only 24 hours.** `none` means nothing ran today, not that nothing ever ran.
  For the full history of one episode, query the table by `episode_id`; for one
  run, use `stats --run`.
- **An attempt that dies before the episode row exists logs nothing.**
  `processing_logs.episode_id` is an enforced foreign key, so a run that fails
  during `content_extraction` on an episode `begin_episode` never touched has
  nothing to attach its stages to.

```
Run My_Hero_Academia_S1_20260919T101144_17039f1e: running
  My Hero Academia season 1, command process-season
  started 2026-09-19 17:11:44, finished -
  episode states: {'succeeded': 2, 'in_progress': 1}
    E1: succeeded (attempts 1)
    E2: succeeded (attempts 1)
    E3: in_progress (attempts 1)
```

The status counts are season-wide, not scoped to the pass you are inspecting:
after a resume the useful question is "what is done now".

Straight from Python, when you want more than the CLI prints:

```python
from core.database import DatabaseManager

db = DatabaseManager("data/databases/video_generator.db")
run = db.find_resumable_run("My Hero Academia", 1)
if run is not None:
    progress = db.get_run_progress(run["run_id"])
    print(progress["status_counts"])
    for row in progress["episodes"]:
        print(row["episode"], row["status"], row["attempts"], row["last_error"])
```

## Telemetry

Every orchestrator entry point prints a stage table on the way out, of both the
success and the failure branch. The columns are the stage name, the
[architecture.md](architecture.md) stage it maps to (`-` when the architecture
document does not number it), wall-clock seconds from `time.perf_counter()`, its
share of the measured total, and status. A stage that raised is recorded with
`FAILED (...)` and the exception still propagates. Below the table: the run
wall-clock, the residual outside instrumented stages, the LLM calls with their
token counts, and the cost block. A worked example is in
[telemetry.md](telemetry.md#what-a-run-prints).

```bash
python main.py --telemetry-json runs/ process-episode "My Hero Academia" 1 4 --full
python main.py --no-telemetry process-season "My Hero Academia" 1 --full
ANIME_TELEMETRY=0 make demo
```

`--no-telemetry` and `--telemetry-json` are global flags and must come **before**
the subcommand; they set `ANIME_TELEMETRY` and `ANIME_TELEMETRY_JSON` before
anything constructs an orchestrator, because `RunTelemetry.from_env` is read at
construction time. A directory (or a path ending in a separator) gets one
`telemetry-<job id>.json` per run; anything else is used as the filename.

Telemetry is also written to the `run_telemetry` table by `_record_telemetry`,
from the same `finally` that prints it, keyed by job id and tied to the season
`run_id`. Reporting and persistence both swallow their own errors: telemetry can
never fail a run.

## The offline demo

```bash
make demo        # renders demo_output/*.mp4, no key, no network
make docker-demo # same, in a container, with --network none
make clean-demo  # delete what it wrote
```

`scripts/demo.py` clears `GOOGLE_API_KEY`, `GEMINI_API_KEY` and
`GOOGLE_APPLICATION_CREDENTIALS` before importing anything that reads them, then
monkeypatches `socket.connect` so an off-box call raises `DemoMadeANetworkCall`.
"No network" is checked, not promised. Its first step renders the branding intro
clip through a real MoviePy encode, which doubles as an ffmpeg preflight before
the main render starts.

**Exercised for real:** BeautifulSoup parsing, content extraction and quality
validation, SQLite persistence (a real `.db` is written), character-weighted
scene timing, adaptive quality profile selection, visual-coherence prompt
construction, PIL frame rendering via the production no-key fallback, and the
MoviePy/ffmpeg encode.

**Not exercised:** the HTTP scrape (canned page), Gemini summarisation (replayed
JSON), Imagen (the production no-key placeholder branch), Gemini TTS (a locally
synthesised tone), and ChromaDB character analysis (a canned stand-in). The demo
therefore proves nothing about transcript discovery against live sites, about
token cost, or about the latency of any paid stage — see
[operations.md](operations.md#the-demo-numbers-are-not-production-numbers).

## Tests

```bash
make test       # pytest; -m 'not network' and --timeout=120 come from pyproject
make lint
make typecheck  # core.* only
make eval       # offline generation eval against the golden set
```

Eight test modules carry `pytestmark = pytest.mark.network` and are deselected
by default. Run them deliberately and expect them to be slow or to hang — see
[troubleshooting.md](troubleshooting.md#the-test-suite-hangs).
