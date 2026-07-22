import {
  IconArrowRight,
  IconDeviceGamepad2,
  IconPercentage,
  IconRobot,
  IconTrophy,
} from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getLeaderboard, getUserProfile, updateCurrentUser } from "../api/client";
import DescriptionEditor from "../components/DescriptionEditor";
import { formatGame, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const leaderboardLimit = 500;
const playerBotsPageSize = 10;

export function formatPercent(value) {
  return `${value.toFixed(1)}%`;
}

export function getWinRate(bot) {
  if (bot.games_played === 0) {
    return 0;
  }

  return (bot.wins / bot.games_played) * 100;
}

export function getRecord(bot) {
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
  const { username: usernameParam } = useParams();
  const { loading: authLoading, user } = useAuth();
  const username = usernameParam ? decodeURIComponent(usernameParam) : "";
  const [playerState, setPlayerState] = useState({
    loading: true,
    leaderboards: [],
    error: null,
  });
  const [profileState, setProfileState] = useState({
    loading: true,
    data: null,
    error: null,
  });
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    if (authLoading) {
      return;
    }

    let ignore = false;

    setPlayerState((current) => ({
      loading: true,
      leaderboards: current.leaderboards,
      error: null,
    }));
    setProfileState({ loading: true, data: null, error: null });

    Promise.all([
      getUserProfile(username),
      Promise.all(
        supportedGames.map((game) =>
          getLeaderboard({
            game_id: game.id,
            limit: leaderboardLimit,
            offset: 0,
          }).then((bots) => ({ gameId: game.id, bots })),
        ),
      ),
    ])
      .then(([profile, leaderboards]) => {
        if (!ignore) {
          setProfileState({
            loading: false,
            data: profile,
            error: null,
          });
          setPlayerState({
            loading: false,
            leaderboards,
            error: null,
          });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setProfileState({
            loading: false,
            data: null,
            error,
          });
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
  }, [authLoading, username]);

  const playerBots = useMemo(
    () => getRankedBots(playerState.leaderboards, username),
    [playerState.leaderboards, username],
  );
  const summary = useMemo(() => summarizeBots(playerBots), [playerBots]);
  const isOwnProfile = user?.username === username;
  const totalPages = Math.max(1, Math.ceil(playerBots.length / playerBotsPageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageOffset = (safeCurrentPage - 1) * playerBotsPageSize;
  const visiblePlayerBots = playerBots.slice(
    pageOffset,
    pageOffset + playerBotsPageSize,
  );
  const botsRangeText =
    playerBots.length === 0
      ? "No bots"
      : `${pageOffset + 1}-${pageOffset + visiblePlayerBots.length} of ${
          playerBots.length
        }`;
  const statCards = [
    {
      label: "Bots",
      value: playerBots.length,
      icon: IconRobot,
      muted: playerBots.length === 0,
    },
    {
      label: "Best rating",
      value: summary.topBot ? Math.round(summary.topBot.rating) : "N/A",
      icon: IconTrophy,
      muted: !summary.topBot,
    },
    {
      label: "Games played",
      value: summary.gamesPlayed,
      icon: IconDeviceGamepad2,
      muted: summary.gamesPlayed === 0,
    },
    {
      label: "Win rate",
      value: formatPercent(summary.winRate),
      icon: IconPercentage,
      muted: summary.gamesPlayed === 0,
    },
  ];

  useEffect(() => {
    setCurrentPage(1);
  }, [username, playerBots.length]);

  async function handleSaveDescription(description) {
    const updatedUser = await updateCurrentUser({ description });
    setProfileState({
      loading: false,
      data: {
        id: updatedUser.id,
        username: updatedUser.username,
        description: updatedUser.description,
        created_at: updatedUser.created_at,
      },
      error: null,
    });
  }

  if (authLoading || playerState.loading || profileState.loading) {
    return (
      <main className="player-page">
        <p className="empty-state">Loading player...</p>
      </main>
    );
  }

  return (
    <main className="player-page">
      <div className="page-header player-header">
        <div className="player-header-content">
          <h1>{username}</h1>
          <DescriptionEditor
            description={profileState.data?.description ?? ""}
            editable={isOwnProfile}
            emptyText={
              isOwnProfile
                ? "Add a description for your player profile."
                : "No player description yet."
            }
            onSave={handleSaveDescription}
          />
        </div>
        {isOwnProfile && (
          <Link className="button-link" to="/bots/new">
            Register bot
          </Link>
        )}
      </div>

      {(playerState.error || profileState.error) && (
        <p className="error" role="alert">
          Could not load player: {(playerState.error || profileState.error).message}
        </p>
      )}

      {!playerState.error && !profileState.error && (
        <>
          <section className="player-stats" aria-label="Player summary">
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
                <h2>Bots</h2>
              </div>
              <span>{botsRangeText}</span>
            </div>

            {playerBots.length === 0 && (
              <div className="empty-state player-empty-state">
                <IconRobot size={40} stroke={1.5} aria-hidden="true" />
                <p>No bots registered yet.</p>
                {isOwnProfile && (
                  <Link className="empty-state-link" to="/bots/new">
                    Register first bot
                    <IconArrowRight size={15} stroke={1.75} aria-hidden="true" />
                  </Link>
                )}
              </div>
            )}

            {playerBots.length > 0 && (
              <div className="table-scroll">
                <table className="data-table player-bot-table">
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
                    {visiblePlayerBots.map((bot) => {
                      const records = getRecord(bot);

                      return (
                        <tr key={`${bot.game_id}-${bot.bot_id}`}>
                          <td className="player-name">
                            <Link className="bot-name-link" to={`/bots/${bot.bot_id}`}>
                              <VersionedBotName bot={bot} />
                            </Link>
                          </td>
                          <td>{bot.game_label}</td>
                          <td>{Math.round(bot.rating)}</td>
                          <td>#{bot.rank}</td>
                          <td>{bot.games_played}</td>
                          <td>{formatPercent(getWinRate(bot))}</td>
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

            {playerBots.length > 0 && (
              <div className="pagination-controls" aria-label="Player bots pagination">
                <button
                  type="button"
                  className="pagination-button previous"
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                  disabled={safeCurrentPage === 1}
                >
                  Previous
                </button>
                <span>Page {safeCurrentPage}</span>
                <button
                  type="button"
                  className="pagination-button next"
                  onClick={() =>
                    setCurrentPage((page) => Math.min(totalPages, page + 1))
                  }
                  disabled={safeCurrentPage === totalPages}
                >
                  Next
                </button>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
