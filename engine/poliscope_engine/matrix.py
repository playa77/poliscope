"""Sparse projections over explicit catalog links and accepted execution evidence.

No callbacks, numerical recomputation, inferred links or Cartesian choice space.
"""
from collections import Counter, defaultdict
from itertools import product
import json
from typing import get_args
from poliscope_engine import atlas
from poliscope_engine.contracts.matrix import MatrixQuery, MatrixEndpoint, MatrixRelationship, MatrixCell, MatrixPage
from poliscope_engine.contracts.mechanisms import Domain
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.evaluation.identity import digest, serialized

DOMAINS = {name: f'society:domain/{i:02}' for i, name in enumerate(get_args(Domain), 1)}


def bounded_id(identity):
    return identity if len(identity) <= 256 else digest(identity)


def compound(parts):
    return bounded_id('/'.join(p.replace('%', '%25').replace('/', '%2F') for p in parts))


def endpoint(identity, label=None, **tags):
    return MatrixEndpoint(id=bounded_id(identity), label=((label or identity).split('\n')[0].strip() or identity)[:256],
        **{k: sorted(set(tags.get(k, []))) for k in ('domains', 'branches', 'decisions', 'alternatives', 'scopes')})


def relationships(service, record, scope, saved, release):
    """Yield recorded relationships once; unresolved endpoints remain inspectable."""
    definitions, packs = atlas.catalogs(release)
    rows = atlas.entries(service, record, scope, release)
    endpoints, choice_queries = {}, {}
    for row in rows:
        selected_key = compound([row.question.id, row.selected_id]) if row.selected_id else None
        for definition in [row.question, *row.options]:
            # Proposal IDs are local to their question, not global identities.
            key = compound([row.question.id, definition.id])
            endpoints[(row.question.id, definition.id)] = endpoint(key, definition.original_text,
                domains=row.domain_refs, branches=row.branch_refs, decisions=[row.question.id],
                alternatives=[selected_key] if selected_key and (definition.kind == 'question' or definition.id == row.selected_id) else [], scopes=[scope])
            choice_queries[key] = row.interview
    source_ids = {s.reference.id for p in packs for s in p.sources}
    def inspect(collection, identity):
        return dict(context=record.context, scope_id=scope, collection=collection, item_id=identity,
                    cursor=None, all_scopes=True)
    def edge(kind, a, b, *, provenance='documentary', coverage='unmodeled', activation='documentary',
             explanation, mechanisms=(), rules=(), sources=(), inspectors=(), magnitude=None, salt=None):
        queries = {serialized(choice_queries[e.id]): choice_queries[e.id] for e in (a, b) if choice_queries.get(e.id)}
        return MatrixRelationship(id=digest([kind, a.id, b.id, provenance, salt]), relationship_type=kind,
            row=a, column=b, provenance=provenance, coverage=coverage, activation=activation,
            magnitude=magnitude, explanation=explanation, mechanism_refs=sorted(set(mechanisms)), rule_refs=sorted(set(rules)),
            interviews=list(queries.values()), sources=[dict(context=record.context, source_ref=s) for s in sorted(set(sources) & source_ids)],
            inspectors=[*inspectors, *[inspect('references', s) for s in sorted(set(sources)) if any(r.id == s for r in saved.references)]][:100])
    # Supersession retains its documentary direction: new definition -> old.
    for row in rows:
        for definition in [row.question, *row.options]:
            a = endpoints[(row.question.id, definition.id)]
            for target in sorted(set(definition.supersedes_refs)):
                matches = [e for (q, d), e in endpoints.items() if d == target]
                b = matches[0] if len(matches) == 1 else endpoint(target)
                yield edge('supersedes', a, b, explanation='Documentary supersession; source adoption does not activate a player policy or causal dependency.', sources=definition.source_refs)
            for target in sorted(set(definition.mechanism_refs)):
                yield edge('influences', a, endpoint(target), explanation='Documented mechanism reference only; model activation and causal strength are not established by source prose.', sources=definition.source_refs)

    execution = record.inputs.design.execution
    instances = {i.id: i for i in execution.dependencies.instances}
    evaluation, report = saved.evaluation, saved.report
    declarations = {d['id']: d for d in json.loads(evaluation.model_json)['definitions']} if evaluation else {}
    accounts = {a.id: a for a in execution.batch.accounts} if execution.batch else {}
    node_traces = defaultdict(list)
    if report:
        for trace in report.traces:
            for member in trace.members:
                node_traces[tuple(member.node)].append(trace.id)
    observations = {tuple(o.node): o for o in evaluation.observations} if evaluation else {}
    def node(key):
        instance = instances.get(key[1]) if key[0] in ('input', 'output', 'claim', 'actual_consumption') else None
        account = accounts.get(key[1]) if key[0] in ('account', 'account_result') else None
        declaration = declarations.get(instance.mechanism_id, {}) if instance else {}
        return endpoint('node:' + compound(key), label='node:' + '/'.join(key), domains=[DOMAINS[declaration['domain']]] if declaration else [],
            scopes=[instance.scope_id] if instance else [account.scope_id] if account else [])
    def links(keys):
        result = {}
        for key in keys:
            for trace in node_traces[tuple(key)]:
                result[('traces', trace)] = inspect('traces', trace)
            if key[0] in ('account', 'account_result') and key[1] in accounts and evaluation and evaluation.accounts and report:
                result[('accounts', key[1])] = inspect('accounts', key[1])
                for member, traces in node_traces.items():
                    if member[:2] == ('account_result', key[1]):
                        for trace in traces:
                            result[('traces', trace)] = inspect('traces', trace)
        return list(result.values())
    if evaluation:
        for link in evaluation.trace_edges:
            a, b = link.source, link.target
            kind = 'supplies' if a[0] == 'output' and b[0] in ('input', 'account') else 'requires'
            # Requires is consumer -> prerequisite. Supplies is producer -> recipient.
            left, right = (a, b) if kind == 'supplies' else (b, a)
            statuses = [observations[tuple(k)].status for k in (a, b) if tuple(k) in observations]
            coverage = next((s for s in ('conflict', 'solver_failure', 'missing_input', 'unmodeled', 'partial', 'not_applicable') if s in statuses), 'known')
            mechanisms = [instances[k[1]].mechanism_id for k in (a, b) if k[0] in ('input', 'output', 'claim', 'actual_consumption') and k[1] in instances]
            sources = [s for k in (a, b) for s in (observations[tuple(k)].source_refs if tuple(k) in observations else [])]
            yield edge(kind, node(left), node(right), provenance='retained_execution', coverage=coverage,
                activation='observed' if coverage in ('known', 'partial') else 'unavailable', mechanisms=mechanisms,
                explanation='Retained solver dependency. Requires points from consumer to prerequisite; supplies from producer to recipient. Count is not strength; inspect the trace for exact node values and coverage.',
                sources=sources, inspectors=links((a, b)))
    if evaluation and evaluation.final_batch_json and report:
        final = AccountBatch.model_validate_json(evaluation.final_batch_json)
        for posting in final.postings:
            source = accounts.get(posting.source_id)
            destination = accounts.get(posting.destination_id)
            account = source or destination
            a = node(['account', source.id]) if source else endpoint('external:' + posting.id, scopes=[account.scope_id])
            b = node(['account', destination.id]) if destination else endpoint('use:' + posting.id, scopes=[account.scope_id])
            yield edge('supplies', a, b, provenance='retained_execution', coverage='known', activation='observed',
                magnitude=dict(kind='quantity', value=posting.amount, unit_id=account.unit_id, time_basis_id=account.period_id, denominator_scope_id=None),
                mechanisms=[posting.mechanism_ref], sources=posting.source_refs,
                inspectors=links([['account', x.id] for x in (source, destination) if x]), salt=posting.id,
                explanation=f'Retained account posting {posting.id} ({posting.kind}). Exact posted quantity is separate from relationship count; this is a local account transfer, not a strength-of-effect score.')
    for relation in execution.dependencies.relationships:
        a, b = instances[relation.source_instance_id], instances[relation.target_instance_id]
        yield edge('influences', node(['output', a.id]), node(['input', b.id]),
            provenance='documentary' if relation.kind == 'documentary' else 'model',
            activation='documentary' if relation.kind == 'documentary' else 'declared',
            mechanisms=[a.mechanism_id, b.mechanism_id], rules=[relation.relationship_ref], salt=relation.relationship_ref,
            explanation=f'Explicit {relation.kind} context link; excluded from the numerical dependency graph. No causal effect is inferred.')
    # A star records membership in a shared allocation pool in linear space.
    # It does not fabricate pairwise conflicts or imply that demand exceeds supply.
    pools = Counter(c.account_id for c in execution.dependencies.claims)
    for claim in execution.dependencies.claims:
        if pools[claim.account_id] < 2:
            continue
        key = ['claim', claim.instance_id, claim.claim_id]
        yield edge('competes', node(key), node(['account', claim.account_id]), provenance='model', activation='declared',
            mechanisms=[instances[claim.instance_id].mechanism_id], rules=[claim.allocation_id],
            explanation='Claim participates in this shared finite account allocation pool. Pool membership records competition, not an inferred shortage or pairwise incompatibility.', inspectors=links((key, ['account', claim.account_id])))
    policies = {p.id: p for p in record.inputs.design.policies}
    if evaluation:
        for result in evaluation.policies.results:
            if result.status != 'conflict':
                continue
            # Finding -> participant star preserves conflict grouping without n² pairs.
            hub = endpoint('conflict:' + digest([result.entity_id, result.parameter_id]), scopes=sorted({policies[p].scope_id for p in result.participant_ids}))
            for identity in result.participant_ids:
                policy = policies[identity]
                definition = declarations.get(policy.mechanism.id)
                a = endpoint('policy:' + identity, domains=[DOMAINS[definition['domain']]] if definition else [], scopes=[policy.scope_id], decisions=policy.choice_refs)
                yield edge('conflicts', a, hub, provenance='retained_execution', coverage='conflict', activation='observed',
                    mechanisms=[policy.mechanism.id], rules=[r.identity.id for r in record.inputs.design.policy_rules if identity in r.participant_ids],
                    explanation='Retained unresolved policy conflict group; no implicit winning authority. Inspect the policy and findings for affected accounts and required resolution.',
                    sources=result.source_refs, inspectors=[inspect('policies', identity), *links([['account', a] for a in policy.account_refs]), *[inspect('findings', f.id) for f in (report.findings if report else []) if f.category == 'institutional_gap']][:100], salt=[result.entity_id, result.parameter_id])
    for binding in record.inputs.design.world_inputs:
        value = next(v for v in record.inputs.values if v.id == binding.value_id)
        if value.partition != 'conditions':
            continue
        yield edge('requires', node(['input', binding.consumer.instance_id, binding.consumer.port_id]),
            endpoint('condition:' + value.id, scopes=[value.scope_id]), provenance='model', activation='declared',
            explanation='Explicit current-condition binding; quantities are read from the retained revision, never inferred from source prose.',
            mechanisms=[instances[binding.consumer.instance_id].mechanism_id], sources=value.provenance.source_refs,
            inspectors=[inspect('conditions', value.id)])

    # Canonical world edges are declarations, not inferred causal effects.
    labels = {e.id: e.label for e in record.inputs.entities} | {s.id: s.label for s in record.inputs.scopes}
    entity_scopes = defaultdict(set)
    for value in record.inputs.values:
        entity_scopes[value.entity_id].add(value.scope_id)
    for relation in record.inputs.relationships:
        if relation.aggregation.kind != 'non_aggregating':
            entity_scopes[relation.from_id].add(relation.to_id)
    scope_ids = {s.id for s in record.inputs.scopes}
    def world_endpoint(identity):
        return endpoint(compound(['world', identity]), labels.get(identity, identity),
            scopes=[identity] if identity in scope_ids else sorted(entity_scopes[identity]))
    for relation in record.inputs.relationships:
        kind = {'supplies': 'supplies', 'consumes': 'requires', 'access': 'requires'}.get(relation.relationship_kind, 'influences')
        details = [inspect('conditions', v.id) for v in record.inputs.values
                   if v.entity_id in (relation.from_id, relation.to_id) and (v.partition == 'conditions' or
                       v.property_id == 'world:relationship:' + digest(relation.id).split(':')[-1][:40])][:100]
        account_ids = {a.id for a in execution.batch.accounts} if execution.batch else set()
        details += [inspect('accounts', i) for i in (relation.from_id, relation.to_id) if i in account_ids]
        item = edge(kind, world_endpoint(relation.from_id), world_endpoint(relation.to_id),
            provenance='documentary', activation='declared',
            explanation=f'Canonical {relation.relationship_kind} {relation.id} version {relation.relationship_version}: {relation.from_id} → {relation.to_id}. Empty scope tags mean scope is unspecified. This is a declared world relationship, not proof of fulfillment, causal effect or deliverable capacity.',
            inspectors=details[:100], sources=relation.provenance.source_refs, salt=relation.id)
        yield item.model_copy(update={'world_refs': list(dict.fromkeys([relation.from_id, relation.to_id]))})


def groups(e, axis):
    return getattr(e, {'domain': 'domains', 'branch': 'branches', 'decision': 'decisions', 'scope': 'scopes', 'selected_alternative': 'alternatives'}[axis]) or ['unmapped']


def page(service, data, *, release=None):
    query = MatrixQuery.model_validate(data)
    record = service.read(query.context)
    if query.scope_id not in {s.id for s in record.inputs.scopes}:
        raise ValueError('unknown_scope')
    saved = service.evidence(query.context)
    release = release or atlas.bundled_release()
    prefix = digest(dict(query=query.model_dump(exclude={'cursor', 'detail_cursor'}), evidence=saved.closure_digest, catalog=release.digest))
    def offset(token, kind):
        if token is None:
            return 0
        bound, marker, raw = token.rsplit(':', 2)
        number = int(raw)
        if bound != prefix or marker != kind or str(number) != raw or number <= 0:
            raise ValueError('invalid_matrix_cursor')
        return number
    cell_offset, detail_offset = offset(query.cursor, 'c'), offset(query.detail_cursor, 'd')
    counts, details, count, unmapped = Counter(), [], 0, 0
    for relation in relationships(service, record, query.scope_id, saved, release):
        # Cross-scope edges remain visible when either endpoint is in this scope.
        if query.scope_id not in set(relation.row.scopes + relation.column.scopes) and not (
                relation.world_refs and not (relation.row.scopes or relation.column.scopes)):
            continue
        if query.relationship_type and query.relationship_type != relation.relationship_type:
            continue
        if query.provenance != 'any' and query.provenance != relation.provenance:
            continue
        if query.axis == 'selected_alternative' and not (relation.row.alternatives or relation.column.alternatives):
            continue
        matched, unresolved = False, False
        for a, b in product(groups(relation.row, query.axis), groups(relation.column, query.axis)):
            if query.row_id is not None and a != query.row_id or query.column_id is not None and b != query.column_id:
                continue
            matched = True
            unresolved |= a == 'unmapped' or b == 'unmapped'
            counts[(a, b, relation.relationship_type, relation.provenance, relation.activation, relation.coverage)] += 1
            if len(counts) > 100000:
                raise ValueError('matrix_group_budget_exhausted')
        if not matched:
            continue
        unmapped += unresolved
        if detail_offset <= count < detail_offset + 10:
            details.append(relation)
        count += 1
    keys = sorted(counts)
    if cell_offset and cell_offset >= len(keys) or detail_offset and detail_offset >= count:
        raise ValueError('invalid_matrix_offset')
    cells = [MatrixCell(row_id=k[0], column_id=k[1], relationship_type=k[2], provenance=k[3], activation=k[4], coverage=k[5], count=counts[k]) for k in keys[cell_offset:cell_offset+25]]
    def cursor(end, total, kind):
        return f'{prefix}:{kind}:{end}' if end < total else None
    reply = MatrixPage(matrix_contract=1, query=query, versions=record.inputs.versions, effective_time=record.inputs.design.effective_time,
        catalog_digest=release.digest, evidence_digest=saved.closure_digest, evidence_state=saved.state,
        cells=cells, relationships=details, cell_total=len(keys), relationship_total=count, unmapped_count=unmapped,
        next_cursor=cursor(cell_offset+len(cells), len(keys), 'c'), detail_next_cursor=cursor(detail_offset+len(details), count, 'd'))
    if len(reply.model_dump_json().encode()) > 900000:
        raise ValueError('matrix_page_requires_chunking')
    return reply


def model(service, data):
    """Inspect only the selected revision's retained data, never load code."""
    from poliscope_engine.contracts.matrix import MatrixModelQuery, MatrixModelReply
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    query = MatrixModelQuery.model_validate(data)
    record, saved = service.read(query.context), service.evidence(query.context)
    mechanism, policy, allocation, condition = None, None, None, None
    if query.kind == 'mechanism' and saved.evaluation:
        candidates = [MechanismDefinition.model_validate(d) for d in json.loads(saved.evaluation.model_json)['definitions']
            if d['id'] == query.identity and (query.version is None or d['version'] == query.version)]
        mechanism = candidates[0] if len(candidates) == 1 else None
    elif query.kind == 'rule' and query.version is None:
        policy = next((r for r in record.inputs.design.policy_rules if r.identity.id == query.identity), None)
        allocation = next((r for r in record.inputs.design.execution.allocations if r.id == query.identity), None)
        condition = next((r for r in record.inputs.design.conditions if r.identity.id == query.identity), None)
    graphs = []
    if mechanism and saved.evaluation:
        from poliscope_engine.contracts.expressions import ExpressionGraph
        references = [s.implementation for s in (mechanism.support.static, mechanism.support.transition) if s and s.kind == 'declarative_graph']
        graphs = [ExpressionGraph.model_validate(g) for g in json.loads(saved.evaluation.model_json).get('graphs', [])
            if any((g['id'], g['version']) == (r.id, r.version) for r in references)]
    return MatrixModelReply(expression_graphs=graphs, matrix_contract=1, query=query, status='retained' if any((mechanism, policy, allocation, condition)) else 'unavailable',
        mechanism=mechanism, policy_rule=policy, allocation_rule=allocation, condition_rule=condition)
