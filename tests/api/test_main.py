from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base, get_db
from api.models import Match, Move
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
            {"bot": "random"},
            {"bot": "random"},
        ],
    }


def valid_connectfour_match_request():
    return {
        "game": "connect-four",
        "players": [
            {"bot": "random"},
            {"bot": "random"},
        ],
    }


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
    bot_one_id="random-x",
    bot_two_id="random-o",
    winner="X",
    result_reason="win",
    created_at=None,
    completed_at=None,
    moves=None,
):
    return Match(
        game_id=game_id,
        bot_one_id=bot_one_id,
        bot_two_id=bot_two_id,
        winner=winner,
        result_reason=result_reason,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=completed_at or datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        moves=moves or [],
    )


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    older = make_persisted_match(
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )
    newer = make_persisted_match(
        game_id="connect-four",
        winner=None,
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
    assert body["items"][1]["game"] == "tictactoe"


def test_list_matches_paginates_results(sqlite_database_dependency):
    oldest = make_persisted_match(
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )
    middle = make_persisted_match(
        completed_at=datetime(2026, 1, 2, 0, 0, 1, tzinfo=timezone.utc),
    )
    newest = make_persisted_match(
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


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_matches_validates_pagination_parameters(query):
    response = client.get(f"/matches?{query}")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request body is invalid."
    assert body["error"]["details"]


def test_get_match_returns_metadata_result_summary_and_moves(sqlite_database_dependency):
    match = make_persisted_match(
        moves=[
            Move(move_number=2, player="O", move=[1, 0]),
            Move(move_number=1, player="X", move=[0, 0]),
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
    assert body["bot_one_id"] == "random-x"
    assert body["bot_two_id"] == "random-o"
    assert body["winner"] == "X"
    assert body["result_reason"] == "win"
    assert body["created_at"]
    assert body["completed_at"]
    assert body["moves"] == [
        {"move_number": 1, "player": "X", "move": [0, 0]},
        {"move_number": 2, "player": "O", "move": [1, 0]},
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


def test_create_match_uses_overridden_database_session(override_database_dependency):
    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    assert override_database_dependency.closed is True


def test_create_match_runs_tictactoe_match_successfully(monkeypatch):
    observed = {}

    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
        observed["p1_command"] = p1_command
        observed["p2_command"] = p2_command
        for player, move in [
            ("X", (0, 0)),
            ("O", (1, 0)),
            ("X", (0, 1)),
            ("O", (1, 1)),
            ("X", (0, 2)),
        ]:
            on_move(player, move, [])
        return {
            "winner": "X",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    assert response.headers["location"] == "/matches/123"
    assert observed["p1_command"] == api_main.bot_registry.get_command(
        "random",
        "tictactoe",
    )
    assert observed["p2_command"] == api_main.bot_registry.get_command(
        "random",
        "tictactoe",
    )
    assert response.json() == {
        "match_id": 123,
        "game": "tictactoe",
        "winner": "X",
        "result_reason": "win",
    }


def test_create_match_persists_completed_match(override_database_dependency, monkeypatch):
    def fake_run_tictactoe_match(p1_command, p2_command, on_move):
        on_move("X", (0, 0), [])
        on_move("O", (1, 0), [])
        return {
            "winner": "O",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    assert response.json()["match_id"] == 123
    assert override_database_dependency.commits == 1
    assert len(override_database_dependency.added) == 1
    assert override_database_dependency.refreshed == override_database_dependency.added

    match = override_database_dependency.added[0]
    assert match.game_id == "tictactoe"
    assert match.bot_one_id == "random"
    assert match.bot_two_id == "random"
    assert match.winner == "O"
    assert match.result_reason == "win"
    assert [
        (move.move_number, move.player, move.move)
        for move in match.moves
    ] == [
        (1, "X", (0, 0)),
        (2, "O", (1, 0)),
    ]


def test_create_match_runs_connectfour_match_successfully(
    override_database_dependency,
    monkeypatch,
):
    observed = {}

    def fake_run_connectfour_match(p1_command, p2_command, on_move):
        observed["p1_command"] = p1_command
        observed["p2_command"] = p2_command
        for player, move in [
            ("X", 0),
            ("O", 1),
            ("X", 0),
            ("O", 1),
            ("X", 0),
            ("O", 1),
            ("X", 0),
        ]:
            on_move(player, move, [])
        return {
            "winner": "X",
            "reason": "win",
        }

    monkeypatch.setattr(api_main, "run_connectfour_match", fake_run_connectfour_match)

    response = client.post("/matches", json=valid_connectfour_match_request())

    assert response.status_code == 201
    assert response.headers["location"] == "/matches/123"
    assert observed["p1_command"] == api_main.bot_registry.get_command(
        "random",
        "connect-four",
    )
    assert observed["p2_command"] == api_main.bot_registry.get_command(
        "random",
        "connect-four",
    )
    assert response.json() == {
        "match_id": 123,
        "game": "connect-four",
        "winner": "X",
        "result_reason": "win",
    }
    match = override_database_dependency.added[0]
    assert [
        (move.move_number, move.player, move.move)
        for move in match.moves
    ] == [
        (1, "X", 0),
        (2, "O", 1),
        (3, "X", 0),
        (4, "O", 1),
        (5, "X", 0),
        (6, "O", 1),
        (7, "X", 0),
    ]
    assert [
        (move.player, move.move)
        for move in match.moves
    ] == [
        ("X", 0),
        ("O", 1),
        ("X", 0),
        ("O", 1),
        ("X", 0),
        ("O", 1),
        ("X", 0),
    ]


def test_create_match_runs_real_random_bot_match_end_to_end():
    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 201
    body = response.json()

    assert body["game"] == "tictactoe"
    assert body["match_id"] == 123
    assert body["winner"] in {"X", "O", None}
    assert body["result_reason"] in {"win", "draw"}
    assert "players" not in body
    assert "result" not in body


def test_create_match_rejects_unknown_bot():
    payload = valid_match_request()
    payload["players"][1]["bot"] = "missing-bot"

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unknown_bot",
            "message": "Unknown bot: missing-bot",
        }
    }


def test_create_match_rejects_unknown_first_player_bot():
    payload = valid_match_request()
    payload["players"][0]["bot"] = "missing-first-bot"

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unknown_bot",
            "message": "Unknown bot: missing-first-bot",
        }
    }


def test_create_match_rejects_missing_required_fields():
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


def test_create_match_runs_real_random_connectfour_bot_match_end_to_end():
    payload = valid_match_request()
    payload["game"] = "connect-four"

    response = client.post("/matches", json=payload)

    assert response.status_code == 201
    body = response.json()

    assert body["game"] == "connect-four"
    assert body["match_id"] == 123
    assert body["winner"] in {"X", "O", None}
    assert body["result_reason"] in {"win", "draw"}
    assert "players" not in body
    assert "result" not in body


def test_create_match_rejects_unsupported_game(override_database_dependency):
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
    override_database_dependency,
    monkeypatch,
):
    def failing_run_tictactoe_match(p1_command, p2_command, on_move):
        raise RuntimeError("runner failed")

    monkeypatch.setattr(api_main, "run_tictactoe_match", failing_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 500
    assert override_database_dependency.added == []
    assert override_database_dependency.commits == 0
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
