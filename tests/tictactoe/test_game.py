from engine.tictactoe import Game

def test_new_game_starts_with_x():
    game = Game()

    assert game.current_player == "X"

def test_make_valid_move_places_x_first():
    game = Game()

    result = game.make_move(0, 0)

    assert result is True
    assert game.board.grid[0][0] == "X"

def test_make_move_switches_player_after_valid_move():
    game = Game()

    game.make_move(0, 0)

    assert game.current_player == "O"

def test_second_valid_move_places_o():
    game = Game()

    game.make_move(0, 0)
    game.make_move(1, 1)

    assert game.board.grid[1][1] == "O"

def test_invalid_move_does_not_switch_player():
    game = Game()

    game.make_move(0, 0)
    result = game.make_move(0, 0)

    assert result is False
    assert game.current_player == "O"

def test_players_alternate_correctly():
    game = Game()

    game.make_move(0, 0)  # X
    game.make_move(0, 1)  # O
    game.make_move(1, 1)  # X

    assert game.board.grid[0][0] == "X"
    assert game.board.grid[0][1] == "O"
    assert game.board.grid[1][1] == "X"
    assert game.current_player == "O"

def test_game_over_after_winner():
    game = Game()

    game.make_move(0, 0)  # X
    game.make_move(1, 0)  # O
    game.make_move(0, 1)  # X
    game.make_move(1, 1)  # O
    game.make_move(0, 2)  # X wins

    assert game.board.winner() == "X"
    assert game.board.is_game_over() is True


def test_parse_move_rejects_boolean_coordinates():
    game = Game()

    assert game.parse_move({"row": True, "col": 1}) is None
    assert game.parse_move({"row": 1, "col": False}) is None
