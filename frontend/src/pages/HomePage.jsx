import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createMatch, getBots, getMatchJob, getMatchJobs, getMatches } from "../api/client";
import { formatGame, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const recentMatchLimit = 5;
const matchJobLimit = 100;
const testMatchSubmitCount = 10;
const matchJobPollIntervalMs = 1500;

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

function getBotSelectDisabled({ selectedGame, botsState }) {
  return !selectedGame || botsState.loading || botsState.items.length === 0;
}

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [selectedGame, setSelectedGame] = useState("");
  const [botsState, setBotsState] = useState({
    loading: false,
    items: [],
    error: null,
  });
  const [matchesState, setMatchesState] = useState({
    loading: false,
    items: [],
    total: 0,
    error: null,
  });
  const [jobsState, setJobsState] = useState({
    loading: false,
    items: [],
    total: 0,
    error: null,
  });
  const [botOne, setBotOne] = useState("");
  const [botTwo, setBotTwo] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
    jobId: null,
  });

  const loadJobs = useCallback(
    async ({ showLoading = false } = {}) => {
      if (showLoading) {
        setJobsState((current) => ({ ...current, loading: true, error: null }));
      }

      try {
        const [queuedJobs, runningJobs] = await Promise.all([
          getMatchJobs({ limit: matchJobLimit, status: "queued" }),
          getMatchJobs({ limit: matchJobLimit, status: "running" }),
        ]);
        const jobs = [...queuedJobs.items, ...runningJobs.items]
          .sort((first, second) => new Date(second.created_at) - new Date(first.created_at))
          .slice(0, matchJobLimit);

        setJobsState({
          loading: false,
          items: jobs,
          total: queuedJobs.total + runningJobs.total,
          error: null,
        });
      } catch (error) {
        setJobsState({ loading: false, items: [], total: 0, error });
      }
    },
    [],
  );

  useEffect(() => {
    let ignore = false;

    if (!selectedGame) {
      setBotsState({ loading: false, items: [], error: null });
      setBotOne("");
      setBotTwo("");
      setSubmitState({ loading: false, error: null, jobId: null });
      return undefined;
    }

    setBotsState({ loading: true, items: [], error: null });
    setBotOne("");
    setBotTwo("");
    setSubmitState({ loading: false, error: null, jobId: null });

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

    getMatches({ limit: recentMatchLimit })
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
  }, []);

  useEffect(() => {
    setJobsState({ loading: true, items: [], total: 0, error: null });
    loadJobs({ showLoading: false });
  }, [loadJobs]);

  const hasActiveJobs = jobsState.items.some(
    (job) => job.status === "queued" || job.status === "running",
  );

  useEffect(() => {
    if (!hasActiveJobs) {
      return undefined;
    }

    const intervalId = window.setInterval(loadJobs, matchJobPollIntervalMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [hasActiveJobs, loadJobs]);

  const submittedJob = submitState.jobId
    ? jobsState.items.find((job) => job.job_id === submitState.jobId) ?? null
    : null;
  const activeJobsInQueueOrder = [...jobsState.items].sort(
    (first, second) => new Date(first.created_at) - new Date(second.created_at),
  );
  const submittedJobPosition = submitState.jobId
    ? activeJobsInQueueOrder.findIndex((job) => job.job_id === submitState.jobId) + 1
    : 0;
  const queueStatusText =
    jobsState.total === 0
      ? "No matches are currently queued or running."
      : `There ${jobsState.total === 1 ? "is" : "are"} ${jobsState.total} active ${
          jobsState.total === 1 ? "match" : "matches"
        } in queue.`;

  useEffect(() => {
    if (!submittedJob) {
      return;
    }

    if (!submitState.loading) {
      setSubmitState({ loading: true, error: null, jobId: submittedJob.job_id });
    }
  }, [navigate, submitState.loading, submittedJob]);

  useEffect(() => {
    if (!submitState.jobId) {
      return undefined;
    }

    let ignore = false;

    async function loadSubmittedJob() {
      try {
        const job = await getMatchJob(submitState.jobId);

        if (ignore) {
          return;
        }

        if (job.status === "completed") {
          if (job.match_id) {
            setSubmitState({ loading: false, error: null, jobId: null });
            navigate(`/matches/${job.match_id}`);
          } else {
            setSubmitState({
              loading: false,
              error: new Error("The match job completed without a match id."),
              jobId: null,
            });
          }
          return;
        }

        if (job.status === "failed") {
          setSubmitState({
            loading: false,
            error: new Error(job.error_message || "The queued match failed."),
            jobId: null,
          });
        }
      } catch (error) {
        if (!ignore) {
          setSubmitState({ loading: false, error, jobId: null });
        }
      }
    }

    loadSubmittedJob();
    const intervalId = window.setInterval(loadSubmittedJob, matchJobPollIntervalMs);

    return () => {
      ignore = true;
      window.clearInterval(intervalId);
    };
  }, [navigate, submitState.jobId]);

  const canSubmit = useMemo(
    () =>
      Boolean(
        isAuthenticated &&
          selectedGame &&
          botOne &&
          botTwo &&
          botOne !== botTwo &&
          !submitState.loading,
      ),
    [botOne, botTwo, isAuthenticated, selectedGame, submitState.loading],
  );
  const hasDuplicateBots = Boolean(botOne && botTwo && botOne === botTwo);
  const botSelectDisabled = getBotSelectDisabled({ selectedGame, botsState });
  const matchFeedback = submitState.error
    ? {
        className: "error",
        message: errorMessageFor(submitState.error),
      }
    : submittedJob?.status === "failed"
      ? {
          className: "error",
          message: submittedJob.error_message || "The queued match failed.",
        }
    : submittedJob
      ? {
          className: "success",
          message: `Match job #${submittedJob.job_id} is ${submittedJob.status}.`,
        }
    : hasDuplicateBots
      ? {
          className: "error",
          message: "Choose two different bots to start a match.",
        }
      : !selectedGame
        ? {
            className: "empty-state",
            message: "Select a game to load available bots.",
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

    setSubmitState({ loading: true, error: null, jobId: null });

    try {
      const matchRequest = {
        game: selectedGame,
        players: [{ bot: botOne }, { bot: botTwo }],
      };
      const jobs = await Promise.all(
        Array.from({ length: testMatchSubmitCount }, () => createMatch(matchRequest)),
      );
      const job = jobs[0];

      setSubmitState({ loading: true, error: null, jobId: job.job_id });
      setJobsState((current) => ({
        ...current,
        items: [
          ...jobs.map((createdJob) => ({
            ...createdJob,
            game: selectedGame,
            bot_one_name: botOne,
            bot_two_name: botTwo,
            match_id: null,
            error_message: null,
            created_at: new Date().toISOString(),
            started_at: null,
            completed_at: null,
          })),
          ...current.items.filter(
            (item) => !jobs.some((createdJob) => createdJob.job_id === item.job_id),
          ),
        ].slice(0, matchJobLimit),
        total: current.total + jobs.length,
      }));
    } catch (error) {
      if (error.status === 401) {
        navigate("/login");
        return;
      }

      setSubmitState({ loading: false, error, jobId: null });
    }
  }

  return (
    <main className="home-page">
      <section className="match-panel">
        <div className="section-heading">
          <h2>Start a new match</h2>
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
              <span>Select game</span>
              <select
                value={selectedGame}
                onChange={(event) => setSelectedGame(event.target.value)}
              >
                <option value="">Select game</option>
                {supportedGames.map((game) => (
                  <option key={game.id} value={game.id}>
                    {game.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Select your bot</span>
              <select
                value={botOne}
                onChange={(event) => setBotOne(event.target.value)}
                disabled={botSelectDisabled}
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
                disabled={botSelectDisabled}
              >
                {botsState.items.map((bot) => (
                  <option key={bot.bot_id} value={bot.name}>
                    {formatBotOption(bot)}
                  </option>
                ))}
              </select>
            </label>

            <button type="submit" disabled={!canSubmit}>
              {submitState.loading ? "Waiting..." : "Queue match"}
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

      <section className="queue-card">
        <div className="section-heading">
          <h2>Queue</h2>
        </div>

        {jobsState.error && (
          <p className="error">Could not load queue: {jobsState.error.message}</p>
        )}

        {jobsState.loading && <p className="empty-state">Loading queue...</p>}

        {!jobsState.loading && !jobsState.error && (
          <p className="queue-summary">
            {queueStatusText}
            {submittedJobPosition > 0 && (
              <span className="queue-position"> Your match is #{submittedJobPosition}.</span>
            )}
          </p>
        )}
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
          <p className="empty-state">No matches have been played yet.</p>
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
                  <span>
                    {formatGame(match.game)} - {formatResult(match)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
