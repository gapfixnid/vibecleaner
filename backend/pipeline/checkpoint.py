from __future__ import annotations

import json
import os
import tempfile
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _checkpoint_encode(value: Any) -> Any:
    """Convert runtime-only proxy wrappers to pickle-safe values."""
    from .context import StageOutput
    if isinstance(value, StageOutput):
        return {
            "__checkpoint_type__": "StageOutput",
            "stage": value.stage,
            "values": _checkpoint_encode(dict(value.values)),
        }
    if isinstance(value, dict):
        return {key: _checkpoint_encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_checkpoint_encode(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_checkpoint_encode(item) for item in value)
    return value


def _checkpoint_decode(value: Any) -> Any:
    from .context import StageOutput
    if isinstance(value, dict) and value.get("__checkpoint_type__") == "StageOutput":
        return StageOutput(
            stage=str(value["stage"]),
            values=_checkpoint_decode(value.get("values", {})),
        )
    if isinstance(value, dict):
        return {key: _checkpoint_decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_checkpoint_decode(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_checkpoint_decode(item) for item in value)
    return value


@dataclass
class CheckpointManifest:
    run_id: str
    page_id: str
    completed_stages: list[str] = field(default_factory=list)
    artifact_keys: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def contract_version(self) -> str:
        return str(self.metadata.get("pipeline_contract_version", "unknown"))


class JsonCheckpointStore:
    """Atomic JSON manifest store; artifact payloads remain stage-owned."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)

    def path_for(self, run_id: str) -> Path:
        return self.root / f"{run_id}.json"

    def payload_path_for(self, run_id: str) -> Path:
        return self.root / f"{run_id}.payload"

    def save(self, manifest: CheckpointManifest) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.path_for(manifest.run_id)
        fd, temporary = tempfile.mkstemp(prefix=f".{manifest.run_id}.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(manifest), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load(self, run_id: str) -> CheckpointManifest | None:
        target = self.path_for(run_id)
        if not target.exists():
            return None
        with target.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return CheckpointManifest(**data)

    def save_artifacts(self, run_id: str, artifacts: dict[str, Any]) -> None:
        """Persist stage-owned page artifacts beside the JSON manifest."""
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.payload_path_for(run_id)
        fd, temporary = tempfile.mkstemp(prefix=f".{run_id}.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as handle:
                pickle.dump(_checkpoint_encode(artifacts), handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load_artifacts(self, run_id: str) -> dict[str, Any]:
        target = self.payload_path_for(run_id)
        if not target.exists():
            return {}
        with target.open("rb") as handle:
            payload = pickle.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid checkpoint artifact payload for run {run_id}")
        return _checkpoint_decode(payload)

    def delete(self, run_id: str) -> None:
        self.path_for(run_id).unlink(missing_ok=True)
        self.payload_path_for(run_id).unlink(missing_ok=True)
