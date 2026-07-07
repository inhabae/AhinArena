from fastapi.testclient import TestClient

import api.main as api_main


client = TestClient(api_main.app)


def valid_match_request():
    return {
        "game": "tictactoe",
        "players": [
            {"id": "player-x", "bot": "random"},
            {"id": "player-o", "bot": "random"},
        ],
    }


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert observed["p1_command"] == api_main.bot_registry.get_command("random")
    assert observed["p2_command"] == api_main.bot_registry.get_command("random")
    assert response.json() == {
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


def test_create_match_runs_real_random_bot_match_end_to_end():
    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 200
    body = response.json()
    result = body["result"]

    assert body["game"] == "tictactoe"
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


def test_create_match_rejects_unsupported_game():
    payload = valid_match_request()
    payload["game"] = "connect-four"

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unsupported_game",
            "message": "Unsupported game: connect-four",
        }
    }


def test_create_match_rejects_invalid_player_count():
    payload = {
        "game": "tictactoe",
        "players": [{"id": "solo", "bot": "random"}],
    }

    response = client.post("/matches", json=payload)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_player_count",
            "message": "Tic-Tac-Toe requires exactly 2 players",
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
            "message": "Tic-Tac-Toe requires exactly 2 players",
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
            "message": "Tic-Tac-Toe requires exactly 2 players",
        }
    }


def test_create_match_returns_error_when_match_execution_fails(monkeypatch):
    def failing_run_tictactoe_match(p1_command, p2_command):
        raise RuntimeError("runner failed")

    monkeypatch.setattr(api_main, "run_tictactoe_match", failing_run_tictactoe_match)

    response = client.post("/matches", json=valid_match_request())

    assert response.status_code == 500
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
