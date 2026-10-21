"""Independent hypothetical balance/shortage oracles, never refreshed goldens."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.provisioning import ProvisioningRequest
from poliscope_engine.domains.provisioning.chain import evaluate_chain
from poliscope_engine.numeric import Registry, Unit, NumericError

MODEL = 'authored:provisioning-chain-v1'


def units():
    return Registry(tuple(Unit(name, ((dimension, 1),), kind, Decimal(1))
        for name, dimension, kind in [('kg', 'mass', 'stock'),
            ('throughput', 'mass', 'capacity'), ('hours', 'time', 'capacity'),
            ('land-days', 'area-time', 'capacity'), ('energy', 'energy', 'capacity')]))


def account(aid, opening, scope='east', unit='kg'):
    stock = unit == 'kg'
    return dict(contract_version=1, id=aid, kind='stock' if stock else 'capacity',
        unit_id=unit, scope_id=scope, period_id=None if stock else 'day:0',
        invariant='physical' if stock else 'budget', quantum='0.1' if unit == 'hours' else '1', maximum='1000',
        opening=str(opening), source_refs=[MODEL])


def claim(cid, aid, amount):
    return dict(id=cid, account_id=aid, claimant_id='group:' + cid,
        requested=str(amount), source_refs=[MODEL])


def requirement(aid, rate='1', kind='funding'):
    return dict(account_id=aid, per_unit=rate, kind=kind)


def choice(cid, requirements=(), outputs=(), loss='0'):
    return dict(claim_id=cid, access='allowed', access_limit='1000', funding_known=True,
        requirements=list(requirements), outputs=list(outputs), loss_per_unit=loss,
        mechanism_ref=MODEL, source_refs=[MODEL])


def output(aid, rate, role='product'):
    return dict(account_id=aid, per_unit=rate, role=role)


def phase(pid, kind, claims, **extra):
    return dict(id=pid, kind=kind, claims=claims, reservations=[], procedure='priority',
        claim_order=[c['id'] for c in claims], mechanism_ref=MODEL, source_refs=[MODEL], **extra)


def request():
    accounts = [account('raw', 20), account('product', 0), account('residual', 0),
        account('receiving', 0, 'west'), account('stored', 0, 'west'),
        account('labor', 12, unit='hours'), account('land', 4, unit='land-days'),
        account('energy', 20, unit='energy'), account('truck', 10, unit='throughput'),
        account('handling', 3, 'west', 'throughput'), account('rights', 2, 'west', 'throughput')]
    return dict(contract_version=1, period_id='day:0',
        batch=dict(contract_version=1, accounts=accounts, claims=[], postings=[], reservations=[], subtotals=[]),
        resources=[dict(account_id=a, resource_id=r) for a, r in [
            ('raw', 'unprocessed'), ('product', 'food'), ('residual', 'byproduct'),
            ('receiving', 'food'), ('stored', 'food')]],
        phases=[phase('make', 'production', [claim('make-food', 'raw', 30)],
            choices=[choice('make-food', [requirement('labor', '0.5'),
                requirement('land', '0.2'), requirement('energy')],
                [output('product', '0.7'), output('residual', '0.2', 'residual')], '0.1')]),
            phase('deliver', 'freight', [claim('ship-food', 'product', 10)],
                routes=[dict(claim_id='ship-food', destination_id='receiving', capacity_id='truck',
                    capacity_per_unit='1', access='allowed', access_limit='10', funding_known=True,
                    requirements=[requirement('labor', '0.5')], mechanism_ref=MODEL, source_refs=[MODEL])]),
            phase('store', 'storage', [claim('store-food', 'receiving', 10)],
                choices=[choice('store-food', [requirement('handling')], [output('stored', '1')])]),
            phase('eat', 'use', [claim('eat-food', 'stored', 6)],
                choices=[choice('eat-food', [requirement('rights', kind='entitlement')])])])


def run(data=None):
    return evaluate_chain(ProvisioningRequest.model_validate(data or request()), units())


def balances(result):
    return {a.account_id: a.closing for a in result.accounts.accounts}


def set_opening(data, aid, amount):
    next(a for a in data['batch']['accounts'] if a['id'] == aid)['opening'] = str(amount)


def test_full_chain_literal_oracle_and_shared_labor():
    data = request()
    before = deepcopy(data)
    result = run(data)
    assert data == before and result.status == 'resolved'
    assert balances(result) == dict(raw='0', product='10', residual='4', receiving='1', stored='1',
        labor='0', land='0', energy='0', truck='6', handling='0', rights='0')
    assert {c.claim_id: (c.actual, c.unmet) for c in result.accounts.claims} == {
        'make-food': ('20', '10'), 'ship-food': ('4', '6'),
        'store-food': ('3', '7'), 'eat-food': ('2', '4')}
    make = result.phases[0].evidence.actuals[0]
    assert (make.allocated, make.outputs, make.loss) == ('20', ['14', '4'], '2')
    # Independent mass balance includes consumed food and declared process loss.
    b = balances(result)
    assert sum(Fraction(b[a]) for a in ['raw', 'product', 'residual', 'receiving', 'stored']) + 2 + 2 == 20
    movement = result.phases[1].evidence.movements[0]
    posts = {p.id: p for p in result.batch.postings}
    assert sum(Fraction(posts[p].amount) for p in movement.export_posting_ids) == 4
    assert posts[movement.import_posting_id].amount == '4'
    # Every phase retains full prior history, while new results are increments.
    assert [len(p.evidence.batch.claims) for p in result.phases] == [1, 2, 3, 4]
    assert next(a for a in result.phases[2].evidence.actuals if a.claim_id == 'make-food').allocated == '0'


@pytest.mark.parametrize('aid,value,production,delivery', [
    ('raw', 10, '10', '7'), ('labor', 9, '10', '7'),
    ('land', 3, '10', '7'), ('energy', 15, '10', '7'), ('truck', 0, '20', '0')])
def test_each_finite_upstream_port_constrains_actual_outputs(aid, value, production, delivery):
    data = request()
    set_opening(data, aid, value)
    result = run(data)
    assert result.phases[0].evidence.actuals[0].allocated == production
    assert result.phases[1].evidence.movements[0].delivered == delivery
    if aid == 'truck':
        assert balances(result)['product'] == '14'
        assert next(c for c in result.accounts.claims if c.claim_id == 'eat-food').unmet == '6'


@pytest.mark.parametrize('kind', ['freight', 'storage', 'use'])
def test_denied_access_leaves_stock_and_unmet_demand_visible(kind):
    data = request()
    selected = next(p for p in data['phases'] if p['kind'] == kind)
    selected['routes' if kind == 'freight' else 'choices'][0]['access'] = 'denied'
    result = run(data)
    assert next(c for c in result.accounts.claims if c.claim_id == 'eat-food').actual == '0'
    assert balances(result)[{'freight': 'product', 'storage': 'receiving', 'use': 'stored'}[kind]] == {
        'freight': '14', 'storage': '4', 'use': '3'}[kind]


@pytest.mark.parametrize('stage,missing', product(range(4), ['procedure', 'access', 'funding']))
def test_unknown_anywhere_withholds_complete_candidate(stage, missing):
    data = request()
    selected = data['phases'][stage]
    selected_choice = selected['routes' if selected['kind'] == 'freight' else 'choices'][0]
    if missing == 'procedure': selected['procedure'] = None
    if missing == 'access': selected_choice['access'] = 'unknown'
    if missing == 'funding': selected_choice['funding_known'] = False
    before = deepcopy(data)
    result = run(data)
    assert data == before
    assert result.status == 'unresolved' and result.batch is None and result.accounts is None
    assert result.blocked_phase_id == selected['id'] and len(result.phases) == stage + 1
    evidence = result.phases[-1].evidence
    allocation = evidence.allocation if selected['kind'] == 'freight' else evidence
    assert missing in allocation.missing


def test_reservation_fulfillment_once_and_remaining_hold_is_not_released():
    data = request()
    data['phases'][0]['reservations'] = [dict(id='hold-raw', account_id='raw', claim_id='make-food', amount='20')]
    data['phases'][1]['reservations'] = [dict(id='hold-delivery', account_id='product', claim_id='ship-food', amount='8')]
    result = run(data)
    held = {a.account_id: a.outstanding_reserved for a in result.accounts.accounts}
    assert held['raw'] == '0' and held['product'] == '4'
    assert sum(Fraction(p.amount) for p in result.batch.postings if p.reservation_id == 'hold-delivery') == 4
    assert next(c for c in result.accounts.claims if c.claim_id == 'ship-food').actual == '4'


def test_prior_claims_and_actuals_are_closed_and_never_reproduced():
    data = request()
    data['batch']['claims'] = [claim('old', 'raw', 8)]
    data['batch']['postings'] = [dict(id='old-use', kind='use', source_id='raw', destination_id=None,
        amount='4', claim_id='old', reservation_id='old-hold', mechanism_ref=MODEL, source_refs=[MODEL])]
    data['batch']['reservations'] = [dict(id='old-hold', account_id='raw', claim_id='old', amount='6')]
    result = run(data)
    assert next(c for c in result.accounts.claims if c.claim_id == 'old').actual == '4'
    assert sum(p.claim_id == 'old' for p in result.batch.postings) == 1
    assert result.phases[0].evidence.actuals[0].allocated == '10'  # 14 free, 10 representable
    assert next(a for a in result.accounts.accounts if a.account_id == 'raw').outstanding_reserved == '2'


def test_whole_candidate_rejected_for_late_storage_overflow():
    data = request()
    next(a for a in data['batch']['accounts'] if a['id'] == 'stored')['maximum'] = '2'
    before = deepcopy(data)
    with pytest.raises(NumericError, match='invalid_balance'): run(data)
    assert data == before


@pytest.mark.parametrize('change,code', [
    ('period', 'incompatible_provisioning_period'), ('duplicate-phase', 'duplicate_phase'),
    ('old-order', 'invalid_claim_order'), ('duplicate-claim', 'duplicate_identity'),
    ('resource', 'incompatible_storage_resource'), ('missing-resource', 'invalid_resource_bindings'),
    ('duplicate-resource', 'invalid_resource_bindings'), ('yield', 'transformation_conservation_failure'),
    ('no-yield', 'missing_production_yields'), ('use-output', 'invalid_use_outputs'),
    ('decay', 'invalid_storage_outputs'), ('capacity-stock', 'invalid_provisioning_stock'),
    ('foreign-hold', 'incompatible_reservation'), ('output-scope', 'incompatible_transformation_output'),
    ('recycle', 'coupled_allocation_requires_solver')])
def test_invalid_interfaces_reject_without_mutation(change, code):
    data = request()
    if change == 'period': data['period_id'] = 'day:1'
    if change == 'duplicate-phase': data['phases'][1]['id'] = 'make'
    if change == 'old-order': data['phases'][-1]['claim_order'].append('make-food')
    if change == 'duplicate-claim':
        data['phases'][1]['claims'][0]['id'] = 'make-food'
        data['phases'][1]['claim_order'] = ['make-food']
    if change == 'resource': data['resources'][-1]['resource_id'] = 'different'
    if change == 'missing-resource': data['resources'].pop()
    if change == 'duplicate-resource': data['resources'].append(data['resources'][0])
    if change == 'yield': data['phases'][0]['choices'][0]['outputs'][0]['per_unit'] = '0.8'
    if change == 'no-yield':
        data['phases'][0]['choices'][0].update(outputs=[], loss_per_unit='0')
    if change == 'use-output': data['phases'][-1]['choices'][0]['outputs'] = [output('raw', '1')]
    if change == 'decay': data['phases'][2]['choices'][0]['loss_per_unit'] = '0.1'
    if change == 'capacity-stock': data['phases'][0]['claims'][0]['account_id'] = 'labor'
    if change == 'foreign-hold': data['phases'][0]['reservations'] = [dict(id='bad-hold', account_id='product', claim_id='make-food', amount='2')]
    if change == 'output-scope': next(a for a in data['batch']['accounts'] if a['id'] == 'product')['scope_id'] = 'west'
    if change == 'recycle': data['phases'][2]['choices'][0]['outputs'][0]['account_id'] = 'product'
    # Recycling must still have the same resource, so rejection comes from the
    # dependency guard rather than invented list-order/fixed-point semantics.
    before = deepcopy(data)
    with pytest.raises(AccountError, match=code): run(data)
    assert data == before


def test_integer_oracle_for_shared_production_and_delivery_labor():
    # Exhaust feasible integer production (input multiples of 10) and delivery.
    # Explicit production-first priority maximizes input, then delivered output.
    for raw, labor, truck in product([0, 10, 20], [0, 4, 9, 12], [0, 3, 10]):
        data = request()
        for aid, value in [('raw', raw), ('labor', labor), ('truck', truck)]: set_opening(data, aid, value)
        feasible = [(n, d) for n in range(0, raw + 1, 10) for d in range(11)
            if n <= 20 and d <= n * 7 // 10 and d <= truck and n + d <= 2 * labor]
        expected = max(feasible)
        result = run(data)
        assert (int(result.phases[0].evidence.actuals[0].allocated),
            int(result.phases[1].evidence.movements[0].delivered)) == expected
        assert int(balances(result)['stored']) == max(0, min(expected[1], 3) - 2)


def test_fractional_inputs_outputs_and_ambient_precision():
    data = request()
    for a in data['batch']['accounts']: a['quantum'] = '0.01'
    set_opening(data, 'raw', '0.3')
    with localcontext() as ctx:
        ctx.prec = 2
        result = run(data)
    make = result.phases[0].evidence.actuals[0]
    assert (make.allocated, make.outputs, make.loss) == ('0.3', ['0.21', '0.06'], '0.03')
    assert next(c for c in result.accounts.claims if c.claim_id == 'eat-food').actual == '0.2'
    assert balances(result)['product'] == '0.01'  # crew quantum forbids the next 0.01 shipment


def test_dto_and_all_stage_snapshots_are_detached():
    dto = ProvisioningRequest.model_validate(request())
    result = evaluate_chain(dto, units())
    dto.phases[0].source_refs.append('later')
    assert result.request.phases[0].source_refs == [MODEL]
    result.phases[0].evidence.batch.claims.clear()
    assert len(result.batch.claims) == 4
    dto.phases.append(dto.phases[0])
    with pytest.raises(AccountError, match='duplicate_phase'): evaluate_chain(dto, units())


@pytest.mark.parametrize('value', [0.1, 'NaN', 'Infinity'])
def test_nonfinite_or_binary_float_coefficients_are_rejected(value):
    data = request()
    data['phases'][0]['choices'][0]['loss_per_unit'] = value
    with pytest.raises((ValidationError, NumericError)): run(data)


def test_phase_count_bound_is_enforced():
    data = request()
    data['phases'] *= 9
    with pytest.raises(ValidationError): run(data)


@pytest.mark.parametrize('stage', range(4))
def test_missing_procedure_with_no_order_remains_unresolved(stage):
    data = request()
    data['phases'][stage].update(procedure=None, claim_order=[])
    result = run(data)
    assert result.status == 'unresolved' and result.batch is None
    assert result.blocked_phase_id == data['phases'][stage]['id']


def test_explicit_all_or_nothing_prevents_partial_use():
    data = request()
    data['phases'][-1]['procedure'] = 'all_or_nothing'
    result = run(data)
    assert balances(result)['stored'] == '3' and balances(result)['rights'] == '2'
    assert next(c for c in result.accounts.claims if c.claim_id == 'eat-food').actual == '0'


def test_two_local_groups_compete_for_one_canonical_entitlement():
    data = request()
    local = data['phases'][-1]
    local['claims'].append(claim('eat-other', 'stored', 2))
    local['claims'][0]['requested'] = '2'
    local['choices'].append(choice('eat-other', [requirement('rights', kind='entitlement')]))
    local['claim_order'] = ['eat-other', 'eat-food']
    result = run(data)
    claims = {c.claim_id: c.actual for c in result.accounts.claims}
    assert claims['eat-other'] == '2' and claims['eat-food'] == '0'
    local['claim_order'].reverse()
    claims = {c.claim_id: c.actual for c in run(data).accounts.claims}
    assert claims['eat-other'] == '0' and claims['eat-food'] == '2'


def test_unknown_local_competitor_cannot_advantage_known_group():
    data = request()
    local = data['phases'][-1]
    local['claims'].append(claim('eat-other', 'stored', 2))
    local['choices'].append(choice('eat-other'))
    local['choices'][-1]['access'] = 'unknown'
    local['claim_order'].append('eat-other')
    result = run(data)
    assert result.batch is None
    assert all(a.allocated == '0' for a in result.phases[-1].evidence.actuals)


def test_production_claims_compete_globally_and_yield_only_actual_inputs():
    data = request()
    make = data['phases'][0]
    make['claims'].append(claim('other-maker', 'raw', 20))
    other = deepcopy(make['choices'][0])
    other['claim_id'] = 'other-maker'
    make['choices'].append(other)
    make['claim_order'] = ['other-maker', 'make-food']
    result = run(data)
    actuals = {a.claim_id: a for a in result.phases[0].evidence.actuals}
    assert actuals['other-maker'].allocated == '20'
    assert actuals['other-maker'].outputs == ['14', '4']
    assert actuals['make-food'].allocated == '0' and actuals['make-food'].outputs == ['0', '0']
    assert balances(result)['product'] == '10'


def test_repeating_pure_plan_reproduces_without_input_mutation():
    dto = ProvisioningRequest.model_validate(request())
    before = dto.model_dump_json()
    assert evaluate_chain(dto, units()).model_dump_json() == evaluate_chain(dto, units()).model_dump_json()
    assert dto.model_dump_json() == before
