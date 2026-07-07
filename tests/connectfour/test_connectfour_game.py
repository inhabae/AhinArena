from engine.connectfour import Game


def test_new_game_starts_with_x():
    game = Game()

    assert game.current_player == "X"


def test_make_valid_move_places_x_first():
    game = Game()

    result = game.make_move(2)

    assert result is True
    assert game.board.grid[5][2] == "X"


def test_make_move_switches_player_after_valid_move():
    game = Game()

    game.make_move(2)

    assert game.current_player == "O"


def test_second_valid_move_places_o():
    game = Game()

    game.make_move(2)
    game.make_move(2)

    assert game.board.grid[4][2] == "O"


def test_invalid_move_does_not_switch_player():
    game = Game()

    result = game.make_move(7)

    assert result is False
    assert game.current_player == "X"


def test_players_alternate_correctly():
    game = Game()

    game.make_move(0)
    game.make_move(1)
    game.make_move(0)

    assert game.board.grid[5][0] == "X"
    assert game.board.grid[5][1] == "O"
    assert game.board.grid[4][0] == "X"
    assert game.current_player == "O"


def test_game_over_after_winner_rejects_more_moves():
    game = Game()

    game.make_move(0)  # X
    game.make_move(1)  # O
    game.make_move(0)  # X
    game.make_move(1)  # O
    game.make_move(0)  # X
    game.make_move(1)  # O
    game.make_move(0)  # X wins

    assert game.board.winner() == "X"
    assert game.board.is_game_over() is True
    assert game.make_move(2) is False
