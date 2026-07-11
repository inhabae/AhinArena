import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { getMatches } from "../api/client";
import { formatGame, gameFilters } from "../games";

const pageSize = 20;

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatResult(match) {
  if (match.winner_bot_name) {
    return `${match.winner_bot_name} won`;
  }

  return match.result_reason === "draw" ? "Draw" : match.result_reason;
}

function formatDelta(value) {
  if (value > 0) {
    return `+${value}`;
  }

  return String(value);
}

function getValidGame(gameId) {
  return gameFilters.some((game) => game.id === gameId) ? gameId : "";
}

function getValidOffset(value) {
  const parsed = Number.parseInt(value ?? "0", 10);

  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0;
  }

  return Math.floor(parsed / pageSize) * pageSize;
}

export default function MatchHistoryPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedGame = getValidGame(searchParams.get("game") ?? "");
  const offset = getValidOffset(searchParams.get("offset"));
  const [matchesState, setMatchesState] = useState({
    loading: true,
    items: [],
    total: 0,
    error: null,
  });

  useEffect(() => {
    let ignore = false;

    setMatchesState((current) => ({
      loading: true,
      items: current.items,
      total: current.total,
      error: null,
    }));

    getMatches({
      game_id: selectedGame,
      limit: pageSize,
      offset,
    })
      .then((data) => {
        if (!ignore) {
          setMatchesState({
            loading: false,
            items: data.items,
            total: data.total,
            error: null,
          });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setMatchesState({
            loading: false,
            items: [],
            total: 0,
            error,
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedGame, offset]);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(matchesState.total / pageSize));
  const rangeText = useMemo(() => {
    if (matchesState.total === 0) {
      return "No matches";
    }

    const start = offset + 1;
    const end = Math.min(offset + pageSize, matchesState.total);

    return `${start}-${end} of ${matchesState.total}`;
  }, [matchesState.total, offset]);
  const isPreviousDisabled = offset === 0 || matchesState.loading;
  const isNextDisabled =
    matchesState.loading || offset + pageSize >= matchesState.total;

  function updateParams(nextGame, nextOffset) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);

      if (nextGame) {
        next.set("game", nextGame);
      } else {
        next.delete("game");
      }

      if (nextOffset > 0) {
        next.set("offset", String(nextOffset));
      } else {
        next.delete("offset");
      }

      return next;
    });
  }

  function handleGameChange(gameId) {
    updateParams(gameId, 0);
  }

  function handlePreviousPage() {
    updateParams(selectedGame, Math.max(0, offset - pageSize));
  }

  function handleNextPage() {
    updateParams(selectedGame, offset + pageSize);
  }

  return (
    <main className="match-history-page">
      <div className="page-header">
        <h1>Match history</h1>
        <p>Browse completed arena matches across all supported games.</p>
      </div>

      <div className="game-tabs" role="tablist" aria-label="Filter matches by game">
        {gameFilters.map((game) => (
          <button
            key={game.label}
            type="button"
            role="tab"
            aria-selected={selectedGame === game.id}
            className={selectedGame === game.id ? "game-tab active" : "game-tab"}
            onClick={() => handleGameChange(game.id)}
          >
            {game.label}
          </button>
        ))}
      </div>

      <section className="history-panel">
        <div className="section-heading">
          <h2>Persisted matches</h2>
          <span>{matchesState.loading ? "Loading..." : rangeText}</span>
        </div>

        {matchesState.error && (
          <p className="error" role="alert">
            Could not load matches: {matchesState.error.message}
          </p>
        )}

        {!matchesState.error && !matchesState.loading && matchesState.items.length === 0 && (
          <p className="empty-state">No matches found for this filter.</p>
        )}

        {matchesState.items.length > 0 && (
          <div className="table-scroll">
            <table className="match-history-table">
              <thead>
                <tr>
                  <th scope="col">Game</th>
                  <th scope="col">Players</th>
                  <th scope="col">Result</th>
                  <th scope="col">Rating change</th>
                  <th scope="col">Completed date</th>
                </tr>
              </thead>
              <tbody>
                {matchesState.items.map((match) => (
                  <tr
                    key={match.match_id}
                    className="clickable-row"
                    tabIndex={0}
                    onClick={() => navigate(`/matches/${match.match_id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/matches/${match.match_id}`);
                      }
                    }}
                  >
                    <td>{formatGame(match.game)}</td>
                    <td>
                      <span className="players-cell">
                        <span
                          className={
                            match.winner_bot_id === match.bot_one_id
                              ? "winner-name"
                              : undefined
                          }
                        >
                          {match.bot_one_name} ({match.bot_one_rating_before})
                        </span>
                        <span aria-hidden="true">vs</span>
                        <span
                          className={
                            match.winner_bot_id === match.bot_two_id
                              ? "winner-name"
                              : undefined
                          }
                        >
                          {match.bot_two_name} ({match.bot_two_rating_before})
                        </span>
                      </span>
                    </td>
                    <td>{formatResult(match)}</td>
                    <td>
                      <span className="rating-delta">
                        <span>{formatDelta(match.bot_one_rating_delta)}</span>
                        <span>{formatDelta(match.bot_two_rating_delta)}</span>
                      </span>
                    </td>
                    <td>{formatDate(match.completed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls" aria-label="Match history pagination">
          <button
            type="button"
            onClick={handlePreviousPage}
            disabled={isPreviousDisabled}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button type="button" onClick={handleNextPage} disabled={isNextDisabled}>
            Next
          </button>
        </div>
      </section>
    </main>
  );
}
