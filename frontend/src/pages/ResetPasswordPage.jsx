import { useEffect, useState } from "react";
import { IconCircleCheck } from "@tabler/icons-react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { confirmPasswordReset, validatePasswordResetToken } from "../api/client";

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

function errorMessageFor(error) {
  if (error.code === "invalid_or_expired_token") {
    return [
      "This reset link has already been used or has expired.",
      "Request a new password reset link if you still need to change your password.",
    ];
  }

  return [error.message || "Could not reset the password."];
}

export default function ResetPasswordPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [state, setState] = useState({
    checkingToken: Boolean(token),
    loading: false,
    error: null,
    complete: false,
  });
  const passwordError = passwordErrorFor(password);
  const showPasswordError = passwordTouched && Boolean(passwordError);
  const resetLinkUnavailable = state.error?.code === "invalid_or_expired_token";
  const showResetForm = !state.checkingToken && !resetLinkUnavailable && !state.complete;

  useEffect(() => {
    if (!token) {
      setState({ checkingToken: false, loading: false, error: null, complete: false });
      return;
    }

    let ignore = false;
    setState({ checkingToken: true, loading: false, error: null, complete: false });

    validatePasswordResetToken(token)
      .then(() => {
        if (!ignore) {
          setState({ checkingToken: false, loading: false, error: null, complete: false });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setState({ checkingToken: false, loading: false, error, complete: false });
        }
      });

    return () => {
      ignore = true;
    };
  }, [location.key, token]);

  async function handleSubmit(event) {
    event.preventDefault();
    setPasswordTouched(true);

    if (!token || passwordError) {
      return;
    }

    setState({ checkingToken: false, loading: true, error: null, complete: false });

    try {
      await confirmPasswordReset({ token, password });
      setState({ checkingToken: false, loading: false, error: null, complete: true });
    } catch (error) {
      setState({ checkingToken: false, loading: false, error, complete: false });
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

        {state.checkingToken && <p>Checking reset link...</p>}

        {state.error && (
          <div className="error" role="alert">
            {errorMessageFor(state.error).map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        )}

        {resetLinkUnavailable && (
          <p className="form-footer">
            <Link to="/forgot-password">Request a new reset link</Link>
          </p>
        )}

        {showResetForm && (
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
        )}

        {state.complete && (
          <div className="auth-success-state" role="status">
            <div className="auth-success-heading">
              <h2>Password updated</h2>
              <IconCircleCheck aria-hidden="true" />
            </div>
            <p>You can log in now.</p>
          </div>
        )}

        {showResetForm && (
          <button type="submit" disabled={state.loading || !token}>
            {state.loading ? "Resetting..." : "Reset password"}
          </button>
        )}

        <p className="form-footer">
          Continue to <Link to="/login">log in</Link>
        </p>
      </form>
    </main>
  );
}
