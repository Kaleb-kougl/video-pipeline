# Data model

The SQLite schema in `core/database.py`, table by table: what each column means,
what writes it and when. Read off the DDL and the writing methods at `d98476a`;
column lists are transcribed from the `CREATE TABLE` statements, not summarised.
Re-read against `d58f1c7`, which added `core.schemas.enforce_scene_cap` without
changing any column, type or writer.

<!-- verified: 7e48b43 sources: core/database.py, core/schemas.py -->

Default path `data/databases/video_generator.db` (`Settings.database_path`),
gitignored twice over (`*.db` and `data/databases/`). Everything is created or
migrated by `DatabaseManager.init_database`, which runs from `__init__`, so
merely constructing a `DatabaseManager` against the production file migrates it.

```python
from core.database import DatabaseManager

db = DatabaseManager("data/databases/video_generator.db")
print(db.schema_version)  # 2
```

Every connection this module opens goes through `DatabaseManager._connect`,
which sets `PRAGMA foreign_keys = ON`. SQLite defaults that pragma **off**, and
scopes it to one connection, so a declared foreign key enforces nothing until
something sets it — see [`processing_logs`](#processing_logs).

## Migration policy

`SCHEMA_VERSION = 2`, recorded in SQLite's `PRAGMA user_version`.

| Version | Shape |
|---|---|
| 0 | `episodes`, `processing_logs`, and sometimes `season_summaries`. Databases predating run tracking report 0 **because nothing ever set the pragma** — which is exactly what makes them detectable |
| 1 | Adds `runs` and `run_telemetry`, and the `attempts` / `last_error` / `run_id` / `completed_at` columns on `episodes` |
| 2 | Adds `season_summaries` to the migration path. The table was previously created on demand by whichever season-summary method ran first, so it was outside `user_version` entirely. The DDL is the lazy creator's, unchanged, so an existing table is untouched |

`_migrate` is **additive only**: `ALTER TABLE ... ADD COLUMN` and
`CREATE TABLE IF NOT EXISTS`. No table is dropped, no column removed, no row
rewritten — so a database migrated by a new build is still readable by an old
one. Column additions are driven by `PRAGMA table_info`, not assumed, so
re-running is safe.

**Legacy rows keep `status = 'pending'`, deliberately.** The column existed
before v1 but nothing ever wrote it, so a `pending` row from a v0 database
carries no evidence that the episode's media was ever produced. Backfilling it
to `succeeded` would make `--resume` skip work that never happened; leaving it
`pending` means the episode is redone. Wrong in the safe direction. The same
reasoning covers `get_episode_status`, which returns `None` — not a guess — for
a value it does not recognise.

## `episodes`

One row per (show, season, episode). Both content store and state machine.

| Column | Type | Written by |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | insert |
| `show`, `season`, `episode` | TEXT NOT NULL | insert. `UNIQUE(show, season, episode)` is the real key; **all three are strings**, and the run methods coerce with `str()` |
| `url` | TEXT NOT NULL | `save_episode`. `begin_episode` inserts `''` when creating a placeholder |
| `transcript`, `summary` | TEXT | `save_episode` |
| `plot_points` | TEXT | `save_episode`, as `json.dumps(list)` or NULL. Stored **untruncated**: `enforce_scene_cap` bounds the number of *images* rendered, not the summary persisted, so a row may list more plot points than the video has scenes |
| `status` | TEXT DEFAULT `'pending'` | `begin_episode` → `in_progress`; `complete_episode` → `succeeded`/`failed`. Values are `core.schemas.EpisodeStatus` |
| `created_at`, `updated_at` | TIMESTAMP | defaults / every write |
| `attempts` *(v1)* | INTEGER NOT NULL DEFAULT 0 | `begin_episode`, `+1` per attempt across all runs |
| `last_error` *(v1)* | TEXT | `complete_episode` on failure; cleared by `begin_episode` |
| `run_id` *(v1)* | TEXT | `begin_episode`; `complete_episode` via `COALESCE` so it is never blanked |
| `completed_at` *(v1)* | TIMESTAMP | `complete_episode`, **only on success** — so "when was this episode's media actually made" stays answerable |

Index: `idx_episodes_show_season_episode(show, season, episode)`.

A single-episode run never touches the state machine: only
`process_season_batch` calls `begin_episode`/`complete_episode`. A row created
by `process-episode` sits at `pending` forever.

<!-- docs-check: absent DatabaseManager.update_episode_status - deleted, see below -->

`update_episode_status` used to sit here with no callers anywhere in the
repository. It is gone. It took a bare `str` and its own docstring offered
`'completed'` — a value `EpisodeStatus` does not have, so writing it would make
`get_episode_status` return `None` and a resume redo a finished episode.
`begin_episode` and `complete_episode` are the validated writers for this
column.

### `save_episode` is an UPSERT, and that matters

```sql
INSERT INTO episodes (...) VALUES (...)
ON CONFLICT(show, season, episode) DO UPDATE SET
    url = excluded.url, transcript = excluded.transcript,
    summary = excluded.summary, plot_points = excluded.plot_points,
    updated_at = CURRENT_TIMESTAMP
```

It used to be `INSERT OR REPLACE`, which **deletes** the conflicting row and
inserts a new one. Once the row carried resumable state that had two
consequences: `status`, `attempts`, `run_id` and `created_at` were reset to
their defaults — so re-saving content silently erased the evidence a resume
depends on — and the row got a brand-new `id`, leaving every
`processing_logs.episode_id` pointing at a row that no longer existed. The
UPSERT updates content and leaves the state machine alone. Note which columns
are in the `DO UPDATE SET` list: the state columns are deliberately absent.

## `processing_logs`

The per-*episode* audit trail: one row per pipeline stage per attempt.
Append-only — a retried episode adds rows rather than replacing the failed
attempt's.

| Column | Type | Written by |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | insert |
| `episode_id` | INTEGER, `FOREIGN KEY → episodes(id)` | `get_episode_id(show, season, episode)`. **Enforced** — see below |
| `task_type` | TEXT NOT NULL | The stage name: `content_extraction`, `summarization`, `persistence`, `character_enrichment`, `quality_profile`, `prompt_construction`, `image_generation`, `audio_synthesis`, `video_encode`, and for the discovery path `transcript_discovery` / `transcript_parse` |
| `status` | TEXT NOT NULL | `completed` or `failed` |
| `error_message` | TEXT | `TypeName: message`, on a failed stage |
| `processing_time` | REAL | Stage wall-clock seconds |
| `created_at` | TIMESTAMP | Insert time |

Index: `idx_processing_logs_episode(episode_id, created_at)`.

Written by `WorkflowOrchestrator._record_processing_logs`, from the same
`finally` that publishes the telemetry report, so a failed attempt is recorded
as well as a successful one. Stage outcomes are buffered in the orchestrator
during the run and filed at the end, because the episode's row — and so the
`episodes.id` the foreign key needs — may not exist until the `persistence`
stage partway through.

`get_processing_stats` rolls the last 24 hours up into `recent_activity`, which
is what `stats` prints under "Recent activity".

**Why this and `run_telemetry` both exist.** They record the same stage
boundaries at different keys. `run_telemetry` is keyed by job id and carries
tokens and cost: it answers *what did this run cost*. It has no episode column
at all. `processing_logs` is keyed by `episodes.id`: it answers *what has
happened to episode 7*. Neither can answer the other's question, and they are
written from the same place so they cannot drift.

**The stage boundaries are not read back off the telemetry payload.**
`ANIME_TELEMETRY=0` yields an inert collector that records no stages, and an
operator who turned off timing did not ask the database to forget that a render
failed. The orchestrator's own `_stage` wrapper collects both.

**The foreign key is enforced.** `DatabaseManager._connect` sets
`PRAGMA foreign_keys = ON` on every connection, which SQLite requires per
connection and defaults to off. A log row naming an episode that does not exist
is rejected, and `log_processing_task` swallows the `IntegrityError`: an audit
trail must never be able to fail the run it describes. Enabling enforcement
found no violation in the existing database — `processing_logs` had no rows,
because nothing ever wrote it.

## `runs`

One row per season batch. This is run identity: "the same run" is a fact in the
database, not a guess.

| Column | Type | Meaning |
|---|---|---|
| `run_id` | TEXT PRIMARY KEY | From `new_run_id`: `<slug>_S<season>_<YYYYmmddTHHMMSS>_<8 hex>` |
| `show` | TEXT NOT NULL | |
| `season` | TEXT NOT NULL | Stored as a string, like `episodes.season` |
| `command` | TEXT | Provenance. `process_season_batch` passes `"process-season"` |
| `status` | TEXT NOT NULL DEFAULT `'running'` | `core.schemas.RunStatus`: `running`, `succeeded`, `partial`, `failed` |
| `start_episode`, `end_episode` | INTEGER | The requested range |
| `full_processing` | INTEGER NOT NULL DEFAULT 0 | `--full` as 0/1 |
| `resumed_count` | INTEGER NOT NULL DEFAULT 0 | `+1` each time `start_run` re-opens this id |
| `error` | TEXT | Set by `finish_run`; cleared on re-open |
| `created_at`, `updated_at`, `finished_at` | TIMESTAMP | `finished_at` is NULL until `finish_run` |

Index: `idx_runs_show_season(show, season, status)`.

`status = 'running'` is ambiguous by design — it is both a live run and a dead
one, because a process that dies cannot write its own epitaph. That ambiguity is
the signal: `find_resumable_run` returns the most recent row for a show and
season whose status is *not* `succeeded`, ordered by
`datetime(created_at) DESC, rowid DESC`.

`start_run` is an upsert on `run_id`, which is why `new_run_id` appends a random
token rather than trusting the timestamp: a colliding id would not fail, it
would silently re-open an unrelated run and increment its resume counter. Two
back-to-back runs of the same season in the same second is an ordinary thing to
do.

`episodes.run_id` and `run_telemetry.run_id` reference this table by convention
only — no foreign key is declared.

## `run_telemetry`

Append-only. One row per stage plus one run-level row per job, written by
`save_run_telemetry` from one `RunTelemetry.to_dict()` payload.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `job_id` | TEXT NOT NULL | The telemetry report's own id: `<run_id>/<label>` inside a batch, else `<label>_<isoformat>`. Falls back to `'unattributed'` |
| `run_id` | TEXT | The season run, so a resumed run's episodes stay attributable to one run |
| `scope` | TEXT NOT NULL | `'run'` or `'stage'` |
| `stage` | TEXT | Stage name; NULL on the run row |
| `wall_seconds` | REAL | |
| `ok` | INTEGER | 1 on the run row; the stage's own `ok` otherwise |
| `error` | TEXT | Stage rows only |
| `input_tokens`, `output_tokens` | INTEGER | Run row only; NULL when the provider reported no usage |
| `cost_amount`, `cost_currency`, `cost_note` | REAL / TEXT / TEXT | Run row only. `cost_amount` is NULL unless a price table was configured — see [operations.md](operations.md#cost-no-price-table-ships) |
| `started_at` | TEXT | From the payload |
| `recorded_at` | TIMESTAMP | Insert time |

Index: `idx_run_telemetry_job(job_id, scope)`.

A disabled report (`enabled: false`) or an empty payload writes nothing and
returns 0. A `sqlite3.Error` here is logged and swallowed: telemetry must never
fail a run. A retried episode appends another set of rows rather than
overwriting the failed attempt's — so the same `(run_id, episode)` can have
several jobs, and any aggregation has to decide which attempt it means.

Read back with `get_run_telemetry(job_id)`. There is no rollup query and no CLI
surface for this table.

## `season_summaries`

<!-- docs-check: absent DatabaseManager.init_season_summaries_table - deleted in the v2 migration -->

Created by `_migrate` at schema v2, like every other table. It used to be
created lazily by `init_season_summaries_table`, which `save_season_summary`
and the getters each called on themselves: a fresh database had no such table
until a summary was written, its shape was whatever the running build's lazy
creator said, and no migration could be written against it because nothing knew
when it had appeared. That method is gone.

| Column | Type |
|---|---|
| `id` | INTEGER PK AUTOINCREMENT |
| `show` | TEXT NOT NULL |
| `season` | INTEGER NOT NULL — an integer here, unlike everywhere else |
| `summary` | TEXT NOT NULL |
| `analysis_data` | TEXT, `json.dumps(dict)` |
| `media_files` | TEXT, `json.dumps(dict)` |
| `created_at`, `updated_at` | TIMESTAMP |
| | `UNIQUE(show, season)` |

Written once, from `create-season-summary`. `media_files` records
`export_format` as `"standard"` whenever a platform export was skipped, keeping
the request in `requested_export_format`, so no row claims a file that was never
produced.

### `save_season_summary` is an UPSERT too

```sql
INSERT INTO season_summaries (...) VALUES (...)
ON CONFLICT(show, season) DO UPDATE SET
    summary = excluded.summary, analysis_data = excluded.analysis_data,
    media_files = excluded.media_files, updated_at = CURRENT_TIMESTAMP
```

It used to be `INSERT OR REPLACE`, the same delete-and-reinsert that
`save_episode` was moved off. Regenerating a summary rotated the `id` that
`create-season-summary` prints back to the user and reset `created_at` to now,
so the row could no longer say when the season was first summarised. With
`PRAGMA foreign_keys` on, that hidden delete is also the orphaning hazard it
always looked like. The returned id is read back with a `SELECT` rather than
taken from `lastrowid`, which reports the inserted row only on the INSERT
branch.

The update replaces content rather than merging it: re-saving with no
`analysis_data` sets the column to NULL.

## Retention

There is no retention policy, and you should plan for that.

- **The database grows unbounded.** `core/database.py` contains no `DELETE`, no
  `DROP` and no `VACUUM`. `episodes` stores full transcripts as TEXT;
  `run_telemetry` gains a row per stage per attempt forever. Nothing prunes,
  archives or rotates.
- **Generated media is unmanaged.** MP4, WAV, PNG and JPG are gitignored, as are
  `demo_output/` and the per-show output directories. They are written under
  `<show>/Season<n>/Episode<n>/` relative to the working directory and nothing
  ever deletes them. `make clean-demo` removes `demo_output/` only.
- **Backups are manual.** The file is a plain SQLite database; copy it. Note
  that opening it with a `DatabaseManager` migrates it in place, so take the
  copy first if you want a pre-migration artifact.
