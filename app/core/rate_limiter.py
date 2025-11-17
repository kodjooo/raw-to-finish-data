from __future__ import annotations

import time
from collections import deque
from typing import Deque


class RateLimiter:
    """Примитивный ограничитель RPS/RPM для последовательных вызовов."""

    def __init__(self, *, max_rps: float, max_rpm: int) -> None:
        self._min_interval = 1.0 / max_rps if max_rps > 0 else 0.0
        self._max_rpm = max_rpm
        self._last_call: float | None = None
        self._window: Deque[float] = deque()

    def wait(self) -> None:
        if self._min_interval > 0 and self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

        if self._max_rpm <= 0:
            return

        while True:
            now = time.time()
            while self._window and now - self._window[0] >= 60:
                self._window.popleft()
            if len(self._window) < self._max_rpm:
                self._window.append(now)
                return
            sleep_time = 60 - (now - self._window[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
