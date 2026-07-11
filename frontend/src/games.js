export const supportedGames = [
  { id: "tictactoe", label: "Tic Tac Toe" },
  { id: "connect-four", label: "Connect Four" },
];

export const gameFilters = [
  { id: "", label: "All games" },
  ...supportedGames,
];

export const defaultGameId = supportedGames[0].id;

export function formatGame(gameId) {
  return supportedGames.find((game) => game.id === gameId)?.label ?? gameId;
}

export function isSupportedGame(gameId) {
  return supportedGames.some((game) => game.id === gameId);
}
