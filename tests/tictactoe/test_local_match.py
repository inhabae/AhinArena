from scripts.run_local_tictactoe import format_board


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
