import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../useAuth";

export default function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
  });

  const searchParams = new URLSearchParams(location.search);
  const nextPath = searchParams.get("next") || "/";

  async function handleSubmit(event) {
    event.preventDefault();

    setSubmitState({ loading: true, error: null });

    try {
      await login({ email, password });
      navigate(nextPath, { replace: true });
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
            {submitState.error.message}
          </p>
        )}

        <button type="submit" disabled={submitState.loading}>
          {submitState.loading ? "Logging in..." : "Log in"}
        </button>
      </form>
    </main>
  );
}
