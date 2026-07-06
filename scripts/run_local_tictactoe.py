import argparse
import sys

from engine.referee import Referee


DEFAULT_BOT_COMMAND = [sys.executable, "-m", "engine.tictactoe.random_bot"]


def format_board(grid):
    rows = []

    for row in grid:
        rows.append(" | ".join(cell if cell != " " else "." for cell in row))

    return "\n---------\n".join(rows)


def run_local_match(x_command=None, o_command=None, timeout=2.0, output=None):
    output = output or sys.stdout
    x_command = x_command or DEFAULT_BOT_COMMAND
    o_command = o_command or DEFAULT_BOT_COMMAND

    print("Starting local Tic-Tac-Toe match: X bot vs O bot", file=output)

    move_count = 0

    def print_move(marker, move, board):
        nonlocal move_count
        move_count += 1
        row, col = move
        print(
            f"\nMove {move_count}: {marker} -> row {row}, col {col}",
            file=output,
        )
        print(format_board(board), file=output)

    referee = Referee(
        x_command,
        o_command,
        timeout=timeout,
        on_move=print_move,
    )
    result = referee.run_match()

    print("\nFinal result", file=output)

    if result["winner"] is None:
        print(f"Draw ({result['reason']})", file=output)
    else:
        print(f"Winner: {result['winner']} ({result['reason']})", file=output)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run a full local Tic-Tac-Toe match between two bots."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Seconds to wait for each bot move.",
    )
    args = parser.parse_args()

    run_local_match(timeout=args.timeout)


if __name__ == "__main__":
    main()
