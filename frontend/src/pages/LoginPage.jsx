import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../useAuth";

function errorMessageFor(error) {
  if (error.code === "invalid_credentials") {
    return "The email, username, or password is incorrect.";
  }

  if (error.code === "email_not_verified") {
    return "Please verify your email before logging in.";
  }

  return error.message || "Could not log in.";
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [loginIdentifier, setLoginIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
  });

  async function handleSubmit(event) {
    event.preventDefault();

    setSubmitState({ loading: true, error: null });

    try {
      await login({ login: loginIdentifier, password });
      navigate("/", { replace: true });
    } catch (error) {
      setSubmitState({ loading: false, error });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Log in</h1>
        <p>Use your account to start matches and register bots.</p>
      </div>

      <form className="form-panel" onSubmit={handleSubmit}>
        <label>
          <span>Email or username</span>
          <input
            type="text"
            value={loginIdentifier}
            autoComplete="username"
            onChange={(event) => setLoginIdentifier(event.target.value)}
            required
          />
        </label>

        <label>
          <span>Password</span>
          <input
            type="password"
            value={password}
            autoComplete="current-password"
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
          {submitState.loading ? "Logging in..." : "Log in"}
        </button>

        <p className="form-footer">
          Need an account? <Link to="/register">Register</Link>
        </p>
        <p className="form-footer">
          Forgot your password? <Link to="/forgot-password">Reset it</Link>
        </p>
      </form>
    </main>
  );
}
