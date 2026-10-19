"""Pure finite allocation, staged atomically through the shared account book."""
from fractions import Fraction
from math import lcm, gcd
from poliscope_engine.accounts import AccountBook, index, quantity, fail
from poliscope_engine.contracts.accounts import AccountBatch, AccountPosting
from poliscope_engine.contracts.allocations import AllocationRequest, AllocationActual, AllocationEvaluation
from poliscope_engine.numeric import Registry, exact, canonical


def encoded(value):
    return canonical(exact(value))


def common_step(left, right):
    """Least positive quantity representable in both rational quantum lattices."""
    return Fraction(lcm(left.numerator, right.numerator), gcd(left.denominator, right.denominator))


def allocate(request: AllocationRequest, units: Registry) -> AllocationEvaluation:
    # Revalidate nested mutable DTOs/model_construct and detach caller data.
    request = AllocationRequest.model_validate_json(request.model_dump_json())
    base = AccountBook(request.batch, units)
    batch = base.batch
    initial = base.evaluate()
    definitions, claims = index(batch.accounts), index(batch.claims)
    choices = {choice.claim_id: choice for choice in request.choices}
    if len(choices) != len(request.choices) or set(choices) != set(claims):
        fail('invalid_choices')
    order = request.claim_order
    if order and (len(order) != len(set(order)) or set(order) != set(claims)):
        fail('invalid_claim_order')
    if request.procedure is not None and set(order) != set(claims):
        fail('invalid_claim_order')
    resources = {claim.account_id for claim in claims.values()}
    funding = {r.account_id for c in choices.values() for r in c.requirements}
    targets = {o.account_id for c in choices.values() for o in c.outputs}
    if resources & funding or targets & (resources | funding):
        fail('coupled_allocation_requires_solver')
    if not (funding | targets) <= set(definitions):
        fail('unknown_account')
    steps = {}
    for cid, choice in choices.items():
        source = definitions[claims[cid].account_id]
        step = quantity(source.quantum)
        quantity(choice.access_limit)
        if len({r.account_id for r in choice.requirements}) != len(choice.requirements):
            fail('duplicate_requirement')
        if len({o.account_id for o in choice.outputs}) != len(choice.outputs):
            fail('duplicate_output')
        for requirement in choice.requirements:
            account = definitions[requirement.account_id]
            rate = quantity(requirement.per_unit)
            if (rate <= 0 or account.invariant == 'physical'
                    or account.scope_id != source.scope_id
                    or (account.period_id != source.period_id
                        and not (source.kind == 'stock' and source.invariant == 'physical'
                                 and source.period_id is None
                                 and account.kind == 'capacity' and account.period_id is not None))):
                fail('incompatible_requirement')
            step = common_step(step, quantity(account.quantum) / rate)
        mass = quantity(choice.loss_per_unit)
        if choice.outputs or mass:
            if source.kind != 'stock' or source.invariant != 'physical':
                fail('invalid_transformation_input')
            source_unit = units.unit(source.unit_id)
            for output in choice.outputs:
                account = definitions[output.account_id]
                unit = units.unit(account.unit_id)
                rate = quantity(output.per_unit)
                if (rate <= 0 or unit.dimension != source_unit.dimension
                        or account.kind != source.kind or account.invariant != 'physical'
                        or account.scope_id != source.scope_id or account.period_id != source.period_id):
                    fail('incompatible_transformation_output')
                mass += rate * Fraction(unit.scale) / Fraction(source_unit.scale)
                step = common_step(step, quantity(account.quantum) / rate)
            if mass != 1:
                fail('transformation_conservation_failure')
        steps[cid] = step
    missing = []
    if request.procedure is None:
        missing.append('procedure')
    if any(c.access == 'unknown' for c in choices.values()):
        missing.append('access')
    if any(not c.funding_known for c in choices.values()):
        missing.append('funding')
    remaining = {r.claim_id: quantity(r.unmet) for r in initial.claims}
    if missing:
        # Unknown competitors cannot be silently skipped to favor known ones.
        return AllocationEvaluation(contract_version=1, status='unresolved', missing=missing,
            request=request, actuals=[AllocationActual(claim_id=cid, allocated='0',
                unmet=encoded(remaining[cid]), reason='unresolved', outputs=[], loss='0')
                for cid in sorted(claims)], batch=batch, accounts=initial)
    available = {a.account_id: quantity(a.available) for a in initial.accounts}
    fulfilled = {r.id: Fraction() for r in batch.reservations}
    for posting in batch.postings:
        if posting.reservation_id is not None:
            fulfilled[posting.reservation_id] += quantity(posting.amount)
    holds = {cid: [] for cid in claims}
    for reservation in sorted(batch.reservations, key=lambda r: r.id):
        holds[reservation.claim_id].append((reservation.id,
            quantity(reservation.amount) - fulfilled[reservation.id]))
    postings = list(batch.postings)
    used_ids = {item.id for group in (batch.accounts, batch.postings, batch.claims,
        batch.reservations, batch.subtotals) for item in group}
    serial = 0

    def post(choice, amount, kind, source, destination=None, claim=None, reservation=None):
        nonlocal serial
        if not amount:
            return
        while True:
            pid = f'allocation:{serial}'
            serial += 1
            if pid not in used_ids:
                break
        used_ids.add(pid)
        postings.append(AccountPosting(id=pid, kind=kind, source_id=source,
            destination_id=destination, amount=encoded(amount), claim_id=claim,
            reservation_id=reservation, mechanism_ref=choice.mechanism_ref,
            source_refs=choice.source_refs))

    actuals = []
    for cid in order:
        choice, claim = choices[cid], claims[cid]
        aid = claim.account_id
        own_hold = sum((amount for _, amount in holds[cid]), Fraction())
        cap = min(remaining[cid], quantity(choice.access_limit), available[aid] + own_hold)
        if choice.access == 'denied':
            cap = Fraction()
        for requirement in choice.requirements:
            cap = min(cap, available[requirement.account_id] / quantity(requirement.per_unit))
        # Only exact quantum multiples move. Unspent quantities stay in their
        # explicit source accounts, never disappear into rounding or consumption.
        amount = (cap // steps[cid]) * steps[cid]
        if request.procedure == 'all_or_nothing' and amount != remaining[cid]:
            amount = Fraction()
        left = amount
        for rid, hold in holds[cid]:
            take = min(left, hold)
            post(choice, take, 'use', aid, claim=cid, reservation=rid)
            left -= take
        post(choice, left, 'use', aid, claim=cid)
        available[aid] -= left
        for requirement in choice.requirements:
            debit = amount * quantity(requirement.per_unit)
            post(choice, debit, 'use', requirement.account_id)
            available[requirement.account_id] -= debit
        outputs = []
        for output in choice.outputs:
            value = amount * quantity(output.per_unit)
            post(choice, value, 'production', None, output.account_id)
            outputs.append(encoded(value))
        actuals.append(AllocationActual(claim_id=cid, allocated=encoded(amount),
            unmet=encoded(remaining[cid] - amount),
            reason='denied' if choice.access == 'denied' else
                   'satisfied' if amount == remaining[cid] else 'limited',
            outputs=outputs, loss=encoded(amount * quantity(choice.loss_per_unit))))
    candidate = AccountBatch.model_validate(batch.model_dump() | {'postings': postings})
    final = AccountBook(candidate, units).evaluate()
    return AllocationEvaluation(contract_version=1, status='resolved', missing=[],
        request=request, actuals=sorted(actuals, key=lambda a: a.claim_id), batch=candidate, accounts=final)
