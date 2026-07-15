import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.models import Bot, BotSubmission, Match, Move, Session as AuthSession, User


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

auth_spec = importlib.util.spec_from_file_location(
    "add_users_and_sessions",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "49ec82f79706_add_users_and_sessions.py",
)
auth_schema = importlib.util.module_from_spec(auth_spec)
assert auth_spec.loader is not None
auth_spec.loader.exec_module(auth_schema)

bot_owner_spec = importlib.util.spec_from_file_location(
    "replace_bot_created_by_with_owner_id",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "8a4f1f3d7b20_replace_bot_created_by_with_owner_id.py",
)
bot_owner_schema = importlib.util.module_from_spec(bot_owner_spec)
assert bot_owner_spec.loader is not None
bot_owner_spec.loader.exec_module(bot_owner_schema)

username_spec = importlib.util.spec_from_file_location(
    "add_usernames",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "c2e49a7b6d12_add_usernames.py",
)
username_schema = importlib.util.module_from_spec(username_spec)
assert username_spec.loader is not None
username_spec.loader.exec_module(username_schema)

cleanup_indexes_spec = importlib.util.spec_from_file_location(
    "cleanup_redundant_pk_indexes",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "d6f4c8a1b2e3_cleanup_redundant_pk_indexes.py",
)
cleanup_indexes_schema = importlib.util.module_from_spec(cleanup_indexes_spec)
assert cleanup_indexes_spec.loader is not None
cleanup_indexes_spec.loader.exec_module(cleanup_indexes_schema)

bot_submissions_spec = importlib.util.spec_from_file_location(
    "add_bot_submissions",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "3f2a1b0c9d8e_add_bot_submissions.py",
)
bot_submissions_schema = importlib.util.module_from_spec(bot_submissions_spec)
assert bot_submissions_spec.loader is not None
bot_submissions_spec.loader.exec_module(bot_submissions_schema)

descriptions_spec = importlib.util.spec_from_file_location(
    "add_profile_descriptions",
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "5f7d8c9a0b12_add_profile_descriptions.py",
)
descriptions_schema = importlib.util.module_from_spec(descriptions_spec)
assert descriptions_spec.loader is not None
descriptions_spec.loader.exec_module(descriptions_schema)

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
    "description",
    "game_id",
    "owner_id",
    "active_submission_id",
    "rating",
    "games_played",
    "wins",
    "losses",
    "draws",
    "created_at",
    "updated_at",
}

EXPECTED_BOT_OWNER_MIGRATION_BOT_COLUMNS = EXPECTED_BOT_COLUMNS - {
    "active_submission_id",
    "description",
}
EXPECTED_BOT_SUBMISSIONS_MIGRATION_BOT_COLUMNS = EXPECTED_BOT_COLUMNS - {
    "description",
}

EXPECTED_BASELINE_BOT_COLUMNS = (EXPECTED_BOT_COLUMNS - {"owner_id"}) | {"created_by"}
EXPECTED_BASELINE_BOT_COLUMNS -= {"active_submission_id", "description"}

EXPECTED_BOT_SUBMISSION_COLUMNS = {
    "id",
    "bot_id",
    "version",
    "language",
    "source_code",
    "created_at",
}

EXPECTED_USER_COLUMNS = {
    "id",
    "email",
    "username",
    "description",
    "password_hash",
    "created_at",
}

EXPECTED_AUTH_MIGRATION_USER_COLUMNS = EXPECTED_USER_COLUMNS - {"username", "description"}
EXPECTED_USERNAME_MIGRATION_USER_COLUMNS = EXPECTED_USER_COLUMNS - {"description"}

EXPECTED_SESSION_COLUMNS = {
    "id",
    "user_id",
    "created_at",
    "expires_at",
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
    assert Bot.__table__.c.description.nullable is False
    assert Bot.__table__.c.game_id.nullable is False
    assert Bot.__table__.c.owner_id.nullable is True
    assert {
        foreign_key.target_fullname
        for foreign_key in Bot.__table__.c.owner_id.foreign_keys
    } == {"users.id"}
    assert Bot.__table__.c.active_submission_id.nullable is True
    assert {
        foreign_key.target_fullname
        for foreign_key in Bot.__table__.c.active_submission_id.foreign_keys
    } == {"bot_submissions.id"}
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
    assert column_default_value(Bot.__table__.c.description) == ""
    assert server_default_value(Bot.__table__.c.rating) == "1200"
    assert server_default_value(Bot.__table__.c.games_played) == "0"
    assert server_default_value(Bot.__table__.c.wins) == "0"
    assert server_default_value(Bot.__table__.c.losses) == "0"
    assert server_default_value(Bot.__table__.c.draws) == "0"
    assert server_default_value(Bot.__table__.c.description) == ""

    constraints = {constraint.name: constraint for constraint in Bot.__table__.constraints}
    assert "uq_bots_game_id_name" in constraints
    assert constraints["uq_bots_game_id_name"].columns.keys() == ["game_id", "name"]
    assert "ck_bots_rating_non_negative" in constraints
    assert "ck_bots_games_played_non_negative" in constraints
    assert "ck_bots_wins_non_negative" in constraints
    assert "ck_bots_losses_non_negative" in constraints
    assert "ck_bots_draws_non_negative" in constraints
    assert "ck_bots_record_matches_games_played" in constraints
    assert "ck_bots_description_max_length" in constraints

    indexes = {index.name: index for index in Bot.__table__.indexes}
    assert indexes["ix_bots_game_id_rating"].columns.keys() == ["game_id", "rating"]
    assert "ix_bots_id" not in indexes


def test_bot_submission_model_declares_expected_columns_and_constraints():
    assert set(BotSubmission.__table__.columns.keys()) == EXPECTED_BOT_SUBMISSION_COLUMNS

    assert BotSubmission.__table__.c.bot_id.nullable is False
    assert BotSubmission.__table__.c.version.nullable is False
    assert BotSubmission.__table__.c.language.nullable is False
    assert BotSubmission.__table__.c.source_code.nullable is False
    assert BotSubmission.__table__.c.created_at.nullable is False
    assert {
        foreign_key.target_fullname
        for foreign_key in BotSubmission.__table__.c.bot_id.foreign_keys
    } == {"bots.id"}

    constraints = {
        constraint.name: constraint for constraint in BotSubmission.__table__.constraints
    }
    assert constraints["uq_bot_submissions_bot_id_version"].columns.keys() == [
        "bot_id",
        "version",
    ]


def test_bot_table_applies_defaults_and_unique_names_within_game():
    engine = sa.create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    Bot.__table__.create(engine)

    with Session(engine) as session:
        bot = Bot(name="random", game_id="tictactoe")
        same_name_different_game = Bot(
            name="random",
            game_id="connect-four",
        )
        session.add_all([bot, same_name_different_game])
        session.commit()

        assert bot.rating == 1200
        assert bot.games_played == 0
        assert bot.wins == 0
        assert bot.losses == 0
        assert bot.draws == 0

        session.add(Bot(name="random", game_id="tictactoe"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_bot_submission_table_rejects_duplicate_bot_versions():
    engine = sa.create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    Bot.__table__.create(engine)
    BotSubmission.__table__.create(engine)

    with Session(engine) as session:
        bot = Bot(name="random", game_id="tictactoe")
        session.add(bot)
        session.flush()

        session.add_all(
            [
                BotSubmission(
                    bot_id=bot.id,
                    version=1,
                    language="python",
                    source_code="print(1)",
                ),
                BotSubmission(
                    bot_id=bot.id,
                    version=1,
                    language="python",
                    source_code="print(2)",
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_user_model_declares_expected_columns_and_constraints():
    assert set(User.__table__.columns.keys()) == EXPECTED_USER_COLUMNS

    assert User.__table__.c.email.nullable is False
    assert User.__table__.c.email.type.length == 320
    assert User.__table__.c.username.nullable is False
    assert User.__table__.c.username.type.length == 80
    assert User.__table__.c.description.nullable is False
    assert User.__table__.c.password_hash.nullable is False
    assert User.__table__.c.password_hash.type.length == 255
    assert User.__table__.c.created_at.nullable is False

    constraints = {constraint.name: constraint for constraint in User.__table__.constraints}
    assert constraints["uq_users_email"].columns.keys() == ["email"]
    assert constraints["uq_users_username"].columns.keys() == ["username"]
    assert "ck_users_email_max_length" in constraints
    assert "ck_users_email_format" in constraints
    assert "ck_users_username_min_length" in constraints
    assert "ck_users_username_max_length" in constraints
    assert "ck_users_description_max_length" in constraints

    assert not User.__table__.indexes


def test_session_model_declares_expected_columns_and_cascade_foreign_key():
    assert set(AuthSession.__table__.columns.keys()) == EXPECTED_SESSION_COLUMNS

    assert AuthSession.__table__.c.id.nullable is False
    assert AuthSession.__table__.c.id.type.length == 128
    assert AuthSession.__table__.c.user_id.nullable is False
    assert AuthSession.__table__.c.created_at.nullable is False
    assert AuthSession.__table__.c.expires_at.nullable is False

    foreign_keys = list(AuthSession.__table__.c.user_id.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "users.id"
    assert foreign_keys[0].ondelete == "CASCADE"

    indexes = {index.name: index for index in AuthSession.__table__.indexes}
    assert indexes["ix_sessions_user_id"].columns.keys() == ["user_id"]


def test_user_table_enforces_unique_email_and_email_format():
    engine = sa.create_engine("sqlite:///:memory:")
    User.__table__.create(engine)

    with Session(engine) as session:
        session.add(User(username="player", email="player@example.com", password_hash="hash"))
        session.commit()

        session.add(User(username="player", email="player@example.com", password_hash="other-hash"))
        with pytest.raises(IntegrityError):
            session.commit()

    with Session(engine) as session:
        session.add(User(username="other-player", email="first@example.com", password_hash="hash"))
        session.commit()

        session.add(User(username="other-player", email="second@example.com", password_hash="hash"))
        with pytest.raises(IntegrityError):
            session.commit()

    with Session(engine) as session:
        session.add(User(username="player", email="not-an-email", password_hash="hash"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_deleting_user_cascades_to_sessions():
    engine = sa.create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    User.__table__.create(engine)
    AuthSession.__table__.create(engine)

    with Session(engine) as session:
        user = User(username="player", email="player@example.com", password_hash="hash")
        user.sessions.append(
            AuthSession(
                id="opaque-session-token",
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        )
        session.add(user)
        session.commit()

        session.delete(user)
        session.commit()

        assert session.query(AuthSession).count() == 0


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

    indexes = {index.name: index for index in Match.__table__.indexes}
    assert indexes["ix_matches_game_id"].columns.keys() == ["game_id"]
    assert "ix_matches_id" not in indexes


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

    indexes = {index.name: index for index in Move.__table__.indexes}
    assert "ix_moves_id" not in indexes


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

        assert set(bot_columns) == EXPECTED_BASELINE_BOT_COLUMNS
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


def test_auth_migration_creates_users_and_sessions_schema(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()

        inspector = sa.inspect(connection)
        user_columns = {column["name"]: column for column in inspector.get_columns("users")}
        session_columns = {
            column["name"]: column for column in inspector.get_columns("sessions")
        }
        user_unique_constraints = inspector.get_unique_constraints("users")
        user_check_constraints = inspector.get_check_constraints("users")
        session_foreign_keys = inspector.get_foreign_keys("sessions")
        session_indexes = inspector.get_indexes("sessions")

        assert set(user_columns) == EXPECTED_AUTH_MIGRATION_USER_COLUMNS
        assert set(session_columns) == EXPECTED_SESSION_COLUMNS

        assert user_columns["email"]["nullable"] is False
        assert user_columns["email"]["type"].length == 320
        assert user_columns["password_hash"]["nullable"] is False
        assert user_columns["password_hash"]["type"].length == 255
        assert user_columns["created_at"]["nullable"] is False
        assert inspector.get_pk_constraint("users")["constrained_columns"] == ["id"]
        assert any(
            constraint["column_names"] == ["email"]
            for constraint in user_unique_constraints
        )
        assert {
            constraint["name"] for constraint in user_check_constraints
        } >= {"ck_users_email_format", "ck_users_email_max_length"}

        assert session_columns["id"]["nullable"] is False
        assert session_columns["id"]["type"].length == 128
        assert session_columns["user_id"]["nullable"] is False
        assert session_columns["created_at"]["nullable"] is False
        assert session_columns["expires_at"]["nullable"] is False
        assert inspector.get_pk_constraint("sessions")["constrained_columns"] == ["id"]
        assert any(
            foreign_key["constrained_columns"] == ["user_id"]
            and foreign_key["referred_table"] == "users"
            and foreign_key["referred_columns"] == ["id"]
            and foreign_key["options"].get("ondelete") == "CASCADE"
            for foreign_key in session_foreign_keys
        )
        assert any(
            index["column_names"] == ["user_id"]
            for index in session_indexes
        )


def test_username_migration_adds_unique_required_username(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)
        monkeypatch.setattr(bot_owner_schema, "op", operations)
        monkeypatch.setattr(username_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()
        bot_owner_schema.upgrade()
        connection.execute(
            sa.text(
                "INSERT INTO users (email, password_hash) "
                "VALUES ('player@example.com', 'hash')"
            )
        )
        username_schema.upgrade()

        inspector = sa.inspect(connection)
        user_columns = {column["name"]: column for column in inspector.get_columns("users")}
        user_unique_constraints = inspector.get_unique_constraints("users")
        user_check_constraints = inspector.get_check_constraints("users")
        rows = connection.execute(sa.text("SELECT email, username FROM users")).all()

        assert set(user_columns) == EXPECTED_USERNAME_MIGRATION_USER_COLUMNS
        assert user_columns["username"]["nullable"] is False
        assert user_columns["username"]["type"].length == 80
        assert rows == [("player@example.com", "player@example.com")]
        assert any(
            constraint["column_names"] == ["username"]
            for constraint in user_unique_constraints
        )
        assert {
            constraint["name"] for constraint in user_check_constraints
        } >= {"ck_users_username_min_length", "ck_users_username_max_length"}


def test_cleanup_indexes_migration_removes_redundant_pk_indexes(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)
        monkeypatch.setattr(bot_owner_schema, "op", operations)
        monkeypatch.setattr(username_schema, "op", operations)
        monkeypatch.setattr(cleanup_indexes_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()
        bot_owner_schema.upgrade()
        username_schema.upgrade()
        cleanup_indexes_schema.upgrade()

        inspector = sa.inspect(connection)
        bot_indexes = {index["name"]: index for index in inspector.get_indexes("bots")}
        match_indexes = {
            index["name"]: index for index in inspector.get_indexes("matches")
        }
        move_indexes = {index["name"]: index for index in inspector.get_indexes("moves")}
        user_indexes = {index["name"]: index for index in inspector.get_indexes("users")}

        assert "ix_bots_id" not in bot_indexes
        assert "ix_matches_id" not in match_indexes
        assert "ix_moves_id" not in move_indexes
        assert "ix_users_id" not in user_indexes
        assert match_indexes["ix_matches_game_id"]["column_names"] == ["game_id"]
        assert bot_indexes["ix_bots_game_id_rating"]["column_names"] == [
            "game_id",
            "rating",
        ]
        assert move_indexes["ix_moves_match_id"]["column_names"] == ["match_id"]


def test_bot_owner_migration_replaces_created_by_with_nullable_owner_id(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)
        monkeypatch.setattr(bot_owner_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()
        bot_owner_schema.upgrade()

        inspector = sa.inspect(connection)
        bot_columns = {column["name"]: column for column in inspector.get_columns("bots")}
        bot_foreign_keys = inspector.get_foreign_keys("bots")

        assert set(bot_columns) == EXPECTED_BOT_OWNER_MIGRATION_BOT_COLUMNS
        assert bot_columns["owner_id"]["nullable"] is True
        assert any(
            foreign_key["constrained_columns"] == ["owner_id"]
            and foreign_key["referred_table"] == "users"
            and foreign_key["referred_columns"] == ["id"]
            for foreign_key in bot_foreign_keys
        )


def test_bot_submissions_migration_adds_submissions_and_active_pointer(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)
        monkeypatch.setattr(bot_owner_schema, "op", operations)
        monkeypatch.setattr(username_schema, "op", operations)
        monkeypatch.setattr(cleanup_indexes_schema, "op", operations)
        monkeypatch.setattr(bot_submissions_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()
        bot_owner_schema.upgrade()
        username_schema.upgrade()
        cleanup_indexes_schema.upgrade()
        bot_submissions_schema.upgrade()

        inspector = sa.inspect(connection)
        bot_columns = {column["name"]: column for column in inspector.get_columns("bots")}
        submission_columns = {
            column["name"]: column
            for column in inspector.get_columns("bot_submissions")
        }
        bot_foreign_keys = inspector.get_foreign_keys("bots")
        submission_foreign_keys = inspector.get_foreign_keys("bot_submissions")
        submission_unique_constraints = inspector.get_unique_constraints(
            "bot_submissions"
        )

        assert set(bot_columns) == EXPECTED_BOT_SUBMISSIONS_MIGRATION_BOT_COLUMNS
        assert bot_columns["active_submission_id"]["nullable"] is True
        assert set(submission_columns) == EXPECTED_BOT_SUBMISSION_COLUMNS
        assert submission_columns["bot_id"]["nullable"] is False
        assert submission_columns["version"]["nullable"] is False
        assert submission_columns["language"]["nullable"] is False
        assert submission_columns["source_code"]["nullable"] is False
        assert any(
            foreign_key["constrained_columns"] == ["active_submission_id"]
            and foreign_key["referred_table"] == "bot_submissions"
            and foreign_key["referred_columns"] == ["id"]
            for foreign_key in bot_foreign_keys
        )
        assert any(
            foreign_key["constrained_columns"] == ["bot_id"]
            and foreign_key["referred_table"] == "bots"
            and foreign_key["referred_columns"] == ["id"]
            for foreign_key in submission_foreign_keys
        )
        assert any(
            constraint["column_names"] == ["bot_id", "version"]
            for constraint in submission_unique_constraints
        )


def test_descriptions_migration_adds_user_and_bot_descriptions(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)
        monkeypatch.setattr(bot_owner_schema, "op", operations)
        monkeypatch.setattr(username_schema, "op", operations)
        monkeypatch.setattr(cleanup_indexes_schema, "op", operations)
        monkeypatch.setattr(bot_submissions_schema, "op", operations)
        monkeypatch.setattr(descriptions_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()
        bot_owner_schema.upgrade()
        username_schema.upgrade()
        cleanup_indexes_schema.upgrade()
        bot_submissions_schema.upgrade()
        descriptions_schema.upgrade()

        inspector = sa.inspect(connection)
        user_columns = {column["name"]: column for column in inspector.get_columns("users")}
        bot_columns = {column["name"]: column for column in inspector.get_columns("bots")}
        user_check_constraints = inspector.get_check_constraints("users")
        bot_check_constraints = inspector.get_check_constraints("bots")

        assert set(user_columns) == EXPECTED_USER_COLUMNS
        assert user_columns["description"]["nullable"] is False
        assert reflected_default_value(user_columns["description"]) == ""
        assert set(bot_columns) == EXPECTED_BOT_COLUMNS
        assert bot_columns["description"]["nullable"] is False
        assert reflected_default_value(bot_columns["description"]) == ""
        assert "ck_users_description_max_length" in {
            constraint["name"] for constraint in user_check_constraints
        }
        assert "ck_bots_description_max_length" in {
            constraint["name"] for constraint in bot_check_constraints
        }


def test_auth_migration_downgrade_drops_users_and_sessions(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(baseline_schema, "op", operations)
        monkeypatch.setattr(auth_schema, "op", operations)

        baseline_schema.upgrade()
        auth_schema.upgrade()
        auth_schema.downgrade()

        inspector = sa.inspect(connection)
        assert "users" not in inspector.get_table_names()
        assert "sessions" not in inspector.get_table_names()
        assert {"bots", "matches", "moves"} <= set(inspector.get_table_names())


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
