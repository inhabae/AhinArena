import hashlib
import logging
import os
import re
import secrets
import struct
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.auth import hash_password, verify_password
from api.bot_sandbox import build_bot_sandbox
from api.config import validate_production_configuration
from api.database import get_db, get_sessionmaker
from api.email_delivery import (
    EmailDeliveryConfigurationError,
    EmailDeliveryError,
    is_email_delivery_configured,
    send_password_reset_email,
    send_verification_email,
)
from api.featured_games import select_featured_match_jobs
from api.models import (
    AuthRateLimitEvent,
    AuthToken,
    Bot,
    BotSubmission,
    Match,
    MatchJob,
    Move,
    Session as AuthSession,
    User,
)
from api.match_execution import (
    DEFAULT_BOT_MOVE_TIMEOUT_SECONDS,
    DEFAULT_BOT_STARTUP_TIMEOUT_SECONDS,
    apply_match_record_updates,
    get_bot_move_timeout_seconds,
    get_bot_startup_timeout_seconds,
)
from api.match_execution import score_for_bot_one_or_error as _score_for_bot_one_or_error
from engine.connectfour.runner import run_connectfour_match
from engine.tictactoe.runner import run_tictactoe_match
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import (
    api_error,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)

from api.schemas import (
    MatchJobDetail,
    MatchJobCreateResponse,
    FeaturedGamesResponse,
    LiveMatchDetail,
    LiveMoveEntry,
    MatchJobListResponse,
    MatchJobSummary,
    MatchRequest,
    MatchSummary,
    MatchDetail,
    MatchListResponse,
    MoveEntry,
    LeaderboardEntry,
    BotDetail,
    BotSummary,
    BotCreateResponse,
    BotSubmissionResponse,
    BOT_NAME_MAX_LENGTH,
    BOT_NAME_MIN_LENGTH,
    BOT_NAME_PATTERN,
    DescriptionUpdateRequest,
    EmailVerificationResendRequest,
    EmailVerificationResendResponse,
    EmailVerificationRequest,
    UserLoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    PasswordResetValidationRequest,
    UserProfile,
    UserPublic,
    UserRegisterRequest,
    UserRegisterResponse,
)


DEFAULT_BOT_NAMES = ("randombot1", "randombot2")
SUPPORTED_GAMES = ("tictactoe", "connect-four")
DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:3000,"
    "http://127.0.0.1:3000"
)
SESSION_COOKIE_NAME = "ahin_arena_session"
SESSION_ID_BYTES = 48
SESSION_TTL = timedelta(days=14)
EMAIL_VERIFICATION_TTL = timedelta(days=2)
PASSWORD_RESET_TTL = timedelta(hours=1)
AUTH_TOKEN_BYTES = 32
DEFAULT_MAX_BOT_EXECUTABLE_BYTES = 10 * 1024 * 1024
MAX_BOT_EXECUTABLE_BYTES_ENV_VAR = "MAX_BOT_EXECUTABLE_BYTES"
MAX_BOTS_PER_USER_ENV_VAR = "MAX_BOTS_PER_USER"
MAX_ACTIVE_MATCH_JOBS_PER_USER_ENV_VAR = "MAX_ACTIVE_MATCH_JOBS_PER_USER"
DEFAULT_MAX_BOTS_PER_USER = 25
DEFAULT_MAX_ACTIVE_MATCH_JOBS_PER_USER = 10
DEPLOY_ENVIRONMENT_ENV_VAR = "DEPLOY_ENVIRONMENT"
LEGACY_DEPLOY_ENVIRONMENT_ENV_VARS = ("ENVIRONMENT", "APP_ENV", "FASTAPI_ENV")
REQUIRE_SECURE_COOKIES_ENV_VAR = "REQUIRE_SECURE_COOKIES"
AUTH_RATE_LIMITS = {
    "register": {
        "account": (5, timedelta(hours=1)),
        "ip": (10, timedelta(hours=1)),
    },
    "login": {
        "account": (5, timedelta(minutes=15)),
        "ip": (30, timedelta(minutes=15)),
    },
    "password_reset": {
        "account": (5, timedelta(hours=1)),
        "ip": (20, timedelta(hours=1)),
    },
    "verification_resend_daily": {
        "account": (3, timedelta(days=1)),
        "ip": (20, timedelta(days=1)),
    },
}

logger = logging.getLogger(__name__)

DEFAULT_BOT_EXECUTABLE_DIR_ENV_VAR = "DEFAULT_BOT_EXECUTABLE_DIR"
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
# This cannot be a username because usernames may not contain spaces.
BUILT_IN_BOT_OWNER_NAME = "Built-in bot"


def get_bot_owner_name(bot: Bot) -> str:
    if bot.owner is None:
        return BUILT_IN_BOT_OWNER_NAME

    return bot.owner.username


def get_bot_owner_display_name(bot: Bot) -> str | None:
    if bot.owner is None:
        return None

    return bot.owner.username


def serialize_user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        description=user.description,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


def make_auth_token(db: Session, *, user: User, purpose: str, ttl: timedelta) -> AuthToken:
    token = AuthToken(
        user_id=user.id,
        token=secrets.token_urlsafe(AUTH_TOKEN_BYTES),
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + ttl,
    )
    db.add(token)
    db.flush()
    return token


def frontend_url(path: str) -> str:
    base_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base_url}{path}"


def should_send_verification_email(email: str) -> bool:
    return is_email_delivery_configured() and not email.lower().startswith("a")


def email_delivery_error(error: EmailDeliveryError) -> None:
    if isinstance(error, EmailDeliveryConfigurationError):
        api_error(
            500,
            "email_delivery_not_configured",
            "Email delivery is not fully configured.",
        )

    api_error(
        502,
        "email_delivery_failed",
        "Could not send email. Please try again.",
    )


def resolve_active_auth_token(db: Session, *, token: str, purpose: str) -> AuthToken:
    auth_token = (
        db.query(AuthToken)
        .options(selectinload(AuthToken.user))
        .filter(AuthToken.token == token, AuthToken.purpose == purpose)
        .first()
    )

    if auth_token is None or auth_token.used_at is not None or is_expired(auth_token.expires_at):
        api_error(400, "invalid_or_expired_token", "The token is invalid or expired.")

    return auth_token


def serialize_user_profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        username=user.username,
        description=user.description,
        created_at=user.created_at,
    )


def get_cors_allowed_origins() -> list[str]:
    origins = os.environ.get("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS)
    allowed_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]
    if "*" in allowed_origins:
        raise ValueError("CORS_ALLOWED_ORIGINS cannot include * when credentials are enabled.")
    return allowed_origins


def get_deploy_environment() -> str:
    environment = os.environ.get(DEPLOY_ENVIRONMENT_ENV_VAR)
    if environment:
        return environment

    for env_var in LEGACY_DEPLOY_ENVIRONMENT_ENV_VARS:
        environment = os.environ.get(env_var)
        if environment:
            return environment

    return "development"


def get_positive_int_env(env_var: str, default: int) -> int:
    raw_value = os.environ.get(env_var, "").strip()
    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("%s=%r is invalid; using default %s.", env_var, raw_value, default)
        return default

    if value < 1:
        logger.warning("%s=%r must be at least 1; using default %s.", env_var, raw_value, default)
        return default

    return value


def get_max_bots_per_user() -> int:
    return get_positive_int_env(MAX_BOTS_PER_USER_ENV_VAR, DEFAULT_MAX_BOTS_PER_USER)


def get_max_active_match_jobs_per_user() -> int:
    return get_positive_int_env(
        MAX_ACTIVE_MATCH_JOBS_PER_USER_ENV_VAR,
        DEFAULT_MAX_ACTIVE_MATCH_JOBS_PER_USER,
    )


def should_secure_auth_cookie() -> bool:
    environment = get_deploy_environment()
    return environment.lower() in {"production", "prod"}


def require_secure_cookies() -> bool:
    return os.environ.get(REQUIRE_SECURE_COOKIES_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def validate_auth_cookie_security() -> None:
    configured_environment = os.environ.get(DEPLOY_ENVIRONMENT_ENV_VAR)
    legacy_environment = next(
        (
            env_var
            for env_var in LEGACY_DEPLOY_ENVIRONMENT_ENV_VARS
            if os.environ.get(env_var)
        ),
        None,
    )

    if not configured_environment:
        logger.warning(
            "%s is not set; auth session cookies will be issued without Secure unless "
            "a legacy environment variable (%s) is set to production. Set %s=production "
            "for production deploys.",
            DEPLOY_ENVIRONMENT_ENV_VAR,
            ", ".join(LEGACY_DEPLOY_ENVIRONMENT_ENV_VARS),
            DEPLOY_ENVIRONMENT_ENV_VAR,
        )

    if legacy_environment and not configured_environment:
        logger.warning(
            "Using legacy %s to determine auth session cookie security. Prefer %s.",
            legacy_environment,
            DEPLOY_ENVIRONMENT_ENV_VAR,
        )

    if require_secure_cookies() and not should_secure_auth_cookie():
        raise RuntimeError(
            f"{REQUIRE_SECURE_COOKIES_ENV_VAR}=true but auth session cookies would be "
            f"issued without Secure. Set {DEPLOY_ENVIRONMENT_ENV_VAR}=production."
        )


def set_session_cookie(response: Response, session_id: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=max_age,
        httponly=True,
        secure=should_secure_auth_cookie(),
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        secure=should_secure_auth_cookie(),
        samesite="lax",
    )


def is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def unauthorized():
    api_error(401, "unauthorized", "Unauthorized.")


def invalid_credentials():
    api_error(401, "invalid_credentials", "Invalid credentials.")


def client_rate_limit_key(request: Request) -> str:
    if request.client is None or request.client.host is None:
        return "unknown"

    return request.client.host


def require_auth_rate_limit(
    db: Session,
    *,
    action: str,
    account_key: str,
    ip_key: str,
) -> None:
    now = datetime.now(timezone.utc)
    longest_window = max(window for limits in AUTH_RATE_LIMITS.values() for _, window in limits.values())
    db.query(AuthRateLimitEvent).filter(
        AuthRateLimitEvent.created_at < now - longest_window
    ).delete(synchronize_session=False)

    for scope, key in (("account", account_key.strip().lower()), ("ip", ip_key.strip())):
        limit, window = AUTH_RATE_LIMITS[action][scope]
        bucket = f"{action}:{scope}"
        window_start = now - window
        attempts = (
            db.query(func.count(AuthRateLimitEvent.id))
            .filter(
                AuthRateLimitEvent.bucket == bucket,
                AuthRateLimitEvent.key == key,
                AuthRateLimitEvent.created_at >= window_start,
            )
            .scalar()
        )

        if attempts >= limit:
            db.rollback()
            api_error(
                429,
                "rate_limited",
                "Too many requests. Please try again later.",
            )

    for scope, key in (("account", account_key.strip().lower()), ("ip", ip_key.strip())):
        db.add(AuthRateLimitEvent(bucket=f"{action}:{scope}", key=key))

    db.commit()


def get_current_user(
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not session_id:
        unauthorized()

    auth_session = (
        db.query(AuthSession)
        .options(selectinload(AuthSession.user))
        .filter(AuthSession.id == session_id)
        .first()
    )

    if auth_session is None or auth_session.user is None:
        unauthorized()

    if is_expired(auth_session.expires_at):
        db.delete(auth_session)
        db.commit()
        unauthorized()

    return auth_session.user


def seed_default_bots(db: Session) -> None:
    artifact_dir_value = os.environ.get(DEFAULT_BOT_EXECUTABLE_DIR_ENV_VAR, "").strip()
    artifact_dir = Path(artifact_dir_value) if artifact_dir_value else None

    try:
        for game_id in SUPPORTED_GAMES:
            existing_bots = {
                bot.name: bot
                for bot in (
                    db.query(Bot)
                    .filter(Bot.game_id == game_id, Bot.name.in_(DEFAULT_BOT_NAMES))
                    .all()
                )
            }

            for bot_name in DEFAULT_BOT_NAMES:
                bot = existing_bots.get(bot_name)
                if bot is None:
                    bot = Bot(name=bot_name, game_id=game_id, owner_id=None)
                    db.add(bot)
                    db.flush()

                if bot.active_submission_id is None:
                    artifact_path = artifact_dir / game_id if artifact_dir is not None else None
                    if artifact_path is None or not artifact_path.is_file():
                        logger.warning(
                            "Built-in bot executable is unavailable for %s; system bots remain inactive",
                            game_id,
                        )
                        continue
                    artifact = artifact_path.read_bytes()
                    try:
                        validate_bot_executable(artifact)
                    except HTTPException as exc:
                        detail = exc.detail
                        message = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
                        raise RuntimeError(
                            f"Built-in bot executable for {game_id} is invalid: {message}"
                        ) from exc
                    submission = BotSubmission(
                        bot_id=bot.id,
                        version=bot.latest_submission_version + 1,
                        executable=artifact,
                        executable_size=len(artifact),
                        executable_digest=hashlib.sha256(artifact).hexdigest(),
                        original_filename=game_id,
                    )
                    db.add(submission)
                    db.flush()
                    bot.active_submission_id = submission.id
                    bot.latest_submission_version = submission.version

        db.commit()
    except Exception:
        db.rollback()
        raise


def serialize_match_summary(match: Match) -> MatchSummary:
    winner_bot_name = None
    if match.winner_bot_id == match.bot_one_id:
        winner_bot_name = match.bot_one.name
    elif match.winner_bot_id == match.bot_two_id:
        winner_bot_name = match.bot_two.name

    return MatchSummary(
        match_id=match.id,
        game=match.game_id,
        bot_one_id=match.bot_one_id,
        bot_two_id=match.bot_two_id,
        bot_one_name=match.bot_one.name,
        bot_two_name=match.bot_two.name,
        bot_one_rating_before=match.bot_one_rating_before,
        bot_two_rating_before=match.bot_two_rating_before,
        bot_one_rating_after=match.bot_one_rating_after,
        bot_two_rating_after=match.bot_two_rating_after,
        bot_one_rating_delta=match.bot_one_rating_delta,
        bot_two_rating_delta=match.bot_two_rating_delta,
        winner_bot_id=match.winner_bot_id,
        winner_bot_name=winner_bot_name,
        result_reason=match.result_reason,
        created_at=match.created_at,
        completed_at=match.completed_at,
    )

def serialize_match_detail(match: Match) -> MatchDetail:
    summary = serialize_match_summary(match)
    return MatchDetail(
        **summary.model_dump(),
        moves=[
            MoveEntry(
                move_number=move.move_number,
                bot_id=move.bot_id,
                move=move.move,
            )
            for move in match.moves
        ],
    )

def empty_board_state(game_id: str) -> list[list[str | None]]:
    if game_id == "connect-four":
        return [[None for _ in range(7)] for _ in range(6)]

    return [[None for _ in range(3)] for _ in range(3)]

def normalize_board_state(board_state) -> list[list[str | None]]:
    return [
        [None if cell in (None, " ") else cell for cell in row]
        for row in board_state
    ]

def apply_move_to_board(game_id: str, board, move, marker: str):
    next_board = [row.copy() for row in board]

    if game_id == "connect-four":
        column = move if isinstance(move, int) else move[1] if isinstance(move, list) else move["col"]
        for row_index in range(len(next_board) - 1, -1, -1):
            if next_board[row_index][column] is None:
                next_board[row_index][column] = marker
                return next_board
        return next_board

    row = move[0] if isinstance(move, list) else move["row"]
    col = move[1] if isinstance(move, list) else move["col"]
    next_board[row][col] = marker
    return next_board

def live_moves_from_completed_match(match: Match) -> list[LiveMoveEntry]:
    board_state = empty_board_state(match.game_id)
    live_moves: list[LiveMoveEntry] = []

    for index, move in enumerate(match.moves):
        marker = "X" if index % 2 == 0 else "O"
        board_state = apply_move_to_board(match.game_id, board_state, move.move, marker)
        live_moves.append(
            LiveMoveEntry(
                move_number=move.move_number,
                bot_id=move.bot_id,
                move=move.move,
                board_state=board_state,
            )
        )

    return live_moves

def serialize_live_match_job(job: MatchJob) -> LiveMatchDetail:
    match = job.match
    if match is not None:
        moves = live_moves_from_completed_match(match)
        winner_bot_name = None
        if match.winner_bot_id == match.bot_one_id:
            winner_bot_name = match.bot_one.name
        elif match.winner_bot_id == match.bot_two_id:
            winner_bot_name = match.bot_two.name

        return LiveMatchDetail(
            job_id=job.id,
            status=job.status,
            match_id=job.match_id,
            error_message=job.error_message,
            game=match.game_id,
            bot_one_id=match.bot_one_id,
            bot_two_id=match.bot_two_id,
            bot_one_name=match.bot_one.name,
            bot_two_name=match.bot_two.name,
            bot_one_rating_before=match.bot_one_rating_before,
            bot_two_rating_before=match.bot_two_rating_before,
            bot_one_rating_after=match.bot_one_rating_after,
            bot_two_rating_after=match.bot_two_rating_after,
            bot_one_rating_delta=match.bot_one_rating_delta,
            bot_two_rating_delta=match.bot_two_rating_delta,
            winner_bot_id=match.winner_bot_id,
            winner_bot_name=winner_bot_name,
            result_reason=match.result_reason,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            board_state=moves[-1].board_state if moves else empty_board_state(match.game_id),
            moves=moves,
        )

    moves = [
        LiveMoveEntry(
            move_number=move.move_number,
            bot_id=move.bot_id,
            move=move.move,
            board_state=normalize_board_state(move.board_state),
        )
        for move in job.moves
    ]

    return LiveMatchDetail(
        job_id=job.id,
        status=job.status,
        match_id=job.match_id,
        error_message=job.error_message,
        game=job.game_id,
        bot_one_id=job.bot_one_id,
        bot_two_id=job.bot_two_id,
        bot_one_name=job.bot_one.name,
        bot_two_name=job.bot_two.name,
        bot_one_rating_before=job.bot_one.rating,
        bot_two_rating_before=job.bot_two.rating,
        bot_one_rating_after=job.bot_one.rating,
        bot_two_rating_after=job.bot_two.rating,
        bot_one_rating_delta=0,
        bot_two_rating_delta=0,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        board_state=moves[-1].board_state if moves else empty_board_state(job.game_id),
        moves=moves,
    )

def serialize_match_job_summary(job: MatchJob) -> MatchJobSummary:
    return MatchJobSummary(
        job_id=job.id,
        status=job.status,
        match_id=job.match_id,
        error_message=job.error_message,
        game=job.game_id,
        bot_one_name=job.bot_one.name,
        bot_two_name=job.bot_two.name,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )

def resolve_bot(db: Session, *, game_id: str, bot_name: str) -> Bot:
    bot = (
        db.query(Bot)
        .filter(Bot.game_id == game_id, Bot.name == bot_name)
        .first()
    )

    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_name}")

    return bot


def score_for_bot_one_or_error(
    winner_bot_id: int | None,
    bot_one_id: int,
    bot_two_id: int,
) -> float:
    try:
        return _score_for_bot_one_or_error(
            winner_bot_id=winner_bot_id,
            bot_one_id=bot_one_id,
            bot_two_id=bot_two_id,
        )
    except ValueError:
        api_error(500, "unknown_winner_bot", f"Unknown winner bot: {winner_bot_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_configuration()
    validate_auth_cookie_security()
    db = get_sessionmaker()()
    try:
        seed_default_bots(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="AhinArena API",
    description="REST API that exposes the AhinArena game engine for match execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRegisterResponse,
)
def register_user(
    register_request: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    normalized_email = register_request.email.strip().lower()
    username = register_request.username.strip()

    if not username:
        api_error(422, "validation_error", "Username is required.")

    require_auth_rate_limit(
        db,
        action="register",
        account_key=normalized_email,
        ip_key=client_rate_limit_key(request),
    )

    existing_user = (
        db.query(User)
        .filter((User.email == normalized_email) | (User.username == username))
        .first()
    )

    if existing_user is not None and existing_user.email == normalized_email:
        api_error(
            409,
            "email_already_registered",
            "Email is already registered.",
        )

    if existing_user is not None:
        api_error(
            409,
            "username_already_taken",
            "Username is already taken.",
        )

    user = User(
        email=normalized_email,
        username=username,
        password_hash=hash_password(register_request.password),
    )
    db.add(user)

    try:
        db.flush()
        verification_token = make_auth_token(
            db,
            user=user,
            purpose="email_verification",
            ttl=EMAIL_VERIFICATION_TTL,
        )
    except IntegrityError:
        db.rollback()
        api_error(409, "registration_conflict", "Email or username is already registered.")

    verification_url = frontend_url(f"/verify-email?token={verification_token.token}")

    if should_send_verification_email(user.email):
        try:
            send_verification_email(
                to=user.email,
                username=user.username,
                verification_url=verification_url,
            )
        except EmailDeliveryError as error:
            db.rollback()
            email_delivery_error(error)

        db.commit()
        db.refresh(user)
        return UserRegisterResponse(user=serialize_user_public(user))

    db.commit()
    db.refresh(user)

    return UserRegisterResponse(user=serialize_user_public(user))


@app.post("/auth/verify-email", response_model=UserPublic)
def verify_email(request: EmailVerificationRequest, db: Session = Depends(get_db)):
    auth_token = resolve_active_auth_token(
        db,
        token=request.token,
        purpose="email_verification",
    )
    auth_token.user.is_email_verified = True
    auth_token.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(auth_token.user)

    return serialize_user_public(auth_token.user)


@app.post("/auth/verify-email/resend", response_model=EmailVerificationResendResponse)
def resend_verification_email(
    resend_request: EmailVerificationResendRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_auth_rate_limit(
        db,
        action="verification_resend_daily",
        account_key=resend_request.email,
        ip_key=client_rate_limit_key(request),
    )

    user = db.query(User).filter(User.email == resend_request.email).first()
    if user is None or user.is_email_verified:
        return EmailVerificationResendResponse()

    now = datetime.now(timezone.utc)
    (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user.id,
            AuthToken.purpose == "email_verification",
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > now,
        )
        .update({AuthToken.used_at: now}, synchronize_session=False)
    )
    verification_token = make_auth_token(
        db,
        user=user,
        purpose="email_verification",
        ttl=EMAIL_VERIFICATION_TTL,
    )
    verification_url = frontend_url(f"/verify-email?token={verification_token.token}")

    if should_send_verification_email(user.email):
        try:
            send_verification_email(
                to=user.email,
                username=user.username,
                verification_url=verification_url,
            )
        except EmailDeliveryError as error:
            db.rollback()
            email_delivery_error(error)

        db.commit()
        return EmailVerificationResendResponse()

    db.commit()
    return EmailVerificationResendResponse()


@app.post("/auth/password-reset", response_model=PasswordResetResponse)
def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_auth_rate_limit(
        db,
        action="password_reset",
        account_key=reset_request.email,
        ip_key=client_rate_limit_key(request),
    )

    user = db.query(User).filter(User.email == reset_request.email).first()
    if user is None:
        return PasswordResetResponse()

    reset_token = make_auth_token(
        db,
        user=user,
        purpose="password_reset",
        ttl=PASSWORD_RESET_TTL,
    )
    reset_url = frontend_url(f"/reset-password?token={reset_token.token}")

    if is_email_delivery_configured():
        try:
            send_password_reset_email(
                to=user.email,
                username=user.username,
                reset_url=reset_url,
            )
        except EmailDeliveryError as error:
            db.rollback()
            email_delivery_error(error)

        db.commit()
        return PasswordResetResponse()

    db.commit()

    return PasswordResetResponse(
        reset_token=reset_token.token,
        reset_url=reset_url,
    )


@app.post("/auth/password-reset/validate", status_code=status.HTTP_204_NO_CONTENT)
def validate_password_reset_token(
    request: PasswordResetValidationRequest,
    db: Session = Depends(get_db),
):
    resolve_active_auth_token(
        db,
        token=request.token,
        purpose="password_reset",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/auth/password-reset/confirm", response_model=UserPublic)
def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
):
    auth_token = resolve_active_auth_token(
        db,
        token=request.token,
        purpose="password_reset",
    )
    auth_token.user.password_hash = hash_password(request.password)
    auth_token.user.is_email_verified = True
    auth_token.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(auth_token.user)

    return serialize_user_public(auth_token.user)


@app.post(
    "/auth/login",
    response_model=UserPublic,
)
def login_user(
    login_request: UserLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    login_identifier = login_request.login if login_request.login is not None else login_request.email
    login_identifier = login_identifier.strip()
    normalized_email = login_identifier.lower()
    require_auth_rate_limit(
        db,
        action="login",
        account_key=normalized_email,
        ip_key=client_rate_limit_key(request),
    )

    user = (
        db.query(User)
        .filter(or_(User.email == normalized_email, User.username == login_identifier))
        .first()
    )

    if user is None or not verify_password(login_request.password, user.password_hash):
        invalid_credentials()

    if not user.is_email_verified:
        api_error(403, "email_not_verified", "Please verify your email before logging in.")

    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    auth_session = AuthSession(
        id=secrets.token_urlsafe(SESSION_ID_BYTES),
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.commit()

    set_session_cookie(response, auth_session.id, expires_at)

    return serialize_user_public(user)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if session_id:
        auth_session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
        if auth_session is not None:
            db.delete(auth_session)
            db.commit()

    clear_session_cookie(response)


@app.get("/auth/me", response_model=UserPublic)
def get_authenticated_user(current_user: User = Depends(get_current_user)):
    return serialize_user_public(current_user)


@app.get("/users/{username}", response_model=UserProfile)
def get_user_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()

    if user is None:
        api_error(404, "user_not_found", f"User not found: {username}")

    return serialize_user_profile(user)


@app.patch("/auth/me", response_model=UserPublic)
def update_authenticated_user(
    request: DescriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if user is None:
        unauthorized()

    user.description = request.description
    db.commit()
    db.refresh(user)

    return serialize_user_public(user)


def bot_name_taken():
    api_error(409, "bot_name_taken", "Bot name is already taken for this game.")


def enforce_user_bot_limit(db: Session, *, user_id: int) -> None:
    max_bots = get_max_bots_per_user()
    bot_count = db.query(func.count(Bot.id)).filter(Bot.owner_id == user_id).scalar()
    if bot_count >= max_bots:
        api_error(
            429,
            "bot_limit_exceeded",
            f"User bot limit exceeded. Maximum allowed bots: {max_bots}.",
        )


def enforce_user_active_match_job_limit(db: Session, *, user_id: int) -> None:
    max_jobs = get_max_active_match_jobs_per_user()
    active_job_count = (
        db.query(func.count(MatchJob.id))
        .filter(
            MatchJob.requester_user_id == user_id,
            MatchJob.status.in_(("queued", "running")),
        )
        .scalar()
    )
    if active_job_count >= max_jobs:
        api_error(
            429,
            "match_job_limit_exceeded",
            f"Limit reached ({max_jobs} active matches). Finish one to continue.",
        )


def get_max_bot_executable_bytes() -> int:
    return get_positive_int_env(
        MAX_BOT_EXECUTABLE_BYTES_ENV_VAR,
        DEFAULT_MAX_BOT_EXECUTABLE_BYTES,
    )


def sanitize_executable_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    safe = SAFE_FILENAME_PATTERN.sub("_", Path(filename).name).strip("._")
    return safe[:255] or None


def validate_bot_executable(executable: bytes) -> None:
    """Validate a static, little-endian, x86-64 ELF without executing it."""
    if len(executable) < 64 or executable[:4] != b"\x7fELF":
        api_error(422, "invalid_executable", "Upload must be a valid ELF executable.")
    if executable[4] != 2 or executable[5] != 1:
        api_error(422, "unsupported_architecture", "Executable must be 64-bit little-endian x86-64 ELF.")

    try:
        elf_type, machine = struct.unpack_from("<HH", executable, 16)
        program_offset = struct.unpack_from("<Q", executable, 32)[0]
        program_entry_size, program_count = struct.unpack_from("<HH", executable, 54)
    except struct.error:
        api_error(422, "invalid_executable", "ELF header is truncated.")

    if machine != 62:
        api_error(422, "unsupported_architecture", "Executable must target Linux x86-64.")
    if elf_type not in (2, 3) or program_entry_size < 56:
        api_error(422, "invalid_executable", "ELF file is not an executable.")
    if program_count == 0 or program_offset > len(executable):
        api_error(422, "invalid_executable", "ELF program headers are missing.")

    dynamically_linked = False
    for index in range(program_count):
        offset = program_offset + index * program_entry_size
        if offset + 56 > len(executable):
            api_error(422, "invalid_executable", "ELF program headers are truncated.")
        segment_type = struct.unpack_from("<I", executable, offset)[0]
        if segment_type == 3:  # PT_INTERP
            dynamically_linked = True
        if segment_type == 2:  # PT_DYNAMIC
            dynamic_offset = struct.unpack_from("<Q", executable, offset + 8)[0]
            dynamic_size = struct.unpack_from("<Q", executable, offset + 32)[0]
            if dynamic_offset + dynamic_size > len(executable):
                api_error(422, "invalid_executable", "ELF dynamic segment is truncated.")
            for item_offset in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
                if item_offset + 16 > len(executable):
                    api_error(422, "invalid_executable", "ELF dynamic table is truncated.")
                tag = struct.unpack_from("<Q", executable, item_offset)[0]
                if tag == 0:
                    break
                if tag == 1:  # DT_NEEDED
                    dynamically_linked = True
    if dynamically_linked:
        api_error(422, "dynamic_executable", "Executable must be statically linked.")


def read_bot_executable(upload: UploadFile) -> tuple[bytes, str, str | None]:
    limit = get_max_bot_executable_bytes()
    chunks: list[bytes] = []
    size = 0
    digest = hashlib.sha256()
    while True:
        chunk = upload.file.read(min(1024 * 1024, limit + 1 - size))
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            api_error(413, "submission_too_large", f"Executable exceeds the {limit}-byte limit.")
        digest.update(chunk)
        chunks.append(chunk)
    executable = b"".join(chunks)
    if not executable:
        api_error(422, "invalid_executable", "Executable file is required.")
    validate_bot_executable(executable)
    return executable, digest.hexdigest(), sanitize_executable_filename(upload.filename)


@app.post(
    "/bots",
    status_code=status.HTTP_201_CREATED,
    response_model=BotCreateResponse,
)
def create_bot(
    game_id: str = Form(...),
    name: str = Form(...),
    executable: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if game_id not in SUPPORTED_GAMES:
        api_error(400, "unsupported_game", f"Unsupported game: {game_id}")

    bot_name = name.strip()
    if not (BOT_NAME_MIN_LENGTH <= len(bot_name) <= BOT_NAME_MAX_LENGTH):
        api_error(422, "validation_error", "Bot name must be 3-32 characters.")
    if not bot_name.isascii() or not BOT_NAME_PATTERN.fullmatch(bot_name):
        api_error(422, "validation_error", "Bot name contains unsupported characters.")
    enforce_user_bot_limit(db, user_id=current_user.id)

    executable_bytes, digest, filename = read_bot_executable(executable)

    existing_bot = (
        db.query(Bot)
        .filter(Bot.game_id == game_id, Bot.name == bot_name)
        .first()
    )
    if existing_bot is not None:
        bot_name_taken()

    bot = Bot(
        name=bot_name,
        game_id=game_id,
        owner_id=current_user.id,
        latest_submission_version=1,
    )
    db.add(bot)

    try:
        db.flush()
        submission = BotSubmission(
            bot_id=bot.id,
            version=1,
            executable=executable_bytes,
            executable_size=len(executable_bytes),
            executable_digest=digest,
            original_filename=filename,
        )
        db.add(submission)
        db.flush()
        bot.active_submission_id = submission.id
        db.commit()
    except IntegrityError:
        db.rollback()
        bot_name_taken()

    db.refresh(bot)
    db.refresh(submission)

    return BotCreateResponse(
        bot_id=bot.id,
        game_id=bot.game_id,
        name=bot.name,
        owner_id=bot.owner_id,
        submission_id=submission.id,
        version=submission.version,
    )


@app.post(
    "/bots/{bot_id}/submission",
    status_code=status.HTTP_201_CREATED,
    response_model=BotSubmissionResponse,
)
def submit_bot_executable(
    bot_id: int,
    executable: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_id}")

    if bot.owner_id != current_user.id:
        api_error(403, "bot_not_owned", "Bot is not owned by the authenticated user.")

    executable_bytes, digest, filename = read_bot_executable(executable)

    next_version = bot.latest_submission_version + 1
    submission = BotSubmission(
        bot_id=bot.id,
        version=next_version,
        executable=executable_bytes,
        executable_size=len(executable_bytes),
        executable_digest=digest,
        original_filename=filename,
    )
    db.add(submission)

    try:
        db.flush()
        bot.active_submission_id = submission.id
        bot.latest_submission_version = next_version
        db.commit()
    except IntegrityError:
        db.rollback()
        api_error(409, "submission_conflict", "Submission version already exists.")

    db.refresh(submission)
    db.refresh(bot)

    return BotSubmissionResponse(
        bot_id=bot.id,
        submission_id=submission.id,
        version=submission.version,
    )


@app.patch("/bots/{bot_id}", response_model=BotDetail)
def update_bot(
    bot_id: int,
    request: DescriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = (
        db.query(Bot)
        .options(selectinload(Bot.owner))
        .filter(Bot.id == bot_id)
        .first()
    )
    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_id}")

    if bot.owner_id != current_user.id:
        api_error(403, "bot_not_owned", "Bot is not owned by the authenticated user.")

    bot.description = request.description
    db.commit()
    db.refresh(bot)

    return BotDetail(
        bot_id=bot.id,
        name=bot.name,
        description=bot.description,
        game_id=bot.game_id,
        owner_name=get_bot_owner_name(bot),
        rating=bot.rating,
        games_played=bot.games_played,
        wins=bot.wins,
        losses=bot.losses,
        draws=bot.draws,
        created_at=bot.created_at,
    )


@app.post(
    "/matches",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MatchJobCreateResponse,
)
def create_match(
    request: MatchRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.game not in SUPPORTED_GAMES:
        api_error(400, "unsupported_game", f"Unsupported game: {request.game}")

    if len(request.players) != 2:
        api_error(
            400,
            "invalid_player_count",
            f"{request.game} requires exactly 2 players",
        )

    bot_one = resolve_bot(db, game_id=request.game, bot_name=request.players[0].bot)
    bot_two = resolve_bot(db, game_id=request.game, bot_name=request.players[1].bot)

    if bot_one.id == bot_two.id:
        api_error(400, "duplicate_bot_match", "A bot cannot play against itself")

    job = MatchJob(
        game_id=request.game,
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        requester_user_id=current_user.id,
        status="queued",
    )
    enforce_user_active_match_job_limit(db, user_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(text("NOTIFY match_jobs_channel"))
        db.commit()

    response.headers["Location"] = f"/match-jobs/{job.id}"

    return MatchJobCreateResponse(job_id=job.id, status=job.status)

@app.get("/match-jobs", response_model=MatchJobListResponse)
def list_match_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    game_id: str = Query(default=""),
    status_filter: str = Query(default="", alias="status"),
    db: Session = Depends(get_db),
):
    query = db.query(MatchJob)

    if game_id:
        query = query.filter(MatchJob.game_id == game_id)

    if status_filter:
        query = query.filter(MatchJob.status == status_filter)

    total = query.count()

    jobs = (
        query
        .options(selectinload(MatchJob.bot_one), selectinload(MatchJob.bot_two))
        .order_by(MatchJob.created_at.desc(), MatchJob.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return MatchJobListResponse(
        items=[serialize_match_job_summary(job) for job in jobs],
        limit=limit,
        offset=offset,
        total=total,
    )

@app.get("/featured-games", response_model=FeaturedGamesResponse)
def get_featured_games(db: Session = Depends(get_db)):
    return FeaturedGamesResponse(
        items=[
            serialize_live_match_job(job)
            for job in select_featured_match_jobs(db, limit=3)
        ]
    )

@app.get("/match-jobs/{job_id}", response_model=MatchJobDetail)
def get_match_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(MatchJob).filter(MatchJob.id == job_id).first()

    if job is None:
        api_error(404, "match_job_not_found", f"Match job not found: {job_id}")

    return MatchJobDetail(
        job_id=job.id,
        status=job.status,
        match_id=job.match_id,
        error_message=job.error_message,
    )

@app.get("/match-jobs/{job_id}/live", response_model=LiveMatchDetail)
def get_live_match_job(job_id: int, db: Session = Depends(get_db)):
    job = (
        db.query(MatchJob)
        .options(
            selectinload(MatchJob.bot_one),
            selectinload(MatchJob.bot_two),
            selectinload(MatchJob.moves),
            selectinload(MatchJob.match).selectinload(Match.moves),
            selectinload(MatchJob.match).selectinload(Match.bot_one),
            selectinload(MatchJob.match).selectinload(Match.bot_two),
        )
        .filter(MatchJob.id == job_id)
        .first()
    )

    if job is None:
        api_error(404, "match_job_not_found", f"Match job not found: {job_id}")

    return serialize_live_match_job(job)

@app.get("/matches", response_model=MatchListResponse)
def list_matches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    game_id: str = Query(default=""),
    bot_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Match)

    if game_id:
        query = query.filter(Match.game_id == game_id)

    if bot_id is not None:
        query = query.filter(or_(Match.bot_one_id == bot_id, Match.bot_two_id == bot_id))

    total = query.count()

    matches = (
        query
        .options(selectinload(Match.bot_one), selectinload(Match.bot_two))
        .order_by(Match.completed_at.desc(), Match.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return MatchListResponse(
        items=[serialize_match_summary(match) for match in matches],
        limit=limit,
        offset=offset,
        total=total,
    )

@app.get("/matches/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = (
        db.query(Match)
        .options(
            selectinload(Match.bot_one),
            selectinload(Match.bot_two),
            selectinload(Match.moves),
        )
        .filter(Match.id == match_id)
        .first()
    )

    if match is None:
        api_error(404, "match_not_found", f"Match not found: {match_id}")

    return serialize_match_detail(match)

@app.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(
    game_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    bots = (
        db.query(Bot)
        .options(selectinload(Bot.owner))
        .filter(Bot.game_id == game_id)
        .order_by(Bot.rating.desc(), Bot.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "bot_id": bot.id,
            "name": bot.name,
            "owner_name": get_bot_owner_name(bot),
            "rating": bot.rating,
            "games_played": bot.games_played,
            "wins": bot.wins,
            "losses": bot.losses,
            "draws": bot.draws,
        }
        for bot in bots
    ]

@app.get("/bots", response_model=list[BotSummary])
def list_bots(
    game_id: str = Query(default=""),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Bot)

    if game_id:
        query = query.filter(Bot.game_id == game_id)

    bots = (
        query.options(selectinload(Bot.owner))
        .order_by(Bot.name.asc(), Bot.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        BotSummary(
            bot_id=bot.id,
            name=bot.name,
            owner_name=get_bot_owner_display_name(bot),
            has_active_submission=bot.active_submission_id is not None,
        )
        for bot in bots
    ]

@app.get("/bots/{bot_id}", response_model=BotDetail)
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = (
        db.query(Bot)
        .options(selectinload(Bot.owner))
        .filter(Bot.id == bot_id)
        .first()
    )

    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_id}")

    return BotDetail(
        bot_id=bot.id,
        name=bot.name,
        description=bot.description,
        game_id=bot.game_id,
        owner_name=get_bot_owner_name(bot),
        rating=bot.rating,
        games_played=bot.games_played,
        wins=bot.wins,
        losses=bot.losses,
        draws=bot.draws,
        created_at=bot.created_at,
    )
