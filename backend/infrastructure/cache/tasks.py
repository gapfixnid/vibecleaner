from concurrent.futures import ThreadPoolExecutor
from typing import Callable


cache_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vibecleaner-cache")


def submit_cache_task(worker: Callable[[], None]) -> None:
    cache_executor.submit(worker)
