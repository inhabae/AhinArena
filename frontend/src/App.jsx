import { Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import { AuthProvider } from "./auth";
import BotRegistrationPage from "./pages/BotRegistrationPage";
import HomePage from "./pages/HomePage";
import MatchHistoryPage from "./pages/MatchHistoryPage";
import LeaderboardPage from "./pages/LeaderboardPage";
import LoginPage from "./pages/LoginPage";
import MatchDetailPage from "./pages/MatchDetailPage";
import PlayerPage from "./pages/PlayerPage";
import RegisterPage from "./pages/RegisterPage";

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
            path="/matches/:matchId"
            element={<MatchDetailPage />}
          />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;
