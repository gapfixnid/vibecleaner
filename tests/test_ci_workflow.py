from pathlib import Path


def test_fast_ci_runs_and_uploads_golden_regression_report():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/benchmark_golden_regression.py" in workflow
    assert "golden-regression.json" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_fast_ci_does_not_require_machine_specific_baseline():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--baseline" not in workflow
