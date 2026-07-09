from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class CacheTaskQueue:
    """Single-worker background queue for cache warm-up tasks (container-owned)."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vibecleaner-cache")

    def submit(self, worker: Callable[[], None]) -> None:
        self._executor.submit(worker)
