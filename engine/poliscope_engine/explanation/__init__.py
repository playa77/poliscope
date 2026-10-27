"""Pure trace DAGs, authored templates and detached accepted-result closure.

This service prepares and reads data. WP-018 must persist the complete closure
atomically with acceptance, independently of disposable evaluation caches.
"""
import json
from hashlib import sha256
import orjson
from types import MappingProxyType
from poliscope_engine.contracts.measurements import (
    CalculationTrace, MechanismRef, MeasurementReport, AcceptedEvidence,
    EvidenceReference, TraceQuery, CalculationTracePage)
from poliscope_engine.dependencies import _components
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.evaluation.canonical import Memo

_trace_plans = Memo(8 * 1024 * 1024, entries=4)
_reference_sets = Memo(8 * 1024 * 1024, entries=16)


def _trace_plan(observations, edges):
    key = tuple(sorted(observations)), tuple(sorted(edges))
    cached = _trace_plans.get(key)
    if cached is not None:
        return cached
    groups = _components(observations, edges, set())
    node_trace = {}
    for group in groups:
        trace_id = digest(dict(trace_schema=1, nodes=group.nodes))
        node_trace.update((node, trace_id) for node in group.nodes)
    dependencies = {node_trace[g.nodes[0]]: set() for g in groups}
    internal = {identity: [] for identity in dependencies}
    for a, b in sorted(edges):
        source, target = node_trace[a], node_trace[b]
        if source != target:
            dependencies[target].add(source)
        else:
            internal[source].append((a, b))
    plan = (groups, MappingProxyType(node_trace),
        MappingProxyType({k: tuple(sorted(v)) for k, v in dependencies.items()}),
        MappingProxyType({k: tuple(v) for k, v in internal.items()}))
    _trace_plans.put(key, plan, len(repr(key).encode()) + len(repr(plan).encode()))
    return plan

# Fixed host-authored text is separate from numerical values and any AI prose.
TEMPLATES = {
    'named_diagnostic:v1': 'A named diagnostic matched. Inspect the rule, value and threshold.',
    'coverage_gap:v1': 'This observation has qualified coverage. Inspect its inputs and assumptions.',
    'player_target:v1': 'A player target was observed after physical evaluation.',
    'unmet_claim:v1': 'A declared claim has an unmet amount. Inspect the allocation and account.',
    'constrained_claim:v1': 'A claim remains unmet under the selected access, funding or allocation constraints.',
    'policy_gap:v1': 'Policy evaluation lacks a resolved applicable rule or value.',
}


class EvidenceError(ValueError):
    pass


def build_traces(result):
    """Condense SCCs; every evaluated node belongs to exactly one DAG vertex."""
    from poliscope_engine.contracts.evaluation import NodeObservation
    observations = {tuple(o.node): NodeObservation.model_validate_json(o.model_dump_json()) for o in result.observations}
    if len(observations) != len(result.observations):
        raise EvidenceError('duplicate_trace_node')
    edges = {(tuple(e.source), tuple(e.target)) for e in result.trace_edges}
    if any(a not in observations or b not in observations for a, b in edges):
        raise EvidenceError('dangling_trace_edge')
    snapshot = orjson.loads(result.input_json)
    design = snapshot['design']
    world_values = {v['id']: v for v in snapshot['world']['values']}
    for binding in design['world_inputs']:
        consumer = binding['consumer']
        key = ('input', consumer['instance_id'], consumer['port_id'])
        row = observations[key]
        provenance = world_values[binding['value_id']]['provenance']
        observations[key] = row.model_copy(update={
            'source_refs': sorted(set(row.source_refs) | set(provenance['source_refs'])),
            'assumption_refs': sorted(set(row.assumption_refs) | set(provenance['assumption_refs']))})
    for binding in design['assumption_inputs']:
        consumer = binding['consumer']
        key = ('input', consumer['instance_id'], consumer['port_id'])
        row = observations[key]
        observations[key] = row.model_copy(update={'assumption_refs': sorted(set(row.assumption_refs) | {binding['value_id']})})
    instances = design['execution']['dependencies']['instances']
    instances = {i['id']: MechanismRef(instance_id=i['id'], **{k: v for k, v in i.items() if k != 'id'}) for i in instances}
    groups, planned_nodes, dependencies, internal = _trace_plan(observations, edges)
    node_trace = dict(planned_nodes)
    traces = []
    for group in groups:
        key = node_trace[group.nodes[0]]
        refs = {n[1] for n in group.nodes if n[0] in ('input', 'output', 'claim', 'actual_consumption')}
        if not refs <= instances.keys():
            raise EvidenceError('missing_trace_mechanism')
        traces.append(CalculationTrace(id=key, kind='solved_component' if group.cyclic else 'node',
            members=[observations[n] for n in group.nodes], mechanisms=[instances[i] for i in sorted(refs)],
            effective_time=result.effective_time, dependency_refs=list(dependencies[key]),
            internal_edges=[(list(a), list(b)) for a, b in internal[key]]))
    # Final account and distribution values also need traversable evidence;
    # they are not all compiler ports (e.g. closing balance and unmet claims).
    if result.accounts is not None:
        from poliscope_engine.contracts.evaluation import NodeObservation
        from poliscope_engine.contracts.world import QuantityValue, LabelValue
        batch = orjson.loads(result.final_batch_json)
        accounts = {a['id']: a for a in batch['accounts']}
        claims = {c['id']: c for c in batch['claims']}
        execution = orjson.loads(result.input_json)['design']['execution']
        mappings = {c['account_claim_id']: c for c in execution['claims']}
        def final_trace(kind, identity, fields, account, source_refs, dependencies):
            members = [NodeObservation(node=[kind, identity, name], scope_id=account['scope_id'],
                entity_id=account['id'], status='known', reason='exact_final_account',
                value=QuantityValue(kind='quantity', value=value, unit_id=account['unit_id'],
                    time_basis_id=account['period_id'], denominator_scope_id=None),
                source_refs=source_refs, assumption_refs=[]) for name, value in fields]
            trace_id = digest(dict(trace_schema=1, nodes=[m.node for m in members]))
            traces.append(CalculationTrace(id=trace_id, kind='node', members=members, mechanisms=[],
                effective_time=result.effective_time, dependency_refs=sorted(set(dependencies)), internal_edges=[]))
            for member in members:
                node_trace[tuple(member.node)] = trace_id
            return trace_id
        account_traces = {}
        # Final balances depend on the completed numerical allocation graph.
        used = {ref for trace in traces for ref in trace.dependency_refs}
        terminal = sorted(trace.id for trace in traces if trace.id not in used)
        barrier_id = digest(dict(trace_schema=1, finalization=True))
        traces.append(CalculationTrace(id=barrier_id, kind='node',
            members=[NodeObservation(node=['evaluation_result', 'finalization'], scope_id=None,
                entity_id=None, status='known', reason='retained_output_identity',
                value=LabelValue(kind='label', value=result.identities.output_digest),
                source_refs=[], assumption_refs=[])], mechanisms=[],
            effective_time=result.effective_time, dependency_refs=terminal, internal_edges=[]))
        graph_roots = [barrier_id]
        posting_traces = {key: [] for key in accounts}
        for posting in batch['postings']:
            account_id = posting['source_id'] or posting['destination_id']
            account = accounts[account_id]
            ref = final_trace('posting_result', posting['id'], [('amount', posting['amount'])],
                account, posting['source_refs'], graph_roots)
            for endpoint in (posting['source_id'], posting['destination_id']):
                if endpoint is not None:
                    posting_traces[endpoint].append(ref)
        for row in result.accounts.accounts:
            account = accounts[row.account_id]
            account_traces[row.account_id] = final_trace('account_result', row.account_id,
                [(name, getattr(row, name)) for name in ('closing', 'available', 'outstanding_reserved')],
                account, account['source_refs'], graph_roots + posting_traces[row.account_id])
        for row in result.accounts.claims:
            claim = claims[row.claim_id]
            account = accounts[claim['account_id']]
            dependencies = [account_traces[claim['account_id']]]
            mapping = mappings.get(row.claim_id)
            if mapping is not None:
                key = ('actual_consumption', mapping['instance_id'], mapping['claim_id'])
                if key in node_trace:
                    dependencies.append(node_trace[key])
            final_trace('claim_result', row.claim_id, [('actual', row.actual), ('unmet', row.unmet)],
                account, claim['source_refs'], dependencies)
    return sorted(traces, key=serialized), node_trace


def verify_report(report):
    report = MeasurementReport.model_validate_json(report.model_dump_json())
    from poliscope_engine.verification import contains, remember
    if contains('report', report):
        return report
    if digest(report.model_dump(mode='json', exclude={'report_digest'})) != report.report_digest:
        raise EvidenceError('report_identity_mismatch')
    remember('report', report)
    return report


def trace_page(report, query):
    """Context-bound, byte-bounded DAG pages. Root includes its transitive inputs."""
    report = verify_report(report)
    query = TraceQuery.model_validate_json(query.model_dump_json())
    if query.report_digest != report.report_digest:
        raise EvidenceError('stale_report')
    indexed = {t.id: t for t in report.traces}
    if len(indexed) != len(report.traces):
        raise EvidenceError('duplicate_trace_identity')
    if query.root_id is None:
        selected = set(indexed)
    else:
        if query.root_id not in indexed:
            raise EvidenceError('unknown_trace')
        selected, pending = set(), [query.root_id]
        while pending:
            node = pending.pop()
            if node in selected:
                continue
            if node not in indexed:
                raise EvidenceError('unavailable_trace_dependency')
            selected.add(node)
            pending.extend(indexed[node].dependency_refs)
    rows = [t for t in report.traces if t.id in selected]
    # Open the requested calculation before traversing its dependency closure.
    if query.root_id is not None:
        rows.sort(key=lambda t: t.id != query.root_id)
    scope = digest(dict(report=report.report_digest, root=query.root_id))
    offset = 0
    if query.cursor is not None:
        try:
            prefix, raw = query.cursor.rsplit(':', 1)
            offset = int(raw)
            if prefix != scope or str(offset) != raw or not 0 < offset < len(rows):
                raise ValueError()
        except ValueError as exc:
            raise EvidenceError('invalid_trace_cursor') from exc
    items = []
    end = offset
    for row in rows[offset:offset + query.limit]:
        candidate = dict(report_digest=report.report_digest, items=items + [row], next_cursor=scope + ':' + str(end + 1))
        if len(serialized(candidate).encode()) > 900000:
            if not items:
                raise EvidenceError('trace_node_requires_chunking')
            break
        items.append(row)
        end += 1
    return CalculationTracePage(report_digest=report.report_digest, items=items,
        next_cursor=scope + ':' + str(end) if end < len(rows) else None)


def _referenced(value):
    """Evidence references only; private payloads never enter through this API."""
    found = set()
    def visit(item):
        if isinstance(item, dict):
            for name, val in item.items():
                if name in ('source_refs', 'assumption_refs', 'supersedes_refs'):
                    found.update(('assumption' if name == 'assumption_refs' else 'source', ref) for ref in val)
                elif isinstance(val, (dict, list)):
                    visit(val)
        elif isinstance(item, list):
            for val in item:
                if isinstance(val, (dict, list)):
                    visit(val)
    visit(value)
    return found


def _reference_closure(evaluation, report, indexed):
    required = _referenced(report.model_dump(mode='json'))
    for snapshot in (evaluation.input_json, evaluation.model_json):
        key = sha256(snapshot.encode()).digest()
        refs = _reference_sets.get(key)
        if refs is None:
            refs = frozenset(_referenced(orjson.loads(snapshot)))
            _reference_sets.put(key, refs, len(repr(refs).encode()) + 32)
        required |= refs
    pending = list(required)
    while pending:
        key = pending.pop()
        if key not in indexed:
            continue
        linked = _referenced(indexed[key].model_dump(mode='json')) - required
        required |= linked
        pending.extend(linked)
    return required


def retain(evaluation, report, references=()):
    """Create a detached persistence-ready closure, never publish or write it.

    Only producer-approved simulation data belongs in EvaluationResult. The
    references catalog can classify private source/assumption metadata separately.
    Missing reference metadata is unavailable and private by default.
    """
    from poliscope_engine.measurements import verify_evaluation, observe
    from poliscope_engine.verification import contains, remember
    # A report just produced from these exact evaluation bytes already passed
    # the computation below. Changes to either member invalidate this proof.
    if not contains('observed', evaluation, report):
        evaluation = verify_evaluation(evaluation)
        report = verify_report(report)
        expected = observe(evaluation, report.definitions, report.goal_definitions)
        if expected != report:
            raise EvidenceError('report_evaluation_mismatch')
        remember('observed', evaluation, report)
    references = [EvidenceReference.model_validate_json(r.model_dump_json()) for r in references]
    indexed = {(r.kind, r.id): r for r in references}
    if len(indexed) != len(references):
        raise EvidenceError('duplicate_evidence_reference')
    required = _reference_closure(evaluation, report, indexed)
    for key in required - indexed.keys():
        kind, ref = key
        indexed[key] = EvidenceReference(id=ref, kind=kind, visibility='private', availability='unavailable', description=None)
    if indexed.keys() - required:
        raise EvidenceError('unreferenced_evidence_metadata')
    payload = dict(evidence_version=1, state='complete', evaluation=evaluation, report=report,
        references=[indexed[key] for key in sorted(indexed)])
    from poliscope_engine.evaluation.canonical import seal, remember_document
    _, text = seal(payload, 'closure_digest')
    saved = AcceptedEvidence.model_validate_json(text)
    remember_document(saved, text)
    from poliscope_engine.verification import remember
    remember('closure', saved)
    return saved


def unavailable():
    """Missing legacy evidence is a fact, never recalculated under today's model."""
    payload = dict(evidence_version=1, state='unavailable', evaluation=None, report=None, references=[])
    return AcceptedEvidence(**payload, closure_digest=digest(payload))


def read_retained(data):
    """Trusted data-only read with no registry, callback, cache or evaluator call."""
    saved = AcceptedEvidence.model_validate_json(data)
    from poliscope_engine.verification import contains, remember
    if contains('closure', saved):
        return saved
    if saved.closure_digest != digest(saved.model_dump(mode='json', exclude={'closure_digest'})):
        raise EvidenceError('closure_identity_mismatch')
    if saved.state == 'unavailable':
        if saved.evaluation is not None or saved.report is not None or saved.references:
            raise EvidenceError('invalid_unavailable_evidence')
        return saved
    if saved.evaluation is None or saved.report is None:
        raise EvidenceError('incomplete_accepted_evidence')
    # Verify identities and closure without recomputing historical measurements.
    from poliscope_engine.measurements import verify_evaluation
    verify_evaluation(saved.evaluation)
    verify_report(saved.report)
    if saved.report.physical_output_digest != saved.evaluation.identities.output_digest:
        raise EvidenceError('report_evaluation_mismatch')
    traces, _ = build_traces(saved.evaluation)
    if saved.report.traces != traces:
        raise EvidenceError('trace_closure_mismatch')
    required = _reference_closure(saved.evaluation, saved.report, {(r.kind, r.id): r for r in saved.references})
    refs = {(r.kind, r.id) for r in saved.references}
    if len(refs) != len(saved.references) or refs != required:
        raise EvidenceError('reference_closure_mismatch')
    remember('closure', saved)
    return saved


def public_projection(saved):
    """Explicitly public evidence only; private metadata/hashes are omitted.

    This projection excludes local input/model snapshots and all player goals.
    It has its own digest; the physical result identity remains an opaque identity
    of approved simulation data. Omitted references are marked by counts, never
    private-only IDs or hashes. It is not a complete portable save (WP-040).
    """
    saved = read_retained(saved.model_dump_json())
    if saved.state == 'unavailable':
        payload = dict(projection_version=1, state='unavailable', report=None, references=[], omitted_references=0)
    else:
        allowed = {(r.kind, r.id) for r in saved.references if r.visibility == 'public' and r.availability == 'available'}
        report = saved.report.model_dump(mode='json', exclude={'report_digest', 'goal_definitions', 'goals'})
        report['findings'] = [f for f in report['findings'] if f['category'] != 'player_target_observation']
        def redact(item):
            if isinstance(item, dict):
                return {k: ([ref for ref in v if ('assumption' if k == 'assumption_refs' else 'source', ref) in allowed]
                            if k in ('source_refs', 'assumption_refs', 'supersedes_refs') else redact(v)) for k, v in item.items()}
            if isinstance(item, list):
                return [redact(v) for v in item]
            return item
        report = redact(report)
        # Finding IDs include provenance; recalculate after redaction to avoid
        # exposing private-only hashes. Trace IDs depend only on simulation nodes.
        for finding in report['findings']:
            finding['id'] = digest({k: v for k, v in finding.items() if k != 'id'})
        payload = dict(projection_version=1, state='projected', report=report,
            references=[redact(r.model_dump(mode='json')) for r in saved.references if (r.kind, r.id) in allowed],
            omitted_references=len(saved.references) - len(allowed))
    payload['goals_included'] = False
    payload['input_snapshots_included'] = False
    from poliscope_engine.contracts.measurements import PublicEvidenceProjection
    return PublicEvidenceProjection.model_validate_json(serialized(dict(payload, projection_digest=digest(payload)))).model_dump(mode='json')
