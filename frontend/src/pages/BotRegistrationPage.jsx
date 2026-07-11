import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createBot } from "../api/client";
import { useAuth } from "../useAuth";

const games = [
  { id: "tictactoe", label: "Tic Tac Toe" },
  { id: "connect-four", label: "Connect Four" },
];

function errorMessageFor(error) {
  if (error.code === "unsupported_game") {
    return "This game is not supported yet.";
  }

  if (error.code === "bot_name_taken") {
    return "A bot with this name already exists for the selected game.";
  }

  return error.message || "The bot could not be registered.";
}

export default function BotRegistrationPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [selectedGame, setSelectedGame] = useState(games[0].id);
  const [name, setName] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
  });

  async function handleSubmit(event) {
    event.preventDefault();

    if (!isAuthenticated) {
      navigate("/login?next=/bots/new");
      return;
    }

    if (!name.trim()) {
      return;
    }

    setSubmitState({ loading: true, error: null });

    try {
      await createBot({
        game_id: selectedGame,
        name: name.trim(),
      });
      navigate("/");
    } catch (error) {
      if (error.status === 401) {
        navigate("/login?next=/bots/new");
        return;
      }

      setSubmitState({ loading: false, error });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Register a bot</h1>
        <p>Add a named bot to a supported game under your account.</p>
      </div>

      {loading && <p className="empty-state">Checking session...</p>}

      {!loading && !isAuthenticated && (
        <section className="form-panel login-gate">
          <div>
            <h2>Log in to register a bot</h2>
            <p>Bot ownership is tied to your account.</p>
          </div>
          <Link className="button-link" to="/login?next=/bots/new">
            Log in
          </Link>
        </section>
      )}

      {!loading && isAuthenticated && (
        <form className="form-panel" onSubmit={handleSubmit}>
          <label>
            <span>Game</span>
            <select
              value={selectedGame}
              onChange={(event) => setSelectedGame(event.target.value)}
            >
              {games.map((game) => (
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
              maxLength={120}
              required
            />
          </label>

          {submitState.error && (
            <p className="error" role="alert">
              {errorMessageFor(submitState.error)}
            </p>
          )}

          <button type="submit" disabled={submitState.loading || !name.trim()}>
            {submitState.loading ? "Registering..." : "Register bot"}
          </button>
        </form>
      )}
    </main>
  );
}
