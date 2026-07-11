from datetime import datetime
from pydantic import BaseModel


class UserRegisterRequest(BaseModel):
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    created_at: datetime


class PlayerConfig(BaseModel):
    bot: str

class MatchRequest(BaseModel):
    game: str
    players: list[PlayerConfig]

class MatchCreateResponse(BaseModel):
    match_id: int
    game: str
    winner_bot_id: int | None
    result_reason: str

class MatchSummary(BaseModel):
    match_id: int
    game: str
    bot_one_id: int
    bot_two_id: int
    bot_one_name: str
    bot_two_name: str
    bot_one_rating_before: int
    bot_two_rating_before: int
    bot_one_rating_after: int
    bot_two_rating_after: int
    bot_one_rating_delta: int
    bot_two_rating_delta: int
    winner_bot_id: int | None
    winner_bot_name: str | None
    result_reason: str
    created_at: datetime
    completed_at: datetime

class MoveEntry(BaseModel):
    move_number: int
    bot_id: int
    move: object

class MatchDetail(MatchSummary):
    moves: list[MoveEntry]

class MatchListResponse(BaseModel):
    items: list[MatchSummary]
    limit: int
    offset: int
    total: int

class LeaderboardEntry(BaseModel):
    bot_id: int
    name: str
    owner_name: str
    rating: int
    games_played: int
    wins: int
    losses: int
    draws: int

class BotSummary(BaseModel):
    bot_id: int
    name: str
    owner_name: str | None

class BotCreateRequest(BaseModel):
    game_id: str
    name: str

class BotCreateResponse(BaseModel):
    bot_id: int
    game_id: str
    name: str
    owner_id: int
