"""Actual finite facility/path reach gates explicit economic prerequisites."""
from poliscope_engine.accounts import fail, quantity
from poliscope_engine.contracts.economy_infrastructure import (
    EconomyInfrastructureRequest, EconomyInfrastructureEvaluation,
)
from poliscope_engine.domains.infrastructure import evaluate_infrastructure
from ..provisioning.context import binding as context_binding
from . import evaluate_economy, compile_choices

MODEL = ('authored:economy-infrastructure', 'v1')


def binding(request, graph, units):
    return context_binding(request, graph, units,
        adapter='economy-infrastructure-v1', model=MODEL)


def validate_context(request, graph, units):
    infrastructure, work = request.infrastructure, request.economy
    if infrastructure.period_id != work.period_id:
        fail('infrastructure_counterpart_period_mismatch')
    facility_ids = {x.id for group in (infrastructure.batch.accounts, infrastructure.batch.claims) for x in group}
    economy_ids = {x.id for group in (work.batch.accounts, work.batch.claims) for x in group}
    if facility_ids & economy_ids:
        fail('infrastructure_counterpart_pool_collision')
    entities = {e.id: e.entity_kind for e in graph.registry.entities}
    scopes = {s.id: s.scope_kind for s in graph.registry.scopes}
    for account in [*infrastructure.batch.accounts, *work.batch.accounts]:
        if entities.get(account.id) != 'account':
            fail('counterpart_account_identity')
        if scopes.get(account.scope_id) not in ('settlement', 'region'):
            fail('counterpart_scope_identity')
        if account.period_id is not None and account.period_id != work.period_id:
            fail('counterpart_period_mismatch')
    time_accounts = {a.id for a in work.batch.accounts
                     if units.unit(a.unit_id).dimension == (('time', 1),)}
    if time_accounts != {h.account_id for h in work.holders if h.role == 'time'}:
        fail('counterpart_time_holders')
    if any(entities.get(h.holder_id) != 'population_cohort' for h in work.holders):
        fail('counterpart_holder_identity')
    if any(entities.get(c.claimant_id) != 'population_cohort' for c in work.batch.claims):
        fail('counterpart_claimant_identity')
    # Validate original terms even when facility inputs are unresolved. The pure
    # preflight is discarded; no detached allocation becomes the candidate.
    compile_choices(work, units)
    claims = {c.id: c for c in work.batch.claims}
    accounts = {a.id: a for a in work.batch.accounts}
    demands = {d.claim_id: d for d in infrastructure.demands}
    facility_claims = {c.id: c for c in infrastructure.batch.claims}
    seen = set()
    for requirement in request.prerequisites:
        claim = claims.get(requirement.claim_id)
        if (claim is None or claim.id in seen
                or len(set(requirement.demand_ids)) != len(requirement.demand_ids)):
            fail('invalid_infrastructure_counterpart_prerequisite')
        seen.add(claim.id)
        for did in requirement.demand_ids:
            if did not in demands or did not in facility_claims:
                fail('unknown_infrastructure_counterpart_demand')
            if (facility_claims[did].claimant_id != claim.claimant_id
                    or accounts[claim.account_id].scope_id != infrastructure.scope_id):
                fail('infrastructure_counterpart_claim_context')
    if seen != set(claims):
        fail('incomplete_infrastructure_counterpart_prerequisites')


def evaluate_pair(request, *, graph, units):
    request = EconomyInfrastructureRequest.model_validate_json(request.model_dump_json())
    validate_context(request, graph, units)
    infrastructure = evaluate_infrastructure(request.infrastructure, graph=graph, units=units)
    economy = None
    if infrastructure.status == 'resolved':
        results = {r.claim_id: r for r in infrastructure.results}
        blocked = {r.claim_id for r in request.prerequisites
                   if any(results[d].findings or quantity(results[d].unmet) > 0 for d in r.demand_ids)}
        data = request.economy.model_dump()
        for activity in data['activities']:
            # Reach restricts, never grants access or removes independent unknowns.
            if activity['claim_id'] in blocked and activity['eligibility'] != 'unknown':
                activity['eligibility'] = 'denied'
        staged = type(request.economy).model_validate(data)
        economy = evaluate_economy(staged, units)
    resolved = economy is not None and economy.status == 'resolved'
    return EconomyInfrastructureEvaluation(contract_version=1,
        adapter_version='economy-infrastructure-v1', baseline_digest=binding(request, graph, units),
        evidence_status='hypothetical', status='resolved' if resolved else 'unresolved',
        request=request, infrastructure=infrastructure, economy=economy,
        batch=economy.batch if resolved else None)
