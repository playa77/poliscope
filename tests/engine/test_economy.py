"""Independent hypothetical access/time oracles; no empirical social claims."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.economy import EconomyRequest
from poliscope_engine.contracts.allocations import AllocationRequest, FundingRequirement
from poliscope_engine.contracts.provisioning import ProvisioningRequest
from poliscope_engine.domains.economy import compile_choices, evaluate_economy
from poliscope_engine.domains.provisioning.chain import evaluate_chain
from poliscope_engine.numeric import Registry, Unit, NumericError

MODEL = 'authored:economy-access-work-v1'


def units():
    return Registry(tuple(Unit(name, ((dimension, 1),), kind, Decimal(1))
        for name, dimension, kind in [('kg', 'mass', 'stock'),
            ('rights', 'entitlement', 'capacity'), ('coins', 'currency', 'stock'),
            ('hours', 'time', 'capacity')]))


def account(aid, opening, scope='east', unit='kg'):
    capacity = unit in ('rights', 'hours')
    return dict(contract_version=1, id=aid, kind='capacity' if capacity else 'stock',
        unit_id=unit, scope_id=scope, period_id='day:0' if capacity else None,
        invariant='physical' if unit == 'kg' else 'budget', quantum='1',
        maximum='1000', opening=str(opening), source_refs=[MODEL])


def claim(cid, aid, amount, claimant):
    return dict(id=cid, account_id=aid, claimant_id=claimant,
        requested=str(amount), source_refs=[MODEL])


def holder(aid, owner, role='entitlement'):
    return dict(account_id=aid, holder_id=owner, role=role)


def activity(cid, kind='goods', **changes):
    return dict(claim_id=cid, kind=kind, eligibility='allowed', access_limit='1000',
        terms_known=True, requirements=[], mechanism_ref=MODEL, source_refs=[MODEL]) | changes


def requirement(aid, rate='1', kind='entitlement'):
    return dict(account_id=aid, per_unit=rate, kind=kind)


def request():
    return dict(contract_version=1, period_id='day:0', batch=dict(contract_version=1,
        accounts=[account('east:food', 10), account('west:food', 100, 'west'),
            account('rights:a', 10, unit='rights'), account('rights:b', 10, unit='rights')],
        claims=[claim('a', 'east:food', 12, 'cohort:a'), claim('b', 'east:food', 8, 'cohort:b')],
        postings=[], reservations=[], subtotals=[]),
        holders=[holder('rights:a', 'cohort:a'), holder('rights:b', 'cohort:b')],
        activities=[activity('a', requirements=[requirement('rights:a')]),
                    activity('b', requirements=[requirement('rights:b')])],
        procedure='priority', claim_order=['a', 'b'], mechanism_ref=MODEL,
        source_refs=['synthetic:economy'])


def run(data=None):
    return evaluate_economy(EconomyRequest.model_validate(data or request()), units())


def actuals(result):
    return {a.claim_id: (a.allocated, a.unmet, a.reason) for a in result.allocation.actuals}


def balances(result):
    return {a.account_id: a.closing for a in result.allocation.accounts.accounts}


def test_explicit_procedures_change_distribution_without_creating_supply():
    data = request()
    before = deepcopy(data)
    priority = run(data)
    assert actuals(priority) == {'a': ('10', '2', 'limited'), 'b': ('0', '8', 'limited')}
    data['procedure'] = 'all_or_nothing'
    whole = run(data)
    assert actuals(whole) == {'a': ('0', '12', 'limited'), 'b': ('8', '0', 'satisfied')}
    assert balances(priority) == {'east:food': '0', 'west:food': '100', 'rights:a': '0', 'rights:b': '10'}
    assert balances(whole) == {'east:food': '2', 'west:food': '100', 'rights:a': '10', 'rights:b': '2'}
    assert priority.request.model_dump() == before
    assert priority.batch == priority.allocation.batch


def test_stock_exists_without_entitlement_or_eligibility():
    data = request()
    data['batch']['accounts'][2]['opening'] = '0'
    data['activities'][1]['eligibility'] = 'denied'
    result = run(data)
    assert actuals(result) == {'a': ('0', '12', 'limited'), 'b': ('0', '8', 'denied')}
    assert balances(result)['east:food'] == '10'
    assert balances(result)['west:food'] == '100'


@pytest.mark.parametrize('field,missing', [('procedure', 'procedure'),
    ('eligibility', 'access'), ('terms_known', 'funding')])
def test_unspecified_rules_block_all_competitors_without_candidate(field, missing):
    data = request()
    if field == 'procedure':
        data[field] = None
        data['claim_order'] = []
    else:
        data['activities'][1][field] = 'unknown' if field == 'eligibility' else False
    result = run(data)
    assert result.status == 'unresolved' and result.batch is None
    assert result.allocation.missing == [missing]
    assert all(a.reason == 'unresolved' for a in result.allocation.actuals)
    assert result.allocation.batch.postings == []
    assert balances(result)['east:food'] == '10'


def work_request():
    data = request()
    kinds = ['paid_work', 'unpaid_work', 'care', 'training', 'participation']
    data['batch']['accounts'] = [account('time:a', 10, unit='hours'),
        account('time:b', 4, 'west', 'hours')]
    data['batch']['claims'] = [claim(k, 'time:a', 3, 'cohort:a') for k in kinds]
    data['batch']['claims'].append(claim('west:care', 'time:b', 6, 'cohort:b'))
    data['holders'] = [holder('time:a', 'cohort:a', 'time'), holder('time:b', 'cohort:b', 'time')]
    data['activities'] = [activity(k, k) for k in kinds] + [activity('west:care', 'care')]
    data['claim_order'] = [*kinds, 'west:care']
    return data


def test_five_work_categories_share_one_dated_cohort_budget():
    result = run(work_request())
    assert actuals(result) == {'paid_work': ('3', '0', 'satisfied'),
        'unpaid_work': ('3', '0', 'satisfied'), 'care': ('3', '0', 'satisfied'),
        'training': ('1', '2', 'limited'), 'participation': ('0', '3', 'limited'),
        'west:care': ('4', '2', 'limited')}
    assert balances(result) == {'time:a': '0', 'time:b': '0'}
    assert {a.kind for a in result.request.activities} == {
        'paid_work', 'unpaid_work', 'care', 'training', 'participation'}
    assert all(p.kind == 'use' and p.destination_id is None for p in result.batch.postings)


def test_explicit_work_precedence_and_storage_permutations():
    data = work_request()
    data['claim_order'].reverse()
    result = run(data)
    assert actuals(result)['paid_work'] == ('0', '3', 'limited')
    assert actuals(result)['participation'] == ('3', '0', 'satisfied')
    for items in [data['activities'], data['holders'], data['batch']['claims'], data['batch']['accounts']]:
        items.reverse()
    assert run(data).batch.postings == result.batch.postings
    assert actuals(run(data)) == actuals(result)


def test_funding_and_rights_are_separate_and_neither_produces_goods():
    data = request()
    data['batch']['accounts'].append(account('funds:a', 6, unit='coins'))
    data['holders'].append(holder('funds:a', 'cohort:a', 'funding'))
    data['activities'][0]['requirements'].append(requirement('funds:a', '2', 'funding'))
    result = run(data)
    assert actuals(result)['a'] == ('3', '9', 'limited')
    assert actuals(result)['b'] == ('7', '1', 'limited')
    assert balances(result)['funds:a'] == '0' and balances(result)['rights:a'] == '7'
    data['batch']['accounts'][0]['opening'] = '0'
    data['batch']['accounts'][-1]['opening'] = '1000'
    assert all(a.allocated == '0' for a in run(data).allocation.actuals)


def test_holds_and_prior_actuals_are_preserved_not_spent_twice():
    data = request()
    data['batch']['reservations'] = [dict(id='hold:b', account_id='east:food', claim_id='b', amount='6')]
    data['batch']['postings'] = [dict(id='past', kind='use', source_id='east:food',
        destination_id=None, amount='2', claim_id='b', reservation_id='hold:b',
        mechanism_ref='past:model', source_refs=['past:source'])]
    result = run(data)
    assert actuals(result)['a'] == ('4', '8', 'limited')
    assert actuals(result)['b'] == ('4', '2', 'limited')
    assert result.batch.postings[0].model_dump() == data['batch']['postings'][0]
    assert next(c for c in result.allocation.accounts.claims if c.claim_id == 'b').actual == '6'
    assert balances(result)['rights:b'] == '6'
    replay = deepcopy(data)
    replay['batch'] = result.batch.model_dump()
    assert run(replay).batch.postings == result.batch.postings


def test_quantum_remainder_stays_in_explicit_budgets():
    data = request()
    data['batch']['accounts'][0].update(opening='10', quantum='0.1')
    data['activities'][0]['requirements'][0]['per_unit'] = '3'
    data['activities'][1]['eligibility'] = 'denied'
    data['batch']['claims'][0]['requested'] = '1.3'
    result = run(data)
    assert actuals(result)['a'] == ('1', '0.3', 'limited')
    assert balances(result)['east:food'] == '9' and balances(result)['rights:a'] == '7'


@pytest.mark.parametrize('change,code', [
    ('duplicate_holder', 'duplicate_economy_holder'), ('foreign_holder', 'invalid_economy_term_holder'),
    ('foreign_role', 'invalid_economy_term_holder'), ('unknown_holder', 'unknown_account'),
    ('physical_budget', 'invalid_economy_budget'), ('wrong_period', 'incompatible_economy_period'),
    ('foreign_scope', 'incompatible_requirement'), ('duplicate_activity', 'invalid_economy_activities'),
    ('missing_activity', 'invalid_economy_activities'), ('duplicate_term', 'duplicate_requirement'),
    ('negative_limit', 'negative_quantity'), ('zero_rate', 'incompatible_requirement'),
    ('bad_order', 'invalid_claim_order'), ('bad_goods', 'invalid_economy_goods')])
def test_invalid_goods_interfaces_reject_without_mutation(change, code):
    data = request()
    if change == 'duplicate_holder': data['holders'].append(data['holders'][0])
    if change == 'foreign_holder': data['holders'][0]['holder_id'] = 'cohort:b'
    if change == 'foreign_role': data['holders'][0]['role'] = 'funding'
    if change == 'unknown_holder': data['holders'][0]['account_id'] = 'missing'
    if change == 'physical_budget': data['holders'][0]['account_id'] = 'east:food'
    if change == 'wrong_period': data['batch']['accounts'][2]['period_id'] = 'day:1'
    if change == 'foreign_scope': data['batch']['accounts'][2]['scope_id'] = 'west'
    if change == 'duplicate_activity': data['activities'].append(data['activities'][0])
    if change == 'missing_activity': data['activities'].pop()
    if change == 'duplicate_term': data['activities'][0]['requirements'] *= 2
    if change == 'negative_limit': data['activities'][0]['access_limit'] = '-1'
    if change == 'zero_rate': data['activities'][0]['requirements'][0]['per_unit'] = '0'
    if change == 'bad_order': data['claim_order'] = ['a']
    if change == 'bad_goods': data['batch']['accounts'][0]['period_id'] = 'day:0'
    before = deepcopy(data)
    with pytest.raises(AccountError, match=code): run(data)
    assert data == before


@pytest.mark.parametrize('change,code', [
    ('second_budget', 'duplicate_cohort_time_budget'), ('wrong_owner', 'invalid_economy_time_owner'),
    ('wrong_dimension', 'invalid_economy_time'), ('wrong_role', 'invalid_economy_time_owner'),
    ('time_as_term', 'invalid_economy_term_holder'), ('wrong_period', 'incompatible_economy_period')])
def test_time_authority_conflicts_cannot_create_another_workforce(change, code):
    data = work_request()
    if change == 'second_budget': data['holders'][1]['holder_id'] = 'cohort:a'
    if change == 'wrong_owner': data['batch']['claims'][0]['claimant_id'] = 'cohort:b'
    if change == 'wrong_dimension': data['batch']['accounts'][0]['unit_id'] = 'rights'
    if change == 'wrong_role': data['holders'][0]['role'] = 'funding'
    if change == 'time_as_term': data['activities'][0]['requirements'] = [requirement('time:a', kind='funding')]
    if change == 'wrong_period': data['period_id'] = 'day:1'
    with pytest.raises(AccountError, match=code): run(data)


def test_two_scopes_cannot_pool_unreachable_stock_or_transfer_rights():
    data = request()
    data['batch']['claims'][1]['account_id'] = 'west:food'
    data['batch']['accounts'][3]['scope_id'] = 'west'
    result = run(data)
    assert actuals(result)['a'][0] == '10' and actuals(result)['b'][0] == '8'
    assert balances(result)['west:food'] == '92'
    data['activities'][0]['requirements'] = [requirement('rights:b')]
    with pytest.raises(AccountError, match='invalid_economy_term_holder'): run(data)


def test_compiled_economy_choices_drive_actual_provisioning_use():
    data = request()
    choices = compile_choices(EconomyRequest.model_validate(data), units())
    chain = dict(contract_version=1, period_id=data['period_id'], batch=data['batch'] | {'claims': []},
        resources=[dict(account_id=a, resource_id='food') for a in ['east:food', 'west:food']],
        phases=[dict(id='consume', kind='use', claims=data['batch']['claims'], reservations=[],
            procedure=data['procedure'], claim_order=data['claim_order'],
            choices=[c.model_dump() for c in choices], mechanism_ref=MODEL, source_refs=['synthetic:paired'])])
    paired = evaluate_chain(ProvisioningRequest.model_validate(chain), units())
    assert paired.batch == run(data).batch
    assert {a.account_id: a.closing for a in paired.accounts.accounts} == balances(run(data))
    assert {c.claim_id: (c.actual, c.unmet) for c in paired.accounts.claims} == {
        'a': ('10', '2'), 'b': ('0', '8')}


def test_provenance_detachment_and_nested_mutation_validation():
    dto = EconomyRequest.model_validate(request())
    result = evaluate_economy(dto, units())
    dto.activities[0].source_refs.append('later:edit')
    assert result.request.activities[0].source_refs == [MODEL]
    assert all(p.mechanism_ref == MODEL and p.source_refs == [MODEL] for p in result.batch.postings)
    result.batch.postings.clear()
    assert evaluate_economy(dto, units()).batch.postings
    dto.holders.append(dto.holders[0])
    with pytest.raises(AccountError, match='duplicate_economy_holder'): evaluate_economy(dto, units())


def test_care_and_training_compete_with_actual_production_and_freight():
    from test_provisioning_chain import request as chain_request, units as chain_units
    chain = chain_request()
    claims = [claim('care', 'labor', 3, 'shared:cohort'),
              claim('training', 'labor', 3, 'shared:cohort')]
    data = dict(contract_version=1, period_id='day:0',
        batch=chain['batch'] | {'claims': claims},
        holders=[holder('labor', 'shared:cohort', 'time')],
        activities=[activity('care', 'care'), activity('training', 'training')],
        procedure='priority', claim_order=['care', 'training'],
        mechanism_ref=MODEL, source_refs=[MODEL])
    work = evaluate_economy(EconomyRequest.model_validate(data), chain_units())
    assert balances(work)['labor'] == '6'
    chain['batch'] = work.batch.model_dump()
    result = evaluate_chain(ProvisioningRequest.model_validate(chain), chain_units())
    by_claim = {c.claim_id: c.actual for c in result.accounts.claims}
    # 12 h - 3 h care - 3 h training = 6 h. Whole-kg output lattice
    # permits 10 kg input (5 h); the final 1 h delivers 2 kg at .5 h/kg.
    assert by_claim == {'care': '3', 'training': '3', 'make-food': '10',
        'ship-food': '2', 'store-food': '2', 'eat-food': '2'}
    assert next(a for a in result.accounts.accounts if a.account_id == 'labor').closing == '0'
    assert result.batch.postings[:2] == work.batch.postings


@pytest.mark.parametrize('access', ['allowed', 'unknown'])
def test_only_explicitly_closed_time_claims_can_fund_a_later_phase(access):
    from poliscope_engine.allocations import allocate
    data = request()
    data['batch']['accounts'].append(account('labor', 5, unit='hours'))
    data['batch']['claims'].append(claim('care', 'labor', 3, 'cohort:a'))
    choices = compile_choices(EconomyRequest.model_validate(data | {
        'batch': data['batch'] | {'claims': data['batch']['claims'][:2]}}), units())
    choices[0] = choices[0].model_copy(update={
        'requirements': [*choices[0].requirements,
            FundingRequirement(account_id='labor', per_unit='1', kind='funding')]})
    choices.append(choices[1].model_copy(update={'claim_id': 'care', 'access': access,
        'requirements': []}))
    with pytest.raises(AccountError, match='coupled_allocation_requires_solver'):
        allocate(AllocationRequest(contract_version=1, batch=data['batch'], procedure='priority',
            claim_order=['care', 'a', 'b'], choices=choices, mechanism_ref=MODEL,
            source_refs=[MODEL]), units())


@pytest.mark.parametrize('field,value', [('contract_version', 2), ('procedure', 'market'),
    ('claim_order', 'a'), ('period_id', None)])
def test_strict_contract(field, value):
    data = request()
    data[field] = value
    with pytest.raises(ValidationError): run(data)


def test_numeric_strings_and_work_categories_are_explicit():
    data = request()
    data['activities'][0]['access_limit'] = 0.1
    with pytest.raises(ValidationError): run(data)
    data['activities'][0]['access_limit'] = '1'
    data['activities'][0]['kind'] = 'employment_rate'
    with pytest.raises(ValidationError): run(data)


def test_model_construct_and_nested_dicts_do_not_bypass_validation():
    dto = EconomyRequest.model_validate(request())
    dto.activities[0].requirements.append(dict(account_id='rights:a', per_unit=2, kind='entitlement'))
    with pytest.warns(UserWarning, match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError): evaluate_economy(dto, units())


def test_compiler_revalidates_scope_and_returns_detached_terms():
    dto = EconomyRequest.model_validate(request())
    choices = compile_choices(dto, units())
    choices[0].source_refs.append('later')
    assert dto.activities[0].source_refs == [MODEL]
    dto.batch.accounts[2] = dto.batch.accounts[2].model_copy(update={'scope_id': 'west'})
    with pytest.raises(AccountError, match='incompatible_requirement'): compile_choices(dto, units())


def test_independent_small_integer_feasible_set_oracle():
    for supply, rights_a, rights_b in product(range(4), repeat=3):
        data = request()
        data['batch']['accounts'][0]['opening'] = str(supply)
        data['batch']['accounts'][2]['opening'] = str(rights_a)
        data['batch']['accounts'][3]['opening'] = str(rights_b)
        feasible = [(a, b) for a, b in product(range(4), repeat=2)
                    if a + b <= supply and a <= rights_a and b <= rights_b]
        expected = max(feasible)
        with localcontext() as context:
            context.prec = 3
            result = run(data)
        assert tuple(int(actuals(result)[c][0]) for c in ['a', 'b']) == expected
        assert Fraction(balances(result)['east:food']) + sum(expected) == supply


def test_overflow_rejects_without_changing_request():
    data = request()
    data['batch']['accounts'][0]['opening'] = '1001'
    before = deepcopy(data)
    with pytest.raises(NumericError, match='invalid_balance'): run(data)
    assert data == before
