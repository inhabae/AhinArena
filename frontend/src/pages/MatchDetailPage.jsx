import {
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { getMatch } from "../api/client";
import {
  buildConnectFourReplay,
  buildTicTacToeReplay,
} from "./matchReplay";

const games = [
  { id: "tictactoe", label: "Tic Tac Toe" },
  { id: "connect-four", label: "Connect Four" },
];

const nonStandardEndings = new Set(["timeout", "bot_error", "invalid_move"]);

function formatGame(gameId) {
  return games.find((game) => game.id === gameId)?.label ?? gameId;
}

function formatDelta(value) {
  if (value > 0) {
    return `+${value}`;
  }

  return String(value);
}

function formatResult(match) {
  if (match.winner_bot_name) {
    return `${match.winner_bot_name} won`;
  }

  return match.result_reason === "draw" ? "Draw" : match.result_reason;
}

function formatReason(reason) {
  return reason.replaceAll("_", " ");
}

function getErrorMessage(error) {
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
  return (
    <div className="match-rating-line">
      <span>{label}</span>
      <strong>
        {before} &rarr; {after}
      </strong>
      <em className={deltaClassName}>{formatDelta(delta)}</em>
    </div>
  );
}

function PlayerSummary({
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
      <strong>{name}</strong>
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

function TicTacToeBoard({ board, lastMove }) {
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

function ConnectFourBoard({ board, lastMove }) {
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

function MatchBoard({ game, board, lastMove }) {
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
  const { matchId } = useParams();
  const [matchState, setMatchState] = useState({
    loading: true,
    data: null,
    error: null,
  });
  const [step, setStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let ignore = false;

    setMatchState({ loading: true, data: null, error: null });
    setStep(0);
    setIsPlaying(false);

    getMatch(matchId)
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
  }, [matchId]);

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
    if (!isPlaying) {
      return undefined;
    }

    if (step >= maxStep) {
      setIsPlaying(false);
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setStep((currentStep) => {
        if (currentStep >= maxStep) {
          setIsPlaying(false);
          return currentStep;
        }

        const nextStep = currentStep + 1;

        if (nextStep >= maxStep) {
          setIsPlaying(false);
        }

        return nextStep;
      });
    }, 800);

    return () => window.clearInterval(intervalId);
  }, [isPlaying, maxStep, step]);

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

  if (match.game !== "tictactoe" && match.game !== "connect-four") {
    return (
      <main className="match-detail-page">
        <div className="page-header">
          <h1>Match replay</h1>
          <p>{formatGame(match.game)}</p>
        </div>

        <section className="history-panel">
          <div className="section-heading">
            <h2>{match.bot_one_name} vs {match.bot_two_name}</h2>
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
    step === maxStep && nonStandardEndings.has(match.result_reason);

  return (
    <main className="match-detail-page">
      <div className="page-header">
        <h1>{match.bot_one_name} vs {match.bot_two_name}</h1>
        <p>{formatGame(match.game)} match #{match.match_id}</p>
      </div>

      <section className="history-panel match-replay-panel">
        <div className="section-heading match-detail-heading">
          <div>
            <h2>Replay</h2>
            <span>Move {step} of {maxStep}</span>
          </div>
          <span className="result-badge">{formatResult(match)}</span>
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

            <div className="replay-controls" aria-label="Replay controls">
              <button type="button" onClick={() => setStep(0)} disabled={step === 0}>
                &lt;&lt;
              </button>
              <button
                type="button"
                onClick={() => setStep((currentStep) => Math.max(0, currentStep - 1))}
                disabled={step === 0}
              >
                &lt;
              </button>
              <button
                type="button"
                aria-label={isPlaying ? "Pause replay" : "Play replay"}
                onClick={() => setIsPlaying((current) => !current)}
                disabled={maxStep === 0 || (step === maxStep && !isPlaying)}
              >
                {isPlaying ? (
                  <IconPlayerPauseFilled size={16} aria-hidden="true" />
                ) : (
                  <IconPlayerPlayFilled size={16} aria-hidden="true" />
                )}
              </button>
              <button
                type="button"
                onClick={() =>
                  setStep((currentStep) => Math.min(maxStep, currentStep + 1))
                }
                disabled={step === maxStep}
              >
                &gt;
              </button>
              <button
                type="button"
                onClick={() => setStep(maxStep)}
                disabled={step === maxStep}
              >
                &gt;&gt;
              </button>
            </div>

            <label className="replay-scrubber">
              <span>Move</span>
              <input
                type="range"
                min="0"
                max={maxStep}
                value={step}
                onChange={(event) => {
                  setIsPlaying(false);
                  setStep(Number.parseInt(event.target.value, 10));
                }}
              />
            </label>
          </div>

          <aside className="match-summary-panel">
            <PlayerSummary
              game={match.game}
              marker="X"
              name={match.bot_one_name}
              before={match.bot_one_rating_before}
              after={match.bot_one_rating_after}
              delta={match.bot_one_rating_delta}
              deltaClassName={getDeltaClassName(match, match.bot_one_rating_delta)}
            />
            <PlayerSummary
              game={match.game}
              marker="O"
              name={match.bot_two_name}
              before={match.bot_two_rating_before}
              after={match.bot_two_rating_after}
              delta={match.bot_two_rating_delta}
              deltaClassName={getDeltaClassName(match, match.bot_two_rating_delta)}
            />

            <div className="move-history">
              <h3>Move history</h3>
              {moves.length === 0 ? (
                <p className="empty-state">No moves recorded.</p>
              ) : (
                <ol>
                  {moves.map((entry, index) => {
                    const marker = index % 2 === 0 ? "X" : "O";
                    const botName = marker === "X" ? match.bot_one_name : match.bot_two_name;

                    return (
                      <li
                        key={entry.move_number}
                        className={step === entry.move_number ? "active-move" : undefined}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            setIsPlaying(false);
                            setStep(entry.move_number);
                          }}
                        >
                          <span>{entry.move_number}</span>
                          <strong>{marker}</strong>
                          <em>{botName}</em>
                          <code>{formatMove(match.game, entry.move)}</code>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
