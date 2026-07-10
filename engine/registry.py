import sys


class UnknownBotError(Exception):
    pass


class BotRegistry:
    def __init__(self):
        self._bots = {}

    def register(self, bot_id, command, game="tictactoe"):
        self._bots[(game, bot_id)] = command

    def get_command(self, bot_id, game="tictactoe"):
        key = (game, bot_id)

        if key not in self._bots:
            raise UnknownBotError(f"Unknown bot: {bot_id}")

        return self._bots[key]


bot_registry = BotRegistry()

for bot_name in ("random", "randombot1", "randombot2"):
    bot_registry.register(
        bot_name,
        [sys.executable, "-m", "engine.tictactoe.random_bot"],
        game="tictactoe",
    )

    bot_registry.register(
        bot_name,
        [sys.executable, "-m", "engine.connectfour.random_bot"],
        game="connect-four",
    )
