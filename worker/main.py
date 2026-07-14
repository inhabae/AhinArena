import os
import time
from datetime import datetime, timezone

import psycopg
from api.config import get_database_url
from api.database import get_engine, get_sessionmaker
from api.match_execution import (
    execute_match,
    get_bot_move_timeout_seconds,
    get_bot_startup_timeout_seconds,
)
from api.models import MatchJob
from sqlalchemy import text
from sqlalchemy.orm import Session


MATCH_JOBS_CHANNEL = "match_jobs_channel"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_MATCH_JOB_STALL_TIMEOUT_SECONDS = 30.0
DEFAULT_MATCH_JOB_MAX_ATTEMPTS = 3


class PollingJobNotifier:
    def wait(self, timeout_seconds: float) -> None:
        time.sleep(timeout_seconds)

    def close(self) -> None:
        pass


class PostgresJobNotifier:
    def __init__(self, database_url: str, channel: str = MATCH_JOBS_CHANNEL):
        self.connection = psycopg.connect(database_url, autocommit=True)
        self.connection.execute(f"LISTEN {channel}")

    def wait(self, timeout_seconds: float) -> None:
        next(
            self.connection.notifies(timeout=timeout_seconds, stop_after=1),
            None,
        )

    def close(self) -> None:
        self.connection.close()


def get_poll_interval_seconds() -> float:
    return float(
        os.environ.get("WORKER_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS)
    )


def get_match_job_stall_timeout_seconds() -> float:
    return float(
        os.environ.get(
            "MATCH_JOB_STALL_TIMEOUT_SECONDS",
            DEFAULT_MATCH_JOB_STALL_TIMEOUT_SECONDS,
        )
    )


def get_match_job_max_attempts() -> int:
    return int(os.environ.get("MATCH_JOB_MAX_ATTEMPTS", DEFAULT_MATCH_JOB_MAX_ATTEMPTS))


def create_job_notifier():
    if get_engine().dialect.name != "postgresql":
        return PollingJobNotifier()

    try:
        return PostgresJobNotifier(get_database_url())
    except Exception:
        return PollingJobNotifier()


def claim_next_job(db: Session) -> MatchJob | None:
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        row = db.execute(
            text(
                """
                SELECT id
                FROM match_jobs
                WHERE status = 'queued'
                ORDER BY created_at, id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
        ).first()
    else:
        row = (
            db.query(MatchJob.id)
            .filter(MatchJob.status == "queued")
            .order_by(MatchJob.created_at, MatchJob.id)
            .first()
        )

    if row is None:
        db.rollback()
        return None

    job_id = row[0]
    job = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def reap_stalled_jobs(
    db: Session,
    *,
    stall_timeout_seconds: float,
    max_attempts: int,
    now: datetime | None = None,
) -> tuple[int, int]:
    now = now or datetime.now(timezone.utc)
    cutoff = datetime.fromtimestamp(
        now.timestamp() - stall_timeout_seconds,
        tz=timezone.utc,
    )
    bind = db.get_bind()

    if bind is not None and bind.dialect.name == "postgresql":
        rows = db.execute(
            text(
                """
                SELECT id
                FROM match_jobs
                WHERE status = 'running'
                  AND started_at IS NOT NULL
                  AND started_at < :cutoff
                ORDER BY started_at, id
                FOR UPDATE SKIP LOCKED
                """
            ),
            {"cutoff": cutoff},
        ).all()
        stalled_job_ids = [row[0] for row in rows]
    else:
        stalled_job_ids = [
            row[0]
            for row in (
                db.query(MatchJob.id)
                .filter(
                    MatchJob.status == "running",
                    MatchJob.started_at.is_not(None),
                    MatchJob.started_at < cutoff,
                )
                .order_by(MatchJob.started_at, MatchJob.id)
                .all()
            )
        ]

    if not stalled_job_ids:
        db.rollback()
        return 0, 0

    requeued_count = 0
    failed_count = 0
    for job in db.query(MatchJob).filter(MatchJob.id.in_(stalled_job_ids)).all():
        if job.attempts >= max_attempts:
            job.status = "failed"
            job.completed_at = now
            job.error_message = "Match job stalled after maximum attempts."
            failed_count += 1
        else:
            job.status = "queued"
            job.error_message = None
            requeued_count += 1

        job.started_at = None

    db.commit()
    return requeued_count, failed_count


def run_reaper_once() -> tuple[int, int]:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        return reap_stalled_jobs(
            db,
            stall_timeout_seconds=get_match_job_stall_timeout_seconds(),
            max_attempts=get_match_job_max_attempts(),
        )
    finally:
        db.close()


def run_job(db: Session, job: MatchJob) -> int:
    match = execute_match(
        db,
        game_id=job.game_id,
        bot_one_id=job.bot_one_id,
        bot_two_id=job.bot_two_id,
        move_timeout_seconds=get_bot_move_timeout_seconds(),
        startup_timeout_seconds=get_bot_startup_timeout_seconds(),
    )
    job.status = "completed"
    job.match_id = match.id
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = None
    db.commit()
    return match.id


def mark_job_failed(db: Session, job_id: int, exc: Exception) -> None:
    db.rollback()
    job = db.query(MatchJob).filter(MatchJob.id == job_id).one()
    job.status = "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = str(exc)
    db.commit()


def run_once() -> bool:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        job = claim_next_job(db)
        if job is None:
            return False

        job_id = job.id
        try:
            run_job(db, job)
        except Exception as exc:
            mark_job_failed(db, job_id, exc)
        return True
    finally:
        db.close()


def run_loop(
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    notifier=None,
) -> None:
    job_notifier = notifier or create_job_notifier()
    next_reaper_at = 0.0
    try:
        while True:
            now = time.monotonic()
            if now >= next_reaper_at:
                run_reaper_once()
                next_reaper_at = now + poll_interval_seconds

            processed = run_once()
            if not processed:
                job_notifier.wait(poll_interval_seconds)
    finally:
        job_notifier.close()


def main() -> None:
    run_loop(poll_interval_seconds=get_poll_interval_seconds())


if __name__ == "__main__":
    main()
