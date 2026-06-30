# download_models.py
import os
import sys
import logging

# Ensure current directory and backend directory are in search path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "backend"))

from modules.logging_config import configure_logging
from modules.utils.download import ModelDownloader, ModelID
from app.version import APP_NAME

configure_logging()
logger = logging.getLogger(__name__)

MINIMAL_MODEL_IDS = [
    ModelID.RTDETR_INT8_ONNX,
    ModelID.MANGA_OCR_MOBILE_ONNX,
]

ALL_CORE_MODEL_IDS = [
    ModelID.RTDETR_INT8_ONNX,
    ModelID.MANGA_OCR_MOBILE_ONNX,
    ModelID.PPOCR_V5_DET_MOBILE,
    ModelID.PPOCR_V5_REC_MOBILE,
    ModelID.PPOCR_V5_REC_EN_MOBILE,
    ModelID.PPOCR_V4_CLS,
]


def get_model_ids(profile: str = "all") -> list[ModelID]:
    return MINIMAL_MODEL_IDS if profile == "minimal" else ALL_CORE_MODEL_IDS


def main():
    print("==================================================")
    print(f" {APP_NAME} AI Models Downloader")
    print("==================================================")
    print("Required models to download:")
    print(" 1. RT-DETR-v2 Text & Bubble Detector (INT8 ONNX)")
    print(" 2. Manga OCR Mobile Japanese Recognition (ONNX)")
    print(" 3. PaddleOCR v5 Multilingual Detector (ONNX)")
    print(" 4. PaddleOCR v5 Chinese/Korean/English Recognition (ONNX)")
    print("==================================================")

    # Core models needed for standard operations
    core_models = get_model_ids("minimal" if "--minimal" in sys.argv else "all")

    failed_models = []
    success_count = 0
    already_count = 0

    for model_id in core_models:
        spec = ModelDownloader.registry.get(model_id)
        if not spec:
            print(f"[-] Unknown model ID: {model_id}")
            continue

        print(f"\n[*] Checking: {model_id.value}...")
        if ModelDownloader.is_downloaded(model_id):
            print(f"[+] Already downloaded: {model_id.value}")
            already_count += 1
            continue

        # Retry logic (up to 3 times) for network robustness
        max_retries = 3
        download_success = False
        for attempt in range(max_retries):
            try:
                print(f"[*] Downloading {model_id.value} (Attempt {attempt + 1}/{max_retries})...")
                print(f"[*] Target location: {spec.save_dir}")
                ModelDownloader.get(model_id)
                print(f"[+] Download complete: {model_id.value}")
                download_success = True
                success_count += 1
                break
            except Exception as e:
                logger.exception(
                    "Model download attempt failed. model_id=%s attempt=%s/%s target=%s",
                    model_id.value,
                    attempt + 1,
                    max_retries,
                    spec.save_dir,
                )
                print(f"[!] Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    import time  # Delayed import: only needed when retrying failed downloads.

                    time.sleep(2.0)

        if not download_success:
            logger.error("Failed to download model after retries. model_id=%s", model_id.value)
            print(f"[ERROR] Failed to download {model_id.value} after {max_retries} attempts.")
            failed_models.append(model_id.value)

    print("\n==================================================")
    print(f" {APP_NAME} Model Downloader Summary")
    print("==================================================")
    print(f" - Already Present: {already_count}")
    print(f" - Newly Downloaded: {success_count}")

    if failed_models:
        print(f" - Failed to Download ({len(failed_models)}):")
        for f_model in failed_models:
            print(f"   * {f_model}")
        print("==================================================")
        print("\n[!] Warning: Some core AI models failed to download.")
        print("If automatic download fails, please download the models manually")
        print("from their respective Hugging Face repositories:")
        print(" - RT-DETR: https://huggingface.co/ogkalu/comic-text-and-bubble-detector")
        print(" - Manga OCR: https://huggingface.co/ogkalu/manga-ocr-mobile")
        print(" - PaddleOCR v5: https://huggingface.co/ogkalu/ppocr-v5-onnx")
        sys.exit(1)
    else:
        print(" - All core AI models are ready!")
        print("==================================================")


if __name__ == "__main__":
    main()
