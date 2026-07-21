# engines/ocr/local.py
import numpy as np
import threading
from ..common.textblock import TextBlock
from .ppocr.engine import PPOCRv6Engine
from .preprocessing_profile import resolve_ocr_preprocessing_profile

class DummySettings:
    def is_gpu_enabled(self):
        import onnxruntime as ort
        try:
            providers = ort.get_available_providers()
            return "CUDAExecutionProvider" in providers
        except Exception:
            return False
        
    def get_credentials(self, key):
        return {}

class LocalOCR:
    def __init__(self, lang: str = "Japanese"):
        self.lang = lang
        self.settings = DummySettings()
        self.korean_engine = None
        self.ppocr_engines = {}
        self._lock = threading.Lock()

    def _resolve_engine_name(self, engine: str | None = None) -> str:
        # PP-OCR is the sole local OCR runtime. Legacy values are accepted so
        # old projects and settings migrate without attempting a removed model.
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
        profile = resolve_ocr_preprocessing_profile(
            self.lang,
            engine_name,
            padding=padding,
            crop_scale=crop_scale,
            adaptive_binarization=adaptive_binarization,
            adaptive_binarization_strength=adaptive_binarization_strength,
        )
        lang_code = self._ppocr_lang_code()
        if lang_code not in self.ppocr_engines:
            with self._lock:
                if lang_code not in self.ppocr_engines:
                    ppocr_engine = PPOCRv6Engine()
                    device = "cuda" if self.settings.is_gpu_enabled() else "cpu"
                    ppocr_engine.initialize(lang=lang_code, device=device)
                    ppocr_engine.source_language = self.lang
                    self.ppocr_engines[lang_code] = ppocr_engine
                    if lang_code == "ko":
                        self.korean_engine = ppocr_engine
        return self.ppocr_engines[lang_code].process_image(
            image,
            text_blocks,
            padding=profile.padding,
            crop_scale=profile.crop_scale,
            adaptive_binarization=profile.adaptive_binarization,
            adaptive_binarization_strength=profile.adaptive_binarization_strength,
        )
