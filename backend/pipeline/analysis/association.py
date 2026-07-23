from __future__ import annotations


def can_merge_bubble_sources(
    first_id: int | None,
    second_id: int | None,
) -> bool:
    """Never merge blocks that came from different detected bubbles."""
    if first_id is not None or second_id is not None:
        return first_id is not None and first_id == second_id
    return True
