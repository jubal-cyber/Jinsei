"""Runs blocking Windows Hello calls on a worker thread and delivers the result on the UI thread."""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal

from .biometrics import BioResult

_runner: "BioRunner | None" = None


class BioRunner(QObject):
    _finished = Signal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self._next = 1
        self._callbacks: dict[int, Callable[[BioResult], None]] = {}
        self._finished.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    def run(self, fn: Callable[..., BioResult], *args, callback: Callable[[BioResult], None]) -> int:
        token = self._next
        self._next += 1
        self._callbacks[token] = callback

        def work() -> None:
            try:
                result = fn(*args)
            except Exception as exc:  # never let the thread die silently
                result = BioResult("error", f"Windows Hello couldn't start ({exc}).")
            self._finished.emit(token, result)

        threading.Thread(target=work, daemon=True).start()
        return token

    def cancel(self, token: int | None) -> None:
        """Ignore the result of an earlier request (e.g. the person chose the password instead)."""
        if token is not None:
            self._callbacks.pop(token, None)

    def _dispatch(self, token: int, result: BioResult) -> None:
        callback = self._callbacks.pop(token, None)
        if callback:
            callback(result)


def runner() -> BioRunner:
    global _runner
    if _runner is None:
        _runner = BioRunner()
    return _runner
