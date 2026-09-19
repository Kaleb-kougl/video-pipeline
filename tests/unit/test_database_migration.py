"""
The schema migration and the per-episode state machine in ``core/database.py``.

There is a real database at ``data/databases/`` with real rows in it. Adding
run tracking must therefore be a migration, not a rewrite: a database written
by the previous build has to come out the other side with every row intact.
``LEGACY_SCHEMA`` below is that previous build's DDL, copied verbatim from
``core/database.py`` as of commit ``c262fff``, so these tests migrate a
genuinely old-shaped database rather than a convenient approximation of one.
"""

import sqlite3

import pytest

from core.database import SCHEMA_VERSION, DatabaseManager
from core.schemas import EpisodeStatus, RunStatus

# The pre-migration shape, verbatim. Deliberately not generated from the
# current module: a migration test that builds its "old" database out of the
# new code cannot detect a migration that was never needed.
LEGACY_SCHEMA = (
    """
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
    """,
    """
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
    """,
    """
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
    """,
)


@pytest.fixture
def legacy_db_path(tmp_path):
    """A database in the old shape, carrying rows a migration must not lose."""
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as conn:
        for statement in LEGACY_SCHEMA:
            conn.execute(statement)
        conn.execute(
            """
            INSERT INTO episodes (show, season, episode, url, transcript, summary, plot_points)
            VALUES ('My Hero Academia', '1', '1', 'https://example.invalid/e1',
                    'legacy transcript', 'legacy summary', '["a", "b"]')
        """
        )
        conn.execute(
            """
            INSERT INTO episodes (show, season, episode, url, transcript)
            VALUES ('My Hero Academia', '1', '2', 'https://example.invalid/e2', 'second')
        """
        )
        conn.execute(
            """
            INSERT INTO season_summaries (show, season, summary)
            VALUES ('My Hero Academia', 1, 'legacy season summary')
        """
        )
        conn.execute(
            """
            INSERT INTO processing_logs (episode_id, task_type, status)
            VALUES (1, 'transcript_discovery', 'completed')
        """
        )
    return path


class TestMigration:
    """An existing database must survive the upgrade with its contents intact."""

    def test_legacy_database_reports_version_zero_before_migration(self, legacy_db_path):
        """The premise: an old file is detectable because nothing ever set the pragma."""
        with sqlite3.connect(legacy_db_path) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 0

    def test_migration_preserves_every_existing_row(self, legacy_db_path):
        db = DatabaseManager(legacy_db_path)

        episode = db.get_episode("My Hero Academia", "1", "1")
        assert episode is not None
        assert episode["transcript"] == "legacy transcript"
        assert episode["summary"] == "legacy summary"
        assert episode["url"] == "https://example.invalid/e1"

        assert len(db.get_episodes_by_show("My Hero Academia")) == 2

        summary = db.get_season_summary("My Hero Academia", 1)
        assert summary is not None
        assert summary["summary"] == "legacy season summary"

        with sqlite3.connect(legacy_db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM processing_logs").fetchone()[0] == 1

    def test_migration_adds_the_new_columns_and_tables(self, legacy_db_path):
        db = DatabaseManager(legacy_db_path)

        with sqlite3.connect(legacy_db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
            tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }

        assert {"attempts", "last_error", "run_id", "completed_at"} <= columns
        assert {"runs", "run_telemetry"} <= tables
        assert db.schema_version == SCHEMA_VERSION

    def test_migration_is_idempotent(self, legacy_db_path):
        """Opening the database repeatedly must not double-apply anything."""
        DatabaseManager(legacy_db_path)
        DatabaseManager(legacy_db_path)
        db = DatabaseManager(legacy_db_path)

        assert db.schema_version == SCHEMA_VERSION
        assert len(db.get_episodes_by_show("My Hero Academia")) == 2

    def test_legacy_rows_are_not_credited_with_work_they_may_not_have_done(self, legacy_db_path):
        """
        A migrated row keeps ``pending`` and so is *not* skipped by a resume.

        The status column was never written before this change, so a legacy row
        carries no evidence that its media was ever produced. Promoting it to
        ``succeeded`` because it happens to hold a transcript would make a
        resume skip work that never happened - the one failure mode a resume
        must not have.
        """
        db = DatabaseManager(legacy_db_path)

        assert db.get_episode_status("My Hero Academia", 1, 1) is EpisodeStatus.PENDING
        assert db.is_episode_complete("My Hero Academia", 1, 1) is False

    def test_a_fresh_database_starts_at_the_current_version(self, tmp_path):
        db = DatabaseManager(str(tmp_path / "fresh.db"))
        assert db.schema_version == SCHEMA_VERSION


class TestEpisodeStateMachine:
    """``episodes.status`` as resumable state rather than a column that never moved."""

    def test_an_unknown_episode_has_no_status(self, database_manager):
        assert database_manager.get_episode_status("Show", 1, 1) is None
        assert database_manager.is_episode_complete("Show", 1, 1) is False

    def test_begin_marks_in_progress_before_any_work(self, database_manager):
        database_manager.begin_episode("Show", 1, 1, run_id="run-1")

        assert database_manager.get_episode_status("Show", 1, 1) is EpisodeStatus.IN_PROGRESS
        # in_progress is what a killed process leaves behind, and it must never
        # be mistaken for completion.
        assert database_manager.is_episode_complete("Show", 1, 1) is False

    def test_only_success_counts_as_complete(self, database_manager):
        database_manager.begin_episode("Show", 1, 1, run_id="run-1")
        database_manager.complete_episode(
            "Show", 1, 1, EpisodeStatus.FAILED, error="no transcript source", run_id="run-1"
        )
        assert database_manager.is_episode_complete("Show", 1, 1) is False

        database_manager.begin_episode("Show", 1, 1, run_id="run-1")
        database_manager.complete_episode("Show", 1, 1, EpisodeStatus.SUCCEEDED, run_id="run-1")
        assert database_manager.is_episode_complete("Show", 1, 1) is True

    def test_a_failure_records_its_reason_and_a_success_clears_it(self, database_manager):
        database_manager.begin_episode("Show", 1, 1)
        database_manager.complete_episode(
            "Show", 1, 1, EpisodeStatus.FAILED, error="429 from the source"
        )
        row = database_manager.get_episode("Show", "1", "1")
        assert row["last_error"] == "429 from the source"
        assert row["completed_at"] is None

        database_manager.begin_episode("Show", 1, 1)
        database_manager.complete_episode("Show", 1, 1, EpisodeStatus.SUCCEEDED)
        row = database_manager.get_episode("Show", "1", "1")
        assert row["last_error"] is None
        assert row["completed_at"] is not None

    def test_attempts_accumulate_across_runs(self, database_manager):
        for _ in range(3):
            database_manager.begin_episode("Show", 1, 1, run_id="run-1")
        assert database_manager.get_episode("Show", "1", "1")["attempts"] == 3

    def test_saving_an_episode_does_not_reset_its_state(self, database_manager):
        """
        The upsert in ``save_episode`` protects the state machine.

        The old ``INSERT OR REPLACE`` deleted the conflicting row, which would
        have reset status, attempts and run_id and handed the episode a new
        ``id`` - orphaning every ``processing_logs`` row pointing at it.
        """
        database_manager.begin_episode("Show", 1, 1, run_id="run-1")
        database_manager.complete_episode("Show", 1, 1, EpisodeStatus.SUCCEEDED, run_id="run-1")
        original_id = database_manager.get_episode("Show", "1", "1")["id"]

        database_manager.save_episode(
            "Show", "1", "1", "https://example.invalid/e1", "transcript", "summary", ["a"]
        )

        row = database_manager.get_episode("Show", "1", "1")
        assert row["id"] == original_id
        assert row["status"] == EpisodeStatus.SUCCEEDED.value
        assert row["attempts"] == 1
        assert row["run_id"] == "run-1"
        assert row["transcript"] == "transcript"

    def test_an_unrecognised_status_is_reported_as_unknown_not_guessed(self, database_manager):
        database_manager.save_episode("Show", "1", "1", "https://example.invalid/e1")
        with sqlite3.connect(database_manager.db_path) as conn:
            conn.execute("UPDATE episodes SET status = 'half-done'")

        assert database_manager.get_episode_status("Show", 1, 1) is None
        # Unknown means redo it, which is the safe direction to be wrong in.
        assert database_manager.is_episode_complete("Show", 1, 1) is False


class TestRunIdentity:
    """A run is a row, so a resumed run is the same run and can prove it."""

    def test_a_run_is_recorded_as_running_until_it_finishes(self, database_manager):
        database_manager.start_run("run-1", "Show", 1, command="process-season")
        assert database_manager.get_run("run-1")["status"] == RunStatus.RUNNING.value

        database_manager.finish_run("run-1", RunStatus.SUCCEEDED)
        run = database_manager.get_run("run-1")
        assert run["status"] == RunStatus.SUCCEEDED.value
        assert run["finished_at"] is not None

    def test_reopening_a_run_counts_the_resume_instead_of_forking_it(self, database_manager):
        database_manager.start_run("run-1", "Show", 1)
        database_manager.finish_run("run-1", RunStatus.PARTIAL, error="episode 3 failed")

        database_manager.start_run("run-1", "Show", 1)

        run = database_manager.get_run("run-1")
        assert run["resumed_count"] == 1
        assert run["status"] == RunStatus.RUNNING.value
        assert run["error"] is None
        assert run["finished_at"] is None

    def test_a_finished_run_is_not_offered_for_resume(self, database_manager):
        database_manager.start_run("run-1", "Show", 1)
        database_manager.finish_run("run-1", RunStatus.SUCCEEDED)
        assert database_manager.find_resumable_run("Show", 1) is None

    @pytest.mark.parametrize("status", [RunStatus.RUNNING, RunStatus.PARTIAL, RunStatus.FAILED])
    def test_any_run_that_did_not_finish_cleanly_is_resumable(self, database_manager, status):
        database_manager.start_run("run-1", "Show", 1)
        if status is not RunStatus.RUNNING:
            database_manager.finish_run("run-1", status)

        candidate = database_manager.find_resumable_run("Show", 1)
        assert candidate is not None and candidate["run_id"] == "run-1"

    def test_resume_candidates_are_scoped_to_one_show_and_season(self, database_manager):
        database_manager.start_run("run-1", "Show", 1)
        assert database_manager.find_resumable_run("Show", 2) is None
        assert database_manager.find_resumable_run("Other Show", 1) is None

    def test_run_ids_are_readable_and_sort_chronologically(self):
        first = DatabaseManager.new_run_id("My Hero Academia", 1, started_at="20260101T000000")
        second = DatabaseManager.new_run_id("My Hero Academia", 1, started_at="20260101T000001")
        assert first.startswith("My_Hero_Academia_S1_20260101T000000_")
        assert first < second

    def test_two_runs_started_in_the_same_second_get_different_ids(self):
        """
        A collision would not fail - ``start_run`` upserts, so it would quietly
        re-open the other run and let a fresh batch inherit its identity.
        """
        stamp = "20260101T000000"
        ids = {DatabaseManager.new_run_id("Show", 1, started_at=stamp) for _ in range(50)}
        assert len(ids) == 50

    def test_run_progress_reports_what_a_partial_run_accomplished(self, database_manager):
        database_manager.start_run("run-1", "Show", 1, command="process-season")
        for episode, status in ((1, EpisodeStatus.SUCCEEDED), (2, EpisodeStatus.FAILED)):
            database_manager.begin_episode("Show", 1, episode, "run-1")
            database_manager.complete_episode(
                "Show", 1, episode, status, error="boom" if status is EpisodeStatus.FAILED else None
            )
        database_manager.begin_episode("Show", 1, 3, "run-1")  # killed here

        progress = database_manager.get_run_progress("run-1")

        assert progress["found"] is True
        assert progress["status_counts"] == {"succeeded": 1, "failed": 1, "in_progress": 1}
        assert [row["episode"] for row in progress["episodes"]] == ["1", "2", "3"]
        assert progress["episodes"][1]["last_error"] == "boom"

    def test_run_progress_for_an_unknown_run_says_so(self, database_manager):
        assert database_manager.get_run_progress("nope")["found"] is False


class TestRunTelemetryTable:
    """``core/telemetry.py`` flagged that its report belongs in the database."""

    @staticmethod
    def _report(job_id: str = "job-1") -> dict:
        from core.telemetry import RunTelemetry

        telemetry = RunTelemetry(job_id)
        telemetry.start_run(job_id)
        with telemetry.stage("summarization"):
            pass
        telemetry.end_run()
        return telemetry.to_dict()

    def test_a_report_becomes_one_row_per_stage_plus_a_run_level_row(self, database_manager):
        written = database_manager.save_run_telemetry(self._report(), run_id="run-1")
        assert written == 2

        rows = database_manager.get_run_telemetry("job-1")
        assert [row["scope"] for row in rows] == ["run", "stage"]
        assert rows[0]["stage"] is None
        assert rows[0]["run_id"] == "run-1"
        assert rows[1]["stage"] == "summarization"
        assert rows[1]["ok"] == 1

    def test_a_failing_stage_records_its_error(self, database_manager):
        from core.telemetry import RunTelemetry

        telemetry = RunTelemetry("job-2")
        telemetry.start_run("job-2")
        with pytest.raises(RuntimeError), telemetry.stage("video_encode"):
            raise RuntimeError("encoder unavailable")
        telemetry.end_run()

        database_manager.save_run_telemetry(telemetry.to_dict())

        stage = database_manager.get_run_telemetry("job-2")[1]
        assert stage["ok"] == 0
        assert "encoder unavailable" in stage["error"]

    def test_retries_append_rather_than_overwrite_the_failed_attempt(self, database_manager):
        database_manager.save_run_telemetry(self._report(), run_id="run-1")
        database_manager.save_run_telemetry(self._report(), run_id="run-1")

        assert len(database_manager.get_run_telemetry("job-1")) == 4

    def test_a_disabled_collector_writes_nothing(self, database_manager):
        from core.telemetry import RunTelemetry

        telemetry = RunTelemetry("job-3", enabled=False)
        telemetry.start_run("job-3")
        telemetry.end_run()

        assert database_manager.save_run_telemetry(telemetry.to_dict()) == 0
        assert database_manager.get_run_telemetry("job-3") == []


# The v1 shape: everything `_migrate` produced at `e0264e9`, with the pragma
# set, and - the point of this fixture - *no* `season_summaries`. That table
# was created lazily by whichever season-summary method ran first, so a v1
# database that had never written a summary genuinely did not have it.
V1_SCHEMA = (
    LEGACY_SCHEMA[0],
    LEGACY_SCHEMA[1],
    """
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
    """,
    """
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
    """,
)


@pytest.fixture
def v1_db_path(tmp_path):
    """A database at schema v1, with the v1 columns and no season summaries."""
    path = str(tmp_path / "v1.db")
    with sqlite3.connect(path) as conn:
        for statement in V1_SCHEMA:
            conn.execute(statement)
        for column in (
            "attempts INTEGER NOT NULL DEFAULT 0",
            "last_error TEXT",
            "run_id TEXT",
            "completed_at TIMESTAMP",
        ):
            conn.execute(f"ALTER TABLE episodes ADD COLUMN {column}")
        conn.execute(
            """
            INSERT INTO episodes (show, season, episode, url, status, attempts)
            VALUES ('My Hero Academia', '1', '1', 'https://example.invalid/e1', 'succeeded', 2)
        """
        )
        conn.execute("PRAGMA user_version = 1")
    return path


def _tables(path: str) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class TestSeasonSummariesJoinTheMigrationPath:
    """v2: ``season_summaries`` is created by ``init_database``, not on demand.

    It used to be created by ``init_season_summaries_table``, which every
    season-summary method called on itself. That put the table outside the
    ``user_version`` path entirely: a fresh database did not have it, and no
    migration could ever be written against it because nothing knew when it
    had appeared.
    """

    def test_a_fresh_database_has_the_table_before_any_summary_is_written(self, tmp_path):
        path = str(tmp_path / "fresh.db")
        DatabaseManager(path)

        assert "season_summaries" in _tables(path)

    def test_a_v1_database_gains_the_table_and_reports_the_new_version(self, v1_db_path):
        assert "season_summaries" not in _tables(v1_db_path)

        db = DatabaseManager(v1_db_path)

        assert "season_summaries" in _tables(v1_db_path)
        assert db.schema_version == SCHEMA_VERSION == 2

    def test_the_v1_state_machine_survives_the_v2_migration(self, v1_db_path):
        """v1 -> v2 adds a table. It must not touch a row that a resume reads."""
        db = DatabaseManager(v1_db_path)

        row = db.get_episode("My Hero Academia", "1", "1")
        assert row["status"] == EpisodeStatus.SUCCEEDED.value
        assert row["attempts"] == 2
        assert db.is_episode_complete("My Hero Academia", 1, 1) is True

    def test_a_legacy_databases_existing_summaries_are_left_alone(self, legacy_db_path):
        """A v0 database already has the table, with rows. Adopting it is a no-op."""
        db = DatabaseManager(legacy_db_path)

        summary = db.get_season_summary("My Hero Academia", 1)
        assert summary is not None and summary["summary"] == "legacy season summary"
        assert db.schema_version == SCHEMA_VERSION


class TestSeasonSummaryUpsert:
    """Re-saving a season summary updates it instead of replacing the row.

    ``INSERT OR REPLACE`` deletes the conflicting row and inserts a new one -
    the bug ``save_episode`` was moved off in ``e0264e9``. Here it rotated the
    ``id`` that ``create-season-summary`` prints back to the user and reset
    ``created_at`` to now, so the row could no longer say when the season was
    first summarised.
    """

    def test_resaving_keeps_the_id(self, database_manager):
        first = database_manager.save_season_summary("Show", 1, "first pass")
        second = database_manager.save_season_summary("Show", 1, "second pass")

        assert first is not None
        assert second == first
        assert database_manager.get_season_summary("Show", 1)["summary"] == "second pass"

    def test_resaving_keeps_created_at_and_moves_updated_at(self, database_manager):
        database_manager.save_season_summary("Show", 1, "first pass")
        with sqlite3.connect(database_manager.db_path) as conn:
            conn.execute("UPDATE season_summaries SET created_at = '2020-01-01 00:00:00'")

        database_manager.save_season_summary("Show", 1, "second pass")

        row = database_manager.get_season_summary("Show", 1)
        assert row["created_at"] == "2020-01-01 00:00:00"
        assert row["updated_at"] != "2020-01-01 00:00:00"

    def test_content_is_replaced_not_merged(self, database_manager):
        database_manager.save_season_summary(
            "Show", 1, "first", analysis_data={"a": 1}, media_files={"video": "x.mp4"}
        )
        database_manager.save_season_summary("Show", 1, "second")

        row = database_manager.get_season_summary("Show", 1)
        assert row["analysis_data"] is None
        assert row["media_files"] is None

    def test_two_seasons_of_one_show_stay_separate(self, database_manager):
        database_manager.save_season_summary("Show", 1, "s1")
        database_manager.save_season_summary("Show", 2, "s2")

        assert len(database_manager.get_all_season_summaries("Show")) == 2


class TestForeignKeysAreEnforced:
    """``PRAGMA foreign_keys`` is off by default, per connection.

    Until ``_connect`` existed, ``FOREIGN KEY (episode_id) REFERENCES
    episodes (id)`` on ``processing_logs`` was decorative: SQLite parsed it and
    then ignored it on every connection this module opened.
    """

    def test_every_connection_this_module_opens_has_it_on(self, database_manager):
        with database_manager._connect() as conn:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_a_log_row_cannot_reference_an_episode_that_does_not_exist(self, database_manager):
        database_manager.log_processing_task(9999, "video_encode", "completed")

        with sqlite3.connect(database_manager.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM processing_logs").fetchone()[0] == 0

    def test_the_rejection_is_logged_not_raised(self, database_manager):
        """An audit trail must never be able to fail the run it describes."""
        database_manager.log_processing_task(9999, "video_encode", "failed", "boom", 1.5)
        # Reaching here without an exception is the assertion.

    def test_a_log_row_against_a_real_episode_is_accepted(self, database_manager):
        database_manager.save_episode("Show", "1", "1", "https://example.invalid/e1")
        episode_id = database_manager.get_episode_id("Show", 1, 1)
        assert episode_id is not None

        database_manager.log_processing_task(episode_id, "video_encode", "completed", None, 2.5)

        activity = database_manager.get_processing_stats()["recent_activity"]
        assert activity == [{"task_type": "video_encode", "status": "completed", "count": 1}]

    def test_migrating_a_legacy_database_leaves_no_violations(self, legacy_db_path):
        """Turning enforcement on must not reject the database that already exists."""
        db = DatabaseManager(legacy_db_path)

        with db._connect() as conn:
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    def test_an_unknown_episode_has_no_id(self, database_manager):
        assert database_manager.get_episode_id("Nobody", 9, 9) is None
