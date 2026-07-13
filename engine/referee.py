import json
import os
import selectors
import subprocess
import time
from typing import Any, Protocol

PROCESS_EXIT_TIMEOUT = 1.0


class BotTimeoutError(RuntimeError):
    pass


class BotProcess:
    def __init__(self, command, timeout=1.0):
        self.timeout = timeout
        self._stdout_buffer = b""
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

        response = self._read_response_line()

        if not response:
            stderr = self.process.stderr.read()
            raise RuntimeError(f"Bot did not return a move. stderr: {stderr}")

        return json.loads(response)

    def _read_response_line(self):
        deadline = time.monotonic() + self.timeout
        stdout_fd = self.process.stdout.fileno()
        os.set_blocking(stdout_fd, False)

        with selectors.DefaultSelector() as selector:
            selector.register(stdout_fd, selectors.EVENT_READ)

            while True:
                if b"\n" in self._stdout_buffer:
                    line, self._stdout_buffer = self._stdout_buffer.split(
                        b"\n",
                        1,
                    )
                    return line.decode()

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._kill_and_wait()
                    raise BotTimeoutError(
                        f"Bot timed out after {self.timeout} seconds"
                    )

                events = selector.select(timeout=remaining)
                if not events:
                    self._kill_and_wait()
                    raise BotTimeoutError(
                        f"Bot timed out after {self.timeout} seconds"
                    )

                while True:
                    try:
                        chunk = os.read(stdout_fd, 4096)
                    except BlockingIOError:
                        break

                    if not chunk:
                        response = self._stdout_buffer.decode()
                        self._stdout_buffer = b""
                        return response

                    self._stdout_buffer += chunk

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=PROCESS_EXIT_TIMEOUT)
            except subprocess.TimeoutExpired:
                self._kill_and_wait()

    def _kill_and_wait(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=PROCESS_EXIT_TIMEOUT)


class GameRules(Protocol):
    players: tuple[str, ...]
    current_player: str

    def bot_state(self, player: str) -> dict[str, Any]:
        pass

    def parse_move(self, response: Any) -> Any:
        pass

    def apply_move(self, move: Any) -> bool:
        pass

    def is_terminal(self) -> bool:
        pass

    def winner(self) -> str | None:
        pass

    def forfeit_winner(self, player: str) -> str | None:
        pass

    def board_state(self) -> Any:
        pass


class Referee:
    def __init__(
        self,
        player_commands,
        game_rules: GameRules,
        timeout=2.0,
        on_move=None,
    ):
        self.game = game_rules
        self.player_ids = tuple(self.game.players)
        missing_players = set(self.player_ids) - set(player_commands)
        if missing_players:
            raise ValueError(
                f"Missing bot commands for players: {sorted(missing_players)}"
            )

        self.bot_processes = {
            player: BotProcess(player_commands[player], timeout)
            for player in self.player_ids
        }
        self.on_move = on_move

    def run_match(self):
        try:
            while not self.game.is_terminal():
                player = self.game.current_player
                bot = self.bot_processes[player]
                state = self.game.bot_state(player)

                try:
                    response = bot.request_move(state)
                except BotTimeoutError as e:
                    return self._result(
                        winner=self.game.forfeit_winner(player),
                        reason="timeout",
                        error=str(e),
                        player=player,
                    )
                except Exception as e:
                    return self._result(
                        winner=self.game.forfeit_winner(player),
                        reason="bot_error",
                        error=str(e),
                        player=player,
                    )

                move = self.game.parse_move(response)

                if move is None:
                    return self._result(
                        winner=self.game.forfeit_winner(player),
                        reason="invalid_move",
                    )

                if not self.game.apply_move(move):
                    return self._result(
                        winner=self.game.forfeit_winner(player),
                        reason="invalid_move",
                    )

                if self.on_move is not None:
                    self.on_move(
                        player,
                        move,
                        self.game.board_state(),
                    )

            winner = self.game.winner()

            return self._result(
                winner=winner,
                reason="win" if winner else "draw",
            )

        finally:
            for bot_process in self.bot_processes.values():
                bot_process.close()

    def _result(self, winner, reason, **extra):
        result = {
            "winner": winner,
            "reason": reason,
        }

        result.update(extra)
        return result
