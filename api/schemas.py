from pydantic import BaseModel


class PlayerConfig(BaseModel):
    bot: str


class MatchRequest(BaseModel):
    game: str
    players: list[PlayerConfig]
