import os
import sys
import glob
import cv2
import argparse
from concurrent.futures import ThreadPoolExecutor

# Make sure backend is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Qt offscreen for font metrics
from PySide6.QtWidgets import QApplication
qt_app = QApplication.instance() or QApplication(["-platform", "offscreen"])

# Initialize config BEFORE importing services
from modules.config import config


# Import services
from services.translation_service import TranslationService
from services.detection_service import DetectionService
from services.inpainting_service import InpaintingService
from services.render_service import RenderService
from services.export_service import ExportService
from services.page_analysis_service import PageAnalysisService
from services.bubble_analysis_service import BubbleAnalysisService
from services.layout_planner_service import LayoutPlannerService
from services.font_resolver_service import resolver as font_resolver
from app.models import MangaPage
from services.pipeline_utils import _bubbles_from_analysis, _merge_overlapping_bubbles, _inpaint_boxes, _bubble_clip_boxes

def process_directory(target_dir: str, model_name: str, workers: int = 4):


    # Initialize services
    detection_service = DetectionService()
    page_analysis = PageAnalysisService()
    bubble_analysis = BubbleAnalysisService()
    layout_planner = LayoutPlannerService()
    inpainting_service = InpaintingService()
    translation_service = TranslationService()
    render_service = RenderService()
    export_service = ExportService(render_service)

    # Check connection
    if not translation_service.check_connection():
        print("Ollama 서버 로딩 안됨. 프로그램을 종료합니다.")
        sys.exit(1)

    models = translation_service.installed_models
    if not models:
        print("Ollama 서버에 설치된 모델이 없습니다. 프로그램을 종료합니다.")
        sys.exit(1)
        
    print(f"Ollama 서버에 로딩된 실제 서버 모델: {', '.join(models)}")
    
    if not model_name:
        model_name = models[0]
    elif model_name not in models:
        print(f"경고: 요청한 모델 '{model_name}'이(가) 없습니다. '{models[0]}' 모델을 대신 사용합니다.")
        model_name = models[0]

    config.translation_model = model_name
    print(f"Ollama 서버 번역 모델로 '{model_name}'을(를) 사용합니다.")

    out_dir = os.path.join(target_dir, "translated_output")
    os.makedirs(out_dir, exist_ok=True)

    image_exts = ('*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp')
    images = []
    for ext in image_exts:
        images.extend(glob.glob(os.path.join(target_dir, ext)))

    print(f"총 {len(images)}개의 이미지를 찾았습니다. 번역을 시작합니다...")

    def process_single_image(img_path: str):
        filename = os.path.basename(img_path)
        print(f"\n[{filename}] 처리 시작...")
        
        try:
            import numpy as np
            stream = open(img_path, "rb")
            bytes_array = bytearray(stream.read())
            numpy_array = np.asarray(bytes_array, dtype=np.uint8)
            cv_image = cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)
            stream.close()
        except Exception as e:
            cv_image = None

        if cv_image is None:
            print(f"[{filename}] 이미지를 읽을 수 없습니다. 건너뜁니다.")
            return

        print(f"[{filename}] 텍스트 영역 감지 중...")
        blocks = detection_service.detect_and_ocr(cv_image, lang=config.source_language)
        
        print(f"[{filename}] 레이아웃 및 말풍선 분석 중...")
        bubbles = _bubbles_from_analysis(
            cv_image, blocks, config.source_language, config.target_language,
            page_analysis, bubble_analysis, layout_planner
        )
        bubbles = _merge_overlapping_bubbles(bubbles)
        for idx, b in enumerate(bubbles, 1):
            b.id = idx

        inpainted_image = None

        def task_inpaint():
            nonlocal inpainted_image
            boxes = _inpaint_boxes(bubbles)
            bubble_boxes = _bubble_clip_boxes(bubbles)
            inpainted_image = inpainting_service.clean_background(cv_image, boxes, bubble_boxes, protect_edges=True)

        def task_translate():
            from modules.utils.textblock import TextBlock
            import numpy as np
            temp_blocks = [
                TextBlock(text_bbox=np.array(b.source_xyxy()).astype(np.int32), text=b.text)
                for b in bubbles
            ]
            translation_service.translate_blocks(temp_blocks, config.source_language, config.target_language, cv_image)
            for bubble, text_block in zip(bubbles, temp_blocks):
                bubble.translated = text_block.translation

        print(f"[{filename}] 번역 및 인페인팅 진행 중...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            f1, f2 = executor.submit(task_inpaint), executor.submit(task_translate)
            f1.result()
            f2.result()

        page = MangaPage(
            file_path=img_path, 
            cv_image=cv_image, 
            inpainted_image=inpainted_image, 
            bubbles=bubbles, 
            bubble_counter=len(bubbles)
        )

        print(f"[{filename}] 최종 렌더링 및 저장 중...")
        def custom_font_resolver(family: str):
            res, _ = font_resolver.resolve(text="", requested_family=family, target_lang="Korean")
            return res.path
            
        resolved, _ = font_resolver.resolve(text="", requested_family="Pretendard Variable", target_lang="Korean")
        pil_image = export_service.render_page(page, font_path=resolved.path, font_family="Pretendard Variable", font_resolver=custom_font_resolver)
        
        save_path = os.path.join(out_dir, filename)
        pil_image.save(save_path)
        print(f"[{filename}] 완료 -> {save_path}")

    # Process all images in parallel
    print(f"작업 스레드 {workers}개로 병렬 처리를 시작합니다...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_single_image, path) for path in images]
        for future in futures:
            future.result()  # Re-raise any exceptions

    print("\n모든 작업이 완료되었습니다!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vibecleaner CLI 일괄 번역기 (Ollama 지원)")
    parser.add_argument(
        "--dir", 
        type=str, 
        default=".", 
        help="번역할 이미지가 있는 디렉토리 경로 (기본값: 현재 폴더)"
    )
    parser.add_argument("--model", type=str, default=None, help="사용할 Ollama 모델명 (기본값: 서버에 설치된 첫 번째 모델)")
    parser.add_argument("--workers", type=int, default=4, help="동시 처리할 이미지 수 (기본값: 4)")
    args = parser.parse_args()

    process_directory(args.dir, args.model, args.workers)
