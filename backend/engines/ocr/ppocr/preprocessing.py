from __future__ import annotations

import logging

import cv2
import numpy as np
from ....infrastructure import image as imk

logger = logging.getLogger(__name__)


def apply_adaptive_binarization(crop: np.ndarray, strength: float = 2.0) -> np.ndarray:
	"""Apply CLAHE and adaptive thresholding to an OCR crop."""
	if crop is None or crop.size == 0:
		return crop
	try:
		if len(crop.shape) == 3:
			if crop.shape[2] == 3:
				gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
			elif crop.shape[2] == 4:
				gray = cv2.cvtColor(crop, cv2.COLOR_RGBA2GRAY)
			else:
				gray = crop
		else:
			gray = crop

		clip_limit = max(0.5, min(5.0, float(strength)))
		clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
		enhanced = clahe.apply(gray)
		thresh = cv2.adaptiveThreshold(
			enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
		)
		return cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
	except Exception:
		logger.exception("Adaptive binarization failed")
		return crop


def resize_keep_stride(img: np.ndarray, limit_side_len: int = 960, limit_type: str = "min") -> np.ndarray:
	"""Resize image so that min or max side meets threshold, snapping to multiple of 32.

	This matches the common PP-OCR DB-det precondition: H,W % 32 == 0.
	"""
	h, w = img.shape[:2]
	if limit_type == "max":
		if max(h, w) > limit_side_len:
			ratio = float(limit_side_len) / (h if h > w else w)
		else:
			ratio = 1.0
	else:
		if min(h, w) < limit_side_len:
			ratio = float(limit_side_len) / (h if h < w else w)
		else:
			ratio = 1.0

	nh = int(round((h * ratio) / 32) * 32)
	nw = int(round((w * ratio) / 32) * 32)
	nh = max(nh, 32)
	nw = max(nw, 32)
	if nh == h and nw == w:
		return img
	# imk.resize expects (w, h)
	return imk.resize(img, (nw, nh))


def det_preprocess(img: np.ndarray, mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5),
				   limit_side_len: int = 960, limit_type: str = "min") -> np.ndarray:
	"""Preprocess for DB detector: resize, normalize, CHW, NCHW float32."""
	resized = resize_keep_stride(img, limit_side_len, limit_type)
	x = resized.astype(np.float32) / 255.0
	x = (x - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
	x = x.transpose(2, 0, 1)
	x = np.expand_dims(x, 0).astype(np.float32)
	return x


def rec_resize_norm(img: np.ndarray, img_shape=(3, 48, 320), max_wh_ratio: float | None = None) -> np.ndarray:
	"""Resize and normalize for PP-OCR recognition (CTC):
	- target H=img_shape[1], W computed from ratio, padded to target width.
	- normalize to [-1,1].
	Returns CHW float32 padded array.
	"""
	c, H, W = img_shape
	assert img.shape[2] == c, "Expect BGR with 3 channels"

	if max_wh_ratio is None:
		max_wh_ratio = W / float(H)

	h, w = img.shape[:2]
	ratio = w / float(h)
	target_w = int(H * max_wh_ratio)
	resized_w = min(target_w, int(np.ceil(H * ratio)))

	resized = imk.resize(img, (resized_w, H))
	x = resized.astype(np.float32) / 255.0
	x = x.transpose(2, 0, 1)
	x = (x - 0.5) / 0.5

	out = np.zeros((c, H, target_w), dtype=np.float32)
	out[:, :, :resized_w] = x
	return out


def crop_quad(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
	"""Perspective-crop a quadrilateral region. Auto-rotate tall crops."""
	pts = quad.astype(np.float32)
	w = int(max(np.linalg.norm(pts[0]-pts[1]), np.linalg.norm(pts[2]-pts[3])))
	h = int(max(np.linalg.norm(pts[0]-pts[3]), np.linalg.norm(pts[1]-pts[2])))
	dst = np.array([[0,0],[w,0],[w,h],[0,h]], dtype=np.float32)
	# the image toolkit expects 4x2 arrays (x,y)
	M = imk.get_perspective_transform(pts, dst)
	crop = imk.warp_perspective(img, M, (w, h))
	if h > 0 and w > 0 and (h / float(w)) >= 1.5:
		crop = np.rot90(crop)
	return crop


def crop_text_line(
	img: np.ndarray,
	line,
	padding: int | None = None,
	crop_scale: float | None = None,
	adaptive_binarization: bool | None = None,
	adaptive_binarization_strength: float | None = None,
) -> np.ndarray | None:
	"""Crop an OCR line, preserving rotation when a quadrilateral is available."""
	base_padding = 8 if padding is None else int(padding)
	scale = 1.5 if crop_scale is None else float(crop_scale or 1.5)
	scale = max(0.5, min(3.0, scale))
	adaptive_bin = True if adaptive_binarization is None else bool(adaptive_binarization)
	strength = 2.0 if adaptive_binarization_strength is None else float(adaptive_binarization_strength)

	arr = np.asarray(line)
	if arr.ndim == 2 and arr.shape[0] >= 4 and arr.shape[1] == 2:
		crop = crop_quad(img, arr[:4].astype(np.float32))
		if crop is None or crop.size == 0:
			return None
		pad = _dynamic_crop_padding(crop.shape[0], base_padding, scale)
		if pad > 0:
			pad_width = ((pad, pad), (pad, pad))
			if crop.ndim == 3:
				pad_width += ((0, 0),)
			crop = np.pad(crop, pad_width, mode="constant", constant_values=255)
		if adaptive_bin:
			crop = apply_adaptive_binarization(crop, strength=strength)
		return crop

	if arr.size != 4:
		return None
	x1, y1, x2, y2 = [int(round(float(value))) for value in arr.reshape(-1)[:4]]
	pad = _dynamic_crop_padding(max(1, y2 - y1), base_padding, scale)
	x1 = max(0, x1 - pad)
	y1 = max(0, y1 - pad)
	x2 = min(img.shape[1], x2 + pad)
	y2 = min(img.shape[0], y2 + pad)
	if x2 <= x1 or y2 <= y1:
		return None

	crop = img[y1:y2, x1:x2]
	if adaptive_bin:
		crop = apply_adaptive_binarization(crop, strength=strength)
	h, w = crop.shape[:2]
	if h > 0 and w > 0 and h / float(w) >= 1.5:
		crop = np.rot90(crop)
	return crop


def _dynamic_crop_padding(region_height: int, base_padding: int, scale: float) -> int:
	if region_height < 20:
		value = base_padding + 8
	elif region_height < 40:
		value = base_padding + 4
	else:
		value = base_padding
	return max(0, int(round(value * scale)))
