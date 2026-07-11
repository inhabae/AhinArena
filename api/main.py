import os
from contextlib import asynccontextmanager

from api.database import get_db, get_sessionmaker
from api.models import Bot, Match, Move
from api.ratings import DEFAULT_ELO_K_FACTOR, calculate_elo_rating_change
from engine.connectfour.runner import run_connectfour_match
from engine.tictactoe.runner import run_tictactoe_match
from engine.registry import UnknownBotError, bot_registry
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import (
    api_error,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)

from api.schemas import (
    MatchCreateResponse,
    MatchRequest,
    MatchSummary,
    MatchDetail,
    MatchListResponse,
    MoveEntry,
    LeaderboardEntry,
    BotSummary,
)


DEFAULT_BOT_NAMES = ("randombot1", "randombot2")
SUPPORTED_GAMES = ("tictactoe", "connect-four")
DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:3000,"
    "http://127.0.0.1:3000"
)


def get_cors_allowed_origins() -> list[str]:
    origins = os.environ.get("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS)
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def seed_default_bots(db: Session) -> None:
    for game_id in SUPPORTED_GAMES:
        existing_names = {
            name
            for (name,) in (
                db.query(Bot.name)
                .filter(Bot.game_id == game_id, Bot.name.in_(DEFAULT_BOT_NAMES))
                .all()
            )
        }

        for bot_name in DEFAULT_BOT_NAMES:
            if bot_name not in existing_names:
                db.add(Bot(name=bot_name, game_id=game_id, created_by="system"))

    db.commit()


def serialize_match_summary(match: Match) -> MatchSummary:
    winner_bot_name = None
    if match.winner_bot_id == match.bot_one_id:
        winner_bot_name = match.bot_one.name
    elif match.winner_bot_id == match.bot_two_id:
        winner_bot_name = match.bot_two.name

    return MatchSummary(
        match_id=match.id,
        game=match.game_id,
        bot_one_id=match.bot_one_id,
        bot_two_id=match.bot_two_id,
        bot_one_name=match.bot_one.name,
        bot_two_name=match.bot_two.name,
        bot_one_rating_before=match.bot_one_rating_before,
        bot_two_rating_before=match.bot_two_rating_before,
        bot_one_rating_after=match.bot_one_rating_after,
        bot_two_rating_after=match.bot_two_rating_after,
        bot_one_rating_delta=match.bot_one_rating_delta,
        bot_two_rating_delta=match.bot_two_rating_delta,
        winner_bot_id=match.winner_bot_id,
        winner_bot_name=winner_bot_name,
        result_reason=match.result_reason,
        created_at=match.created_at,
        completed_at=match.completed_at,
    )

def serialize_match_detail(match: Match) -> MatchDetail:
    summary = serialize_match_summary(match)
    return MatchDetail(
        **summary.model_dump(),
        moves=[
            MoveEntry(
                move_number=move.move_number,
                bot_id=move.bot_id,
                move=move.move,
            )
            for move in match.moves
        ],
    )

def resolve_bot(db: Session, *, game_id: str, bot_name: str) -> Bot:
    bot = (
        db.query(Bot)
        .filter(Bot.game_id == game_id, Bot.name == bot_name)
        .first()
    )

    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_name}")

    return bot


def score_for_bot_one(
    winner_bot_id: int | None,
    bot_one_id: int,
    bot_two_id: int,
) -> float:
    if winner_bot_id == bot_one_id:
        return 1.0

    if winner_bot_id is None:
        return 0.5

    if winner_bot_id != bot_two_id:
        api_error(500, "unknown_winner_bot", f"Unknown winner bot: {winner_bot_id}")

    return 0.0


def apply_match_record_updates(
    *,
    bot_one: Bot,
    bot_two: Bot,
    winner_bot_id: int | None,
    bot_one_rating_after: int,
    bot_two_rating_after: int,
) -> None:
    if bot_one.id == bot_two.id:
        bot_one.rating += (bot_one_rating_after - bot_one.rating) + (
            bot_two_rating_after - bot_two.rating
        )
        bot_one.games_played += 2
        if winner_bot_id is None:
            bot_one.draws += 2
        else:
            bot_one.wins += 1
            bot_one.losses += 1
        return

    bot_one.rating = bot_one_rating_after
    bot_two.rating = bot_two_rating_after
    bot_one.games_played += 1
    bot_two.games_played += 1

    if winner_bot_id is None:
        bot_one.draws += 1
        bot_two.draws += 1
    elif winner_bot_id == bot_one.id:
        bot_one.wins += 1
        bot_two.losses += 1
    elif winner_bot_id == bot_two.id:
        bot_two.wins += 1
        bot_one.losses += 1
    else:
        api_error(500, "unknown_winner_bot", f"Unknown winner bot: {winner_bot_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_sessionmaker()()
    try:
        seed_default_bots(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="AhinArena API",
    description="REST API that exposes the AhinArena game engine for match execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post(
    "/matches",
    status_code=status.HTTP_201_CREATED,
    response_model=MatchCreateResponse,
)
def create_match(
    request: MatchRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    runners = {
        "tictactoe": run_tictactoe_match,
        "connect-four": run_connectfour_match,
    }

    if request.game not in runners:
        api_error(400, "unsupported_game", f"Unsupported game: {request.game}")
    
    if len(request.players) != 2:
        api_error(400, "invalid_player_count", f"{request.game} requires exactly 2 players")

    bot_one = resolve_bot(db, game_id=request.game, bot_name=request.players[0].bot)
    bot_two = resolve_bot(db, game_id=request.game, bot_name=request.players[1].bot)

    try:
        p1_command = bot_registry.get_command(bot_one.name, request.game)
        p2_command = bot_registry.get_command(bot_two.name, request.game)
    except UnknownBotError as error:
        api_error(400, "unknown_bot", str(error))

    try:
        moves = []

        def record_move(player, move, board):
            bot_id = bot_one.id if player == "p1" else bot_two.id
            moves.append((bot_id, move))

        result = runners[request.game](
            p1_command=p1_command,
            p2_command=p2_command,
            on_move=record_move,
        )
    except Exception as error:
        api_error(500, "match_execution_failed", str(error))

    bot_one_rating_before = bot_one.rating
    bot_two_rating_before = bot_two.rating
    winner_bot_id = (
        None if result["winner"] is None
        else bot_one.id if result["winner"] == "p1"
        else bot_two.id
    )
    rating_change = calculate_elo_rating_change(
        bot_one_rating=bot_one_rating_before,
        bot_two_rating=bot_two_rating_before,
        bot_one_score=score_for_bot_one(
            winner_bot_id,
            bot_one.id,
            bot_two.id,
        ),
        k_factor=DEFAULT_ELO_K_FACTOR,
    )
    bot_one_rating_delta = rating_change.bot_one_rating - bot_one_rating_before
    bot_two_rating_delta = rating_change.bot_two_rating - bot_two_rating_before

    match = Match(
        game_id=request.game,
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        bot_one_rating_before=bot_one_rating_before,
        bot_two_rating_before=bot_two_rating_before,
        bot_one_rating_after=rating_change.bot_one_rating,
        bot_two_rating_after=rating_change.bot_two_rating,
        bot_one_rating_delta=bot_one_rating_delta,
        bot_two_rating_delta=bot_two_rating_delta,
        winner_bot_id=winner_bot_id,
        result_reason=result["reason"],
        moves=[
            Move(move_number=index, bot_id=bot_id, move=move)
            for index, (bot_id, move) in enumerate(moves, start=1)
        ],
    )
    apply_match_record_updates(
        bot_one=bot_one,
        bot_two=bot_two,
        winner_bot_id=winner_bot_id,
        bot_one_rating_after=rating_change.bot_one_rating,
        bot_two_rating_after=rating_change.bot_two_rating,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    response.headers["Location"] = f"/matches/{match.id}"

    return MatchCreateResponse(
        match_id=match.id,
        game=match.game_id,
        winner_bot_id=match.winner_bot_id,
        result_reason=match.result_reason,
    )

@app.get("/matches", response_model=MatchListResponse)
def list_matches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    game_id: str = Query(default=""),
    db: Session = Depends(get_db),
):
    query = db.query(Match)

    if game_id:
        query = query.filter(Match.game_id == game_id)

    total = query.count()

    matches = (
        query
        .options(selectinload(Match.bot_one), selectinload(Match.bot_two))
        .order_by(Match.completed_at.desc(), Match.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return MatchListResponse(
        items=[serialize_match_summary(match) for match in matches],
        limit=limit,
        offset=offset,
        total=total,
    )

@app.get("/matches/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = (
        db.query(Match)
        .options(
            selectinload(Match.bot_one),
            selectinload(Match.bot_two),
            selectinload(Match.moves),
        )
        .filter(Match.id == match_id)
        .first()
    )

    if match is None:
        api_error(404, "match_not_found", f"Match not found: {match_id}")

    return serialize_match_detail(match)

@app.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(
    game_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    bots = (
        db.query(Bot)
        .filter(Bot.game_id == game_id)
        .order_by(Bot.rating.desc(), Bot.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "bot_id": bot.id,
            "name": bot.name,
            "rating": bot.rating,
            "games_played": bot.games_played,
            "wins": bot.wins,
            "losses": bot.losses,
            "draws": bot.draws,
        }
        for bot in bots
    ]

@app.get("/bots", response_model=list[BotSummary])
def list_bots(
    game_id: str = Query(default=""),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Bot)

    if game_id:
        query = query.filter(Bot.game_id == game_id)

    bots = query.order_by(Bot.name.asc(), Bot.id.asc()).offset(offset).limit(limit).all()

    return [
        BotSummary(
            bot_id=bot.id,
            name=bot.name,
        )
        for bot in bots
    ]
