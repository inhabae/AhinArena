import json
import sys

from engine.referee import Referee


def scripted_bot_command(moves):
    code = (
        "import json, sys\n"
        "moves = json.loads(sys.argv[1])\n"
        "for line in sys.stdin:\n"
        "    json.loads(line)\n"
        "    row, col = moves.pop(0)\n"
        "    print(json.dumps({'row': row, 'col': col}), flush=True)\n"
    )

    return [sys.executable, "-c", code, json.dumps(moves)]


def malformed_json_bot_command():
    code = (
        "import sys\n"
        "for line in sys.stdin:\n"
        "    print('not json', flush=True)\n"
    )

    return [sys.executable, "-c", code]


def crashing_bot_command():
    return [sys.executable, "-c", "import sys; sys.exit(1)"]


def sleeping_bot_command():
    code = (
        "import time, sys\n"
        "for line in sys.stdin:\n"
        "    time.sleep(10)\n"
    )

    return [sys.executable, "-c", code]


def test_referee_runs_match_and_reports_x_win():
    referee = Referee(
        scripted_bot_command([[0, 0], [0, 1], [0, 2]]),
        scripted_bot_command([[1, 0], [1, 1]]),
    )

    result = referee.run_match()

    assert result["winner"] == "X"
    assert result["reason"] == "win"
    assert result["moves"] == [
        ("X", (0, 0)),
        ("O", (1, 0)),
        ("X", (0, 1)),
        ("O", (1, 1)),
        ("X", (0, 2)),
    ]
    assert result["final_board"] == [
        ["X", "X", "X"],
        ["O", "O", " "],
        [" ", " ", " "],
    ]


def test_referee_assigns_x_and_o_players_and_alternates_turns():
    referee = Referee(
        scripted_bot_command([[0, 0], [1, 1], [2, 2]]),
        scripted_bot_command([[0, 1], [0, 2]]),
    )

    result = referee.run_match()

    assert [marker for marker, move in result["moves"]] == [
        "X",
        "O",
        "X",
        "O",
        "X",
    ]


def test_referee_calls_on_move_with_updated_board_after_each_valid_move():
    observed_moves = []

    def on_move(marker, move, board):
        observed_moves.append((marker, move, board))

    referee = Referee(
        scripted_bot_command([[0, 0], [0, 1], [0, 2]]),
        scripted_bot_command([[1, 0], [1, 1]]),
        on_move=on_move,
    )

    result = referee.run_match()

    assert result["winner"] == "X"
    assert observed_moves == [
        (
            "X",
            (0, 0),
            [
                ["X", " ", " "],
                [" ", " ", " "],
                [" ", " ", " "],
            ],
        ),
        (
            "O",
            (1, 0),
            [
                ["X", " ", " "],
                ["O", " ", " "],
                [" ", " ", " "],
            ],
        ),
        (
            "X",
            (0, 1),
            [
                ["X", "X", " "],
                ["O", " ", " "],
                [" ", " ", " "],
            ],
        ),
        (
            "O",
            (1, 1),
            [
                ["X", "X", " "],
                ["O", "O", " "],
                [" ", " ", " "],
            ],
        ),
        (
            "X",
            (0, 2),
            [
                ["X", "X", "X"],
                ["O", "O", " "],
                [" ", " ", " "],
            ],
        ),
    ]


def test_referee_handles_invalid_move():
    referee = Referee(
        scripted_bot_command([[3, 3]]),
        scripted_bot_command([]),
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "invalid_move"


def test_referee_handles_malformed_json_response():
    referee = Referee(
        malformed_json_bot_command(),
        scripted_bot_command([]),
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "bot_error"
    assert result["marker"] == "X"


def test_referee_handles_bot_crash():
    referee = Referee(
        crashing_bot_command(),
        scripted_bot_command([]),
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "bot_error"
    assert result["marker"] == "X"


def test_referee_handles_bot_timeout():
    referee = Referee(
        sleeping_bot_command(),
        scripted_bot_command([]),
        timeout=0.1,
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "timeout"
    assert result["marker"] == "X"
