import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createMatch, getBots, getMatches } from "../api/client";
import { formatGame, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const recentMatchLimit = 5;

function errorMessageFor(error) {
  if (error.code === "unsupported_game") {
    return "This game is not supported yet.";
  }

  if (error.code === "invalid_player_count") {
    return "A match requires exactly two bots.";
  }

  if (error.code === "bot_not_found") {
    return "One of the selected bots could not be found. Refresh the list and try again.";
  }

  if (error.code === "duplicate_bot_match") {
    return "Choose two different bots to start a match.";
  }

  return error.message || "The match could not be started.";
}

function formatResult(match) {
  if (match.winner_bot_name) {
    return `${match.winner_bot_name} won`;
  }

  return match.result_reason === "draw" ? "Draw" : match.result_reason;
}

function formatBotOption(bot) {
  return bot.owner_name ? `${bot.name} (${bot.owner_name})` : bot.name;
}

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [selectedGame, setSelectedGame] = useState(supportedGames[0].id);
  const [botsState, setBotsState] = useState({
    loading: true,
    items: [],
    error: null,
  });
  const [matchesState, setMatchesState] = useState({
    loading: true,
    items: [],
    total: 0,
    error: null,
  });
  const [botOne, setBotOne] = useState("");
  const [botTwo, setBotTwo] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
    job: null,
  });

  useEffect(() => {
    let ignore = false;

    setBotsState({ loading: true, items: [], error: null });
    setBotOne("");
    setBotTwo("");
    setSubmitState({ loading: false, error: null, job: null });

    getBots({ game_id: selectedGame })
      .then((items) => {
        if (!ignore) {
          setBotsState({ loading: false, items, error: null });
          setBotOne(items[0]?.name ?? "");
          setBotTwo(items[1]?.name ?? items[0]?.name ?? "");
        }
      })
      .catch((error) => {
        if (!ignore) {
          setBotsState({ loading: false, items: [], error });
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedGame]);

  useEffect(() => {
    let ignore = false;

    setMatchesState({ loading: true, items: [], total: 0, error: null });

    getMatches({ game_id: selectedGame, limit: recentMatchLimit })
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
          setMatchesState({ loading: false, items: [], total: 0, error });
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedGame]);

  const canSubmit = useMemo(
    () =>
      Boolean(
        isAuthenticated &&
          botOne &&
          botTwo &&
          botOne !== botTwo &&
          !submitState.loading,
      ),
    [botOne, botTwo, isAuthenticated, submitState.loading],
  );
  const hasDuplicateBots = Boolean(botOne && botTwo && botOne === botTwo);
  const matchFeedback = submitState.error
    ? {
        className: "error",
        message: errorMessageFor(submitState.error),
      }
    : submitState.job
      ? {
          className: "success",
          message: `Match queued as job #${submitState.job.job_id}.`,
        }
    : hasDuplicateBots
      ? {
          className: "error",
          message: "Choose two different bots to start a match.",
        }
      : !botsState.loading && botsState.items.length === 0
        ? {
            className: "empty-state",
            message: "No bots are registered for this game yet.",
          }
        : null;

  async function handleSubmit(event) {
    event.preventDefault();

    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    if (!canSubmit) {
      return;
    }

    setSubmitState({ loading: true, error: null, job: null });

    try {
      const job = await createMatch({
        game: selectedGame,
        players: [{ bot: botOne }, { bot: botTwo }],
      });

      setSubmitState({ loading: false, error: null, job });
    } catch (error) {
      if (error.status === 401) {
        navigate("/login");
        return;
      }

      setSubmitState({ loading: false, error, job: null });
    }
  }

  return (
    <main className="home-page">
      <div className="page-header">
        <h1>Start a match</h1>
        <p>Pick a game, choose two registered bots, and run the next arena match.</p>
      </div>

      <div className="game-tabs" role="tablist" aria-label="Game">
        {supportedGames.map((game) => (
          <button
            key={game.id}
            type="button"
            role="tab"
            aria-selected={selectedGame === game.id}
            className={selectedGame === game.id ? "game-tab active" : "game-tab"}
            onClick={() => setSelectedGame(game.id)}
          >
            {game.label}
          </button>
        ))}
      </div>

      <section className="home-grid">
        <section className="match-panel">
          <div className="section-heading">
            <h2>Start a new match</h2>
            <span>{formatGame(selectedGame)}</span>
          </div>

          {botsState.error && (
            <p className="error" role="alert">
              Could not load bots: {botsState.error.message}
            </p>
          )}

          {authLoading && <p className="empty-state">Checking session...</p>}

          {!authLoading && !isAuthenticated && (
            <div className="login-gate">
              <div>
                <h3>Log in to start a match</h3>
                <p>Match creation is available after you log in.</p>
              </div>
              <Link className="button-link" to="/login">
                Log in
              </Link>
            </div>
          )}

          {!authLoading && isAuthenticated && (
            <form className="match-controls" onSubmit={handleSubmit}>
              <label>
                <span>Select your bot</span>
                <select
                  value={botOne}
                  onChange={(event) => setBotOne(event.target.value)}
                  disabled={botsState.loading || botsState.items.length === 0}
                >
                  {botsState.items.map((bot) => (
                    <option key={bot.bot_id} value={bot.name}>
                      {formatBotOption(bot)}
                    </option>
                  ))}
                </select>
              </label>

              <span className="versus">vs</span>

              <label>
                <span>Select opponent bot</span>
                <select
                  value={botTwo}
                  onChange={(event) => setBotTwo(event.target.value)}
                  disabled={botsState.loading || botsState.items.length === 0}
                >
                  {botsState.items.map((bot) => (
                    <option key={bot.bot_id} value={bot.name}>
                      {formatBotOption(bot)}
                    </option>
                  ))}
                </select>
              </label>

              <button type="submit" disabled={!canSubmit}>
                {submitState.loading ? "Queueing..." : "Queue match"}
              </button>
            </form>
          )}

          <div className="match-feedback" aria-live="polite">
            {matchFeedback && (
              <p className={matchFeedback.className} role="alert">
                {matchFeedback.message}
              </p>
            )}
          </div>
        </section>

        <div className="stats-row" aria-label={`${formatGame(selectedGame)} stats`}>
          <div className="stat-card">
            <span>Matches played</span>
            <strong>{matchesState.loading ? "..." : matchesState.total}</strong>
          </div>
          <div className="stat-card">
            <span>Bots registered</span>
            <strong>{botsState.loading ? "..." : botsState.items.length}</strong>
          </div>
        </div>
      </section>

      <section className="recent-panel">
        <div className="section-heading">
          <h2>Recent matches</h2>
          <Link to="/matches">View all</Link>
        </div>

        {matchesState.error && (
          <p className="error">Could not load recent matches: {matchesState.error.message}</p>
        )}

        {matchesState.loading && <p className="empty-state">Loading matches...</p>}

        {!matchesState.loading && matchesState.items.length === 0 && (
          <p className="empty-state">No matches have been played for this game yet.</p>
        )}

        {matchesState.items.length > 0 && (
          <ul className="recent-match-list">
            {matchesState.items.map((match) => (
              <li key={match.match_id}>
                <Link to={`/matches/${match.match_id}`}>
                  <span>
                    <strong>{match.bot_one_name}</strong> vs{" "}
                    <strong>{match.bot_two_name}</strong>
                  </span>
                  <span>{formatResult(match)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
