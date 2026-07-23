from __future__ import annotations

import numpy as np

from backend.core.models import Rect, TextBubble
from backend.core.models.problem import (
    BubbleProblem,
    BubbleProblemCode,
    normalize_bubble_problem,
)
from backend.engines.common.textblock import TextBlock
from backend.engines.ocr.retry import (
    OcrSnapshot,
    choose_ocr_retry,
)
from backend.infrastructure.storage.project_schema import (
    CURRENT_PROJECT_SCHEMA_VERSION,
    normalize_project_metadata,
)
from backend.pipeline.analysis.bubbles import BubbleAnalysisService
from backend.pipeline.page_analysis import merge_overlapping_bubbles
from backend.engines.translation.outcome import (
    TranslationRequestContext,
    translate_with_legacy_adapter,
)
from backend.pipeline.page_translation_stages import _quality_rank
from backend.pipeline.quality import QualityScore


def test_schema_v2_problem_migration_is_lossless_and_idempotent():
    source = {
        "format": "vibecleaner-project",
        "schema_version": 2,
        "version": "2.0",
        "pages": [
            {
                "page_id": "page_a",
                "bubbles": [
                    {
                        "id": 1,
                        "box": [0, 0, 10, 10],
                        "problems": [
                            "layout overflow",
                            "manual note one",
                            "manual note two",
                        ],
                    }
                ],
            }
        ],
    }

    migrated = normalize_project_metadata(source)
    problems = migrated["pages"][0]["bubbles"][0]["problems"]
    assert migrated["schema_version"] == CURRENT_PROJECT_SCHEMA_VERSION
    assert problems == [
        {"code": "TEXT_OVERFLOW", "detail": None},
        {"code": "LEGACY_REVIEW_NOTE", "detail": "manual note one"},
        {"code": "LEGACY_REVIEW_NOTE", "detail": "manual note two"},
    ]
    assert normalize_project_metadata(migrated) == migrated


def test_unknown_structured_problem_preserves_original_detail():
    problem = normalize_bubble_problem(
        {"code": "FUTURE_CODE", "detail": "keep me"}
    )
    assert problem.code == BubbleProblemCode.LEGACY_REVIEW_NOTE
    assert problem.detail == "keep me"


def test_legacy_translation_failure_message_is_not_reclassified():
    problem = normalize_bubble_problem(
        "translation provider connection failed"
    )
    assert problem == BubbleProblem(
        BubbleProblemCode.LEGACY_REVIEW_NOTE,
        "translation provider connection failed",
    )


def test_loaded_input_warnings_survive_layout_only_reconciliation():
    bubble = TextBubble(
        id=1,
        box=Rect(0, 0, 40, 40),
        problems=[
            BubbleProblem(BubbleProblemCode.OCR_UNCERTAIN),
            BubbleProblem(BubbleProblemCode.MASK_UNCERTAIN),
        ],
    )
    assert bubble._derived_problem_codes == {
        "OCR_UNCERTAIN",
        "MASK_UNCERTAIN",
    }


def test_ocr_suspicious_recovery_overrides_normal_improvement_rule():
    decision = choose_ocr_retry(
        OcrSnapshot("", None),
        OcrSnapshot("これは正常な長い台詞です", 0.75),
        "Japanese",
    )
    assert decision.accepted
    assert decision.selected.text == "これは正常な長い台詞です"


def test_ocr_retry_without_candidate_confidence_keeps_original():
    decision = choose_ocr_retry(
        OcrSnapshot("あ", 0.2),
        OcrSnapshot("ありがとう", None),
        "Japanese",
    )
    assert not decision.accepted
    assert decision.uncertain


def test_rejected_retry_does_not_warn_for_high_confidence_original():
    decision = choose_ocr_retry(
        OcrSnapshot("정상 원문입니다", 0.90),
        OcrSnapshot("bad candidate", 0.91),
        "Korean",
    )
    assert not decision.accepted
    assert not decision.uncertain


def test_long_english_candidate_requires_half_latin_script():
    decision = choose_ocr_retry(
        OcrSnapshot("", None),
        OcrSnapshot("abcd가나다라마바사아자차", 0.90),
        "English",
    )
    assert not decision.accepted
    assert decision.reason == "invalid_candidate"


def test_different_detector_bubble_ids_never_merge_in_analysis_or_postpass():
    image = np.full((120, 160, 3), 255, np.uint8)
    first = TextBlock(
        text_bbox=np.array([20, 20, 70, 60]),
        bubble_bbox=np.array([10, 10, 90, 80]),
        text="first",
        bubble_match_id=1,
    )
    second = TextBlock(
        text_bbox=np.array([45, 25, 95, 65]),
        bubble_bbox=np.array([12, 12, 92, 82]),
        text="second",
        bubble_match_id=2,
    )
    analyzed = BubbleAnalysisService().analyze(
        image, [first, second]
    )
    assert len(analyzed.bubbles) == 2

    runtime = [
        TextBubble(
            id=1,
            box=Rect(10, 10, 80, 70),
            _source_bubble_match_id=1,
        ),
        TextBubble(
            id=2,
            box=Rect(12, 12, 80, 70),
            _source_bubble_match_id=2,
        ),
    ]
    assert len(merge_overlapping_bubbles(runtime)) == 2


def test_translation_outcome_does_not_mutate_original_blocks():
    class LegacyProvider:
        def translate_blocks(
            self, blocks, _source, _target, _image
        ):
            blocks[0].translation = "translated"

    original = TextBlock(text="source", translation="")
    outcome = translate_with_legacy_adapter(
        LegacyProvider(),
        [original],
        "Japanese",
        "Korean",
        None,
        TranslationRequestContext(
            provider="legacy",
            model="test",
            vision_enabled=False,
            image_digest=None,
            temperature=None,
            top_p=None,
            max_tokens=None,
        ),
    )
    assert original.translation == ""
    assert outcome.values[0].text == "translated"


def test_detection_retry_rank_keeps_better_initial_attempt():
    initial = QualityScore(
        "detection",
        0.88,
        True,
        {
            "ambiguous_match_ratio": 0.05,
            "unmatched_ratio": 0.0,
        },
    )
    retry = QualityScore(
        "detection",
        0.65,
        False,
        {
            "ambiguous_match_ratio": 0.30,
            "unmatched_ratio": 0.25,
        },
    )
    assert _quality_rank(initial) > _quality_rank(retry)
