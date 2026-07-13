from scripts.evaluate_pipeline_rollout import evaluate_records


def record(*, equivalent=True, success=True, match=1.0):
    return {
        "primary_succeeded": success,
        "shadow_succeeded": success,
        "equivalent": equivalent,
        "metadata": {
            "ocr_text_match_ratio": match,
            "translation_match_ratio": match,
        },
    }


def test_rollout_gate_passes_validated_samples():
    result = evaluate_records([record() for _ in range(10)])
    assert result["passed"] is True
    assert result["metrics"]["equivalence_rate"] == 1.0


def test_rollout_gate_rejects_insufficient_or_regressed_samples():
    result = evaluate_records([record(equivalent=False, match=0.5)], minimum_samples=2)
    assert result["passed"] is False
    assert "requires at least 2 samples" in result["failures"]
    assert "equivalence rate below threshold" in result["failures"]
