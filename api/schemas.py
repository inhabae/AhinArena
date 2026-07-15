import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
BOT_NAME_MIN_LENGTH = 3
BOT_NAME_MAX_LENGTH = 32

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
BOT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]*")


class UserRegisterRequest(BaseModel):
    email: str = Field(max_length=EMAIL_MAX_LENGTH)
    username: str = Field(min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        email = value.strip().lower()
        if not email.isascii():
            raise ValueError("Email must use ASCII characters.")

        if not EMAIL_PATTERN.fullmatch(email):
            raise ValueError("Email format is invalid.")

        local_part, domain = email.rsplit("@", maxsplit=1)
        if local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
            raise ValueError("Email format is invalid.")

        domain_parts = domain.split(".")
        if any(part.startswith("-") or part.endswith("-") for part in domain_parts):
            raise ValueError("Email format is invalid.")

        return email

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        username = value.strip()
        if not username:
            raise ValueError("Username is required.")

        if not username.isascii() or not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("Username can only contain letters, numbers, periods, underscores, and hyphens.")

        return username


class UserLoginRequest(BaseModel):
    login: str | None = None
    email: str | None = None
    password: str = Field(max_length=72)

    @model_validator(mode="after")
    def validate_login_identifier(self):
        if self.login is None and self.email is None:
            raise ValueError("Email or username is required.")

        if self.login is not None:
            self.login = self.login.strip()

        if self.email is not None:
            self.email = self.email.strip()

        if not self.login and not self.email:
            raise ValueError("Email or username is required.")

        return self


class UserPublic(BaseModel):
    id: int
    email: str
    username: str
    description: str = ""
    created_at: datetime

class UserProfile(BaseModel):
    id: int
    username: str
    description: str = ""
    created_at: datetime

class DescriptionUpdateRequest(BaseModel):
    description: str = Field(max_length=280)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value):
        return value.strip()


class PlayerConfig(BaseModel):
    bot: str

class MatchRequest(BaseModel):
    game: str
    players: list[PlayerConfig]

class MatchJobCreateResponse(BaseModel):
    job_id: int
    status: str

class MatchJobDetail(BaseModel):
    job_id: int
    status: str
    match_id: int | None
    error_message: str | None

class MatchJobSummary(MatchJobDetail):
    game: str
    bot_one_name: str
    bot_two_name: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

class MatchJobListResponse(BaseModel):
    items: list[MatchJobSummary]
    limit: int
    offset: int
    total: int

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

class LiveMoveEntry(MoveEntry):
    board_state: list[list[str | None]]

class LiveMatchDetail(BaseModel):
    job_id: int
    status: str
    match_id: int | None
    error_message: str | None
    game: str
    bot_one_id: int
    bot_two_id: int
    bot_one_name: str
    bot_two_name: str
    winner_bot_id: int | None = None
    winner_bot_name: str | None = None
    result_reason: str | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    board_state: list[list[str | None]]
    moves: list[LiveMoveEntry]

class FeaturedGamesResponse(BaseModel):
    items: list[LiveMatchDetail]

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

class BotDetail(BaseModel):
    bot_id: int
    name: str
    description: str = ""
    game_id: str
    owner_name: str
    rating: int
    games_played: int
    wins: int
    losses: int
    draws: int
    created_at: datetime

class BotCreateRequest(BaseModel):
    game_id: str
    name: str = Field(min_length=BOT_NAME_MIN_LENGTH, max_length=BOT_NAME_MAX_LENGTH)
    source_code: str
    language: str = "python"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        name = value.strip()
        if not name:
            raise ValueError("Bot name is required.")

        if not name.isascii() or not BOT_NAME_PATTERN.fullmatch(name):
            raise ValueError("Bot name can only contain letters, numbers, spaces, underscores, and hyphens.")

        return name

class BotCreateResponse(BaseModel):
    bot_id: int
    game_id: str
    name: str
    owner_id: int
    submission_id: int
    version: int

class BotSubmissionRequest(BaseModel):
    source_code: str
    language: str = "python"

class BotSubmissionResponse(BaseModel):
    bot_id: int
    submission_id: int
    version: int
