from __future__ import annotations

from typing import Any, List, Tuple, Optional
import re
import numpy as np
import onnxruntime as ort
import yaml

from ..base import OCREngine
from ...common.textblock import TextBlock
from ...common.textblock import lists_to_blk_list
from ...common.language_utils import is_no_space_lang
from ....infrastructure.runtime.device import get_providers
from ....infrastructure.downloads import ModelDownloader, ModelID
from ....infrastructure.runtime.onnx import make_session
from .preprocessing import apply_adaptive_binarization, crop_text_line, det_preprocess, crop_quad, rec_resize_norm
from .postprocessing import DBPostProcessor, CTCLabelDecoder


def _make_ppocr_session_options(threads: int = 4):
	opts = ort.SessionOptions()
	opts.log_severity_level = 3
	opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
	opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
	opts.intra_op_num_threads = threads
	opts.inter_op_num_threads = 1
	opts.enable_cpu_mem_arena = True
	opts.enable_mem_pattern = True
	return opts


class PPOCRv6Engine(OCREngine):
	"""PP-OCRv6 Medium ONNX detection and recognition pipeline.
	"""

	def __init__(self):
		# Sessions are created lazily in initialize(); keep startup light.
		self.det_sess: Optional[Any] = None
		self.rec_sess: Optional[Any] = None
		self.use_text_lines = True
		self.det_model = 'mobile'
		self.device = 'cpu'
		self.det_post = DBPostProcessor(
			thresh=0.2,
			box_thresh=0.45,
			max_candidates=3000,
			unclip_ratio=1.4,
			use_dilation=False
		)
		self.decoder: Optional[CTCLabelDecoder] = None
		self.rec_img_shape = (3, 48, 320)
		self.rec_batch_size = 8
		self.rec_threads = 4
		self.source_language = 'Chinese'

	def initialize(
		self, 
		lang: str = 'ch', 
		device: str = 'cpu', 
		det_model: str = 'mobile',
		use_text_lines: bool = True
	) -> None:
		self.det_model = det_model
		self.device = device
		self.use_text_lines = use_text_lines
		self.rec_batch_size = 1 if lang == 'latin' else 8
		if lang == 'latin':
			self.rec_threads = 3
		elif lang == 'ko':
			self.rec_threads = 6
		else:
			self.rec_threads = 4
		rec_id = ModelID.PPOCR_V6_REC_MEDIUM
		ModelDownloader.ensure([rec_id])

		rec_paths = ModelDownloader.file_path_map(rec_id)
		rec_model = [p for n, p in rec_paths.items() if n.endswith('.onnx')][0]
		# dict file name can vary per lang
		config_file = [p for n, p in rec_paths.items() if n.endswith('.yml')]
		config_path = config_file[0] if config_file else None

		providers = get_providers(device)
		sess_opt = _make_ppocr_session_options(self.rec_threads)
		self.rec_sess = make_session(rec_model, sess_options=sess_opt, providers=providers)

		# Prepare CTC decoder
		if config_path:
			with open(config_path, 'r', encoding='utf-8') as config_handle:
				model_config = yaml.safe_load(config_handle) or {}
			charset = ((model_config.get('PostProcess') or {}).get('character_dict') or [])
			if charset:
				self.decoder = CTCLabelDecoder(charset=charset)
		else:
			# try pull embedded vocab from model metadata
			meta = self.rec_sess.get_modelmeta().custom_metadata_map
			if 'character' in meta:
				chars = meta['character'].splitlines()
				self.decoder = CTCLabelDecoder(charset=chars)
			else:
				raise RuntimeError('Recognition dictionary not found')

	def _det_infer(self, img: np.ndarray) -> Tuple[np.ndarray, List[float]]:
		self._ensure_det_session()
		assert self.det_sess is not None
		inp = det_preprocess(
			img,
			mean=(0.485, 0.456, 0.406),
			std=(0.229, 0.224, 0.225),
			limit_side_len=960,
			limit_type='min',
		)
		input_name = self.det_sess.get_inputs()[0].name
		output_name = self.det_sess.get_outputs()[0].name
		pred = self.det_sess.run([output_name], {input_name: inp})[0]
		boxes, scores = self.det_post(pred, (img.shape[0], img.shape[1]))
		return boxes, scores

	def _ensure_det_session(self) -> None:
		if self.det_sess is not None:
			return
		det_id = ModelID.PPOCR_V6_DET_MEDIUM
		ModelDownloader.ensure([det_id])
		det_path = ModelDownloader.primary_path(det_id)
		providers = get_providers(self.device)
		sess_opt = ort.SessionOptions()
		sess_opt.log_severity_level = 3
		self.det_sess = make_session(det_path, sess_options=sess_opt, providers=providers)

	def _rec_infer(self, crops: List[np.ndarray]) -> Tuple[List[str], List[float]]:
		assert self.rec_sess is not None and self.decoder is not None
		if not crops:
			return [], []
		# Batch by exact padded recognition width to reduce wasted padding.
		target_widths = [_rec_target_width(crop, self.rec_img_shape) for crop in crops]
		texts = [""] * len(crops)
		confs = [0.0] * len(crops)
		buckets: dict[int, list[int]] = {}
		for crop_index, target_w in enumerate(target_widths):
			buckets.setdefault(target_w, []).append(crop_index)
		inp_name = self.rec_sess.get_inputs()[0].name
		out_name = self.rec_sess.get_outputs()[0].name
		for target_w, idxs in buckets.items():
			max_ratio = target_w / float(self.rec_img_shape[1])
			batch = [
				rec_resize_norm(crops[crop_index], self.rec_img_shape, max_ratio)[None, ...]
				for crop_index in idxs
			]
			x = np.concatenate(batch, axis=0).astype(np.float32)
			logits = self.rec_sess.run([out_name], {inp_name: x})[0]  # (N, T, C) or (N, C, T)
			if logits.ndim == 3 and logits.shape[1] > logits.shape[2]:
				# If output is (N, C, T), transpose to (N, T, C)
				logits = np.transpose(logits, (0, 2, 1))
			# Match PaddleOCR behavior: do not drop characters by per-step prob threshold
			dec_texts, dec_confs = self.decoder(logits, prob_threshold=0.0)
			for oi, t, s in zip(idxs, dec_texts, dec_confs):
				texts[oi] = t
				confs[oi] = float(s)
		return texts, confs

	def process_image(
		self,
		img: np.ndarray,
		blk_list: List[TextBlock],
		padding: int | None = None,
		crop_scale: float | None = None,
		adaptive_binarization: bool | None = None,
		adaptive_binarization_strength: float | None = None,
	) -> List[TextBlock]:
		if self.rec_sess is None or self.decoder is None:
			return blk_list
		if self.use_text_lines and any(getattr(blk, "lines", None) for blk in blk_list):
			for blk in blk_list:
				lines = getattr(blk, "lines", None) or [blk.xyxy]
				raw_crops = [
					_crop_line(
						img,
						line,
						padding=padding,
						crop_scale=crop_scale,
						adaptive_binarization=False,
						adaptive_binarization_strength=adaptive_binarization_strength,
					)
					for line in lines
				]
				raw_results = self._recognize_line_crops(raw_crops)
				results = raw_results

				# Japanese coloured dialogue and highlighted captions are often
				# damaged by thresholding. When the user explicitly enables it,
				# compare both candidates and keep the stronger recognition instead
				# of destructively replacing the colour crop.
				if bool(adaptive_binarization) and _is_japanese_language(self.source_language):
					adaptive_crops = [
						_crop_line(
							img,
							line,
							padding=padding,
							crop_scale=crop_scale,
							adaptive_binarization=True,
							adaptive_binarization_strength=adaptive_binarization_strength,
						)
						for line in lines
					]
					adaptive_results = self._recognize_line_crops(adaptive_crops)
					results = [
						_choose_japanese_candidate(raw, adaptive)
						for raw, adaptive in zip(raw_results, adaptive_results)
					]
				elif bool(adaptive_binarization):
					adaptive_crops = [
						_crop_line(
							img,
							line,
							padding=padding,
							crop_scale=crop_scale,
							adaptive_binarization=True,
							adaptive_binarization_strength=adaptive_binarization_strength,
						)
						for line in lines
					]
					results = self._recognize_line_crops(adaptive_crops)

				texts = [text for text, _ in results]
				confidences = [confidence for _, confidence in results]
				valid_confidences = [
					float(confidence)
					for text, confidence in zip(texts, confidences)
					if text and text.strip()
				]
				texts = [text.strip() for text in texts if text and text.strip()]
				blk.texts = texts
				blk.text = (
					"".join(texts)
					if is_no_space_lang(getattr(blk, "source_lang", ""))
					else " ".join(texts)
				)
				blk.ocr_confidence = (
					sum(valid_confidences) / len(valid_confidences)
					if valid_confidences
					else None
				)
			return blk_list

		boxes, _ = self._det_infer(img)
		if boxes is None or len(boxes) == 0:
			return blk_list

		adaptive_bin = True if adaptive_binarization is None else bool(adaptive_binarization)
		strength = 2.0 if adaptive_binarization_strength is None else float(adaptive_binarization_strength)
		crops = []
		for quad in boxes:
			crop = crop_quad(img, quad.astype(np.float32))
			if crop is not None and adaptive_bin:
				crop = apply_adaptive_binarization(crop, strength=strength)
			crops.append(crop)

		texts, confidences = self._rec_infer(crops)
		# map quads -> axis-aligned boxes
		bboxes = []
		for quad in boxes:
			xs = quad[:, 0]
			ys = quad[:, 1]
			x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
			bboxes.append((x1, y1, x2, y2))
		result = lists_to_blk_list(blk_list, bboxes, texts)
		average_confidence = (
			sum(float(value) for value in confidences) / len(confidences)
			if confidences
			else None
		)
		for block in result:
			block.ocr_confidence = average_confidence
		return result

	def _recognize_line_crops(self, crops: List[np.ndarray | None]) -> List[Tuple[str, float]]:
		results: List[Tuple[str, float]] = [("", 0.0) for _ in crops]
		valid_indices = [
			index for index, crop in enumerate(crops)
			if crop is not None and crop.size > 0
		]
		texts, confidences = self._rec_infer([crops[index] for index in valid_indices])
		for index, text, confidence in zip(valid_indices, texts, confidences):
			results[index] = (str(text or "").strip(), float(confidence))
		return results


def _is_japanese_language(language: str | None) -> bool:
	return str(language or "").strip().lower() in {"japanese", "日本語", "ja"}


def _japanese_candidate_score(candidate: Tuple[str, float]) -> float:
	text, confidence = candidate
	if not text:
		return -1.0
	meaningful = [char for char in text if not char.isspace() and not re.match(r"[\W_]", char)]
	if not meaningful:
		return float(confidence) - 0.5
	jp_count = sum(
		"\u3040" <= char <= "\u30ff" or "\u3400" <= char <= "\u9fff"
		for char in meaningful
	)
	latin_or_digit = sum(char.isascii() and char.isalnum() for char in meaningful)
	ratio = jp_count / len(meaningful)
	foreign_ratio = latin_or_digit / len(meaningful)
	repeated_penalty = 0.25 if re.search(r"(.)\1{5,}", text) else 0.0
	return float(confidence) + 0.18 * ratio - 0.22 * foreign_ratio - repeated_penalty


def _choose_japanese_candidate(
	raw: Tuple[str, float],
	adaptive: Tuple[str, float],
) -> Tuple[str, float]:
	# Keep the colour crop on near-ties; thresholding must provide a meaningful
	# improvement to replace it.
	return adaptive if _japanese_candidate_score(adaptive) > _japanese_candidate_score(raw) + 0.04 else raw


def _crop_line(
	img: np.ndarray,
	line,
	padding: int | None = None,
	crop_scale: float | None = None,
	adaptive_binarization: bool | None = None,
	adaptive_binarization_strength: float | None = None,
) -> np.ndarray | None:
	return crop_text_line(
		img,
		line,
		padding=padding,
		crop_scale=crop_scale,
		adaptive_binarization=adaptive_binarization,
		adaptive_binarization_strength=adaptive_binarization_strength,
	)


def _rec_target_width(img: np.ndarray, img_shape=(3, 48, 320)) -> int:
	_, H, W = img_shape
	h, w = img.shape[:2]
	ratio = w / float(max(1, h))
	return max(W, int(np.ceil(H * ratio)))
