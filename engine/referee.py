import json
import selectors
import subprocess
from engine.tictactoe import Game


class BotTimeoutError(RuntimeError):
    pass


class BotProcess:
    def __init__(self, command, timeout=1.0):
        self.timeout = timeout
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def request_move(self, state):
        self.process.stdin.write(json.dumps(state) + "\n")
        self.process.stdin.flush()

        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)

        events = selector.select(timeout=self.timeout)

        if not events:
            self.process.kill()
            raise BotTimeoutError(
                f"Bot timed out after {self.timeout} seconds"
            )

        response = self.process.stdout.readline()

        if not response:
            stderr = self.process.stderr.read()
            raise RuntimeError(f"Bot did not return a move. stderr: {stderr}")

        return json.loads(response)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()


class Referee:
    def __init__(self, x_command, o_command, timeout=2.0):
        self.game = Game()
        self.players = {
            "X": BotProcess(x_command, timeout),
            "O": BotProcess(o_command, timeout),
        }
        self.moves = []

    def run_match(self):
        try:
            while not self.game.board.is_game_over():
                marker = self.game.current_player
                bot = self.players[marker]

                state = {
                    "marker": marker,
                    "board": self.game.board.grid,
                }

                try:
                    response = bot.request_move(state)
                except BotTimeoutError as e:
                    return self._result(
                        winner=self._opponent(marker),
                        reason="timeout",
                        error=str(e),
                        marker=marker,
                    )
                except Exception as e:
                    return self._result(
                        winner=self._opponent(marker),
                        reason="bot_error",
                        error=str(e),
                        marker=marker,
                    )

                move = self._parse_move(response)

                if move is None:
                    return self._result(
                        winner=self._opponent(marker),
                        reason="invalid_move",
                    )

                row, col = move

                if not self.game.make_move(row, col):
                    return self._result(
                        winner=self._opponent(marker),
                        reason="invalid_move",
                    )

                self.moves.append((marker, move))

            winner = self.game.board.winner()

            return self._result(
                winner=winner,
                reason="win" if winner else "draw",
            )

        finally:
            self.players["X"].close()
            self.players["O"].close()

    def _parse_move(self, response):
        if not isinstance(response, dict):
            return None

        row = response.get("row")
        col = response.get("col")

        if not isinstance(row, int) or not isinstance(col, int):
            return None

        return row, col

    def _opponent(self, marker):
        return "O" if marker == "X" else "X"

    def _result(self, winner, reason, **extra):
        result = {
            "winner": winner,
            "reason": reason,
            "moves": self.moves,
            "final_board": self.game.board.grid,
        }

        result.update(extra)
        return result
