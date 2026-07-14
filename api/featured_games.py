from api.models import Match, MatchJob
from sqlalchemy import case
from sqlalchemy.orm import Session, selectinload


def select_featured_match_jobs(db: Session, *, limit: int = 3) -> list[MatchJob]:
    """Placeholder featured-game heuristic.

    Prefer the newest running jobs, then recently completed jobs.
    Future ranking/live flags should replace only this function.
    """

    status_rank = case(
        (MatchJob.status == "running", 0),
        (MatchJob.status == "completed", 1),
        else_=3,
    )

    return (
        db.query(MatchJob)
        .options(
            selectinload(MatchJob.bot_one),
            selectinload(MatchJob.bot_two),
            selectinload(MatchJob.moves),
            selectinload(MatchJob.match),
            selectinload(MatchJob.match).selectinload(Match.moves),
            selectinload(MatchJob.match).selectinload(Match.bot_one),
            selectinload(MatchJob.match).selectinload(Match.bot_two),
        )
        .filter(MatchJob.status.in_(("running", "completed")))
        .order_by(status_rank, MatchJob.created_at.desc(), MatchJob.id.desc())
        .limit(limit)
        .all()
    )
