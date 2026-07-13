import os
import time
from datetime import datetime, timezone

from api.database import get_sessionmaker
from api.match_execution import (
    execute_match,
    get_bot_move_timeout_seconds,
    get_bot_startup_timeout_seconds,
)
from api.models import MatchJob
from sqlalchemy import text
from sqlalchemy.orm import Session


DEFAULT_POLL_INTERVAL_SECONDS = 1.0


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


def run_loop(poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
    while True:
        processed = run_once()
        if not processed:
            time.sleep(poll_interval_seconds)


def main() -> None:
    poll_interval = float(
        os.environ.get("WORKER_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS)
    )
    run_loop(poll_interval_seconds=poll_interval)


if __name__ == "__main__":
    main()
