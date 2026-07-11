import pytest

from api.ratings import (
    DEFAULT_ELO_K_FACTOR,
    DEFAULT_ELO_RATING,
    EloRatingChange,
    calculate_elo_rating_change,
    expected_score,
    score_for_bot_one,
)


def test_rating_skeleton_exports_default_rating_and_change_type():
    assert DEFAULT_ELO_RATING == 1200
    assert DEFAULT_ELO_K_FACTOR == 32
    assert EloRatingChange(bot_one_rating=1216, bot_two_rating=1184)


def test_expected_score_returns_even_odds_for_equal_ratings():
    assert expected_score(1200, 1200) == pytest.approx(0.5)


def test_expected_score_favors_higher_rated_player():
    assert expected_score(1400, 1200) == pytest.approx(0.7597469266479578)
    assert expected_score(1200, 1400) == pytest.approx(0.2402530733520421)


def test_calculate_elo_rating_change_for_equal_ratings_and_win():
    rating_change = calculate_elo_rating_change(
        bot_one_rating=1200,
        bot_two_rating=1200,
        bot_one_score=1.0,
        k_factor=32,
    )

    assert rating_change == EloRatingChange(bot_one_rating=1216, bot_two_rating=1184)


def test_calculate_elo_rating_change_for_equal_ratings_and_draw():
    rating_change = calculate_elo_rating_change(
        bot_one_rating=1200,
        bot_two_rating=1200,
        bot_one_score=0.5,
        k_factor=32,
    )

    assert rating_change == EloRatingChange(bot_one_rating=1200, bot_two_rating=1200)


def test_calculate_elo_rating_change_for_underdog_win():
    rating_change = calculate_elo_rating_change(
        bot_one_rating=1200,
        bot_two_rating=1400,
        bot_one_score=1.0,
        k_factor=32,
    )

    assert rating_change == EloRatingChange(bot_one_rating=1224, bot_two_rating=1376)


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_calculate_elo_rating_change_rejects_invalid_score(score):
    with pytest.raises(ValueError, match="bot_one_score must be between 0 and 1"):
        calculate_elo_rating_change(
            bot_one_rating=1200,
            bot_two_rating=1200,
            bot_one_score=score,
            k_factor=32,
        )


def test_calculate_elo_rating_change_rejects_non_positive_k_factor():
    with pytest.raises(ValueError, match="k_factor must be greater than 0"):
        calculate_elo_rating_change(
            bot_one_rating=1200,
            bot_two_rating=1200,
            bot_one_score=1.0,
            k_factor=0,
        )


@pytest.mark.parametrize(
    ("winner_bot_id", "expected_score"),
    [
        (1, 1.0),
        (2, 0.0),
        (None, 0.5),
    ],
)
def test_score_for_bot_one_maps_match_result_to_elo_score(winner_bot_id, expected_score):
    assert (
        score_for_bot_one(
            winner_bot_id=winner_bot_id,
            bot_one_id=1,
            bot_two_id=2,
        )
        == expected_score
    )


def test_score_for_bot_one_rejects_unknown_winner_bot():
    with pytest.raises(ValueError, match="Unknown winner bot: 3"):
        score_for_bot_one(
            winner_bot_id=3,
            bot_one_id=1,
            bot_two_id=2,
        )
