import json
import random
import sys

from engine.tictactoe import Board


def main():
    for line in sys.stdin:
        state = json.loads(line)

        board = Board()
        board.grid = state["board"]
        row, col = random.choice(board.legal_moves())

        response = {
            "row": row,
            "col": col,
        }

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
