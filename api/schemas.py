from pydantic import BaseModel


class PlayerConfig(BaseModel):
    id: str
    bot: str


class MatchRequest(BaseModel):
    game: str
    players: list[PlayerConfig]