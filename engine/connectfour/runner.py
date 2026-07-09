import sys

from engine.connectfour import Game
from engine.referee import Referee


DEFAULT_BOT_COMMAND = [sys.executable, "-m", "engine.connectfour.random_bot"]


PLAYER_FROM_MARKER = {
    "X": "p1",
    "O": "p2",
}


def _translate_result(result):
    return {
        **result,
        "winner": None if result["winner"] is None else PLAYER_FROM_MARKER[result["winner"]],
    }


def run_connectfour_match(
    p1_command=None,
    p2_command=None,
    timeout=2.0,
    on_move=None,
):
    p1_command = p1_command or DEFAULT_BOT_COMMAND
    p2_command = p2_command or DEFAULT_BOT_COMMAND

    translated_on_move = None
    if on_move is not None:
        def translated_on_move(player, move, board):
            on_move(PLAYER_FROM_MARKER[player], move, board)

    referee = Referee(
        {
            "X": p1_command,
            "O": p2_command,
        },
        Game(),
        timeout=timeout,
        on_move=translated_on_move,
    )

    return _translate_result(referee.run_match())
