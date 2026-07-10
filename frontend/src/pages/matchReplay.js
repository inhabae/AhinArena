export function emptyTicTacToeBoard() {
  return Array.from({ length: 3 }, () => Array.from({ length: 3 }, () => null));
}

export function getTicTacToeMovePosition(move) {
  if (Array.isArray(move)) {
    return { row: move[0], col: move[1] };
  }

  return { row: move.row, col: move.col };
}

export function applyTicTacToeMove(board, move, marker) {
  const { row, col } = getTicTacToeMovePosition(move);
  const nextBoard = board.map((row) => [...row]);

  nextBoard[row][col] = marker;

  return nextBoard;
}

export function buildTicTacToeReplay(moves) {
  const boards = [emptyTicTacToeBoard()];
  const lastMoves = [null];
  let currentBoard = boards[0];

  moves.forEach((entry, index) => {
    const marker = index % 2 === 0 ? "X" : "O";
    const lastMove = getTicTacToeMovePosition(entry.move);
    currentBoard = applyTicTacToeMove(currentBoard, entry.move, marker);
    boards.push(currentBoard);
    lastMoves.push(lastMove);
  });

  return { boards, lastMoves };
}
