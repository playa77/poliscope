"""Retain 100,000 real semantic trace nodes through ordinary revision services.

This workload complements benchmark_scale; it never certifies the DEC-06 domain
or native UI budgets. No DTO, transport, archive or execution quota is bypassed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.scale_fixtures import history_fixture
from scripts.benchmark_scale import measure, summarize, machine
from poliscope_engine.archives import export_archive, validate_archive, ArchiveError
from poliscope_engine.contracts.revisions import CreateRequest, PreviewRequest, ApplyRequest, BranchRequest, HistoryQuery
from poliscope_engine.contracts.measurements import TraceQuery
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.explanation import trace_page
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store


def collect(directory, *, revisions=1000, branches=20, samples=30):
    host, inputs = history_fixture()
    counts = dict(committed_revisions=revisions, named_branches=branches, semantic_trace_nodes=revisions * 100)
    result = dict(version=1, package='WP-051', workload='semantic-history-v1', counts=counts,
        layer='ordinary Create/Preview/Apply/Fork, retained evidence and trace pages; synthetic increment chain',
        candidate=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT)).hexdigest(),
        fixture_digest=digest(inputs), machine=machine(), samples=samples,
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in [
            'scripts/benchmark_history.py', 'scripts/scale_fixtures.py',
            'engine/poliscope_engine/explanation/__init__.py']},
        limitations=['not the coupled twelve-domain preview/advance workload',
            'Python service measurements exclude Electron', 'native validation is owner-run'])
    with Store(directory / 'store') as store:
        service = Revisions(store, registry=host)
        outcome = service.create(CreateRequest(revision_contract=1, data_store_id=service.data_store_id,
            civilization_id='scale:civ', branch_id='main', name='Synthetic semantic history',
            operation_id='history:create', inputs=inputs))
        initial = outcome.context
        first = service.evidence(initial)
        durations = []
        for i in range(1, revisions):
            value = inputs.values[0].model_copy(update={'value': inputs.values[0].value.model_copy(update={'value': str(i)})})
            request = PreviewRequest(revision_contract=1, context=outcome.context,
                changes=[dict(kind='set_values', writer_id='scale:writer', partition='conditions', values=[value])],
                decision=dict(alternatives=[], selected_id=None, rationale_ref=None))
            start = time.perf_counter_ns()
            candidate = service.preview(request)
            durations.append((time.perf_counter_ns() - start) / 1e6)
            outcome = service.apply(ApplyRequest(revision_contract=1, operation_id=f'history:{i}',
                preview=request, candidate_digest=candidate.candidate_digest))
            if i % 50 == 0:
                print(f'Retained {i + 1}/{revisions} revisions', flush=True)
        for i in range(1, branches):
            service.change_branch(BranchRequest(revision_contract=1, operation_id=f'history:fork:{i}',
                context=outcome.context, expected_sequence=outcome.branch_sequence, action='fork',
                new_branch_id=f'scale:branch:{i}', name=f'Synthetic branch {i}'))
        assert len(service.catalogue()) == branches
        cursor, total, nodes, identities = None, 0, 0, []
        while True:
            page = service.history(HistoryQuery(context=outcome.context, cursor=cursor, limit=100))
            assert len(page.items) <= 100 and len(page.model_dump_json().encode()) < 1048576
            for row in page.items:
                saved = service.evidence(row.context)
                # Independent integer oracle verifies every retained node's value,
                # not just a SQLite row count or the final aggregate.
                for trace in saved.report.traces:
                    member, = trace.members
                    step = int(member.node[1].rsplit(':', 1)[1])
                    assert member.value.value == str(total + step + (member.node[0] == 'output'))
                assert len(saved.report.traces) == 100
                assert sum(len(t.dependency_refs) for t in saved.report.traces) == 99
                identities.append([row.context.revision_id, saved.closure_digest])
                total += 1
                nodes += len(saved.report.traces)
            cursor = page.next_cursor
            if cursor is None:
                break
        assert total == revisions and nodes == counts['semantic_trace_nodes']
        result['retained_identity_digest'] = digest(identities)
        result['preview'] = summarize(durations) if durations else None
        query = HistoryQuery(context=outcome.context, cursor=None, limit=100)
        result['history_page'], _ = measure(lambda: service.history(query), samples)
        saved = service.evidence(outcome.context)
        root = next(t.id for t in saved.report.traces if t.members[0].node == ['output', 'scale:step:49', 'scale:out'])
        tq = TraceQuery(report_digest=saved.report.report_digest, root_id=root, cursor=None, limit=25)
        result['trace_page'], page = measure(lambda: trace_page(saved.report, tq), samples)
        result['trace_page_bytes'] = len(page.model_dump_json().encode())
        cursor, seen = None, set()
        while True:
            page = trace_page(saved.report, tq.model_copy(update={'cursor': cursor}))
            assert len(page.items) <= 25 and len(page.model_dump_json().encode()) < 1048576
            assert not seen.intersection(t.id for t in page.items)
            seen.update(t.id for t in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        assert seen == {t.id for t in saved.report.traces}
        with store.transaction():
            store.clear_caches()
        service.registry = None
        assert service.evidence(initial) == first
        assert service.evidence(outcome.context) == saved
        result['data_only_read_after_cache_clear'] = True
        start = time.perf_counter_ns()
        try:
            exported = export_archive(service, directory / 'semantic-history.zip')
            _, items = validate_archive(directory / 'semantic-history.zip')
            result['archive'] = dict(status='validated', elapsed_ms=(time.perf_counter_ns() - start) / 1e6,
                samples=1, revisions=exported.revisions, branches=exported.branches,
                bytes=(directory / 'semantic-history.zip').stat().st_size, entries=len(items))
        except ArchiveError as error:
            result['archive'] = dict(status='blocked', diagnostic=str(error), issue='PERF-SEMANTIC-ARCHIVE-001')
        result['status'] = 'passed' if result['archive']['status'] == 'validated' else 'blocked'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='New isolated writable directory; retains the generated store')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    result = collect(args.directory)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
