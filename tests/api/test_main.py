from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import hash_password, verify_password
from api.database import Base, get_db
from api.models import Bot, BotSubmission, Match, Move, Session as AuthSession, User
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
def override_database_dependency():
    client.cookies.clear()
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


def seed_bot(session, *, name="random", game_id="tictactoe"):
    bot = Bot(name=name, game_id=game_id)
    session.add(bot)
    session.commit()
    return bot


def login_user(session, *, email="player@example.com", password="correct"):
    user = User(
        username=email.split("@", maxsplit=1)[0],
        email=email,
        password_hash=hash_password(password),
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
            "password": "super-secret",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"id", "email", "username", "created_at"}
    assert body["email"] == "player@example.com"
    assert body["username"] == "PlayerOne"
    assert body["created_at"]

    user = sqlite_database_dependency.query(User).one()
    assert user.email == "player@example.com"
    assert user.username == "PlayerOne"
    assert user.password_hash != "super-secret"
    assert verify_password("super-secret", user.password_hash) is True


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
            "password": "new-password",
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
            "password": "new-password",
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
    ],
)
def test_register_user_returns_422_for_invalid_email(email, sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "username": "player",
            "password": "new-password",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


def test_register_user_returns_422_for_overlong_email(sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": f"{'a' * 309}@example.com",
            "username": "player",
            "password": "new-password",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sqlite_database_dependency.query(User).count() == 0


@pytest.mark.parametrize("username", ["", "   ", "a" * 81])
def test_register_user_returns_422_for_invalid_username(username, sqlite_database_dependency):
    response = client.post(
        "/auth/register",
        json={
            "email": "player@example.com",
            "username": username,
            "password": "new-password",
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


def test_login_sets_http_only_lax_cookie(sqlite_database_dependency):
    user = User(username="player", email="player@example.com", password_hash=hash_password("correct"))
    sqlite_database_dependency.add(user)
    sqlite_database_dependency.commit()

    response = client.post(
        "/auth/login",
        json={"email": "PLAYER@example.com", "password": "correct"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "email", "username", "created_at"}
    assert body["email"] == "player@example.com"
    assert body["username"] == "player"
    assert sqlite_database_dependency.query(AuthSession).count() == 1

    set_cookie = response.headers["set-cookie"]
    assert f"{api_main.SESSION_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_session_cookie_is_secure_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
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
        User(username="player", email="player@example.com", password_hash=hash_password("correct"))
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


def test_auth_me_returns_current_user_from_cookie(sqlite_database_dependency):
    user = User(username="player", email="player@example.com", password_hash=hash_password("correct"))
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
    user = User(username="player", email="player@example.com", password_hash=hash_password("correct"))
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
        {"bot_id": alpha.id, "name": "alpha", "owner_name": None},
        {"bot_id": beta.id, "name": "beta", "owner_name": None},
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
        {"bot_id": alpha.id, "name": "alpha", "owner_name": None},
        {"bot_id": beta.id, "name": "beta", "owner_name": None},
    ]


def test_list_bots_returns_all_bots_for_empty_game_id(sqlite_database_dependency):
    alpha = seed_bot(sqlite_database_dependency, name="alpha", game_id="tictactoe")
    beta = seed_bot(sqlite_database_dependency, name="beta", game_id="connect-four")

    response = client.get("/bots?game_id=")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": alpha.id, "name": "alpha", "owner_name": None},
        {"bot_id": beta.id, "name": "beta", "owner_name": None},
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
        {"bot_id": system_bot.id, "name": "alpha", "owner_name": None},
        {"bot_id": user_bot.id, "name": "beta", "owner_name": "owner"},
    ]


def test_create_bot_requires_authentication(sqlite_database_dependency):
    response = client.post(
        "/bots",
        json={"game_id": "tictactoe", "name": "custom"},
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

    response = client.post(
        "/bots",
        json={"game_id": "missing-game", "name": "custom"},
    )

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

    response = client.post(
        "/bots",
        json={"game_id": "tictactoe", "name": "custom"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "bot_name_taken",
            "message": "Bot name is already taken for this game.",
        }
    }
    assert sqlite_database_dependency.query(Bot).count() == 1


def test_create_bot_sets_owner_to_authenticated_user(sqlite_database_dependency):
    user = login_user(sqlite_database_dependency)

    response = client.post(
        "/bots",
        json={"game_id": "tictactoe", "name": "custom"},
    )

    assert response.status_code == 201
    body = response.json()
    bot = sqlite_database_dependency.query(Bot).one()

    assert body == {
        "bot_id": bot.id,
        "game_id": "tictactoe",
        "name": "custom",
        "owner_id": user.id,
    }
    assert bot.owner_id == user.id


def test_submit_bot_source_creates_first_submission_and_sets_active(
    sqlite_database_dependency,
):
    user = login_user(sqlite_database_dependency)
    bot = Bot(name="custom", game_id="tictactoe", owner_id=user.id)
    sqlite_database_dependency.add(bot)
    sqlite_database_dependency.commit()

    response = client.post(
        f"/bots/{bot.id}/submission",
        json={"source_code": "def choose_move(board):\n    return 0\n"},
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
    assert submission.language == "python"
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
        json={"source_code": "def choose_move(board):\n    return 0\n"},
    )
    second_response = client.post(
        f"/bots/{bot.id}/submission",
        json={"source_code": "def choose_move(board):\n    return 1\n"},
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
        json={"source_code": "def choose_move(board):\n    return 0\n"},
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
        json={"source_code": "def choose_move(board):\n    return 0\n"},
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
        json={"source_code": "def choose_move(board):\n    return 0\n"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "bot_not_found"
    assert sqlite_database_dependency.query(BotSubmission).count() == 0


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
):
    api_main.seed_default_bots(sqlite_database_dependency)

    response = client.get("/bots?game_id=tictactoe")

    assert response.status_code == 200
    assert response.json() == [
        {"bot_id": 1, "name": "randombot1", "owner_name": None},
        {"bot_id": 2, "name": "randombot2", "owner_name": None},
    ]

    connectfour_response = client.get("/bots?game_id=connect-four")

    assert connectfour_response.status_code == 200
    assert connectfour_response.json() == [
        {"bot_id": 3, "name": "randombot1", "owner_name": None},
        {"bot_id": 4, "name": "randombot2", "owner_name": None},
    ]
    assert {
        bot.owner_id
        for bot in sqlite_database_dependency.query(Bot)
        .filter(Bot.name.in_(("randombot1", "randombot2")))
        .all()
    } == {None}


def test_seed_default_bots_is_idempotent(sqlite_database_dependency):
    api_main.seed_default_bots(sqlite_database_dependency)
    api_main.seed_default_bots(sqlite_database_dependency)

    assert sqlite_database_dependency.query(Bot).count() == 4


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
        {"bot_id": bots[1].id, "name": "beta", "owner_name": None}
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


def test_create_match_uses_overridden_database_session(sqlite_database_dependency):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    assert sqlite_database_dependency.query(Match).count() == 1


def test_create_match_runs_tictactoe_match_successfully(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)
    observed = {}

    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
        observed["p1_command"] = p1_command
        observed["p2_command"] = p2_command
        for player, move in [
            ("p1", (0, 0)),
            ("p2", (1, 0)),
            ("p1", (0, 1)),
            ("p2", (1, 1)),
            ("p1", (0, 2)),
        ]:
            on_move(player, move, [])
        return {
            "winner": "p1",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    match = sqlite_database_dependency.query(Match).one()
    assert response.headers["location"] == f"/matches/{match.id}"
    assert observed["p1_command"] == api_main.bot_registry.get_command(
        "randombot1",
        "tictactoe",
    )
    assert observed["p2_command"] == api_main.bot_registry.get_command(
        "randombot2",
        "tictactoe",
    )
    assert response.json() == {
        "match_id": match.id,
        "game": "tictactoe",
        "winner_bot_id": match.winner_bot_id,
        "result_reason": "win",
    }


def test_create_match_persists_completed_match(sqlite_database_dependency, monkeypatch):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
        on_move("p1", (0, 0), [])
        on_move("p2", (1, 0), [])
        return {
            "winner": "p2",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    match = sqlite_database_dependency.query(Match).one()
    assert response.json()["match_id"] == match.id

    assert match.game_id == "tictactoe"
    assert match.bot_one.name == "randombot1"
    assert match.bot_two.name == "randombot2"
    assert match.bot_one_rating_before == 1200
    assert match.bot_two_rating_before == 1200
    assert match.bot_one_rating_after == 1184
    assert match.bot_two_rating_after == 1216
    assert match.bot_one_rating_delta == -16
    assert match.bot_two_rating_delta == 16
    assert match.winner_bot_id == match.bot_two_id
    assert match.result_reason == "win"
    assert [
        (move.move_number, move.bot_id, move.move)
        for move in match.moves
    ] == [
        (1, match.bot_one_id, [0, 0]),
        (2, match.bot_two_id, [1, 0]),
    ]
    bot_one = sqlite_database_dependency.get(Bot, match.bot_one_id)
    bot_two = sqlite_database_dependency.get(Bot, match.bot_two_id)
    assert bot_one.rating == 1184
    assert bot_one.games_played == 1
    assert bot_one.wins == 0
    assert bot_one.losses == 1
    assert bot_one.draws == 0
    assert bot_two.rating == 1216
    assert bot_two.games_played == 1
    assert bot_two.wins == 1
    assert bot_two.losses == 0
    assert bot_two.draws == 0


def test_create_match_rejects_same_bot_for_both_players(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    seed_bot(sqlite_database_dependency)

    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
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


def test_create_match_updates_distinct_bot_ratings_and_records(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    bot_one = Bot(
        name="alpha",
        game_id="tictactoe",
        rating=1400,
        games_played=3,
        wins=2,
        losses=1,
        draws=0,
    )
    bot_two = Bot(
        name="beta",
        game_id="tictactoe",
        rating=1200,
        games_played=4,
        wins=1,
        losses=2,
        draws=1,
    )
    sqlite_database_dependency.add_all([bot_one, bot_two])
    sqlite_database_dependency.commit()

    class TestBotRegistry:
        def get_command(self, bot_name, game_id):
            return ["run", bot_name, game_id]

    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
        return {
            "winner": "p2",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "bot_registry", TestBotRegistry())
    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [
                {"bot": "alpha"},
                {"bot": "beta"},
            ],
        },
    )

    assert response.status_code == 201
    match = sqlite_database_dependency.query(Match).one()
    sqlite_database_dependency.refresh(bot_one)
    sqlite_database_dependency.refresh(bot_two)

    assert match.bot_one_id == bot_one.id
    assert match.bot_two_id == bot_two.id
    assert match.bot_one_rating_before == 1400
    assert match.bot_two_rating_before == 1200
    assert match.bot_one_rating_after == 1376
    assert match.bot_two_rating_after == 1224
    assert match.bot_one_rating_delta == -24
    assert match.bot_two_rating_delta == 24
    assert match.winner_bot_id == bot_two.id

    assert bot_one.rating == 1376
    assert bot_one.games_played == 4
    assert bot_one.wins == 2
    assert bot_one.losses == 2
    assert bot_one.draws == 0
    assert bot_two.rating == 1224
    assert bot_two.games_played == 5
    assert bot_two.wins == 2
    assert bot_two.losses == 2
    assert bot_two.draws == 1


def test_create_match_updates_ratings_and_records_for_draw(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    bot_one = Bot(name="draw-alpha", game_id="tictactoe")
    bot_two = Bot(name="draw-beta", game_id="tictactoe")
    sqlite_database_dependency.add_all([bot_one, bot_two])
    sqlite_database_dependency.commit()

    class TestBotRegistry:
        def get_command(self, bot_name, game_id):
            return ["run", bot_name, game_id]

    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
        return {
            "winner": None,
            "reason": "draw",
        }

    monkeypatch.setattr(api_main, "bot_registry", TestBotRegistry())
    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [
                {"bot": "draw-alpha"},
                {"bot": "draw-beta"},
            ],
        },
    )

    assert response.status_code == 201
    match = sqlite_database_dependency.query(Match).one()
    sqlite_database_dependency.refresh(bot_one)
    sqlite_database_dependency.refresh(bot_two)

    assert match.bot_one_rating_after == 1200
    assert match.bot_two_rating_after == 1200
    assert match.bot_one_rating_delta == 0
    assert match.bot_two_rating_delta == 0
    assert match.winner_bot_id is None
    assert bot_one.rating == 1200
    assert bot_two.rating == 1200
    assert bot_one.games_played == 1
    assert bot_two.games_played == 1
    assert bot_one.draws == 1
    assert bot_two.draws == 1


def test_create_match_runs_connectfour_match_successfully(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)
    observed = {}

    def fake_run_connectfour_match(p1_command, p2_command, on_move):
        observed["p1_command"] = p1_command
        observed["p2_command"] = p2_command
        for player, move in [
            ("p1", 0),
            ("p2", 1),
            ("p1", 0),
            ("p2", 1),
            ("p1", 0),
            ("p2", 1),
            ("p1", 0),
        ]:
            on_move(player, move, [])
        return {
            "winner": "p1",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "run_connectfour_match", fake_run_connectfour_match)

    response = client.post("/matches", json=valid_connectfour_match_request())

    assert response.status_code == 201
    match = sqlite_database_dependency.query(Match).one()
    assert response.headers["location"] == f"/matches/{match.id}"
    assert observed["p1_command"] == api_main.bot_registry.get_command(
        "randombot1",
        "connect-four",
    )
    assert observed["p2_command"] == api_main.bot_registry.get_command(
        "randombot2",
        "connect-four",
    )
    assert response.json() == {
        "match_id": match.id,
        "game": "connect-four",
        "winner_bot_id": match.winner_bot_id,
        "result_reason": "win",
    }
    assert [
        (move.move_number, move.bot_id, move.move)
        for move in match.moves
    ] == [
        (1, match.bot_one_id, 0),
        (2, match.bot_two_id, 1),
        (3, match.bot_one_id, 0),
        (4, match.bot_two_id, 1),
        (5, match.bot_one_id, 0),
        (6, match.bot_two_id, 1),
        (7, match.bot_one_id, 0),
    ]
    assert [
        (move.bot_id, move.move)
        for move in match.moves
    ] == [
        (match.bot_one_id, 0),
        (match.bot_two_id, 1),
        (match.bot_one_id, 0),
        (match.bot_two_id, 1),
        (match.bot_one_id, 0),
        (match.bot_two_id, 1),
        (match.bot_one_id, 0),
    ]


def test_create_match_runs_real_random_bot_match_end_to_end(sqlite_database_dependency):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    body = response.json()
    match = sqlite_database_dependency.query(Match).one()

    assert body["game"] == "tictactoe"
    assert body["match_id"] == match.id
    assert body["winner_bot_id"] in {match.bot_one_id, match.bot_two_id, None}
    assert body["result_reason"] in {"win", "draw"}
    assert "players" not in body
    assert "result" not in body
    assert match.bot_one_rating_before == 1200
    assert match.bot_two_rating_before == 1200


def test_create_match_runs_seeded_random_bot_aliases(sqlite_database_dependency):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [
                {"bot": "randombot1"},
                {"bot": "randombot2"},
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    match = sqlite_database_dependency.query(Match).one()
    assert body["match_id"] == match.id
    assert {match.bot_one.name, match.bot_two.name} == {"randombot1", "randombot2"}


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


def test_create_match_rejects_database_bot_without_registry_command(
    sqlite_database_dependency,
):
    authenticate_request_dependency()
    seed_bot(sqlite_database_dependency, name="database-only-one")
    seed_bot(sqlite_database_dependency, name="database-only-two")

    response = client.post(
        "/matches",
        json={
            "game": "tictactoe",
            "players": [
                {"bot": "database-only-one"},
                {"bot": "database-only-two"},
            ],
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unknown_bot",
            "message": "Unknown bot: database-only-one",
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


def test_create_match_runs_real_random_connectfour_bot_match_end_to_end(
    sqlite_database_dependency,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    payload = valid_match_request()
    payload["game"] = "connect-four"

    response = client.post("/matches", json=payload)

    assert response.status_code == 201
    body = response.json()
    match = sqlite_database_dependency.query(Match).one()

    assert body["game"] == "connect-four"
    assert body["match_id"] == match.id
    assert body["winner_bot_id"] in {match.bot_one_id, match.bot_two_id, None}
    assert body["result_reason"] in {"win", "draw"}
    assert "players" not in body
    assert "result" not in body
    assert match.bot_one_rating_before == 1200
    assert match.bot_two_rating_before == 1200


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


def test_create_match_returns_error_when_match_execution_fails(
    sqlite_database_dependency,
    monkeypatch,
):
    authenticate_request_dependency()
    api_main.seed_default_bots(sqlite_database_dependency)

    def failing_run_tictactoe_match(p1_command, p2_command, on_move):
        raise RuntimeError("runner failed")

    monkeypatch.setattr(api_main, "run_tictactoe_match", failing_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 500
    assert sqlite_database_dependency.query(Match).count() == 0
    assert response.json() == {
        "error": {
            "code": "match_execution_failed",
            "message": "runner failed",
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
