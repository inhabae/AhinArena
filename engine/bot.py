from abc import ABC, abstractmethod

class Bot(ABC):
    def __init__(self, marker):
        self.marker = marker

    @abstractmethod
    def choose_move(self, board) -> tuple[int, int]:
        """Return the next move as (row, col)."""
        raise NotImplementedError