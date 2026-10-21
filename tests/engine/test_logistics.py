"""Independent freight oracles; synthetic figures carry no empirical claim."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.allocations import allocate
from poliscope_engine.contracts.allocations import AllocationRequest
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.contracts.logistics import LogisticsRequest
from poliscope_engine.domains.provisioning.logistics import transport
from poliscope_engine.numeric import Registry, Unit, NumericError


def units():
    return Registry((Unit('kg', (('mass', 1),), 'stock', Decimal(1)),
        Unit('freight-kg', (('mass', 1),), 'capacity', Decimal(1)),
        Unit('hours', (('time', 1),), 'capacity', Decimal(1))))


def account(aid, opening, scope='east', kind='stock', unit='kg'):
    return dict(contract_version=1, id=aid, kind=kind, unit_id=unit, scope_id=scope,
        period_id=None if kind == 'stock' else 'day:0',
        invariant='physical' if kind == 'stock' else 'budget', quantum='1',
        maximum='1000', opening=opening, source_refs=['authored:freight-v1'])


def request():
    return dict(contract_version=1, period_id='day:0', batch=dict(contract_version=1,
        accounts=[account('food:east', '20'), account('food:west', '0', 'west'),
            account('food:north', '0', 'north'),
            account('truck', '10', kind='capacity', unit='freight-kg'),
            account('crew', '8', kind='capacity', unit='hours')],
        claims=[dict(id=c, account_id='food:east', claimant_id=g, requested='8', source_refs=[])
            for c, g in [('west-delivery', 'west-group'), ('north-delivery', 'north-group')]],
        postings=[], reservations=[], subtotals=[]),
        resources=[dict(account_id=a, resource_id='food') for a in ['food:east', 'food:west', 'food:north']],
        routes=[dict(claim_id=c, destination_id=d, capacity_id='truck', capacity_per_unit='1',
            access='allowed', access_limit='100', funding_known=True,
            requirements=[dict(account_id='crew', per_unit='1', kind='funding')],
            mechanism_ref='authored:freight-v1', source_refs=['authored:freight-v1'])
            for c, d in [('west-delivery', 'food:west'), ('north-delivery', 'food:north')]],
        procedure='priority', claim_order=['west-delivery', 'north-delivery'],
        mechanism_ref='authored:priority-v1', source_refs=['authored:freight-v1'])


def run(data=None):
    return transport(LogisticsRequest.model_validate(data or request()), units())


def balances(result):
    return {a.account_id: a.closing for a in result.accounts.accounts}


def delivered(result):
    return {m.claim_id: m.delivered for m in result.movements}


def test_shared_crew_stock_and_throughput_are_deducted_once():
    data = request()
    before = deepcopy(data)
    result = run(data)
    assert data == before
    assert delivered(result) == {'north-delivery': '0', 'west-delivery': '8'}
    assert balances(result) == {'food:east': '12', 'food:west': '8', 'food:north': '0', 'truck': '2', 'crew': '0'}
    assert [(c.claim_id, c.actual, c.unmet) for c in result.accounts.claims] == [
        ('north-delivery', '0', '8'), ('west-delivery', '8', '0')]
    movement = next(m for m in result.movements if m.claim_id == 'west-delivery')
    posts = {p.id: p for p in result.batch.postings}
    assert posts[movement.import_posting_id].amount == '8'
    assert sum(Fraction(posts[p].amount) for p in movement.export_posting_ids) == 8
    assert all(posts[p].kind == 'export' for p in movement.export_posting_ids)
    assert posts[movement.import_posting_id].source_refs == ['authored:freight-v1']
    assert sum(Fraction(v) for k, v in balances(result).items() if k.startswith('food:')) == 20


def test_explicit_order_changes_distribution_but_not_stock():
    data = request()
    data['claim_order'].reverse()
    assert delivered(run(data)) == {'north-delivery': '8', 'west-delivery': '0'}


@pytest.mark.parametrize('constraint', ['stock', 'truck', 'crew', 'access'])
def test_independent_bottlenecks(constraint):
    data = request()
    if constraint == 'access': data['routes'][0]['access_limit'] = '3'
    else:
        aid = {'stock': 'food:east', 'truck': 'truck', 'crew': 'crew'}[constraint]
        next(a for a in data['batch']['accounts'] if a['id'] == aid)['opening'] = '3'
    result = run(data)
    assert delivered(result)['west-delivery'] == '3'
    assert delivered(result)['north-delivery'] == ('5' if constraint == 'access' else '0')


def test_reservation_consumed_once_and_undelivered_hold_survives():
    data = request()
    data['batch']['reservations'] = [dict(id='hold', account_id='food:east', claim_id='north-delivery', amount='8')]
    data['batch']['accounts'][0]['opening'] = '10'
    result = run(data)
    assert delivered(result) == {'north-delivery': '6', 'west-delivery': '2'}
    east = next(a for a in result.accounts.accounts if a.account_id == 'food:east')
    assert (east.closing, east.outstanding_reserved, east.available) == ('2', '2', '0')
    assert sum(Fraction(p.amount) for p in result.batch.postings if p.reservation_id == 'hold') == 6


def test_no_throughput_leaves_distant_surplus_unavailable_and_access_is_distinct():
    data = request()
    data['batch']['accounts'][3]['opening'] = '0'
    assert balances(run(data))['food:east'] == '20'
    assert balances(run(data))['food:west'] == '0'
    data['batch']['accounts'][3]['opening'] = '10'
    data['routes'][0]['access'] = 'denied'
    result = run(data)
    assert delivered(result) == {'north-delivery': '8', 'west-delivery': '0'}
    assert next(a for a in result.allocation.actuals if a.claim_id == 'west-delivery').reason == 'denied'


@pytest.mark.parametrize('field', ['procedure', 'access', 'funding'])
def test_unknown_competitor_never_allocates_known_routes(field):
    data = request()
    if field == 'procedure': data['procedure'] = None
    if field == 'access': data['routes'][1]['access'] = 'unknown'
    if field == 'funding': data['routes'][1]['funding_known'] = False
    result = run(data)
    assert result.allocation.status == 'unresolved'
    assert result.allocation.missing == [field]
    assert result.batch.postings == []
    assert all(m.delivered == '0' for m in result.movements)


def test_no_procedure_inferred_from_ids_and_all_or_nothing_is_explicit():
    data = request()
    data['batch']['accounts'][4]['opening'] = '7'
    data['procedure'] = 'all_or_nothing'
    assert all(m.delivered == '0' for m in run(data).movements)
    data['procedure'] = 'priority'
    assert delivered(run(data))['west-delivery'] == '7'


def test_completed_postings_are_not_mirrored_again():
    first = run()
    data = request()
    data['batch'] = first.batch.model_dump()
    second = run(data)
    assert second.batch == first.batch
    assert all(m.delivered == '0' and m.import_posting_id is None for m in second.movements)


def test_prior_fulfillment_only_new_actual_is_transported():
    data = request()
    data['batch']['postings'] = [dict(id='prior', kind='export', source_id='food:east',
        destination_id=None, amount='3', reservation_id=None, claim_id='west-delivery',
        mechanism_ref='prior:shipment', source_refs=[])]
    result = run(data)
    assert delivered(result) == {'north-delivery': '3', 'west-delivery': '5'}
    assert balances(result)['food:west'] == '5'


def test_incompatible_or_missing_route_never_becomes_free_supply():
    data = request()
    data['routes'].pop()
    with pytest.raises(AccountError, match='invalid_routes'): run(data)


@pytest.mark.parametrize('change,code', [
    ('duplicate_route', 'invalid_routes'), ('duplicate_resource', 'invalid_resource_bindings'),
    ('resource', 'transport_resource_mismatch'), ('missing_resource', 'transport_resource_mismatch'),
    ('unknown', 'unknown_account'), ('same_scope', 'incompatible_transport_stock'),
    ('quantum', 'incompatible_transport_stock'), ('ledger', 'incompatible_transport_stock'),
    ('capacity_scope', 'invalid_transport_capacity'), ('capacity_kind', 'invalid_transport_capacity'),
    ('capacity_unit', 'invalid_transport_capacity'), ('capacity_rate', 'invalid_transport_capacity'),
    ('duplicate_requirement', 'duplicate_requirement'), ('cycle', 'coupled_transport_requires_solver'),
])
def test_invalid_interfaces_reject_whole_candidate(change, code):
    data = request()
    if change == 'duplicate_route': data['routes'].append(deepcopy(data['routes'][0]))
    if change == 'duplicate_resource': data['resources'].append(deepcopy(data['resources'][0]))
    if change == 'resource': data['resources'][1]['resource_id'] = 'metal'
    if change == 'missing_resource': data['resources'].pop(1)
    if change == 'unknown': data['routes'][0]['destination_id'] = 'missing'
    if change == 'same_scope': data['batch']['accounts'][1]['scope_id'] = 'east'
    if change == 'quantum': data['batch']['accounts'][1]['quantum'] = '0.1'
    if change == 'ledger': data['batch']['accounts'][1]['invariant'] = 'ledger'
    if change == 'capacity_scope': data['batch']['accounts'][3]['scope_id'] = 'region'
    if change == 'capacity_kind': data['routes'][0]['capacity_id'] = 'food:north'
    if change == 'capacity_unit': data['batch']['accounts'][3]['unit_id'] = 'hours'
    if change == 'capacity_rate': data['routes'][0]['capacity_per_unit'] = '0'
    if change == 'duplicate_requirement': data['routes'][0]['requirements'].append(dict(account_id='truck', per_unit='1', kind='funding'))
    if change == 'cycle': data['routes'][0]['destination_id'] = 'food:east'
    before = deepcopy(data)
    with pytest.raises(AccountError, match=code): run(data)
    assert data == before


def test_destination_overflow_rejects_whole_candidate_and_leaves_inputs_unchanged():
    data = request()
    data['batch']['accounts'][1]['maximum'] = '2'
    before = deepcopy(data)
    with pytest.raises(NumericError, match='invalid_balance'): run(data)
    assert data == before


def test_bound_dtos_revalidate_and_do_not_alias():
    dto = LogisticsRequest.model_validate(request())
    result = transport(dto, units())
    dto.routes[0].source_refs.append('later')
    assert result.request.routes[0].source_refs == ['authored:freight-v1']
    dto.routes.append(dto.routes[0])
    with pytest.raises(AccountError, match='invalid_routes'): transport(dto, units())


@pytest.mark.parametrize('value', [0.1, 'NaN', 'Infinity'])
def test_binary_float_and_nonfinite_capacity_rejected(value):
    data = request()
    data['routes'][0]['capacity_per_unit'] = value
    with pytest.raises((ValidationError, NumericError)): run(data)


def test_ambient_precision_and_id_collisions_do_not_change_delivery():
    data = request()
    data['batch']['accounts'].append(account('transport:0', '0'))
    with localcontext() as ctx:
        ctx.prec = 2
        result = run(data)
    assert delivered(result)['west-delivery'] == '8'
    assert result.movements[1].import_posting_id == 'transport:1'


def test_integer_oracle_for_shared_stock_capacity_and_crew():
    # Enumerate feasible shipments; explicit priority selects lexicographic max.
    # Expected values use no production allocator or numeric helper.
    for stock, truck, crew in product(range(4), repeat=3):
        data = request()
        for aid, value in [('food:east', stock), ('truck', truck), ('crew', crew)]:
            next(a for a in data['batch']['accounts'] if a['id'] == aid)['opening'] = str(value)
        for c in data['batch']['claims']: c['requested'] = '2'
        feasible = [(w, n) for w in range(3) for n in range(3)
            if w + n <= stock and w + n <= truck and w + n <= crew]
        expected = max(feasible)
        result = run(data)
        assert tuple(int(delivered(result)[c]) for c in data['claim_order']) == expected
        b = balances(result)
        assert int(b['food:east']) + int(b['food:west']) + int(b['food:north']) == stock
        assert int(b['truck']) + sum(expected) == truck
        assert int(b['crew']) + sum(expected) == crew


@pytest.mark.parametrize('account_id,code', [('truck', 'invalid_transport_capacity'), ('crew', 'incompatible_transport_period')])
def test_capacity_and_crew_cannot_be_borrowed_from_a_different_day(account_id, code):
    data = request()
    next(a for a in data['batch']['accounts'] if a['id'] == account_id)['period_id'] = 'day:1'
    with pytest.raises(AccountError, match=code): run(data)


def test_fractional_quantum_keeps_exact_remainder_in_source():
    data = request()
    for a in data['batch']['accounts']: a['quantum'] = '0.1'
    data['batch']['accounts'][3]['opening'] = '1'
    data['routes'][0]['capacity_per_unit'] = '3'
    result = run(data)
    assert delivered(result)['west-delivery'] == '0.3'
    # 0.1 capacity remains: it cannot transport another 0.1 kg at rate 3.
    # The second route explicitly uses rate 1, so it consumes that final 0.1.
    assert delivered(result)['north-delivery'] == '0.1'
    assert balances(result)['food:east'] == '19.6'


def test_delivery_then_local_access_does_not_conflate_entitlement_and_supply():
    freight = run()
    data = freight.batch.model_dump()
    data['claims'].append(dict(id='eat', account_id='food:west', claimant_id='west-group', requested='6', source_refs=[]))
    # Prior delivery claims remain in the shared book with their old actuals;
    # the host explicitly closes that phase's access before local consumption.
    choices = [dict(claim_id=c['id'], access='denied', access_limit='0', funding_known=True,
        requirements=[], outputs=[], loss_per_unit='0', mechanism_ref='authored:local-access', source_refs=[])
        for c in data['claims']]
    denied = allocate(AllocationRequest(contract_version=1, batch=AccountBatch.model_validate(data),
        procedure='priority', claim_order=[c['id'] for c in data['claims']], choices=choices,
        mechanism_ref='authored:local-access', source_refs=[]), units())
    assert next(c for c in denied.accounts.claims if c.claim_id == 'eat').unmet == '6'
    assert balances(denied)['food:west'] == '8'
    choices[-1]['access'] = 'allowed'
    choices[-1]['access_limit'] = '6'
    allowed = allocate(AllocationRequest(contract_version=1, batch=AccountBatch.model_validate(data),
        procedure='priority', claim_order=[c['id'] for c in data['claims']], choices=choices,
        mechanism_ref='authored:local-access', source_refs=[]), units())
    assert balances(allowed)['food:west'] == '2'
    assert next(c for c in allowed.accounts.claims if c.claim_id == 'eat').actual == '6'
