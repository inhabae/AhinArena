class Board:
    ROWS = 6
    COLUMNS = 7
    EMPTY = " "

    def __init__(self):
        self.grid = [
            [self.EMPTY for _ in range(self.COLUMNS)]
            for _ in range(self.ROWS)
        ]

    def drop_marker(self, column, marker):
        if column < 0 or column >= self.COLUMNS:
            return False

        for row in range(self.ROWS - 1, -1, -1):
            if self.grid[row][column] == self.EMPTY:
                self.grid[row][column] = marker
                return True

        return False

    def legal_moves(self):
        moves = []

        for column in range(self.COLUMNS):
            if self.grid[0][column] == self.EMPTY:
                moves.append(column)

        return moves

    def winner(self):
        directions = [
            (0, 1),
            (1, 0),
            (1, 1),
            (1, -1),
        ]

        for row in range(self.ROWS):
            for column in range(self.COLUMNS):
                marker = self.grid[row][column]

                if marker == self.EMPTY:
                    continue

                for row_delta, column_delta in directions:
                    if self._has_four_from(
                        row,
                        column,
                        row_delta,
                        column_delta,
                        marker,
                    ):
                        return marker

        return None

    def is_draw(self):
        return self.winner() is None and len(self.legal_moves()) == 0

    def is_game_over(self):
        return self.winner() is not None or len(self.legal_moves()) == 0

    def _has_four_from(self, row, column, row_delta, column_delta, marker):
        for offset in range(4):
            next_row = row + row_delta * offset
            next_column = column + column_delta * offset

            if not self._is_in_bounds(next_row, next_column):
                return False

            if self.grid[next_row][next_column] != marker:
                return False

        return True

    def _is_in_bounds(self, row, column):
        return (
            0 <= row < self.ROWS
            and 0 <= column < self.COLUMNS
        )


class Game:
    players = ("X", "O")

    def __init__(self):
        self.board = Board()
        self.current_player = "X"

    def make_move(self, column):
        if self.board.is_game_over():
            return False

        if not self.board.drop_marker(column, self.current_player):
            return False

        self.current_player = "O" if self.current_player == "X" else "X"
        return True

    def bot_state(self, marker):
        return {
            "marker": marker,
            "board": self.board_state(),
        }

    def parse_move(self, response):
        if not isinstance(response, dict):
            return None

        column = response.get("col")

        if not isinstance(column, int):
            return None

        return column

    def apply_move(self, move):
        return self.make_move(move)

    def is_terminal(self):
        return self.board.is_game_over()

    def winner(self):
        return self.board.winner()

    def forfeit_winner(self, player):
        first, second = self.players
        return second if player == first else first

    def board_state(self):
        return [row.copy() for row in self.board.grid]
