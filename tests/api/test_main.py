from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import struct

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import hash_password, verify_password
import api.bot_sandbox as bot_sandbox
from api.database import Base, get_db
from api.models import (
    AuthRateLimitEvent,
    AuthToken,
    Bot,
    BotSubmission,
    Match,
    MatchJob,
    MatchJobMove,
    Move,
    Session as AuthSession,
    User,
)
from api.schemas import UserRegisterRequest
import api.main as api_main


client = TestClient(api_main.app)


class DummySession:
    def __init__(self):
        self.closed = False
        self.added = []
        self.commits = 0
        self.refreshed = []

    def close(self):
        self.closed = True

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.commits += 1
        self.added[-1].id = 123

    def refresh(self, record):
        self.refreshed.append(record)


@pytest.fixture(autouse=True)
def override_database_dependency(monkeypatch):
    client.cookies.clear()
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    session = DummySession()

    def fake_get_db():
        try:
            yield session
        finally:
            session.close()

    api_main.app.dependency_overrides[get_db] = fake_get_db
    yield session
    api_main.app.dependency_overrides.clear()


def valid_match_request():
    return {
        "game": "tictactoe",
        "players": [
            {"bot": "randombot1"},
            {"bot": "randombot2"},
        ],
    }


def valid_connectfour_match_request():
    return {
        "game": "connect-four",
        "players": [
            {"bot": "randombot1"},
            {"bot": "randombot2"},
        ],
    }


def valid_bot_source():
    return "def choose_move(board):\n    return 0\n"


def valid_bot_executable(payload=b"\x90"):
    import struct
    data = bytearray(120 + len(payload))
    data[:16] = b"\x7fELF\x02\x01\x01" + b"\x00" * 9
    struct.pack_into("<HHIQQQIHHHHHH", data, 16, 2, 62, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, len(data), len(data), 4096)
    data[120:] = payload
    return bytes(data)


def bot_multipart(name="custom", game_id="tictactoe", executable=None, filename="player"):
    return {
        "data": {"game_id": game_id, "name": name},
        "files": {
            "executable": (
                filename,
                executable if executable is not None else valid_bot_executable(),
                "application/octet-stream",
            )
        },
    }


def test_score_for_bot_one_or_error_maps_unknown_winner_to_api_error():
    with pytest.raises(HTTPException) as error:
        api_main.score_for_bot_one_or_error(
            winner_bot_id=3,
            bot_one_id=1,
            bot_two_id=2,
        )

    assert error.value.status_code == 500
    assert error.value.detail == {
        "code": "unknown_winner_bot",
        "message": "Unknown winner bot: 3",
    }


def test_build_bot_sandbox_creates_locked_down_docker_command(monkeypatch):
    bot = Bot(id=42, name="sandboxed", game_id="tictactoe")
    submission = BotSubmission(
        id=7,
        bot_id=42,
        version=1,
        executable=valid_bot_executable(), executable_size=len(valid_bot_executable()), executable_digest="0" * 64,
    )
    bot.active_submission_id = submission.id
    bot.active_submission = submission
    monkeypatch.setenv("DOCKER_BINARY", "podman")
    monkeypatch.setenv("BOT_SANDBOX_IMAGE", "custom-runner:latest")
    monkeypatch.setenv("BOT_SANDBOX_MEMORY_LIMIT", "64m")
    monkeypatch.setenv("BOT_SANDBOX_CPU_LIMIT", "0.25")
    monkeypatch.setenv("BOT_SANDBOX_PIDS_LIMIT", "32")
    monkeypatch.setenv("BOT_SANDBOX_TMPFS_SIZE", "8m")

    sandbox = api_main.build_bot_sandbox(bot)

    try:
        command = sandbox.command
        assert command[:3] == ["podman", "run", "--rm"]
        assert "-i" in command
        assert "--init" in command
        assert command[command.index("--network") + 1] == "none"
        assert command[command.index("--cap-drop") + 1] == "ALL"
        assert command[command.index("--security-opt") + 1] == "no-new-privileges"
        assert "--read-only" in command
        assert command[command.index("--tmpfs") + 1] == (
            "/tmp:rw,noexec,nosuid,nodev,size=8m"
        )
        assert command[command.index("--memory") + 1] == "64m"
        assert command[command.index("--cpus") + 1] == "0.25"
        assert command[command.index("--pids-limit") + 1] == "32"
        assert command[command.index("--name") + 1] == sandbox.container_name
        assert command[-2:] == ["custom-runner:latest", "/bot/player"]
        assert command[command.index("--mount") + 1] == (
            f"type=bind,src={sandbox.source_path},dst=/bot/player,readonly"
        )
        assert sandbox.container_name.startswith("ahinarena-bot-42-")
        assert sandbox.source_path.read_bytes() == valid_bot_executable()
    finally:
        sandbox.cleanup()


def test_build_bot_sandbox_uses_fixed_executable_path():
    bot = Bot(id=42, name="sandboxed", game_id="tictactoe")
    submission = BotSubmission(
        id=7,
        bot_id=42,
        version=1,
        executable=valid_bot_executable(), executable_size=len(valid_bot_executable()), executable_digest="0" * 64,
    )
    bot.active_submission_id = submission.id
    bot.active_submission = submission

    sandbox = api_main.build_bot_sandbox(bot)

    try:
        command = sandbox.command
        assert sandbox.source_path.name == "player"
        assert command[command.index("--mount") + 1] == (
            f"type=bind,src={sandbox.source_path},dst=/bot/player,readonly"
        )
        assert command[-2:] == ["ahinarena-bot-runner:latest", "/bot/player"]
        assert sandbox.source_path.read_bytes() == valid_bot_executable()
    finally:
        sandbox.cleanup()


def test_build_bot_sandbox_raises_existing_no_submission_error():
    bot = Bot(id=42, name="empty", game_id="tictactoe")

    with pytest.raises(ValueError, match="Bot has no active submission: empty"):
        api_main.build_bot_sandbox(bot)


def test_cleanup_bot_sandbox_force_removes_container_and_deletes_temp_file(
    monkeypatch,
):
    bot = Bot(id=42, name="sandboxed", game_id="tictactoe")
    submission = BotSubmission(
        id=7,
        bot_id=42,
        version=1,
        executable=valid_bot_executable(), executable_size=len(valid_bot_executable()), executable_digest="0" * 64,
    )
    bot.active_submission_id = submission.id
    bot.active_submission = submission
    sandbox = api_main.build_bot_sandbox(bot)
    calls = []

    def fake_run(command, stdout, stderr, check):
        calls.append(
            {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "check": check,
            }
        )
        raise OSError("docker unavailable")

    monkeypatch.setattr(bot_sandbox.subprocess, "run", fake_run)

    sandbox.cleanup()

    assert calls[0]["command"] == ["docker", "rm", "--force", sandbox.container_name]
    assert calls[0]["check"] is False
    assert not sandbox.source_path.exists()
    assert not sandbox.temp_dir.exists()


def seed_bot(session, *, name="random", game_id="tictactoe"):
    bot = Bot(name=name, game_id=game_id)
    session.add(bot)
    session.commit()
    seed_submission(session, bot)
    return bot


def seed_submission(session, bot, *, source_code="print('ok')\n", version=1):
    executable = valid_bot_executable(source_code.encode())
    submission = BotSubmission(
        bot_id=bot.id,
        version=version,
        executable=executable,
        executable_size=len(executable),
        executable_digest="0" * 64,
    )
    session.add(submission)
    session.flush()
    bot.active_submission_id = submission.id
    bot.latest_submission_version = max(bot.latest_submission_version, version)
    session.commit()
    session.refresh(bot)
    return submission


def mounted_source_path(command):
    mount_index = command.index("--mount") + 1
    mount = command[mount_index]
    parts = dict(
        part.split("=", maxsplit=1)
        for part in mount.split(",")
        if "=" in part
    )
    return Path(parts["src"])


def login_user(session, *, email="player@example.com", password="correct"):
    user = User(
        username=email.split("@", maxsplit=1)[0],
        email=email,
        password_hash=hash_password(password),
        is_email_verified=True,
    )
    session.add(user)
    session.commit()

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200

    return user


def authenticate_request_dependency():
    api_main.app.dependency_overrides[api_main.get_current_user] = lambda: User(
        id=1,
        username="player",
        email="player@example.com",
        password_hash="unused",
    )


@pytest.fixture
def sqlite_database_dependency():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    session = testing_session()

    def fake_get_db():
        try:
            yield session
        finally:
            pass

    api_main.app.dependency_overrides[get_db] = fake_get_db
    yield session
    session.close()
    api_main.app.dependency_overrides.clear()


def make_persisted_match(
    *,
    game_id="tictactoe",
    bot_one_id=1,
    bot_two_id=2,
    winner_bot_id=1,
    result_reason="win",
    created_at=None,
    completed_at=None,
    moves=None,
    bot_one_rating_before=1200,
    bot_two_rating_before=1200,
    bot_one_rating_after=1216,
    bot_two_rating_after=1184,
    bot_one_rating_delta=16,
    bot_two_rating_delta=-16,
):
    return Match(
        game_id=game_id,
        bot_one_id=bot_one_id,
        bot_two_id=bot_two_id,
        bot_one_rating_before=bot_one_rating_before,
        bot_two_rating_before=bot_two_rating_before,
        bot_one_rating_after=bot_one_rating_after,
        bot_two_rating_after=bot_two_rating_after,
        bot_one_rating_delta=bot_one_rating_delta,
        bot_two_rating_delta=bot_two_rating_delta,
        winner_bot_id=winner_bot_id,
        result_reason=result_reason,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=completed_at or datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        moves=moves or [],
    )


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_password_hash_verifies_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash) is True


def test_password_hash_rejects_wrong_password():
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("wrong password", password_hash) is False


def test_register_user_creates_public_user_response(sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": "Player@Example.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"user"}
    assert body["user"]["email"] == "player@example.com"
    assert body["user"]["username"] == "PlayerOne"
    assert body["user"]["description"] == ""
    assert body["user"]["is_email_verified"] is False
    assert body["user"]["created_at"]

    user = sqlite_database_dependency.query(User).one()
    assert user.email == "player@example.com"
    assert user.username == "PlayerOne"
    assert user.password_hash != "Super-secret1"
    assert verify_password("Super-secret1", user.password_hash) is True
    assert user.is_email_verified is False
    token = sqlite_database_dependency.query(AuthToken).one()
    assert token.user_id == user.id
    assert token.purpose == "email_verification"
    assert token.used_at is None


def test_register_user_sends_verification_email_when_email_delivery_is_configured(
    monkeypatch,
    sqlite_database_dependency,
):
    sent_messages = []

    def fake_send_verification_email(**message):
        sent_messages.append(message)

    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "AhinArena <noreply@example.com>")
    monkeypatch.setenv("FRONTEND_URL", "https://arena.example.com")
    monkeypatch.setattr(api_main, "send_verification_email", fake_send_verification_email)

    response = client.post(
        "/auth/register",
        json={
            "email": "Player@Example.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )

    assert response.status_code == 201
    assert set(response.json().keys()) == {"user"}
    token = sqlite_database_dependency.query(AuthToken).one()
    assert sent_messages == [
        {
            "to": "player@example.com",
            "username": "PlayerOne",
            "verification_url": f"https://arena.example.com/verify-email?token={token.token}",
        }
    ]


def test_register_user_skips_verification_email_for_addresses_starting_with_a(
    monkeypatch,
    sqlite_database_dependency,
):
    sent_messages = []

    def fake_send_verification_email(**message):
        sent_messages.append(message)

    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "AhinArena <noreply@example.com>")
    monkeypatch.setattr(api_main, "send_verification_email", fake_send_verification_email)

    response = client.post(
        "/auth/register",
        json={
            "email": "aaa@gmail.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )

    assert response.status_code == 201
    assert set(response.json().keys()) == {"user"}
    token = sqlite_database_dependency.query(AuthToken).one()
    assert token.purpose == "email_verification"
    assert token.used_at is None
    assert sent_messages == []


def test_resend_verification_email_reissues_token(sqlite_database_dependency):
    register_response = client.post(
        "/auth/register",
        json={
            "email": "Player@Example.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )
    original_token = sqlite_database_dependency.query(AuthToken).one().token

    response = client.post(
        "/auth/verify-email/resend",
        json={"email": "Player@Example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {}

    tokens = sqlite_database_dependency.query(AuthToken).order_by(AuthToken.id).all()
    assert len(tokens) == 2
    assert tokens[0].used_at is not None
    assert tokens[1].used_at is None
    assert tokens[1].token != original_token


def test_resend_verification_email_sends_email_when_delivery_is_configured(
    monkeypatch,
    sqlite_database_dependency,
):
    sent_messages = []

    def fake_send_verification_email(**message):
        sent_messages.append(message)

    register_response = client.post(
        "/auth/register",
        json={
            "email": "Player@Example.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )
    assert register_response.status_code == 201

    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "AhinArena <noreply@example.com>")
    monkeypatch.setenv("FRONTEND_URL", "https://arena.example.com")
    monkeypatch.setattr(api_main, "send_verification_email", fake_send_verification_email)

    response = client.post(
        "/auth/verify-email/resend",
        json={"email": "Player@Example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {}
    token = sqlite_database_dependency.query(AuthToken).order_by(AuthToken.id.desc()).first()
    assert sent_messages == [
        {
            "to": "player@example.com",
            "username": "PlayerOne",
            "verification_url": f"https://arena.example.com/verify-email?token={token.token}",
        }
    ]


def test_resend_verification_email_skips_email_for_addresses_starting_with_a(
    monkeypatch,
    sqlite_database_dependency,
):
    sent_messages = []

    def fake_send_verification_email(**message):
        sent_messages.append(message)

    register_response = client.post(
        "/auth/register",
        json={
            "email": "aaa@gmail.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )
    assert register_response.status_code == 201

    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "AhinArena <noreply@example.com>")
    monkeypatch.setattr(api_main, "send_verification_email", fake_send_verification_email)

    response = client.post(
        "/auth/verify-email/resend",
        json={"email": "aaa@gmail.com"},
    )

    assert response.status_code == 200
    assert response.json() == {}
    tokens = sqlite_database_dependency.query(AuthToken).order_by(AuthToken.id).all()
    assert len(tokens) == 2
    assert tokens[0].used_at is not None
    assert tokens[1].used_at is None
    assert sent_messages == []


def test_resend_verification_email_is_noop_for_verified_user(sqlite_database_dependency):
    register_response = client.post(
        "/auth/register",
        json={
            "email": "Player@Example.com",
            "username": "PlayerOne",
            "password": "Super-secret1",
        },
    )
    token = sqlite_database_dependency.query(AuthToken).one().token
    verify_response = client.post("/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 200

    response = client.post(
        "/auth/verify-email/resend",
        json={"email": "Player@Example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {}
    assert sqlite_database_dependency.query(AuthToken).count() == 1


def test_register_user_returns_422_for_weak_password(sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": "player@example.com",
            "username": "player",
            "password": "password",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


def test_user_register_request_normalizes_email_and_username():
    request = UserRegisterRequest(
        email="  Player@Example.com  ",
        username="  PlayerOne  ",
        password="Super-secret1",
    )

    assert request.email == "player@example.com"
    assert request.username == "PlayerOne"


def test_register_user_returns_409_for_duplicate_email(sqlite_database_dependency):
    sqlite_database_dependency.add(
        User(username="player", email="player@example.com", password_hash=hash_password("old-password"))
    )
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/register",
        json={
            "email": "PLAYER@example.com",
            "username": "other-player",
            "password": "New-password1",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "email_already_registered",
            "message": "Email is already registered.",
        }
    }
    assert sqlite_database_dependency.query(User).count() == 1


def test_register_user_returns_409_for_duplicate_username(sqlite_database_dependency):
    sqlite_database_dependency.add(
        User(
            username="player",
            email="player@example.com",
            password_hash=hash_password("old-password"),
        )
    )
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "username": "player",
            "password": "New-password1",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "username_already_taken",
            "message": "Username is already taken.",
        }
    }
    assert sqlite_database_dependency.query(User).count() == 1


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",
        "player@example",
        "@example.com",
        "player@example.",
        "player..example",
        "玩家@example.com",
        "player@例子.com",
    ],
)
def test_register_user_returns_422_for_invalid_email(email, sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "username": "player",
            "password": "New-password1",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


def test_register_user_returns_422_for_overlong_email(sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": f"{'a' * 243}@example.com",
            "username": "player",
            "password": "New-password1",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


@pytest.mark.parametrize("username", ["", "   ", "ab", "a" * 21, "player one", "玩家", "player!"])
def test_register_user_returns_422_for_invalid_username(username, sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": "player@example.com",
            "username": username,
            "password": "New-password1",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


@pytest.mark.parametrize("password", ["short", "a" * 73])
def test_register_user_returns_422_for_invalid_password(password, sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": "player@example.com",
            "username": "player",
            "password": password,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


def test_cors_allowed_origins_default_to_local_react_dev_servers(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert api_main.get_cors_allowed_origins() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_cors_allowed_origins_are_configurable(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://arena.example.com, http://localhost:4173, ",
    )

    assert api_main.get_cors_allowed_origins() == [
        "https://arena.example.com",
        "http://localhost:4173",
    ]


def test_cors_preflight_allows_local_frontend_origin(sqlite_database_dependency):
    response = client.options(
        "/matches",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_cors_allowed_origins_rejects_wildcard_when_credentials_are_enabled(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(ValueError, match="cannot include"):
        api_main.get_cors_allowed_origins()


def clear_deploy_environment(monkeypatch):
    monkeypatch.delenv(api_main.DEPLOY_ENVIRONMENT_ENV_VAR, raising=False)
    monkeypatch.delenv(api_main.REQUIRE_SECURE_COOKIES_ENV_VAR, raising=False)
    for env_var in api_main.LEGACY_DEPLOY_ENVIRONMENT_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_auth_cookie_secure_flag_uses_canonical_production_env(monkeypatch):
    clear_deploy_environment(monkeypatch)
    monkeypatch.setenv(api_main.DEPLOY_ENVIRONMENT_ENV_VAR, "production")

    assert api_main.should_secure_auth_cookie() is True


def test_auth_cookie_secure_flag_defaults_to_false_when_environment_unset(monkeypatch):
    clear_deploy_environment(monkeypatch)

    assert api_main.should_secure_auth_cookie() is False


def test_login_sets_secure_cookie_with_canonical_production_env(
    monkeypatch,
    sqlite_database_dependency,
):
    clear_deploy_environment(monkeypatch)
    monkeypatch.setenv(api_main.DEPLOY_ENVIRONMENT_ENV_VAR, "production")
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("correct"),
        is_email_verified=True,
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "correct"},
    )

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert f"{api_main.SESSION_COOKIE_NAME}=" in set_cookie
    assert "Secure" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_auth_cookie_startup_check_warns_when_canonical_env_is_unset(
    caplog,
    monkeypatch,
):
    clear_deploy_environment(monkeypatch)

    api_main.validate_auth_cookie_security()

    assert api_main.DEPLOY_ENVIRONMENT_ENV_VAR in caplog.text
    assert "auth session cookies will be issued without Secure" in caplog.text


def test_auth_cookie_startup_check_requires_secure_cookie_when_enabled(monkeypatch):
    clear_deploy_environment(monkeypatch)
    monkeypatch.setenv(api_main.REQUIRE_SECURE_COOKIES_ENV_VAR, "true")

    with pytest.raises(RuntimeError, match="auth session cookies would be issued without Secure"):
        api_main.validate_auth_cookie_security()


def test_login_sets_http_only_lax_cookie(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("correct"),
        is_email_verified=True,
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/login",
        json={"email": "PLAYER@example.com", "password": "correct"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "email", "username", "description", "is_email_verified", "created_at"}
    assert body["email"] == "player@example.com"
    assert body["username"] == "player"
    assert body["description"] == ""
    assert sqlite_database_dependency.query(AuthSession).count() == 1

    set_cookie = response.headers["set-cookie"]
    assert f"{api_main.SESSION_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_login_accepts_username(sqlite_database_dependency):
    user = User(
        username="PlayerOne",
        email="player@example.com",
        password_hash=hash_password("correct"),
        is_email_verified=True,
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/login",
        json={"login": "PlayerOne", "password": "correct"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "player@example.com"
    assert body["username"] == "PlayerOne"
    assert sqlite_database_dependency.query(AuthSession).count() == 1
    assert f"{api_main.SESSION_COOKIE_NAME}=" in response.headers["set-cookie"]


def test_login_rejects_unverified_email(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("correct"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "correct"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "email_not_verified",
            "message": "Please verify your email before logging in.",
        }
    }
    assert sqlite_database_dependency.query(AuthSession).count() == 0


def test_verify_email_marks_user_verified(sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": "player@example.com",
            "username": "player",
            "password": "Strong-pass1",
        },
    )
    token = sqlite_database_dependency.query(AuthToken).one().token

    verify_response = client.post("/auth/verify-email", json={"token": token})

    assert verify_response.status_code == 200
    assert verify_response.json()["is_email_verified"] is True
    user = sqlite_database_dependency.query(User).one()
    auth_token = sqlite_database_dependency.query(AuthToken).one()
    assert user.is_email_verified is True
    assert auth_token.used_at is not None


def test_password_reset_confirm_updates_password_and_verifies_user(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("old-password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    reset_response = client.post("/auth/password-reset", json={"email": "player@example.com"})
    token = reset_response.json()["reset_token"]

    confirm_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "New-password1"},
    )

    assert confirm_response.status_code == 200
    sqlite_database_dependency.refresh(user)
    assert user.is_email_verified is True
    assert verify_password("New-password1", user.password_hash) is True
    assert verify_password("old-password", user.password_hash) is False


def test_password_reset_validate_accepts_active_token(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("old-password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    reset_response = client.post("/auth/password-reset", json={"email": "player@example.com"})
    token = reset_response.json()["reset_token"]

    validate_response = client.post("/auth/password-reset/validate", json={"token": token})

    assert validate_response.status_code == 204


def test_password_reset_validate_rejects_used_token(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("old-password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    reset_response = client.post("/auth/password-reset", json={"email": "player@example.com"})
    token = reset_response.json()["reset_token"]
    client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "New-password1"},
    )

    validate_response = client.post("/auth/password-reset/validate", json={"token": token})

    assert validate_response.status_code == 400
    assert validate_response.json()["error"]["code"] == "invalid_or_expired_token"


def test_password_reset_sends_email_when_email_delivery_is_configured(
    monkeypatch,
    sqlite_database_dependency,
):
    sent_messages = []
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("old-password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    def fake_send_password_reset_email(**message):
        sent_messages.append(message)

    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "AhinArena <noreply@example.com>")
    monkeypatch.setenv("FRONTEND_URL", "https://arena.example.com")
    monkeypatch.setattr(api_main, "send_password_reset_email", fake_send_password_reset_email)

    response = client.post("/auth/password-reset", json={"email": "player@example.com"})

    assert response.status_code == 200
    assert response.json() == {"reset_token": None, "reset_url": None}
    token = sqlite_database_dependency.query(AuthToken).one()
    assert sent_messages == [
        {
            "to": "player@example.com",
            "username": "player",
            "reset_url": f"https://arena.example.com/reset-password?token={token.token}",
        }
    ]


def test_session_cookie_is_secure_in_production(monkeypatch):
    clear_deploy_environment(monkeypatch)
    monkeypatch.setenv(api_main.DEPLOY_ENVIRONMENT_ENV_VAR, "production")
    response = Response()

    api_main.set_session_cookie(
        response,
        "session-id",
        datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("missing@example.com", "correct"),
        ("player@example.com", "wrong"),
    ],
)
def test_login_returns_same_401_for_wrong_email_or_password(
    sqlite_database_dependency,
    email,
    password,
):
    sqlite_database_dependency.add(
        User(
            username="player",
            email="player@example.com",
            password_hash=hash_password("correct"),
            is_email_verified=True,
        )
    )
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "invalid_credentials",
            "message": "Invalid credentials.",
        }
    }


def test_login_rate_limit_counts_failed_attempts_by_account(sqlite_database_dependency):
    sqlite_database_dependency.add(
        User(
            username="player",
            email="player@example.com",
            password_hash=hash_password("correct"),
            is_email_verified=True,
        )
    )
    sqlite_database_dependency.commit()

    for _ in range(api_main.AUTH_RATE_LIMITS["login"]["account"][0]):
        response = client.post(
            "/auth/login",
            json={"email": "PLAYER@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "correct"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert sqlite_database_dependency.query(AuthSession).count() == 0
    assert (
        sqlite_database_dependency.query(AuthRateLimitEvent)
        .filter(AuthRateLimitEvent.bucket == "login:account")
        .count()
        == api_main.AUTH_RATE_LIMITS["login"]["account"][0]
    )


def test_login_rate_limit_counts_failed_attempts_by_ip(sqlite_database_dependency):
    for index in range(api_main.AUTH_RATE_LIMITS["login"]["ip"][0]):
        response = client.post(
            "/auth/login",
            json={"email": f"missing-{index}@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"email": "another-missing@example.com", "password": "wrong"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_password_reset_rate_limit_counts_nonexistent_email(sqlite_database_dependency):
    limit = api_main.AUTH_RATE_LIMITS["password_reset"]["account"][0]

    for _ in range(limit):
        response = client.post("/auth/password-reset", json={"email": "missing@example.com"})
        assert response.status_code == 200
        assert response.json() == {"reset_token": None, "reset_url": None}

    response = client.post("/auth/password-reset", json={"email": "missing@example.com"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert sqlite_database_dependency.query(AuthToken).count() == 0


def test_verification_resend_daily_limit_is_separate_from_login_limit(
    sqlite_database_dependency,
):
    client.post(
        "/auth/register",
        json={
            "email": "player@example.com",
            "username": "player",
            "password": "Strong-pass1",
        },
    )
    limit = api_main.AUTH_RATE_LIMITS["verification_resend_daily"]["account"][0]

    for _ in range(limit):
        response = client.post(
            "/auth/verify-email/resend",
            json={"email": "player@example.com"},
        )
        assert response.status_code == 200

    response = client.post(
        "/auth/verify-email/resend",
        json={"email": "player@example.com"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert (
        sqlite_database_dependency.query(AuthRateLimitEvent)
        .filter(AuthRateLimitEvent.bucket == "verification_resend_daily:account")
        .count()
        == limit
    )
    assert (
        sqlite_database_dependency.query(AuthRateLimitEvent)
        .filter(AuthRateLimitEvent.bucket == "login:account")
        .count()
        == 0
    )


def test_auth_me_returns_current_user_from_cookie(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        description="Builder of careful bots.",
        password_hash=hash_password("correct"),
        is_email_verified=True,
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    login_response = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "correct"},
    )
    response = client.get("/auth/me")

    assert login_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["email"] == "player@example.com"
    assert response.json()["username"] == "player"
    assert response.json()["description"] == "Builder of careful bots."


def test_get_user_profile_returns_public_description(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        description="Tic tac tactician.",
        password_hash=hash_password("correct"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    response = client.get("/users/player")

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "username": "player",
        "description": "Tic tac tactician.",
        "created_at": user.created_at.isoformat(),
    }


def test_get_user_profile_returns_404_for_unknown_username(sqlite_database_dependency):
    response = client.get("/users/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "user_not_found",
            "message": "User not found: missing",
        }
    }


def test_update_auth_me_updates_description(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)

    response = client.patch(
        "/auth/me",
        json={"description": "  Connect Four enjoyer.  "},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Connect Four enjoyer."
    sqlite_database_dependency.refresh(user)
    assert user.description == "Connect Four enjoyer."


def test_update_auth_me_rejects_overlong_description(sqlite_database_dependency):
    login_user(sqlite_database_dependency)

    response = client.patch(
        "/auth/me",
        json={"description": "a" * 281},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_auth_me_returns_401_for_missing_cookie(sqlite_database_dependency):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Unauthorized.",
        }
    }


def test_auth_me_returns_401_for_invalid_session_id(sqlite_database_dependency):
    client.cookies.set(api_main.SESSION_COOKIE_NAME, "missing-session")

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_auth_me_returns_401_for_expired_session(sqlite_database_dependency):
    user = User(username="player", email="player@example.com", password_hash=hash_password("correct"))
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()
    sqlite_database_dependency.add(
        AuthSession(
            id="expired-session",
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    sqlite_database_dependency.commit()
    client.cookies.set(api_main.SESSION_COOKIE_NAME, "expired-session")

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_logout_deletes_session_and_replayed_cookie_is_rejected(sqlite_database_dependency):
    user = User(
        username="player",
        email="player@example.com",
        password_hash=hash_password("correct"),
        is_email_verified=True,
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()
    login_response = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "correct"},
    )
    session_id = client.cookies.get(api_main.SESSION_COOKIE_NAME)

    logout_response = client.post("/auth/logout")

    assert login_response.status_code == 200
    assert logout_response.status_code == 204
    assert sqlite_database_dependency.query(AuthSession).count() == 0

    client.cookies.set(api_main.SESSION_COOKIE_NAME, session_id)
    replay_response = client.get("/auth/me")

    assert replay_response.status_code == 401
    assert replay_response.json()["error"]["code"] == "unauthorized"


def test_list_matches_returns_empty_history(sqlite_database_dependency):
    response = client.get("/matches")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "limit": 20,
        "offset": 0,
        "total": 0,
    }


def test_list_matches_returns_recent_matches_first(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    older = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )
    newer = make_persisted_match(
        game_id="connect-four",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=None,
        result_reason="draw",
        completed_at=datetime(2026, 1, 2, 0, 0, 1, tzinfo=timezone.utc),
    )
    sqlite_database_dependency.add_all([older, newer])
    sqlite_database_dependency.commit()

    response = client.get("/matches")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["match_id"] for item in body["items"]] == [newer.id, older.id]
    assert body["items"][0]["game"] == "connect-four"
    assert body["items"][0]["bot_one_name"] == "alpha"
    assert body["items"][0]["bot_two_name"] == "beta"
    assert body["items"][0]["winner_bot_name"] is None
    assert body["items"][1]["game"] == "tictactoe"
    assert body["items"][1]["bot_one_name"] == "alpha"
    assert body["items"][1]["bot_two_name"] == "beta"
    assert body["items"][1]["winner_bot_name"] == "alpha"


def test_list_matches_paginates_results(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    oldest = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )
    middle = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
        completed_at=datetime(2026, 1, 2, 0, 0, 1, tzinfo=timezone.utc),
    )
    newest = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
        completed_at=datetime(2026, 1, 3, 0, 0, 1, tzinfo=timezone.utc),
    )
    sqlite_database_dependency.add_all([oldest, middle, newest])
    sqlite_database_dependency.commit()

    response = client.get("/matches?limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert body["total"] == 3
    assert [item["match_id"] for item in body["items"]] == [middle.id]
    assert body["items"][0]["bot_one_name"] == "alpha"
    assert body["items"][0]["bot_two_name"] == "beta"
    assert body["items"][0]["winner_bot_name"] == "alpha"


def test_list_matches_filters_by_game_id(sqlite_database_dependency):
    tictactoe_bot = seed_bot(sqlite_database_dependency, name="ttt", game_id="tictactoe")
    connectfour_bot = seed_bot(
        sqlite_database_dependency,
        name="c4",
        game_id="connect-four",
    )
    tictactoe_match = make_persisted_match(
        game_id="tictactoe",
        bot_one_id=tictactoe_bot.id,
        bot_two_id=tictactoe_bot.id,
        winner_bot_id=tictactoe_bot.id,
    )
    connectfour_match = make_persisted_match(
        game_id="connect-four",
        bot_one_id=connectfour_bot.id,
        bot_two_id=connectfour_bot.id,
        winner_bot_id=None,
        completed_at=datetime(2026, 1, 2, 0, 0, 1, tzinfo=timezone.utc),
    )
    sqlite_database_dependency.add_all([tictactoe_match, connectfour_match])
    sqlite_database_dependency.commit()

    response = client.get("/matches?game_id=connect-four")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["match_id"] for item in body["items"]] == [connectfour_match.id]
    assert body["items"][0]["game"] == "connect-four"


def test_list_matches_filters_by_bot_id(sqlite_database_dependency):
    alpha = seed_bot(sqlite_database_dependency, name="alpha")
    beta = seed_bot(sqlite_database_dependency, name="beta")
    gamma = seed_bot(sqlite_database_dependency, name="gamma")
    alpha_as_bot_one = make_persisted_match(
        bot_one_id=alpha.id,
        bot_two_id=beta.id,
        winner_bot_id=alpha.id,
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )
    alpha_as_bot_two = make_persisted_match(
        bot_one_id=beta.id,
        bot_two_id=alpha.id,
        winner_bot_id=beta.id,
        completed_at=datetime(2026, 1, 2, 0, 0, 1, tzinfo=timezone.utc),
    )
    unrelated = make_persisted_match(
        bot_one_id=beta.id,
        bot_two_id=gamma.id,
        winner_bot_id=gamma.id,
        completed_at=datetime(2026, 1, 3, 0, 0, 1, tzinfo=timezone.utc),
    )
    sqlite_database_dependency.add_all([alpha_as_bot_one, alpha_as_bot_two, unrelated])
    sqlite_database_dependency.commit()

    response = client.get(f"/matches?bot_id={alpha.id}&limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert body["total"] == 2
    assert [item["match_id"] for item in body["items"]] == [alpha_as_bot_one.id]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_matches_validates_pagination_parameters(query):
    response = client.get(f"/matches?{query}")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_leaderboard_returns_bots_ordered_by_rating(sqlite_database_dependency):
    low = Bot(
        name="low",
        game_id="tictactoe",
        rating=1100,
        games_played=3,
        wins=1,
        losses=2,
        draws=0,
    )
    high = Bot(
        name="high",
        game_id="tictactoe",
        rating=1500,
        games_played=4,
        wins=3,
        losses=1,
        draws=0,
    )
    no_games = Bot(name="new", game_id="tictactoe")
    other_game = Bot(
        name="connect-four-high",
        game_id="connect-four",
        rating=1800,
    )
    sqlite_database_dependency.add_all([low, high, no_games, other_game])
    sqlite_database_dependency.commit()

    response = client.get("/leaderboard?game_id=tictactoe")

    assert response.status_code == 200
    assert response.json() == [
        {
            "bot_id": high.id,
            "name": "high",
            "owner_name": "System",
            "rating": 1500,
            "games_played": 4,
            "wins": 3,
            "losses": 1,
            "draws": 0,
        },
        {
            "bot_id": no_games.id,
            "name": "new",
            "owner_name": "System",
            "rating": 1200,
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
        },
        {
            "bot_id": low.id,
            "name": "low",
            "owner_name": "System",
            "rating": 1100,
            "games_played": 3,
            "wins": 1,
            "losses": 2,
            "draws": 0,
        },
    ]


def test_leaderboard_uses_stable_tie_breaker(sqlite_database_dependency):
    second = Bot(name="second", game_id="tictactoe", rating=1300)
    first = Bot(name="first", game_id="tictactoe", rating=1300)
    sqlite_database_dependency.add_all([second, first])
    sqlite_database_dependency.commit()

    response = client.get("/leaderboard?game_id=tictactoe")

    assert response.status_code == 200
    assert [bot["bot_id"] for bot in response.json()] == [second.id, first.id]


def test_leaderboard_returns_user_and_system_bot_owners(sqlite_database_dependency):
    user = User(
        username="owner",
        email="owner@example.com",
        password_hash=hash_password("password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.flush()
    system_bot = Bot(name="system", game_id="tictactoe", rating=1400)
    user_bot = Bot(
        name="owned",
        game_id="tictactoe",
        rating=1300,
        owner_id=user.id,
    )
    sqlite_database_dependency.add_all([system_bot, user_bot])
    sqlite_database_dependency.commit()

    response = client.get("/leaderboard?game_id=tictactoe")

    assert response.status_code == 200
    assert [
        (bot["name"], bot["owner_name"])
        for bot in response.json()
    ] == [
        ("system", "System"),
        ("owned", "owner"),
    ]


def test_leaderboard_paginates_results(sqlite_database_dependency):
    bots = [
        Bot(name="first", game_id="tictactoe", rating=1500),
        Bot(name="second", game_id="tictactoe", rating=1400),
        Bot(name="third", game_id="tictactoe", rating=1300),
    ]
    sqlite_database_dependency.add_all(bots)
    sqlite_database_dependency.commit()

    response = client.get("/leaderboard?game_id=tictactoe&limit=1&offset=1")

    assert response.status_code == 200
    assert response.json() == [
        {
            "bot_id": bots[1].id,
            "name": "second",
            "owner_name": "System",
            "rating": 1400,
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
        }
    ]


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1"])
def test_leaderboard_validates_pagination_parameters(query):
    response = client.get(f"/leaderboard?game_id=tictactoe&{query}")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_list_bots_returns_bots_for_game_ordered_by_name(sqlite_database_dependency):
    beta = Bot(name="beta", game_id="tictactoe")
    alpha = Bot(name="alpha", game_id="tictactoe")
    other_game = Bot(name="alpha", game_id="connect-four")
    sqlite_database_dependency.add_all([beta, alpha, other_game])
    sqlite_database_dependency.commit()

    response = client.get("/bots?game_id=tictactoe")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": alpha.id, "name": "alpha", "owner_name": None, "has_active_submission": False},
        {"bot_id": beta.id, "name": "beta", "owner_name": None, "has_active_submission": False},
    ]


def test_list_bots_returns_empty_list_for_unknown_game(sqlite_database_dependency):
    seed_bot(sqlite_database_dependency, name="random", game_id="tictactoe")

    response = client.get("/bots?game_id=unknown")

    assert response.status_code == 200
    assert response.json() == []


def test_list_bots_returns_all_bots_without_game_id(sqlite_database_dependency):
    alpha = seed_bot(sqlite_database_dependency, name="alpha", game_id="tictactoe")
    beta = seed_bot(sqlite_database_dependency, name="beta", game_id="connect-four")

    response = client.get("/bots")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": alpha.id, "name": "alpha", "owner_name": None, "has_active_submission": True},
        {"bot_id": beta.id, "name": "beta", "owner_name": None, "has_active_submission": True},
    ]


def test_list_bots_returns_all_bots_for_empty_game_id(sqlite_database_dependency):
    alpha = seed_bot(sqlite_database_dependency, name="alpha", game_id="tictactoe")
    beta = seed_bot(sqlite_database_dependency, name="beta", game_id="connect-four")

    response = client.get("/bots?game_id=")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": alpha.id, "name": "alpha", "owner_name": None, "has_active_submission": True},
        {"bot_id": beta.id, "name": "beta", "owner_name": None, "has_active_submission": True},
    ]


def test_list_bots_returns_user_and_system_bot_owners(sqlite_database_dependency):
    user = User(
        username="owner",
        email="owner@example.com",
        password_hash=hash_password("password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.flush()
    system_bot = Bot(name="alpha", game_id="tictactoe")
    user_bot = Bot(name="beta", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add_all([system_bot, user_bot])
    sqlite_database_dependency.commit()

    response = client.get("/bots?game_id=tictactoe")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": system_bot.id, "name": "alpha", "owner_name": None, "has_active_submission": False},
        {"bot_id": user_bot.id, "name": "beta", "owner_name": "owner", "has_active_submission": False},
    ]


def test_get_bot_returns_bot_detail(sqlite_database_dependency):
    user = User(
        username="owner",
        email="owner@example.com",
        password_hash=hash_password("password"),
    )
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.flush()
    bot = Bot(
        name="alpha",
        game_id="tictactoe",
        owner_id=user.id,
        rating=1337,
        games_played=5,
        wins=3,
        losses=1,
        draws=1,
    )
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.get(f"/bots/{bot.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["bot_id"] == bot.id
    assert body["name"] == "alpha"
    assert body["description"] == ""
    assert body["game_id"] == "tictactoe"
    assert body["owner_name"] == "owner"
    assert body["rating"] == 1337
    assert body["games_played"] == 5
    assert body["wins"] == 3
    assert body["losses"] == 1
    assert body["draws"] == 1
    assert body["created_at"]


def test_get_bot_returns_system_owner_for_default_bot(sqlite_database_dependency):
    bot = seed_bot(sqlite_database_dependency, name="system")

    response = client.get(f"/bots/{bot.id}")

    assert response.status_code == 200
    assert response.json()["owner_name"] == "System"


def test_get_bot_returns_not_found(sqlite_database_dependency):
    response = client.get("/bots/999")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "bot_not_found",
        "message": "Bot not found: 999",
    }


def test_update_bot_updates_owned_bot_description(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="alpha", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.patch(
        f"/bots/{bot.id}",
        json={"description": "  Plays the center whenever possible.  "},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Plays the center whenever possible."
    sqlite_database_dependency.refresh(bot)
    assert bot.description == "Plays the center whenever possible."


def test_update_bot_rejects_unowned_bot(sqlite_database_dependency):
    owner = User(
        username="owner",
        email="owner@example.com",
        password_hash=hash_password("password"),
    )
    sqlite_database_dependency.add(owner)
    sqlite_database_dependency.commit()
    bot = Bot(name="alpha", game_id="tictactoe", owner_id=owner.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()
    login_user(sqlite_database_dependency, email="other@example.com")

    response = client.patch(
        f"/bots/{bot.id}",
        json={"description": "Not mine."},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "bot_not_owned",
            "message": "Bot is not owned by the authenticated user.",
        }
    }
    sqlite_database_dependency.refresh(bot)
    assert bot.description == ""


def test_update_bot_rejects_overlong_description(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="alpha", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.patch(
        f"/bots/{bot.id}",
        json={"description": "a" * 281},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_bot_requires_authentication(sqlite_database_dependency):
    response = client.post(
        "/bots",
        json={
            "game_id": "tictactoe",
            "name": "custom",
            "source_code": valid_bot_source(),
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Unauthorized.",
        }
    }
    assert sqlite_database_dependency.query(Bot).count() == 0


def test_create_bot_rejects_unsupported_game(sqlite_database_dependency):
    login_user(sqlite_database_dependency)

    response = client.post("/bots", **bot_multipart(game_id="missing-game"))

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unsupported_game",
            "message": "Unsupported game: missing-game",
        }
    }
    assert sqlite_database_dependency.query(Bot).count() == 0


def test_create_bot_returns_409_for_duplicate_name_within_game(sqlite_database_dependency):
    login_user(sqlite_database_dependency)
    seed_bot(sqlite_database_dependency, name="custom", game_id="tictactoe")

    response = client.post("/bots", **bot_multipart())

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "bot_name_taken",
            "message": "Bot name is already taken for this game.",
        }
    }
    assert sqlite_database_dependency.query(Bot).count() == 1


def test_create_bot_trims_name_before_storing(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)

    response = client.post("/bots", **bot_multipart(name="  custom  "))

    assert response.status_code == 201
    bot = sqlite_database_dependency.query(Bot).one()
    assert response.json() == {
        "bot_id": bot.id,
        "game_id": "tictactoe",
        "name": "custom",
        "owner_id": user.id,
        "submission_id": bot.active_submission_id,
        "version": 1,
    }
    assert bot.name == "custom"
    assert sqlite_database_dependency.query(BotSubmission).count() == 1


@pytest.mark.parametrize("name", ["", "   ", "ab", "a" * 33, "玩家", "custom.bot", "custom!"])
def test_create_bot_rejects_invalid_name(name, sqlite_database_dependency):
    login_user(sqlite_database_dependency)

    response = client.post("/bots", **bot_multipart(name=name))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(Bot).count() == 0
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


def test_create_bot_rejects_duplicate_name_after_trimming(sqlite_database_dependency):
    login_user(sqlite_database_dependency)
    seed_bot(sqlite_database_dependency, name="custom", game_id="tictactoe")

    response = client.post("/bots", **bot_multipart(name=" custom "))

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "bot_name_taken",
            "message": "Bot name is already taken for this game.",
        }
    }
    assert sqlite_database_dependency.query(Bot).count() == 1


def test_create_bot_rejects_blank_name_after_trimming(sqlite_database_dependency):
    login_user(sqlite_database_dependency)

    response = client.post("/bots", **bot_multipart(name="   "))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Bot name must be 3-32 characters."
    assert sqlite_database_dependency.query(Bot).count() == 0


def test_create_bot_sets_owner_to_authenticated_user(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)

    response = client.post("/bots", **bot_multipart())

    assert response.status_code == 201
    body = response.json()
    bot = sqlite_database_dependency.query(Bot).one()

    assert body == {
        "bot_id": bot.id,
        "game_id": "tictactoe",
        "name": "custom",
        "owner_id": user.id,
        "submission_id": bot.active_submission_id,
        "version": 1,
    }
    assert bot.owner_id == user.id
    assert bot.active_submission_id is not None


def test_create_bot_rejects_user_over_bot_limit(
    sqlite_database_dependency,
    monkeypatch,
):
    user = login_user(sqlite_database_dependency)
    monkeypatch.setenv(api_main.MAX_BOTS_PER_USER_ENV_VAR, "1")
    existing_bot = seed_bot(sqlite_database_dependency, name="existing", game_id="tictactoe")
    existing_bot.owner_id = user.id
    sqlite_database_dependency.commit()

    response = client.post("/bots", **bot_multipart())

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "bot_limit_exceeded",
            "message": "User bot limit exceeded. Maximum allowed bots: 1.",
        }
    }
    assert sqlite_database_dependency.query(Bot).count() == 1


@pytest.mark.skip(reason="source submissions were removed")
def test_create_bot_rejects_invalid_python_without_creating_bot(
    sqlite_database_dependency,
):
    login_user(sqlite_database_dependency)

    response = client.post(
        "/bots",
        json={
            "game_id": "tictactoe",
            "name": "custom",
            "source_code": "def choose_move(:\n    return 0\n",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_syntax"
    assert sqlite_database_dependency.query(Bot).count() == 0
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


@pytest.mark.skip(reason="source submissions were removed")
def test_create_bot_rejects_oversized_source_without_creating_bot(
    sqlite_database_dependency,
):
    login_user(sqlite_database_dependency)

    response = client.post(
        "/bots",
        json={
            "game_id": "tictactoe",
            "name": "custom",
            "source_code": "x = 1\n" + ("#" * api_main.MAX_BOT_SUBMISSION_SOURCE_BYTES),
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "submission_too_large"
    assert sqlite_database_dependency.query(Bot).count() == 0
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


@pytest.mark.skip(reason="language selection was removed")
def test_create_bot_rejects_unsupported_language_without_creating_bot(
    sqlite_database_dependency,
):
    login_user(sqlite_database_dependency)

    response = client.post(
        "/bots",
        json={
            "game_id": "tictactoe",
            "name": "custom",
            "source_code": valid_bot_source(),
            "language": "javascript",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_language"
    assert "python, node, bash" in response.json()["error"]["message"]
    assert sqlite_database_dependency.query(Bot).count() == 0
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


@pytest.mark.skip(reason="source submissions were removed")
def test_create_bot_accepts_node_submission(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)

    response = client.post(
        "/bots",
        json={
            "game_id": "tictactoe",
            "name": "node bot",
            "source_code": "const move = { row: 0, col: 0 };\n",
            "language": "node",
        },
    )

    assert response.status_code == 201
    submission = sqlite_database_dependency.query(BotSubmission).one()
    bot = sqlite_database_dependency.query(Bot).one()
    assert submission.language == "node"
    assert submission.source_code == "const move = { row: 0, col: 0 };\n"
    assert bot.owner_id == user.id
    assert bot.active_submission_id == submission.id


def test_submit_bot_source_creates_first_submission_and_sets_active(
    sqlite_database_dependency,
):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.post(
        f"/bots/{bot.id}/submission",
        files={"executable": ("player", valid_bot_executable(), "application/octet-stream")},
    )

    assert response.status_code == 201
    submission = sqlite_database_dependency.query(BotSubmission).one()
    sqlite_database_dependency.refresh(bot)
    assert response.json() == {
        "bot_id": bot.id,
        "submission_id": submission.id,
        "version": 1,
    }
    assert submission.bot_id == bot.id
    assert submission.version == 1
    assert submission.executable == valid_bot_executable()
    assert bot.active_submission_id == submission.id


def test_submit_bot_source_versions_successive_submissions_and_latest_is_active(
    sqlite_database_dependency,
):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    first_response = client.post(
        f"/bots/{bot.id}/submission",
        files={"executable": ("player", valid_bot_executable(b"first"), "application/octet-stream")},
    )
    second_response = client.post(
        f"/bots/{bot.id}/submission",
        files={"executable": ("player", valid_bot_executable(b"second"), "application/octet-stream")},
    )

    submissions = (
        sqlite_database_dependency.query(BotSubmission)
        .order_by(BotSubmission.version)
        .all()
    )
    sqlite_database_dependency.refresh(bot)
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert [submission.version for submission in submissions] == [1, 2]
    assert first_response.json()["version"] == 1
    assert second_response.json()["version"] == 2
    assert bot.active_submission_id == submissions[-1].id


def test_submit_bot_source_requires_authentication(sqlite_database_dependency):
    bot = Bot(name="custom", game_id="tictactoe", owner_id=1)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.post(
        f"/bots/{bot.id}/submission",
        files={"executable": ("player", valid_bot_executable(), "application/octet-stream")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


def test_submit_bot_source_rejects_non_owner(sqlite_database_dependency):
    owner = User(
        username="owner",
        email="owner@example.com",
        password_hash=hash_password("password"),
    )
    sqlite_database_dependency.add(owner)
    sqlite_database_dependency.commit()
    bot = Bot(name="custom", game_id="tictactoe", owner_id=owner.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()
    login_user(sqlite_database_dependency, email="other@example.com")

    response = client.post(
        f"/bots/{bot.id}/submission",
        files={"executable": ("player", valid_bot_executable(), "application/octet-stream")},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "bot_not_owned",
            "message": "Bot is not owned by the authenticated user.",
        }
    }
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


def test_submit_bot_source_returns_404_for_missing_bot(sqlite_database_dependency):
    login_user(sqlite_database_dependency)

    response = client.post(
        "/bots/999/submission",
        files={"executable": ("player", valid_bot_executable(), "application/octet-stream")},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "bot_not_found"
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


@pytest.mark.skip(reason="source submissions were removed")
def test_submit_bot_source_rejects_invalid_python_before_insert(
    sqlite_database_dependency,
):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.post(
        f"/bots/{bot.id}/submission",
        json={"source_code": "def choose_move(:\n    return 0\n"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_syntax"
    assert sqlite_database_dependency.query(BotSubmission).count() == 0
    sqlite_database_dependency.refresh(bot)
    assert bot.active_submission_id is None


@pytest.mark.skip(reason="source submissions were removed")
def test_submit_bot_source_accepts_bash_without_python_syntax_validation(
    sqlite_database_dependency,
):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.post(
        f"/bots/{bot.id}/submission",
        json={
            "source_code": "while read line; do echo '{\"row\":0,\"col\":0}'; done\n",
            "language": "bash",
        },
    )

    assert response.status_code == 201
    submission = sqlite_database_dependency.query(BotSubmission).one()
    assert submission.language == "bash"
    sqlite_database_dependency.refresh(bot)
    assert bot.active_submission_id == submission.id


@pytest.mark.skip(reason="source submissions were removed")
def test_submit_bot_source_rejects_oversized_source_before_insert(
    sqlite_database_dependency,
):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.post(
        f"/bots/{bot.id}/submission",
        json={"source_code": "x = 1\n" + ("#" * api_main.MAX_BOT_SUBMISSION_SOURCE_BYTES)},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "submission_too_large"
    assert sqlite_database_dependency.query(BotSubmission).count() == 0
    sqlite_database_dependency.refresh(bot)
    assert bot.active_submission_id is None


def test_seed_default_bots_creates_two_random_bot_aliases_for_each_game(
    sqlite_database_dependency,
    tmp_path,
    monkeypatch,
):
    (tmp_path / "tictactoe").write_bytes(valid_bot_executable())
    (tmp_path / "connect-four").write_bytes(valid_bot_executable())
    monkeypatch.setenv(api_main.DEFAULT_BOT_EXECUTABLE_DIR_ENV_VAR, str(tmp_path))
    api_main.seed_default_bots(sqlite_database_dependency)

    response = client.get("/bots?game_id=tictactoe")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": 1, "name": "randombot1", "owner_name": None, "has_active_submission": True},
        {"bot_id": 2, "name": "randombot2", "owner_name": None, "has_active_submission": True},
    ]

    connectfour_response = client.get("/bots?game_id=connect-four")

    assert connectfour_response.status_code == 200
    assert connectfour_response.json() == [
        {"bot_id": 3, "name": "randombot1", "owner_name": None, "has_active_submission": True},
        {"bot_id": 4, "name": "randombot2", "owner_name": None, "has_active_submission": True},
    ]
    assert {
        bot.owner_id
        for bot in sqlite_database_dependency.query(Bot)
        .filter(Bot.name.in_(("randombot1", "randombot2")))
        .all()
    } == {None}
    seeded_bots = sqlite_database_dependency.query(Bot).all()
    assert all(bot.active_submission_id is not None for bot in seeded_bots)
    assert sqlite_database_dependency.query(BotSubmission).count() == 4
    assert {
        submission.version
        for submission in sqlite_database_dependency.query(BotSubmission).all()
    } == {1}


def test_seed_default_bots_is_idempotent(sqlite_database_dependency, tmp_path, monkeypatch):
    (tmp_path / "tictactoe").write_bytes(valid_bot_executable())
    (tmp_path / "connect-four").write_bytes(valid_bot_executable())
    monkeypatch.setenv(api_main.DEFAULT_BOT_EXECUTABLE_DIR_ENV_VAR, str(tmp_path))
    api_main.seed_default_bots(sqlite_database_dependency)
    api_main.seed_default_bots(sqlite_database_dependency)

    assert sqlite_database_dependency.query(Bot).count() == 4
    assert sqlite_database_dependency.query(BotSubmission).count() == 4


def test_list_bots_paginates_results(sqlite_database_dependency):
    bots = [
        Bot(name="alpha", game_id="tictactoe"),
        Bot(name="beta", game_id="tictactoe"),
        Bot(name="gamma", game_id="tictactoe"),
    ]
    sqlite_database_dependency.add_all(bots)
    sqlite_database_dependency.commit()

    response = client.get("/bots?game_id=tictactoe&limit=1&offset=1")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": bots[1].id, "name": "beta", "owner_name": None, "has_active_submission": False}
    ]


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1"])
def test_list_bots_validates_pagination_parameters(query):
    response = client.get(f"/bots?game_id=tictactoe&{query}")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_get_match_returns_metadata_result_summary_and_moves(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    match = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
        moves=[
            Move(move_number=2, bot_id=bot_two.id, move=[1, 0]),
            Move(move_number=1, bot_id=bot_one.id, move=[0, 0]),
        ],
    )
    sqlite_database_dependency.add(match)
    sqlite_database_dependency.commit()
    sqlite_database_dependency.refresh(match)

    response = client.get(f"/matches/{match.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["match_id"] == match.id
    assert body["game"] == "tictactoe"
    assert body["bot_one_id"] == bot_one.id
    assert body["bot_two_id"] == bot_two.id
    assert body["bot_one_name"] == "alpha"
    assert body["bot_two_name"] == "beta"
    assert body["bot_one_rating_before"] == 1200
    assert body["bot_two_rating_before"] == 1200
    assert body["bot_one_rating_after"] == 1216
    assert body["bot_two_rating_after"] == 1184
    assert body["bot_one_rating_delta"] == 16
    assert body["bot_two_rating_delta"] == -16
    assert body["winner_bot_id"] == bot_one.id
    assert body["winner_bot_name"] == "alpha"
    assert body["result_reason"] == "win"
    assert body["created_at"]
    assert body["completed_at"]
    assert body["moves"] == [
        {"move_number": 1, "bot_id": bot_one.id, "move": [0, 0]},
        {"move_number": 2, "bot_id": bot_two.id, "move": [1, 0]},
    ]


def test_get_match_returns_404_for_unknown_match_id(sqlite_database_dependency):
    response = client.get("/matches/999")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "match_not_found",
            "message": "Match not found: 999",
        }
    }


def test_create_match_requires_authentication(sqlite_database_dependency):
    api_main.seed_default_bots(sqlite_database_dependency)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Unauthorized.",
        }
    }
    assert sqlite_database_dependency.query(Match).count() == 0


def test_create_match_uses_overridden_database_session(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    def fake_run_tictactoe_match(p1_command, p2_command, on_move, **_kwargs):
        raise AssertionError("runner should not be called")

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 202
    assert sqlite_database_dependency.query(Match).count() == 0
    assert sqlite_database_dependency.query(MatchJob).count() == 1


def test_create_match_enqueues_match_job(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    def fake_run_tictactoe_match(p1_command, p2_command, on_move, **_kwargs):
        raise AssertionError("runner should not be called")

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 202
    job = sqlite_database_dependency.query(MatchJob).one()
    assert response.headers["location"] == f"/match-jobs/{job.id}"
    assert response.json() == {
        "job_id": job.id,
        "status": "queued",
    }
    assert job.game_id == "tictactoe"
    assert job.bot_one.name == "randombot1"
    assert job.bot_two.name == "randombot2"
    assert job.requester_user_id == 1
    assert job.status == "queued"
    assert job.match_id is None
    assert sqlite_database_dependency.query(Match).count() == 0


def test_create_match_rejects_user_over_active_job_limit(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    monkeypatch.setenv(api_main.MAX_ACTIVE_MATCH_JOBS_PER_USER_ENV_VAR, "2")
    bot_one = seed_bot(sqlite_database_dependency, name="randombot1")
    bot_two = seed_bot(sqlite_database_dependency, name="randombot2")
    queued = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        requester_user_id=1,
        status="queued",
    )
    running = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        requester_user_id=1,
        status="running",
    )
    completed = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        requester_user_id=1,
        status="completed",
    )
    other_user = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        requester_user_id=2,
        status="queued",
    )
    sqlite_database_dependency.add_all([queued, running, completed, other_user])
    sqlite_database_dependency.commit()

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "match_job_limit_exceeded",
            "message": "Limit reached (2 active matches). Finish one to continue.",
        }
    }
    assert sqlite_database_dependency.query(MatchJob).count() == 4


def test_get_match_job_returns_queued_job(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="queued",
    )
    sqlite_database_dependency.add(job)
    sqlite_database_dependency.commit()

    response = client.get(f"/match-jobs/{job.id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job.id,
        "status": "queued",
        "match_id": None,
        "error_message": None,
    }


def test_get_live_match_job_returns_running_moves_and_board(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="running",
    )
    sqlite_database_dependency.add(job)
    sqlite_database_dependency.commit()
    sqlite_database_dependency.add_all(
        [
            MatchJobMove(
                job_id=job.id,
                move_number=1,
                bot_id=bot_one.id,
                move=[0, 0],
                board_state=[
                    ["X", None, None],
                    [None, None, None],
                    [None, None, None],
                ],
            ),
            MatchJobMove(
                job_id=job.id,
                move_number=2,
                bot_id=bot_two.id,
                move=[1, 1],
                board_state=[
                    ["X", None, None],
                    [None, "O", None],
                    [None, None, None],
                ],
            ),
        ]
    )
    sqlite_database_dependency.commit()

    response = client.get(f"/match-jobs/{job.id}/live")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job.id
    assert body["status"] == "running"
    assert body["match_id"] is None
    assert body["game"] == "tictactoe"
    assert body["bot_one_name"] == "alpha"
    assert body["bot_two_name"] == "beta"
    assert body["bot_one_rating_before"] == bot_one.rating
    assert body["bot_two_rating_before"] == bot_two.rating
    assert body["bot_one_rating_after"] == bot_one.rating
    assert body["bot_two_rating_after"] == bot_two.rating
    assert body["bot_one_rating_delta"] == 0
    assert body["bot_two_rating_delta"] == 0
    assert body["board_state"] == [
        ["X", None, None],
        [None, "O", None],
        [None, None, None],
    ]
    assert body["moves"] == [
        {
            "move_number": 1,
            "bot_id": bot_one.id,
            "move": [0, 0],
            "board_state": [
                ["X", None, None],
                [None, None, None],
                [None, None, None],
            ],
        },
        {
            "move_number": 2,
            "bot_id": bot_two.id,
            "move": [1, 1],
            "board_state": [
                ["X", None, None],
                [None, "O", None],
                [None, None, None],
            ],
        },
    ]


def test_get_live_match_job_returns_completed_match_rating_snapshots(
    sqlite_database_dependency,
):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    match = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
        bot_one_rating_before=1184,
        bot_two_rating_before=1216,
        bot_one_rating_after=1200,
        bot_two_rating_after=1200,
        bot_one_rating_delta=16,
        bot_two_rating_delta=-16,
    )
    sqlite_database_dependency.add(match)
    sqlite_database_dependency.commit()
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="completed",
        match_id=match.id,
    )
    sqlite_database_dependency.add(job)
    sqlite_database_dependency.commit()

    response = client.get(f"/match-jobs/{job.id}/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["match_id"] == match.id
    assert body["bot_one_rating_before"] == 1184
    assert body["bot_two_rating_before"] == 1216
    assert body["bot_one_rating_after"] == 1200
    assert body["bot_two_rating_after"] == 1200
    assert body["bot_one_rating_delta"] == 16
    assert body["bot_two_rating_delta"] == -16


def test_featured_games_returns_up_to_three_jobs_by_placeholder_heuristic(
    sqlite_database_dependency,
):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jobs = [
        MatchJob(
            game_id="tictactoe",
            bot_one_id=bot_one.id,
            bot_two_id=bot_two.id,
            status="queued",
            created_at=base_time + timedelta(minutes=1),
        ),
        MatchJob(
            game_id="tictactoe",
            bot_one_id=bot_one.id,
            bot_two_id=bot_two.id,
            status="running",
            created_at=base_time,
            started_at=base_time,
        ),
        MatchJob(
            game_id="tictactoe",
            bot_one_id=bot_two.id,
            bot_two_id=bot_one.id,
            status="running",
            created_at=base_time + timedelta(minutes=2),
            started_at=base_time + timedelta(minutes=2),
        ),
        MatchJob(
            game_id="tictactoe",
            bot_one_id=bot_one.id,
            bot_two_id=bot_two.id,
            status="failed",
            created_at=base_time + timedelta(minutes=3),
        ),
    ]
    sqlite_database_dependency.add_all(jobs)
    sqlite_database_dependency.commit()

    response = client.get("/featured-games")

    assert response.status_code == 200
    body = response.json()
    assert [item["job_id"] for item in body["items"]] == [
        jobs[2].id,
        jobs[1].id,
    ]
    assert body["items"][0]["board_state"] == [
        [None, None, None],
        [None, None, None],
        [None, None, None],
    ]


def test_list_match_jobs_returns_recent_jobs_for_game(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    other_bot_one = seed_bot(
        sqlite_database_dependency,
        name="gamma",
        game_id="connect-four",
    )
    other_bot_two = seed_bot(
        sqlite_database_dependency,
        name="delta",
        game_id="connect-four",
    )
    older = datetime(2024, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2024, 1, 2, tzinfo=timezone.utc)
    queued = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="queued",
        created_at=older,
    )
    running = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_two.id,
        bot_two_id=bot_one.id,
        status="running",
        created_at=newer,
        started_at=newer,
    )
    other_game = MatchJob(
        game_id="connect-four",
        bot_one_id=other_bot_one.id,
        bot_two_id=other_bot_two.id,
        status="queued",
        created_at=newer,
    )
    sqlite_database_dependency.add_all([queued, running, other_game])
    sqlite_database_dependency.commit()

    response = client.get("/match-jobs?game_id=tictactoe")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "job_id": running.id,
                "status": "running",
                "match_id": None,
                "error_message": None,
                "game": "tictactoe",
                "bot_one_name": "beta",
                "bot_two_name": "alpha",
                "created_at": newer.replace(tzinfo=None).isoformat(),
                "started_at": newer.replace(tzinfo=None).isoformat(),
                "completed_at": None,
            },
            {
                "job_id": queued.id,
                "status": "queued",
                "match_id": None,
                "error_message": None,
                "game": "tictactoe",
                "bot_one_name": "alpha",
                "bot_two_name": "beta",
                "created_at": older.replace(tzinfo=None).isoformat(),
                "started_at": None,
                "completed_at": None,
            },
        ],
        "limit": 20,
        "offset": 0,
        "total": 2,
    }


def test_list_match_jobs_filters_by_status(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    queued = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="queued",
    )
    failed = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="failed",
        error_message="bot timed out",
    )
    sqlite_database_dependency.add_all([queued, failed])
    sqlite_database_dependency.commit()

    response = client.get("/match-jobs?status=failed")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["job_id"] == failed.id
    assert body["items"][0]["status"] == "failed"
    assert body["items"][0]["error_message"] == "bot timed out"


def test_get_match_job_returns_completed_job_with_resolvable_match(
    sqlite_database_dependency,
):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    match = make_persisted_match(
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        winner_bot_id=bot_one.id,
    )
    sqlite_database_dependency.add(match)
    sqlite_database_dependency.commit()
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="completed",
        match_id=match.id,
    )
    sqlite_database_dependency.add(job)
    sqlite_database_dependency.commit()

    response = client.get(f"/match-jobs/{job.id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job.id,
        "status": "completed",
        "match_id": match.id,
        "error_message": None,
    }

    match_response = client.get(f"/matches/{match.id}")
    assert match_response.status_code == 200
    assert match_response.json()["match_id"] == match.id


def test_get_match_job_returns_failed_job_error_message(sqlite_database_dependency):
    bot_one = seed_bot(sqlite_database_dependency, name="alpha")
    bot_two = seed_bot(sqlite_database_dependency, name="beta")
    job = MatchJob(
        game_id="tictactoe",
        bot_one_id=bot_one.id,
        bot_two_id=bot_two.id,
        status="failed",
        error_message="bot timed out",
    )
    sqlite_database_dependency.add(job)
    sqlite_database_dependency.commit()

    response = client.get(f"/match-jobs/{job.id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job.id,
        "status": "failed",
        "match_id": None,
        "error_message": "bot timed out",
    }


def test_get_match_job_returns_404_for_unknown_job_id(sqlite_database_dependency):
    response = client.get("/match-jobs/999")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "match_job_not_found",
            "message": "Match job not found: 999",
        }
    }


def test_create_match_rejects_same_bot_for_both_players(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    seed_bot(sqlite_database_dependency)

    def fake_run_tictactoe_match(p1_command, p2_command, on_move, **_kwargs):
        raise AssertionError("runner should not be called")

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [{"bot": "random"}, {"bot": "random"}],
        },
    )

    assert response.status_code == 400
    assert sqlite_database_dependency.query(Match).count() == 0
    assert response.json() == {
        "error": {
            "code": "duplicate_bot_match",
            "message": "A bot cannot play against itself",
        }
    }


def test_create_match_enqueues_active_submission_bots(
    sqlite_database_dependency,
    monkeypatch,
):
    user = login_user(sqlite_database_dependency)
    bot_one = Bot(name="versioned", game_id="tictactoe", owner_id=user.id)
    bot_two = Bot(name="opponent", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add_all([bot_one, bot_two])
    sqlite_database_dependency.commit()

    first_source = (
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    print(json.dumps({'row': 0, 'col': 0}), flush=True)\n"
    )
    second_source = (
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    print(json.dumps({'row': 2, 'col': 2}), flush=True)\n"
    )
    opponent_source = (
        "import json, sys\n"
        "moves = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1)]\n"
        "for index, line in enumerate(sys.stdin):\n"
        "    row, col = moves[index]\n"
        "    print(json.dumps({'row': row, 'col': col}), flush=True)\n"
    )

    assert client.post(
        f"/bots/{bot_one.id}/submission",
        files={"executable": ("player", valid_bot_executable(first_source.encode()), "application/octet-stream")},
    ).status_code == 201
    assert client.post(
        f"/bots/{bot_one.id}/submission",
        files={"executable": ("player", valid_bot_executable(second_source.encode()), "application/octet-stream")},
    ).status_code == 201
    assert client.post(
        f"/bots/{bot_two.id}/submission",
        files={"executable": ("player", valid_bot_executable(opponent_source.encode()), "application/octet-stream")},
    ).status_code == 201

    def fake_run_tictactoe_match(p1_command, p2_command, on_move, **_kwargs):
        raise AssertionError("runner should not be called")

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [{"bot": "versioned"}, {"bot": "opponent"}],
        },
    )

    assert response.status_code == 202
    job = sqlite_database_dependency.query(MatchJob).one()
    assert job.bot_one_id == bot_one.id
    assert job.bot_two_id == bot_two.id
    assert job.status == "queued"


def test_create_match_rejects_bot_missing_from_database(sqlite_database_dependency):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)
    payload = valid_match_request()
    payload["players"][1]["bot"] = "missing-bot"

    response = client.post("/matches", json=payload)

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "bot_not_found",
            "message": "Bot not found: missing-bot",
        }
    }


def test_create_match_rejects_first_player_missing_from_database(
    sqlite_database_dependency,
):
    authenticate_request_dependency()
    payload = valid_match_request()
    payload["players"][0]["bot"] = "missing-first-bot"

    response = client.post("/matches", json=payload)

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "bot_not_found",
            "message": "Bot not found: missing-first-bot",
        }
    }


def test_create_match_rejects_missing_required_fields():
    authenticate_request_dependency()
    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [{}],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_create_match_rejects_malformed_json_body():
    authenticate_request_dependency()
    response = client.post(
        "/matches",
        content="{not valid json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_create_match_rejects_wrong_payload_types():
    authenticate_request_dependency()
    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": "random-vs-random",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_create_match_enqueues_connectfour_match_job(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    def fake_run_connectfour_match(p1_command, p2_command, on_move, **_kwargs):
        raise AssertionError("runner should not be called")

    monkeypatch.setattr(api_main, "run_connectfour_match", fake_run_connectfour_match)

    payload = valid_match_request()
    payload["game"] = "connect-four"

    response = client.post("/matches", json=payload)

    assert response.status_code == 202
    body = response.json()
    job = sqlite_database_dependency.query(MatchJob).one()

    assert body == {"job_id": job.id, "status": "queued"}
    assert response.headers["location"] == f"/match-jobs/{job.id}"
    assert job.game_id == "connect-four"
    assert "players" not in body
    assert "result" not in body
    assert sqlite_database_dependency.query(Match).count() == 0


def test_create_match_rejects_unsupported_game(override_database_dependency):
    authenticate_request_dependency()
    payload = valid_match_request()
    payload["game"] = "missing-game"

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert override_database_dependency.added == []
    assert override_database_dependency.commits == 0
    assert response.json() == {
        "error": {
            "code": "unsupported_game",
            "message": "Unsupported game: missing-game",
        }
    }


def test_create_match_rejects_invalid_player_count(override_database_dependency):
    authenticate_request_dependency()
    payload = {
        "game": "tictactoe",
        "players": [{"bot": "random"}],
    }

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert override_database_dependency.added == []
    assert override_database_dependency.commits == 0
    assert response.json() == {
        "error": {
            "code": "invalid_player_count",
            "message": "tictactoe requires exactly 2 players",
        }
    }


def test_create_match_rejects_empty_players():
    authenticate_request_dependency()
    payload = {
        "game": "tictactoe",
        "players": [],
    }

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_player_count",
            "message": "tictactoe requires exactly 2 players",
        }
    }


def test_create_match_rejects_too_many_players():
    authenticate_request_dependency()
    payload = valid_match_request()
    payload["players"].append({"bot": "random"})

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_player_count",
            "message": "tictactoe requires exactly 2 players",
        }
    }


def test_unknown_route_returns_standard_http_error():
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Request failed.",
        }
    }


def test_create_bot_accepts_static_executable_multipart(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)
    artifact = valid_bot_executable(b"artifact")
    response = client.post("/bots", **bot_multipart(executable=artifact, filename="../player.bin"))
    assert response.status_code == 201
    bot = sqlite_database_dependency.query(Bot).one()
    submission = sqlite_database_dependency.query(BotSubmission).one()
    assert bot.owner_id == user.id
    assert bot.active_submission_id == submission.id
    assert submission.executable == artifact
    assert submission.executable_size == len(artifact)
    assert submission.executable_digest == hashlib.sha256(artifact).hexdigest()
    assert submission.original_filename == "player.bin"


def test_executable_submission_versions_and_activates(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id, latest_submission_version=4)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()
    response = client.post(
        f"/bots/{bot.id}/submission",
        files={"executable": ("player", valid_bot_executable(), "application/octet-stream")},
    )
    assert response.status_code == 201
    sqlite_database_dependency.refresh(bot)
    assert response.json()["version"] == 5
    assert bot.latest_submission_version == 5
    assert bot.active_submission_id is not None


def test_create_bot_rejects_non_elf(sqlite_database_dependency):
    login_user(sqlite_database_dependency)
    response = client.post("/bots", **bot_multipart(executable=b"#!/bin/sh\n"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_executable"


def test_create_bot_rejects_wrong_architecture(sqlite_database_dependency):
    login_user(sqlite_database_dependency)
    artifact = bytearray(valid_bot_executable())
    struct.pack_into("<H", artifact, 18, 183)
    response = client.post("/bots", **bot_multipart(executable=bytes(artifact)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_architecture"


def test_create_bot_rejects_dynamic_executable(sqlite_database_dependency):
    login_user(sqlite_database_dependency)
    artifact = bytearray(valid_bot_executable())
    struct.pack_into("<I", artifact, 64, 3)
    response = client.post("/bots", **bot_multipart(executable=bytes(artifact)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "dynamic_executable"
