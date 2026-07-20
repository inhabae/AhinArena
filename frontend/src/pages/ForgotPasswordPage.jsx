import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { requestPasswordReset } from "../api/client";

function emailErrorFor(email) {
  const trimmedEmail = email.trim();
  const emailPattern = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/;

  if (!trimmedEmail) {
    return "Email is required.";
  }

  if (trimmedEmail.length > 254) {
    return "Email must be 254 characters or fewer.";
  }

  if (!/^[\x00-\x7F]*$/.test(trimmedEmail) || !emailPattern.test(trimmedEmail)) {
    return "Enter a valid email address.";
  }

  const [localPart, domain] = trimmedEmail.split("@");
  if (localPart.startsWith(".") || localPart.endsWith(".") || localPart.includes("..")) {
    return "Enter a valid email address.";
  }

  if (domain.split(".").some((part) => part.startsWith("-") || part.endsWith("-"))) {
    return "Enter a valid email address.";
  }

  return "";
}

function isEmailOverLimit(email) {
  return email.trim().length > 254;
}

export default function ForgotPasswordPage() {
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [state, setState] = useState({ loading: false, error: null, result: null });
  const emailError = emailErrorFor(email);
  const showEmailError = (emailTouched || isEmailOverLimit(email)) && Boolean(emailError);

  useEffect(() => {
    setEmail("");
    setEmailTouched(false);
    setState({ loading: false, error: null, result: null });
  }, [location.key]);

  async function handleSubmit(event) {
    event.preventDefault();
    setEmailTouched(true);

    if (emailError) {
      return;
    }

    setState({ loading: true, error: null, result: null });

    try {
      const result = await requestPasswordReset(email);
      setState({ loading: false, error: null, result });
    } catch (error) {
      setState({ loading: false, error, result: null });
    }
  }

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Forgot password</h1>
        <p>Request a reset link for your account email.</p>
      </div>

      <form className="form-panel" onSubmit={handleSubmit}>
        <label>
          <span>Email</span>
          <input
            type="text"
            value={email}
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            onBlur={() => setEmailTouched(true)}
            aria-describedby={showEmailError ? "forgot-password-email-requirements" : undefined}
            aria-invalid={showEmailError}
          />
          {showEmailError && (
            <span id="forgot-password-email-requirements" className="field-error">
              {emailError}
            </span>
          )}
        </label>

        {state.error && (
          <p className="error" role="alert">
            {state.error.message || "Could not request a password reset."}
          </p>
        )}

        {state.result && (
          <div className="inline-success" role="status">
            <p>If an account with that email exists, a password reset link has been sent.</p>
          </div>
        )}

        <button type="submit" disabled={state.loading}>
          {state.loading ? "Sending..." : "Send reset link"}
        </button>

        <p className="form-footer">
          Remembered it? <Link to="/login">Log in</Link>
        </p>
      </form>
    </main>
  );
}
