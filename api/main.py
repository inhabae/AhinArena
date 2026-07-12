import ast
import os
import secrets
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.auth import hash_password, verify_password
from api.database import get_db, get_sessionmaker
from api.models import Bot, BotSubmission, Match, Move, Session as AuthSession, User
from api.ratings import DEFAULT_ELO_K_FACTOR, calculate_elo_rating_change
from api.ratings import score_for_bot_one as calculate_score_for_bot_one
from engine.connectfour.runner import run_connectfour_match
from engine.tictactoe.runner import run_tictactoe_match
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
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
    MatchCreateResponse,
    MatchRequest,
    MatchSummary,
    MatchDetail,
    MatchListResponse,
    MoveEntry,
    LeaderboardEntry,
    BotSummary,
    BotCreateRequest,
    BotCreateResponse,
    BotSubmissionRequest,
    BotSubmissionResponse,
    UserLoginRequest,
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

def resolve_bot(db: Session, *, game_id: str, bot_name: str) -> Bot:
    bot = (
        db.query(Bot)
        .filter(Bot.game_id == game_id, Bot.name == bot_name)
        .first()
    )

    if bot is None:
        api_error(404, "bot_not_found", f"Bot not found: {bot_name}")

    return bot


def resolve_bot_command(bot: Bot) -> list[str]:
    if bot.active_submission_id is None or bot.active_submission is None:
        api_error(
            400,
            "bot_has_no_submission",
            f"Bot has no active submission: {bot.name}",
        )

    project_root = Path(__file__).resolve().parent.parent
    source_code = bot.active_submission.source_code
    bootstrapped_source = (
        "import sys\n"
        f"sys.path.insert(0, {str(project_root)!r})\n"
        f"exec(compile({source_code!r}, __file__, 'exec'))\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix=f"ahinarena_bot_{bot.id}_",
        encoding="utf-8",
        delete=False,
    ) as source_file:
        source_file.write(bootstrapped_source)
        source_path = source_file.name

    return [sys.executable, source_path]


def cleanup_bot_command_temp_source(command: list[str]) -> None:
    if len(command) < 2:
        return

    source_path = Path(command[1])
    if (
        source_path.parent != Path(tempfile.gettempdir())
        or source_path.suffix != ".py"
        or not source_path.name.startswith("ahinarena_bot_")
    ):
        return

    source_path.unlink(missing_ok=True)


def score_for_bot_one_or_error(
    winner_bot_id: int | None,
    bot_one_id: int,
    bot_two_id: int,
) -> float:
    try:
        return calculate_score_for_bot_one(
            winner_bot_id=winner_bot_id,
            bot_one_id=bot_one_id,
            bot_two_id=bot_two_id,
        )
    except ValueError:
        api_error(500, "unknown_winner_bot", f"Unknown winner bot: {winner_bot_id}")


def apply_match_record_updates(
    *,
    bot_one: Bot,
    bot_two: Bot,
    winner_bot_id: int | None,
    bot_one_rating_after: int,
    bot_two_rating_after: int,
) -> None:
    assert bot_one.id != bot_two.id
    assert winner_bot_id in {bot_one.id, bot_two.id, None}

    bot_one.rating = bot_one_rating_after
    bot_two.rating = bot_two_rating_after
    bot_one.games_played += 1
    bot_two.games_played += 1

    if winner_bot_id is None:
        bot_one.draws += 1
        bot_two.draws += 1
    elif winner_bot_id == bot_one.id:
        bot_one.wins += 1
        bot_two.losses += 1
    elif winner_bot_id == bot_two.id:
        bot_two.wins += 1
        bot_one.losses += 1


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

    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
    )


@app.post(
    "/auth/login",
    response_model=UserPublic,
)
def login_user(
    request: UserLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

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

    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
    )


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
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at,
    )


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

    existing_bot = (
        db.query(Bot)
        .filter(Bot.game_id == request.game_id, Bot.name == request.name)
        .first()
    )
    if existing_bot is not None:
        bot_name_taken()

    bot = Bot(
        name=request.name,
        game_id=request.game_id,
        owner_id=current_user.id,
    )
    db.add(bot)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        bot_name_taken()

    db.refresh(bot)

    return BotCreateResponse(
        bot_id=bot.id,
        game_id=bot.game_id,
        name=bot.name,
        owner_id=bot.owner_id,
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


@app.post(
    "/matches",
    status_code=status.HTTP_201_CREATED,
    response_model=MatchCreateResponse,
)
def create_match(
    request: MatchRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runners = {
        "tictactoe": run_tictactoe_match,
        "connect-four": run_connectfour_match,
    }

    if request.game not in runners:
        api_error(400, "unsupported_game", f"Unsupported game: {request.game}")
    
    if len(request.players) != 2:
        api_error(400, "invalid_player_count", f"{request.game} requires exactly 2 players")

    bot_one = resolve_bot(db, game_id=request.game, bot_name=request.players[0].bot)
    bot_two = resolve_bot(db, game_id=request.game, bot_name=request.players[1].bot)

    if bot_one.id == bot_two.id:
        api_error(400, "duplicate_bot_match", "A bot cannot play against itself")

    p1_command = []
    p2_command = []
    try:
        p1_command = resolve_bot_command(bot_one)
        p2_command = resolve_bot_command(bot_two)

        try:
            moves = []

            def record_move(player, move, board):
                bot_id = bot_one.id if player == "p1" else bot_two.id
                moves.append((bot_id, move))

            result = runners[request.game](
                p1_command=p1_command,
                p2_command=p2_command,
                on_move=record_move,
            )
        except Exception as error:
            api_error(500, "match_execution_failed", str(error))
    finally:
        cleanup_bot_command_temp_source(p1_command)
        cleanup_bot_command_temp_source(p2_command)

    bot_one_rating_before = bot_one.rating
    bot_two_rating_before = bot_two.rating
    winner_bot_id = (
        None if result["winner"] is None
        else bot_one.id if result["winner"] == "p1"
        else bot_two.id
    )
    rating_change = calculate_elo_rating_change(
        bot_one_rating=bot_one_rating_before,
        bot_two_rating=bot_two_rating_before,
        bot_one_score=score_for_bot_one_or_error(
            winner_bot_id,
            bot_one.id,
            bot_two.id,
        ),
        k_factor=DEFAULT_ELO_K_FACTOR,
    )
    bot_one_rating_delta = rating_change.bot_one_rating - bot_one_rating_before
    bot_two_rating_delta = rating_change.bot_two_rating - bot_two_rating_before

    match = Match(
        game_id=request.game,
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        bot_one_rating_before=bot_one_rating_before,
        bot_two_rating_before=bot_two_rating_before,
        bot_one_rating_after=rating_change.bot_one_rating,
        bot_two_rating_after=rating_change.bot_two_rating,
        bot_one_rating_delta=bot_one_rating_delta,
        bot_two_rating_delta=bot_two_rating_delta,
        winner_bot_id=winner_bot_id,
        result_reason=result["reason"],
        moves=[
            Move(move_number=index, bot_id=bot_id, move=move)
            for index, (bot_id, move) in enumerate(moves, start=1)
        ],
    )
    apply_match_record_updates(
        bot_one=bot_one,
        bot_two=bot_two,
        winner_bot_id=winner_bot_id,
        bot_one_rating_after=rating_change.bot_one_rating,
        bot_two_rating_after=rating_change.bot_two_rating,
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    response.headers["Location"] = f"/matches/{match.id}"

    return MatchCreateResponse(
        match_id=match.id,
        game=match.game_id,
        winner_bot_id=match.winner_bot_id,
        result_reason=match.result_reason,
    )

@app.get("/matches", response_model=MatchListResponse)
def list_matches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    game_id: str = Query(default=""),
    db: Session = Depends(get_db),
):
    query = db.query(Match)

    if game_id:
        query = query.filter(Match.game_id == game_id)

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
