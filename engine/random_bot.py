from .bot import Bot
import random

class RandomBot(Bot):
    def choose_move(self, board):
        return random.choice(board.legal_moves())