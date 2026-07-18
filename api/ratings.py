from dataclasses import dataclass


DEFAULT_ELO_RATING = 1200.0
DEFAULT_ELO_K_FACTOR = 32


@dataclass(frozen=True)
class EloRatingChange:
    bot_one_rating: float
    bot_two_rating: float


def expected_score(player_rating: float, opponent_rating: float) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def calculate_elo_rating_change(
    *,
    bot_one_rating: float,
    bot_two_rating: float,
    bot_one_score: float,
    k_factor: int,
) -> EloRatingChange:
    if not 0 <= bot_one_score <= 1:
        raise ValueError("bot_one_score must be between 0 and 1")

    if k_factor <= 0:
        raise ValueError("k_factor must be greater than 0")

    bot_two_score = 1 - bot_one_score
    bot_one_expected = expected_score(bot_one_rating, bot_two_rating)
    bot_two_expected = expected_score(bot_two_rating, bot_one_rating)

    return EloRatingChange(
        bot_one_rating=max(0.0, bot_one_rating + k_factor * (bot_one_score - bot_one_expected)),
        bot_two_rating=max(0.0, bot_two_rating + k_factor * (bot_two_score - bot_two_expected)),
    )


def score_for_bot_one(
    *,
    winner_bot_id: int | None,
    bot_one_id: int,
    bot_two_id: int,
) -> float:
    if winner_bot_id == bot_one_id:
        return 1.0

    if winner_bot_id is None:
        return 0.5

    if winner_bot_id != bot_two_id:
        raise ValueError(f"Unknown winner bot: {winner_bot_id}")

    return 0.0
