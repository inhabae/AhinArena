from engine.connectfour import Board


def test_new_board_is_empty():
    board = Board()

    assert board.grid == [
        [" ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " "],
        [" ", " ", " ", " ", " ", " ", " "],
    ]


def test_drop_marker_places_marker_in_lowest_open_row():
    board = Board()

    result = board.drop_marker(3, "X")

    assert result is True
    assert board.grid[5][3] == "X"


def test_drop_marker_stacks_markers_in_column():
    board = Board()

    board.drop_marker(3, "X")
    board.drop_marker(3, "O")

    assert board.grid[5][3] == "X"
    assert board.grid[4][3] == "O"


def test_drop_marker_rejects_out_of_bounds_column():
    board = Board()

    assert board.drop_marker(-1, "X") is False
    assert board.drop_marker(7, "X") is False


def test_drop_marker_rejects_full_column():
    board = Board()

    for _ in range(6):
        assert board.drop_marker(0, "X") is True

    assert board.drop_marker(0, "O") is False


def test_legal_moves_excludes_full_columns():
    board = Board()

    for _ in range(6):
        board.drop_marker(0, "X")

    assert 0 not in board.legal_moves()
    assert board.legal_moves() == [1, 2, 3, 4, 5, 6]


def test_legal_moves_empty_board():
    board = Board()

    assert board.legal_moves() == [0, 1, 2, 3, 4, 5, 6]


def test_horizontal_winner():
    board = Board()
    board.grid[5][0] = "X"
    board.grid[5][1] = "X"
    board.grid[5][2] = "X"
    board.grid[5][3] = "X"

    assert board.winner() == "X"


def test_vertical_winner():
    board = Board()
    board.grid[5][2] = "O"
    board.grid[4][2] = "O"
    board.grid[3][2] = "O"
    board.grid[2][2] = "O"

    assert board.winner() == "O"


def test_down_right_diagonal_winner():
    board = Board()
    board.grid[2][1] = "X"
    board.grid[3][2] = "X"
    board.grid[4][3] = "X"
    board.grid[5][4] = "X"

    assert board.winner() == "X"


def test_down_left_diagonal_winner():
    board = Board()
    board.grid[2][4] = "O"
    board.grid[3][3] = "O"
    board.grid[4][2] = "O"
    board.grid[5][1] = "O"

    assert board.winner() == "O"


def test_no_winner():
    board = Board()

    assert board.winner() is None


def test_draw_when_full_board_has_no_winner():
    board = Board()
    board.grid = [
        ["X", "X", "O", "O", "X", "X", "O"],
        ["O", "O", "X", "X", "O", "O", "X"],
        ["X", "X", "O", "O", "X", "X", "O"],
        ["O", "O", "X", "X", "O", "O", "X"],
        ["X", "X", "O", "O", "X", "X", "O"],
        ["O", "O", "X", "X", "O", "O", "X"],
    ]

    assert board.is_draw() is True
    assert board.is_game_over() is True


def test_game_over_when_winner_exists():
    board = Board()
    board.grid[5][0] = "X"
    board.grid[5][1] = "X"
    board.grid[5][2] = "X"
    board.grid[5][3] = "X"

    assert board.is_game_over() is True


def test_game_not_over_when_moves_left_and_no_winner():
    board = Board()
    board.drop_marker(0, "X")
    board.drop_marker(1, "O")

    assert board.is_draw() is False
    assert board.is_game_over() is False
