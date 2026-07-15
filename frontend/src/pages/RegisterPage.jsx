import { useState } from "react";
import { Link } from "react-router-dom";

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

function usernameErrorFor(username) {
  const trimmedUsername = username.trim();

  if (!trimmedUsername) {
    return "Username must be 3-20 characters.";
  }

  if (trimmedUsername.length < 3 || trimmedUsername.length > 20) {
    return "Username must be 3-20 characters.";
  }

  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(trimmedUsername)) {
    return "Username can only use letters, numbers, periods, underscores, or hyphens.";
  }

  return "";
}

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

function passwordErrorFor(password) {
  const requirements = [];

  if (password.length < 8) {
    requirements.push("8+ characters");
  }

  if (password.length > 72) {
    requirements.push("72 characters or fewer");
  }

  if (!/[a-z]/.test(password)) {
    requirements.push("a lowercase letter");
  }

  if (!/[A-Z]/.test(password)) {
    requirements.push("an uppercase letter");
  }

  if (!/[0-9]/.test(password)) {
    requirements.push("a number");
  }

  if (!/[^A-Za-z0-9]/.test(password)) {
    requirements.push("a symbol");
  }

  if (requirements.length > 0) {
    return `Password must include ${requirements.join(", ")}.`;
  }

  return "";
}

function isEmailOverLimit(email) {
  return email.trim().length > 254;
}

function isUsernameOverLimit(username) {
  return username.trim().length > 20;
}

function isPasswordOverLimit(password) {
  return password.length > 72;
}

export default function RegisterPage() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitState, setSubmitState] = useState({
    loading: false,
    error: null,
    registered: null,
  });
  const [emailTouched, setEmailTouched] = useState(false);
  const [usernameTouched, setUsernameTouched] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);
  const emailError = emailErrorFor(email);
  const usernameError = usernameErrorFor(username);
  const passwordError = passwordErrorFor(password);
  const showEmailError = (emailTouched || isEmailOverLimit(email)) && Boolean(emailError);
  const showUsernameError =
    (usernameTouched || isUsernameOverLimit(username)) && Boolean(usernameError);
  const showPasswordError =
    (passwordTouched || isPasswordOverLimit(password)) && Boolean(passwordError);

  async function handleSubmit(event) {
    event.preventDefault();
    setEmailTouched(true);
    setUsernameTouched(true);
    setPasswordTouched(true);

    if (emailError || usernameError || passwordError) {
      return;
    }

    setSubmitState({ loading: true, error: null, registered: null });

    try {
      const registered = await register({ email, username, password });
      setSubmitState({ loading: false, error: null, registered });
    } catch (error) {
      setSubmitState({ loading: false, error, registered: null });
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
            type="text"
            value={email}
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            onBlur={() => setEmailTouched(true)}
            aria-describedby={showEmailError ? "email-requirements" : undefined}
            aria-invalid={showEmailError}
          />
          {showEmailError && (
            <span id="email-requirements" className="field-error">
              {emailError}
            </span>
          )}
        </label>

        <label>
          <span>Username</span>
          <input
            type="text"
            value={username}
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            onBlur={() => setUsernameTouched(true)}
            aria-describedby={showUsernameError ? "username-requirements" : undefined}
            aria-invalid={showUsernameError}
          />
          {showUsernameError && (
            <span id="username-requirements" className="field-error">
              {usernameError}
            </span>
          )}
        </label>

        <label>
          <span>Password</span>
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

        {submitState.error && (
          <p className="error" role="alert">
            {errorMessageFor(submitState.error)}
          </p>
        )}

        {submitState.registered && (
          <div className="form-message success" role="status">
            <p>Account created. Verify your email before logging in.</p>
            <p>
              Development verification link:{" "}
              <Link to={`/verify-email?token=${submitState.registered.verification_token}`}>
                Verify email
              </Link>
            </p>
          </div>
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
