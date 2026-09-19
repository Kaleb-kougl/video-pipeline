"""
Database management for storing and retrieving episode information.

Beyond storing episode rows this module owns the *state machine* a season batch
resumes from. A season run makes paid LLM calls and renders a video per
episode, so a crash at episode 7 of 12 must not throw away the first six. Three
things make that possible:

``runs``
    One row per season batch, carrying the run identity that a resumed run
    reuses, so "the same run" is a fact in the database rather than a guess.

``episodes.status``
    A real per-episode state machine (see :class:`core.schemas.EpisodeStatus`)
    instead of a column that only ever read ``pending``.

``run_telemetry``
    One row per stage plus a run-level row for each job, keyed by job id - the
    shape ``core.telemetry.RunTelemetry.to_dict()`` already produces.

Schema changes are applied by :meth:`DatabaseManager.init_database`, which
migrates an existing database in place rather than expecting a fresh one; see
:data:`SCHEMA_VERSION`.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any
from uuid import uuid4

from core.schemas import EpisodeStatus, RunStatus

logger = logging.getLogger(__name__)

#: Current schema generation, recorded in SQLite's ``user_version`` pragma.
#:
#: 0 - the original shape: ``episodes``, ``processing_logs`` and (sometimes)
#:     ``season_summaries``. Databases predating run tracking report 0 because
#:     nothing ever set the pragma, which is exactly what makes them detectable.
#: 1 - adds run identity and the per-episode state machine: the ``runs`` and
#:     ``run_telemetry`` tables, and the ``attempts``/``last_error``/``run_id``/
#:     ``completed_at`` columns on ``episodes``.
SCHEMA_VERSION = 1

#: Statuses that mean "this episode's work is done; do not pay for it again".
#: Only a recorded success qualifies. ``in_progress`` deliberately does not:
#: it is what a killed process leaves behind, and the work it was doing may
#: have got anywhere from zero to almost-finished.
_COMPLETED_STATUSES = frozenset({EpisodeStatus.SUCCEEDED.value})


class DatabaseManager:
    """Manages the SQLite database for storing and retrieving episode information."""

    def __init__(self, db_path: str = "data/databases/video_generator.db"):
        """
        Initialize the DatabaseManager.

        Args:
            db_path (str): The path to the SQLite database file.
        """
        self.db_path = db_path
        self.init_database()

    def init_database(self) -> None:
        """
        Create the schema if absent, and migrate it forward if it is old.

        Safe to call on an empty path and on a database written by any earlier
        version of this file: every statement is conditional, and the column
        additions are driven by ``PRAGMA table_info`` rather than assumed. No
        existing row is rewritten - in particular, legacy rows keep their
        ``pending`` status, because the column was never written before and so
        carries no evidence that the episode's media was ever produced.
        Claiming otherwise would make a resume skip work that never happened.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Create the 'episodes' table to store details about each show episode.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show TEXT NOT NULL,
                    season TEXT NOT NULL,
                    episode TEXT NOT NULL,
                    url TEXT NOT NULL,
                    transcript TEXT,
                    summary TEXT,
                    plot_points TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show, season, episode)
                )
            """)

            # Create the 'processing_logs' table to log the status of various tasks.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    processing_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (episode_id) REFERENCES episodes (id)
                )
            """)

            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_show_season_episode
                ON episodes(show, season, episode)
            """)

            self._migrate(conn)

            logger.info("Database initialized successfully")

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    @staticmethod
    def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        """Column names currently present on ``table``."""
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """
        Bring an existing database up to :data:`SCHEMA_VERSION`, in place.

        Run inside :meth:`init_database`, so every construction of a
        ``DatabaseManager`` - including one pointed at the production file with
        real rows in it - goes through here. The steps are additive only:
        ``ALTER TABLE ... ADD COLUMN`` and ``CREATE TABLE IF NOT EXISTS``. No
        table is dropped, no row is rewritten and no column is removed, so a
        database can be migrated by a new build and still be read by an old one.
        """
        before = conn.execute("PRAGMA user_version").fetchone()[0]

        # -- episodes: the per-episode state machine's supporting columns.
        # `status` itself already exists (defaulting to 'pending'); what was
        # missing was everything needed to say *why* and *when* and *for which
        # run*, which is what turns a log into resumable state.
        episode_columns = self._existing_columns(conn, "episodes")
        for column, ddl in (
            ("attempts", "ALTER TABLE episodes ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"),
            ("last_error", "ALTER TABLE episodes ADD COLUMN last_error TEXT"),
            ("run_id", "ALTER TABLE episodes ADD COLUMN run_id TEXT"),
            ("completed_at", "ALTER TABLE episodes ADD COLUMN completed_at TIMESTAMP"),
        ):
            if column not in episode_columns:
                conn.execute(ddl)
                logger.info(f"Migrated episodes: added column {column}")

        # -- runs: one row per season batch. This is the run identity a
        # resumed run reuses, so `--resume` continues *this* run rather than
        # starting a lookalike.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                show TEXT NOT NULL,
                season TEXT NOT NULL,
                command TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                start_episode INTEGER,
                end_episode INTEGER,
                full_processing INTEGER NOT NULL DEFAULT 0,
                resumed_count INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_show_season
            ON runs(show, season, status)
        """)

        # -- run_telemetry: the table core/telemetry.py said belongs here.
        # Keyed by job id, one row per stage plus a run-level row (scope
        # 'run'). Append-only: a retried episode records another set of rows
        # rather than overwriting the evidence of the attempt that failed.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS run_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                run_id TEXT,
                scope TEXT NOT NULL,
                stage TEXT,
                wall_seconds REAL,
                ok INTEGER,
                error TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_amount REAL,
                cost_currency TEXT,
                cost_note TEXT,
                started_at TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_telemetry_job
            ON run_telemetry(job_id, scope)
        """)

        if before != SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            logger.info(f"Database schema migrated from version {before} to {SCHEMA_VERSION}")

    @property
    def schema_version(self) -> int:
        """The schema generation this database file is currently at."""
        with sqlite3.connect(self.db_path) as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    def save_episode(
        self,
        show: str,
        season: str,
        episode: str,
        url: str,
        transcript: str | None = None,
        summary: str | None = None,
        plot_points: list | None = None,
    ) -> None:
        """
        Save or update an episode's data in the database.

        Args:
            show (str): The name of the show.
            season (str): The season number.
            episode (str): The episode number.
            url (str): The URL of the episode transcript.
            transcript (str, optional): The full transcript.
            summary (str, optional): The summary of the episode.
            plot_points (list, optional): A list of key plot points.

        Note:
            This is an UPSERT, not ``INSERT OR REPLACE``. The difference
            matters now that the row carries resumable state: ``INSERT OR
            REPLACE`` deletes the conflicting row and inserts a new one, which
            would reset ``status``, ``attempts``, ``run_id`` and ``created_at``
            to their defaults and hand the episode a brand-new ``id`` - leaving
            every ``processing_logs.episode_id`` pointing at a row that no
            longer exists. Re-saving an episode now updates its content and
            leaves its state machine alone.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO episodes
                    (show, season, episode, url, transcript, summary, plot_points, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(show, season, episode) DO UPDATE SET
                        url = excluded.url,
                        transcript = excluded.transcript,
                        summary = excluded.summary,
                        plot_points = excluded.plot_points,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        show,
                        season,
                        episode,
                        url,
                        transcript,
                        summary,
                        json.dumps(plot_points) if plot_points else None,
                    ),
                )

                logger.info(f"Saved episode: {show} S{season}E{episode}")

        except sqlite3.Error as e:
            logger.error(f"Database error saving episode {show} S{season}E{episode}: {e}")
            raise

    def get_episode(self, show: str, season: str, episode: str) -> sqlite3.Row | None:
        """
        Retrieve a specific episode's data from the database.

        Args:
            show (str): The name of the show.
            season (str): The season number.
            episode (str): The episode number.

        Returns:
            sqlite3.Row: The episode data, or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM episodes WHERE show = ? AND season = ? AND episode = ?
                """,
                    (show, season, episode),
                )
                result = cursor.fetchone()

                if result:
                    logger.debug(f"Retrieved episode: {show} S{season}E{episode}")

                return result

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving episode {show} S{season}E{episode}: {e}")
            return None

    def get_episodes_by_show(self, show: str, season: str | None = None) -> list:
        """
        Get all episodes for a show, optionally filtered by season.

        Args:
            show (str): The name of the show.
            season (str, optional): The season number to filter by.

        Returns:
            list: List of episode rows.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if season:
                    cursor = conn.execute(
                        """
                        SELECT * FROM episodes 
                        WHERE show = ? AND season = ? 
                        ORDER BY CAST(season AS INTEGER), CAST(episode AS INTEGER)
                    """,
                        (show, season),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM episodes 
                        WHERE show = ? 
                        ORDER BY CAST(season AS INTEGER), CAST(episode AS INTEGER)
                    """,
                        (show,),
                    )

                return cursor.fetchall()

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving episodes for {show}: {e}")
            return []

    def log_processing_task(
        self,
        episode_id: int,
        task_type: str,
        status: str,
        error_message: str | None = None,
        processing_time: float | None = None,
    ) -> None:
        """
        Log a processing task to the database.

        Args:
            episode_id (int): The episode ID.
            task_type (str): Type of task (e.g., 'transcript_discovery', 'video_generation').
            status (str): Task status ('pending', 'completed', 'failed').
            error_message (str, optional): Error message if task failed.
            processing_time (float, optional): Time taken to complete task in seconds.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO processing_logs 
                    (episode_id, task_type, status, error_message, processing_time)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (episode_id, task_type, status, error_message, processing_time),
                )

                logger.debug(f"Logged processing task: {task_type} - {status}")

        except sqlite3.Error as e:
            logger.error(f"Database error logging task: {e}")

    def get_processing_stats(self) -> dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            dict: Statistics about processed episodes.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Get episode counts by status
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM episodes 
                    GROUP BY status
                """)
                status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

                # Get total episodes
                cursor = conn.execute("SELECT COUNT(*) as total FROM episodes")
                total = cursor.fetchone()["total"]

                # Get recent processing activity
                cursor = conn.execute("""
                    SELECT task_type, status, COUNT(*) as count 
                    FROM processing_logs 
                    WHERE created_at > datetime('now', '-24 hours')
                    GROUP BY task_type, status
                """)
                recent_activity = cursor.fetchall()

                # Runs that did not finish cleanly. A user who has lost the run
                # id of a killed batch has no other way to find it, and without
                # it they cannot resume - so the id has to be discoverable from
                # the command they would naturally reach for.
                cursor = conn.execute(
                    """
                    SELECT run_id, show, season, status, created_at
                    FROM runs
                    WHERE status != ?
                    ORDER BY datetime(created_at) DESC, rowid DESC
                    LIMIT 10
                """,
                    (RunStatus.SUCCEEDED.value,),
                )
                unfinished_runs = [dict(row) for row in cursor.fetchall()]

                return {
                    "total_episodes": total,
                    "status_counts": status_counts,
                    "recent_activity": [dict(row) for row in recent_activity],
                    "unfinished_runs": unfinished_runs,
                }

        except sqlite3.Error as e:
            logger.error(f"Database error getting stats: {e}")
            return {
                "total_episodes": 0,
                "status_counts": {},
                "recent_activity": [],
                "unfinished_runs": [],
            }

    def update_episode_status(self, show: str, season: str, episode: str, status: str) -> None:
        """
        Update the status of an episode.

        Args:
            show (str): The name of the show.
            season (str): The season number.
            episode (str): The episode number.
            status (str): New status ('pending', 'completed', 'failed').
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE episodes 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE show = ? AND season = ? AND episode = ?
                """,
                    (status, show, season, episode),
                )

                logger.debug(f"Updated episode status: {show} S{season}E{episode} -> {status}")

        except sqlite3.Error as e:
            logger.error(f"Database error updating episode status: {e}")
            raise

    # ------------------------------------------------------------------
    # Run identity and the per-episode state machine
    # ------------------------------------------------------------------

    def start_run(
        self,
        run_id: str,
        show: str,
        season: int | str,
        *,
        command: str | None = None,
        start_episode: int | None = None,
        end_episode: int | None = None,
        full_processing: bool = False,
    ) -> str:
        """
        Open a run, or re-open the existing one if ``run_id`` is already known.

        Re-opening is what makes ``--resume`` honest: the resumed pass writes
        against the same row, bumping ``resumed_count`` and clearing the
        terminal fields, so the database says "this run was continued" rather
        than showing two runs that happen to look alike.

        Args:
            run_id: Identity of the run. See :meth:`new_run_id`.
            show: Show name.
            season: Season number.
            command: The CLI command that opened it, for provenance.
            start_episode: First episode of the requested range.
            end_episode: Last episode of the requested range.
            full_processing: Whether the run does full AI/video processing.

        Returns:
            The ``run_id``, for convenient chaining.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs
                (run_id, show, season, command, status, start_episode, end_episode,
                 full_processing, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = ?,
                    resumed_count = runs.resumed_count + 1,
                    error = NULL,
                    finished_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    run_id,
                    show,
                    str(season),
                    command,
                    RunStatus.RUNNING.value,
                    start_episode,
                    end_episode,
                    1 if full_processing else 0,
                    RunStatus.RUNNING.value,
                ),
            )
        logger.info(f"Run {run_id} open for {show} season {season}")
        return run_id

    def finish_run(self, run_id: str, status: RunStatus, error: str | None = None) -> None:
        """Record a run's terminal state. A run left ``running`` is one that died."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, error = ?, finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE run_id = ?
            """,
                (status.value, error, run_id),
            )
        logger.info(f"Run {run_id} finished with status {status.value}")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """The ``runs`` row for ``run_id``, or ``None``."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return dict(row) if row else None

    def find_resumable_run(self, show: str, season: int | str) -> dict[str, Any] | None:
        """
        The most recent run for this show and season that did not finish cleanly.

        That means any status other than ``succeeded``:

        * ``running`` - either genuinely in flight, or (the case this exists
          for) a process that died before it could write its own outcome.
          Nothing here can tell those two apart, so resuming a run that is
          actually still alive is the operator's call; this only reports the
          candidate.
        * ``partial`` / ``failed`` - episodes are left to redo, which is
          precisely what a resume is for once the cause is fixed.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM runs
                WHERE show = ? AND season = ? AND status != ?
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
            """,
                (show, str(season), RunStatus.SUCCEEDED.value),
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def new_run_id(show: str, season: int | str, started_at: str | None = None) -> str:
        """
        Mint a run identity.

        Built from show, season and a timestamp so it is readable in a log line
        and sorts chronologically, plus a random token so that two runs started
        in the same second cannot collide.

        The token is not decoration. :meth:`start_run` upserts, so a colliding
        id does not fail - it silently *re-opens* the other run, and a fresh
        batch would inherit an unrelated run's identity and increment its
        resume counter. Two back-to-back runs of the same season is an ordinary
        thing to do, so second-resolution timestamps alone are not enough.
        """
        stamp = started_at or datetime.now().strftime("%Y%m%dT%H%M%S")
        slug = "".join(ch if ch.isalnum() else "_" for ch in show).strip("_") or "show"
        return f"{slug}_S{season}_{stamp}_{uuid4().hex[:8]}"

    def begin_episode(
        self, show: str, season: int | str, episode: int | str, run_id: str | None = None
    ) -> None:
        """
        Mark an episode as being worked on right now, and count the attempt.

        Written *before* any paid call, so a process killed mid-episode leaves
        ``in_progress`` behind. That is the honest record: the work started and
        nothing is known about how far it got, so a resumed run retries it
        rather than assuming either outcome.

        Creates a placeholder row when the episode has never been seen, so the
        state exists even if discovery fails before anything is saved.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO episodes (show, season, episode, url, status, attempts, run_id)
                VALUES (?, ?, ?, '', ?, 1, ?)
                ON CONFLICT(show, season, episode) DO UPDATE SET
                    status = excluded.status,
                    attempts = episodes.attempts + 1,
                    run_id = excluded.run_id,
                    last_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    show,
                    str(season),
                    str(episode),
                    EpisodeStatus.IN_PROGRESS.value,
                    run_id,
                ),
            )

    def complete_episode(
        self,
        show: str,
        season: int | str,
        episode: int | str,
        status: EpisodeStatus,
        error: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """
        Record an episode's outcome.

        ``completed_at`` is set only on success, so "when did this episode's
        media actually get made" stays answerable and is never filled in by a
        failure.
        """
        succeeded = status is EpisodeStatus.SUCCEEDED
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE episodes
                SET status = ?,
                    last_error = ?,
                    run_id = COALESCE(?, run_id),
                    completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE show = ? AND season = ? AND episode = ?
            """,
                (
                    status.value,
                    error,
                    run_id,
                    1 if succeeded else 0,
                    show,
                    str(season),
                    str(episode),
                ),
            )
        logger.debug(f"Episode {show} S{season}E{episode} -> {status.value}")

    def get_episode_status(
        self, show: str, season: int | str, episode: int | str
    ) -> EpisodeStatus | None:
        """
        The recorded state of one episode, or ``None`` if it has never been seen.

        An unrecognised value in the column (an older build, or a hand-edited
        row) is reported as ``None`` rather than guessed at, which makes a
        resume redo the episode - the safe direction to be wrong in.
        """
        row = self.get_episode(show, str(season), str(episode))
        if row is None:
            return None
        try:
            return EpisodeStatus(row["status"])
        except ValueError:
            logger.warning(
                f"Episode {show} S{season}E{episode} has unrecognised status "
                f"{row['status']!r}; treating it as unknown"
            )
            return None

    def is_episode_complete(self, show: str, season: int | str, episode: int | str) -> bool:
        """
        Whether this episode's work is already done and must not be paid for again.

        Only a recorded success counts. Rows written before run tracking
        existed report ``pending``, so they are redone - the column was never
        written back then and carries no evidence either way.
        """
        status = self.get_episode_status(show, season, episode)
        return status is not None and status.value in _COMPLETED_STATUSES

    def get_run_episodes(self, show: str, season: int | str) -> list[dict[str, Any]]:
        """Every known episode of a season with its state, in episode order."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT episode, status, attempts, last_error, run_id, completed_at, updated_at
                FROM episodes
                WHERE show = ? AND season = ?
                ORDER BY CAST(episode AS INTEGER)
            """,
                (show, str(season)),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_run_progress(self, run_id: str) -> dict[str, Any]:
        """
        What a run accomplished, for showing a user after a partial run.

        Reports the run row, a count per episode status for its season, and the
        per-episode detail. The counts are season-wide rather than
        run-scoped on purpose: after a resume the question worth answering is
        "what is done now", not "what did this particular pass touch".
        """
        run = self.get_run(run_id)
        if run is None:
            return {"run_id": run_id, "found": False, "status_counts": {}, "episodes": []}

        episodes = self.get_run_episodes(run["show"], run["season"])
        counts: dict[str, int] = {}
        for row in episodes:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {
            "run_id": run_id,
            "found": True,
            "run": run,
            "status_counts": counts,
            "episodes": episodes,
        }

    # ------------------------------------------------------------------
    # Run telemetry
    # ------------------------------------------------------------------

    def save_run_telemetry(self, payload: dict[str, Any], run_id: str | None = None) -> int:
        """
        Persist one ``RunTelemetry.to_dict()`` report.

        Writes one row per stage plus a run-level row, all keyed by the job id
        the report carries. ``run_id`` ties the job to the season batch it
        belonged to, so a resumed run's episodes stay attributable to one run.

        Telemetry must never be able to fail a pipeline run, so a database
        error here is logged and swallowed.

        Returns:
            The number of rows written (0 if the report was disabled or the
            write failed).
        """
        if not payload or not payload.get("enabled", True):
            return 0

        job_id = payload.get("run_id") or "unattributed"
        tokens = payload.get("tokens") or {}
        cost = payload.get("cost") or {}

        rows: list[tuple[Any, ...]] = [
            (
                job_id,
                run_id,
                "run",
                None,
                payload.get("wall_seconds"),
                1,
                None,
                tokens.get("input"),
                tokens.get("output"),
                cost.get("amount"),
                cost.get("currency"),
                cost.get("note") or cost.get("basis"),
                payload.get("started_at"),
            )
        ]
        for stage in payload.get("stages") or []:
            rows.append(
                (
                    job_id,
                    run_id,
                    "stage",
                    stage.get("stage"),
                    stage.get("wall_seconds"),
                    1 if stage.get("ok", True) else 0,
                    stage.get("error"),
                    None,
                    None,
                    None,
                    None,
                    None,
                    stage.get("started_at"),
                )
            )

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    """
                    INSERT INTO run_telemetry
                    (job_id, run_id, scope, stage, wall_seconds, ok, error,
                     input_tokens, output_tokens, cost_amount, cost_currency,
                     cost_note, started_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    rows,
                )
            return len(rows)
        except sqlite3.Error as e:
            logger.warning(f"Could not persist telemetry for job {job_id}: {e}")
            return 0

    def get_run_telemetry(self, job_id: str) -> list[dict[str, Any]]:
        """Every telemetry row recorded for a job id, oldest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM run_telemetry WHERE job_id = ? ORDER BY id",
                (job_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def init_season_summaries_table(self) -> None:
        """Initialize the season summaries table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS season_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    analysis_data TEXT,
                    media_files TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show, season)
                )
            """)
            logger.debug("Season summaries table initialized")

    def save_season_summary(
        self,
        show: str,
        season: int,
        summary: str,
        analysis_data: dict | None = None,
        media_files: dict | None = None,
    ) -> int | None:
        """
        Save or update a season summary.

        Args:
            show: Show name
            season: Season number
            summary: Season summary text
            analysis_data: Analysis data dictionary
            media_files: Media files dictionary

        Returns:
            The ID of the saved summary
        """
        # Ensure table exists
        self.init_season_summaries_table()

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Convert dictionaries to JSON strings
                analysis_json = json.dumps(analysis_data) if analysis_data else None
                media_json = json.dumps(media_files) if media_files else None

                # Use INSERT OR REPLACE to handle duplicates
                cursor = conn.execute(
                    """
                    INSERT OR REPLACE INTO season_summaries 
                    (show, season, summary, analysis_data, media_files, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (show, season, summary, analysis_json, media_json),
                )

                summary_id = cursor.lastrowid
                logger.info(f"Saved season summary: {show} Season {season} (ID: {summary_id})")
                return summary_id

        except sqlite3.Error as e:
            logger.error(f"Database error saving season summary: {e}")
            raise

    def get_season_summary(self, show: str, season: int) -> dict | None:
        """
        Retrieve a season summary.

        Args:
            show: Show name
            season: Season number

        Returns:
            Dictionary with summary data or None if not found
        """
        # Ensure table exists
        self.init_season_summaries_table()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM season_summaries 
                    WHERE show = ? AND season = ?
                """,
                    (show, season),
                )

                row = cursor.fetchone()
                if row:
                    return {
                        "id": row["id"],
                        "show": row["show"],
                        "season": row["season"],
                        "summary": row["summary"],
                        "analysis_data": json.loads(row["analysis_data"])
                        if row["analysis_data"]
                        else None,
                        "media_files": json.loads(row["media_files"])
                        if row["media_files"]
                        else None,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                return None

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving season summary: {e}")
            return None

    def get_all_season_summaries(self, show: str | None = None) -> list[dict]:
        """
        Retrieve all season summaries, optionally filtered by show.

        Args:
            show: Optional show name to filter by

        Returns:
            List of season summary dictionaries
        """
        # Ensure table exists
        self.init_season_summaries_table()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if show:
                    cursor = conn.execute(
                        """
                        SELECT * FROM season_summaries 
                        WHERE show = ?
                        ORDER BY season
                    """,
                        (show,),
                    )
                else:
                    cursor = conn.execute("""
                        SELECT * FROM season_summaries 
                        ORDER BY show, season
                    """)

                summaries = []
                for row in cursor.fetchall():
                    summaries.append(
                        {
                            "id": row["id"],
                            "show": row["show"],
                            "season": row["season"],
                            "summary": row["summary"],
                            "analysis_data": json.loads(row["analysis_data"])
                            if row["analysis_data"]
                            else None,
                            "media_files": json.loads(row["media_files"])
                            if row["media_files"]
                            else None,
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
                    )

                return summaries

        except sqlite3.Error as e:
            logger.error(f"Database error retrieving season summaries: {e}")
            return []
