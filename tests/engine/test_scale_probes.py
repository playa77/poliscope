"""Scale gates must expose current production admission limits, never bypass them."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.scale_fixtures import structural, graph
from scripts.benchmark_scale import admission, summarize
from scripts import benchmark_scale

MANIFEST = json.loads(Path('docs/roadmap/execution/benchmarks.json').read_text())


@pytest.mark.parametrize('name', ['classroom-v1', 'exploratory-v1'])
def test_stable_exact_structural_counts_and_explicit_admission_blockers(name):
    counts = MANIFEST['fixtures'][name]
    entities, scopes, edges = structural(counts)
    assert len(scopes) == counts['scopes']
    assert len(entities) == 1 + sum(counts[k] for k in ['cohorts', 'assets', 'decision_instances'])
    assert len(edges) == counts['active_typed_edges']
    assert len({x.id for x in edges}) == len(edges)
    memberships = [r for r in edges if r.relationship_kind == 'cohort_membership']
    assert len(memberships) == 2 * counts['cohorts']
    assert all(sum(r.from_id == f'scale:population_cohort:{i:05}' for r in memberships) == 2
        for i in range(counts['cohorts']))
    a, b = admission(counts), admission(counts)
    assert a == b
    assert a['status'] == 'blocked'
    assert any(e['path'] == ['relationships'] and e['type'] == 'too_long' for e in a['errors'])
    assert any(e['contract'] == 'DependencyRequest' and e['path'] == ['instances'] for e in a['errors'])
    g = graph(counts)
    target = 'scale:asset:00000'
    assert [r.id for r in g.related(target)] == [r.id for r in edges if target in (r.from_id, r.to_id)]


def test_nearest_rank_p95_keeps_unsorted_raw_measurements():
    values = list(reversed(range(1, 31)))
    summary = summarize(values)
    assert summary['p95_ms'] == 29
    assert summary['raw_ms'] == values


@pytest.mark.parametrize('diagnostic,exit_code', [(False, 1), (True, 0)])
def test_unmet_release_gate_never_becomes_passed_receipt(monkeypatch, tmp_path, diagnostic, exit_code):
    receipt = dict(status='release-blocked', blockers=[dict(id='PERF-REF-001')])
    monkeypatch.setattr(benchmark_scale, 'collect', lambda samples: receipt)
    output = tmp_path/'receipt.json'
    monkeypatch.setattr(sys, 'argv', ['benchmark_scale', '--output', str(output),
        *(['--diagnostic-only'] if diagnostic else [])])
    assert benchmark_scale.main() == exit_code
    assert json.loads(output.read_text()) == receipt
