from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class HistoryEntry:
    snapshot: dict


class HistoryManager:
    def __init__(self, capacity: int = 50) -> None:
        # Initialize undo/redo stacks with a maximum capacity.
        self.capacity = capacity
        self._stack: List[HistoryEntry] = []
        self._redo_stack: List[HistoryEntry] = []
        self._lock = False

    def clear(self) -> None:
        # Remove all stored history entries.
        self._stack.clear()
        self._redo_stack.clear()

    def push(self, snapshot: dict) -> None:
        # Add a new state snapshot to the undo stack.
        if self._lock:
            return
        self._stack.append(HistoryEntry(snapshot=snapshot))
        if len(self._stack) > self.capacity:
            self._stack.pop(0)
        self._redo_stack.clear()

    def undo(self, apply_state: Callable[[dict], None]) -> None:
        # Revert to the previous snapshot if available.
        if not self._stack:
            return
        entry = self._stack.pop()
        self._redo_stack.append(entry)
        state = self._stack[-1].snapshot if self._stack else entry.snapshot
        self._apply(state, apply_state)

    def redo(self, apply_state: Callable[[dict], None]) -> None:
        # Reapply the most recently undone snapshot.
        if not self._redo_stack:
            return
        entry = self._redo_stack.pop()
        self._stack.append(entry)
        self._apply(entry.snapshot, apply_state)

    def capture(self, snapshot_provider: Callable[[], dict]) -> None:
        # Record a new snapshot provided by the caller.
        if self._lock:
            return
        self.push(snapshot_provider())

    def restore(self, state: dict, apply_state: Callable[[dict], None]) -> None:
        # Forcefully apply a given state without modifying history.
        self._apply(state, apply_state)

    def _apply(self, state: dict, apply_state: Callable[[dict], None]) -> None:
        # Apply a snapshot while preventing recursive history changes.
        self._lock = True
        try:
            apply_state(state)
        finally:
            self._lock = False


__all__ = ["HistoryManager"]
