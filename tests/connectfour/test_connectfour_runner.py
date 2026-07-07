import json
import sys

from engine.connectfour.runner import DEFAULT_BOT_COMMAND, run_connectfour_match


def scripted_column_bot_command(columns):
    code = (
        "import json, sys\n"
        "columns = json.loads(sys.argv[1])\n"
        "for line in sys.stdin:\n"
        "    json.loads(line)\n"
        "    print(json.dumps({'col': columns.pop(0)}), flush=True)\n"
    )

    return [sys.executable, "-c", code, json.dumps(columns)]


def test_connectfour_runner_uses_default_random_bot_command():
    assert DEFAULT_BOT_COMMAND == [
        sys.executable,
        "-m",
        "engine.connectfour.random_bot",
    ]


def test_connectfour_runner_returns_referee_result_shape_for_x_win():
    result = run_connectfour_match(
        p1_command=scripted_column_bot_command([0, 0, 0, 0]),
        p2_command=scripted_column_bot_command([1, 1, 1]),
        timeout=1.0,
    )

    assert result == {
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


def test_connectfour_runner_calls_on_move_with_updated_board():
    observed = []

    def on_move(player, move, board):
        observed.append((player, move, board))

    result = run_connectfour_match(
        p1_command=scripted_column_bot_command([0, 0, 0, 0]),
        p2_command=scripted_column_bot_command([1, 1, 1]),
        timeout=1.0,
        on_move=on_move,
    )

    assert result["winner"] == "X"
    assert observed[0] == (
        "X",
        0,
        [
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            ["X", " ", " ", " ", " ", " ", " "],
        ],
    )
    assert observed[-1][0] == "X"
    assert observed[-1][1] == 0
    assert observed[-1][2] == result["final_board"]


def test_connectfour_runner_executes_default_random_bots_successfully():
    result = run_connectfour_match(timeout=1.0)

    assert result["winner"] in {"X", "O", None}
    assert result["reason"] in {"win", "draw"}
    assert len(result["moves"]) >= 7
    assert len(result["moves"]) <= 42
    assert len(result["final_board"]) == 6
    assert all(len(row) == 7 for row in result["final_board"])
