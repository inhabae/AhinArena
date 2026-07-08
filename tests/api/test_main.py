import pytest
from fastapi.testclient import TestClient

from api.database import get_db
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
            {"id": "player-x", "bot": "random"},
            {"id": "player-o", "bot": "random"},
        ],
    }


def valid_connectfour_match_request():
    return {
        "game": "connect-four",
        "players": [
            {"id": "player-x", "bot": "random"},
            {"id": "player-o", "bot": "random"},
        ],
    }


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_match_uses_overridden_database_session(override_database_dependency):
    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 200
    assert override_database_dependency.closed is True


def test_create_match_runs_tictactoe_match_successfully(monkeypatch):
    observed = {}

    def fake_run_tictactoe_match(p1_command, p2_command):
        observed["p1_command"] = p1_command
        observed["p2_command"] = p2_command
        return {
            "winner": "X",
            "reason": "win",
            "moves": [
                ("X", (0, 0)),
                ("O", (1, 0)),
                ("X", (0, 1)),
                ("O", (1, 1)),
                ("X", (0, 2)),
            ],
            "final_board": [
                ["X", "X", "X"],
                ["O", "O", " "],
                [" ", " ", " "],
            ],
        }

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 200
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
        "players": [
            {"id": "player-x", "bot": "random"},
            {"id": "player-o", "bot": "random"},
        ],
        "result": {
            "winner": "X",
            "reason": "win",
            "moves": [
                ["X", [0, 0]],
                ["O", [1, 0]],
                ["X", [0, 1]],
                ["O", [1, 1]],
                ["X", [0, 2]],
            ],
            "final_board": [
                ["X", "X", "X"],
                ["O", "O", " "],
                [" ", " ", " "],
            ],
        },
    }


def test_create_match_persists_completed_match(override_database_dependency, monkeypatch):
    def fake_run_tictactoe_match(p1_command, p2_command):
        return {
            "winner": "O",
            "reason": "win",
            "moves": [
                ("X", (0, 0)),
                ("O", (1, 0)),
            ],
            "final_board": [
                ["X", " ", " "],
                ["O", " ", " "],
                [" ", " ", " "],
            ],
        }

    monkeypatch.setattr(api_main, "run_tictactoe_match", fake_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 200
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
    assert match.move_history == [
        ("X", (0, 0)),
        ("O", (1, 0)),
    ]


def test_create_match_runs_connectfour_match_successfully(monkeypatch):
    observed = {}

    def fake_run_connectfour_match(p1_command, p2_command):
        observed["p1_command"] = p1_command
        observed["p2_command"] = p2_command
        return {
            "winner": "X",
            "reason": "win",
            "moves": [
                ("X", 0),
                ("O", 1),
                ("X", 0),
                ("O", 1),
                ("X", 0),
                ("O", 1),
                ("X", 0),
            ],
            "final_board": [
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                ["X", " ", " ", " ", " ", " ", " "],
                ["X", "O", " ", " ", " ", " ", " "],
                ["X", "O", " ", " ", " ", " ", " "],
                ["X", "O", " ", " ", " ", " ", " "],
            ],
        }

    monkeypatch.setattr(api_main, "run_connectfour_match", fake_run_connectfour_match)

    response = client.post("/matches", json=valid_connectfour_match_request())

    assert response.status_code == 200
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
        "players": [
            {"id": "player-x", "bot": "random"},
            {"id": "player-o", "bot": "random"},
        ],
        "result": {
            "winner": "X",
            "reason": "win",
            "moves": [
                ["X", 0],
                ["O", 1],
                ["X", 0],
                ["O", 1],
                ["X", 0],
                ["O", 1],
                ["X", 0],
            ],
            "final_board": [
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                ["X", " ", " ", " ", " ", " ", " "],
                ["X", "O", " ", " ", " ", " ", " "],
                ["X", "O", " ", " ", " ", " ", " "],
                ["X", "O", " ", " ", " ", " ", " "],
            ],
        },
    }


def test_create_match_runs_real_random_bot_match_end_to_end():
    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 200
    body = response.json()
    result = body["result"]

    assert body["game"] == "tictactoe"
    assert body["match_id"] == 123
    assert body["players"] == valid_match_request()["players"]
    assert result["winner"] in {"X", "O", None}
    assert result["reason"] in {"win", "draw"}
    assert len(result["moves"]) >= 5
    assert len(result["moves"]) <= 9
    assert len(result["final_board"]) == 3
    assert all(len(row) == 3 for row in result["final_board"])


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
            "players": [{"id": "player-x"}],
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

    assert response.status_code == 200
    body = response.json()
    result = body["result"]

    assert body["game"] == "connect-four"
    assert body["match_id"] == 123
    assert body["players"] == payload["players"]
    assert result["winner"] in {"X", "O", None}
    assert result["reason"] in {"win", "draw"}
    assert len(result["moves"]) >= 7
    assert len(result["moves"]) <= 42
    assert len(result["final_board"]) == 6
    assert all(len(row) == 7 for row in result["final_board"])


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
        "players": [{"id": "solo", "bot": "random"}],
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
    payload["players"].append({"id": "player-extra", "bot": "random"})

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
    def failing_run_tictactoe_match(p1_command, p2_command):
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
