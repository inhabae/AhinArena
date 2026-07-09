import io
import sys

from scripts.run_local_tictactoe import format_board, run_local_match


def test_format_board_uses_dots_for_empty_cells():
    text = format_board(
        [
            ["X", " ", "O"],
            [" ", "X", " "],
            ["O", " ", "X"],
        ]
    )

    assert text == (
        "X | . | O\n"
        "---------\n"
        ". | X | .\n"
        "---------\n"
        "O | . | X"
    )


def test_local_tictactoe_match_runs_to_completion():
    output = io.StringIO()
    bot_command = [sys.executable, "-m", "engine.tictactoe.random_bot"]

    result = run_local_match(
        x_command=bot_command,
        o_command=bot_command,
        timeout=1.0,
        output=output,
    )

    text = output.getvalue()

    assert result["reason"] in {"win", "draw"}
    assert result["winner"] in {"p1", "p2", None}
    assert "moves" not in result
    assert "Starting local Tic-Tac-Toe match: X bot vs O bot" in text
    assert "Move 1:" in text
    assert text.count("Move ") >= 5
    assert text.count("Move ") <= 9
    assert " | " in text
    assert "---------" in text
    assert "Final result" in text

    if result["winner"] is None:
        assert "Draw (draw)" in text
    else:
        assert f"Winner: {result['winner']} (win)" in text
