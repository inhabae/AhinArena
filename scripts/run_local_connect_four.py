import argparse
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.connectfour.runner import run_connectfour_match


DEFAULT_BOT_COMMAND = ["build/default-bots/connect-four"]


def format_board(grid):
    rows = []

    for row in grid:
        rows.append(" | ".join(cell if cell != " " else "." for cell in row))

    column_labels = "   ".join(str(column) for column in range(len(grid[0])))
    return "\n".join(rows + [column_labels])


def run_local_match(x_command=None, o_command=None, timeout=2.0, output=None):
    output = output or sys.stdout
    x_command = x_command or DEFAULT_BOT_COMMAND
    o_command = o_command or DEFAULT_BOT_COMMAND

    print("Starting local Connect Four match: X bot vs O bot", file=output)

    move_count = 0

    def print_move(marker, move, board):
        nonlocal move_count
        move_count += 1
        print(
            f"\nMove {move_count}: {marker} -> column {move}",
            file=output,
        )
        print(format_board(board), file=output)

    result = run_connectfour_match(
        p1_command=x_command,
        p2_command=o_command,
        timeout=timeout,
        on_move=print_move,
    )

    print("\nFinal result", file=output)

    if result["winner"] is None:
        print(f"Draw ({result['reason']})", file=output)
    else:
        print(f"Winner: {result['winner']} ({result['reason']})", file=output)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run a full local Connect Four match between two bots."
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
