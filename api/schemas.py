from pydantic import BaseModel


class PlayerConfig(BaseModel):
    bot: str


class MatchRequest(BaseModel):
    game: str
    players: list[PlayerConfig]


class LeaderboardEntry(BaseModel):
    bot_id: int
    name: str
    rating: int
    games_played: int
    wins: int
    losses: int
    draws: int
