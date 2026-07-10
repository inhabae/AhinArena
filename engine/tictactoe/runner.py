import sys

from engine.tictactoe import Game
from engine.runner import run_match


DEFAULT_BOT_COMMAND = [sys.executable, "-m", "engine.tictactoe.random_bot"]


def run_tictactoe_match(p1_command=None, p2_command=None, timeout=2.0, on_move=None):
    return run_match(
        Game,
        DEFAULT_BOT_COMMAND,
        p1_command=p1_command,
        p2_command=p2_command,
        timeout=timeout,
        on_move=on_move,
    )
