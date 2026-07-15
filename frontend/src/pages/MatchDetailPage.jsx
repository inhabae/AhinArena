import {
  IconChevronLeft,
  IconChevronRight,
  IconPlayerTrackNextFilled,
  IconPlayerTrackPrevFilled,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getLiveMatchJob, getMatch } from "../api/client";
import { formatGame, isSupportedGame } from "../games";
import {
  buildConnectFourReplay,
  buildTicTacToeReplay,
} from "./matchReplay";

const nonStandardEndings = new Set(["timeout", "bot_error", "invalid_move"]);

function formatDelta(value) {
  if (value > 0) {
    return `+${value}`;
  }

  if (value < 0) {
    return `- ${Math.abs(value)}`;
  }

  return String(value);
}

function formatResult(match) {
  if (match.winner_bot_name) {
    return `${match.winner_bot_name} won`;
  }

  if (!match.result_reason) {
    if (match.status === "failed") {
      return "Failed";
    }

    return match.status === "queued" ? "Queued" : "Live";
  }

  return match.result_reason === "draw" ? "Draw" : match.result_reason;
}

function formatReason(reason) {
  return reason.replaceAll("_", " ");
}

function getErrorMessage(error) {
  if (error.status === 404 || error.code === "match_job_not_found") {
    return "Match job not found.";
  }

  if (error.status === 404 || error.code === "match_not_found") {
    return "Match not found.";
  }

  return error.message || "The match could not be loaded.";
}

function getBotName(match, botId) {
  if (botId === match.bot_one_id) {
    return match.bot_one_name;
  }

  if (botId === match.bot_two_id) {
    return match.bot_two_name;
  }

  return "Unknown bot";
}

function getForfeitingBot(match) {
  const losingBotId =
    match.winner_bot_id === match.bot_one_id ? match.bot_two_id : match.bot_one_id;

  return getBotName(match, losingBotId);
}

function getDeltaClassName(match, delta) {
  if (match.result_reason === "draw" || delta === 0) {
    return undefined;
  }

  return delta > 0 ? "positive-delta" : "negative-delta";
}

function RatingLine({ label, before, after, delta, deltaClassName }) {
  if (before === undefined || after === undefined || delta === undefined) {
    return null;
  }

  return (
    <div className="match-rating-line">
      <span>{label}</span>
      <strong>{before}</strong>
      <span aria-hidden="true">&rarr;</span>
      <strong>{after}</strong>
      <em className={deltaClassName}>{formatDelta(delta)}</em>
    </div>
  );
}

function PlayerSummary({
  botId,
  game,
  marker,
  name,
  before,
  after,
  delta,
  deltaClassName,
}) {
  return (
    <div className="player-summary-row">
      <span className={`marker-pill ${game}-marker-${marker.toLowerCase()}`}>
        {marker}
      </span>
      <strong>
        <Link className="bot-name-link" to={`/bots/${botId}`}>
          {name}
        </Link>
      </strong>
      <RatingLine
        label="Rating"
        before={before}
        after={after}
        delta={delta}
        deltaClassName={deltaClassName}
      />
    </div>
  );
}

export function TicTacToeBoard({ board, lastMove }) {
  return (
    <div className="tictactoe-board" role="grid" aria-label="Tic Tac Toe board">
      {board.map((row, rowIndex) =>
        row.map((cell, colIndex) => {
          const isLastMove = lastMove?.row === rowIndex && lastMove?.col === colIndex;
          const markerClass = cell
            ? ` tictactoe-marker-${cell.toLowerCase()}`
            : " marker-empty";

          return (
            <div
              key={`${rowIndex}-${colIndex}`}
              role="gridcell"
              aria-label={`Row ${rowIndex + 1}, column ${colIndex + 1}: ${cell ?? "empty"}`}
              className={
                isLastMove
                  ? `tictactoe-cell last-move${markerClass}`
                  : `tictactoe-cell${markerClass}`
              }
            >
              {cell}
            </div>
          );
        }),
      )}
    </div>
  );
}

export function ConnectFourBoard({ board, lastMove }) {
  return (
    <div className="connect-four-board" role="grid" aria-label="Connect Four board">
      {board.map((row, rowIndex) =>
        row.map((cell, colIndex) => {
          const isLastMove = lastMove?.row === rowIndex && lastMove?.col === colIndex;
          const markerClass = cell
            ? ` connect-four-marker-${cell.toLowerCase()}`
            : " marker-empty";

          return (
            <div
              key={`${rowIndex}-${colIndex}`}
              role="gridcell"
              aria-label={`Row ${rowIndex + 1}, column ${colIndex + 1}: ${cell ?? "empty"}`}
              className={
                isLastMove
                  ? `connect-four-cell last-move${markerClass}`
                  : `connect-four-cell${markerClass}`
              }
            >
              <span aria-hidden="true" />
            </div>
          );
        }),
      )}
    </div>
  );
}

export function MatchBoard({ game, board, lastMove }) {
  if (game === "connect-four") {
    return <ConnectFourBoard board={board} lastMove={lastMove} />;
  }

  return <TicTacToeBoard board={board} lastMove={lastMove} />;
}

function formatMove(game, move) {
  if (game === "connect-four") {
    const col = typeof move === "number" ? move : move.col;
    return `c${col + 1}`;
  }

  const row = Array.isArray(move) ? move[0] : move.row;
  const col = Array.isArray(move) ? move[1] : move.col;

  return `r${row + 1}, c${col + 1}`;
}

export default function MatchDetailPage() {
  const { jobId, matchId } = useParams();
  const isLiveJob = Boolean(jobId);
  const [matchState, setMatchState] = useState({
    loading: true,
    data: null,
    error: null,
  });
  const [step, setStep] = useState(0);

  useEffect(() => {
    let ignore = false;

    setMatchState({ loading: true, data: null, error: null });
    setStep(0);

    const loadMatch = isLiveJob ? getLiveMatchJob(jobId) : getMatch(matchId);

    loadMatch
      .then((data) => {
        if (!ignore) {
          setMatchState({ loading: false, data, error: null });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setMatchState({ loading: false, data: null, error });
        }
      });

    return () => {
      ignore = true;
    };
  }, [isLiveJob, jobId, matchId]);

  useEffect(() => {
    if (
      !isLiveJob ||
      !matchState.data ||
      !["queued", "running"].includes(matchState.data.status)
    ) {
      return undefined;
    }

    let ignore = false;

    async function pollLiveJob() {
      try {
        const data = await getLiveMatchJob(jobId);

        if (!ignore) {
          setMatchState({ loading: false, data, error: null });
        }
      } catch (error) {
        if (!ignore) {
          setMatchState((current) => ({ ...current, error }));
        }
      }
    }

    const intervalId = window.setInterval(pollLiveJob, 1500);

    return () => {
      ignore = true;
      window.clearInterval(intervalId);
    };
  }, [isLiveJob, jobId, matchState.data]);

  const match = matchState.data;
  const moves = match?.moves;
  const { boards, lastMoves } = useMemo(() => {
    if (match?.game === "tictactoe") {
      return buildTicTacToeReplay(match.moves ?? []);
    }

    if (match?.game === "connect-four") {
      return buildConnectFourReplay(match.moves ?? []);
    }

    return { boards: [], lastMoves: [] };
  }, [match?.game, match?.moves]);
  const maxStep = moves?.length ?? 0;

  useEffect(() => {
    if (isLiveJob) {
      setStep(maxStep);
    }
  }, [isLiveJob, maxStep]);

  useEffect(() => {
    function handleReplayKeyDown(event) {
      if (
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLSelectElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target?.isContentEditable
      ) {
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setStep(0);
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        setStep(maxStep);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        setStep((currentStep) => Math.max(0, currentStep - 1));
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        setStep((currentStep) => Math.min(maxStep, currentStep + 1));
      }
    }

    window.addEventListener("keydown", handleReplayKeyDown);

    return () => {
      window.removeEventListener("keydown", handleReplayKeyDown);
    };
  }, [maxStep]);

  if (matchState.loading) {
    return (
      <main className="match-detail-page">
        <div className="page-header">
          <h1>Match replay</h1>
          <p>Loading match...</p>
        </div>
      </main>
    );
  }

  if (matchState.error) {
    return (
      <main className="match-detail-page">
        <div className="page-header">
          <h1>Match replay</h1>
        </div>
        <p className="error" role="alert">
          {getErrorMessage(matchState.error)}
        </p>
      </main>
    );
  }

  if (!isSupportedGame(match.game)) {
    return (
      <main className="match-detail-page">
        <div className="page-header">
          <h1>Match replay</h1>
          <p>{formatGame(match.game)}</p>
        </div>

        <section className="history-panel">
          <div className="section-heading">
            <h2>
              <Link className="bot-name-link" to={`/bots/${match.bot_one_id}`}>
                {match.bot_one_name}
              </Link>{" "}
              vs{" "}
              <Link className="bot-name-link" to={`/bots/${match.bot_two_id}`}>
                {match.bot_two_name}
              </Link>
            </h2>
            <span>{formatResult(match)}</span>
          </div>
          <p className="empty-state">Replay for this game isn't supported yet.</p>
        </section>
      </main>
    );
  }

  const board = boards[step];
  const lastMove = lastMoves[step];
  const showEndingBanner =
    step === maxStep && match.result_reason && nonStandardEndings.has(match.result_reason);

  return (
    <main className="match-detail-page">
      <div className="page-header match-viewer-header">
        <Link className="match-viewer-back-link" to="/matches">
          &larr; Back to matches
        </Link>
        <h1>{isLiveJob ? "Live Match" : "Match Replay"}</h1>
        <p>
          {match.bot_one_name} vs {match.bot_two_name} &middot; {formatGame(match.game)}
        </p>
      </div>

      <section className="history-panel match-replay-panel">
        <div className="match-summary-panel">
          <PlayerSummary
            botId={match.bot_one_id}
            game={match.game}
            marker="X"
            name={match.bot_one_name}
            before={match.bot_one_rating_before}
            after={match.bot_one_rating_after}
            delta={match.bot_one_rating_delta}
            deltaClassName={getDeltaClassName(match, match.bot_one_rating_delta)}
          />
          <PlayerSummary
            botId={match.bot_two_id}
            game={match.game}
            marker="O"
            name={match.bot_two_name}
            before={match.bot_two_rating_before}
            after={match.bot_two_rating_after}
            delta={match.bot_two_rating_delta}
            deltaClassName={getDeltaClassName(match, match.bot_two_rating_delta)}
          />
        </div>

        <div className="match-detail-grid">
          <div className="replay-board-panel">
            {showEndingBanner && (
              <div className="ending-banner" role="status">
                <strong>{formatReason(match.result_reason)}</strong>
                <span>
                  {getForfeitingBot(match)} caused the match to end by{" "}
                  {formatReason(match.result_reason)}.
                </span>
              </div>
            )}

            <MatchBoard game={match.game} board={board} lastMove={lastMove} />
          </div>

          <aside className="match-side-panel">
            <div className="move-history">
              <h3>Moves</h3>
              {moves.length === 0 ? (
                <p className="empty-state">No moves recorded.</p>
              ) : (
                <ol>
                  {moves.map((entry) => (
                    <li
                      key={entry.move_number}
                      className={step === entry.move_number ? "active-move" : undefined}
                    >
                      <button
                        type="button"
                        onClick={() => setStep(entry.move_number)}
                      >
                        <span>{entry.move_number}</span>
                        <code>{formatMove(match.game, entry.move)}</code>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <div className="replay-controls" aria-label="Replay controls">
              <button
                type="button"
                aria-label="Go to first move"
                onClick={() => setStep(0)}
                disabled={step === 0}
              >
                <IconPlayerTrackPrevFilled size={16} aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Go to previous move"
                onClick={() => setStep((currentStep) => Math.max(0, currentStep - 1))}
                disabled={step === 0}
              >
                <IconChevronLeft size={18} aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Go to next move"
                onClick={() =>
                  setStep((currentStep) => Math.min(maxStep, currentStep + 1))
                }
                disabled={step === maxStep}
              >
                <IconChevronRight size={18} aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Go to last move"
                onClick={() => setStep(maxStep)}
                disabled={step === maxStep}
              >
                <IconPlayerTrackNextFilled size={16} aria-hidden="true" />
              </button>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
