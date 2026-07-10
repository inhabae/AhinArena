import { useParams } from "react-router-dom";

export default function MatchDetailPage() {
  const { matchId } = useParams();

  return (
    <main>
      <h1>Match Detail</h1>
      <p>Placeholder for match {matchId}.</p>
    </main>
  );
}
