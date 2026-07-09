import importlib
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.models import Bot, Match, Move


spec = importlib.util.spec_from_file_location(
    "baseline_schema",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "b4e57400891e_baseline_schema.py",
)
baseline_schema = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(baseline_schema)

EXPECTED_MATCH_COLUMNS = {
    "id",
    "game_id",
    "bot_one_id",
    "bot_two_id",
    "bot_one_rating_before",
    "bot_two_rating_before",
    "bot_one_rating_after",
    "bot_two_rating_after",
    "bot_one_rating_delta",
    "bot_two_rating_delta",
    "winner_bot_id",
    "result_reason",
    "created_at",
    "completed_at",
}

EXPECTED_MOVE_COLUMNS = {
    "id",
    "match_id",
    "move_number",
    "bot_id",
    "move",
}

EXPECTED_BOT_COLUMNS = {
    "id",
    "name",
    "game_id",
    "created_by",
    "rating",
    "games_played",
    "wins",
    "losses",
    "draws",
    "created_at",
    "updated_at",
}


def column_default_value(column):
    return column.default.arg if column.default is not None else None


def server_default_value(column):
    return str(column.server_default.arg) if column.server_default is not None else None


def reflected_default_value(column):
    default = column["default"]
    return default.strip("'") if default is not None else None


def test_bot_model_declares_expected_columns_defaults_and_constraints():
    assert set(Bot.__table__.columns.keys()) == EXPECTED_BOT_COLUMNS

    assert Bot.__table__.c.name.nullable is False
    assert Bot.__table__.c.game_id.nullable is False
    assert Bot.__table__.c.created_by.nullable is False
    assert Bot.__table__.c.rating.nullable is False
    assert Bot.__table__.c.games_played.nullable is False
    assert Bot.__table__.c.wins.nullable is False
    assert Bot.__table__.c.losses.nullable is False
    assert Bot.__table__.c.draws.nullable is False
    assert Bot.__table__.c.created_at.nullable is False
    assert Bot.__table__.c.updated_at.nullable is False

    assert column_default_value(Bot.__table__.c.rating) == 1200
    assert column_default_value(Bot.__table__.c.games_played) == 0
    assert column_default_value(Bot.__table__.c.wins) == 0
    assert column_default_value(Bot.__table__.c.losses) == 0
    assert column_default_value(Bot.__table__.c.draws) == 0
    assert server_default_value(Bot.__table__.c.rating) == "1200"
    assert server_default_value(Bot.__table__.c.games_played) == "0"
    assert server_default_value(Bot.__table__.c.wins) == "0"
    assert server_default_value(Bot.__table__.c.losses) == "0"
    assert server_default_value(Bot.__table__.c.draws) == "0"

    constraints = {constraint.name: constraint for constraint in Bot.__table__.constraints}
    assert "uq_bots_game_id_name" in constraints
    assert constraints["uq_bots_game_id_name"].columns.keys() == ["game_id", "name"]
    assert "ck_bots_rating_non_negative" in constraints
    assert "ck_bots_games_played_non_negative" in constraints
    assert "ck_bots_wins_non_negative" in constraints
    assert "ck_bots_losses_non_negative" in constraints
    assert "ck_bots_draws_non_negative" in constraints
    assert "ck_bots_record_matches_games_played" in constraints

    indexes = {index.name: index for index in Bot.__table__.indexes}
    assert indexes["ix_bots_game_id_rating"].columns.keys() == ["game_id", "rating"]


def test_bot_table_applies_defaults_and_unique_names_within_game():
    engine = sa.create_engine("sqlite:///:memory:")
    Bot.__table__.create(engine)

    with Session(engine) as session:
        bot = Bot(name="random", game_id="tictactoe", created_by="system")
        same_name_different_game = Bot(
            name="random",
            game_id="connect-four",
            created_by="system",
        )
        session.add_all([bot, same_name_different_game])
        session.commit()

        assert bot.rating == 1200
        assert bot.games_played == 0
        assert bot.wins == 0
        assert bot.losses == 0
        assert bot.draws == 0

        session.add(Bot(name="random", game_id="tictactoe", created_by="system"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_match_model_declares_expected_columns():
    assert set(Match.__table__.columns.keys()) == EXPECTED_MATCH_COLUMNS
    assert Match.__table__.c.game_id.nullable is False
    assert Match.__table__.c.bot_one_id.nullable is False
    assert Match.__table__.c.bot_two_id.nullable is False
    assert Match.__table__.c.bot_one_rating_before.nullable is False
    assert Match.__table__.c.bot_two_rating_before.nullable is False
    assert Match.__table__.c.bot_one_rating_after.nullable is False
    assert Match.__table__.c.bot_two_rating_after.nullable is False
    assert Match.__table__.c.bot_one_rating_delta.nullable is False
    assert Match.__table__.c.bot_two_rating_delta.nullable is False
    assert isinstance(Match.__table__.c.bot_one_id.type, sa.Integer)
    assert isinstance(Match.__table__.c.bot_two_id.type, sa.Integer)
    assert isinstance(Match.__table__.c.winner_bot_id.type, sa.Integer)
    assert {
        foreign_key.target_fullname
        for foreign_key in Match.__table__.c.bot_one_id.foreign_keys
    } == {"bots.id"}
    assert {
        foreign_key.target_fullname
        for foreign_key in Match.__table__.c.bot_two_id.foreign_keys
    } == {"bots.id"}
    assert {
        foreign_key.target_fullname
        for foreign_key in Match.__table__.c.winner_bot_id.foreign_keys
    } == {"bots.id"}
    assert Match.__table__.c.winner_bot_id.nullable is True
    assert Match.__table__.c.result_reason.nullable is False


def test_move_model_declares_expected_columns():
    assert set(Move.__table__.columns.keys()) == EXPECTED_MOVE_COLUMNS
    assert Move.__table__.c.match_id.nullable is False
    assert Move.__table__.c.move_number.nullable is False
    assert Move.__table__.c.bot_id.nullable is False
    assert isinstance(Move.__table__.c.bot_id.type, sa.Integer)
    assert {
        foreign_key.target_fullname
        for foreign_key in Move.__table__.c.bot_id.foreign_keys
    } == {"bots.id"}
    assert Move.__table__.c.move.nullable is False


def test_baseline_migration_creates_expected_schema(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)

        baseline_schema.upgrade()

        inspector = sa.inspect(connection)
        bot_columns = {column["name"]: column for column in inspector.get_columns("bots")}
        match_columns = {
            column["name"]: column for column in inspector.get_columns("matches")
        }
        move_columns = {
            column["name"]: column for column in inspector.get_columns("moves")
        }
        move_foreign_keys = inspector.get_foreign_keys("moves")
        move_unique_constraints = inspector.get_unique_constraints("moves")
        match_foreign_keys = inspector.get_foreign_keys("matches")
        bot_unique_constraints = inspector.get_unique_constraints("bots")

        assert set(bot_columns) == EXPECTED_BOT_COLUMNS
        assert set(match_columns) == EXPECTED_MATCH_COLUMNS
        assert set(move_columns) == EXPECTED_MOVE_COLUMNS

        assert reflected_default_value(bot_columns["rating"]) == "1200"
        assert reflected_default_value(bot_columns["games_played"]) == "0"
        assert reflected_default_value(bot_columns["wins"]) == "0"
        assert reflected_default_value(bot_columns["losses"]) == "0"
        assert reflected_default_value(bot_columns["draws"]) == "0"
        assert any(
            constraint["column_names"] == ["game_id", "name"]
            for constraint in bot_unique_constraints
        )

        assert match_columns["game_id"]["nullable"] is False
        assert match_columns["bot_one_id"]["nullable"] is False
        assert match_columns["bot_two_id"]["nullable"] is False
        assert match_columns["winner_bot_id"]["nullable"] is True
        assert match_columns["result_reason"]["nullable"] is False
        assert inspector.get_pk_constraint("matches")["constrained_columns"] == ["id"]
        assert any(
            foreign_key["constrained_columns"] == ["bot_one_id"]
            and foreign_key["referred_table"] == "bots"
            for foreign_key in match_foreign_keys
        )
        assert any(
            foreign_key["constrained_columns"] == ["bot_two_id"]
            and foreign_key["referred_table"] == "bots"
            for foreign_key in match_foreign_keys
        )
        assert any(
            foreign_key["constrained_columns"] == ["winner_bot_id"]
            and foreign_key["referred_table"] == "bots"
            for foreign_key in match_foreign_keys
        )

        assert move_columns["match_id"]["nullable"] is False
        assert move_columns["move_number"]["nullable"] is False
        assert move_columns["bot_id"]["nullable"] is False
        assert move_columns["move"]["nullable"] is False
        assert inspector.get_pk_constraint("moves")["constrained_columns"] == ["id"]
        assert any(
            foreign_key["constrained_columns"] == ["match_id"]
            and foreign_key["referred_table"] == "matches"
            for foreign_key in move_foreign_keys
        )
        assert any(
            foreign_key["constrained_columns"] == ["bot_id"]
            and foreign_key["referred_table"] == "bots"
            for foreign_key in move_foreign_keys
        )
        assert any(
            constraint["column_names"] == ["match_id", "move_number"]
            for constraint in move_unique_constraints
        )


def test_baseline_migration_downgrade_drops_schema(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)

        baseline_schema.upgrade()
        baseline_schema.downgrade()

        inspector = sa.inspect(connection)
        assert inspector.get_table_names() == []
