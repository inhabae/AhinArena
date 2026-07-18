import json
import sys

from engine.runner import run_match
from engine.tictactoe import Game


def scripted_tictactoe_bot_command(moves):
    code = (
        "import json, sys\n"
        "moves = json.loads(sys.argv[1])\n"
        "for line in sys.stdin:\n"
        "    json.loads(line)\n"
        "    move = moves.pop(0)\n"
        "    print(json.dumps({'row': move[0], 'col': move[1]}), flush=True)\n"
    )

    return [sys.executable, "-c", code, json.dumps(moves)]


def scripted_bash_tictactoe_bot_command(moves):
    encoded_moves = [json.dumps({"row": row, "col": col}) for row, col in moves]
    script = (
        "moves=("
        + " ".join("'" + move.replace("'", "'\\''") + "'" for move in encoded_moves)
        + "); "
        + "index=0; "
        + "while IFS= read -r line; do "
        + 'printf "%s\\n" "${moves[$index]}"; '
        + "index=$((index + 1)); "
        + "done"
    )
    return ["bash", "-c", script]


def test_run_match_translates_player_markers_for_result_and_moves():
    observed_moves = []

    def on_move(player, move, board):
        observed_moves.append((player, move, board))

    result = run_match(
        Game,
        default_bot_command=["/unused-default-bot"],
        p1_command=scripted_tictactoe_bot_command([[0, 0], [0, 1], [0, 2]]),
        p2_command=scripted_tictactoe_bot_command([[1, 0], [1, 1]]),
        timeout=1.0,
        on_move=on_move,
    )

    assert result == {
        "winner": "p1",
        "reason": "win",
    }
    assert [player for player, _move, _board in observed_moves] == [
        "p1",
        "p2",
        "p1",
        "p2",
        "p1",
    ]
    assert observed_moves[-1][1] == (0, 2)


def test_run_match_accepts_non_python_bot_command_end_to_end():
    result = run_match(
        Game,
        default_bot_command=["/unused-default-bot"],
        p1_command=scripted_bash_tictactoe_bot_command([[0, 0], [0, 1], [0, 2]]),
        p2_command=scripted_tictactoe_bot_command([[1, 0], [1, 1]]),
        timeout=1.0,
    )

    assert result == {
        "winner": "p1",
        "reason": "win",
    }
