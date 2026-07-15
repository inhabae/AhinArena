import { Route, Routes } from "react-router-dom";

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
            element={<BotRegistrationPage />}
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
            element={<LoginPage />}
          />

          <Route
            path="/register"
            element={<RegisterPage />}
          />

          <Route
            path="/verify-email"
            element={<VerifyEmailPage />}
          />

          <Route
            path="/forgot-password"
            element={<ForgotPasswordPage />}
          />

          <Route
            path="/reset-password"
            element={<ResetPasswordPage />}
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
