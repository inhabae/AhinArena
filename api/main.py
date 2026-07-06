from io import StringIO

from fastapi import FastAPI, HTTPException

from api.schemas import MatchRequest
from engine.tictactoe.runner import run_tictactoe_match
from engine.registry import UnknownBotError, bot_registry


app = FastAPI(
    title="AhinArena API",
    description="REST API that exposes the AhinArena game engine for match execution.",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/matches")
def create_match(request: MatchRequest):
    if request.game != "tictactoe":
        raise HTTPException(status_code=400, detail="Unsupported game")
    
    if len(request.players) != 2:
        raise HTTPException(
            status_code=400,
            detail="Tic-Tac-Toe requires exactly 2 players",
        )
    
    for player in request.players:
        if player.bot != "random":
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported bot: {player.bot}",
            )

    try:
        p1_command = bot_registry.get_command(request.players[0].bot)
        p2_command = bot_registry.get_command(request.players[1].bot)
    except UnknownBotError as error:
        raise HTTPException(status_code=400, detail=str(error))

    result = run_tictactoe_match(
        p1_command=p1_command,
        p2_command=p2_command,
    )

    return {
        "game": request.game,
        "players": request.players,
        "result": result,
    }