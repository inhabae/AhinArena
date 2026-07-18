class Board:
    def __init__(self):
        self.grid = [[" " for _ in range(3)] for _ in range(3)]

    def place_marker(self, row, col, marker):
        if row < 0 or row > 2 or col < 0 or col > 2:
            return False

        if self.grid[row][col] != " ":
            return False

        self.grid[row][col] = marker
        return True

    def legal_moves(self):
        moves = []

        for row in range(3):
            for col in range(3):
                if self.grid[row][col] == " ":
                    moves.append((row, col))
        
        return moves
    
    def winner(self):
        lines = []

        # rows
        lines.extend(self.grid)

        # columns
        for col in range(3):
            lines.append([self.grid[0][col], self.grid[1][col], self.grid[2][col]])

        # diagonals
        lines.append([self.grid[0][0], self.grid[1][1], self.grid[2][2]])
        lines.append([self.grid[0][2], self.grid[1][1], self.grid[2][0]])

        for line in lines:
            if line[0] != " " and line[0] == line[1] == line[2]:
                return line[0]

        return None
    
    def is_draw(self):
        return self.winner() is None and len(self.legal_moves()) == 0

    def is_game_over(self):
        return self.winner() is not None or len(self.legal_moves()) == 0

    def print_board(self):
        for row in self.grid:
            print(" | ".join(row))
            print("-" * 9)

class Game:
    players = ("X", "O")

    def __init__(self):
        self.board = Board()
        self.current_player = "X"

    def make_move(self, row, col):
        if self.board.is_game_over():
            return False

        if not self.board.place_marker(row, col, self.current_player):
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

        row = response.get("row")
        col = response.get("col")

        if (
            not isinstance(row, int)
            or isinstance(row, bool)
            or not isinstance(col, int)
            or isinstance(col, bool)
        ):
            return None

        return row, col

    def apply_move(self, move):
        row, col = move
        return self.make_move(row, col)

    def is_terminal(self):
        return self.board.is_game_over()

    def winner(self):
        return self.board.winner()

    def forfeit_winner(self, player):
        first, second = self.players
        return second if player == first else first

    def board_state(self):
        return [row.copy() for row in self.board.grid]
