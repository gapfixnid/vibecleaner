from __future__ import annotations

from contextlib import contextmanager
from threading import BoundedSemaphore, RLock
from typing import Iterator


class ProviderQueueFullError(RuntimeError):
    pass


class ProviderConcurrencyGate:
    """Bound provider waiters separately from active provider calls."""

    def __init__(self, *, max_concurrency: int = 1, queue_capacity: int = 8) -> None:
        if max_concurrency < 1 or queue_capacity < 0:
            raise ValueError("Provider concurrency must be positive and queue capacity non-negative")
        self._admission = BoundedSemaphore(max_concurrency + queue_capacity)
        self._execution = BoundedSemaphore(max_concurrency)
        self._lock = RLock()
        self._active = 0
        self._waiting = 0
        self._rejected = 0

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._admission.acquire(blocking=False):
            with self._lock:
                self._rejected += 1
            raise ProviderQueueFullError("Provider queue is full; retry later")
        with self._lock:
            self._waiting += 1
        try:
            self._execution.acquire()
            with self._lock:
                self._waiting -= 1
                self._active += 1
            try:
                yield
            finally:
                with self._lock:
                    self._active -= 1
                self._execution.release()
        finally:
            self._admission.release()

    def status(self) -> dict[str, int]:
        with self._lock:
            return {
                "active": self._active,
                "waiting": self._waiting,
                "rejected": self._rejected,
            }
