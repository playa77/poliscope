"""Pure facility reach: explicit paths, canonical assets, one finite account book."""
from poliscope_engine.accounts import AccountBook, index, quantity, fail
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.allocations import AllocationChoice, AllocationRequest, FundingRequirement
from poliscope_engine.contracts.infrastructure import InfrastructureRequest, InfrastructureEvaluation, FacilityReachResult


def evaluate_infrastructure(request, *, graph, units):
    request = InfrastructureRequest.model_validate_json(request.model_dump_json())
    entities = {e.id: e for e in graph.registry.entities}
    scopes = {s.id: s for s in graph.registry.scopes}
    relationships = {r.id: r for r in graph.relationships}
    if request.scope_id not in scopes or scopes[request.scope_id].scope_kind not in ('settlement', 'region'):
        fail('invalid_infrastructure_scope')
    accounts, claims = index(request.batch.accounts), index(request.batch.claims)
    facilities = {f.asset_id: f for f in request.facilities}
    links = {l.asset_id: l for l in request.links}
    demands = {d.claim_id: d for d in request.demands}
    if len(demands) != len(request.demands) or set(demands) != set(claims):
        fail('invalid_infrastructure_demands')
    mapped = [x.account_id for x in [*request.facilities, *request.links]]
    if (len(facilities) != len(request.facilities) or len(links) != len(request.links)
            or set(facilities) & set(links) or len(mapped) != len(set(mapped))
            or set(mapped) != set(accounts)):
        fail('duplicate_or_unmapped_infrastructure_capacity')
    if len({l.relationship_id for l in request.links}) != len(request.links):
        fail('duplicate_infrastructure_connectivity')
    unit_ids = set()

    def entity(eid, kind):
        if eid not in entities or entities[eid].entity_kind != kind:
            fail('invalid_infrastructure_entity')

    for item in [*request.facilities, *request.links]:
        entity(item.asset_id, 'asset')
        account = accounts[item.account_id]
        if (account.kind != 'capacity' or account.invariant != 'budget'
                or account.period_id != request.period_id or account.scope_id != request.scope_id
                or units.unit(account.unit_id).dimension != (('facility_slot', 1),)):
            fail('invalid_infrastructure_capacity')
        unit_ids.add(account.unit_id)
    # One-to-one slot use; conversions and heterogeneous network quantities need
    # a separately specified mechanism, never a dimension-only scale assumption.
    if len(unit_ids) != 1:
        fail('incompatible_infrastructure_units')
    for facility in request.facilities:
        entity(facility.location_id, 'location')
        rel = relationships.get(facility.location_relationship_id)
        if (rel is None or rel.relationship_kind != 'containment'
                or rel.from_id != facility.asset_id or rel.to_id != facility.location_id):
            fail('invalid_infrastructure_location')
    adjacency = {}
    for link in request.links:
        entity(link.from_id, 'location'); entity(link.to_id, 'location')
        rel = relationships.get(link.relationship_id)
        if (link.from_id == link.to_id or rel is None or rel.relationship_kind != 'connectivity'
                or rel.from_id != link.from_id or rel.to_id != link.to_id):
            fail('invalid_infrastructure_connectivity')
        adjacency.setdefault(link.from_id, set()).add(link.to_id)

    def connected(origin, target):
        seen, pending = set(), [origin]
        while pending:
            node = pending.pop()
            if node == target:
                return True
            if node not in seen:
                seen.add(node); pending.extend(adjacency.get(node, set()) - seen)
        return False

    choices, findings_by_claim = [], {}
    for demand in request.demands:
        claim = claims[demand.claim_id]
        entity(claim.claimant_id, 'population_cohort'); entity(demand.origin_id, 'location')
        facility = facilities.get(demand.facility_asset_id)
        if facility is None or claim.account_id != facility.account_id or quantity(claim.requested) <= 0:
            fail('invalid_infrastructure_facility_claim')
        path, node, visited = [], demand.origin_id, {demand.origin_id}
        for lid in demand.path:
            link = links.get(lid)
            if link is None or link.from_id != node or link.to_id in visited:
                fail('invalid_infrastructure_path')
            path.append(link); node = link.to_id; visited.add(node)
        reachable = node == facility.location_id
        if not reachable and (path or connected(demand.origin_id, facility.location_id)):
            fail('incomplete_infrastructure_path')
        findings = [] if reachable else ['disconnected']
        assets = [facility, *path]
        if any(a.availability in ('planned', 'offline', 'retired') for a in assets):
            findings.append('nonoperating_asset')
        if any(a.availability == 'unknown' for a in assets):
            findings.append('unknown_asset_availability')
        if demand.access == 'denied':
            findings.append('access_denied')
        findings_by_claim[demand.claim_id] = findings
        # Unknown input stays unknown even when another prerequisite blocks use.
        access = ('unknown' if demand.access == 'unknown' or 'unknown_asset_availability' in findings else
                  'denied' if findings else 'allowed')
        choices.append(AllocationChoice(claim_id=demand.claim_id, access=access,
            access_limit=demand.access_limit, funding_known=True,
            requirements=[FundingRequirement(account_id=l.account_id, per_unit='1', kind='funding') for l in path],
            outputs=[], loss_per_unit='0', mechanism_ref=request.mechanism_ref,
            source_refs=demand.source_refs))
    initial = AccountBook(request.batch, units).evaluate()
    prior = {r.claim_id: r.actual for r in initial.claims}
    allocation = allocate(AllocationRequest(contract_version=1, batch=request.batch,
        procedure=request.procedure, claim_order=request.claim_order, choices=choices,
        mechanism_ref=request.mechanism_ref, source_refs=request.source_refs), units)
    actuals = {a.claim_id: a for a in allocation.actuals}
    results = []
    for demand in request.demands:
        claim, actual = claims[demand.claim_id], actuals[demand.claim_id]
        facility = facilities[demand.facility_asset_id]
        findings = list(findings_by_claim[demand.claim_id])
        if allocation.status == 'unresolved':
            findings.append('unknown_capacity_allocation')
        elif quantity(actual.unmet) > 0 and not findings:
            findings.append('capacity_shortfall')
        results.append(FacilityReachResult(claim_id=claim.id, claimant_id=claim.claimant_id,
            facility_asset_id=facility.asset_id, account_id=facility.account_id,
            origin_id=demand.origin_id, destination_id=facility.location_id, path=demand.path,
            scope_id=request.scope_id, period_id=request.period_id, unit_id=accounts[claim.account_id].unit_id,
            status=allocation.status, findings=findings, requested=claim.requested, prior=prior[claim.id],
            additional=actual.allocated if allocation.status == 'resolved' else None,
            unmet=actual.unmet if allocation.status == 'resolved' else None))
    return InfrastructureEvaluation(contract_version=1, evidence_status='hypothetical',
        status=allocation.status, request=request, allocation=allocation, results=results)
