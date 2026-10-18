"""Pure authoritative arithmetic; callers publish staged results transactionally.

Decimal inputs are exact. Every operation uses a fresh context; Fraction and
integer quantum counts check representability/conservation independently.
"""
from dataclasses import dataclass
from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext, InvalidOperation, DivisionByZero, Overflow, Underflow
from fractions import Fraction
import re
from typing import Literal

RUNTIME_ID = 'decimal28-half-even-exact-v1'
# Identity fixes precision, rounding, +/-256 adjusted exponent, plain canonical
# encoding (scientific when plain exceeds 256 chars), strict 256-char input,
# exact conversions and quantum rules.
_PATTERN = re.compile(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?')


class NumericError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def context() -> Context:
    return Context(prec=28, rounding=ROUND_HALF_EVEN, Emin=-256, Emax=256,
                   capitals=1, clamp=0, flags=[],
                   traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def _checked(value: Decimal) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise NumericError('invalid_decimal')
    if value and not -256 <= value.adjusted() <= 256:
        raise NumericError('precision_unsupported')
    # Bound exponent as well as adjusted exponent to prevent tiny trailing zeros
    # or zeros from causing unbounded integer/canonical allocations.
    if not -512 <= value.as_tuple().exponent <= 256:
        raise NumericError('precision_unsupported')
    try:
        with localcontext(context()):
            rounded = +value
    except DecimalException as exc:
        raise NumericError('precision_unsupported') from exc
    if rounded != value:
        raise NumericError('precision_unsupported')
    return value


def parse(value: str) -> Decimal:
    if type(value) is not str or len(value) > 256 or not _PATTERN.fullmatch(value):
        raise NumericError('invalid_decimal')
    try:
        return _checked(Decimal(value))
    except DecimalException as exc:
        raise NumericError('invalid_decimal') from exc


def canonical(value: Decimal) -> str:
    _checked(value)
    if not value:
        return '0'
    encoded = format(value, 'f')
    encoded = encoded.rstrip('0').rstrip('.') if '.' in encoded else encoded
    if len(encoded) <= 256:
        return encoded
    sign, digits, exponent = value.as_tuple()
    coefficient = ''.join(map(str, digits)).rstrip('0')
    mantissa = coefficient[0] + ('.' + coefficient[1:] if len(coefficient) > 1 else '')
    return ('-' if sign else '') + mantissa + 'e' + str(value.adjusted())


def exact(value: Fraction) -> Decimal:
    """Reject results that cannot be represented exactly in the runtime."""
    try:
        with localcontext(context()):
            result = Decimal(value.numerator) / Decimal(value.denominator)
    except DecimalException as exc:
        raise NumericError('precision_unsupported') from exc
    _checked(result)
    if Fraction(result) != value:
        raise NumericError('precision_unsupported')
    return result


def calculate(left: Decimal, right: Decimal, operation: Literal['add', 'subtract', 'multiply', 'divide']) -> Decimal:
    a, b = Fraction(_checked(left)), Fraction(_checked(right))
    if operation == 'divide' and not b:
        raise NumericError('invalid_denominator')
    oracles = {'add': lambda: a + b, 'subtract': lambda: a - b,
               'multiply': lambda: a * b, 'divide': lambda: a / b}
    if operation not in oracles:
        raise NumericError('unknown_operation')
    try:
        with localcontext(context()):
            if operation == 'add':
                result = left + right
            elif operation == 'subtract':
                result = left - right
            elif operation == 'multiply':
                result = left * right
            else:
                result = left / right
    except DecimalException as exc:
        raise NumericError('precision_unsupported') from exc
    _checked(result)
    if Fraction(result) != oracles[operation]():
        raise NumericError('precision_unsupported')
    return result


def display(value: Decimal, places: int) -> str:
    """Presentation only. Never feed this rounded string into account mutation."""
    _checked(value)
    if type(places) is not int or not 0 <= places <= 28:
        raise NumericError('invalid_display_precision')
    # Display can contain more digits than authoritative precision (large stock
    # plus fixed fractional places). Its context is deliberately separate.
    with localcontext(Context(prec=600, rounding=ROUND_HALF_EVEN, Emin=-999, Emax=999,
                              capitals=1, clamp=0, flags=[], traps=[InvalidOperation])):
        return format(value.quantize(Decimal((0, (1,), -places))), 'f')


Dimension = tuple[tuple[str, int], ...]
Kind = Literal['stock', 'flow', 'capacity', 'count', 'time', 'entitlement', 'money', 'indicator']
_KINDS = {'stock', 'flow', 'capacity', 'count', 'time', 'entitlement', 'money', 'indicator'}


@dataclass(frozen=True)
class Unit:
    id: str
    dimension: Dimension
    kind: Kind
    scale: Decimal

    def __post_init__(self):
        if (not self.id or self.kind not in _KINDS or type(self.dimension) is not tuple
                or any(type(pair) is not tuple or len(pair) != 2
                       or type(pair[0]) is not str or not pair[0]
                       or type(pair[1]) is not int or pair[1] == 0 for pair in self.dimension)
                or tuple(sorted(self.dimension)) != self.dimension
                or len(dict(self.dimension)) != len(self.dimension)):
            raise NumericError('invalid_unit')
        if _checked(self.scale) <= 0:
            raise NumericError('invalid_unit_scale')


@dataclass(frozen=True)
class TimeBasis:
    id: str
    seconds: Decimal

    def __post_init__(self):
        if not self.id or _checked(self.seconds) <= 0:
            raise NumericError('invalid_time_basis')


@dataclass(frozen=True)
class Population:
    id: str
    scope_id: str
    count: Decimal

    def __post_init__(self):
        if not self.id or not self.scope_id or _checked(self.count) <= 0:
            raise NumericError('invalid_denominator')


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit_id: str
    scope_id: str
    time_basis: TimeBasis | None = None
    population: Population | None = None

    def __post_init__(self):
        _checked(self.value)
        if not self.unit_id or not self.scope_id:
            raise NumericError('invalid_quantity')
        if self.population and self.population.scope_id != self.scope_id:
            raise NumericError('incompatible_scope')


@dataclass(frozen=True)
class Registry:
    """Frozen definitions; extend by constructing a new versioned registry."""
    units: tuple[Unit, ...]

    def __post_init__(self):
        if type(self.units) is not tuple or len({u.id for u in self.units}) != len(self.units):
            raise NumericError('duplicate_unit')

    def unit(self, unit_id: str) -> Unit:
        for unit in self.units:
            if unit.id == unit_id:
                return unit
        raise NumericError('unknown_unit')

    def convert(self, quantity: Quantity, target_id: str, *,
                time_basis: TimeBasis | None = None,
                population: Population | None = None,
                scope_id: str | None = None) -> Quantity:
        source, target = self.unit(quantity.unit_id), self.unit(target_id)
        if source.dimension != target.dimension or source.kind != target.kind:
            raise NumericError('incompatible_unit')
        scope = quantity.scope_id if scope_id is None else scope_id
        # Spatial aggregation needs explicit world membership/weights (WP-007).
        if scope != quantity.scope_id or (population and population.scope_id != scope):
            raise NumericError('incompatible_scope')
        if bool(time_basis) != bool(quantity.time_basis):
            raise NumericError('incompatible_time_basis')
        if source.kind in {'flow', 'capacity'} and time_basis is None:
            raise NumericError('invalid_time_basis')
        if source.kind not in {'flow', 'capacity', 'indicator'} and time_basis is not None:
            raise NumericError('invalid_time_basis')
        value = Fraction(quantity.value) * Fraction(source.scale) / Fraction(target.scale)
        if time_basis is not None:
            value *= Fraction(time_basis.seconds) / Fraction(quantity.time_basis.seconds)
        # Population references are explicit observed/assumed counts, never an
        # implicit equal distribution or a second copy of world population.
        if quantity.population:
            value *= Fraction(quantity.population.count)
        if population:
            value /= Fraction(population.count)
        return Quantity(exact(value), target_id, scope, time_basis, population)


@dataclass(frozen=True)
class Quantized:
    posted: Decimal
    residual: Decimal


@dataclass(frozen=True)
class AccountPolicy:
    quantum: Decimal
    maximum: Decimal
    residual_rule: Literal['reject', 'retain']

    def __post_init__(self):
        q, m = _checked(self.quantum), _checked(self.maximum)
        # Power-of-ten quantum and at most 28 integer quantum digits ensure all
        # points in the declared range have exact runtime representations.
        if (q <= 0 or m <= 0 or self.residual_rule not in {'reject', 'retain'}
                or Fraction(q) != Fraction(Decimal(1).scaleb(q.adjusted(), context=context()))):
            raise NumericError('invalid_account_policy')
        count = Fraction(m) / Fraction(q)
        if count.denominator != 1 or count >= 10**28:
            raise NumericError('precision_unsupported')

    def count(self, value: Decimal) -> int:
        _checked(value)
        count = Fraction(value) / Fraction(self.quantum)
        if value < 0 or value > self.maximum or count.denominator != 1:
            raise NumericError('invalid_balance')
        return count.numerator

    def quantize(self, value: Decimal) -> Quantized:
        _checked(value)
        if value < 0 or value > self.maximum:
            raise NumericError('invalid_transfer')
        ratio = Fraction(value) / Fraction(self.quantum)
        # Fraction.__round__ uses exact nearest/half-even, independently of the
        # Decimal context and without rounding large quantum counts first.
        posted = exact(round(ratio) * Fraction(self.quantum))
        residual = exact(Fraction(value) - Fraction(posted))
        self.count(posted)
        if residual and self.residual_rule == 'reject':
            raise NumericError('residual_required')
        return Quantized(posted, residual)


@dataclass(frozen=True)
class Balance:
    id: str
    unit_id: str
    scope_id: str
    policy: AccountPolicy
    value: Decimal

    def __post_init__(self):
        if not self.id or not self.unit_id or not self.scope_id:
            raise NumericError('invalid_account')
        self.policy.count(self.value)


@dataclass(frozen=True)
class Transfer:
    source: Balance
    destination: Balance
    posted: Decimal
    residual: Decimal
    residual_account: Balance | None


def stage_transfer(source: Balance, destination: Balance, amount: Decimal, *,
                   residual_account: Balance | None = None) -> Transfer:
    """Pure candidate: debit requested amount, credit posting and signed residual.

    All returned balances must be published atomically by the owning store. A
    retained residual has an explicit real account in the same unit and scope,
    with sufficient resolution/range (and funding for a negative remainder).
    """
    accounts = [source, destination] + ([residual_account] if residual_account else [])
    if (len({account.id for account in accounts}) != len(accounts)
            or len({(account.unit_id, account.scope_id) for account in accounts}) != 1):
        raise NumericError('incompatible_account')
    quantized = destination.policy.quantize(amount)
    if quantized.residual and residual_account is None:
        raise NumericError('residual_required')
    if amount and not quantized.posted:
        raise NumericError('lost_transfer')
    if amount > source.value:
        raise NumericError('insufficient_balance')
    def updated(account, change):
        return Balance(account.id, account.unit_id, account.scope_id, account.policy,
                       exact(Fraction(account.value) + change))
    new_source = updated(source, -Fraction(amount))
    new_destination = updated(destination, Fraction(quantized.posted))
    new_residual = (updated(residual_account, Fraction(quantized.residual))
                    if residual_account else None)
    after = [new_source, new_destination] + ([new_residual] if new_residual else [])
    # Exact rational sums of integer quantum counts, independent of Decimal.
    def total(items):
        return sum((item.policy.count(item.value) * Fraction(item.policy.quantum)
                    for item in items), Fraction())
    if (total(accounts) != total(after)
            or Fraction(amount) != Fraction(quantized.posted) + Fraction(quantized.residual)):
        raise NumericError('conservation_failure')
    return Transfer(new_source, new_destination, quantized.posted,
                    quantized.residual, new_residual)
