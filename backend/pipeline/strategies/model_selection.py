from __future__ import annotations

from ...core.config import AppConfigSnapshot


class ModelSelectionStrategy:
    def detection_model_id(self, settings: AppConfigSnapshot) -> str:
        if settings.detect_model in {"Small (INT8)", "Small (INT8) [기본값]"}:
            return "rtdetr-int8-onnx"
        return "rtdetr-v2-onnx"