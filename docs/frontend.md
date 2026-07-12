# Frontend

The AhinArena frontend is a React application under `frontend/`, built with
Vite and React Router. It presents the current match and ranking workflows on
top of the FastAPI backend.

## Local Development

The frontend expects the backend API to be running locally on
`http://127.0.0.1:8000`.

```sh
cd frontend
npm install
npm run dev
```

Vite serves the app, usually at `http://localhost:5173`. In development,
`frontend/vite.config.js` proxies `/api/*` to `http://127.0.0.1:8000/*`.

## Route Map

Routes are defined in `frontend/src/App.jsx`:

- `/` renders `HomePage`.
- `/matches` renders `MatchHistoryPage`.
- `/leaderboard` renders `LeaderboardPage`.
- `/bots/new` renders `BotRegistrationPage`.
- `/login` renders `LoginPage`.
- `/register` renders `RegisterPage`.
- `/matches/:matchId` renders `MatchDetailPage`.

All routes share `AppLayout`, which provides the common application shell.

## Pages

### Home

`frontend/src/pages/HomePage.jsx` is the match start page. It lets a user select
either Tic-Tac-Toe or Connect Four, loads registered bots for that game with
`getBots`, and submits a `POST /matches` request through `createMatch`. A
successful match creation navigates directly to the persisted match detail page.
Starting a match requires an authenticated session; unauthenticated users are
sent to `/login`.

The page also loads a small recent-match list with `getMatches`, filtered to the
selected game and limited to five rows. It displays basic totals for matches
played and bots registered.

### Login and Register

`frontend/src/pages/LoginPage.jsx` posts email and password credentials through
`loginUser`. A successful login stores the session in the backend's HTTP-only
cookie and refreshes the shared auth context.

`frontend/src/pages/RegisterPage.jsx` creates an account through `registerUser`
and then sends the user to `/login`. Registration errors map backend auth error
codes such as `email_already_registered` and `username_already_taken` to form
messages.

### Bot Registration

`frontend/src/pages/BotRegistrationPage.jsx` requires an authenticated session.
It submits `POST /bots` through `createBot`, assigning the new bot to the
current user and selected supported game. After the bot is created, the page
shows a source-code textarea and submits Python code through
`submitBotCode`, which calls `POST /bots/{bot_id}/submission`. Users without a
valid session are sent to `/login`.

The page reports the accepted submission version and maps backend submission
errors such as `submission_too_large`, `invalid_syntax`, `unsupported_language`,
`bot_not_owned`, and `bot_not_found` to user-facing form messages.

### Match History

`frontend/src/pages/MatchHistoryPage.jsx` lists completed persisted matches
from `GET /matches`. It supports:

- all-game or per-game filtering through the `game` search parameter;
- fixed 20-row pages through `limit=20` and `offset`;
- previous and next pagination controls;
- result, rating change, completed date, and player rating snapshot columns;
- row activation that opens `/matches/:matchId`.

### Leaderboard

`frontend/src/pages/LeaderboardPage.jsx` displays bot rankings from
`GET /leaderboard`. A game is always selected because the backend leaderboard is
scoped by `game_id`.

The page supports configurable page sizes of 25, 50, 100, 250, and 500 rows,
stores `game`, `limit`, and `offset` in the URL, and paginates while preserving
rank numbering across offsets.

### Match Detail and Replay

`frontend/src/pages/MatchDetailPage.jsx` loads one persisted match with
`GET /matches/{match_id}`. It displays player names, result, rating before/after
values, rating deltas, and ordered move history.

For `tictactoe` and `connect-four`, the page builds replay boards from the move
history and supports:

- jump to start and end;
- previous and next move;
- play and pause with an 800 ms step interval;
- range-input scrubbing;
- direct move selection from the move history;
- last-move highlighting;
- final-state banners for timeout, bot error, and invalid move endings.

If the match uses an unsupported game ID, the page still shows the matchup and
result, then falls back to the message `Replay for this game isn't supported
yet.`

## Replay Reconstruction

Replay helpers live in `frontend/src/pages/matchReplay.js`.

Tic-Tac-Toe replay starts with an empty 3x3 board. Each move is normalized from
either `[row, col]` or `{ row, col }`, copied into a new board, and assigned an
alternating marker: `X` for even-indexed moves and `O` for odd-indexed moves.
The helper returns parallel arrays:

- `boards`, with the initial empty board at index 0 and one board after each
  move;
- `lastMoves`, with `null` at index 0 and the row/column of the move that
  produced each board.

Connect Four replay starts with an empty 6x7 board. Each move is normalized from
either a numeric column or `{ col }`. The marker is placed in the lowest empty
row for that column, matching normal Connect Four gravity. It returns the same
`boards` and `lastMoves` shape used by the match detail page.

The frontend does not currently validate legal moves while replaying. It trusts
the ordered move history persisted by the backend/referee.

## API Client Conventions

`frontend/src/api/client.js` is the single frontend API wrapper.

- `buildUrl(path, params)` prefixes every path with `/api` and omits query
  params whose values are `undefined`, `null`, or an empty string.
- `request(path, options)` sends `Accept: application/json`, parses JSON
  responses, and returns the decoded body for successful responses.
- Empty responses are represented as `null`.
- Invalid JSON raises `ApiError` with code `invalid_json`.
- Non-2xx responses are expected to use the backend error envelope. The client
  maps `error.code`, `error.message`, and `error.details` into an `ApiError`.
  If the envelope is missing, it uses `request_failed`.

Exported endpoint helpers are:

- `getHealth()` -> `GET /health`
- `getMatches(params)` -> `GET /matches`
- `getMatch(matchId)` -> `GET /matches/{matchId}`
- `createMatch(match)` -> `POST /matches`
- `getLeaderboard(params)` -> `GET /leaderboard`
- `getBots(params)` -> `GET /bots`
- `createBot(bot)` -> `POST /bots`
- `submitBotCode(botId, submission)` -> `POST /bots/{botId}/submission`
- `getCurrentUser()` -> `GET /auth/me`
- `loginUser(credentials)` -> `POST /auth/login`
- `registerUser(credentials)` -> `POST /auth/register`
- `logoutUser()` -> `POST /auth/logout`

Pages should use these helpers instead of calling `fetch` directly so error
handling and `/api` URL construction stay consistent.

Known gap: auth-aware pages use the shared session context, but the frontend
does not yet provide password reset, email verification, or full account
management screens.
