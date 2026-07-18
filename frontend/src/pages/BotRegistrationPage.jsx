import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { createBot } from "../api/client";
import { defaultGameId, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const maxExecutableBytes = 10 * 1024 * 1024;

function errorMessageFor(error) {
  const messages = {
    unsupported_game: "This game is not supported yet.",
    bot_name_taken: "A bot with this name already exists for the selected game.",
    submission_too_large: "The executable must be 10 MiB or smaller.",
    invalid_executable: "Choose a valid Linux ELF executable.",
    unsupported_architecture: "The executable must be 64-bit Linux x86-64.",
    dynamic_executable: "The executable must be statically linked.",
  };
  return messages[error.code] || error.message || "The bot could not be registered.";
}

function botNameErrorFor(name) {
  const trimmed = name.trim();
  if (trimmed.length < 3 || trimmed.length > 32) return "Bot name must be 3-32 characters.";
  if (!/^[A-Za-z0-9][A-Za-z0-9 _-]*$/.test(trimmed)) {
    return "Bot name can only use letters, numbers, spaces, underscores, or hyphens.";
  }
  return "";
}

function formatBytes(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.ceil(bytes / 1024)} KiB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

export default function BotRegistrationPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [selectedGame, setSelectedGame] = useState(defaultGameId);
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [nameTouched, setNameTouched] = useState(false);
  const [submitState, setSubmitState] = useState({ loading: false, error: null, botName: "", version: null });
  const nameError = botNameErrorFor(name);
  const fileError = file?.size > maxExecutableBytes ? "The executable must be 10 MiB or smaller." : "";

  useEffect(() => {
    setSelectedGame(defaultGameId);
    setName("");
    setFile(null);
    setNameTouched(false);
    setSubmitState({ loading: false, error: null, botName: "", version: null });
  }, [location.key]);

  async function handleSubmit(event) {
    event.preventDefault();
    setNameTouched(true);
    if (!isAuthenticated) return navigate("/login");
    if (nameError || !file || fileError) return;
    setSubmitState({ loading: true, error: null, botName: "", version: null });
    try {
      const bot = await createBot({ game_id: selectedGame, name: name.trim(), executable: file });
      setSubmitState({ loading: false, error: null, botName: bot.name, version: bot.version });
    } catch (error) {
      if (error.status === 401) return navigate("/login");
      setSubmitState({ loading: false, error, botName: "", version: null });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Register a bot</h1>
        <p>Upload a statically linked, 64-bit Linux x86-64 executable.</p>
      </div>
      {loading && <p className="empty-state">Checking session...</p>}
      {!loading && !isAuthenticated && (
        <section className="form-panel login-gate">
          <div><h2>Log in to register a bot</h2><p>Bot ownership is tied to your account.</p></div>
          <Link className="button-link" to="/login">Log in</Link>
        </section>
      )}
      {!loading && isAuthenticated && (
        <form className="form-panel" onSubmit={handleSubmit}>
          <label><span>Game</span><select value={selectedGame} onChange={(event) => setSelectedGame(event.target.value)}>
            {supportedGames.map((game) => <option key={game.id} value={game.id}>{game.label}</option>)}
          </select></label>
          <label><span>Bot name</span><input value={name} onChange={(event) => setName(event.target.value)} onBlur={() => setNameTouched(true)} />
            {nameTouched && nameError && <span className="field-error">{nameError}</span>}
          </label>
          <label><span>Player executable</span><input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
            {file && !fileError && <span>{file.name} ({formatBytes(file.size)})</span>}
            {fileError && <span className="field-error">{fileError}</span>}
          </label>
          <p>Maximum 10 MiB. The executable must communicate using the documented JSON-lines protocol.</p>
          {submitState.version && <p className="inline-success" role="status">{submitState.botName} is registered with executable version {submitState.version}.</p>}
          {submitState.error && <p className="error" role="alert">{errorMessageFor(submitState.error)}</p>}
          <button type="submit" disabled={submitState.loading || !file || Boolean(fileError)}>{submitState.loading ? "Registering..." : "Register bot"}</button>
        </form>
      )}
    </main>
  );
}
