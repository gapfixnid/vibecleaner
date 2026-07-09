# engines/ocr/local.py
import numpy as np
import threading
from ..common.textblock import TextBlock
from .manga_ocr.mobile.onnx_engine import MangaOCRMobileONNXEngine
from .ppocr.engine import PPOCRv5Engine

class DummySettings:
    def is_gpu_enabled(self):
        import onnxruntime as ort
        try:
            providers = ort.get_available_providers()
            return "CUDAExecutionProvider" in providers or "ROCMExecutionProvider" in providers
        except Exception:
            return False
        
    def get_credentials(self, key):
        return {}

class LocalOCR:
    def __init__(self, lang: str = "Japanese"):
        self.lang = lang
        self.settings = DummySettings()
        self.japanese_engine = None
        self.korean_engine = None
        self.ppocr_engines = {}
        self._lock = threading.Lock()

    def _resolve_engine_name(self, engine: str | None = None) -> str:
        requested = str(engine or "auto").strip().lower()
        if requested in {"manga_ocr", "manga-ocr", "manga", "manga_ocr_mobile"}:
            return "manga_ocr"
        if requested in {"ppocr", "paddleocr", "paddle_ocr", "fast", "speed"}:
            return "ppocr"
        if requested in {"balanced", "standard", "auto"}:
            if self.lang in ["Japanese", "日本語", "ja"]:
                return "manga_ocr"
            return "ppocr"
        if self.lang in ["Japanese", "日本語", "ja"]:
            return "manga_ocr"
        return "ppocr"

    def _ppocr_lang_code(self) -> str:
        if self.lang in ["English", "en"]:
            return "en"
        if self.lang in ["Chinese", "zh", "Japanese", "日本語", "ja"]:
            return "ch"
        return "ko"
        
    def recognize_text(
        self,
        image: np.ndarray,
        text_blocks: list[TextBlock],
        *,
        engine: str | None = None,
        padding: int | None = None,
        crop_scale: float | None = None,
        adaptive_binarization: bool | None = None,
        adaptive_binarization_strength: float | None = None,
    ) -> list[TextBlock]:
        """
        Runs the real OCR engine on a list of TextBlock objects.
        """
        if not text_blocks:
            return text_blocks
            
        engine_name = self._resolve_engine_name(engine)
        if engine_name == "manga_ocr":
            if self.japanese_engine is None:
                with self._lock:
                    if self.japanese_engine is None:
                        engine = MangaOCRMobileONNXEngine()
                        engine.initialize()
                        self.japanese_engine = engine
            return self.japanese_engine.process_image(
                image,
                text_blocks,
                padding=padding,
                crop_scale=crop_scale,
                adaptive_binarization=adaptive_binarization,
                adaptive_binarization_strength=adaptive_binarization_strength,
            )
        else:
            lang_code = self._ppocr_lang_code()
            if lang_code not in self.ppocr_engines:
                with self._lock:
                    if lang_code not in self.ppocr_engines:
                        engine = PPOCRv5Engine()
                        engine.initialize(lang=lang_code)
                        self.ppocr_engines[lang_code] = engine
                        if lang_code == "ko":
                            self.korean_engine = engine
            return self.ppocr_engines[lang_code].process_image(
                image,
                text_blocks,
                padding=padding,
                crop_scale=crop_scale,
                adaptive_binarization=adaptive_binarization,
                adaptive_binarization_strength=adaptive_binarization_strength,
            )