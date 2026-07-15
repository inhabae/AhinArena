import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createBot } from "../api/client";
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
  const [sourceCode, setSourceCode] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
    botName: "",
    version: null,
  });

  async function handleSubmit(event) {
    event.preventDefault();

    if (!isAuthenticated) {
      navigate("/login");
      return;
    }

    if (!name.trim() || !sourceCode.trim()) {
      return;
    }

    setSubmitState({
      loading: true,
      error: null,
      botName: "",
      version: null,
    });

    try {
      const bot = await createBot({
        game_id: selectedGame,
        name: name.trim(),
        source_code: sourceCode,
      });

      setSubmitState({
        loading: false,
        error: null,
        botName: bot.name,
        version: bot.version,
      });
    } catch (error) {
      if (error.status === 401) {
        navigate("/login");
        return;
      }

      setSubmitState({
        loading: false,
        error,
        botName: "",
        version: null,
      });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Register a bot</h1>
        <p>Add a named bot to a supported game with its first source submission.</p>
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
                onChange={(event) => setSelectedGame(event.target.value)}
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
                onChange={(event) => setName(event.target.value)}
                maxLength={64}
                required
              />
            </label>

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

            {submitState.version && (
              <p className="success" role="status">
                {submitState.botName} is registered with source version{" "}
                {submitState.version}.
              </p>
            )}

            {submitState.error && (
              <p className="error" role="alert">
                {errorMessageFor(submitState.error)}
              </p>
            )}

            <button
              type="submit"
              disabled={submitState.loading || !name.trim() || !sourceCode.trim()}
            >
              {submitState.loading ? "Registering..." : "Register bot"}
            </button>
          </form>
        </div>
      )}
    </main>
  );
}
