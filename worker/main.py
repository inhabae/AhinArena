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
    try:
        while True:
            processed = run_once()
            if not processed:
                job_notifier.wait(poll_interval_seconds)
    finally:
        job_notifier.close()


def main() -> None:
    run_loop(poll_interval_seconds=get_poll_interval_seconds())


if __name__ == "__main__":
    main()
