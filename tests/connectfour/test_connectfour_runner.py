import json
from pathlib import Path
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


def test_connectfour_runner_uses_c_built_default_bot_command():
    assert DEFAULT_BOT_COMMAND == [
        str(Path(__file__).resolve().parents[2] / "build" / "default-bots" / "connect-four")
    ]


def test_connectfour_runner_returns_referee_result_shape_for_x_win():
    observed_moves = []

    def on_move(player, move, board):
        observed_moves.append((player, move))

    result = run_connectfour_match(
        p1_command=scripted_column_bot_command([0, 0, 0, 0]),
        p2_command=scripted_column_bot_command([1, 1, 1]),
        timeout=1.0,
        on_move=on_move,
    )

    assert result == {
        "winner": "p1",
        "reason": "win",
    }
    assert observed_moves == [
        ("p1", 0),
        ("p2", 1),
        ("p1", 0),
        ("p2", 1),
        ("p1", 0),
        ("p2", 1),
        ("p1", 0),
    ]


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

    assert result["winner"] == "p1"
    assert observed[0] == (
        "p1",
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
    assert observed[-1][0] == "p1"
    assert observed[-1][1] == 0
    assert observed[-1][2] == [
        [" ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " "],
        ["X", " ", " ", " ", " ", " ", " "],
        ["X", "O", " ", " ", " ", " ", " "],
        ["X", "O", " ", " ", " ", " ", " "],
        ["X", "O", " ", " ", " ", " ", " "],
    ]
