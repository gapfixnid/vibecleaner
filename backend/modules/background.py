"""Small helper for fire-and-forget background tasks."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def run_background_task(
    target: Callable[..., Any],
    *args: Any,
    name: str | None = None,
    on_error: Callable[[Exception], None] | None = None,
    **kwargs: Any,
) -> threading.Thread:
    """Run a callable in a daemon thread with consistent exception logging."""

    def wrapped() -> None:
        try:
            target(*args, **kwargs)
        except Exception as exc:
            logger.exception("Background task failed: %s", name or getattr(target, "__name__", "worker"))
            if on_error is not None:
                on_error(exc)

    thread = threading.Thread(target=wrapped, daemon=True, name=name)
    thread.start()
    return thread

