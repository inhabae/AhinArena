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

export function emptyConnectFourBoard() {
  return Array.from({ length: 6 }, () => Array.from({ length: 7 }, () => null));
}

export function getConnectFourMoveColumn(move) {
  if (typeof move === "number") {
    return move;
  }

  return move.col;
}

export function applyConnectFourMove(board, move, marker) {
  const column = getConnectFourMoveColumn(move);
  const nextBoard = board.map((row) => [...row]);

  for (let row = nextBoard.length - 1; row >= 0; row -= 1) {
    if (nextBoard[row][column] === null) {
      nextBoard[row][column] = marker;
      return {
        board: nextBoard,
        lastMove: { row, col: column },
      };
    }
  }

  return {
    board: nextBoard,
    lastMove: null,
  };
}

export function buildConnectFourReplay(moves) {
  const boards = [emptyConnectFourBoard()];
  const lastMoves = [null];
  let currentBoard = boards[0];

  moves.forEach((entry, index) => {
    const marker = index % 2 === 0 ? "X" : "O";
    const next = applyConnectFourMove(currentBoard, entry.move, marker);
    currentBoard = next.board;
    boards.push(currentBoard);
    lastMoves.push(next.lastMove);
  });

  return { boards, lastMoves };
}
