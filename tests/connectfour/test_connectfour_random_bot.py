import json
import subprocess
import sys


BOT_COMMAND = [sys.executable, "-m", "engine.connectfour.random_bot"]


def start_bot():
    return subprocess.Popen(
        BOT_COMMAND,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def send_state(process, board, marker="X"):
    state = {
        "marker": marker,
        "board": board,
    }

    process.stdin.write(json.dumps(state) + "\n")
    process.stdin.flush()

    return json.loads(process.stdout.readline())


def test_random_bot_returns_valid_json():
    process = start_bot()

    try:
        response = send_state(
            process,
            [
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
            ],
        )

        assert isinstance(response, dict)
        assert "col" in response
        assert isinstance(response["col"], int)
    finally:
        process.terminate()


def test_random_bot_returns_legal_move():
    process = start_bot()

    try:
        board = [
            ["X", " ", "O", " ", " ", " ", " "],
            ["O", " ", "X", " ", " ", " ", " "],
            ["X", " ", "O", " ", " ", " ", " "],
            ["O", " ", "X", " ", " ", " ", " "],
            ["X", " ", "O", " ", " ", " ", " "],
            ["O", " ", "X", " ", " ", " ", " "],
        ]
        response = send_state(process, board)

        assert response["col"] in [1, 3, 4, 5, 6]
    finally:
        process.terminate()


def test_random_bot_returns_only_legal_move():
    process = start_bot()

    try:
        response = send_state(
            process,
            [
                ["X", "O", "X", "O", "X", "O", " "],
                ["O", "X", "O", "X", "O", "X", " "],
                ["X", "O", "X", "O", "X", "O", " "],
                ["O", "X", "O", "X", "O", "X", " "],
                ["X", "O", "X", "O", "X", "O", " "],
                ["O", "X", "O", "X", "O", "X", " "],
            ],
        )

        assert response == {
            "col": 6,
        }
    finally:
        process.terminate()


def test_random_bot_handles_o_marker():
    process = start_bot()

    try:
        response = send_state(
            process,
            [
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                [" ", " ", " ", " ", " ", " ", " "],
                ["X", "O", "X", "O", "X", "O", "X"],
            ],
            marker="O",
        )

        assert response["col"] in [0, 1, 2, 3, 4, 5, 6]
    finally:
        process.terminate()


def test_random_bot_handles_multiple_requests():
    process = start_bot()

    try:
        first_response = send_state(
            process,
            [
                ["X", "O", "X", "O", "X", "O", " "],
                ["O", "X", "O", "X", "O", "X", " "],
                ["X", "O", "X", "O", "X", "O", " "],
                ["O", "X", "O", "X", "O", "X", " "],
                ["X", "O", "X", "O", "X", "O", " "],
                ["O", "X", "O", "X", "O", "X", " "],
            ],
        )
        second_response = send_state(
            process,
            [
                [" ", "X", "O", "X", "O", "X", "O"],
                [" ", "O", "X", "O", "X", "O", "X"],
                [" ", "X", "O", "X", "O", "X", "O"],
                [" ", "O", "X", "O", "X", "O", "X"],
                [" ", "X", "O", "X", "O", "X", "O"],
                [" ", "O", "X", "O", "X", "O", "X"],
            ],
        )

        assert first_response == {
            "col": 6,
        }
        assert second_response == {
            "col": 0,
        }
    finally:
        process.terminate()
