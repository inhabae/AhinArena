from api.database import get_db
from api.models import Bot, Match, Move
from api.ratings import DEFAULT_ELO_K_FACTOR, calculate_elo_rating_change
from api.schemas import MatchRequest, LeaderboardEntry
from engine.connectfour.runner import run_connectfour_match
from engine.tictactoe.runner import run_tictactoe_match
from engine.registry import UnknownBotError, bot_registry
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import (
    api_error,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)

def serialize_match_summary(match: Match):
    return {
        "match_id": match.id,
        "game": match.game_id,
        "bot_one_id": match.bot_one_id,
        "bot_two_id": match.bot_two_id,
        "bot_one_rating_before": match.bot_one_rating_before,
        "bot_two_rating_before": match.bot_two_rating_before,
        "bot_one_rating_after": match.bot_one_rating_after,
        "bot_two_rating_after": match.bot_two_rating_after,
        "bot_one_rating_delta": match.bot_one_rating_delta,
        "bot_two_rating_delta": match.bot_two_rating_delta,
        "winner_bot_id": match.winner_bot_id,
        "result_reason": match.result_reason,
        "created_at": match.created_at,
        "completed_at": match.completed_at,
    }

def serialize_match_detail(match: Match):
    return {
        **serialize_match_summary(match),
        "moves": [
            {
                "move_number": move.move_number,
                "player": move.player,
                "move": move.move,
            }
            for move in match.moves
        ],
    }

def resolve_bot(db: Session, *, game_id: str, bot_name: str) -> Bot:
    bot = (
        db.query(Bot)
        .filter(Bot.game_id == game_id, Bot.name == bot_name)
        .first()
    )

    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_name}")

    return bot


PLAYER_ONE_MARKER = "X"
PLAYER_TWO_MARKER = "O"


def score_for_player_one(winner: str | None, player_one_marker: str) -> float:
    if winner == player_one_marker:
        return 1.0

    if winner is None:
        return 0.5

    return 0.0


def winner_bot_id_from_player_map(
    *,
    winner: str | None,
    player_to_bot: dict[str, Bot],
) -> int | None:
    if winner is None:
        return None

    winner_bot = player_to_bot.get(winner)
    if winner_bot is None:
        api_error(500, "unknown_winner_player", f"Unknown winner player: {winner}")

    return winner_bot.id


def winner_bot_from_player_map(
    *,
    winner: str | None,
    player_to_bot: dict[str, Bot],
) -> Bot | None:
    if winner is None:
        return None

    winner_bot = player_to_bot.get(winner)
    if winner_bot is None:
        api_error(500, "unknown_winner_player", f"Unknown winner player: {winner}")

    return winner_bot


def loser_bot_from_player_map(
    *,
    winner: str | None,
    player_to_bot: dict[str, Bot],
) -> Bot | None:
    if winner is None:
        return None

    winner_bot = winner_bot_from_player_map(
        winner=winner,
        player_to_bot=player_to_bot,
    )
    return next(bot for bot in player_to_bot.values() if bot.id != winner_bot.id)


def build_player_to_bot_map(*, bot_one: Bot, bot_two: Bot) -> dict[str, Bot]:
    return {
        PLAYER_ONE_MARKER: bot_one,
        PLAYER_TWO_MARKER: bot_two,
    }


def player_one_marker_from_map(player_to_bot: dict[str, Bot], bot_one: Bot) -> str:
    for player_marker, bot in player_to_bot.items():
        if bot.id == bot_one.id:
            return player_marker

    api_error(500, "bot_not_mapped", f"Bot is not mapped to a player: {bot_one.id}")


def apply_match_record_updates(
    *,
    bot_one: Bot,
    bot_two: Bot,
    winner: str | None,
    player_to_bot: dict[str, Bot],
    bot_one_rating_after: int,
    bot_two_rating_after: int,
) -> None:
    if bot_one.id == bot_two.id:
        bot_one.rating += (bot_one_rating_after - bot_one.rating) + (
            bot_two_rating_after - bot_two.rating
        )
        bot_one.games_played += 2
        if winner is None:
            bot_one.draws += 2
        else:
            winner_bot_from_player_map(winner=winner, player_to_bot=player_to_bot)
            bot_one.wins += 1
            bot_one.losses += 1
        return

    bot_one.rating = bot_one_rating_after
    bot_two.rating = bot_two_rating_after
    bot_one.games_played += 1
    bot_two.games_played += 1

    winner_bot = winner_bot_from_player_map(winner=winner, player_to_bot=player_to_bot)
    loser_bot = loser_bot_from_player_map(winner=winner, player_to_bot=player_to_bot)

    if winner_bot is None:
        bot_one.draws += 1
        bot_two.draws += 1
    else:
        winner_bot.wins += 1
        loser_bot.losses += 1


app = FastAPI(
    title="AhinArena API",
    description="REST API that exposes the AhinArena game engine for match execution",
    version="0.1.0",
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/matches", status_code=status.HTTP_201_CREATED)
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
    player_to_bot = build_player_to_bot_map(bot_one=bot_one, bot_two=bot_two)

    try:
        p1_command = bot_registry.get_command(bot_one.name, request.game)
        p2_command = bot_registry.get_command(bot_two.name, request.game)
    except UnknownBotError as error:
        api_error(400, "unknown_bot", str(error))

    try:
        moves = []

        def record_move(player, move, board):
            moves.append((player, move))

        result = runners[request.game](
            p1_command=p1_command,
            p2_command=p2_command,
            on_move=record_move,
        )
    except Exception as error:
        api_error(500, "match_execution_failed", str(error))

    bot_one_rating_before = bot_one.rating
    bot_two_rating_before = bot_two.rating
    rating_change = calculate_elo_rating_change(
        bot_one_rating=bot_one_rating_before,
        bot_two_rating=bot_two_rating_before,
        bot_one_score=score_for_player_one(
            result["winner"],
            player_one_marker_from_map(player_to_bot, bot_one),
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
        winner_bot_id=winner_bot_id_from_player_map(
            winner=result["winner"],
            player_to_bot=player_to_bot,
        ),
        result_reason=result["reason"],
        moves=[
            Move(move_number=index, player=player, move=move)
            for index, (player, move) in enumerate(moves, start=1)
        ],
    )
    apply_match_record_updates(
        bot_one=bot_one,
        bot_two=bot_two,
        winner=result["winner"],
        player_to_bot=player_to_bot,
        bot_one_rating_after=rating_change.bot_one_rating,
        bot_two_rating_after=rating_change.bot_two_rating,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    response.headers["Location"] = f"/matches/{match.id}"

    return {
        "match_id": match.id,
        "game": match.game_id,
        "winner_bot_id": match.winner_bot_id,
        "result_reason": match.result_reason,
    }

@app.get("/matches")
def list_matches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.query(Match).count()

    matches = (
        db.query(Match)
        .order_by(Match.completed_at.desc(), Match.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [serialize_match_summary(match) for match in matches],
        "limit": limit,
        "offset": offset,
        "total": total,
    }

@app.get("/matches/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = (
        db.query(Match)
        .options(selectinload(Match.moves))
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
