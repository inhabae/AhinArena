import ast
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.auth import hash_password, verify_password
from api.bot_sandbox import build_bot_sandbox
from api.database import get_db, get_sessionmaker
from api.featured_games import select_featured_match_jobs
from api.models import Bot, BotSubmission, Match, MatchJob, Move, Session as AuthSession, User
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
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, text
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
    BotCreateRequest,
    BotCreateResponse,
    BotSubmissionRequest,
    BotSubmissionResponse,
    DescriptionUpdateRequest,
    UserLoginRequest,
    UserProfile,
    UserPublic,
    UserRegisterRequest,
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
MAX_BOT_SUBMISSION_SOURCE_BYTES = 100_000

DEFAULT_BOT_SOURCE_PATHS = {
    "tictactoe": Path(__file__).resolve().parent.parent / "engine" / "tictactoe" / "random_bot.py",
    "connect-four": Path(__file__).resolve().parent.parent / "engine" / "connectfour" / "random_bot.py",
}


def get_bot_owner_name(bot: Bot) -> str:
    if bot.owner is None:
        return "System"

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
        created_at=user.created_at,
    )


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


def should_secure_auth_cookie() -> bool:
    environment = (
        os.environ.get("ENVIRONMENT")
        or os.environ.get("APP_ENV")
        or os.environ.get("FASTAPI_ENV")
        or "development"
    )
    return environment.lower() in {"production", "prod"}


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
    default_bot_sources = {
        game_id: source_path.read_text(encoding="utf-8")
        for game_id, source_path in DEFAULT_BOT_SOURCE_PATHS.items()
    }

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
                submission = BotSubmission(
                    bot_id=bot.id,
                    version=1,
                    language="python",
                    source_code=default_bot_sources[game_id],
                )
                db.add(submission)
                db.flush()
                bot.active_submission_id = submission.id

    db.commit()


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
    response_model=UserPublic,
)
def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    normalized_email = request.email.strip().lower()
    username = request.username.strip()

    if not username:
        api_error(422, "validation_error", "Username is required.")

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
        password_hash=hash_password(request.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        api_error(409, "registration_conflict", "Email or username is already registered.")

    db.refresh(user)

    return serialize_user_public(user)


@app.post(
    "/auth/login",
    response_model=UserPublic,
)
def login_user(
    request: UserLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    login_identifier = request.login if request.login is not None else request.email
    login_identifier = login_identifier.strip()
    normalized_email = login_identifier.lower()
    user = (
        db.query(User)
        .filter(or_(User.email == normalized_email, User.username == login_identifier))
        .first()
    )

    if user is None or not verify_password(request.password, user.password_hash):
        invalid_credentials()

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


def validate_python_submission_source(source_code: str) -> None:
    if not source_code.strip():
        api_error(422, "validation_error", "Source code is required.")

    if len(source_code.encode("utf-8")) > MAX_BOT_SUBMISSION_SOURCE_BYTES:
        api_error(413, "submission_too_large", "Submission source code is too large.")

    try:
        ast.parse(source_code)
    except SyntaxError as error:
        api_error(422, "invalid_syntax", f"Invalid Python syntax: {error.msg}.")


@app.post(
    "/bots",
    status_code=status.HTTP_201_CREATED,
    response_model=BotCreateResponse,
)
def create_bot(
    request: BotCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.game_id not in SUPPORTED_GAMES:
        api_error(400, "unsupported_game", f"Unsupported game: {request.game_id}")

    if request.language != "python":
        api_error(400, "unsupported_language", f"Unsupported language: {request.language}")

    bot_name = request.name.strip()
    if not bot_name:
        api_error(422, "validation_error", "Bot name is required.")

    validate_python_submission_source(request.source_code)

    existing_bot = (
        db.query(Bot)
        .filter(Bot.game_id == request.game_id, Bot.name == bot_name)
        .first()
    )
    if existing_bot is not None:
        bot_name_taken()

    bot = Bot(
        name=bot_name,
        game_id=request.game_id,
        owner_id=current_user.id,
    )
    db.add(bot)

    try:
        db.flush()
        submission = BotSubmission(
            bot_id=bot.id,
            version=1,
            language=request.language,
            source_code=request.source_code,
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
def submit_bot_source(
    bot_id: int,
    request: BotSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_id}")

    if bot.owner_id != current_user.id:
        api_error(403, "bot_not_owned", "Bot is not owned by the authenticated user.")

    if request.language != "python":
        api_error(400, "unsupported_language", f"Unsupported language: {request.language}")

    validate_python_submission_source(request.source_code)

    current_max_version = (
        db.query(BotSubmission.version)
        .filter(BotSubmission.bot_id == bot.id)
        .order_by(BotSubmission.version.desc())
        .limit(1)
        .scalar()
    )
    submission = BotSubmission(
        bot_id=bot.id,
        version=(current_max_version or 0) + 1,
        language=request.language,
        source_code=request.source_code,
    )
    db.add(submission)

    try:
        db.flush()
        bot.active_submission_id = submission.id
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
        status="queued",
    )
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
