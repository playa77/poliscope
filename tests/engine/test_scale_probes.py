"""Scale gates must expose current production admission limits, never bypass them."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.scale_fixtures import structural, graph
from scripts.benchmark_scale import admission, summarize
from scripts import benchmark_scale
from scripts.scale_fixtures import history_fixture

MANIFEST = json.loads(Path('docs/roadmap/execution/benchmarks.json').read_text())


def test_reference_requirement_honors_owner_waiver_without_waiving_implementation():
    assert MANIFEST['reference']['validation'] == 'owner-run'
    assert benchmark_scale.reference_blockers(MANIFEST) == []
    assert benchmark_scale.reference_blockers(dict(reference={})) == [dict(
        id='PERF-REF-001', reason='Exact native reference hardware and power settings not selected.')]


def test_semantic_history_harness_validates_retained_closure_and_archive(tmp_path):
    from scripts.benchmark_history import collect
    receipt = collect(tmp_path, revisions=2, branches=3, samples=1)
    assert receipt['counts'] == dict(committed_revisions=2, named_branches=3, semantic_trace_nodes=200)
    assert receipt['data_only_read_after_cache_clear'] is True
    assert receipt['archive']['status'] == 'validated'
    assert receipt['archive']['revisions'] == 2 and receipt['archive']['branches'] == 3
    assert receipt['trace_page_bytes'] < 1048576
    assert receipt['history_page']['samples'] == 1
    assert receipt['trace_page']['samples'] == 1
    assert receipt['status'] == 'passed'


def test_history_fixture_exact_chain_oracle_and_retained_trace_pages(tmp_path):
    from poliscope_engine.contracts.revisions import CreateRequest, PreviewRequest, ApplyRequest
    from poliscope_engine.contracts.measurements import TraceQuery
    from poliscope_engine.explanation import trace_page
    from poliscope_engine.revisions import Revisions
    from poliscope_engine.storage import Store
    host, inputs = history_fixture()
    with Store(tmp_path) as store:
        service = Revisions(store, registry=host)
        initial = service.create(CreateRequest(revision_contract=1, data_store_id=service.data_store_id,
            civilization_id='scale:civ', branch_id='main', name='Synthetic chain', operation_id='create', inputs=inputs))
        value = inputs.values[0].model_copy(update={'value': inputs.values[0].value.model_copy(update={'value': '7'})})
        request = PreviewRequest(revision_contract=1, context=initial.context,
            changes=[dict(kind='set_values', writer_id='scale:writer', partition='conditions', values=[value])],
            decision=dict(alternatives=[], selected_id=None, rationale_ref=None))
        candidate = service.preview(request)
        accepted = service.apply(ApplyRequest(revision_contract=1, operation_id='apply',
            preview=request, candidate_digest=candidate.candidate_digest))
        old = service.evidence(initial.context)
        saved = service.evidence(accepted.context)
        for evidence, start in [(old, 0), (saved, 7)]:
            outputs = {o.node[1]: o.value.value for o in evidence.evaluation.observations if o.node[0] == 'output'}
            assert outputs == {f'scale:step:{i:02}': str(start + i + 1) for i in range(50)}
            assert len(evidence.report.traces) == 100
            assert sum(len(t.dependency_refs) for t in evidence.report.traces) == 99
        root = next(t.id for t in saved.report.traces if t.members[0].node == ['output', 'scale:step:49', 'scale:out'])
        cursor, seen = None, set()
        while True:
            page = trace_page(saved.report, TraceQuery(report_digest=saved.report.report_digest,
                root_id=root, cursor=cursor, limit=25))
            assert len(page.items) <= 25 and len(page.model_dump_json().encode()) < 1048576
            assert not seen.intersection(t.id for t in page.items)
            seen.update(t.id for t in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        assert seen == {t.id for t in saved.report.traces}
        assert service.apply(ApplyRequest(revision_contract=1, operation_id='apply',
            preview=request, candidate_digest=candidate.candidate_digest)) == accepted
        with store.transaction():
            store.clear_caches()
        service.registry = None
        assert service.evidence(initial.context) == old
        assert service.evidence(accepted.context) == saved


def test_coupled_trace_identity_is_hashed_once_and_feedback_is_complete(monkeypatch):
    from poliscope_engine import explanation
    from poliscope_engine.measurements import observe
    from poliscope_engine.evaluation import evaluate
    from poliscope_engine.world.membership import WorldGraph
    from test_dependencies import plain, request, binding
    from test_solvers import host
    from test_evaluation import design
    from test_mechanism_registry import world
    definition = plain(('synthetic:in',))
    ids = [f'cycle:{i:03}' for i in range(100)]
    links = [binding(a, b) for a, b in zip(ids, ids[1:] + ids[:1])]
    registry = host(definition, lambda *a: pytest.fail('unsupported cycle must not execute'))
    result = evaluate(WorldGraph(world()), design(request(ids, definition, bindings=links)),
        (), registry.model, registry=registry)
    assert result.outcome == 'unresolved'
    expected_nodes = sorted((kind, i, port) for i in ids
        for kind, port in [('input', 'synthetic:in'), ('output', 'synthetic:out')])
    from poliscope_engine.evaluation.identity import digest
    expected_id = digest(dict(trace_schema=1, nodes=expected_nodes))
    calls = []
    def counted(payload):
        if isinstance(payload, dict) and payload.get('trace_schema') == 1:
            calls.append(payload)
        return digest(payload)
    monkeypatch.setattr(explanation, 'digest', counted)
    report = observe(result)
    assert len(calls) == 1
    trace, = report.traces
    assert trace.id == expected_id and trace.kind == 'solved_component'
    assert [tuple(m.node) for m in trace.members] == expected_nodes
    expected_edges = {(('input', i, 'synthetic:in'), ('output', i, 'synthetic:out')) for i in ids}
    expected_edges.update((('output', a, 'synthetic:out'), ('input', b, 'synthetic:in'))
        for a, b in zip(ids, ids[1:] + ids[:1]))
    assert {(tuple(a), tuple(b)) for a, b in trace.internal_edges} == expected_edges
    assert trace.dependency_refs == []


@pytest.mark.parametrize('name', ['classroom-v1', 'exploratory-v1'])
def test_stable_exact_structural_counts_and_bounded_aggregate_admission(name):
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
    assert a['status'] == 'admitted-structure-only'
    assert a['errors'] == []
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
