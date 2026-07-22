# Player Executable Submission

AhinArena accepts one statically linked Linux x86-64 ELF executable per bot
version. Source code, scripts, runtime selection, dependency installation, and
multi-file archives are not accepted.

## Build contract

The executable must be a 64-bit little-endian x86-64 ELF (`ET_EXEC` or PIE),
must not contain `PT_INTERP` or `DT_NEEDED`, and must be no larger than 10 MiB
by default. For example, C players can be built on Linux with
`cc -O2 -static -o player player.c`; Go players can use
`CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o player`.

The player remains running for a match. It reads one JSON game state per line
from stdin and writes exactly one JSON move per line to stdout. It must flush
each response. The game state and move schemas are unchanged.

## API

Both endpoints require an authenticated owner and use `multipart/form-data`:

```text
POST /bots
  game_id=tictactoe
  name=my-player
  executable=@player

POST /bots/{bot_id}/submission
  executable=@player
```

Each accepted artifact is stored as a database BLOB with its byte size,
SHA-256 digest, sanitized original filename, version, and creation time. New
submissions atomically become active. The configurable upload limit is
`MAX_BOT_EXECUTABLE_BYTES` (default 10485760).

Admission errors include `invalid_executable`, `unsupported_architecture`,
`dynamic_executable`, and `submission_too_large`. Admission validates the file
format without executing it; protocol failures are handled as bot losses when
a match runs.

Legacy source rows are removed by the migration. Their per-bot version
watermark is retained, while the bots themselves, ratings, and match history
remain. Those bots cannot enter new matches until an executable is uploaded.

## Built-in players

Deployment can supply prebuilt static artifacts in a directory selected by
`DEFAULT_BOT_EXECUTABLE_DIR`, named `tictactoe` and `connect-four`. They are
seeded as `random-tictactoe` and `random-connect-four`. Seeding leaves system
bots inactive and logs a warning if a required artifact is absent.
