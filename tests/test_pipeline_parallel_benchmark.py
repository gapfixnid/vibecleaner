from scripts.benchmark_pipeline_parallel import run_benchmark


def test_parallel_scheduler_retains_expected_wall_clock_speedup():
    result = run_benchmark(delay_seconds=0.02, iterations=3)
    assert result["speedup"] >= 1.5
