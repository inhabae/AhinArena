# Connect Four Engine and Referee

The local Connect Four engine runs two bot processes, assigns one to `X` and one to `O`, and uses the shared referee to enforce game rules.

Connect Four-specific engine code lives under `engine/connectfour/`. Shared match-running infrastructure remains under `engine/`.

## Referee and Bot Communication

Each bot is started as a persistent subprocess. The referee sends one JSON object per turn to the active bot on `stdin`, followed by a newline. The bot must respond with one JSON object on `stdout`, also followed by a newline.

Bots do not call engine APIs directly. Their public interface is line-delimited JSON over standard input and output.

## Game State Sent to Bots

On each turn, the referee sends:

```json
{
  "marker": "X",
  "board": [
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", "X", " ", " ", " "],
    ["O", " ", "X", "O", " ", " ", " "]
  ]
}
```

- `marker` is the bot's assigned marker: `"X"` or `"O"`.
- `board` is a 6x7 list of rows.
- Each cell is `"X"`, `"O"`, or `" "` for empty.
- Columns are zero-indexed from `0` through `6`.
- Row `0` is the top of the board. Row `5` is the bottom.

## Move Format Returned by Bots

Bots must return:

```json
{
  "col": 3
}
```

- `col` must be an integer.
- Valid values are `0` through `6`.
- The selected column must not be full.
- The engine drops the marker into the lowest open row in that column.

Malformed JSON, missing fields, non-integer columns, out-of-range columns, full columns, crashes, and timeouts are bot failures. The opponent wins.

## Match Lifecycle

1. The referee creates a fresh game with an empty 6x7 board and `X` to move first.
2. The referee starts both bot subprocesses.
3. While the game is not over, the referee sends the current state to the active bot.
4. The active bot returns a column.
5. The referee validates the column, drops the marker, records the move, and switches turns.
6. The match ends on a win, draw, invalid move, bot error, or timeout.
7. The referee terminates both bot processes and returns the result.

The result includes:

- `winner`: `"X"`, `"O"`, or `null` for a draw.
- `reason`: `"win"`, `"draw"`, `"invalid_move"`, `"bot_error"`, or `"timeout"`.
