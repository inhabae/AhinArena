import {
  IconDeviceGamepad2,
  IconPercentage,
  IconRobot,
  IconTrophy,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getBot, getMatches, updateBot } from "../api/client";
import DescriptionEditor from "../components/DescriptionEditor";
import { formatGame } from "../games";
import { useAuth } from "../useAuth";
import { formatPercent, getWinRate } from "./PlayerPage";

const pageSize = 10;
const BUILT_IN_BOT_OWNER_NAME = "Built-in bot";

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatHeaderDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

function getErrorMessage(error) {
  if (error.status === 404 || error.code === "bot_not_found") {
    return "Bot not found.";
  }

  return error.message || "The bot could not be loaded.";
}

function stopLinkPropagation(event) {
  event.stopPropagation();
}

function PlayerRating({ rating }) {
  return (
    <span className="player-rating">
      ({Math.round(rating)})
    </span>
  );
}

function getBotMatchResult(match, botId) {
  if (match.result_reason === "draw" || match.winner_bot_id === null) {
    return {
      className: "result-draw",
      label: "Draw",
    };
  }

  if (match.winner_bot_id === botId) {
    return {
      className: "result-win",
      label: "Win",
    };
  }

  return {
    className: "result-loss",
    label: "Loss",
  };
}

export default function BotPage() {
  const navigate = useNavigate();
  const { botId } = useParams();
  const { user } = useAuth();
  const [botState, setBotState] = useState({
    loading: true,
    data: null,
    error: null,
  });
  const [matchesState, setMatchesState] = useState({
    loading: true,
    items: [],
    total: 0,
    error: null,
  });
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    let ignore = false;

    setBotState({ loading: true, data: null, error: null });

    getBot(botId)
      .then((data) => {
        if (!ignore) {
          setBotState({ loading: false, data, error: null });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setBotState({ loading: false, data: null, error });
        }
      });

    return () => {
      ignore = true;
    };
  }, [botId]);

  useEffect(() => {
    setOffset(0);
  }, [botId]);

  useEffect(() => {
    let ignore = false;

    setMatchesState((current) => ({
      loading: true,
      items: current.items,
      total: current.total,
      error: null,
    }));

    getMatches({
      bot_id: botId,
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
  }, [botId, offset]);

  const bot = botState.data;
  const rangeText = useMemo(() => {
    if (matchesState.loading) {
      return "Loading...";
    }

    if (matchesState.total === 0) {
      return "No matches";
    }

    const start = offset + 1;
    const end = Math.min(offset + pageSize, matchesState.total);

    return `${start}-${end} of ${matchesState.total}`;
  }, [matchesState.loading, matchesState.total, offset]);
  const currentPage = Math.floor(offset / pageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(matchesState.total / pageSize));
  const isPreviousDisabled = offset === 0 || matchesState.loading;
  const isNextDisabled =
    matchesState.loading || offset + pageSize >= matchesState.total;
  const isOwnBot = Boolean(user?.username && bot?.owner_name === user.username);

  async function handleSaveDescription(description) {
    const updatedBot = await updateBot(botId, { description });
    setBotState({ loading: false, data: updatedBot, error: null });
  }

  if (botState.loading) {
    return (
      <main className="bot-page">
        <p className="empty-state">Loading bot...</p>
      </main>
    );
  }

  if (botState.error) {
    return (
      <main className="bot-page">
        <p className="error" role="alert">
          {getErrorMessage(botState.error)}
        </p>
      </main>
    );
  }

  const statCards = [
    { label: "Rating", value: Math.round(bot.rating), icon: IconTrophy },
    {
      label: "Games played",
      value: bot.games_played,
      icon: IconDeviceGamepad2,
      muted: bot.games_played === 0,
    },
    {
      label: "Win rate",
      value: formatPercent(getWinRate(bot)),
      icon: IconPercentage,
      muted: bot.games_played === 0,
    },
    {
      label: "W/L/D",
      value: `${bot.wins}/${bot.losses}/${bot.draws}`,
      icon: IconRobot,
      muted: bot.games_played === 0,
    },
  ];

  return (
    <main className="bot-page">
      <section className="bot-header-card" aria-labelledby="bot-title">
        <h1 id="bot-title">{bot.name}</h1>
        <DescriptionEditor
          description={bot.description}
          editable={isOwnBot}
          emptyText={isOwnBot ? "Add a description" : "No bot description yet."}
          onSave={handleSaveDescription}
        />
        <p className="bot-header-info">
          <span>
            Game <strong>{formatGame(bot.game_id)}</strong>
          </span>
          <span aria-hidden="true">&middot;</span>
          <span>
            Owner{" "}
            <strong>
              {bot.owner_name === BUILT_IN_BOT_OWNER_NAME ? (
                BUILT_IN_BOT_OWNER_NAME
              ) : (
                <Link to={`/players/${encodeURIComponent(bot.owner_name)}`}>
                  {bot.owner_name}
                </Link>
              )}
            </strong>
          </span>
          <span aria-hidden="true">&middot;</span>
          <span>
            Created <strong>{formatHeaderDate(bot.created_at)}</strong>
          </span>
        </p>
      </section>

      <section className="player-stats" aria-label="Bot summary">
        {statCards.map(({ label, value, icon: Icon, muted }) => (
          <div className="stat-card" key={label}>
            <span className="stat-label">
              <Icon size={18} stroke={1.75} aria-hidden="true" />
              {label}
            </span>
            <strong className={muted ? "stat-value-muted" : undefined}>
              {value}
            </strong>
          </div>
        ))}
      </section>

      <section className="history-panel">
        <div className="section-heading player-section-heading">
          <div>
            <h2>Matches</h2>
          </div>
          <span>{rangeText}</span>
        </div>

        {matchesState.error && (
          <p className="error" role="alert">
            Could not load matches: {matchesState.error.message}
          </p>
        )}

        {!matchesState.error && !matchesState.loading && matchesState.items.length === 0 && (
          <p className="empty-state">No matches found for this bot.</p>
        )}

        {matchesState.items.length > 0 && (
          <div className="table-scroll">
            <table className="data-table match-history-table">
              <thead>
                <tr>
                  <th scope="col">Game</th>
                  <th scope="col">Players</th>
                  <th scope="col">Result</th>
                  <th scope="col">Completed date</th>
                </tr>
              </thead>
              <tbody>
                {matchesState.items.map((match) => {
                  const result = getBotMatchResult(match, bot.bot_id);

                  return (
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
                          <span className="player-name player-matchup-name">
                            <span>
                              <Link
                                className="bot-name-link"
                                to={`/bots/${match.bot_one_id}`}
                                onClick={stopLinkPropagation}
                              >
                                {match.bot_one_name}
                              </Link>
                            </span>
                            <PlayerRating
                              rating={match.bot_one_rating_before}
                            />
                          </span>
                          <span aria-hidden="true">vs</span>
                          <span className="player-name player-matchup-name">
                            <span>
                              <Link
                                className="bot-name-link"
                                to={`/bots/${match.bot_two_id}`}
                                onClick={stopLinkPropagation}
                              >
                                {match.bot_two_name}
                              </Link>
                            </span>
                            <PlayerRating
                              rating={match.bot_two_rating_before}
                            />
                          </span>
                        </span>
                      </td>
                      <td>
                        <span className={`match-result-badge ${result.className}`}>
                          {result.label}
                        </span>
                      </td>
                      <td className="completed-date">{formatDate(match.completed_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination-controls" aria-label="Bot match history pagination">
          <button
            type="button"
            className="pagination-button previous"
            onClick={() => setOffset((current) => Math.max(0, current - pageSize))}
            disabled={isPreviousDisabled}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            className="pagination-button next"
            onClick={() => setOffset((current) => current + pageSize)}
            disabled={isNextDisabled}
          >
            Next
          </button>
        </div>
      </section>
    </main>
  );
}
