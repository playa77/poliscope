"""Compose actual static adapters over canonical books and explicit conditions.

Local allocations remain independent input commitments. A requirement reports
whether an explicitly dependent use is ready; it never grants access, creates a
right, publishes a service, or assigns a social outcome to a capacity number.
"""
from typing import get_args
from poliscope_engine.accounts import AccountBook, fail
from poliscope_engine.contracts.mechanisms import Domain
from poliscope_engine.contracts.static_system import StaticSystemRequest, StaticSystemEvaluation
from poliscope_engine.domains.economy import evaluate_economy
from poliscope_engine.domains.governance import evaluate_governance
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.domains.social_organization import evaluate_care
from poliscope_engine.domains.knowledge_culture import evaluate_education
from poliscope_engine.domains.health import evaluate_health
from poliscope_engine.domains.infrastructure import evaluate_infrastructure
from poliscope_engine.domains.communication import evaluate_communication
from poliscope_engine.domains.environment import evaluate_environment
from poliscope_engine.domains.meaning_identity import evaluate_participation
from poliscope_engine.domains.security_risk import evaluate_continuity
from poliscope_engine.domains.provisioning.economy import (
    validate_context as validate_provisioning, evaluate_staged_chain)
from poliscope_engine.domains.provisioning.context import binding, policy_evidence, digest
from poliscope_engine.contracts.provisioning import ProvisioningEvaluation
from poliscope_engine.contracts.accounts import AccountBatch

DOMAINS = get_args(Domain)
POLICY = dict(governance=evaluate_governance, law_conflict=evaluate_adjudication,
              knowledge_culture=evaluate_education, health=evaluate_health)
SPATIAL = dict(social_organization=evaluate_care, infrastructure=evaluate_infrastructure,
               communication=evaluate_communication, environment=evaluate_environment,
               meaning_identity=evaluate_participation, security_risk=evaluate_continuity)


def work_request(domain, request):
    if domain == 'provisioning':
        return request.work
    if domain == 'economy':
        return request
    if domain in ('governance', 'law_conflict'):
        return request.administration
    if domain in ('social_organization', 'knowledge_culture', 'health'):
        return request.work
    return None


def books(domain, request):
    work = work_request(domain, request)
    if work is not None:
        yield 'work', work.batch, work
    else:
        yield 'capacity', request.batch, request
    if domain in ('knowledge_culture', 'health'):
        yield 'facility', request.facility_allocation.batch, request.facility_allocation
    # Provisioning's initial book must equal work; its staged chain is already
    # validated by the existing DOM-01/02 adapter, not a second initial budget.


def validate_context(request, graph, units):
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    if graph.registry.scope(request.scope_id).scope_kind not in ('settlement', 'region'):
        fail('invalid_static_system_scope')
    seen = {}
    holders = {}
    for domain in DOMAINS:
        node = getattr(request, domain)
        if node is None:
            continue
        scope = getattr(node, 'scope_id', request.scope_id)
        if scope != request.scope_id:
            fail('static_system_scope_mismatch')
        for kind, batch, procedure in books(domain, node):
            AccountBook(batch, units)
            period = getattr(procedure, 'period_id', request.period_id)
            if period != request.period_id:
                fail('static_system_period_mismatch')
            for account in batch.accounts:
                if entities.get(account.id) != 'account':
                    fail('static_system_account_identity')
                graph.registry.scope(account.scope_id)
                if account.period_id is not None and account.period_id != request.period_id:
                    fail('static_system_period_mismatch')
                # Sharing means the complete procedure, including all claims,
                # postings, holds, queue and holders, is identical. A subset or
                # a second copy of the same opening balance cannot spend twice.
                record = (kind, procedure.model_dump_json())
                if account.id in seen and seen[account.id] != record:
                    fail('static_system_competing_book')
                seen[account.id] = record
            for claim in batch.claims:
                if claim.claimant_id not in entities:
                    fail('static_system_claimant_identity')
            work = work_request(domain, node)
            if kind == 'work':
                for holder in work.holders:
                    if holder.role == 'time':
                        key = (holder.holder_id, work.period_id)
                        if key in holders and holders[key] != holder.account_id:
                            fail('static_system_duplicate_time')
                        holders[key] = holder.account_id
    for requirement in request.requirements:
        for ref in requirement.shared_references:
            if entities.get(ref.entity_id) != ref.entity_kind:
                fail('static_system_shared_identity')
            # A reference must actually occur in both endpoint requests. Catalog
            # anchors alone are not evidence that a real evaluator uses it.
            for domain in (requirement.source, requirement.target):
                if ref.entity_id not in entity_references(getattr(request, domain).model_dump(mode='json')):
                    fail('static_system_unused_reference')


ENTITY_FIELDS = frozenset(('entity_id', 'account_id', 'claimant_id', 'holder_id',
    'cohort_id', 'provider_id', 'beneficiary_id', 'authority_id', 'target_id',
    'resource_id', 'asset_id', 'facility_asset_id', 'institution_id', 'controller_id',
    'sender_id', 'recipient_id', 'member_id', 'group_id', 'arrangement_id',
    'source_id', 'destination_id', 'from_id', 'to_id', 'location_id', 'origin_id'))
ENTITY_LIST_FIELDS = frozenset(('entity_ids', 'account_refs', 'eligible_member_ids'))


def entity_references(value):
    """Canonical model inputs, excluding provenance/obligation strings and prose."""
    if isinstance(value, dict):
        refs = set()
        for key, item in value.items():
            if key in ENTITY_FIELDS and isinstance(item, str):
                refs.add(item)
            elif key in ENTITY_LIST_FIELDS and isinstance(item, list):
                refs.update(v for v in item if isinstance(v, str))
            else:
                refs.update(entity_references(item))
        # Canonical account definitions and care arrangements identify entities
        # in their own id field. Other ids name claims, cases or policies.
        if ({'id', 'opening', 'unit_id', 'invariant'} <= value.keys()
                or set(value) == {'id', 'scope_id', 'source_refs'}):
            refs.add(value['id'])
        return refs
    if isinstance(value, list):
        return set().union(*(entity_references(v) for v in value))
    return set()


def outcomes(domain, result):
    """Fixed semantic conversion; no caller-defined truth expression or code."""
    if domain == 'governance':
        return {result.request.proposal_binding_id: (
            'unresolved' if result.status != 'resolved' else
            'ready' if result.outcome == 'approved' else 'blocked')}
    if domain == 'provisioning':
        if result.accounts is None:
            return {'chain': 'unresolved'}
        phase_claims = {c.id for p in result.request.phases for c in p.claims}
        return {'chain': 'ready' if all(c.unmet == '0' for c in result.accounts.claims
            if c.claim_id in phase_claims) else 'blocked'}
    if domain == 'economy':
        if result.status != 'resolved':
            return {c.id: 'unresolved' for c in result.request.batch.claims}
        return {c.claim_id: 'ready' if c.unmet == '0' else 'blocked' for c in result.allocation.actuals}
    rows = {}
    for row in result.results:
        key = getattr(row, 'service_id', getattr(row, 'case_id', getattr(row, 'claim_id', None)))
        if key is None:
            fail('static_system_unmapped_result')
        if getattr(row, 'status', result.status) != 'resolved':
            rows[key] = 'unresolved'
        elif domain == 'social_organization':
            rows[key] = 'ready' if row.unmet == '0' else 'blocked'
        elif domain == 'law_conflict':
            rows[key] = 'ready' if row.outcome == 'upheld' else 'blocked'
        elif hasattr(row, 'outcome'):
            rows[key] = 'ready' if row.outcome == 'capacity_ready' else 'blocked'
        else:
            rows[key] = 'ready' if row.unmet == '0' else 'blocked'
    return rows


def candidate_batch(results, units):
    """One detached account snapshot, counting shared work exactly once.

    This is a private staged candidate. The ordinary revision service still owns
    durable publication. No candidate is available if any evaluator is unknown.
    """
    if any(result['status'] != 'resolved' for result in results.values()):
        return None, []
    from copy import deepcopy
    results = deepcopy(results)
    pools = {}
    for domain, result in results.items():
        if domain in ('provisioning', 'economy'):
            batches = [result['batch']]
        elif domain == 'governance':
            batches = [result['administration']['batch']]
        elif domain == 'law_conflict':
            batches = [result['administration']['evaluation']['batch']]
        elif domain == 'social_organization':
            batches = [result['work']['evaluation']['batch']]
        elif domain in ('knowledge_culture', 'health'):
            batches = [result['work']['evaluation']['batch'], result['facility_allocation']['batch']]
        else:
            batches = [result['allocation']['batch']]
        for batch in batches:
            if batch is None:
                return None, []
            key = frozenset(a['id'] for a in batch['accounts'])
            if key in pools:
                # Provisioning runs after the shared work allocation, closes its
                # earlier claims and retains all previous postings. Its final
                # book supersedes only that exact initial footprint.
                if pools[key][0] == 'provisioning':
                    continue
                if pools[key][1] != batch:
                    fail('static_system_divergent_allocation')
            pools[key] = (domain, batch)
    # Allocator posting IDs are local to each invocation. Preserve their exact
    # evidence in each domain report; give the combined private snapshot stable
    # pool-qualified identities to avoid unrelated allocation:0 collisions.
    origins = []
    for _, batch in pools.values():
        pool_id = sorted(a['id'] for a in batch['accounts'])
        for posting in batch['postings']:
            identity = 'static:' + digest(dict(pool=pool_id, posting_id=posting['id'])).removeprefix('sha256:')
            origins.append(dict(id=identity,original_id=posting['id'],account_ids=pool_id))
            posting['id'] = identity
    merged = dict(contract_version=1, **{field: [v for _, b in pools.values() for v in b[field]]
        for field in ('accounts', 'claims', 'postings', 'reservations', 'subtotals')})
    batch = AccountBatch.model_validate(merged)
    return AccountBook(batch, units).batch.model_dump(mode='json'), origins


def evaluate_system(request, *, graph, units, mechanisms):
    request = StaticSystemRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    if mechanisms.units != units:
        fail('static_system_policy_units')
    results, readiness = {}, {}
    for domain in DOMAINS:
        node = getattr(request, domain)
        if node is None:
            continue
        if domain == 'provisioning':
            validate_provisioning(node, graph, units, work_only=False)
            work = evaluate_economy(node.work, units)
            result = (ProvisioningEvaluation(contract_version=1, status='unresolved',
                request=node.chain, phases=[], blocked_phase_id=node.chain.phases[0].id,
                batch=None, accounts=None) if work.batch is None else
                evaluate_staged_chain(node, work.batch, units))
        elif domain == 'economy':
            result = evaluate_economy(node, units)
        elif domain in POLICY:
            result = POLICY[domain](node, graph=graph, units=units, mechanisms=mechanisms)
        else:
            result = SPATIAL[domain](node, graph=graph, units=units)
        results[domain] = result.model_dump(mode='json')
        readiness[domain] = outcomes(domain, result)
    original = {d: dict(v) for d, v in readiness.items()}
    for requirement in request.requirements:
        if (requirement.source_result_id not in readiness[requirement.source]
                or requirement.target_result_id not in readiness[requirement.target]):
            fail('static_system_unknown_result')
    # Monotone conjunction also handles cycles: a cycle cannot turn a blocked
    # or unknown prerequisite into readiness. No input ordering chooses a winner.
    for _ in range(sum(map(len, readiness.values())) + 1):
        previous = {d: dict(v) for d, v in readiness.items()}
        for r in request.requirements:
            target = readiness[r.target][r.target_result_id]
            source = readiness[r.source][r.source_result_id]
            readiness[r.target][r.target_result_id] = (
                'unresolved' if 'unresolved' in (target, source) else
                'blocked' if 'blocked' in (target, source) else 'ready')
        if previous == readiness:
            break
    evidence = [dict(id=r.id, source=r.source, target=r.target,
        source_result_id=r.source_result_id, target_result_id=r.target_result_id,
        status=readiness[r.source][r.source_result_id], obligation_ref=r.obligation_ref,
        shared_references=[v.model_dump(mode='json') for v in r.shared_references],
        source_refs=list(r.source_refs)) for r in request.requirements]
    snapshot, origins = candidate_batch(results, units)
    return StaticSystemEvaluation(contract_version=1, adapter_version='static-system-v1',
        baseline_digest=digest(dict(context=binding(request, graph, units,
            adapter='static-system-v1', model=('authored:static-system','v1')), policies=policy_evidence(mechanisms))),
        scope_id=request.scope_id, period_id=request.period_id,
        evidence_status='hypothetical', coverage_status='partial',
        status='unresolved' if any('unresolved' in v.values() for v in readiness.values()) else 'resolved',
        local_readiness=original, integrated_readiness=readiness,
        requirements=evidence, evaluations=results, candidate_batch=snapshot, posting_origins=origins,
        missing_effects=list(request.missing_effects), source_refs=list(request.source_refs)).model_dump(mode='json')
