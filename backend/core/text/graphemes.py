from __future__ import annotations

import unicodedata

import regex


def graphemes(text: object) -> list[str]:
    normalized = unicodedata.normalize("NFC", str(text or ""))
    return regex.findall(r"\X", normalized)


def meaningful_graphemes(text: object) -> list[str]:
    return [
        cluster
        for cluster in graphemes(text)
        if not all(
            char.isspace()
            or unicodedata.category(char).startswith("C")
            for char in cluster
        )
    ]


def grapheme_count(
    text: object,
    *,
    ignore_space: bool = True,
    ignore_control: bool = True,
) -> int:
    clusters = graphemes(text)
    if not ignore_space and not ignore_control:
        return len(clusters)
    return sum(
        not all(
            (ignore_space and char.isspace())
            or (
                ignore_control
                and unicodedata.category(char).startswith("C")
            )
            for char in cluster
        )
        for cluster in clusters
    )


def has_repeated_grapheme(text: object, threshold: int = 9) -> bool:
    run = 0
    previous: str | None = None
    for cluster in meaningful_graphemes(text):
        if cluster == previous:
            run += 1
        else:
            previous = cluster
            run = 1
        if run >= threshold:
            return True
    return False


def script_ratio(text: object, script: str) -> float:
    clusters = meaningful_graphemes(text)
    if not clusters:
        return 0.0
    normalized = script.strip().lower()

    def matches(cluster: str) -> bool:
        if normalized in {"japanese", "ja"}:
            return any(
                "\u3040" <= char <= "\u30ff"
                or "\u3400" <= char <= "\u9fff"
                for char in cluster
            )
        if normalized in {"korean", "ko", "hangul"}:
            return any(
                "\u1100" <= char <= "\u11ff"
                or "\u3130" <= char <= "\u318f"
                or "\uac00" <= char <= "\ud7af"
                for char in cluster
            )
        if normalized in {"latin", "english", "en"}:
            return any(
                "LATIN" in unicodedata.name(char, "")
                for char in cluster
            )
        return False

    return sum(matches(cluster) for cluster in clusters) / len(clusters)
