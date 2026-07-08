# download_models.py
import os
import sys
import logging
import argparse

# Ensure current directory and backend directory are in search path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "backend"))

from infrastructure.logging import configure_logging
from modules.utils.download import ModelDownloader, ModelID
from modules.config import AppConfig
from services.model_requirements import get_required_model_ids
from app.version import APP_NAME

configure_logging()
logger = logging.getLogger(__name__)

MINIMAL_MODEL_IDS = [
    ModelID.RTDETR_INT8_ONNX,
    ModelID.MANGA_OCR_MOBILE_ONNX,
]

ALL_CORE_MODEL_IDS = [
    ModelID.RTDETR_V2_ONNX,
    ModelID.RTDETR_INT8_ONNX,
    ModelID.MANGA_OCR_MOBILE_ONNX,
    ModelID.PPOCR_V5_DET_MOBILE,
    ModelID.PPOCR_V5_REC_MOBILE,
    ModelID.PPOCR_V5_REC_EN_MOBILE,
    ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
    ModelID.PPOCR_V4_CLS,
    ModelID.LAMA_ONNX,
]


def _load_current_settings() -> AppConfig:
    settings = AppConfig()
    settings.load()
    return settings


def get_model_ids(profile: str = "current", settings: AppConfig | None = None) -> list[ModelID]:
    if profile == "minimal":
        return MINIMAL_MODEL_IDS
    if profile == "all":
        return ALL_CORE_MODEL_IDS
    return get_required_model_ids(settings or _load_current_settings())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Download {APP_NAME} AI model files.")
    parser.add_argument(
        "--profile",
        choices=["current", "minimal", "all"],
        default="current",
        help="Model set to download. current uses the saved app settings.",
    )
    parser.add_argument("--minimal", action="store_true", help="Legacy alias for --profile minimal.")
    parser.add_argument("--all", action="store_true", help="Legacy alias for --profile all.")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    profile = "minimal" if args.minimal else "all" if args.all else args.profile

    print("==================================================")
    print(f" {APP_NAME} AI Models Downloader")
    print("==================================================")
    print(f"Profile: {profile}")
    print("==================================================")

    core_models = get_model_ids(profile)
    print("Required models to download:")
    for idx, model_id in enumerate(core_models, start=1):
        print(f" {idx}. {model_id.value}")
    print("==================================================")

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
