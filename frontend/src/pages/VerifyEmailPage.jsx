import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { verifyEmail } from "../api/client";

function errorMessageFor(error) {
  if (error.code === "invalid_or_expired_token") {
    return [
      "This verification link has already been used or has expired.",
      "If you already verified your email, you can log in now.",
    ];
  }

  return [error.message || "Could not verify that email address."];
}

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [state, setState] = useState({ loading: true, error: null });

  useEffect(() => {
    if (!token) {
      setState({ loading: false, error: new Error("Verification token is missing.") });
      return;
    }

    let ignore = false;
    verifyEmail(token)
      .then(() => {
        if (!ignore) {
          setState({ loading: false, error: null });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setState({ loading: false, error });
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  return (
    <main className="form-page">
      <div className="page-header">
        <h1>Email verification</h1>
        <p>Confirm your email address to finish account setup.</p>
      </div>

      <section className="form-panel">
        {state.loading && <p>Verifying email...</p>}
        {!state.loading && !state.error && (
          <>
            <p className="success" role="status">
              Email verified. You can log in now.
            </p>
            <p className="form-footer">
              Continue to <Link to="/login">log in</Link>.
            </p>
          </>
        )}
        {state.error && (
          <>
            <div className="error" role="alert">
              {errorMessageFor(state.error).map((message) => (
                <p key={message}>{message}</p>
              ))}
            </div>
            {state.error.code === "invalid_or_expired_token" && (
              <p className="form-footer">
                Continue to <Link to="/login">log in</Link>.
              </p>
            )}
          </>
        )}
      </section>
    </main>
  );
}
