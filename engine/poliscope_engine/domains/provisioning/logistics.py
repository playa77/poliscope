"""Pure static freight staging with paired, exact cross-scope postings.

The host selects reviewed routes, resource bindings, capacity accounts and order.
This adapter validates accounting and does not grant model/content authority.
"""
from fractions import Fraction
from poliscope_engine.accounts import AccountBook, index, quantity, fail
from poliscope_engine.allocations import allocate, encoded
from poliscope_engine.contracts.accounts import AccountBatch, AccountPosting
from poliscope_engine.contracts.allocations import AllocationRequest, AllocationChoice, FundingRequirement
from poliscope_engine.contracts.logistics import LogisticsRequest, LogisticsEvaluation, TransportActual


def transport(request, units):
    request = LogisticsRequest.model_validate_json(request.model_dump_json())
    batch = AccountBook(request.batch, units).batch
    accounts, claims = index(batch.accounts), index(batch.claims)
    routes = {r.claim_id: r for r in request.routes}
    resources = {r.account_id: r.resource_id for r in request.resources}
    if len(routes) != len(request.routes) or set(routes) != set(claims):
        fail('invalid_routes')
    if len(resources) != len(request.resources) or not set(resources) <= set(accounts):
        fail('invalid_resource_bindings')
    sources = {c.account_id for c in claims.values()}
    destinations = {r.destination_id for r in routes.values()}
    if sources & destinations:
        # No hidden same-pass transshipment, circular production or route solver.
        fail('coupled_transport_requires_solver')
    choices = []
    for cid, route in routes.items():
        source = accounts[claims[cid].account_id]
        destination = accounts.get(route.destination_id)
        capacity = accounts.get(route.capacity_id)
        if destination is None or capacity is None:
            fail('unknown_account')
        if (source.kind != 'stock' or destination.kind != 'stock'
                or source.invariant != 'physical' or destination.invariant != 'physical'
                or source.period_id is not None or destination.period_id is not None
                or source.scope_id == destination.scope_id
                or source.unit_id != destination.unit_id
                or quantity(source.quantum) != quantity(destination.quantum)):
            fail('incompatible_transport_stock')
        if (source.id not in resources or destination.id not in resources
                or resources[source.id] != resources[destination.id]):
            fail('transport_resource_mismatch')
        if (capacity.kind != 'capacity' or capacity.invariant != 'budget'
                or capacity.period_id != request.period_id or capacity.scope_id != source.scope_id
                or units.unit(capacity.unit_id).dimension != units.unit(source.unit_id).dimension
                or quantity(route.capacity_per_unit) <= 0):
            fail('invalid_transport_capacity')
        for requirement in route.requirements:
            account = accounts.get(requirement.account_id)
            if account is None:
                fail('unknown_account')
            if account.period_id != request.period_id:
                fail('incompatible_transport_period')
        # Requirements are serialized by the shared allocator, including a single
        # canonical capacity/crew budget reused by several routes.
        requirements = [FundingRequirement(account_id=capacity.id,
            per_unit=route.capacity_per_unit, kind='funding'), *route.requirements]
        choices.append(AllocationChoice(claim_id=cid, access=route.access,
            access_limit=route.access_limit, funding_known=route.funding_known,
            requirements=requirements, outputs=[], loss_per_unit='0',
            mechanism_ref=route.mechanism_ref, source_refs=route.source_refs))
    allocation = allocate(AllocationRequest(contract_version=1, batch=batch,
        procedure=request.procedure, claim_order=request.claim_order, choices=choices,
        mechanism_ref=request.mechanism_ref, source_refs=request.source_refs), units)
    # Only new fulfillment postings belong to this transport. Existing imports,
    # prior actuals, holds and other stock uses must never be mirrored again.
    original = {p.id for p in batch.postings}
    postings = list(allocation.batch.postings)
    used = {v.id for group in (batch.accounts, postings, batch.claims,
        batch.reservations, batch.subtotals) for v in group}
    movements = []
    serial = 0
    for actual in allocation.actuals:
        cid = actual.claim_id
        route, claim = routes[cid], claims[cid]
        exports = []
        exported = Fraction()
        for i, posting in enumerate(postings):
            if posting.id not in original and posting.claim_id == cid:
                exports.append(posting.id)
                exported += quantity(posting.amount)
                postings[i] = posting.model_copy(update={'kind': 'export'})
        if exported != quantity(actual.allocated):
            fail('transport_conservation_failure')
        import_id = None
        if exported:
            while f'transport:{serial}' in used:
                serial += 1
            import_id = f'transport:{serial}'
            used.add(import_id)
            serial += 1
            postings.append(AccountPosting(id=import_id, kind='import', source_id=None,
                destination_id=route.destination_id, amount=encoded(exported),
                claim_id=None, reservation_id=None, mechanism_ref=route.mechanism_ref,
                source_refs=route.source_refs))
        movements.append(TransportActual(claim_id=cid, source_id=claim.account_id,
            destination_id=route.destination_id, resource_id=resources[claim.account_id],
            delivered=encoded(exported), export_posting_ids=exports,
            import_posting_id=import_id, mechanism_ref=route.mechanism_ref,
            source_refs=route.source_refs))
    candidate = AccountBatch.model_validate(allocation.batch.model_dump() | {'postings': postings})
    final = AccountBook(candidate, units).evaluate()
    return LogisticsEvaluation(contract_version=1, request=request, allocation=allocation,
        movements=movements, batch=candidate, accounts=final)
