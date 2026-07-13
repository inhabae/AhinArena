import json
import sys

from engine.referee import Referee
from engine.tictactoe import Game as TicTacToeGame


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


def delayed_first_move_bot_command():
    code = (
        "import json, sys, time\n"
        "moves = [(0, 0), (0, 1), (0, 2)]\n"
        "for index, line in enumerate(sys.stdin):\n"
        "    json.loads(line)\n"
        "    if index == 0:\n"
        "        time.sleep(0.2)\n"
        "    row, col = moves[index]\n"
        "    print(json.dumps({'row': row, 'col': col}), flush=True)\n"
    )

    return [sys.executable, "-c", code]


def delayed_second_move_bot_command():
    code = (
        "import json, sys, time\n"
        "moves = [(0, 0), (0, 1)]\n"
        "for index, line in enumerate(sys.stdin):\n"
        "    json.loads(line)\n"
        "    if index == 1:\n"
        "        time.sleep(0.2)\n"
        "    row, col = moves[index]\n"
        "    print(json.dumps({'row': row, 'col': col}), flush=True)\n"
    )

    return [sys.executable, "-c", code]


def partial_line_bot_command():
    code = (
        "import sys, time\n"
        "for line in sys.stdin:\n"
        "    sys.stdout.write('{\"row\":')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(10)\n"
    )

    return [sys.executable, "-c", code]


def test_referee_runs_match_and_reports_x_win():
    observed_moves = []

    def on_move(player, move, board):
        observed_moves.append((player, move))

    referee = Referee(
        {
            "X": scripted_bot_command([[0, 0], [0, 1], [0, 2]]),
            "O": scripted_bot_command([[1, 0], [1, 1]]),
        },
        TicTacToeGame(),
        on_move=on_move,
    )

    result = referee.run_match()

    assert result["winner"] == "X"
    assert result["reason"] == "win"
    assert observed_moves == [
        ("X", (0, 0)),
        ("O", (1, 0)),
        ("X", (0, 1)),
        ("O", (1, 1)),
        ("X", (0, 2)),
    ]
    assert "moves" not in result
    assert "final_board" not in result


def test_referee_assigns_x_and_o_players_and_alternates_turns():
    observed_moves = []

    def on_move(player, move, board):
        observed_moves.append((player, move))

    referee = Referee(
        {
            "X": scripted_bot_command([[0, 0], [1, 1], [2, 2]]),
            "O": scripted_bot_command([[0, 1], [0, 2]]),
        },
        TicTacToeGame(),
        on_move=on_move,
    )

    result = referee.run_match()

    assert result["winner"] == "X"
    assert [player for player, move in observed_moves] == [
        "X",
        "O",
        "X",
        "O",
        "X",
    ]


def test_referee_calls_on_move_with_updated_board_after_each_valid_move():
    observed_moves = []

    def on_move(player, move, board):
        observed_moves.append((player, move, board))

    referee = Referee(
        {
            "X": scripted_bot_command([[0, 0], [0, 1], [0, 2]]),
            "O": scripted_bot_command([[1, 0], [1, 1]]),
        },
        TicTacToeGame(),
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
        {
            "X": scripted_bot_command([[3, 3]]),
            "O": scripted_bot_command([]),
        },
        TicTacToeGame(),
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "invalid_move"


def test_referee_handles_malformed_json_response():
    referee = Referee(
        {
            "X": malformed_json_bot_command(),
            "O": scripted_bot_command([]),
        },
        TicTacToeGame(),
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "bot_error"
    assert result["player"] == "X"


def test_referee_handles_bot_crash():
    referee = Referee(
        {
            "X": crashing_bot_command(),
            "O": scripted_bot_command([]),
        },
        TicTacToeGame(),
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "bot_error"
    assert result["player"] == "X"


def test_referee_handles_bot_timeout():
    referee = Referee(
        {
            "X": sleeping_bot_command(),
            "O": scripted_bot_command([]),
        },
        TicTacToeGame(),
        timeout=0.1,
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "timeout"
    assert result["player"] == "X"


def test_referee_allows_separate_startup_timeout_for_first_move():
    observed_moves = []
    referee = Referee(
        {
            "X": delayed_first_move_bot_command(),
            "O": scripted_bot_command([[1, 0], [1, 1]]),
        },
        TicTacToeGame(),
        timeout=0.1,
        startup_timeout=1.0,
        on_move=lambda player, move, board: observed_moves.append((player, move)),
    )

    result = referee.run_match()

    assert result["reason"] == "win"
    assert observed_moves[0] == ("X", (0, 0))


def test_referee_keeps_normal_timeout_after_first_move():
    referee = Referee(
        {
            "X": delayed_second_move_bot_command(),
            "O": scripted_bot_command([[1, 0], [1, 1]]),
        },
        TicTacToeGame(),
        timeout=0.1,
        startup_timeout=1.0,
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "timeout"
    assert result["player"] == "X"


def test_referee_handles_partial_line_bot_timeout():
    referee = Referee(
        {
            "X": partial_line_bot_command(),
            "O": scripted_bot_command([]),
        },
        TicTacToeGame(),
        timeout=0.1,
    )

    result = referee.run_match()

    assert result["winner"] == "O"
    assert result["reason"] == "timeout"
    assert result["player"] == "X"


def column_bot_command(columns):
    code = (
        "import json, sys\n"
        "columns = json.loads(sys.argv[1])\n"
        "for line in sys.stdin:\n"
        "    json.loads(line)\n"
        "    print(json.dumps({'column': columns.pop(0)}), flush=True)\n"
    )

    return [sys.executable, "-c", code, json.dumps(columns)]


class ColumnRaceGame:
    players = ("red", "blue")

    def __init__(self):
        self.current_player = "red"
        self.columns = [" ", " "]
        self.last_player = None

    def bot_state(self, player):
        return {
            "player": player,
            "columns": self.board_state(),
        }

    def parse_move(self, response):
        if not isinstance(response, dict):
            return None

        column = response.get("column")
        if not isinstance(column, int):
            return None

        return column

    def apply_move(self, move):
        if move < 0 or move >= len(self.columns):
            return False

        if self.columns[move] != " ":
            return False

        self.columns[move] = self.current_player
        self.last_player = self.current_player
        self.current_player = "blue" if self.current_player == "red" else "red"
        return True

    def is_terminal(self):
        return " " not in self.columns

    def winner(self):
        return self.last_player

    def forfeit_winner(self, player):
        return "blue" if player == "red" else "red"

    def board_state(self):
        return self.columns.copy()


def test_referee_runs_match_with_supplied_game_rules():
    observed_moves = []

    def on_move(player, move, board):
        observed_moves.append((player, move))

    referee = Referee(
        {
            "red": column_bot_command([0]),
            "blue": column_bot_command([1]),
        },
        ColumnRaceGame(),
        on_move=on_move,
    )

    result = referee.run_match()

    assert result["winner"] == "blue"
    assert result["reason"] == "win"
    assert observed_moves == [
        ("red", 0),
        ("blue", 1),
    ]
    assert "moves" not in result
    assert "final_board" not in result


def test_referee_uses_supplied_game_rules_to_reject_invalid_moves():
    referee = Referee(
        {
            "red": column_bot_command([2]),
            "blue": column_bot_command([]),
        },
        ColumnRaceGame(),
    )

    result = referee.run_match()

    assert result["winner"] == "blue"
    assert result["reason"] == "invalid_move"
    assert "moves" not in result
