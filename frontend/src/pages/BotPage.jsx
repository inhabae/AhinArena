import {
  IconDeviceGamepad2,
  IconFileCode,
  IconPercentage,
  IconRobot,
  IconTrophy,
  IconUpload,
} from "@tabler/icons-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getBot, getMatches, submitBotExecutable, updateBot } from "../api/client";
import DescriptionEditor from "../components/DescriptionEditor";
import { formatGame } from "../games";
import { useAuth } from "../useAuth";
import { formatPercent, getWinRate } from "./PlayerPage";

const pageSize = 10;
const BUILT_IN_BOT_OWNER_NAME = "Built-in bot";
const maxExecutableBytes = 10 * 1024 * 1024;
const rejectedFileExtensions = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "txt",
]);

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

function formatBytes(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.ceil(bytes / 1024)} KiB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function getErrorMessage(error) {
  if (error.status === 404 || error.code === "bot_not_found") {
    return "Bot not found.";
  }

  return error.message || "The bot could not be loaded.";
}

function localFileError(file) {
  if (!file) return "";
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension && rejectedFileExtensions.has(extension)) {
    return "Choose a Linux executable, not a document, image, archive, or text file.";
  }
  if (file.size > maxExecutableBytes) return "The executable must be 10 MiB or smaller.";
  return "";
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

function VersionedBotName({ name, version }) {
  return (
    <>
      {name}
      {version && <span className="bot-version-suffix">v{version}</span>}
    </>
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
  const fileInputRef = useRef(null);
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
  const [selectedSubmissionId, setSelectedSubmissionId] = useState("");
  const [uploadState, setUploadState] = useState({ loading: false, error: null, version: null });
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadFileError, setUploadFileError] = useState("");

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
    setSelectedSubmissionId("");
    setUploadFile(null);
    setUploadFileError("");
    setUploadState({ loading: false, error: null, version: null });
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
      bot_submission_id: selectedSubmissionId,
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
  }, [botId, selectedSubmissionId, offset]);

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

  async function handleFileChange(event) {
    const nextFile = event.target.files?.[0] ?? null;
    const validationError = localFileError(nextFile);
    if (!nextFile || validationError) {
      setUploadFile(null);
      setUploadFileError(validationError);
      event.target.value = "";
      return;
    }

    const header = new Uint8Array(await nextFile.slice(0, 4).arrayBuffer());
    if (header.length !== 4 || header[0] !== 0x7f || header[1] !== 0x45 || header[2] !== 0x4c || header[3] !== 0x46) {
      setUploadFile(null);
      setUploadFileError("Choose a Linux ELF executable. Images, documents, archives, and scripts are not accepted.");
      event.target.value = "";
      return;
    }

    setUploadFile(nextFile);
    setUploadFileError("");
    setUploadState({ loading: false, error: null, version: null });
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  async function handleUploadVersion(event) {
    event.preventDefault();
    if (!uploadFile || uploadFileError) {
      return;
    }

    setUploadState({ loading: true, error: null, version: null });
    try {
      const submission = await submitBotExecutable(botId, uploadFile);
      const updatedBot = await getBot(botId);
      setBotState({ loading: false, data: updatedBot, error: null });
      setSelectedSubmissionId("");
      setOffset(0);
      setUploadFile(null);
      setUploadFileError("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setUploadState({ loading: false, error: null, version: submission.version });
    } catch (error) {
      setUploadState({ loading: false, error, version: null });
    }
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
          {bot.active_version && (
            <>
              <span aria-hidden="true">&middot;</span>
              <span>
                Active <strong>v{bot.active_version}</strong>
              </span>
            </>
          )}
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
            <h2>Versions</h2>
          </div>
          <span>{bot.versions.length} total</span>
        </div>

        {isOwnBot && (
          <form className="version-upload-form" onSubmit={handleUploadVersion}>
            <div className="version-upload-row">
              <input
                ref={fileInputRef}
                className="visually-hidden-file-input"
                type="file"
                onChange={handleFileChange}
                aria-describedby="version-executable-error"
                disabled={uploadState.loading}
                required
              />
              <button
                className="version-file-button"
                type="button"
                onClick={openFilePicker}
                disabled={uploadState.loading}
              >
                <IconUpload size={15} aria-hidden="true" />
                {uploadFile ? "Change file" : "Choose file"}
              </button>
              {uploadFile && !uploadFileError && (
                <div className="version-selected-file">
                  <IconFileCode size={15} aria-hidden="true" />
                  <span>{uploadFile.name}</span>
                  <small>{formatBytes(uploadFile.size)}</small>
                </div>
              )}
              <button
                className="version-submit-button"
                type="submit"
                disabled={uploadState.loading || !uploadFile || Boolean(uploadFileError)}
              >
                {uploadState.loading ? "Uploading..." : "Upload"}
              </button>
            </div>
            {uploadFileError && <span id="version-executable-error" className="field-error">{uploadFileError}</span>}
          </form>
        )}
        {uploadState.error && (
          <p className="error" role="alert">
            Could not upload version: {uploadState.error.message}
          </p>
        )}
        {uploadState.version && (
          <p className="inline-success" role="status">
            Version {uploadState.version} is now active.
          </p>
        )}

        {bot.versions.length > 0 && (
          <div className="table-scroll">
            <table className="data-table bot-version-table">
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Rating</th>
                  <th scope="col">Games</th>
                  <th scope="col">W/L/D</th>
                  <th scope="col">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {bot.versions.map((version) => (
                  <tr key={version.submission_id}>
                    <td>
                      v{version.version}
                      {version.is_active && <span className="version-active-badge">Active</span>}
                    </td>
                    <td>{Math.round(version.rating)}</td>
                    <td>{version.games_played}</td>
                    <td>{version.wins}/{version.losses}/{version.draws}</td>
                    <td>{formatHeaderDate(version.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="history-panel">
        <div className="section-heading player-section-heading">
          <div>
            <h2>Matches</h2>
          </div>
          <label className="version-filter-control">
            <span>Version</span>
            <select
              value={selectedSubmissionId}
              onChange={(event) => {
                setSelectedSubmissionId(event.target.value);
                setOffset(0);
              }}
              disabled={matchesState.loading}
            >
              <option value="">All versions</option>
              {bot.versions.map((version) => (
                <option key={version.submission_id} value={version.submission_id}>
                  v{version.version}
                </option>
              ))}
            </select>
          </label>
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
                                <VersionedBotName
                                  name={match.bot_one_name}
                                  version={match.bot_one_version}
                                />
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
                                <VersionedBotName
                                  name={match.bot_two_name}
                                  version={match.bot_two_version}
                                />
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
