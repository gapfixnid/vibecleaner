# modules/ocr_wrapper.py
import numpy as np
import threading
from modules.utils.textblock import TextBlock
from modules.ocr.manga_ocr.mobile.onnx_engine import MangaOCRMobileONNXEngine
from modules.ocr.ppocr.engine import PPOCRv5Engine

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
        self._lock = threading.Lock()
        
    def recognize_text(self, image: np.ndarray, text_blocks: list[TextBlock]) -> list[TextBlock]:
        """
        Runs the real OCR engine on a list of TextBlock objects.
        """
        if not text_blocks:
            return text_blocks
            
        if self.lang in ["Japanese", "日本語", "ja"]:
            if self.japanese_engine is None:
                with self._lock:
                    if self.japanese_engine is None:
                        engine = MangaOCRMobileONNXEngine()
                        engine.initialize()
                        self.japanese_engine = engine
            return self.japanese_engine.process_image(image, text_blocks)
        else:
            if self.korean_engine is None:
                with self._lock:
                    if self.korean_engine is None:
                        engine = PPOCRv5Engine()
                        lang_code = 'ko'
                        if self.lang in ["English", "en"]:
                            lang_code = 'en'
                        elif self.lang in ["Chinese", "zh"]:
                            lang_code = 'ch'
                        engine.initialize(lang=lang_code)
                        self.korean_engine = engine
            return self.korean_engine.process_image(image, text_blocks)
