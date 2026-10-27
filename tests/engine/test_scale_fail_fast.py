"""Annual requests stop at the short gate instead of repeating a known failure."""
from scripts import benchmark_dynamic_scale as benchmark


def test_requested_annual_run_stops_after_three_slow_measured_boundaries(tmp_path, monkeypatch):
    ticks = iter(range(0, 10**15, 100_000_000))
    monkeypatch.setattr(benchmark.time, 'perf_counter_ns', lambda: next(ticks))
    result = benchmark.run(tmp_path, days=365, seconds=30)
    assert result['status'] == 'annual_throughput_gate_failed'
    assert result['requested_days'] == 365 and result['confirmed_days'] == 3
    assert len(result['raw_boundary_ms']) == 3
    assert result['all_confirmed_values_match_integer_oracle']
    assert result['release_issue'] == 'PERF-DYNAMIC-001'
    assert 'no annual budget claim' in result['performance_claim']
