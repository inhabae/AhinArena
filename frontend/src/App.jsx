import { Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import HomePage from "./pages/HomePage";
import MatchHistoryPage from "./pages/MatchHistoryPage";
import LeaderboardPage from "./pages/LeaderboardPage";
import MatchDetailPage from "./pages/MatchDetailPage";

function App() {
  return (
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
          path="/matches/:matchId"
          element={<MatchDetailPage />}
        />
      </Route>
    </Routes>
  );
}

export default App;
