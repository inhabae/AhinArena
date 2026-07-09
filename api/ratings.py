from dataclasses import dataclass


DEFAULT_ELO_RATING = 1200
DEFAULT_ELO_K_FACTOR = 32


@dataclass(frozen=True)
class EloRatingChange:
    bot_one_rating: int
    bot_two_rating: int


def expected_score(player_rating: int, opponent_rating: int) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def calculate_elo_rating_change(
    *,
    bot_one_rating: int,
    bot_two_rating: int,
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
        bot_one_rating=round(bot_one_rating + k_factor * (bot_one_score - bot_one_expected)),
        bot_two_rating=round(bot_two_rating + k_factor * (bot_two_score - bot_two_expected)),
    )
