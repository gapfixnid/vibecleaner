import json
import subprocess
import sys
from pathlib import Path


def test_golden_corpus_has_required_categories():
    path = Path("tests/fixtures/golden_image_corpus.json")
    corpus = json.loads(path.read_text(encoding="utf-8"))
    categories = {case["category"] for case in corpus["cases"]}
    assert {"black_white_manga", "color_webtoon", "very_long_vertical", "low_contrast_text", "sfx_and_dialogue", "no_text"} <= categories
    assert len({case["case_id"] for case in corpus["cases"]}) == len(corpus["cases"])


def test_golden_regression_script_emits_deterministic_case_results(tmp_path):
    output = tmp_path / "golden.json"
    subprocess.run(
        [sys.executable, "scripts/benchmark_golden_regression.py", "--output", str(output), "--repeat", "1"],
        check=True,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["corpus_id"] == "vibecleaner-golden-images-v1"
    assert len(result["cases"]) == 7
    assert all(item["width"] > 0 and item["height"] > 0 for item in result["cases"])
    assert all(len(item["digest"]) == 64 for item in result["cases"])
