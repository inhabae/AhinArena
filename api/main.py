from api.schemas import MatchRequest
from api.database import get_db
from api.models import Match, Move
from engine.connectfour.runner import run_connectfour_match
from engine.tictactoe.runner import run_tictactoe_match
from engine.registry import UnknownBotError, bot_registry
from fastapi import Depends, FastAPI, HTTPException, Query
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
        "winner": match.winner,
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

@app.post("/matches")
def create_match(request: MatchRequest, db: Session = Depends(get_db)):
    runners = {
        "tictactoe": run_tictactoe_match,
        "connect-four": run_connectfour_match,
    }

    if request.game not in runners:
        api_error(400, "unsupported_game", f"Unsupported game: {request.game}")
    
    if len(request.players) != 2:
        api_error(400, "invalid_player_count", f"{request.game} requires exactly 2 players")

    try:
        p1_command = bot_registry.get_command(request.players[0].bot, request.game)
        p2_command = bot_registry.get_command(request.players[1].bot, request.game)
    except UnknownBotError as error:
        api_error(400, "unknown_bot", str(error))

    try:
        result = runners[request.game](
            p1_command=p1_command,
            p2_command=p2_command,
        )
    except Exception as error:
        api_error(500, "match_execution_failed", str(error))

    match = Match(
        game_id=request.game,
        bot_one_id=request.players[0].bot,
        bot_two_id=request.players[1].bot,
        winner=result["winner"],
        result_reason=result["reason"],
        moves=[
            Move(move_number=index, player=player, move=move)
            for index, (player, move) in enumerate(result["moves"], start=1)
        ],
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    return {
        "match_id": match.id,
        "game": request.game,
        "players": request.players,
        "result": result,
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