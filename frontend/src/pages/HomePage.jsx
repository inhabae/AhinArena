import { useEffect, useState } from "react";

import { getHealth, request } from "../api/client";

export default function HomePage() {
  const [health, setHealth] = useState({
    loading: true,
    value: null,
    error: null,
  });
  const [simulatedError, setSimulatedError] = useState(null);

  useEffect(() => {
    let ignore = false;

    getHealth()
      .then((value) => {
        if (!ignore) {
          setHealth({ loading: false, value, error: null });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setHealth({ loading: false, value: null, error });
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  async function simulateApiError() {
    try {
      setSimulatedError(null);
      await request("/api-error-test");
    } catch (error) {
      setSimulatedError(error.message);
    }
  }

  return (
    <main>
      <h1>Home</h1>

      <section className="status-panel" aria-live="polite">
        <h2>Backend Health</h2>
        {health.loading && <p>Checking API...</p>}
        {health.error && <p className="error">API error: {health.error.message}</p>}
        {health.value && <p>GET /health: {health.value.status}</p>}
      </section>

      <section className="status-panel">
        <h2>API Error Handling</h2>
        <button type="button" onClick={simulateApiError}>
          Simulate API error
        </button>
        {simulatedError && <p className="error">{simulatedError}</p>}
      </section>
    </main>
  );
}
