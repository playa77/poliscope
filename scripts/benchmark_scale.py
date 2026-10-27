"""Reproducible, fail-closed WP-051 diagnostics; no release certification.

Run: uv run --frozen python scripts/benchmark_scale.py --output /tmp/scale.json
Exit 1 means an unmet release gate. --diagnostic-only preserves that status in
the receipt while allowing collection on a nonreference development worker.
"""
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
try:
    import resource
except ImportError:  # Windows has no standard-library process RSS counter.
    resource = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests/engine'))
from pydantic import ValidationError
from poliscope_engine import atlas, grounding
from poliscope_engine.archives import export_archive, validate_archive, ArchiveError
from poliscope_engine.contracts.revisions import RevisionInputs, PreviewRequest, ApplyRequest, BranchRequest, HistoryQuery
from poliscope_engine.contracts.dependencies import DependencyRequest
from poliscope_engine.dependencies import _components
from poliscope_engine.evaluation import EvaluationCache
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.revisions import Revisions, graph as revision_graph
from poliscope_engine.storage import Store
from poliscope_engine.workspace import dispatch, registry
from scripts.scale_fixtures import structural, graph, VERSION
import headless_fixture


def summarize(samples):
    return dict(raw_ms=samples, p95_ms=sorted(samples)[math.ceil(.95 * len(samples))-1],
                min_ms=min(samples), max_ms=max(samples), samples=len(samples))


def measure(function, samples):
    values, result = [], None
    for _ in range(samples):
        start = time.perf_counter_ns()
        result = function()
        values.append((time.perf_counter_ns()-start) / 1_000_000)
    return summarize(values), result


def reference_blockers(manifest):
    """Honor the owner's project-wide native-validation decision explicitly."""
    if manifest['reference'].get('validation') == 'owner-run':
        return []
    return [dict(id='PERF-REF-001', reason='Exact native reference hardware and power settings not selected.')]


def machine():
    """Nonsecret host facts; unknown SSD/power configuration stays unknown."""
    data = dict(logical_cpus=os.cpu_count(), cpu_model=None, ram_bytes=None,
        cpu_quota=None, power_mode=None, ssd_verified=False, native_reference=False,
        workspace_disk_total_bytes=shutil.disk_usage(ROOT).total)
    if sys.platform == 'linux':
        data['cpu_model'] = next((line.split(':', 1)[1].strip()
            for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), None)
        data['ram_bytes'] = next((int(line.split()[1])*1024
            for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')), None)
        quota = Path('/sys/fs/cgroup/cpu.max')
        data['cpu_quota'] = quota.read_text().strip() if quota.exists() else None
    return data


def admission(counts):
    entities, scopes, edges = structural(counts)
    raw = headless_fixture.inputs().model_dump(mode='json')
    raw.update(entities=[x.model_dump() for x in entities], scopes=[x.model_dump() for x in scopes],
               relationships=[x.model_dump() for x in edges])
    # Admission only: no bypass of the production DTO or execution of invalid
    # copied account/scope references is permitted.
    errors = []
    for model, data in [(RevisionInputs, raw), (DependencyRequest,
            raw['design']['execution']['dependencies'] | {'instances': [dict(id=f'instance:{i}',
                mechanism_id='synthetic:demand', mechanism_version='v1', scope_id=scopes[0].id,
                entity_id=entities[0].id) for i in range(counts['decision_instances'])]})]:
        try:
            model.model_validate(data)
        except ValidationError as error:
            errors.extend(dict(contract=model.__name__, path=list(e['loc']), type=e['type']) for e in error.errors())
    return dict(status='blocked' if errors else 'admitted-structure-only', errors=errors,
                serialized_bytes=len(json.dumps(raw).encode()), fixture_digest=digest(dict(
                    version=VERSION, entities=entities, scopes=scopes, relationships=edges)))


def history_probe(root, counts, samples):
    """Actual immutable revisions/branches; a simple history, not a domain run."""
    with Store(root/'history') as store:
        service = Revisions(store, registry=registry())
        created = dispatch(service, 'create', dict(name='Synthetic long history', setup='blank',
            scope_name='Home', population='0', land_area='1'), 'history:create')
        context = created.context
        data = service.read(context).inputs.model_dump(mode='json')
        durations = []
        for i in range(1, counts['committed_revisions']):
            data['values'][0]['value']['value'] = str(i)
            request = PreviewRequest.model_validate(dict(revision_contract=1, context=context,
                changes=[dict(kind='replace_inputs', inputs=data)],
                decision=dict(alternatives=[], selected_id=None, rationale_ref=None)))
            start = time.perf_counter_ns()
            candidate = service.preview(request)
            durations.append((time.perf_counter_ns()-start)/1e6)
            context = service.apply(ApplyRequest(revision_contract=1, operation_id=f'history:{i}',
                preview=request, candidate_digest=candidate.candidate_digest)).context
        sequence = service.branch(context).sequence
        for i in range(1, counts['named_branches']):
            service.change_branch(BranchRequest(revision_contract=1, operation_id=f'branch:{i}',
                context=context, expected_sequence=sequence, action='fork',
                new_branch_id=f'scale:branch:{i}', name=f'Synthetic branch {i}'))
        query = HistoryQuery(context=context, cursor=None, limit=100)
        timings, page = measure(lambda: service.history(query), samples)
        cursor, total, seen = None, 0, set()
        while True:
            part = service.history(query.model_copy(update={'cursor': cursor}))
            assert len(part.items) <= 100 and len(part.model_dump_json().encode()) < 1048576
            for row in part.items:
                assert row.context.revision_id not in seen
                seen.add(row.context.revision_id)
            total += len(part.items)
            cursor = part.next_cursor
            if cursor is None: break
        assert total == counts['committed_revisions']
        assert len(service.catalogue()) == counts['named_branches']
        before = service.evidence(context).model_dump_json()
        with store.transaction(): store.clear_caches()
        assert service.evidence(context).model_dump_json() == before
        result = dict(layer='actual simple immutable revisions and named branches; no domain transitions',
            committed_revisions=total, named_branches=len(service.catalogue()),
            successive_preview=summarize(durations), warm_page=timings,
            page_bytes=len(page.model_dump_json().encode()), preserved_after_cache_clear=True)
        start = time.perf_counter_ns()
        try:
            exported = export_archive(service, root/'long-history.zip')
            _, items = validate_archive(root/'long-history.zip')
            result['archive'] = dict(status='validated', elapsed_ms=(time.perf_counter_ns()-start)/1e6,
                samples=1, revisions=exported.revisions, branches=exported.branches,
                bytes=(root/'long-history.zip').stat().st_size, entries=len(items))
        except ArchiveError as error:
            result['archive'] = dict(status='blocked', diagnostic=str(error))
        return result


def collect(samples):
    manifest = json.loads((ROOT/'docs/roadmap/execution/benchmarks.json').read_text())
    report = dict(version=1, package='WP-051', status='release-blocked', fixture_version=VERSION,
        observed_at=datetime.now(timezone.utc).isoformat(), machine=machine(), command=sys.argv,
        candidate=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git','diff','HEAD'], cwd=ROOT)).hexdigest(),
        platform=platform.platform(), architecture=platform.machine(), python=platform.python_version(),
        node=subprocess.check_output(['node', '--version'], text=True).strip(),
        declared_electron=json.loads((ROOT/'package.json').read_text())['devDependencies']['electron'],
        conditions='Development cloud; no reference certification; run in isolation for interpretable latency diagnostics.',
        logical_cpus=os.cpu_count(), clock='perf_counter_ns; monotonic', samples=samples,
        memory_scope='single diagnostic Python process high-water RSS; excludes Electron; not combined budget evidence',
        reference_machine=False, budgets=manifest['budgets'], workloads={}, blockers=[
            dict(id='PERF-MODEL-001', reason='DEC-06 coupled twelve-domain arithmetic, SCC coefficients and 365-day transition fixture not frozen; structural probes cannot certify evaluation/advance.'),
        ])
    report['native_validation'] = manifest['reference'].get('validation', 'required')
    report['blockers'].extend(reference_blockers(manifest))
    report['owner_run_validation'] = [
        'native Windows/Linux correctness and replay',
        'combined Electron RSS and running-work keyboard/navigation/cancel p95',
        'native reference desktop latency and throughput budgets',
    ] if report['native_validation'] == 'owner-run' else []
    if report['native_validation'] != 'owner-run':
        report['blockers'].append(dict(id='PERF-UI-001', reason='Native integrated UI/RSS measurements pending.'))
    report['source_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in [
        'scripts/benchmark_scale.py', 'scripts/scale_fixtures.py', 'tests/engine/headless_fixture.py',
        'engine/poliscope_engine/world/membership.py', 'engine/poliscope_engine/evaluation/__init__.py',
        'docs/roadmap/execution/benchmarks.json']}
    workloads = report['workloads']
    for name in ['classroom-v1', 'exploratory-v1']:
        print('Measuring '+name, flush=True)
        counts = manifest['fixtures'][name]
        admitted = admission(counts)
        if admitted['status'] == 'blocked':
            report['blockers'].append(dict(id='PERF-ADMISSION-'+name, reason=admitted['errors']))
        g = graph(counts)
        target = 'scale:asset:00000'
        expected = tuple(r.id for r in g.relationships if target in (r.from_id, r.to_id))
        baseline, baseline_rows = measure(lambda: tuple(r for r in g.relationships if target in (r.from_id, r.to_id)), samples)
        warm, result = measure(lambda: g.related(target), samples)
        assert tuple(r.id for r in result) == expected == tuple(r.id for r in baseline_rows)
        workloads[name] = dict(counts=counts, admission=admitted, layer='internal structural WorldGraph; not revision/public world page',
            baseline_scan=baseline, indexed_query=warm, output_digest=digest(expected))
        # Matrix assembly is the actual iterative SCC compiler primitive. The
        # ring creates one coupled SCC; no solver success is inferred.
        keys = [(f'node:{i:05}',) for i in range(counts['decision_instances'])]
        edges = {(keys[i], keys[(i+j+1) % len(keys)]) for i in range(len(keys))
                 for j in range(counts['active_typed_edges']//len(keys))}
        timings, components = measure(lambda: _components(keys, edges, set()), samples)
        workloads[name]['scc_primitive'] = dict(timing=timings, nodes=len(keys), edges=len(edges),
            components=len(components), status='solver_required; graph-only diagnostic')
    with tempfile.TemporaryDirectory(prefix='poliscope-scale-') as directory:
        root = Path(directory)
        with Store(root) as store:
            service = Revisions(store, registry=registry())
            state = dispatch(service, 'create', dict(name='Synthetic scale diagnostic', setup='blank',
                scope_name='Home', population=None, land_area=None), 'scale:create')
            query = dict(context=state.context.model_dump(), scope_id='home')
            timings, page = measure(lambda: atlas.page(service, query), samples)
            workloads['atlas'] = dict(layer='actual bundled catalog and revision; not scaled catalog', timing=timings,
                records=len(page.items), total=page.total, output_digest=digest(page), bytes=len(page.model_dump_json().encode()))
            timings, context = measure(lambda: grounding.assemble(service, dict(context=state.context.model_dump(),
                selection=dict(scope_id='home', task='Explain synthetic inputs', collections=['facts'], tools=True))), samples)
            workloads['assistant-context'] = dict(layer='actual blank revision; not scaled context', timing=timings, output_digest=digest(context))
            indices = itertools.count()
            def export():
                return export_archive(service, root/f'archive-{next(indices)}.zip')
            timings, exported = measure(export, samples)
            destination = root/f'archive-{samples-1}.zip'
            _, items = validate_archive(destination)
            workloads['archive'] = dict(layer='actual single-revision archive; not history-v1', timing=timings,
                entries=len(items), bytes=destination.stat().st_size)
            start = time.perf_counter_ns()
            try:
                export_archive(service, root/'cancel.zip', cancelled=lambda: True)
                raise AssertionError('Cancelled export unexpectedly succeeded')
            except ArchiveError:
                pass
            workloads['archive']['cancel_ack_ms'] = (time.perf_counter_ns()-start)/1_000_000
            workloads['archive']['cancel_preserved_revision'] = service.read(state.context).context == state.context
        print('Building and measuring real history', flush=True)
        workloads['history'] = history_probe(root, manifest['fixtures']['history-v1'], samples)
        if workloads['history']['archive']['status'] == 'blocked':
            report['blockers'].append(dict(id='PERF-HISTORY-ARCHIVE-001', reason=workloads['history']['archive']['diagnostic']))
        # Exact 100k-row SQLite keyset probe, deliberately NOT mislabeled as
        # 100k accepted explanation nodes or 1000 semantic committed revisions.
        with Store(root/'trace-index') as store:
            with store.transaction():
                store.add_context('scale', '{}')
                for i in range(manifest['fixtures']['history-v1']['pageable_trace_nodes']):
                    store.add_record('scale', 'trace-index-probe', f'{i:08}', json.dumps({'dependency': max(0, i-1)}))
            timings, rows = measure(lambda: store.record_page('scale', 'trace-index-probe', after='00050000', limit=100), samples)
            assert [x[0] for x in rows] == [f'{i:08}' for i in range(50001, 50101)]
            workloads['trace-index'] = dict(layer='SQLite primitive only; no accepted trace closure', timing=timings,
                rows=100000, page_size=len(rows), output_digest=digest(rows))
    data = headless_fixture.inputs()
    world, host = revision_graph(data, 'civ'), headless_fixture.registry()
    cache = EvaluationCache()
    def evaluate():
        return cache.evaluate(world, data.design, data.assumptions, host.model, registry=host)
    cold_values, warm_values, identity = [], [], None
    for _ in range(samples):
        cache.clear()
        start = time.perf_counter_ns(); cold = evaluate(); cold_values.append((time.perf_counter_ns()-start)/1e6)
        start = time.perf_counter_ns(); warm = evaluate(); warm_values.append((time.perf_counter_ns()-start)/1e6)
        assert cold == warm
        if identity is None: identity = cold.identities.model_dump()
        assert identity == cold.identities.model_dump()
    workloads['evaluation-cache'] = dict(layer='actual WP-019 finite allocation oracle; not DEC-06 world',
        cold=summarize(cold_values), warm=summarize(warm_values), identities=identity)
    report['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 if resource is not None else None
    report['unverified_workloads'] = ['classroom/exploratory coupled preview and advance',
        '100000 retained trace nodes in semantic accepted evidence',
        'scaled twelve-domain archives/context', 'public sparse matrix pages', 'solver/time/memory quota integration',
        'Windows correctness/replay', 'renderer progress and stale query cancellation']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--diagnostic-only', action='store_true')
    args = parser.parse_args()
    if not 30 <= args.samples <= 1000:
        parser.error('samples must be between 30 and 1000')
    result = collect(args.samples)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(f"{result['status']}: {len(result['blockers'])} blockers; receipt {args.output}")
    return 0 if args.diagnostic_only else 1


if __name__ == '__main__':
    raise SystemExit(main())
