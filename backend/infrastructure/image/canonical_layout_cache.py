from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future
from threading import RLock
from typing import Callable, Generic, TypeVar

from ..runtime.qt import QtRenderExecutor
from .render_budget import CANONICAL_LAYOUT_BUDGET


T = TypeVar("T")
class CanonicalLayoutCache(Generic[T]):
    """Byte-bounded LRU and singleflight for immutable layout artifacts."""

    def __init__(
        self,
        executor: QtRenderExecutor,
        max_bytes: int = CANONICAL_LAYOUT_BUDGET,
    ) -> None:
        self.executor = executor
        self.max_bytes = max_bytes
        self._bytes = 0
        self._entries: OrderedDict[str, T] = OrderedDict()
        self._inflight: dict[str, Future[T]] = {}
        self._lock = RLock()
        self._generation = 0

    @staticmethod
    def _size(value: T) -> int:
        return int(getattr(value, "byte_size", 0))

    @property
    def current_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        if self.executor.is_worker_thread():
            raise RuntimeError("Canonical layout cache cannot be entered from the Qt worker")
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached
            future = self._inflight.get(key)
            owner = future is None
            if owner:
                future = Future()
                self._inflight[key] = future
            generation = self._generation

        assert future is not None
        if not owner:
            return future.result()

        try:
            value = factory()
            size = self._size(value)
            with self._lock:
                if (
                    generation == self._generation
                    and 0 < size <= self.max_bytes
                ):
                    self._entries[key] = value
                    self._entries.move_to_end(key)
                    self._bytes += size
                    while self._bytes > self.max_bytes and self._entries:
                        _old_key, old_value = self._entries.popitem(last=False)
                        self._bytes -= self._size(old_value)
                future.set_result(value)
            return value
        except BaseException as exc:
            with self._lock:
                future.set_exception(exc)
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)

    def clear(self, *, wait: bool = False) -> None:
        with self._lock:
            self._generation += 1
        if wait:
            with self._lock:
                pending = list(self._inflight.values())
            for future in pending:
                try:
                    future.result()
                except Exception:
                    pass
        with self._lock:
            self._entries.clear()
            self._bytes = 0
