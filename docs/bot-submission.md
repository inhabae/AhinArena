# Bot Submission

Milestone 8 adds persistent Python bot submissions. Authenticated developers can
create a bot record, upload source code for that bot, and use the latest accepted
submission in matches.

## Scope

Bot submission currently covers:

- authenticated source upload for existing bots;
- ownership checks before accepting a submission;
- Python-only submission validation;
- monotonically increasing per-bot submission versions;
- an active submission pointer on each bot;
- match execution from the active submitted source;
- default source submissions for the built-in random bots.

Docker isolation, asynchronous queues, and multi-language execution are still
future milestones.

## Data Model

Bot source is stored in the `bot_submissions` table:

- `id` is the submission primary key.
- `bot_id` references the owning bot.
- `version` is unique per bot through `uq_bot_submissions_bot_id_version`.
- `language` records the submitted runtime language.
- `source_code` stores the submitted text.
- `created_at` records insertion time.

The `bots.active_submission_id` column points at the submission used for new
matches. Creating a new submission updates this pointer after the new row is
flushed successfully.

## API

Submit source code:

```http
POST /bots/{bot_id}/submission
Content-Type: application/json
Cookie: ahin_arena_session=...
```

```json
{
  "source_code": "import json\nimport sys\n\nfor line in sys.stdin:\n    state = json.loads(line)\n    print(json.dumps({\"row\": 0, \"col\": 0}), flush=True)\n",
  "language": "python"
}
```

`language` defaults to `python` when omitted. A successful request returns:

```json
{
  "bot_id": 1,
  "submission_id": 10,
  "version": 2
}
```

The endpoint requires an authenticated session and only accepts submissions for
bots owned by the current user.

## Validation

The backend rejects submissions when:

- the bot does not exist: `bot_not_found`;
- the authenticated user does not own the bot: `bot_not_owned`;
- `language` is not `python`: `unsupported_language`;
- `source_code` is empty or whitespace: `validation_error`;
- the UTF-8 source is larger than 100,000 bytes: `submission_too_large`;
- Python parsing fails through `ast.parse`: `invalid_syntax`;
- a duplicate version conflict is detected: `submission_conflict`.

Syntax validation confirms that the source parses as Python. It does not prove
that the bot follows the game protocol or behaves safely at runtime.

## Match Execution

When `POST /matches` resolves each named bot, the backend requires an active
submission. A bot without one is rejected with `bot_has_no_submission`.

For a bot with an active submission, the backend writes the source to a private
temporary file and starts a `docker run` command that bind-mounts that file
read-only at `/bot/source.py`. Each bot container is started with `--rm -i
--init`, no network access, all Linux capabilities dropped, `no-new-privileges`,
a read-only root filesystem, a small `/tmp` tmpfs, and memory, CPU, and PID
limits. Cleanup force-removes the named container and deletes the temporary
source directory, even if match execution fails.

The sandbox image and limits can be changed without code changes:

- `BOT_SANDBOX_IMAGE`
- `BOT_SANDBOX_MEMORY_LIMIT`
- `BOT_SANDBOX_CPU_LIMIT`
- `BOT_SANDBOX_PIDS_LIMIT`
- `BOT_SANDBOX_TMPFS_SIZE`
- `DOCKER_BINARY`

The existing referee still owns the game protocol. It starts each bot as a
persistent subprocess, sends line-delimited JSON states on `stdin`, and expects
line-delimited JSON moves on `stdout`. Timeouts, crashes, invalid JSON, and
illegal moves are treated as bot failures.

## Frontend Flow

`/bots/new` first creates the named bot through `POST /bots`. After creation, it
shows a source-code textarea and submits through `POST /bots/{bot_id}/submission`.
The page reports the accepted submission version and maps backend error codes to
form messages.

## Current Limitations

- Only Python is accepted.
- The UI supports initial source submission after bot creation, but it does not
yet provide a full submission history or rollback screen.
- Temporary bot source files are created for match execution and are not part of
the persisted submission history.
