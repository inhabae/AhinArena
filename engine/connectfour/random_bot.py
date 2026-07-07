import json
import random
import sys

from engine.connectfour import Board


def main():
    for line in sys.stdin:
        state = json.loads(line)

        board = Board()
        board.grid = state["board"]
        column = random.choice(board.legal_moves())

        response = {
            "col": column,
        }

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
