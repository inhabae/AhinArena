# Tic-Tac-Toe Engine and Referee

The local Tic-Tac-Toe engine runs two bot processes, assigns one to `X` and one to `O`, and uses the referee to enforce game rules.

Tic-Tac-Toe-specific engine code lives under `engine/tictactoe/`. Shared match-running infrastructure can remain directly under `engine/`.

## Referee and Bot Communication

Each bot is started as a persistent subprocess. The referee sends one JSON object per turn to the active bot on `stdin`, followed by a newline. The bot must respond with one JSON object on `stdout`, also followed by a newline.

Bots do not call engine APIs directly. Their public interface is line-delimited JSON over standard input and output.

## Game State Sent to Bots

On each turn, the referee sends:

```json
{
  "marker": "X",
  "board": [
    ["X", " ", "O"],
    [" ", "X", " "],
    ["O", " ", " "]
  ]
}
```

- `marker` is the bot's assigned marker: `"X"` or `"O"`.
- `board` is a 3x3 list of rows.
- Each cell is `"X"`, `"O"`, or `" "` for empty.
- Rows and columns are zero-indexed.

## Move Format Returned by Bots

Bots must return:

```json
{
  "row": 0,
  "col": 1
}
```

- `row` and `col` must be integers.
- Valid values are `0`, `1`, or `2`.
- The target cell must be empty.

Malformed JSON, missing fields, non-integer coordinates, out-of-range coordinates, occupied cells, crashes, and timeouts are bot failures. The opponent wins.

## Match Lifecycle

1. The referee creates a fresh game with an empty board and `X` to move first.
2. The referee starts both bot subprocesses.
3. While the game is not over, the referee sends the current state to the active bot.
4. The active bot returns a move.
5. The referee validates and applies the move, records it, and switches turns.
6. The match ends on a win, draw, invalid move, bot error, or timeout.
7. The referee terminates both bot processes and returns the result.

The result includes:

- `winner`: `"X"`, `"O"`, or `null` for a draw.
- `reason`: `"win"`, `"draw"`, `"invalid_move"`, `"bot_error"`, or `"timeout"`.
- `moves`: accepted moves as `(marker, (row, col))` pairs.
- `final_board`: the final 3x3 board.
