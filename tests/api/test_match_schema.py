import importlib
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from api.models import Match


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

EXPECTED_COLUMNS = {
    "id",
    "game_id",
    "bot_one_id",
    "bot_two_id",
    "winner",
    "result_reason",
    "move_history",
    "created_at",
    "completed_at",
}


def test_match_model_declares_expected_columns():
    assert set(Match.__table__.columns.keys()) == EXPECTED_COLUMNS
    assert Match.__table__.c.game_id.nullable is False
    assert Match.__table__.c.bot_one_id.nullable is False
    assert Match.__table__.c.bot_two_id.nullable is False
    assert Match.__table__.c.winner.nullable is True
    assert Match.__table__.c.result_reason.nullable is False
    assert Match.__table__.c.move_history.nullable is False


def test_create_matches_migration_creates_expected_schema(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(create_matches_table, "op", operations)

        create_matches_table.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns("matches")}

        assert set(columns) == EXPECTED_COLUMNS
        assert columns["game_id"]["nullable"] is False
        assert columns["bot_one_id"]["nullable"] is False
        assert columns["bot_two_id"]["nullable"] is False
        assert columns["winner"]["nullable"] is True
        assert columns["result_reason"]["nullable"] is False
        assert columns["move_history"]["nullable"] is False
        assert inspector.get_pk_constraint("matches")["constrained_columns"] == ["id"]
