from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.match_execution as match_execution
from api.database import Base
from api.models import Bot, BotSubmission, Match, MatchJob, Move
from worker import main as worker_main
from tests.elf_fixture import static_arm64_elf


def make_sessionmaker():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed_bot(db, *, name, game_id="tictactoe"):
    bot = Bot(name=name, game_id=game_id)
    db.add(bot)
    db.flush()
    submission = BotSubmission(
        bot_id=bot.id,
        version=1,
        executable=static_arm64_elf(),
        executable_size=len(static_arm64_elf()),
        executable_digest="0" * 64,
    )
    db.add(submission)
    db.flush()
    bot.active_submission_id = submission.id
    db.commit()
    db.refresh(bot)
    return bot


class FakeSandbox:
    def __init__(self, name):
        self.command = [name]
        self.cleaned = False

    def cleanup(self):
        self.cleaned = True


def test_execute_match_persists_match_moves_and_ratings(monkeypatch):
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    bot_one = seed_bot(db, name="alpha")
    bot_two = seed_bot(db, name="beta")

    def fake_build_bot_sandbox(bot):
        return FakeSandbox(bot.name)

    def fake_run_tictactoe_match(p1_command, p2_command, on_move, **_kwargs):
        assert p1_command == ["alpha"]
        assert p2_command == ["beta"]
        on_move("p1", (0, 0), [])
        on_move("p2", (1, 1), [])
        return {"winner": "p1", "reason": "win"}

    monkeypatch.setattr(match_execution, "build_bot_sandbox", fake_build_bot_sandbox)
    monkeypatch.setattr(
        match_execution,
        "run_tictactoe_match",
        fake_run_tictactoe_match,
    )

    match = match_execution.execute_match(
        db,
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        move_timeout_seconds=2.0,
        startup_timeout_seconds=10.0,
    )
    db.commit()

    persisted = db.query(Match).one()
    assert persisted.id == match.id
    assert persisted.game_id == "tictactoe"
    assert persisted.bot_one_id == bot_one.id
    assert persisted.bot_two_id == bot_two.id
    assert persisted.winner_bot_id == bot_one.id
    assert persisted.result_reason == "win"
    assert persisted.bot_one_rating_before == 1200
    assert persisted.bot_two_rating_before == 1200
    assert persisted.bot_one_rating_after == 1216
    assert persisted.bot_two_rating_after == 1184

    moves = db.query(Move).order_by(Move.move_number).all()
    assert [(move.move_number, move.bot_id, move.move) for move in moves] == [
        (1, bot_one.id, [0, 0]),
        (2, bot_two.id, [1, 1]),
    ]


def test_run_once_claims_and_completes_queued_job(monkeypatch):
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    bot_one = seed_bot(db, name="alpha")
    bot_two = seed_bot(db, name="beta")
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="queued",
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    monkeypatch.setattr(worker_main, "get_sessionmaker", lambda: SessionLocal)

    def fake_execute_match(db, **kwargs):
        match = Match(
            game_id=kwargs["game_id"],
            bot_one_id=kwargs["bot_one_id"],
            bot_two_id=kwargs["bot_two_id"],
            bot_one_rating_before=1200,
            bot_two_rating_before=1200,
            bot_one_rating_after=1216,
            bot_two_rating_after=1184,
            bot_one_rating_delta=16,
            bot_two_rating_delta=-16,
            winner_bot_id=kwargs["bot_one_id"],
            result_reason="win",
        )
        db.add(match)
        db.flush()
        return match

    monkeypatch.setattr(worker_main, "execute_match", fake_execute_match)

    assert worker_main.run_once() is True

    db = SessionLocal()
    completed = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    assert completed.status == "completed"
    assert completed.match_id == db.query(Match.id).scalar()
    assert completed.error_message is None
    assert completed.attempts == 1


def test_run_once_marks_job_failed_when_match_execution_raises(monkeypatch):
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    bot_one = seed_bot(db, name="alpha")
    bot_two = seed_bot(db, name="beta")
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="queued",
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    monkeypatch.setattr(worker_main, "get_sessionmaker", lambda: SessionLocal)

    def fake_execute_match(_db, **_kwargs):
        raise RuntimeError("match exploded")

    monkeypatch.setattr(worker_main, "execute_match", fake_execute_match)

    assert worker_main.run_once() is True

    db = SessionLocal()
    failed = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    assert failed.status == "failed"
    assert failed.match_id is None
    assert failed.error_message == "match exploded"
    assert failed.attempts == 1
    assert db.query(Match).count() == 0


def test_get_poll_interval_seconds_defaults_to_five(monkeypatch):
    monkeypatch.delenv("WORKER_POLL_INTERVAL_SECONDS", raising=False)

    assert worker_main.get_poll_interval_seconds() == 5.0


def test_get_poll_interval_seconds_uses_environment(monkeypatch):
    monkeypatch.setenv("WORKER_POLL_INTERVAL_SECONDS", "0.25")

    assert worker_main.get_poll_interval_seconds() == 0.25


def test_get_match_job_stall_timeout_seconds_defaults_to_thirty(monkeypatch):
    monkeypatch.delenv("MATCH_JOB_STALL_TIMEOUT_SECONDS", raising=False)

    assert worker_main.get_match_job_stall_timeout_seconds() == 30.0


def test_get_match_job_stall_timeout_seconds_uses_environment(monkeypatch):
    monkeypatch.setenv("MATCH_JOB_STALL_TIMEOUT_SECONDS", "12.5")

    assert worker_main.get_match_job_stall_timeout_seconds() == 12.5


def test_get_match_job_max_attempts_defaults_to_three(monkeypatch):
    monkeypatch.delenv("MATCH_JOB_MAX_ATTEMPTS", raising=False)

    assert worker_main.get_match_job_max_attempts() == 3


def test_get_match_job_max_attempts_uses_environment(monkeypatch):
    monkeypatch.setenv("MATCH_JOB_MAX_ATTEMPTS", "5")

    assert worker_main.get_match_job_max_attempts() == 5


def test_reap_stalled_jobs_requeues_running_job_past_timeout():
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    bot_one = seed_bot(db, name="alpha")
    bot_two = seed_bot(db, name="beta")
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="running",
        attempts=1,
        started_at=now - timedelta(seconds=31),
        error_message="old error",
    )
    db.add(job)
    db.commit()
    job_id = job.id

    assert worker_main.reap_stalled_jobs(
        db,
        stall_timeout_seconds=30,
        max_attempts=3,
        now=now,
    ) == (1, 0)

    requeued = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    assert requeued.status == "queued"
    assert requeued.attempts == 1
    assert requeued.started_at is None
    assert requeued.completed_at is None
    assert requeued.error_message is None


def test_reap_stalled_jobs_marks_job_failed_at_max_attempts():
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    bot_one = seed_bot(db, name="alpha")
    bot_two = seed_bot(db, name="beta")
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="running",
        attempts=3,
        started_at=now - timedelta(seconds=31),
    )
    db.add(job)
    db.commit()
    job_id = job.id

    assert worker_main.reap_stalled_jobs(
        db,
        stall_timeout_seconds=30,
        max_attempts=3,
        now=now,
    ) == (0, 1)

    failed = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    assert failed.status == "failed"
    assert failed.attempts == 3
    assert failed.started_at is None
    assert failed.completed_at == now.replace(tzinfo=None)
    assert failed.error_message == "Match job stalled after maximum attempts."


def test_reap_stalled_jobs_ignores_recent_running_job():
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    bot_one = seed_bot(db, name="alpha")
    bot_two = seed_bot(db, name="beta")
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="running",
        attempts=1,
        started_at=now - timedelta(seconds=29),
    )
    db.add(job)
    db.commit()
    job_id = job.id

    assert worker_main.reap_stalled_jobs(
        db,
        stall_timeout_seconds=30,
        max_attempts=3,
        now=now,
    ) == (0, 0)

    running = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    assert running.status == "running"
    assert running.started_at is not None


def test_create_job_notifier_uses_postgres_listener_for_postgres(monkeypatch):
    created = []

    class FakeDialect:
        name = "postgresql"

    class FakeEngine:
        dialect = FakeDialect()

    class FakePostgresJobNotifier:
        def __init__(self, database_url):
            created.append(database_url)

    monkeypatch.setattr(worker_main, "get_engine", lambda: FakeEngine())
    monkeypatch.setattr(worker_main, "get_database_url", lambda: "postgresql://db")
    monkeypatch.setattr(
        worker_main,
        "PostgresJobNotifier",
        FakePostgresJobNotifier,
    )

    notifier = worker_main.create_job_notifier()

    assert isinstance(notifier, FakePostgresJobNotifier)
    assert created == ["postgresql://db"]


def test_create_job_notifier_falls_back_to_polling_for_non_postgres(monkeypatch):
    class FakeDialect:
        name = "sqlite"

    class FakeEngine:
        dialect = FakeDialect()

    monkeypatch.setattr(worker_main, "get_engine", lambda: FakeEngine())

    notifier = worker_main.create_job_notifier()

    assert isinstance(notifier, worker_main.PollingJobNotifier)


def test_postgres_job_notifier_listens_and_waits_for_notifications(monkeypatch):
    calls = []

    class FakeConnection:
        def execute(self, sql):
            calls.append(("execute", sql))

        def notifies(self, *, timeout, stop_after):
            calls.append(("notifies", timeout, stop_after))
            yield object()

        def close(self):
            calls.append(("close",))

    class FakePsycopg:
        @staticmethod
        def connect(database_url, autocommit):
            calls.append(("connect", database_url, autocommit))
            return FakeConnection()

    monkeypatch.setattr(worker_main, "psycopg", FakePsycopg)

    notifier = worker_main.PostgresJobNotifier("postgresql://db")
    notifier.wait(3.5)
    notifier.close()

    assert calls == [
        ("connect", "postgresql://db", True),
        ("execute", "LISTEN match_jobs_channel"),
        ("notifies", 3.5, 1),
        ("close",),
    ]


def test_run_loop_waits_on_notifier_after_empty_claim(monkeypatch):
    wait_calls = []

    class StopLoop(Exception):
        pass

    class FakeNotifier:
        def wait(self, timeout_seconds):
            wait_calls.append(timeout_seconds)
            raise StopLoop

        def close(self):
            wait_calls.append("closed")

    monkeypatch.setattr(worker_main, "run_once", lambda: False)
    monkeypatch.setattr(worker_main, "run_reaper_once", lambda: (0, 0))

    with pytest.raises(StopLoop):
        worker_main.run_loop(poll_interval_seconds=7.0, notifier=FakeNotifier())

    assert wait_calls == [7.0, "closed"]


def test_run_loop_retries_immediately_after_processed_job(monkeypatch):
    run_results = iter([True, False])
    run_calls = []
    wait_calls = []

    class StopLoop(Exception):
        pass

    class FakeNotifier:
        def wait(self, timeout_seconds):
            wait_calls.append(timeout_seconds)
            raise StopLoop

        def close(self):
            wait_calls.append("closed")

    def fake_run_once():
        run_calls.append("run")
        return next(run_results)

    monkeypatch.setattr(worker_main, "run_once", fake_run_once)
    monkeypatch.setattr(worker_main, "run_reaper_once", lambda: (0, 0))

    with pytest.raises(StopLoop):
        worker_main.run_loop(poll_interval_seconds=5.0, notifier=FakeNotifier())

    assert run_calls == ["run", "run"]
    assert wait_calls == [5.0, "closed"]


def test_run_loop_runs_reaper_periodically(monkeypatch):
    monotonic_values = iter([0.0, 2.0, 5.0])
    reaper_calls = []
    run_calls = []

    class StopLoop(Exception):
        pass

    class FakeNotifier:
        def wait(self, _timeout_seconds):
            raise StopLoop

        def close(self):
            pass

    def fake_run_reaper_once():
        reaper_calls.append("reap")
        return 0, 0

    def fake_run_once():
        run_calls.append("run")
        if len(run_calls) == 3:
            return False
        return True

    monkeypatch.setattr(worker_main.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(worker_main, "run_reaper_once", fake_run_reaper_once)
    monkeypatch.setattr(worker_main, "run_once", fake_run_once)

    with pytest.raises(StopLoop):
        worker_main.run_loop(poll_interval_seconds=5.0, notifier=FakeNotifier())

    assert reaper_calls == ["reap", "reap"]
    assert run_calls == ["run", "run", "run"]


def test_log_heartbeat_reports_queue_depth(monkeypatch):
    SessionLocal = make_sessionmaker()
    db = SessionLocal()
    db.add_all(
        [
            MatchJob(game_id="tictactoe", bot_one_id=1, bot_two_id=2, status="queued"),
            MatchJob(game_id="tictactoe", bot_one_id=1, bot_two_id=2, status="queued"),
            MatchJob(game_id="tictactoe", bot_one_id=1, bot_two_id=2, status="running"),
        ]
    )
    db.commit()
    db.close()
    events = []
    monkeypatch.setattr(worker_main, "get_sessionmaker", lambda: SessionLocal)
    monkeypatch.setattr(
        worker_main,
        "log_event",
        lambda _logger, event, **fields: events.append((event, fields)),
    )

    worker_main.log_heartbeat()

    assert events == [("worker_heartbeat", {"queue_depth": 2, "running_jobs": 1})]
