from engine.tictactoe import Board

def test_new_board_is_empty():
    board = Board()

    assert board.grid == [
        [" ", " ", " "],
        [" ", " ", " "],
        [" ", " ", " "],
    ]

def test_apply_valid_move():
    board = Board()

    result = board.place_marker(0, 0, "X")

    assert result is True
    assert board.grid[0][0] == "X"

def test_apply_move_out_of_bounds():
    board = Board()

    assert board.place_marker(-1, 0, "X") is False
    assert board.place_marker(3, 0, "X") is False
    assert board.place_marker(0, 3, "X") is False


def test_apply_move_on_taken_cell():
    board = Board()
    board.place_marker(0, 0, "X")

    result = board.place_marker(0, 0, "O")

    assert result is False
    assert board.grid[0][0] == "X"

def test_legal_moves():
    board = Board()
    board.place_marker(0, 0, "X")

    assert (0, 0) not in board.legal_moves()
    assert (0, 1) in board.legal_moves()
    assert len(board.legal_moves()) == 8

def test_legal_moves_full_board():
    board = Board()

    board.grid = [
        ["X", "O", "X"],
        ["X", "O", "O"],
        ["O", "X", "X"],
    ]

    assert board.legal_moves() == []

def test_row_winner():
    board = Board()
    board.grid = [
        ["X", "X", "X"],
        ["O", " ", " "],
        [" ", "O", " "],
    ]

    assert board.winner() == "X"

def test_column_winner():
    board = Board()
    board.grid = [
        ["O", " ", " "],
        ["O", "X", "X"],
        ["O", " ", "X"],
    ]

    assert board.winner() == "O"

def test_diagonal_winner():
    board = Board()
    board.grid = [
        ["X", "O", "O"],
        [" ", "X", " "],
        [" ", " ", "X"],
    ]

    assert board.winner() == "X"

def test_no_winner():
    board = Board()

    assert board.winner() is None

def test_draw():
    board = Board()
    board.grid = [
        ["X", "O", "X"],
        ["X", "O", "O"],
        ["O", "X", "X"],
    ]

    assert board.is_draw() is True
    assert board.is_game_over() is True

def test_game_over_when_winner_exists():
    board = Board()
    board.grid = [
        ["X", "X", "X"],
        ["O", " ", "O"],
        [" ", " ", " "],
    ]

    assert board.is_game_over() is True

def test_game_not_over_when_moves_left_and_no_winner():
    board = Board()
    board.grid = [
        ["X", "O", "X"],
        [" ", "O", " "],
        [" ", "X", " "],
    ]

    assert board.is_draw() is False
    assert board.is_game_over() is False
