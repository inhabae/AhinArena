import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getLeaderboard } from "../api/client";
import { formatGame, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const leaderboardLimit = 500;

function formatPercent(value) {
  return `${value.toFixed(1)}%`;
}

function getWinRate(bot) {
  if (bot.games_played === 0) {
    return 0;
  }

  return (bot.wins / bot.games_played) * 100;
}

function getRecord(bot) {
  return `${bot.wins}/${bot.losses}/${bot.draws}`;
}

function getRankedBots(leaderboards, username) {
  return leaderboards.flatMap(({ gameId, bots }) =>
    bots
      .map((bot, index) => ({
        ...bot,
        game_id: gameId,
        game_label: formatGame(gameId),
        rank: index + 1,
      }))
      .filter((bot) => bot.owner_name === username),
  );
}

function summarizeBots(bots) {
  const gamesPlayed = bots.reduce((total, bot) => total + bot.games_played, 0);
  const wins = bots.reduce((total, bot) => total + bot.wins, 0);
  const losses = bots.reduce((total, bot) => total + bot.losses, 0);
  const draws = bots.reduce((total, bot) => total + bot.draws, 0);
  const topBot = bots.reduce((best, bot) => {
    if (!best || bot.rating > best.rating) {
      return bot;
    }

    return best;
  }, null);

  return {
    gamesPlayed,
    record: `${wins}/${losses}/${draws}`,
    topBot,
    winRate: gamesPlayed === 0 ? 0 : (wins / gamesPlayed) * 100,
  };
}

export default function PlayerPage() {
  const navigate = useNavigate();
  const { username: usernameParam } = useParams();
  const { isAuthenticated, loading: authLoading, user } = useAuth();
  const username = usernameParam ? decodeURIComponent(usernameParam) : "";
  const [playerState, setPlayerState] = useState({
    loading: true,
    leaderboards: [],
    error: null,
  });

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    let ignore = false;

    setPlayerState((current) => ({
      loading: true,
      leaderboards: current.leaderboards,
      error: null,
    }));

    Promise.all(
      supportedGames.map((game) =>
        getLeaderboard({
          game_id: game.id,
          limit: leaderboardLimit,
          offset: 0,
        }).then((bots) => ({ gameId: game.id, bots })),
      ),
    )
      .then((leaderboards) => {
        if (!ignore) {
          setPlayerState({
            loading: false,
            leaderboards,
            error: null,
          });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setPlayerState({
            loading: false,
            leaderboards: [],
            error,
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, [authLoading, isAuthenticated, navigate]);

  const playerBots = useMemo(
    () => getRankedBots(playerState.leaderboards, username),
    [playerState.leaderboards, username],
  );
  const summary = useMemo(() => summarizeBots(playerBots), [playerBots]);
  const isOwnProfile = user?.username === username;

  if (authLoading || playerState.loading) {
    return (
      <main className="player-page">
        <p className="empty-state">Loading player...</p>
      </main>
    );
  }

  return (
    <main className="player-page">
      <div className="page-header player-header">
        <div>
          <h1>{username}</h1>
          <p>
            {isOwnProfile
              ? "Your registered bots, ratings, and match record."
              : "Registered bots, ratings, and match record."}
          </p>
        </div>
        {isOwnProfile && (
          <Link className="button-link" to="/bots/new">
            Register bot
          </Link>
        )}
      </div>

      {playerState.error && (
        <p className="error" role="alert">
          Could not load player: {playerState.error.message}
        </p>
      )}

      {!playerState.error && (
        <>
          <section className="player-stats" aria-label="Player summary">
            <div className="stat-card">
              <span>Bots</span>
              <strong>{playerBots.length}</strong>
            </div>
            <div className="stat-card">
              <span>Best rating</span>
              <strong>{summary.topBot?.rating ?? "N/A"}</strong>
            </div>
            <div className="stat-card">
              <span>Games played</span>
              <strong>{summary.gamesPlayed}</strong>
            </div>
            <div className="stat-card">
              <span>Win rate</span>
              <strong>{formatPercent(summary.winRate)}</strong>
            </div>
          </section>

          <section className="history-panel">
            <div className="section-heading player-section-heading">
              <div>
                <h2>Bots</h2>
              </div>
            </div>

            {playerBots.length === 0 && (
              <p className="empty-state">
                {isOwnProfile
                  ? "You have not registered a bot yet."
                  : "No bots found for this player."}
              </p>
            )}

            {playerBots.length > 0 && (
              <div className="table-scroll">
                <table className="player-bot-table">
                  <thead>
                    <tr>
                      <th scope="col">Bot name</th>
                      <th scope="col">Game</th>
                      <th scope="col">Rating</th>
                      <th scope="col">Rank</th>
                      <th scope="col">Games played</th>
                      <th scope="col">Win rate</th>
                      <th scope="col">W/L/D</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playerBots.map((bot) => (
                      <tr key={`${bot.game_id}-${bot.bot_id}`}>
                        <td className="bot-name-cell">{bot.name}</td>
                        <td>{bot.game_label}</td>
                        <td>{bot.rating}</td>
                        <td>#{bot.rank}</td>
                        <td>{bot.games_played}</td>
                        <td>{formatPercent(getWinRate(bot))}</td>
                        <td>{getRecord(bot)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
