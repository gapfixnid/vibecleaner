import cv2
import numpy as np


THUMBNAIL_WIDTH = 150
PREVIEW_MAX_DIMENSION = 1600
JPEG_QUALITY = 90


def encode_png_bytes(image: np.ndarray) -> bytes:
    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Failed to encode image")
    return buffer.tobytes()


def encode_jpeg_bytes(image: np.ndarray, quality: int = JPEG_QUALITY) -> bytes:
    success, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        raise ValueError("Failed to encode image")
    return buffer.tobytes()


def encode_resized_png_bytes(image: np.ndarray, max_dimension: int) -> bytes:
    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")

    scale = min(max_dimension / max(width, height), 1.0)
    if scale < 1.0:
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return encode_png_bytes(image)


def encode_resized_jpeg_bytes(image: np.ndarray, max_dimension: int, quality: int = JPEG_QUALITY) -> bytes:
    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")

    scale = min(max_dimension / max(width, height), 1.0)
    if scale < 1.0:
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return encode_jpeg_bytes(image, quality=quality)


def encode_thumbnail_bytes(image: np.ndarray) -> bytes:
    return encode_resized_png_bytes(image, THUMBNAIL_WIDTH)


def encode_preview_bytes(image: np.ndarray) -> bytes:
    return encode_resized_png_bytes(image, PREVIEW_MAX_DIMENSION)


def encode_preview_jpeg_bytes(image: np.ndarray) -> bytes:
    return encode_resized_jpeg_bytes(image, PREVIEW_MAX_DIMENSION)
