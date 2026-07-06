import sys


class UnknownBotError(Exception):
    pass


class BotRegistry:
    def __init__(self):
        self._bots = {}

    def register(self, bot_id, command):
        self._bots[bot_id] = command

    def get_command(self, bot_id):
        if bot_id not in self._bots:
            raise UnknownBotError(f"Unknown bot: {bot_id}")

        return self._bots[bot_id]


bot_registry = BotRegistry()

bot_registry.register(
    "random",
    [sys.executable, "-m", "engine.tictactoe.random_bot"],
)