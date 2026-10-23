"""Real finite response-slot commitments gate explicitly mapped chain claims."""
from poliscope_engine.accounts import fail, quantity
from poliscope_engine.contracts.provisioning_continuity import (
    ProvisioningContinuityRequest, ProvisioningContinuityEvaluation,
)
from poliscope_engine.domains.security_risk import evaluate_continuity
from .economy import evaluate_pair as evaluate_provisioning, validate_context as validate_economy_context
from .context import binding as context_binding

MODEL = ('authored:provisioning-continuity', 'v1')


def binding(request, graph, units):
    return context_binding(request, graph, units,
        adapter='provisioning-continuity-v1', model=MODEL)


def validate_context(request, graph, units):
    validate_economy_context(request.provisioning, graph, units)
    continuity = request.continuity
    chain = request.provisioning.chain
    if continuity.period_id != chain.period_id:
        fail('continuity_counterpart_period_mismatch')
    facility_ids = {x.id for group in (continuity.batch.accounts, continuity.batch.claims) for x in group}
    chain_ids = {x.id for group in (chain.batch.accounts, chain.batch.claims) for x in group}
    chain_ids.update(c.id for p in chain.phases for c in p.claims)
    if facility_ids & chain_ids:
        fail('continuity_counterpart_pool_collision')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    if any(entities.get(a.id) != 'account' for a in continuity.batch.accounts):
        fail('continuity_counterpart_account_identity')
    phases = {p.id: p for p in chain.phases}
    demands = {d.claim_id: d for d in continuity.demands}
    seen = set()
    for requirement in request.prerequisites:
        key = (requirement.phase_id, requirement.claim_id)
        phase = phases.get(requirement.phase_id)
        claim = next((c for c in phase.claims if c.id == requirement.claim_id), None) if phase else None
        if key in seen or claim is None or len(set(requirement.demand_ids)) != len(requirement.demand_ids):
            fail('invalid_continuity_counterpart_prerequisite')
        seen.add(key)
        if any(d not in demands for d in requirement.demand_ids):
            fail('unknown_continuity_counterpart_demand')
    # One declaration per phase claim, including explicit prerequisites for use.
    # An omitted gate cannot silently make a complete chain candidate.
    if seen != {(p.id, c.id) for p in chain.phases for c in p.claims}:
        fail('incomplete_continuity_counterpart_prerequisites')


def evaluate_pair(request, *, graph, units):
    request = ProvisioningContinuityRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    continuity = evaluate_continuity(request.continuity, graph=graph, units=units)
    provisioning = None
    if continuity.status == 'resolved':
        results = {r.claim_id: r for r in continuity.results}
        blocked = {(r.phase_id, r.claim_id) for r in request.prerequisites
            if any(results[d].findings or quantity(results[d].unmet) > 0 for d in r.demand_ids)}
        # Restrict existing host choices only. Response capacity never grants access,
        # removes an unknown, selects a route or fabricates a throughput conversion.
        staged_data = request.provisioning.model_dump()
        for phase in staged_data['chain']['phases']:
            for choice in (phase['routes'] if phase['kind'] == 'freight' else phase['choices']):
                if (phase['id'], choice['claim_id']) in blocked and choice['access'] != 'unknown':
                    choice['access'] = 'denied'
        for term in staged_data['use_terms']:
            for activity in term['activities']:
                if (term['phase_id'], activity['claim_id']) in blocked and activity['eligibility'] != 'unknown':
                    activity['eligibility'] = 'denied'
        staged = type(request.provisioning).model_validate(staged_data)
        provisioning = evaluate_provisioning(staged, graph=graph, units=units)
    resolved = provisioning is not None and provisioning.status == 'resolved'
    return ProvisioningContinuityEvaluation(contract_version=1,
        adapter_version='provisioning-continuity-v1', baseline_digest=binding(request, graph, units),
        evidence_status='hypothetical', status='resolved' if resolved else 'unresolved',
        request=request, continuity=continuity, provisioning=provisioning,
        batch=provisioning.batch if resolved else None)
