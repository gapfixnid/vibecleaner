from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from threading import RLock
from typing import Callable, Generic, TypeVar


T = TypeVar("T")
MiB = 1024 * 1024


@dataclass(frozen=True)
class TileCacheKey:
    namespace: str
    page_id: str
    bubble_id: int
    render_fingerprint: str


class TextLayerCache(Generic[T]):
    """Byte-bounded LRU with per-key singleflight creation."""

    def __init__(self, max_bytes: int = 96 * MiB) -> None:
        self.max_bytes = max_bytes
        self._bytes = 0
        self._entries: OrderedDict[TileCacheKey, T] = OrderedDict()
        self._inflight: dict[TileCacheKey, Future[T]] = {}
        self._lock = RLock()

    @staticmethod
    def _size(value: T) -> int:
        return len(getattr(value, "png_bytes", b""))

    @property
    def current_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def get(self, key: TileCacheKey) -> T | None:
        with self._lock:
            value = self._entries.get(key)
            if value is not None:
                self._entries.move_to_end(key)
            return value

    def find_by_public_key(self, namespace: str, page_id: str, bubble_id: int, cache_key: str) -> T | None:
        with self._lock:
            for key, value in reversed(self._entries.items()):
                if (
                    key.namespace == namespace
                    and key.page_id == page_id
                    and key.bubble_id == bubble_id
                    and key.render_fingerprint.startswith(cache_key)
                ):
                    self._entries.move_to_end(key)
                    return value
        return None

    def get_or_create(self, key: TileCacheKey, factory: Callable[[], T]) -> T:
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

        assert future is not None
        if not owner:
            return future.result()

        try:
            value = factory()
            size = self._size(value)
            with self._lock:
                if size <= 32 * MiB and size <= self.max_bytes // 4:
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

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._bytes = 0

