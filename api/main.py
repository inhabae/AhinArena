from io import StringIO

from fastapi import FastAPI, HTTPException

from api.schemas import MatchRequest
from engine.tictactoe.runner import run_tictactoe_match



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

    result = run_tictactoe_match()

    return {
        "game": request.game,
        "players": request.players,
        "result": result,
    }