"""Versioning and compatibility rules for persisted project metadata."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Callable, Mapping
import uuid

from ...core.version import __version__ as APP_VERSION


PROJECT_FORMAT = "vibecleaner-project"
CURRENT_PROJECT_SCHEMA_VERSION = 2
CURRENT_PROJECT_VERSION = "2.0"  # Compatibility alias for existing readers.
LEGACY_PROJECT_SCHEMA_VERSION = 1
SAFE_PAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
ORIGINAL_PAGE_ID_EXTENSION = "vibecleaner_original_page_id"


class ProjectSchemaError(ValueError):
    """Base error for project metadata that cannot be loaded safely."""


class InvalidProjectSchemaError(ProjectSchemaError):
    """Raised when project metadata does not match the expected structure."""


class UnsupportedProjectVersionError(ProjectSchemaError):
    """Raised when no safe migration path exists for a project version."""


def _schema_from_version_alias(raw_version: Any) -> int:
    if isinstance(raw_version, bool):
        raise InvalidProjectSchemaError("Project version must be a number or a 'major.minor' string")
    if isinstance(raw_version, (int, float)):
        raw_version = str(raw_version)
    if not isinstance(raw_version, str):
        raise InvalidProjectSchemaError("Project version must be a number or a 'major.minor' string")

    parts = raw_version.strip().split(".")
    if len(parts) == 1 and parts[0].isdigit():
        parts.append("0")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise InvalidProjectSchemaError(f"Invalid project version: {raw_version!r}")
    major, minor = int(parts[0]), int(parts[1])
    if minor != 0:
        raise UnsupportedProjectVersionError(
            f"Legacy project version {raw_version!r} is not supported; update VibeCleaner to open this project."
        )
    return major


def _read_schema_version(metadata: Mapping[str, Any]) -> int:
    raw_schema = metadata.get("schema_version")
    alias_schema = None
    if "version" in metadata:
        alias_schema = _schema_from_version_alias(metadata["version"])

    if raw_schema is None:
        return alias_schema if alias_schema is not None else LEGACY_PROJECT_SCHEMA_VERSION
    if isinstance(raw_schema, bool) or not isinstance(raw_schema, int) or raw_schema < 1:
        raise InvalidProjectSchemaError("Project schema_version must be a positive integer")
    if alias_schema is not None and alias_schema != raw_schema:
        raise InvalidProjectSchemaError(
            f"Project schema_version {raw_schema} conflicts with version {metadata['version']!r}"
        )
    return raw_schema


def _migrate_1_to_2(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize standalone legacy JSON metadata to project schema 2."""
    migrated = deepcopy(metadata)
    migrated.setdefault("current_index", 0)
    migrated.setdefault("selected_indices", [])
    migrated.setdefault("pages", [])
    migrated["schema_version"] = 2
    migrated["version"] = CURRENT_PROJECT_VERSION
    return migrated


Migration = Callable[[dict[str, Any]], dict[str, Any]]
_MIGRATIONS: dict[int, Migration] = {
    LEGACY_PROJECT_SCHEMA_VERSION: _migrate_1_to_2,
}


def _normalize_current_schema(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(metadata)
    normalized.setdefault("current_index", 0)
    if not isinstance(normalized.get("selected_indices"), list):
        normalized["selected_indices"] = []
    normalized.setdefault("pages", [])
    normalized["format"] = PROJECT_FORMAT
    normalized["schema_version"] = CURRENT_PROJECT_SCHEMA_VERSION
    normalized["version"] = CURRENT_PROJECT_VERSION
    normalized.setdefault("app_version", "unknown")
    _normalize_page_ids(normalized)
    return normalized


def _normalize_page_ids(metadata: dict[str, Any]) -> None:
    """Replace unsafe or duplicate persisted IDs before they reach routes/files."""
    pages = metadata.get("pages")
    if not isinstance(pages, list):
        return

    seen: set[str] = set()
    normalized_pages: list[Any] = []
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            normalized_pages.append(raw_page)
            continue

        page = deepcopy(dict(raw_page))
        original_id = page.get("page_id")
        is_safe = (
            isinstance(original_id, str)
            and SAFE_PAGE_ID_PATTERN.fullmatch(original_id) is not None
            and original_id not in seen
        )
        if not is_safe:
            if "page_id" in page:
                page[ORIGINAL_PAGE_ID_EXTENSION] = deepcopy(original_id)
            replacement = uuid.uuid4().hex
            while replacement in seen:
                replacement = uuid.uuid4().hex
            page["page_id"] = replacement

        seen.add(page["page_id"])
        normalized_pages.append(page)

    metadata["pages"] = normalized_pages


def _validate_current_schema(metadata: Mapping[str, Any]) -> None:
    if metadata.get("format") != PROJECT_FORMAT:
        raise InvalidProjectSchemaError(f"Project format must be {PROJECT_FORMAT!r}")
    if metadata.get("schema_version") != CURRENT_PROJECT_SCHEMA_VERSION:
        raise InvalidProjectSchemaError("Project metadata was not migrated to the current schema")
    if not isinstance(metadata.get("app_version"), str):
        raise InvalidProjectSchemaError("Project app_version must be a string")

    pages = metadata.get("pages")
    if not isinstance(pages, list):
        raise InvalidProjectSchemaError("Project field 'pages' must be a list")
    if any(not isinstance(page, Mapping) for page in pages):
        raise InvalidProjectSchemaError("Every project page must be an object")
    page_ids = [page.get("page_id") for page in pages]
    if any(not isinstance(page_id, str) or SAFE_PAGE_ID_PATTERN.fullmatch(page_id) is None for page_id in page_ids):
        raise InvalidProjectSchemaError("Every project page_id must be a safe path identifier")
    if len(page_ids) != len(set(page_ids)):
        raise InvalidProjectSchemaError("Project page_id values must be unique")


def normalize_project_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate decoded project JSON to the current schema without mutating it."""
    if not isinstance(metadata, Mapping):
        raise InvalidProjectSchemaError("Project metadata must be a JSON object")
    if "format" in metadata and metadata["format"] != PROJECT_FORMAT:
        raise InvalidProjectSchemaError(f"Unsupported project format: {metadata['format']!r}")

    normalized = deepcopy(dict(metadata))
    schema_version = _read_schema_version(normalized)
    if schema_version > CURRENT_PROJECT_SCHEMA_VERSION:
        raise UnsupportedProjectVersionError(
            f"Project schema {schema_version} is newer than supported schema "
            f"{CURRENT_PROJECT_SCHEMA_VERSION}. Update VibeCleaner to open this project."
        )

    while schema_version != CURRENT_PROJECT_SCHEMA_VERSION:
        migration = _MIGRATIONS.get(schema_version)
        if migration is None:
            raise UnsupportedProjectVersionError(
                f"Project schema {schema_version} is not supported; supported schema is "
                f"{CURRENT_PROJECT_SCHEMA_VERSION}."
            )
        normalized = migration(normalized)
        next_version = _read_schema_version(normalized)
        if next_version == schema_version:
            raise RuntimeError(f"Project migration for schema {schema_version} did not advance")
        schema_version = next_version

    normalized = _normalize_current_schema(normalized)
    _validate_current_schema(normalized)
    return normalized


def create_project_metadata(
    *,
    pages: list[dict[str, Any]],
    current_index: int,
    selected_indices: list[int],
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build validated metadata for a newly saved project."""
    return normalize_project_metadata(
        {
            **deepcopy(dict(extensions or {})),
            "format": PROJECT_FORMAT,
            "schema_version": CURRENT_PROJECT_SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "version": CURRENT_PROJECT_VERSION,
            "current_index": current_index,
            "selected_indices": selected_indices,
            "pages": pages,
        }
    )
