from types import SimpleNamespace

from backend.pipeline.page_translation_stages import _inpaint_quality_rank


def test_passed_inpainting_result_ranks_above_higher_scoring_failure():
    failed = SimpleNamespace(
        passed=False, score=0.95,
        signals={"outside_preserved_ratio": 0.8, "target_change_ratio": 0.9},
    )
    passed = SimpleNamespace(
        passed=True, score=0.75,
        signals={"outside_preserved_ratio": 0.98, "target_change_ratio": 0.5},
    )
    assert _inpaint_quality_rank(passed) > _inpaint_quality_rank(failed)
