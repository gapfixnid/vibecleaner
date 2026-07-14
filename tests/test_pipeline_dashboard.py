from scripts.aggregate_pipeline_benchmark import aggregate_records, render_dashboard


def row(date: str, *, equivalent: bool = True, match: float = 1.0):
    return {
        "recorded_at": f"{date}T12:00:00+00:00",
        "primary_succeeded": True,
        "shadow_succeeded": True,
        "equivalent": equivalent,
        "primary_duration_ms": 10,
        "shadow_duration_ms": 20,
        "metadata": {
            "ocr_text_match_ratio": match,
            "translation_match_ratio": match,
        },
    }


def test_benchmark_aggregation_groups_records_by_date():
    summary = aggregate_records([row("2026-07-13"), row("2026-07-13", match=0.5), row("2026-07-14", equivalent=False)])
    assert summary["overall"]["sample_count"] == 3
    assert summary["overall"]["equivalence_rate"] == round(2 / 3, 4)
    assert summary["by_date"]["2026-07-13"]["sample_count"] == 2
    assert summary["by_date"]["2026-07-14"]["equivalence_rate"] == 0.0


def test_dashboard_is_self_contained_and_contains_metrics():
    dashboard = render_dashboard(aggregate_records([row("2026-07-13")]))
    assert "VibeCleaner Pipeline Benchmark" in dashboard
    assert "Equivalence" in dashboard
    assert "2026-07-13" in dashboard
