"""Helpers for reporting providers actually attached to model sessions."""

from typing import Any


def session_providers(session: Any) -> list[str] | None:
    getter = getattr(session, "get_providers", None)
    if not callable(getter):
        return None
    try:
        return [str(provider) for provider in getter()]
    except Exception:
        return None


def model_session_providers(model: Any, *, _depth: int = 0) -> list[str]:
    if model is None or _depth > 2:
        return []
    providers: set[str] = set()
    for value in getattr(model, "__dict__", {}).values():
        names = session_providers(value)
        if names:
            providers.update(names)
        elif hasattr(value, "__dict__"):
            providers.update(model_session_providers(value, _depth=_depth + 1))
    return sorted(providers)
