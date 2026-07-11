import sys


class UnknownBotError(Exception):
    pass


class BotRegistry:
    def __init__(self):
        self._bots = {}

    def register(self, bot_name, command, game="tictactoe"):
        self._bots[(game, bot_name)] = command

    def get_command(self, bot_name, game="tictactoe"):
        key = (game, bot_name)

        if key not in self._bots:
            raise UnknownBotError(f"Unknown bot: {bot_name}")

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
