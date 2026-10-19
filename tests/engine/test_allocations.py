"""Synthetic independent allocation/yield expectations; no scientific claim."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import itertools
import pytest
from pydantic import ValidationError
from poliscope_engine.allocations import allocate
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.allocations import AllocationRequest
from poliscope_engine.numeric import Registry, Unit, NumericError


def account(id='food', opening='10', **changes):
    return dict(contract_version=1, id=id, kind='stock', unit_id='kg',
        scope_id='village', period_id=None, invariant='physical', quantum='0.01',
        maximum='1000', opening=opening, source_refs=[]) | changes


def claim(id='a', requested='8', account_id='food'):
    return dict(id=id, account_id=account_id, claimant_id='group:' + id,
        requested=requested, source_refs=[])


def choice(id='a', **changes):
    return dict(claim_id=id, access='allowed', access_limit='100', funding_known=True,
        requirements=[], outputs=[], loss_per_unit='0', mechanism_ref='reviewed:meal',
        source_refs=['synthetic:allocation']) | changes


def request(**changes):
    return dict(contract_version=1, batch=dict(contract_version=1,
        accounts=[account()], postings=[], claims=[claim('a'), claim('b')],
        reservations=[], subtotals=[]), procedure='priority', claim_order=['a', 'b'],
        choices=[choice('a'), choice('b')], mechanism_ref='selected:priority:v1',
        source_refs=['synthetic:choice']) | changes


def units():
    return Registry((Unit('kg', (('mass', 1),), 'stock', Decimal(1)),
        Unit('g', (('mass', 1),), 'stock', Decimal('0.001')),
        Unit('coin', (('currency', 1),), 'stock', Decimal(1)),
        Unit('hours', (('time', 1),), 'capacity', Decimal(1))))


def run(data):
    return allocate(AllocationRequest.model_validate(data), units())


def actuals(result):
    return {a.claim_id: (a.allocated, a.unmet, a.reason) for a in result.actuals}


def closing(result):
    return {a.account_id: (a.closing, a.outstanding_reserved, a.available) for a in result.accounts.accounts}


def requirement(account_id='money', per_unit='2', kind='funding'):
    return dict(account_id=account_id, per_unit=per_unit, kind=kind)


def funded():
    data = request()
    data['batch']['accounts'].append(account('money', '12', invariant='budget', unit_id='coin'))
    for c in data['choices']:
        c['requirements'] = [requirement()]
    return data


def transformed():
    data = request()
    data['batch']['accounts'] += [account('bread', '0'), account('bran', '0')]
    for c in data['choices']:
        c['outputs'] = [dict(account_id='bread', per_unit='0.7', role='product'),
                        dict(account_id='bran', per_unit='0.2', role='residual')]
        c['loss_per_unit'] = '0.1'
    return data


def test_priority_and_explicit_reverse_change_distribution():
    assert actuals(run(request())) == {'a': ('8', '0', 'satisfied'), 'b': ('2', '6', 'limited')}
    assert actuals(run(request(claim_order=['b', 'a']))) == {
        'a': ('2', '6', 'limited'), 'b': ('8', '0', 'satisfied')}


def test_all_or_nothing_is_a_distinct_selected_procedure():
    data = request(procedure='all_or_nothing')
    data['batch']['claims'][0]['requested'] = '12'
    assert actuals(run(data)) == {'a': ('0', '12', 'limited'), 'b': ('8', '0', 'satisfied')}
    data['procedure'] = 'priority'
    assert actuals(run(data)) == {'a': ('10', '2', 'limited'), 'b': ('0', '8', 'limited')}


@pytest.mark.parametrize('procedure', ['priority', 'all_or_nothing'])
def test_storage_order_never_selects_a_winner(procedure):
    data = request(procedure=procedure)
    expected = run(data).model_dump()
    for perm in itertools.permutations(data['choices']):
        data['choices'] = list(perm)
        data['batch']['claims'].reverse()
        result = run(data)
        assert actuals(result) == actuals(run(request(procedure=procedure)))
        assert result.batch.postings == run(request(procedure=procedure)).batch.postings
        assert result.status == expected['status']


@pytest.mark.parametrize('field,missing', [('procedure', 'procedure'), ('access', 'access'), ('funding', 'funding')])
def test_unknown_competitor_blocks_procedure_without_partial_debits(field, missing):
    data = request()
    if field == 'procedure':
        data['procedure'] = None
        data['claim_order'] = []
    elif field == 'access':
        data['choices'][1]['access'] = 'unknown'
    else:
        data['choices'][1]['funding_known'] = False
    result = run(data)
    assert result.status == 'unresolved' and result.missing == [missing]
    assert result.batch.postings == []
    assert closing(result)['food'] == ('10', '0', '10')
    assert all(a.allocated == '0' and a.reason == 'unresolved' for a in result.actuals)


def test_food_without_access_and_local_unreachable_surplus():
    data = request()
    data['choices'][0]['access'] = 'denied'
    data['choices'][1]['access_limit'] = '1'
    result = run(data)
    assert actuals(result) == {'a': ('0', '8', 'denied'), 'b': ('1', '7', 'limited')}
    assert closing(result)['food'] == ('9', '0', '9')
    assert result.request.source_refs == ['synthetic:choice']
    assert result.request.choices[0].source_refs == ['synthetic:allocation']


def test_shared_funding_cannot_create_physical_supply():
    result = run(funded())
    assert actuals(result) == {'a': ('6', '2', 'limited'), 'b': ('0', '8', 'limited')}
    assert closing(result) == {'food': ('4', '0', '4'), 'money': ('0', '0', '0')}
    data = funded()
    data['batch']['accounts'][1]['opening'] = '1000'
    assert sum(Fraction(a.allocated) for a in run(data).actuals) == 10


def test_shared_entitlements_are_finite_and_separate_from_funding():
    data = funded()
    data['batch']['accounts'].append(account('rights', '3', unit_id='coin', invariant='ledger'))
    for c in data['choices']:
        c['requirements'].append(requirement('rights', '1', 'entitlement'))
    result = run(data)
    assert actuals(result)['a'] == ('3', '5', 'limited')
    assert closing(result)['money'][0] == '6'
    assert closing(result)['rights'][0] == '0'
    assert closing(result)['food'][0] == '7'


def test_quantum_compatible_debits_leave_explicit_source_balances():
    data = funded()
    data['batch']['accounts'][1].update(opening='10', quantum='1')
    data['batch']['claims'][0]['requested'] = '1.3'
    data['choices'][1]['access'] = 'denied'
    data['choices'][0]['requirements'][0]['per_unit'] = '3'
    # Food quantum .01 and funding quantum 1 / rate 3 require multiples of 1.
    result = run(data)
    assert actuals(result)['a'] == ('1', '0.3', 'limited')
    assert closing(result)['food'][0] == '9'
    assert closing(result)['money'][0] == '7'


def test_existing_holds_fulfilled_once_before_unreserved_stock():
    data = request()
    data['batch']['reservations'] = [dict(id='hold:b', account_id='food', claim_id='b', amount='6')]
    result = run(data)
    assert actuals(result) == {'a': ('4', '4', 'limited'), 'b': ('6', '2', 'limited')}
    assert closing(result)['food'] == ('0', '0', '0')
    assert [p.reservation_id for p in result.batch.postings] == [None, 'hold:b']


def test_partial_access_retains_outstanding_hold():
    data = request()
    data['batch']['reservations'] = [dict(id='h', account_id='food', claim_id='a', amount='5')]
    data['choices'][0]['access_limit'] = '2'
    result = run(data)
    assert actuals(result)['a'][0] == '2'
    assert actuals(result)['b'][0] == '5'
    assert closing(result)['food'] == ('3', '3', '0')


def test_existing_actuals_and_multiple_holds_are_not_reallocated():
    data = request()
    data['batch']['reservations'] = [dict(id='h1', account_id='food', claim_id='a', amount='3'),
                                      dict(id='h2', account_id='food', claim_id='a', amount='2')]
    data['batch']['postings'] = [dict(id='past', kind='use', source_id='food', destination_id=None,
        amount='2', reservation_id='h1', claim_id='a', mechanism_ref='past:meal', source_refs=[])]
    result = run(data)
    assert actuals(result)['a'] == ('6', '0', 'satisfied')
    assert actuals(result)['b'] == ('2', '6', 'limited')
    assert result.accounts.claims[0].actual == '8'
    assert closing(result)['food'] == ('0', '0', '0')


def test_shared_labor_and_independent_local_stock():
    data = request()
    data['batch']['accounts'] = [account('labor', '10', kind='capacity', unit_id='hours',
        period_id='day:1', invariant='budget'), account('food:elsewhere', '100', scope_id='elsewhere')]
    for c in data['batch']['claims']:
        c['account_id'] = 'labor'
    result = run(data)
    assert [a.allocated for a in result.actuals] == ['8', '2']
    assert closing(result)['food:elsewhere'] == ('100', '0', '100')


def test_finite_import_is_consumed_once():
    data = request()
    data['batch']['accounts'][0]['opening'] = '0'
    data['batch']['postings'] = [dict(id='finite-import', kind='import', source_id=None,
        destination_id='food', amount='3', reservation_id=None, claim_id=None,
        mechanism_ref='reviewed:import', source_refs=[])]
    assert [a.allocated for a in run(data).actuals] == ['3', '0']


def test_actual_input_drives_products_residuals_and_loss():
    result = run(transformed())
    assert [(a.allocated, a.outputs, a.loss) for a in result.actuals] == [
        ('8', ['5.6', '1.6'], '0.8'), ('2', ['1.4', '0.4'], '0.2')]
    assert {k: v[0] for k, v in closing(result).items()} == {'food': '0', 'bread': '7', 'bran': '2'}
    # Independently: ten kg becomes seven useful + two residual + one loss.
    assert sum(Fraction(v[0]) for v in closing(result).values()) + sum(Fraction(a.loss) for a in result.actuals) == 10


def test_scaled_units_in_transformation():
    data = transformed()
    data['batch']['accounts'][1].update(unit_id='g', maximum='1000000')
    for c in data['choices']:
        c['outputs'][0]['per_unit'] = '700'
    result = run(data)
    assert closing(result)['bread'][0] == '7000'
    assert result.actuals[1].outputs == ['1400', '0.4']


def test_output_quantum_limits_input_without_silent_rounding():
    data = transformed()
    data['batch']['accounts'][0]['opening'] = '1'
    data['batch']['accounts'][1]['quantum'] = '1'
    result = run(data)
    assert all(a.allocated == '0' for a in result.actuals)
    assert closing(result)['food'][0] == '1'


def test_transformation_never_produces_from_requested_inputs():
    data = transformed()
    data['batch']['accounts'][0]['opening'] = '0'
    result = run(data)
    assert all(a.outputs == ['0', '0'] and a.loss == '0' for a in result.actuals)
    assert all(a.closing == '0' for a in result.accounts.accounts)


@pytest.mark.parametrize('order', [['a'], ['a', 'a'], ['b', 'a', 'ghost'], []])
def test_bad_selected_participant_order_rejected(order):
    with pytest.raises(AccountError, match='invalid_claim_order'):
        run(request(claim_order=order))


@pytest.mark.parametrize('change,code', [
    ('duplicate_choice', 'invalid_choices'), ('unknown_choice', 'invalid_choices'),
    ('duplicate_requirement', 'duplicate_requirement'), ('unknown_account', 'unknown_account'),
    ('physical_funding', 'incompatible_requirement'), ('scope', 'incompatible_requirement'),
    ('period', 'incompatible_requirement'), ('zero_rate', 'incompatible_requirement'),
    ('resource_funding', 'coupled_allocation_requires_solver'),
])
def test_bad_funding_structure_rejected(change, code):
    data = funded()
    if change == 'duplicate_choice': data['choices'].append(choice())
    if change == 'unknown_choice': data['choices'][0]['claim_id'] = 'ghost'
    if change == 'duplicate_requirement': data['choices'][0]['requirements'] *= 2
    if change == 'unknown_account': data['choices'][0]['requirements'][0]['account_id'] = 'ghost'
    if change == 'physical_funding': data['batch']['accounts'][1]['invariant'] = 'physical'
    if change == 'scope': data['batch']['accounts'][1]['scope_id'] = 'elsewhere'
    if change == 'period': data['batch']['accounts'][1]['period_id'] = 'day:1'
    if change == 'zero_rate': data['choices'][0]['requirements'][0]['per_unit'] = '0'
    if change == 'resource_funding': data['choices'][0]['requirements'][0]['account_id'] = 'food'
    with pytest.raises(AccountError, match=code): run(data)


@pytest.mark.parametrize('change,code', [
    ('yield', 'transformation_conservation_failure'), ('negative', 'negative_quantity'),
    ('dimension', 'incompatible_transformation_output'), ('scope', 'incompatible_transformation_output'),
    ('kind', 'incompatible_transformation_output'), ('duplicate', 'duplicate_output'),
    ('feedback', 'coupled_allocation_requires_solver'), ('input', 'invalid_transformation_input'),
])
def test_bad_transformation_structure_rejected(change, code):
    data = transformed()
    if change == 'yield': data['choices'][0]['loss_per_unit'] = '0'
    if change == 'negative': data['choices'][0]['outputs'][0]['per_unit'] = '-0.7'
    if change == 'dimension': data['batch']['accounts'][1]['unit_id'] = 'coin'
    if change == 'scope': data['batch']['accounts'][1]['scope_id'] = 'elsewhere'
    if change == 'kind': data['batch']['accounts'][1]['invariant'] = 'budget'
    if change == 'duplicate': data['choices'][0]['outputs'].append(data['choices'][0]['outputs'][0])
    if change == 'feedback': data['choices'][0]['outputs'][0]['account_id'] = 'food'
    if change == 'input': data['batch']['accounts'][0]['invariant'] = 'budget'
    with pytest.raises(AccountError, match=code): run(data)


@pytest.mark.parametrize('field,value', [('procedure', 'sorted_ids'), ('contract_version', 2), ('claim_order', 'a')])
def test_strict_protocol(field, value):
    with pytest.raises(ValidationError): run(request(**{field: value}))


@pytest.mark.parametrize('field', ['requested', 'access_limit', 'per_unit', 'loss_per_unit'])
def test_no_negative_or_binary_float_quantities(field):
    data = funded()
    if field == 'requested': target = data['batch']['claims'][0]
    elif field == 'per_unit': target = data['choices'][0]['requirements'][0]
    else: target = data['choices'][0]
    target[field] = '-1'
    with pytest.raises(AccountError, match='negative_quantity'): run(data)
    target[field] = 0.1
    with pytest.raises(ValidationError): run(data)


def test_nested_mutation_revalidated_and_results_detached():
    dto = AllocationRequest.model_validate(request())
    result = allocate(dto, units())
    dto.choices[0].source_refs.append('later')
    assert result.request.choices[0].source_refs == ['synthetic:allocation']
    result.batch.postings.clear()
    assert len(allocate(dto, units()).batch.postings) == 2
    dto.claim_order.append('a')
    with pytest.raises(AccountError, match='invalid_claim_order'): allocate(dto, units())


def test_bypassed_validation_is_not_trusted():
    dto = AllocationRequest.model_validate(request())
    dto.choices[0].requirements.append(dict(account_id='food', per_unit=2, kind='funding'))
    with pytest.warns(UserWarning, match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError): allocate(dto, units())


def test_ambient_decimal_context_does_not_change_actuals():
    with localcontext() as ctx:
        ctx.prec = 3
        assert actuals(run(funded()))['a'] == ('6', '2', 'limited')
        assert closing(run(transformed()))['bread'][0] == '7'


def test_output_overflow_rejects_whole_candidate_without_mutation():
    data = transformed()
    data['batch']['accounts'][1]['opening'] = '999'
    before = deepcopy(data)
    with pytest.raises(NumericError, match='invalid_balance'): run(data)
    assert data == before


def test_generated_posting_ids_do_not_collide_with_host_ids():
    data = request()
    data['batch']['accounts'].append(account('allocation:0', '0'))
    data['batch']['claims'][0]['id'] = 'allocation:1'
    data['choices'][0]['claim_id'] = 'allocation:1'
    data['claim_order'][0] = 'allocation:1'
    result = run(data)
    assert [p.id for p in result.batch.postings] == ['allocation:2', 'allocation:3']


def test_two_services_share_actual_energy_not_two_requested_outputs():
    data = request()
    data['batch']['accounts'] = [account('food', '100'), account('service:a', '0'), account('service:b', '0')]
    for c, destination in zip(data['choices'], ['service:a', 'service:b']):
        c['outputs'] = [dict(account_id=destination, per_unit='1', role='product')]
    for c in data['batch']['claims']:
        c['requested'] = '100'
    result = run(data)
    assert closing(result)['service:a'][0] == '100'
    assert closing(result)['service:b'][0] == '0'
    assert result.actuals[1].unmet == '100'


def test_different_resource_accounts_contend_for_one_global_funding_budget():
    data = funded()
    data['batch']['accounts'].append(account('other-food', '10'))
    data['batch']['claims'][1]['account_id'] = 'other-food'
    result = run(data)
    assert [a.allocated for a in result.actuals] == ['6', '0']
    assert closing(result)['other-food'][0] == '10'
    data['claim_order'].reverse()
    assert [a.allocated for a in run(data).actuals] == ['0', '6']


def test_small_integer_oracle_checks_global_stock_and_funding_contention():
    # Enumerate every feasible pair independently, then choose the lexicographic
    # maximum mandated by explicit a-before-b priority. No allocator helpers.
    for supply, money, demand_a, demand_b in itertools.product(range(4), repeat=4):
        data = funded()
        data['batch']['accounts'][0]['opening'] = str(supply)
        data['batch']['accounts'][0]['quantum'] = '1'
        data['batch']['accounts'][1]['opening'] = str(money)
        data['batch']['accounts'][1]['quantum'] = '1'
        data['batch']['claims'][0]['requested'] = str(demand_a)
        data['batch']['claims'][1]['requested'] = str(demand_b)
        feasible = [(a, b) for a in range(demand_a + 1) for b in range(demand_b + 1)
                    if a + b <= supply and 2 * (a + b) <= money]
        expected = max(feasible)
        result = run(data)
        assert tuple(int(a.allocated) for a in result.actuals) == expected
        assert int(closing(result)['food'][0]) + sum(expected) == supply
        assert int(closing(result)['money'][0]) + 2 * sum(expected) == money


def test_multiple_missing_decisions_are_reported_together():
    data = request(procedure=None, claim_order=[])
    data['choices'][0]['access'] = 'unknown'
    data['choices'][1]['funding_known'] = False
    assert run(data).missing == ['procedure', 'access', 'funding']


def test_subquantum_request_retains_exact_unmet_and_loss():
    data = transformed()
    data['batch']['accounts'][0].update(opening='1', maximum='1', quantum='0.000000000000000000000000001')
    data['batch']['claims'][0]['requested'] = '0.1234567890123456789012345678'
    # Output quantum .01 with yield .7/.2 requires input steps of .1.
    result = run(data)
    assert result.actuals[0].allocated == '0.1'
    assert result.actuals[0].loss == '0.01'
