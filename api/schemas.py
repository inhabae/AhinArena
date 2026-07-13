from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: str = Field(max_length=320)
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Email must contain an @ sign.")

        local_part, domain = email.rsplit("@", maxsplit=1)
        if not local_part or "." not in domain:
            raise ValueError("Email format is invalid.")

        domain_parts = domain.split(".")
        if any(part == "" for part in domain_parts):
            raise ValueError("Email format is invalid.")

        return email

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        if not value.strip():
            raise ValueError("Username is required.")

        return value.strip()


class UserLoginRequest(BaseModel):
    email: str
    password: str = Field(max_length=72)


class UserPublic(BaseModel):
    id: int
    email: str
    username: str
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

class MatchJobCreateResponse(BaseModel):
    job_id: int
    status: str

class MatchJobDetail(BaseModel):
    job_id: int
    status: str
    match_id: int | None
    error_message: str | None

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
    move: int | list[int]

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
    name: str = Field(max_length=64)

class BotCreateResponse(BaseModel):
    bot_id: int
    game_id: str
    name: str
    owner_id: int

class BotSubmissionRequest(BaseModel):
    source_code: str
    language: str = "python"

class BotSubmissionResponse(BaseModel):
    bot_id: int
    submission_id: int
    version: int
