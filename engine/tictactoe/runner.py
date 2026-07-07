import sys

from engine.referee import Referee
from engine.tictactoe import Game


DEFAULT_BOT_COMMAND = [sys.executable, "-m", "engine.tictactoe.random_bot"]


def run_tictactoe_match(p1_command=None, p2_command=None, timeout=2.0, on_move=None):
    p1_command = p1_command or DEFAULT_BOT_COMMAND
    p2_command = p2_command or DEFAULT_BOT_COMMAND

    referee = Referee(
        {
            "X": p1_command,
            "O": p2_command,
        },
        Game(),
        timeout=timeout,
        on_move=on_move,
    )

    return referee.run_match()
