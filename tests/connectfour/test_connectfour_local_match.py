import io
import sys

from scripts.run_local_connect_four import format_board, run_local_match


def test_format_board_uses_dots_for_empty_cells_and_column_labels():
    text = format_board(
        [
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", " ", " ", " ", " "],
            [" ", " ", " ", "X", " ", " ", " "],
            ["O", " ", "X", "O", " ", " ", " "],
        ]
    )

    assert text == (
        ". | . | . | . | . | . | .\n"
        ". | . | . | . | . | . | .\n"
        ". | . | . | . | . | . | .\n"
        ". | . | . | . | . | . | .\n"
        ". | . | . | X | . | . | .\n"
        "O | . | X | O | . | . | .\n"
        "0   1   2   3   4   5   6"
    )


def test_local_connect_four_match_runs_to_completion():
    output = io.StringIO()
    bot_command = [sys.executable, "-m", "engine.connectfour.random_bot"]

    result = run_local_match(
        x_command=bot_command,
        o_command=bot_command,
        timeout=1.0,
        output=output,
    )

    text = output.getvalue()

    assert result["reason"] in {"win", "draw"}
    assert result["winner"] in {"X", "O", None}
    assert "moves" not in result
    assert "Starting local Connect Four match: X bot vs O bot" in text
    assert "Move 1:" in text
    assert text.count("Move ") >= 7
    assert text.count("Move ") <= 42
    assert " | " in text
    assert "0   1   2   3   4   5   6" in text
    assert "Final result" in text

    if result["winner"] is None:
        assert "Draw (draw)" in text
    else:
        assert f"Winner: {result['winner']} (win)" in text
