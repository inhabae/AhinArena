import { IconTrophyFilled } from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getLeaderboard } from "../api/client";
import { defaultGameId, isSupportedGame, supportedGames } from "../games";

const defaultPageSize = 50;
const maxPageSize = 500;
const pageSizeOptions = [25, 50, 100, 250, 500];

function getValidGame(gameId) {
  return isSupportedGame(gameId) ? gameId : defaultGameId;
}

function clampLimit(value) {
  const parsed = Number.parseInt(value ?? String(defaultPageSize), 10);

  if (!Number.isFinite(parsed)) {
    return defaultPageSize;
  }

  return Math.min(maxPageSize, Math.max(1, parsed));
}

function getValidOffset(value, limit) {
  const parsed = Number.parseInt(value ?? "0", 10);

  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0;
  }

  return Math.floor(parsed / limit) * limit;
}

function formatWinRate(bot) {
  if (bot.games_played === 0) {
    return "0.0%";
  }

  return `${((bot.wins / bot.games_played) * 100).toFixed(1)}%`;
}

function getRecord(bot) {
  return [
    { className: "record-win", label: "wins", value: bot.wins },
    { className: "record-loss", label: "losses", value: bot.losses },
    { className: "record-draw", label: "draws", value: bot.draws },
  ];
}

function VersionedBotName({ bot }) {
  return (
    <>
      {bot.name}
      {bot.version && <span className="bot-version-suffix">v{bot.version}</span>}
    </>
  );
}

function getRangeText({ count, loading, offset, limit }) {
  if (loading) {
    return "Loading...";
  }

  if (count === 0) {
    return "No bots";
  }

  const start = offset + 1;
  const end = offset + count;
  if (count === limit) {
    return `${start}-${end} of ${end}+`;
  }

  return `${start}-${end} of ${end}`;
}

export default function LeaderboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedGame = getValidGame(searchParams.get("game"));
  const limit = clampLimit(searchParams.get("limit"));
  const offset = getValidOffset(searchParams.get("offset"), limit);
  const [leaderboardState, setLeaderboardState] = useState({
    loading: true,
    items: [],
    error: null,
  });

  useEffect(() => {
    let ignore = false;

    setLeaderboardState((current) => ({
      loading: true,
      items: current.items,
      error: null,
    }));

    getLeaderboard({
      game_id: selectedGame,
      limit,
      offset,
    })
      .then((data) => {
        if (!ignore) {
          setLeaderboardState({
            loading: false,
            items: data,
            error: null,
          });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setLeaderboardState({
            loading: false,
            items: [],
            error,
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedGame, limit, offset]);

  const currentPage = Math.floor(offset / limit) + 1;
  const rangeText = useMemo(
    () =>
      getRangeText({
        count: leaderboardState.items.length,
        loading: leaderboardState.loading,
        offset,
        limit,
      }),
    [leaderboardState.items.length, leaderboardState.loading, offset, limit],
  );
  const isPreviousDisabled = offset === 0 || leaderboardState.loading;
  const isNextDisabled =
    leaderboardState.loading || leaderboardState.items.length < limit;

  function updateParams(nextGame, nextLimit, nextOffset) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);

      next.set("game", getValidGame(nextGame));

      if (nextLimit === defaultPageSize) {
        next.delete("limit");
      } else {
        next.set("limit", String(clampLimit(nextLimit)));
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
    updateParams(gameId, limit, 0);
  }

  function handleLimitChange(event) {
    updateParams(selectedGame, clampLimit(event.target.value), 0);
  }

  function handlePreviousPage() {
    updateParams(selectedGame, limit, Math.max(0, offset - limit));
  }

  function handleNextPage() {
    updateParams(selectedGame, limit, offset + limit);
  }

  return (
    <main className="leaderboard-page">
      <div className="page-header">
        <h1>Leaderboard</h1>
        <p>Compare bot ratings and records within each supported game.</p>
      </div>

      <div className="game-tabs" role="tablist" aria-label="Select leaderboard game">
        {supportedGames.map((game) => {
          const GameIcon = game.icon;

          return (
            <button
              key={game.id}
              type="button"
              role="tab"
              aria-selected={selectedGame === game.id}
              className={selectedGame === game.id ? "game-tab active" : "game-tab"}
              onClick={() => handleGameChange(game.id)}
            >
              <GameIcon size={16} aria-hidden="true" />
              <span>{game.label}</span>
            </button>
          );
        })}
      </div>

      <section className="history-panel">
        <div className="section-heading leaderboard-heading">
          <label className="page-size-control">
            <span>Rows</span>
            <select
              value={limit}
              onChange={handleLimitChange}
              disabled={leaderboardState.loading}
            >
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <span>{rangeText}</span>
        </div>

        {leaderboardState.error && (
          <p className="error" role="alert">
            Could not load leaderboard: {leaderboardState.error.message}
          </p>
        )}

        {!leaderboardState.error &&
          !leaderboardState.loading &&
          leaderboardState.items.length === 0 && (
            <p className="empty-state">No bots found for this game.</p>
          )}

        {leaderboardState.items.length > 0 && (
          <div className="table-scroll">
            <table className="data-table leaderboard-table">
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col">Bot name</th>
                  <th scope="col">Owner</th>
                  <th scope="col">Rating</th>
                  <th scope="col">Games played</th>
                  <th scope="col">Win rate</th>
                  <th scope="col">W/L/D</th>
                </tr>
              </thead>
              <tbody>
                {leaderboardState.items.map((bot, index) => {
                  const records = getRecord(bot);
                  const rank = offset + index + 1;

                  return (
                    <tr key={bot.submission_id ?? bot.bot_id}>
                      <td>
                        <span className={rank === 1 ? "rank-cell top-rank" : "rank-cell"}>
                          <span className="rank-icon-slot">
                            {rank === 1 && (
                            <IconTrophyFilled size={13} aria-hidden="true" />
                            )}
                          </span>
                          <span>{rank}</span>
                        </span>
                      </td>
                      <td className="player-name">
                          <Link className="bot-name-link" to={`/bots/${bot.bot_id}`}>
                            <VersionedBotName bot={bot} />
                          </Link>
                      </td>
                      <td>{bot.owner_name}</td>
                      <td>{Math.round(bot.rating)}</td>
                      <td>{bot.games_played}</td>
                      <td>{formatWinRate(bot)}</td>
                      <td>
                        <span
                          className="record-summary"
                          aria-label={records
                            .map((record) => `${record.value} ${record.label}`)
                            .join(", ")}
                        >
                          {records.map((record, recordIndex) => (
                            <span
                              key={record.label}
                              className={`record-value ${record.className}`}
                            >
                              {record.value}
                              {recordIndex < records.length - 1 && (
                                <span className="record-separator">/</span>
                              )}
                            </span>
                          ))}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls" aria-label="Leaderboard pagination">
          <button
            type="button"
            className="pagination-button previous"
            onClick={handlePreviousPage}
            disabled={isPreviousDisabled}
          >
            Previous
          </button>
          <span>Page {currentPage}</span>
          <button
            type="button"
            className="pagination-button next"
            onClick={handleNextPage}
            disabled={isNextDisabled}
          >
            Next
          </button>
        </div>
      </section>
    </main>
  );
}
