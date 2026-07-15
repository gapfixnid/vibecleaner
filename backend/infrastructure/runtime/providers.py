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


def model_session_providers(model: Any) -> list[str]:
    providers: set[str] = set()
    for value in getattr(model, "__dict__", {}).values():
        names = session_providers(value)
        if names:
            providers.update(names)
    return sorted(providers)
