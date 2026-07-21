DEFAULT_DETECTION_BACKEND = "onnx"


def resolve_detection_backend(backend: str | None = None) -> str:
    return DEFAULT_DETECTION_BACKEND
