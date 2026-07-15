import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import { AuthProvider } from "./auth";
import BotPage from "./pages/BotPage";
import BotRegistrationPage from "./pages/BotRegistrationPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import HomePage from "./pages/HomePage";
import MatchHistoryPage from "./pages/MatchHistoryPage";
import LeaderboardPage from "./pages/LeaderboardPage";
import LoginPage from "./pages/LoginPage";
import MatchDetailPage from "./pages/MatchDetailPage";
import PlayerPage from "./pages/PlayerPage";
import RegisterPage from "./pages/RegisterPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import { useAuth } from "./useAuth";

function RequireAuth({ children }) {
  const location = useLocation();
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <main className="empty-state">Checking session...</main>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}

function RequireGuest({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <main className="empty-state">Checking session...</main>;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />

          <Route
            path="/matches"
            element={<MatchHistoryPage />}
          />

          <Route
            path="/leaderboard"
            element={<LeaderboardPage />}
          />

          <Route
            path="/bots/new"
            element={
              <RequireAuth>
                <BotRegistrationPage />
              </RequireAuth>
            }
          />

          <Route
            path="/bots/:botId"
            element={<BotPage />}
          />

          <Route
            path="/players/:username"
            element={<PlayerPage />}
          />

          <Route
            path="/login"
            element={
              <RequireGuest>
                <LoginPage />
              </RequireGuest>
            }
          />

          <Route
            path="/register"
            element={
              <RequireGuest>
                <RegisterPage />
              </RequireGuest>
            }
          />

          <Route
            path="/verify-email"
            element={
              <RequireGuest>
                <VerifyEmailPage />
              </RequireGuest>
            }
          />

          <Route
            path="/forgot-password"
            element={
              <RequireGuest>
                <ForgotPasswordPage />
              </RequireGuest>
            }
          />

          <Route
            path="/reset-password"
            element={
              <RequireGuest>
                <ResetPasswordPage />
              </RequireGuest>
            }
          />

          <Route
            path="/matches/:matchId"
            element={<MatchDetailPage />}
          />

          <Route
            path="/match-jobs/:jobId"
            element={<MatchDetailPage />}
          />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;
