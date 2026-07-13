import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createBot, submitBotCode } from "../api/client";
import { defaultGameId, supportedGames } from "../games";
import { useAuth } from "../useAuth";

const sourceCodePlaceholders = {
  "connect-four": [
    "import json",
    "import random",
    "import sys",
    "",
    "for line in sys.stdin:",
    "    state = json.loads(line)",
    "    legal_cols = [",
    "        col",
    "        for col in range(7)",
    "        if state[\"board\"][0][col] == \" \"",
    "    ]",
    "    print(json.dumps({\"col\": random.choice(legal_cols)}), flush=True)",
  ].join("\n"),
  tictactoe: [
    "import json",
    "import random",
    "import sys",
    "",
    "for line in sys.stdin:",
    "    state = json.loads(line)",
    "    legal_moves = [",
    "        (row, col)",
    "        for row in range(3)",
    "        for col in range(3)",
    "        if state[\"board\"][row][col] == \" \"",
    "    ]",
    "    row, col = random.choice(legal_moves)",
    "    print(json.dumps({\"row\": row, \"col\": col}), flush=True)",
  ].join("\n"),
};

function errorMessageFor(error) {
  if (error.code === "unsupported_game") {
    return "This game is not supported yet.";
  }

  if (error.code === "bot_name_taken") {
    return "A bot with this name already exists for the selected game.";
  }

  if (error.code === "submission_too_large") {
    return "The source code is too large to submit.";
  }

  if (error.code === "invalid_syntax") {
    return error.message || "The source code has invalid Python syntax.";
  }

  if (error.code === "bot_has_no_submission") {
    return "Submit source code before using this bot in a match.";
  }

  if (error.code === "bot_not_owned") {
    return "You can only submit code for bots you own.";
  }

  if (error.code === "bot_not_found") {
    return "This bot could not be found. Register it again and retry.";
  }

  if (error.code === "unsupported_language") {
    return "Only Python submissions are supported right now.";
  }

  return error.message || "The bot could not be registered.";
}

export default function BotRegistrationPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [selectedGame, setSelectedGame] = useState(defaultGameId);
  const [name, setName] = useState("");
  const [createdBot, setCreatedBot] = useState(null);
  const [sourceCode, setSourceCode] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
  });
  const [submissionState, setSubmissionState] = useState({
    loading: false,
    error: null,
    version: null,
  });

  async function handleSubmit(event) {
    event.preventDefault();

    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    if (!name.trim()) {
      return;
    }

    setSubmitState({ loading: true, error: null });
    setSubmissionState({ loading: false, error: null, version: null });

    try {
      const bot = await createBot({
        game_id: selectedGame,
        name: name.trim(),
      });
      setCreatedBot(bot);
      setSubmitState({ loading: false, error: null });
    } catch (error) {
      if (error.status === 401) {
        navigate("/login");
        return;
      }

      setSubmitState({ loading: false, error });
    }
  }

  async function handleCodeSubmit(event) {
    event.preventDefault();

    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    if (!createdBot || !sourceCode.trim()) {
      return;
    }

    setSubmissionState({ loading: true, error: null, version: null });

    try {
      const submission = await submitBotCode(createdBot.bot_id, {
        source_code: sourceCode,
      });
      setSubmissionState({
        loading: false,
        error: null,
        version: submission.version,
      });
    } catch (error) {
      if (error.status === 401) {
        navigate("/login");
        return;
      }

      setSubmissionState({ loading: false, error, version: null });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Register a bot</h1>
        <p>Add a named bot to a supported game, then submit its source code.</p>
      </div>

      {loading && <p className="empty-state">Checking session...</p>}

      {!loading && !isAuthenticated && (
        <section className="form-panel login-gate">
          <div>
            <h2>Log in to register a bot</h2>
            <p>Bot ownership is tied to your account.</p>
          </div>
          <Link className="button-link" to="/login">
            Log in
          </Link>
        </section>
      )}

      {!loading && isAuthenticated && (
        <div className="bot-registration-flow">
          <form className="form-panel" onSubmit={handleSubmit}>
            <label>
              <span>Game</span>
              <select
                value={selectedGame}
                onChange={(event) => {
                  setSelectedGame(event.target.value);
                  setCreatedBot(null);
                  setSubmissionState({
                    loading: false,
                    error: null,
                    version: null,
                  });
                }}
                disabled={Boolean(createdBot)}
              >
                {supportedGames.map((game) => (
                  <option key={game.id} value={game.id}>
                    {game.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Bot name</span>
              <input
                type="text"
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                  setCreatedBot(null);
                  setSubmissionState({
                    loading: false,
                    error: null,
                    version: null,
                  });
                }}
                maxLength={64}
                required
                disabled={Boolean(createdBot)}
              />
            </label>

            {createdBot && (
              <p className="success" role="status">
                {createdBot.name} is registered. Submit source code to make it
                match-ready.
              </p>
            )}

            {submitState.error && (
              <p className="error" role="alert">
                {errorMessageFor(submitState.error)}
              </p>
            )}

            {!createdBot && (
              <button
                type="submit"
                disabled={submitState.loading || !name.trim()}
              >
                {submitState.loading ? "Registering..." : "Register bot"}
              </button>
            )}
          </form>

          {createdBot && (
            <form className="form-panel" onSubmit={handleCodeSubmit}>
              <label>
                <span>Source code</span>
                <textarea
                  value={sourceCode}
                  onChange={(event) => setSourceCode(event.target.value)}
                  placeholder={
                    sourceCodePlaceholders[selectedGame] ??
                    sourceCodePlaceholders.tictactoe
                  }
                  spellCheck="false"
                  required
                />
              </label>

              {submissionState.error && (
                <p className="error" role="alert">
                  {errorMessageFor(submissionState.error)}
                </p>
              )}

              {submissionState.version && (
                <p className="success" role="status">
                  Source code submitted as version {submissionState.version}.
                </p>
              )}

              <button
                type="submit"
                disabled={submissionState.loading || !sourceCode.trim()}
              >
                {submissionState.loading ? "Submitting..." : "Submit code"}
              </button>
            </form>
          )}
        </div>
      )}
    </main>
  );
}
