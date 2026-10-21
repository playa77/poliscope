"""Pure access/work procedures over canonical shared accounts; no IO or clock."""
from poliscope_engine.accounts import AccountBook, fail, index, quantity
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.allocations import AllocationChoice, AllocationRequest
from poliscope_engine.contracts.economy import EconomyRequest, EconomyEvaluation


def _evaluate(request, units):
    request = EconomyRequest.model_validate_json(request.model_dump_json())
    batch = AccountBook(request.batch, units).batch
    accounts, claims = index(batch.accounts), index(batch.claims)
    activities = {a.claim_id: a for a in request.activities}
    if len(activities) != len(request.activities) or set(activities) != set(claims):
        fail('invalid_economy_activities')
    holders = {h.account_id: h for h in request.holders}
    if len(holders) != len(request.holders):
        fail('duplicate_economy_holder')
    time_owners = set()
    for aid, holder in holders.items():
        account = accounts.get(aid)
        if account is None:
            fail('unknown_account')
        if account.invariant == 'physical':
            fail('invalid_economy_budget')
        if account.period_id is not None and account.period_id != request.period_id:
            fail('incompatible_economy_period')
        if holder.role == 'time':
            if (account.kind != 'capacity' or account.invariant != 'budget'
                    or account.period_id != request.period_id
                    or units.unit(account.unit_id).dimension != (('time', 1),)):
                fail('invalid_economy_time')
            # One canonical budget per cohort in the selected period, even across
            # geographic scopes. Disjoint cohorts need distinct canonical IDs.
            if holder.holder_id in time_owners:
                fail('duplicate_cohort_time_budget')
            time_owners.add(holder.holder_id)
    choices = []
    for cid, activity in activities.items():
        claim = claims[cid]
        source = accounts[claim.account_id]
        quantity(activity.access_limit)
        if activity.kind == 'goods':
            if (source.kind != 'stock' or source.invariant != 'physical'
                    or source.period_id is not None):
                fail('invalid_economy_goods')
        else:
            owner = holders.get(source.id)
            if owner is None or owner.role != 'time' or owner.holder_id != claim.claimant_id:
                fail('invalid_economy_time_owner')
        for term in activity.requirements:
            holder = holders.get(term.account_id)
            if (holder is None or holder.holder_id != claim.claimant_id
                    or holder.role != term.kind):
                fail('invalid_economy_term_holder')
        choices.append(AllocationChoice(claim_id=cid, access=activity.eligibility,
            access_limit=activity.access_limit, funding_known=activity.terms_known,
            requirements=activity.requirements, outputs=[], loss_per_unit='0',
            mechanism_ref=activity.mechanism_ref, source_refs=activity.source_refs))
    # Validate scope, rates, lattice, complete order and coupling through the one
    # allocator. Returning choices never publishes its staged result.
    allocation = allocate(AllocationRequest(contract_version=1, batch=batch,
        procedure=request.procedure, claim_order=request.claim_order, choices=choices,
        mechanism_ref=request.mechanism_ref, source_refs=request.source_refs), units)
    return request, allocation


def compile_choices(request, units):
    """Validate terms and return choices consumable by DOM-01 use phases.

    Host inputs must identify canonical accounts and reviewed terms. This does
    not grant rights, activate a model, choose precedence or publish the preview.
    Recompile/revalidate against the actual phase batch before host use.
    """
    return _evaluate(request, units)[1].request.choices


def evaluate_economy(request, units):
    request, allocation = _evaluate(request, units)
    return EconomyEvaluation(contract_version=1, status=allocation.status,
        request=request, allocation=allocation,
        batch=allocation.batch if allocation.status == 'resolved' else None)
