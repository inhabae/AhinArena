import { Link, Route, Routes } from "react-router-dom";

import HomePage from "./pages/HomePage";
import MatchHistoryPage from "./pages/MatchHistoryPage";
import LeaderboardPage from "./pages/LeaderboardPage";
import MatchDetailPage from "./pages/MatchDetailPage";

function App() {
  return (
    <>
      <nav>
        <Link to="/">Home</Link>{" | "}
        <Link to="/matches">Match History</Link>{" | "}
        <Link to="/leaderboard">Leaderboard</Link>
      </nav>

      <hr />

      <Routes>
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
      </Routes>
    </>
  );
}

export default App;