import { IconApps, IconCircles, IconTicTac } from "@tabler/icons-react";

export const supportedGames = [
  { id: "tictactoe", label: "Tic Tac Toe", icon: IconTicTac },
  { id: "connect-four", label: "Connect Four", icon: IconCircles },
];

export const gameFilters = [
  { id: "", label: "All games", icon: IconApps },
  ...supportedGames,
];

export const defaultGameId = supportedGames[0].id;

export function formatGame(gameId) {
  return supportedGames.find((game) => game.id === gameId)?.label ?? gameId;
}

export function isSupportedGame(gameId) {
  return supportedGames.some((game) => game.id === gameId);
}
