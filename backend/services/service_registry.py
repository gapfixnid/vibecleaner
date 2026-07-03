from app.qt_runtime import qt_app  # noqa: F401
from services.bubble_analysis_service import BubbleAnalysisService
from services.detection_service import DetectionService
from services.export_service import ExportService
from services.inpainting_service import InpaintingService
from services.layout_planner_service import LayoutPlannerService
from services.page_analysis_service import PageAnalysisService
from services.render_service import RenderService
from services.translation_service import TranslationService


translation_service = TranslationService()
detection_service = DetectionService()
inpainting_service = InpaintingService()
render_service = RenderService()
export_service = ExportService(render_service)
page_analysis_service = PageAnalysisService()
bubble_analysis_service = BubbleAnalysisService()
layout_planner_service = LayoutPlannerService()
