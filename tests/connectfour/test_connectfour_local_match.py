from scripts.run_local_connect_four import format_board


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
