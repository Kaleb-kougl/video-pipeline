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
