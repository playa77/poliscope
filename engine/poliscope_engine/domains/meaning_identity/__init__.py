"""Pure accommodation eligibility/obligation and shared finite capacity procedure."""
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.allocations import AllocationChoice, AllocationRequest
from poliscope_engine.contracts.meaning_identity import (
    ParticipationRequest, ParticipationEvaluation, ParticipationReadiness,
)


def evaluate_participation(request, *, graph, units):
    request = ParticipationRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    relationships = {r.id: r for r in graph.relationships}
    if request.scope_id not in scopes or scopes[request.scope_id].scope_kind not in ('settlement', 'region'):
        fail('invalid_participation_scope')
    accounts, claims = index(request.batch.accounts), index(request.batch.claims)
    facilities = {f.asset_id: f for f in request.facilities}
    demands = {d.claim_id: d for d in request.demands}
    account_ids = [f.account_id for f in request.facilities]
    if (len(facilities) != len(request.facilities) or len(set(account_ids)) != len(account_ids)
            or set(account_ids) != set(accounts)):
        fail('duplicate_or_unmapped_participation_capacity')
    if len(demands) != len(request.demands) or set(demands) != set(claims):
        fail('invalid_participation_demands')

    def entity(eid, kind):
        if eid not in entities or entities[eid].entity_kind != kind:
            fail('invalid_participation_entity')

    for facility in request.facilities:
        entity(facility.asset_id, 'asset')
        entity(facility.institution_id, 'institution')
        rel = relationships.get(facility.ownership_relationship_id)
        if (rel is None or rel.relationship_kind != 'ownership'
                or rel.from_id != facility.institution_id or rel.to_id != facility.asset_id):
            fail('invalid_participation_authority')
    for account in accounts.values():
        if (account.kind != 'capacity' or account.invariant != 'budget'
                or account.scope_id != request.scope_id or account.period_id != request.period_id
                or units.unit(account.unit_id).dimension != (('participation_slot', 1),)):
            fail('invalid_participation_capacity')
    if len({a.unit_id for a in accounts.values()}) != 1:
        fail('incompatible_participation_units')

    choices, findings_by_claim = [], {}
    for demand in request.demands:
        entity(demand.group_id, 'population_cohort')
        claim = claims[demand.claim_id]
        facility = facilities.get(demand.facility_asset_id)
        if (facility is None or claim.account_id != facility.account_id
                or claim.claimant_id != demand.group_id or quantity(claim.requested) <= 0):
            fail('invalid_participation_claim')
        reachable = demand.access_relationship_id is not None
        if reachable:
            rel = relationships.get(demand.access_relationship_id)
            if (rel is None or rel.relationship_kind != 'access'
                    or rel.from_id != demand.group_id or rel.to_id != facility.asset_id):
                fail('invalid_participation_access_reference')
        if demand.obligation_status != 'compatible' and not demand.obligation_refs:
            fail('missing_participation_obligation_reference')
        findings = [] if reachable else ['no_declared_access']
        unknown = False
        for name, value, allowed in [
            ('participation', demand.participation, 'requested'),
            ('eligibility', demand.eligibility, 'eligible'),
            ('access', demand.access, 'allowed'),
            ('obligation', demand.obligation_status, 'compatible'),
            ('facility', facility.availability, 'operating'),
        ]:
            if value == 'unknown':
                unknown = True
                findings.append('unknown_' + name)
            elif value != allowed:
                findings.append(name + '_' + value)
        # A declared conflict requires resolution by the host; capacity cannot
        # silently resolve conflicting obligations or select a civic answer.
        if demand.obligation_status == 'conflict':
            unknown = True
        findings_by_claim[claim.id] = findings
        choices.append(AllocationChoice(claim_id=claim.id,
            access='unknown' if unknown else 'denied' if findings else 'allowed',
            access_limit=demand.access_limit, funding_known=True, requirements=[],
            outputs=[], loss_per_unit='0', mechanism_ref=request.mechanism_ref,
            source_refs=demand.source_refs))
    initial = AccountBook(request.batch, units).evaluate()
    prior = {r.claim_id: r.actual for r in initial.claims}
    remaining = {r.claim_id: quantity(r.unmet) for r in initial.claims}
    allocation = allocate(AllocationRequest(contract_version=1, batch=request.batch,
        procedure=request.procedure, claim_order=request.claim_order, choices=choices,
        mechanism_ref=request.mechanism_ref, source_refs=request.source_refs), units)
    actuals = {a.claim_id: a for a in allocation.actuals}
    unresolved = allocation.status == 'unresolved'
    results = []
    for demand in request.demands:
        actual = actuals[demand.claim_id]
        findings = list(findings_by_claim[demand.claim_id])
        if unresolved:
            findings.append('unresolved_capacity_allocation')
        elif quantity(actual.unmet) > 0 and not findings:
            if quantity(demand.access_limit) < remaining[demand.claim_id]:
                findings.append('access_limit_shortfall')
            if (quantity(actual.allocated) < min(remaining[demand.claim_id], quantity(demand.access_limit))
                    and not (request.procedure == 'all_or_nothing'
                             and quantity(demand.access_limit) < remaining[demand.claim_id])):
                findings.append('capacity_shortfall')
        results.append(ParticipationReadiness(claim_id=demand.claim_id,
            outcome='unresolved' if unresolved else 'blocked' if findings else 'capacity_ready',
            findings=findings, prior=prior[demand.claim_id],
            additional=None if unresolved else actual.allocated, unmet=None if unresolved else actual.unmet))
    return ParticipationEvaluation(contract_version=1, evidence_status='hypothetical',
        status=allocation.status, request=request, allocation=allocation, results=results)
