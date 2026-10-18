"""Independent integer/rational oracles; synthetic quantities, no model claims."""
from dataclasses import FrozenInstanceError
from decimal import Decimal, getcontext, localcontext, ROUND_UP, DefaultContext
from fractions import Fraction
import json
from pathlib import Path
import pytest
from poliscope_engine.numeric import (
    RUNTIME_ID, AccountPolicy, Balance, NumericError, Population, Quantity,
    Registry, TimeBasis, Unit, calculate, canonical, context, display, exact,
    parse, stage_transfer,
)

FIXTURES = json.loads((Path(__file__).parents[1] / 'fixtures/numeric.json').read_text())


def fails(code, fn):
    with pytest.raises(NumericError) as error:
        fn()
    assert error.value.code == code


@pytest.mark.parametrize('raw,encoded', FIXTURES['canonical'])
def test_canonical(raw, encoded):
    assert canonical(parse(raw)) == encoded
    assert parse(encoded) == Decimal(raw)
    assert canonical(parse(encoded)) == encoded


@pytest.mark.parametrize('operation,left,right,result', FIXTURES['arithmetic'])
def test_arithmetic(operation, left, right, result):
    actual = calculate(parse(left), parse(right), operation)
    assert canonical(actual) == result
    a, b = Fraction(left), Fraction(right)
    oracle = {'add': lambda: a+b, 'subtract': lambda: a-b,
              'multiply': lambda: a*b, 'divide': lambda: a/b}[operation]()
    assert Fraction(actual) == oracle


@pytest.mark.parametrize('value,places,result', FIXTURES['display'])
def test_display(value, places, result):
    stored = parse(value)
    assert display(stored, places) == result
    assert canonical(stored) == value


@pytest.mark.parametrize('raw', [0, 1.25, True, Decimal('1'), '', 'NaN', '-NaN',
    'Infinity', '-Infinity', '+1', '01', '.1', '1.', ' 1', '1\n', '1_000',
    '1e9999999999999999999999999999999', '0' * 257])
def test_invalid_inputs(raw):
    fails('invalid_decimal', lambda: parse(raw))


@pytest.mark.parametrize('raw', ['1e257', '1e-257', '0e-513', '0e257',
    '1.0000000000000000000000000001'])
def test_precision_bounds(raw):
    fails('precision_unsupported', lambda: parse(raw))


def test_arithmetic_precision_and_zero():
    fails('precision_unsupported', lambda: calculate(parse('1e29'), parse('1'), 'subtract'))
    fails('precision_unsupported', lambda: calculate(parse('1'), parse('3'), 'divide'))
    fails('invalid_denominator', lambda: calculate(parse('0'), parse('0'), 'divide'))
    fails('unknown_operation', lambda: calculate(parse('1'), parse('1'), 'power'))
    fails('invalid_decimal', lambda: calculate(0.1, parse('1'), 'add'))
    fails('invalid_decimal', lambda: canonical(Decimal('Infinity')))
    fails('invalid_display_precision', lambda: display(parse('1'), True))


def test_context_independent_of_global_mutation():
    assert FIXTURES['runtime_id'] == RUNTIME_ID
    old = DefaultContext.copy()
    try:
        DefaultContext.prec = 2
        DefaultContext.rounding = ROUND_UP
        DefaultContext.clear_traps()
        with localcontext() as outer:
            outer.prec = 2
            outer.rounding = ROUND_UP
            outer.Emin, outer.Emax = -2, 2
            outer.clear_traps()
            outer.clear_flags()
            assert calculate(parse('123456789'), parse('0.1'), 'multiply') == Decimal('12345678.9')
            assert display(parse('1.245'), 2) == '1.24'
            assert exact(Fraction(1, 8)) == Decimal('0.125')
            assert parse('1e256') == Decimal('1e256')
            assert parse('1e-256') == Decimal('1e-256')
            assert not any(outer.flags.values())
            assert getcontext().prec == 2
            assert context().prec == 28
    finally:
        DefaultContext.prec, DefaultContext.rounding = old.prec, old.rounding
        DefaultContext.traps = old.traps


@pytest.fixture
def registry():
    return Registry((
        Unit('kg', (('mass', 1),), 'stock', parse('1')),
        Unit('g', (('mass', 1),), 'stock', parse('0.001')),
        Unit('third-kg', (('mass', 1),), 'stock', parse('3')),
        Unit('L', (('volume', 1),), 'stock', parse('1')),
        Unit('L-rate', (('volume', 1),), 'flow', parse('1')),
        Unit('mL-rate', (('volume', 1),), 'flow', parse('0.001')),
        Unit('L-capacity', (('volume', 1),), 'capacity', parse('1')),
        Unit('money', (('mass', 1),), 'money', parse('1')),
        Unit('seconds', (('time', 1),), 'time', parse('1')),
        Unit('hours', (('time', 1),), 'time', parse('3600')),
        Unit('people', (('person', 1),), 'count', parse('1')),
        Unit('claim', (('person', 1),), 'entitlement', parse('1')),
        Unit('ratio', (), 'indicator', parse('1')),
    ))


def test_equivalent_units_and_unknown(registry):
    q = Quantity(parse('1250'), 'g', 'north')
    result = registry.convert(q, 'kg')
    assert canonical(result.value) == '1.25'
    assert registry.convert(result, 'g') == q
    assert registry.convert(Quantity(parse('7200'), 'seconds', 'north'), 'hours').value == 2
    for target in ['L', 'money']:
        fails('incompatible_unit', lambda: registry.convert(q, target))
    fails('unknown_unit', lambda: registry.convert(q, 'unknown'))
    fails('precision_unsupported', lambda: registry.convert(Quantity(parse('1'), 'kg', 'north'), 'third-kg'))
    fails('incompatible_unit', lambda: registry.convert(Quantity(parse('1'), 'people', 'north'), 'claim'))


def test_time_population_and_scope(registry):
    day = TimeBasis('fixed-day', parse('86400'))
    year = TimeBasis('explicit-365-day-year', parse('31536000'))
    # Factors are explicit fixture choices; this does not select a game calendar.
    north = Population('cohort-a@revision-1', 'north', parse('100'))
    subgroup = Population('cohort-b@revision-1', 'north', parse('25'))
    q = Quantity(parse('2'), 'L-rate', 'north', day, north)
    result = registry.convert(q, 'mL-rate', time_basis=year)
    assert Fraction(result.value) == 2 * 1000 * 365 * 100
    normalized = registry.convert(q, 'L-rate', time_basis=day, population=subgroup)
    assert normalized.value == 8
    assert registry.convert(normalized, 'L-rate', time_basis=day, population=north) == q
    fails('incompatible_scope', lambda: registry.convert(q, 'L-rate', time_basis=day, scope_id='south'))
    fails('incompatible_scope', lambda: Quantity(parse('1'), 'kg', 'south', population=north))
    fails('incompatible_time_basis', lambda: registry.convert(q, 'L-rate'))
    fails('invalid_time_basis', lambda: registry.convert(Quantity(parse('1'), 'L-rate', 'north'), 'L-rate'))
    fails('invalid_time_basis', lambda: registry.convert(Quantity(parse('1'), 'kg', 'north', day), 'g', time_basis=year))
    fails('incompatible_unit', lambda: registry.convert(q, 'L-capacity', time_basis=day))
    for value in ['0', '-1']:
        fails('invalid_denominator', lambda: Population('x', 'north', parse(value)))
        fails('invalid_time_basis', lambda: TimeBasis('x', parse(value)))
    third = Population('third', 'north', parse('3'))
    fails('precision_unsupported', lambda: registry.convert(Quantity(parse('1'), 'kg', 'north'), 'kg', population=third))


def test_definition_validation_and_immutability(registry):
    with pytest.raises(FrozenInstanceError):
        registry.units = ()
    fails('duplicate_unit', lambda: Registry((registry.units[0], registry.units[0])))
    for dims in [(('z', 1), ('a', 1)), (('a', 0),), (('a', 1), ('a', 2))]:
        fails('invalid_unit', lambda: Unit('x', dims, 'stock', parse('1')))
    fails('invalid_unit_scale', lambda: Unit('x', (), 'stock', parse('0')))


def balance(id, value, quantum='0.01', maximum='1000', rule='reject'):
    return Balance(id, 'kg', 'north', AccountPolicy(parse(quantum), parse(maximum), rule), parse(value))


def test_exact_transfers_and_yield_loss():
    source, product, loss = balance('input', '125'), balance('product', '0'), balance('loss', '0')
    amount = calculate(source.value, parse('0.8'), 'multiply')
    first = stage_transfer(source, product, amount)
    second = stage_transfer(first.source, loss, first.source.value)
    assert (second.source.value, first.destination.value, second.destination.value) == (0, 100, 25)
    assert sum(Fraction(x) for x in [second.source.value, first.destination.value, second.destination.value]) == 125
    assert source.value == 125  # candidates are immutable, no early mutation


def test_repeated_transfers_independent_quantum_counts():
    source, dest = balance('source', '10'), balance('dest', '0')
    for _ in range(100):
        result = stage_transfer(source, dest, parse('0.01'))
        source, dest = result.source, result.destination
    assert (source.policy.count(source.value), dest.policy.count(dest.value)) == (900, 100)
    assert Fraction(source.value) + Fraction(dest.value) == 10


@pytest.mark.parametrize('amount,posted,remainder', [('1.245', '1.24', '0.005'), ('1.255', '1.26', '-0.005')])
def test_retained_residual_is_real_account(amount, posted, remainder):
    source = balance('source', '10', quantum='0.001')
    dest = balance('dest', '0', rule='retain')
    residual = balance('residual', '1', quantum='0.001')
    result = stage_transfer(source, dest, parse(amount), residual_account=residual)
    assert result.posted == Decimal(posted)
    assert result.residual == Decimal(remainder)
    assert Fraction(result.residual_account.value) == 1 + Fraction(remainder)
    assert sum(Fraction(b.value) for b in [result.source, result.destination, result.residual_account]) == 11
    assert Fraction(result.source.value) == 10 - Fraction(amount)
    fails('residual_required', lambda: stage_transfer(source, dest, parse(amount)))
    fails('residual_required', lambda: stage_transfer(source, balance('dest', '0'), parse(amount)))


def test_unfunded_or_unrepresentable_residual_rejects_before_mutation():
    source = balance('source', '10', quantum='0.001')
    dest = balance('dest', '0', rule='retain')
    for residual in [balance('residual', '0', quantum='0.001'), balance('residual', '1')]:
        fails('invalid_balance', lambda: stage_transfer(source, dest, parse('1.255'), residual_account=residual))
    assert source.value == 10 and dest.value == 0


def test_lost_transfer_and_range_witness():
    # 1E29 cannot promise unit resolution. A coarser declared resolution is valid,
    # but rejects unit withdrawals, even when Decimal would leave stock unchanged.
    fails('precision_unsupported', lambda: AccountPolicy(parse('1'), parse('1e29'), 'reject'))
    large = balance('source', '1e29', quantum='1000', maximum='1e29', rule='retain')
    dest = balance('dest', '0', quantum='1000', maximum='1e29', rule='retain')
    for _ in range(10):
        fails('lost_transfer', lambda: stage_transfer(large, dest, parse('1'), residual_account=balance('r', '0')))
    assert large.value == Decimal('1e29') and dest.value == 0
    accepted = stage_transfer(large, dest, parse('1000'))
    assert Fraction(accepted.source.value) == 10**29 - 1000
    assert large.policy.count(accepted.source.value) + dest.policy.count(accepted.destination.value) == 10**26
    fails('invalid_account_policy', lambda: AccountPolicy(parse('0.03'), parse('1000'), 'reject'))
    fails('insufficient_balance', lambda: stage_transfer(balance('s', '0'), balance('d', '0'), parse('1')))
    fails('invalid_balance', lambda: stage_transfer(balance('s', '1'), balance('d', '1000'), parse('1')))
    fails('incompatible_account', lambda: stage_transfer(large, large, parse('0')))
    fails('invalid_transfer', lambda: stage_transfer(large, dest, parse('-1')))


@pytest.mark.parametrize('raw', ['1e256', '-1e256', '1e-256', '-1.2345e-256'])
def test_boundary_canonical_can_be_read(raw):
    encoded = canonical(parse(raw))
    assert len(encoded) <= 256
    assert parse(encoded) == parse(raw)
