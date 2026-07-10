from engine.referee import Referee


def _slot_from_player_id(game_cls):
    first, second = game_cls.players
    return {first: "p1", second: "p2"}


def _translate_result(result, slot_from_player_id):
    return {
        **result,
        "winner": (
            None
            if result["winner"] is None
            else slot_from_player_id[result["winner"]]
        ),
    }


def run_match(
    game_cls,
    default_bot_command,
    p1_command=None,
    p2_command=None,
    timeout=2.0,
    on_move=None,
):
    p1_command = p1_command or default_bot_command
    p2_command = p2_command or default_bot_command

    slot_from_player_id = _slot_from_player_id(game_cls)
    first_player_id, second_player_id = game_cls.players

    translated_on_move = None
    if on_move is not None:
        def translated_on_move(player_id, move, board):
            on_move(slot_from_player_id[player_id], move, board)

    referee = Referee(
        {
            first_player_id: p1_command,
            second_player_id: p2_command,
        },
        game_cls(),
        timeout=timeout,
        on_move=translated_on_move,
    )

    return _translate_result(referee.run_match(), slot_from_player_id)