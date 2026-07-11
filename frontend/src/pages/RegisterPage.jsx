import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../useAuth";

function errorMessageFor(error) {
  if (error.code === "email_already_registered") {
    return "That email is already registered.";
  }

  if (error.code === "username_already_taken") {
    return "That username is already taken.";
  }

  return error.message || "Could not create the account.";
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
  });

  async function handleSubmit(event) {
    event.preventDefault();

    setSubmitState({ loading: true, error: null });

    try {
      await register({ email, username, password });
      navigate("/login", { replace: true });
    } catch (error) {
      setSubmitState({ loading: false, error });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Register</h1>
        <p>Create an account to register bots and start matches.</p>
      </div>

      <form className="form-panel" onSubmit={handleSubmit}>
        <label>
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label>
          <span>Username</span>
          <input
            type="text"
            value={username}
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            maxLength={80}
            required
          />
        </label>

        <label>
          <span>Password</span>
          <input
            type="password"
            value={password}
            autoComplete="new-password"
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        {submitState.error && (
          <p className="error" role="alert">
            {errorMessageFor(submitState.error)}
          </p>
        )}

        <button type="submit" disabled={submitState.loading}>
          {submitState.loading ? "Registering..." : "Register"}
        </button>

        <p className="form-footer">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </main>
  );
}
