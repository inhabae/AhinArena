import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { IconFileCode, IconUpload } from "@tabler/icons-react";

import { createBot } from "../api/client";
import { defaultGameId, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const maxExecutableBytes = 10 * 1024 * 1024;
const rejectedFileExtensions = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "txt",
]);

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

function localFileError(file) {
  if (!file) return "";
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension && rejectedFileExtensions.has(extension)) {
    return "Choose a Linux executable, not a document, image, archive, or text file.";
  }
  if (file.size > maxExecutableBytes) return "The executable must be 10 MiB or smaller.";
  return "";
}

export default function BotRegistrationPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [selectedGame, setSelectedGame] = useState(defaultGameId);
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const fileInputRef = useRef(null);
  const [submitState, setSubmitState] = useState({ loading: false, error: null, botName: "", version: null });
  const nameError = botNameErrorFor(name);

  useEffect(() => {
    setSelectedGame(defaultGameId);
    setName("");
    setFile(null);
    setFileError("");
    setNameTouched(false);
    setSubmitState({ loading: false, error: null, botName: "", version: null });
  }, [location.key]);

  async function handleFileChange(event) {
    const nextFile = event.target.files?.[0] ?? null;
    const validationError = localFileError(nextFile);
    if (!nextFile || validationError) {
      setFile(null);
      setFileError(validationError);
      event.target.value = "";
      return;
    }

    const header = new Uint8Array(await nextFile.slice(0, 4).arrayBuffer());
    if (header.length !== 4 || header[0] !== 0x7f || header[1] !== 0x45 || header[2] !== 0x4c || header[3] !== 0x46) {
      setFile(null);
      setFileError("Choose a Linux ELF executable. Images, documents, archives, and scripts are not accepted.");
      event.target.value = "";
      return;
    }

    setFile(nextFile);
    setFileError("");
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

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
          <div className="executable-field">
            <span className="executable-label">Player executable</span>
            <input
              ref={fileInputRef}
              className="visually-hidden-file-input"
              type="file"
              onChange={handleFileChange}
              aria-describedby="executable-help executable-error"
              required
            />
            <button className="executable-picker" type="button" onClick={openFilePicker}>
              <span className="executable-picker-icon"><IconUpload size={18} /></span>
              <span className="executable-picker-copy">
                <strong>{file ? "Replace executable" : "Choose executable"}</strong>
                <small>Static Linux x86-64 ELF · max 10 MiB</small>
              </span>
              <span className="executable-picker-action">Browse</span>
            </button>
            {file && !fileError && (
              <div className="selected-executable">
                <IconFileCode size={18} aria-hidden="true" />
                <span>{file.name}</span>
                <small>{formatBytes(file.size)}</small>
              </div>
            )}
            <span id="executable-help" className="field-help">No scripts, images, documents, or archives.</span>
            {fileError && <span id="executable-error" className="field-error">{fileError}</span>}
          </div>
          {submitState.version && <p className="inline-success" role="status">{submitState.botName} is registered with executable version {submitState.version}.</p>}
          {submitState.error && <p className="error" role="alert">{errorMessageFor(submitState.error)}</p>}
          <button type="submit" disabled={submitState.loading || !file || Boolean(fileError)}>{submitState.loading ? "Registering..." : "Register bot"}</button>
        </form>
      )}
    </main>
  );
}
