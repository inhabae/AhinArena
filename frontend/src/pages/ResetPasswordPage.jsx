import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { confirmPasswordReset } from "../api/client";

function passwordErrorFor(password) {
  const requirements = [];
  if (password.length < 8) requirements.push("8+ characters");
  if (password.length > 72) requirements.push("72 characters or fewer");
  if (!/[a-z]/.test(password)) requirements.push("a lowercase letter");
  if (!/[A-Z]/.test(password)) requirements.push("an uppercase letter");
  if (!/[0-9]/.test(password)) requirements.push("a number");
  if (!/[^A-Za-z0-9]/.test(password)) requirements.push("a symbol");
  return requirements.length > 0 ? `Password must include ${requirements.join(", ")}.` : "";
}

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [state, setState] = useState({ loading: false, error: null, complete: false });
  const passwordError = passwordErrorFor(password);
  const showPasswordError = passwordTouched && Boolean(passwordError);

  async function handleSubmit(event) {
    event.preventDefault();
    setPasswordTouched(true);

    if (!token || passwordError) {
      return;
    }

    setState({ loading: true, error: null, complete: false });

    try {
      await confirmPasswordReset({ token, password });
      setState({ loading: false, error: null, complete: true });
    } catch (error) {
      setState({ loading: false, error, complete: false });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Reset password</h1>
        <p>Choose a new password for your AhinArena account.</p>
      </div>

      <form className="form-panel" onSubmit={handleSubmit}>
        {!token && (
          <p className="error" role="alert">
            Reset token is missing.
          </p>
        )}

        <label>
          <span>New password</span>
          <input
            type="password"
            value={password}
            autoComplete="new-password"
            onChange={(event) => setPassword(event.target.value)}
            onBlur={() => setPasswordTouched(true)}
            aria-describedby={showPasswordError ? "password-requirements" : undefined}
            aria-invalid={showPasswordError}
          />
          {showPasswordError && (
            <span id="password-requirements" className="field-error">
              {passwordError}
            </span>
          )}
        </label>

        {state.error && (
          <p className="error" role="alert">
            {state.error.message || "Could not reset the password."}
          </p>
        )}

        {state.complete && (
          <p className="success" role="status">
            Password updated. You can log in now.
          </p>
        )}

        <button type="submit" disabled={state.loading || !token}>
          {state.loading ? "Resetting..." : "Reset password"}
        </button>

        <p className="form-footer">
          Continue to <Link to="/login">log in</Link>.
        </p>
      </form>
    </main>
  );
}
