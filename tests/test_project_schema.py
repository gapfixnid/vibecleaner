import json
from pathlib import Path

import pytest

from backend.infrastructure.storage.project_schema import (
    CURRENT_PROJECT_SCHEMA_VERSION,
    CURRENT_PROJECT_VERSION,
    PROJECT_FORMAT,
    InvalidProjectSchemaError,
    UnsupportedProjectVersionError,
    create_project_metadata,
    normalize_project_metadata,
)


FIXTURES = Path(__file__).parent / "fixtures" / "projects"


def test_existing_v2_project_metadata_gets_an_additive_envelope():
    metadata = json.loads((FIXTURES / "project_v2_metadata.json").read_text(encoding="utf-8"))

    normalized = normalize_project_metadata(metadata)

    assert normalized["format"] == PROJECT_FORMAT
    assert normalized["schema_version"] == CURRENT_PROJECT_SCHEMA_VERSION
    assert normalized["app_version"] == "unknown"
    assert normalized["version"] == metadata["version"]
    assert normalized["pages"] == metadata["pages"]
    assert normalized is not metadata
    assert "schema_version" not in metadata


def test_versionless_legacy_json_uses_explicit_migration_path():
    legacy = {
        "current_index": 1,
        "pages": [{"file_path": "page-001.png"}, {"file_path": "page-002.png"}],
    }

    normalized = normalize_project_metadata(legacy)

    assert normalized["version"] == CURRENT_PROJECT_VERSION
    assert normalized["schema_version"] == CURRENT_PROJECT_SCHEMA_VERSION
    assert normalized["current_index"] == 1
    assert normalized["selected_indices"] == []
    assert normalized["pages"] == legacy["pages"]
    assert "version" not in legacy


def test_future_project_version_fails_with_upgrade_guidance():
    with pytest.raises(UnsupportedProjectVersionError, match=r"newer.*Update VibeCleaner"):
        normalize_project_metadata({"schema_version": 3, "pages": []})


def test_unknown_old_project_version_is_not_silently_interpreted():
    with pytest.raises(InvalidProjectSchemaError, match=r"positive integer"):
        normalize_project_metadata({"schema_version": 0, "pages": []})


def test_invalid_pages_shape_fails_clearly():
    with pytest.raises(InvalidProjectSchemaError, match="'pages' must be a list"):
        normalize_project_metadata({"version": "2.0", "pages": {}})


def test_new_project_metadata_always_uses_current_version():
    metadata = create_project_metadata(pages=[], current_index=0, selected_indices=[])

    assert metadata == {
        "format": PROJECT_FORMAT,
        "schema_version": CURRENT_PROJECT_SCHEMA_VERSION,
        "app_version": "0.1.0",
        "version": CURRENT_PROJECT_VERSION,
        "current_index": 0,
        "selected_indices": [],
        "pages": [],
    }


def test_current_schema_normalization_is_idempotent():
    metadata = create_project_metadata(pages=[], current_index=0, selected_indices=[])

    assert normalize_project_metadata(metadata) == metadata


def test_conflicting_schema_aliases_fail_clearly():
    with pytest.raises(InvalidProjectSchemaError, match="conflicts"):
        normalize_project_metadata({"schema_version": 2, "version": "1.0", "pages": []})


def test_unknown_project_format_fails_clearly():
    with pytest.raises(InvalidProjectSchemaError, match="Unsupported project format"):
        normalize_project_metadata({"format": "other-app", "schema_version": 2, "pages": []})


def test_unknown_minor_legacy_version_is_not_treated_as_schema_two():
    with pytest.raises(UnsupportedProjectVersionError, match="2.1.*not supported"):
        normalize_project_metadata({"version": "2.1", "pages": []})
