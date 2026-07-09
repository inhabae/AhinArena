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
    "create_matches_table",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "0002_create_matches_table.py",
)
create_matches_table = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(create_matches_table)

spec = importlib.util.spec_from_file_location(
    "add_moves_table",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "84de88aa274e_add_moves_table.py",
)
add_moves_table = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(add_moves_table)

spec = importlib.util.spec_from_file_location(
    "remove_move_history_from_matches",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "a50c745e19b1_remove_move_history_from_matches.py",
)
remove_move_history_from_matches = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(remove_move_history_from_matches)

EXPECTED_MATCH_COLUMNS = {
    "id",
    "game_id",
    "bot_one_id",
    "bot_two_id",
    "winner",
    "result_reason",
    "created_at",
    "completed_at",
}

EXPECTED_MOVE_COLUMNS = {
    "id",
    "match_id",
    "move_number",
    "player",
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
    assert isinstance(Match.__table__.c.bot_one_id.type, sa.Integer)
    assert isinstance(Match.__table__.c.bot_two_id.type, sa.Integer)
    assert {
        foreign_key.target_fullname
        for foreign_key in Match.__table__.c.bot_one_id.foreign_keys
    } == {"bots.id"}
    assert {
        foreign_key.target_fullname
        for foreign_key in Match.__table__.c.bot_two_id.foreign_keys
    } == {"bots.id"}
    assert Match.__table__.c.winner.nullable is True
    assert Match.__table__.c.result_reason.nullable is False


def test_move_model_declares_expected_columns():
    assert set(Move.__table__.columns.keys()) == EXPECTED_MOVE_COLUMNS
    assert Move.__table__.c.match_id.nullable is False
    assert Move.__table__.c.move_number.nullable is False
    assert Move.__table__.c.player.nullable is False
    assert Move.__table__.c.move.nullable is False


def test_create_matches_migration_creates_expected_schema(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(create_matches_table, "op", operations)

        create_matches_table.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns("matches")}

        assert set(columns) == EXPECTED_MATCH_COLUMNS | {"move_history"}
        assert columns["game_id"]["nullable"] is False
        assert columns["bot_one_id"]["nullable"] is False
        assert columns["bot_two_id"]["nullable"] is False
        assert columns["winner"]["nullable"] is True
        assert columns["result_reason"]["nullable"] is False
        assert columns["move_history"]["nullable"] is False
        assert inspector.get_pk_constraint("matches")["constrained_columns"] == ["id"]


def test_move_migrations_create_expected_schema(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(create_matches_table, "op", operations)
        monkeypatch.setattr(add_moves_table, "op", operations)
        monkeypatch.setattr(remove_move_history_from_matches, "op", operations)

        create_matches_table.upgrade()
        add_moves_table.upgrade()
        remove_move_history_from_matches.upgrade()

        inspector = sa.inspect(connection)
        match_columns = {
            column["name"] for column in inspector.get_columns("matches")
        }
        move_columns = {
            column["name"]: column for column in inspector.get_columns("moves")
        }
        foreign_keys = inspector.get_foreign_keys("moves")
        unique_constraints = inspector.get_unique_constraints("moves")

        assert match_columns == EXPECTED_MATCH_COLUMNS
        assert set(move_columns) == EXPECTED_MOVE_COLUMNS
        assert move_columns["match_id"]["nullable"] is False
        assert move_columns["move_number"]["nullable"] is False
        assert move_columns["player"]["nullable"] is False
        assert move_columns["move"]["nullable"] is False
        assert inspector.get_pk_constraint("moves")["constrained_columns"] == ["id"]
        assert foreign_keys[0]["constrained_columns"] == ["match_id"]
        assert foreign_keys[0]["referred_table"] == "matches"
        assert any(
            constraint["column_names"] == ["match_id", "move_number"]
            for constraint in unique_constraints
        )
