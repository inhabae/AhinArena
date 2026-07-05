import pytest

from engine.bot import Bot
from engine.random_bot import RandomBot
from engine.tictactoe import Board


def test_random_bot_stores_marker():
    bot = RandomBot("X")

    assert bot.marker == "X"


def test_bot_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Bot("X")


def test_random_bot_returns_tuple_move():
    board = Board()
    bot = RandomBot("X")

    move = bot.choose_move(board)

    assert isinstance(move, tuple)
    assert len(move) == 2


def test_random_bot_returns_legal_move():
    board = Board()
    board.place_marker(0, 0, "X")

    bot = RandomBot("O")
    move = bot.choose_move(board)

    assert move in board.legal_moves()


def test_random_bot_does_not_choose_occupied_cell():
    board = Board()
    board.place_marker(0, 0, "X")

    bot = RandomBot("O")

    for _ in range(20):
        move = bot.choose_move(board)
        assert move != (0, 0)


def test_random_bot_returns_only_remaining_move():
    board = Board()
    board.grid = [
        ["X", "O", "X"],
        ["X", "O", "O"],
        ["O", "X", " "],
    ]

    bot = RandomBot("X")
    move = bot.choose_move(board)

    assert move == (2, 2)