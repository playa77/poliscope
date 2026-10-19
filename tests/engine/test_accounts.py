"""Independent quantities: no expected values computed through ledger code."""
from decimal import Decimal, localcontext
import itertools
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountBook, AccountError
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.numeric import Registry, Unit, NumericError, AccountPolicy, Balance, stage_transfer


def definition(id='food', **changes):
    return dict(contract_version=1, id=id, kind='stock', unit_id='kg', scope_id='village',
                period_id=None, invariant='physical', quantum='0.01', maximum='1000',
                opening='10', source_refs=[]) | changes


def posting(id='meal', kind='use', source_id='food', destination_id=None, amount='3', **changes):
    return dict(id=id, kind=kind, source_id=source_id, destination_id=destination_id,
                amount=amount, reservation_id=None, claim_id=None,
                mechanism_ref='reviewed:food', source_refs=[]) | changes


def claim(id='household', requested='8', account_id='food'):
    return dict(id=id, account_id=account_id, claimant_id='people', requested=requested, source_refs=[])


def reservation(id='hold', amount='5', **changes):
    return dict(id=id, account_id='food', claim_id='household', amount=amount) | changes


def batch(**changes):
    return dict(contract_version=1, accounts=[definition()], postings=[], claims=[], reservations=[], subtotals=[]) | changes


def units():
    return Registry((Unit('kg', (('mass', 1),), 'stock', Decimal(1)),
                     Unit('hours', (('time', 1),), 'capacity', Decimal(1)),
                     Unit('rate', (('mass', 1),), 'flow', Decimal(1))))


def book(data):
    return AccountBook(AccountBatch.model_validate(data), units())


def values(b):
    return {a.account_id: (a.closing, a.outstanding_reserved, a.available) for a in b.evaluate().accounts}


def test_stock_import_export_loss_and_actuals():
    # 10 opening + 4 imports + 2 supply + 1 output - 3 use - 2 export - 1 loss = 11.
    p = [posting(), posting('abroad', 'export', amount='2'), posting('spoil', 'loss', amount='1'),
         posting('import', 'import', None, 'food', '4'),
         posting('supply', 'supply', None, 'food', '2'), posting('output', 'production', None, 'food', '1')]
    b = book(batch(postings=p))
    assert values(b) == {'food': ('11', '0', '11')}
    assert {p.kind for p in b.batch.postings} == {'use', 'export', 'loss', 'import', 'supply', 'production'}


def test_hold_is_replaced_once_and_unmet_retained():
    b = book(batch(claims=[claim()], reservations=[reservation()],
                   postings=[posting(claim_id='household', reservation_id='hold')]))
    assert values(b) == {'food': ('7', '2', '5')}
    assert b.evaluate().claims[0].model_dump() == dict(claim_id='household', actual='3', unmet='5')


def test_full_reservation_and_export():
    b = book(batch(claims=[claim()], reservations=[reservation(amount='8')],
                   postings=[posting(kind='export', amount='8', claim_id='household', reservation_id='hold')]))
    assert values(b) == {'food': ('2', '0', '2')}
    assert b.evaluate().claims[0].unmet == '0'


def test_food_present_without_household_access():
    b = book(batch(claims=[claim()]))
    assert values(b)['food'] == ('10', '0', '10')
    assert b.evaluate().claims[0].actual == '0'
    assert b.evaluate().claims[0].unmet == '8'


def test_capacity_and_flow_have_explicit_period_no_automatic_accrual():
    for kind, unit in [('capacity', 'hours'), ('flow', 'rate')]:
        b = book(batch(accounts=[definition(kind=kind, unit_id=unit, period_id='day:1', invariant='budget')],
                       postings=[posting(amount='7')], claims=[claim(requested='20')]))
        assert values(b)['food'] == ('3', '0', '3')
        assert b.evaluate().claims[0].unmet == '20'


@pytest.mark.parametrize('kind', ['capacity', 'flow'])
def test_missing_period(kind):
    with pytest.raises(ValidationError):
        book(batch(accounts=[definition(kind=kind)]))


def test_internal_transfer_and_subtotal():
    b = book(batch(accounts=[definition('food'), definition('store', opening='0')],
        postings=[posting('move', 'transfer', 'food', 'store', '4')],
        subtotals=[dict(id='all', member_ids=['food', 'store'])]))
    assert values(b) == {'food': ('6', '0', '6'), 'store': ('4', '0', '4')}
    assert b.total(('all',)) == '10'
    with pytest.raises(AccountError, match='overlapping_subtotal'):
        b.total(('all', 'food'))


@pytest.mark.parametrize('change,error', [
    ({'postings':[posting(amount='11')]}, 'insufficient_balance'),
    ({'postings':[posting(amount='-1')]}, 'negative_quantity'),
    ({'postings':[posting(source_id='absent')]}, 'unknown_account'),
    ({'postings':[posting(claim_id='absent')]}, 'incompatible_claim'),
    ({'postings':[posting(reservation_id='absent')]}, 'incompatible_reservation'),
    ({'accounts':[definition(), definition()]}, 'duplicate_identity'),
    ({'claims':[claim('food')]}, 'duplicate_identity'),
    ({'claims':[claim(account_id='absent')]}, 'unknown_account'),
    ({'claims':[claim()], 'reservations':[reservation(amount='9')]}, 'reservation_exceeds_claim'),
    ({'claims':[claim(requested='20')], 'reservations':[reservation(amount='11')]}, 'reservation_unfunded'),
    ({'claims':[claim()], 'reservations':[reservation(amount='2')],
      'postings':[posting(claim_id='household', reservation_id='hold')]}, 'reservation_exceeded'),
    ({'claims':[claim(requested='2')], 'postings':[posting(claim_id='household')]}, 'claim_exceeded'),
    ({'claims':[claim()], 'reservations':[reservation(amount='8')],
      'postings':[posting(claim_id='household')]}, 'reservation_exceeds_unmet'),
    ({'accounts':[definition(unit_id='hours')]}, 'incompatible_account_kind'),
])
def test_invalid_candidates(change, error):
    with pytest.raises(AccountError, match=error):
        book(batch(**change))


@pytest.mark.parametrize('change', [dict(scope_id='elsewhere'), dict(period_id='next'),
                                  dict(invariant='ledger')])
def test_transfer_semantics_must_match(change):
    with pytest.raises(AccountError, match='incompatible_transfer'):
        book(batch(accounts=[definition(), definition('other', **change)],
                   postings=[posting(kind='transfer', destination_id='other')]))


@pytest.mark.parametrize('subtotals,error', [
    ([dict(id='all', member_ids=['food','food'])], 'duplicate_subtotal_member'),
    ([dict(id='all', member_ids=['all'])], 'subtotal_cycle'),
    ([dict(id='a',member_ids=['b']),dict(id='b',member_ids=['a'])], 'subtotal_cycle'),
    ([dict(id='all',member_ids=['absent'])], 'unknown_subtotal_member'),
    ([dict(id='a',member_ids=['food']),dict(id='all',member_ids=['food','a'])], 'overlapping_subtotal'),
])
def test_subtotal_failures(subtotals,error):
    with pytest.raises(AccountError, match=error):
        book(batch(subtotals=subtotals))


def test_nested_subtotals_and_mixed_selection():
    b=book(batch(accounts=[definition(),definition('other')],subtotals=[
        dict(id='inner',member_ids=['food']),dict(id='outer',member_ids=['inner','other'])]))
    assert b.total(('outer',)) == '20'
    with pytest.raises(AccountError,match='overlapping_subtotal'):
        b.total(('inner','outer'))


@pytest.mark.parametrize('amount', ['0.001','1e-28','10000000000000000000000000001'])
def test_precision_rejection(amount):
    with pytest.raises(NumericError):
        book(batch(postings=[posting(amount=amount)]))


def test_residual_transfer_posts_all_three_accounts():
    policy=AccountPolicy(Decimal('0.01'), Decimal('1000'), 'retain')
    fine=AccountPolicy(Decimal('0.001'), Decimal('1000'), 'reject')
    transfer=stage_transfer(Balance('food','kg','village',fine,Decimal('10')),
        Balance('other','kg','village',policy,Decimal('0')),Decimal('1.234'),
        residual_account=Balance('dust','kg','village',fine,Decimal('0')))
    assert transfer.posted == Decimal('1.23') and transfer.residual == Decimal('0.004')
    b=book(batch(accounts=[definition(quantum='0.001'),definition('other',opening='0'),
                         definition('dust',opening='0',quantum='0.001')],postings=[
        posting('main','transfer','food','other','1.23'),
        posting('residue','residual','food','dust','0.004')]))
    assert values(b)=={'food':('8.766','0','8.766'),'other':('1.23','0','1.23'),'dust':('0.004','0','0.004')}
    assert b.total(('food','other','dust'))=='10'


def test_snapshot_defends_mutable_lists_and_model_copy():
    dto=AccountBatch.model_validate(batch())
    b=AccountBook(dto, units())
    dto.accounts.clear()
    b.batch.accounts.clear()
    b.evaluate().accounts.clear()
    assert values(b)['food']==('10','0','10')
    with pytest.warns(UserWarning, match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):
            AccountBook(b.batch.model_copy(update={'postings':[posting(amount=3)]}), units())


def test_input_order_and_decimal_context_do_not_choose_results():
    ps=[posting('a',amount='2'), posting('b',amount='4'),posting('c','import',None,'food','1')]
    for order in itertools.permutations(ps):
        with localcontext() as ctx:
            ctx.prec=2
            assert values(book(batch(postings=list(order))))['food']==('5','0','5')


@pytest.mark.parametrize('kind,source,destination', [('import','food',None),('use',None,'food'),
                                                   ('transfer','food',None),('transfer','food','food')])
def test_invalid_endpoints(kind,source,destination):
    with pytest.raises(ValidationError):
        book(batch(postings=[posting(kind=kind,source_id=source,destination_id=destination)]))


def test_finite_external_supply_does_not_multiply():
    b=book(batch(accounts=[definition(opening='0'),definition('outside',opening='5')],
                 postings=[posting('imported','transfer','outside','food','5'),posting(amount='3')]))
    assert values(b)=={'food':('2','0','2'),'outside':('0','0','0')}
    with pytest.raises(AccountError,match='insufficient_balance'):
        book(batch(accounts=[definition(opening='0'),definition('outside',opening='5')],
                   postings=[posting('imported','transfer','outside','food','6')]))


def test_two_holds_for_same_claim_are_not_independent_supply():
    with pytest.raises(AccountError,match='reservation_exceeds_claim'):
        book(batch(claims=[claim()],reservations=[reservation(),reservation('second')]))


def test_negative_rounding_residual_has_explicit_funded_movement():
    # 1.236 requested rounds to 1.24: source contributes 1.236 and residual 0.004.
    b=book(batch(accounts=[definition(quantum='0.001'),definition('other',opening='0',quantum='0.001'),
                          definition('dust',opening='0.01',quantum='0.001')],postings=[
        posting('main','transfer','food','other','1.236'),posting('remainder','residual','dust','other','0.004')]))
    assert values(b)=={'food':('8.764','0','8.764'),'other':('1.24','0','1.24'),'dust':('0.006','0','0.006')}
    assert b.total(('food','other','dust'))=='10.01'


@pytest.mark.parametrize('change', [dict(scope_id='other'),dict(period_id='other'),dict(invariant='ledger')])
def test_subtotal_cannot_mix_account_semantics(change):
    with pytest.raises(AccountError,match='incompatible_subtotal'):
        book(batch(accounts=[definition(),definition('other',**change)],
                   subtotals=[dict(id='all',member_ids=['food','other'])]))


def test_large_stocks_cannot_absorb_small_postings():
    with pytest.raises(NumericError):
        book(batch(accounts=[definition(opening='1e29',maximum='2e29',quantum='1000')],
                   postings=[posting(amount='1')]))


def test_missing_quantities_are_never_zero():
    for amount in [None, 0, 1.2, 'NaN']:
        with pytest.raises(ValidationError):
            book(batch(postings=[posting(amount=amount)]))


def test_all_postings_may_be_reported_for_one_account():
    b=book(batch(postings=[posting(str(i),amount='0.01') for i in range(101)]))
    assert values(b)['food']==('8.99','0','8.99')
    assert len(b.evaluate().accounts[0].posting_ids)==101
