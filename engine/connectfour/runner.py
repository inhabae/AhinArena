from pathlib import Path

from engine.connectfour import Game
from engine.runner import run_match


DEFAULT_BOT_COMMAND = [
    str(Path(__file__).resolve().parents[2] / "build" / "default-bots" / "connect-four")
]


def run_connectfour_match(
    p1_command=None,
    p2_command=None,
    timeout=2.0,
    startup_timeout=None,
    on_move=None,
):
    return run_match(
        Game,
        DEFAULT_BOT_COMMAND,
        p1_command=p1_command,
        p2_command=p2_command,
        timeout=timeout,
        startup_timeout=startup_timeout,
        on_move=on_move,
    )
