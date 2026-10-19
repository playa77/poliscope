"""Pure materialization of solved actuals. No precedence, allocation or IO."""
from fractions import Fraction
from poliscope_engine.contracts.accounts import AccountBatch, AccountEvaluation, AccountResult, ClaimResult
from poliscope_engine.numeric import AccountPolicy, Registry, parse, exact, canonical


class AccountError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def fail(code):
    raise AccountError(code)


def index(items):
    result = {item.id: item for item in items}
    if len(result) != len(items):
        fail('duplicate_identity')
    return result


def quantity(value):
    result = Fraction(parse(value))
    if result < 0:
        fail('negative_quantity')
    return result


def signature(account):
    return account.kind, account.unit_id, account.scope_id, account.period_id, account.invariant


class AccountBook:
    """Snapshot inputs; every query/result is detached from the private source.

    The host supplies canonical IDs, reviewed mechanism outputs and unit registry.
    This checks accounting, not mechanism authorization or scientific validity.
    """
    __slots__ = ('_snapshot', '_units')

    def __init__(self, batch: AccountBatch, units: Registry):
        batch = AccountBatch.model_validate_json(batch.model_dump_json())
        # Validate the entire candidate before retaining it. No partial results.
        self._snapshot = batch.model_dump_json()
        self._units = Registry(tuple(units.units))
        self.evaluate()

    @property
    def batch(self):
        return AccountBatch.model_validate_json(self._snapshot)

    def evaluate(self) -> AccountEvaluation:
        batch = self.batch
        accounts, postings, claims, reservations, subtotals = map(index, (
            batch.accounts, batch.postings, batch.claims, batch.reservations, batch.subtotals))
        groups = (accounts, postings, claims, reservations, subtotals)
        all_ids = [key for group in groups for key in group]
        if len(all_ids) != len(set(all_ids)):
            fail('duplicate_identity')
        policies, opening, closing = {}, {}, {}
        for aid, account in accounts.items():
            unit = self._units.unit(account.unit_id)
            if unit.kind != account.kind:
                fail('incompatible_account_kind')
            policy = AccountPolicy(parse(account.quantum), parse(account.maximum), 'reject')
            policy.count(parse(account.opening))
            policies[aid] = policy
            opening[aid] = quantity(account.opening)
            closing[aid] = opening[aid]
        requested, actual, held, fulfilled = {}, {}, {}, {}
        for cid, claim in claims.items():
            if claim.account_id not in accounts:
                fail('unknown_account')
            requested[cid], actual[cid] = quantity(claim.requested), Fraction()
        for rid, reservation in reservations.items():
            claim = claims.get(reservation.claim_id)
            if claim is None or claim.account_id != reservation.account_id:
                fail('incompatible_reservation')
            held[rid], fulfilled[rid] = quantity(reservation.amount), Fraction()
            policies[reservation.account_id].count(exact(held[rid]))
        reserved_by_claim = {cid: Fraction() for cid in claims}
        for rid, reservation in reservations.items():
            reserved_by_claim[reservation.claim_id] += held[rid]
        if any(reserved_by_claim[cid] > requested[cid] for cid in claims):
            fail('reservation_exceeds_claim')
        refs = {aid: [] for aid in accounts}
        inflows = {aid: Fraction() for aid in accounts}
        outflows = {aid: Fraction() for aid in accounts}
        for pid, posting in postings.items():
            amount = quantity(posting.amount)
            endpoints = [aid for aid in (posting.source_id, posting.destination_id) if aid is not None]
            if any(aid not in accounts for aid in endpoints):
                fail('unknown_account')
            if len(endpoints) == 2 and signature(accounts[endpoints[0]]) != signature(accounts[endpoints[1]]):
                fail('incompatible_transfer')
            for aid in endpoints:
                # Nonzero movements must themselves be representable in both
                # endpoint quanta. Rounded postings require explicit residuals.
                policies[aid].count(exact(amount))
                refs[aid].append(pid)
            if posting.source_id is not None:
                closing[posting.source_id] -= amount
                outflows[posting.source_id] += amount
            if posting.destination_id is not None:
                closing[posting.destination_id] += amount
                inflows[posting.destination_id] += amount
            if posting.claim_id is not None:
                claim = claims.get(posting.claim_id)
                if claim is None or claim.account_id != posting.source_id:
                    fail('incompatible_claim')
                actual[posting.claim_id] += amount
            if posting.reservation_id is not None:
                reservation = reservations.get(posting.reservation_id)
                if (reservation is None or reservation.account_id != posting.source_id
                        or reservation.claim_id != posting.claim_id):
                    fail('incompatible_reservation')
                fulfilled[posting.reservation_id] += amount
        for rid in reservations:
            if fulfilled[rid] > held[rid]:
                fail('reservation_exceeded')
        if any(actual[cid] > requested[cid] for cid in claims):
            fail('claim_exceeded')
        for cid in claims:
            remaining_hold = sum((held[rid] - fulfilled[rid] for rid, reservation in reservations.items()
                                  if reservation.claim_id == cid), Fraction())
            if actual[cid] + remaining_hold > requested[cid]:
                fail('reservation_exceeds_unmet')
        outstanding = {aid: Fraction() for aid in accounts}
        for rid, reservation in reservations.items():
            outstanding[reservation.account_id] += held[rid] - fulfilled[rid]
        results = []
        for aid in sorted(accounts):
            if closing[aid] < 0:
                fail('insufficient_balance')
            policies[aid].count(exact(closing[aid]))
            available = closing[aid] - outstanding[aid]
            if available < 0:
                fail('reservation_unfunded')
            if opening[aid] + inflows[aid] != closing[aid] + outflows[aid]:
                fail('conservation_failure')
            results.append(AccountResult(account_id=aid, closing=canonical(exact(closing[aid])),
                outstanding_reserved=canonical(exact(outstanding[aid])),
                available=canonical(exact(available)), posting_ids=sorted(refs[aid])))
        self._leaves(batch)
        return AccountEvaluation(contract_version=1, accounts=results,
            claims=[ClaimResult(claim_id=cid, actual=canonical(exact(actual[cid])),
                                unmet=canonical(exact(requested[cid] - actual[cid])))
                    for cid in sorted(claims)])

    @staticmethod
    def _leaves(batch):
        accounts = index(batch.accounts)
        pending = index(batch.subtotals)
        leaves = {aid: frozenset([aid]) for aid in accounts}
        while pending:
            progress = False
            for sid, subtotal in list(pending.items()):
                if len(set(subtotal.member_ids)) != len(subtotal.member_ids):
                    fail('duplicate_subtotal_member')
                if any(mid not in accounts and mid not in leaves and mid not in pending for mid in subtotal.member_ids):
                    fail('unknown_subtotal_member')
                if any(mid not in leaves for mid in subtotal.member_ids):
                    continue
                combined = set()
                for mid in subtotal.member_ids:
                    if combined & leaves[mid]:
                        fail('overlapping_subtotal')
                    combined.update(leaves[mid])
                if len({signature(accounts[aid]) for aid in combined}) != 1:
                    fail('incompatible_subtotal')
                leaves[sid] = frozenset(combined)
                del pending[sid]
                progress = True
            if not progress:
                fail('subtotal_cycle')
        return leaves

    def total(self, member_ids: tuple[str, ...]) -> str:
        """Sum closing balances once; reject overlapping selections."""
        if type(member_ids) is not tuple or not 1 <= len(member_ids) <= 1000:
            fail('invalid_selection')
        leaves = self._leaves(self.batch)
        selected = set()
        for mid in member_ids:
            if mid not in leaves:
                fail('unknown_subtotal_member')
            if selected & leaves[mid]:
                fail('overlapping_subtotal')
            selected.update(leaves[mid])
        accounts = index(self.batch.accounts)
        if len({signature(accounts[aid]) for aid in selected}) != 1:
            fail('incompatible_subtotal')
        values = {item.account_id: quantity(item.closing) for item in self.evaluate().accounts}
        return canonical(exact(sum((values[aid] for aid in selected), Fraction())))
