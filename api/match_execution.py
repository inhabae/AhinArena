import os

from api.bot_sandbox import BotSandbox, build_bot_sandbox
from api.models import Bot, BotSubmission, Match, Move
from api.ratings import DEFAULT_ELO_K_FACTOR, calculate_elo_rating_change
from api.ratings import score_for_bot_one as calculate_score_for_bot_one
from engine.connectfour.runner import run_connectfour_match
from engine.tictactoe.runner import run_tictactoe_match
from sqlalchemy.orm import Session, selectinload


PLAYER_ONE_MARKER = "p1"
PLAYER_TWO_MARKER = "p2"
DEFAULT_BOT_MOVE_TIMEOUT_SECONDS = 2.0
DEFAULT_BOT_STARTUP_TIMEOUT_SECONDS = 10.0


def _float_env_setting(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    return parsed if parsed > 0 else default


def get_bot_move_timeout_seconds() -> float:
    return _float_env_setting(
        "BOT_MOVE_TIMEOUT_SECONDS",
        DEFAULT_BOT_MOVE_TIMEOUT_SECONDS,
    )


def get_bot_startup_timeout_seconds() -> float:
    return _float_env_setting(
        "BOT_STARTUP_TIMEOUT_SECONDS",
        DEFAULT_BOT_STARTUP_TIMEOUT_SECONDS,
    )


def score_for_bot_one_or_error(
    winner_bot_id: int | None,
    bot_one_id: int,
    bot_two_id: int,
) -> float:
    return calculate_score_for_bot_one(
        winner_bot_id=winner_bot_id,
        bot_one_id=bot_one_id,
        bot_two_id=bot_two_id,
    )


def apply_match_record_updates(
    *,
    bot_one: Bot,
    bot_two: Bot,
    bot_one_submission: BotSubmission,
    bot_two_submission: BotSubmission,
    winner_bot_id: int | None,
    bot_one_rating_after: float,
    bot_two_rating_after: float,
) -> None:
    assert bot_one.id != bot_two.id
    assert winner_bot_id in {bot_one.id, bot_two.id, None}

    bot_one_submission.rating = bot_one_rating_after
    bot_two_submission.rating = bot_two_rating_after
    bot_one_submission.games_played += 1
    bot_two_submission.games_played += 1

    if winner_bot_id is None:
        bot_one_submission.draws += 1
        bot_two_submission.draws += 1
    elif winner_bot_id == bot_one.id:
        bot_one_submission.wins += 1
        bot_two_submission.losses += 1
    elif winner_bot_id == bot_two.id:
        bot_two_submission.wins += 1
        bot_one_submission.losses += 1


def execute_match(
    db: Session,
    *,
    game_id: str,
    bot_one_id: int,
    bot_two_id: int,
    move_timeout_seconds: float,
    startup_timeout_seconds: float,
    on_live_move=None,
) -> Match:
    bot_one = _load_bot_for_match(db, bot_one_id)
    bot_two = _load_bot_for_match(db, bot_two_id)

    if bot_one.id == bot_two.id:
        raise ValueError("A bot cannot play against itself")
    if bot_one.game_id != game_id or bot_two.game_id != game_id:
        raise ValueError("Match job bot game does not match job game")

    bot_one_submission = bot_one.active_submission
    bot_two_submission = bot_two.active_submission
    bot_one_rating_before = bot_one_submission.rating
    bot_two_rating_before = bot_two_submission.rating
    moves: list[tuple[str, object]] = []
    bot_one_sandbox: BotSandbox | None = None
    bot_two_sandbox: BotSandbox | None = None

    def record_move(player: str, move, board_state) -> None:
        moves.append((player, move))
        if on_live_move is not None:
            on_live_move(
                move_number=len(moves),
                bot_id=bot_one.id if player == PLAYER_ONE_MARKER else bot_two.id,
                move=_json_move(move),
                board_state=_json_board_state(board_state),
            )

    try:
        bot_one_sandbox = build_bot_sandbox(bot_one)
        bot_two_sandbox = build_bot_sandbox(bot_two)
        result = _run_match_for_game(
            game_id,
            p1_command=bot_one_sandbox.command,
            p2_command=bot_two_sandbox.command,
            on_move=record_move,
            timeout=move_timeout_seconds,
            startup_timeout=startup_timeout_seconds,
        )
    finally:
        if bot_one_sandbox is not None:
            bot_one_sandbox.cleanup()
        if bot_two_sandbox is not None:
            bot_two_sandbox.cleanup()

    winner_bot_id = _winner_marker_to_bot_id(
        result.get("winner"),
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
    )
    score = score_for_bot_one_or_error(
        winner_bot_id=winner_bot_id,
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
    )
    rating_change = calculate_elo_rating_change(
        bot_one_rating=bot_one_rating_before,
        bot_two_rating=bot_two_rating_before,
        bot_one_score=score,
        k_factor=DEFAULT_ELO_K_FACTOR,
    )
    bot_one_rating_after = rating_change.bot_one_rating
    bot_two_rating_after = rating_change.bot_two_rating
    bot_one_delta = bot_one_rating_after - bot_one_rating_before
    bot_two_delta = bot_two_rating_after - bot_two_rating_before

    match = Match(
        game_id=game_id,
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        bot_one_submission_id=bot_one_submission.id,
        bot_two_submission_id=bot_two_submission.id,
        bot_one_rating_before=bot_one_rating_before,
        bot_two_rating_before=bot_two_rating_before,
        bot_one_rating_after=bot_one_rating_after,
        bot_two_rating_after=bot_two_rating_after,
        bot_one_rating_delta=bot_one_delta,
        bot_two_rating_delta=bot_two_delta,
        winner_bot_id=winner_bot_id,
        result_reason=result["reason"],
    )
    db.add(match)
    db.flush()

    for index, (player, move) in enumerate(moves, start=1):
        db.add(
            Move(
                match_id=match.id,
                move_number=index,
                bot_id=bot_one.id if player == PLAYER_ONE_MARKER else bot_two.id,
                move=_json_move(move),
            )
        )

    apply_match_record_updates(
        bot_one=bot_one,
        bot_two=bot_two,
        bot_one_submission=bot_one_submission,
        bot_two_submission=bot_two_submission,
        winner_bot_id=winner_bot_id,
        bot_one_rating_after=bot_one_rating_after,
        bot_two_rating_after=bot_two_rating_after,
    )
    db.flush()
    return match


def _load_bot_for_match(db: Session, bot_id: int) -> Bot:
    bot = (
        db.query(Bot)
        .options(selectinload(Bot.active_submission))
        .filter(Bot.id == bot_id)
        .first()
    )
    if bot is None:
        raise ValueError(f"Bot not found: {bot_id}")
    if bot.active_submission_id is None or bot.active_submission is None:
        raise ValueError(f"Bot has no active submission: {bot.name}")
    return bot


def _run_match_for_game(game_id: str, **kwargs):
    if game_id == "tictactoe":
        return run_tictactoe_match(**kwargs)
    if game_id == "connect-four":
        return run_connectfour_match(**kwargs)
    raise ValueError(f"Unsupported game: {game_id}")


def _winner_marker_to_bot_id(
    winner: str | None,
    *,
    bot_one_id: int,
    bot_two_id: int,
) -> int | None:
    if winner is None:
        return None
    if winner == PLAYER_ONE_MARKER:
        return bot_one_id
    if winner == PLAYER_TWO_MARKER:
        return bot_two_id
    raise ValueError(f"Unknown winner marker: {winner}")


def _json_move(move):
    if isinstance(move, tuple):
        return list(move)
    return move


def _json_board_state(board_state):
    return [
        [None if cell == " " else cell for cell in row]
        for row in board_state
    ]
