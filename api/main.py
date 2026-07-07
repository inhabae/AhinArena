from api.schemas import MatchRequest
from engine.tictactoe.runner import run_tictactoe_match
from engine.registry import UnknownBotError, bot_registry
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from api.errors import (
    api_error,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)


app = FastAPI(
    title="AhinArena API",
    description="REST API that exposes the AhinArena game engine for match execution",
    version="0.1.0",
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/matches")
def create_match(request: MatchRequest):
    if request.game != "tictactoe":
        api_error(400, "unsupported_game", f"Unsupported game: {request.game}")
    
    if len(request.players) != 2:
        api_error(400, "invalid_player_count", "Tic-Tac-Toe requires exactly 2 players")

    try:
        p1_command = bot_registry.get_command(request.players[0].bot)
        p2_command = bot_registry.get_command(request.players[1].bot)
    except UnknownBotError as error:
        api_error(400, "unknown_bot", str(error))

    try:
        result = run_tictactoe_match(
            p1_command=p1_command,
            p2_command=p2_command,
        )
    except Exception as error:
        api_error(500, "match_execution_failed", str(error))

    return {
        "game": request.game,
        "players": request.players,
        "result": result,
    }