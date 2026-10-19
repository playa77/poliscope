"""Independent synthetic numerical expectations, not scientific evidence."""
from decimal import Decimal, localcontext
from dataclasses import FrozenInstanceError, replace
from copy import deepcopy
import itertools
import json
import pytest

from poliscope_engine.contracts.solvers import ExecutionRequest
from poliscope_engine.contracts.accounts import AccountBatch
from poliscope_engine.dependencies.solvers import execute, linear_eliminate, Failure
from poliscope_engine.dependencies import DependencyError
from poliscope_engine.mechanisms import Implementation
from poliscope_engine.numeric import parse, context
from test_dependencies import plain, request, binding, demands, demand_request, Q
from test_mechanism_registry import registry, world
from test_allocations import account, claim, choice


def host(definition, callback):
    p = definition.support.static.implementation
    return registry([definition], implementations=[Implementation(p.id, p.version, 'static', callback)])


def quantity(value):
    return dict(Q, value=str(value))


def execution(dep, **updates):
    return ExecutionRequest.model_validate(dict(contract_version=1, dependencies=dep.model_dump(),
        batch=None, claims=[], allocations=[], solvers=[], operation_limit=100000) | updates)


def values(result):
    return {k: json.loads(v).get('value') for k, v in result.values}


def statuses(result):
    return dict(result.statuses)


def loop():
    d = plain(('synthetic:in',))
    req = request(('a',), d, bindings=[binding('a', 'a')])
    return d, req


I = ['input', 'a', 'synthetic:in']
O = ['output', 'a', 'synthetic:out']


def plan(kind='iterative', **updates):
    data = dict(id='selected:solver', kind=kind, nodes=[I, O], equations=[],
        starting_state=[dict(node=k, value='0') for k in (I, O)], update_order=[I, O],
        update_mode='simultaneous', criterion='absolute_residual', tolerance='0.0000001', iteration_limit=200)
    if kind == 'linear':
        data.update(starting_state=[], update_order=[], equations=[
            dict(node=I, constant='0', terms=[dict(node=O, coefficient='1')]),
            dict(node=O, constant='1', terms=[dict(node=I, coefficient='0.5')])])
    return data | updates


def test_chain_diamond_actual_outputs_are_order_independent():
    d = plain(('synthetic:left', 'synthetic:right'), {'synthetic:out': ['synthetic:left', 'synthetic:right']})
    fixed = [dict(consumer=dict(instance_id=i, port_id=p), value=quantity(v))
             for i, p, v in [('a', 'synthetic:left', 2), ('a', 'synthetic:right', 3), ('b', 'synthetic:right', 7), ('c', 'synthetic:right', 11)]]
    links = [binding('a', 'b', 'synthetic:left', 'synthetic:out'), binding('a', 'c', 'synthetic:left', 'synthetic:out'),
             binding('b', 'd', 'synthetic:left', 'synthetic:out'), binding('c', 'd', 'synthetic:right', 'synthetic:out')]
    r = host(d, lambda port, inputs: quantity(sum(parse(v.value) for v in inputs.values())))
    expected = None
    for ids in itertools.permutations('abcd'):
        result = execute(execution(request(ids, d, bindings=links, fixed_inputs=fixed)), r, world())
        assert all(v == 'known' for v in statuses(result).values())
        assert values(result)['output', 'd', 'synthetic:out'] == '28'
        if expected is None:
            expected = result
        assert replace(result, request_json=expected.request_json) == expected


@pytest.mark.parametrize('kind', ['linear', 'iterative'])
@pytest.mark.parametrize('mode', ['simultaneous', 'sequential'])
def test_declared_coupled_solution_and_context_isolation(kind, mode):
    d, req = loop()
    r = host(d, lambda port, inputs: quantity(1 + parse(inputs['synthetic:in'].value) / 2))
    with localcontext() as ambient:
        ambient.prec = 3
        result = execute(execution(req, solvers=[plan(kind, update_mode=mode)]), r, world())
    assert all(s == 'known' for s in statuses(result).values())
    assert abs(Decimal(values(result)[tuple(O)]) - 2) <= Decimal('0.000001')
    if kind == 'linear':
        assert values(result)[tuple(O)] == '2'


@pytest.mark.parametrize('callback,solver,code', [
    (lambda p, i: quantity(parse(i['synthetic:in'].value) + 1), plan(iteration_limit=3), 'nonconvergence'),
    (lambda p, i: quantity(2), plan('linear', equations=[dict(node=I, constant='0', terms=[dict(node=O, coefficient='1')]),dict(node=O, constant='0', terms=[dict(node=I, coefficient='1')])]), 'singular_system'),
    (lambda p, i: quantity(2), plan('linear', equations=[dict(node=I, constant='0', terms=[dict(node=O, coefficient='1')]),dict(node=O, constant='1', terms=[dict(node=I, coefficient='1')])]), 'inconsistent_system'),
    (lambda p, i: quantity(7), plan('linear'), 'linear_residual_failure'),
])
def test_scoped_solver_failure(callback, solver, code):
    d, req = loop()
    result = execute(execution(req, solvers=[solver]), host(d, callback), world())
    assert set(statuses(result).values()) == {code}
    assert not result.values and result.batch_json is None


def test_missing_solver_and_blocked_dependents():
    d = plain(('synthetic:in',))
    req = request(('a', 'b'), d, bindings=[binding('a', 'a'), binding('a', 'b')])
    result = execute(execution(req), host(d, lambda *a: pytest.fail('unresolved callback')), world())
    assert statuses(result)[tuple(I)] == 'missing_solver'
    assert statuses(result)['output', 'b', 'synthetic:out'] == 'blocked'


def test_missing_keeps_independent_known_output():
    d = plain(('synthetic:in',), {'synthetic:dependent': ['synthetic:in'], 'synthetic:independent': []})
    result = execute(execution(request(('a',), d)), host(d, lambda *a: quantity(9)), world())
    assert statuses(result)['input', 'a', 'synthetic:in'] == 'missing_input'
    assert statuses(result)['output', 'a', 'synthetic:dependent'] == 'blocked'
    assert values(result)['output', 'a', 'synthetic:independent'] == '9'


@pytest.mark.parametrize('kind', ['linear', 'iterative'])
def test_budget_exhaustion_has_no_partial_component(kind):
    d, req = loop()
    result = execute(execution(req, solvers=[plan(kind)], operation_limit=1),
        host(d, lambda p, i: quantity(1 + parse(i['synthetic:in'].value) / 2)), world())
    assert set(statuses(result).values()) == {'budget_exhausted'}
    assert result.operations == 1 and not result.values


def contention(**updates):
    dep, d = demand_request()
    batch = dict(contract_version=1, accounts=[account('account', '100', scope_id='local')],
        claims=[claim(i, '100', 'account') for i in ('a', 'b')], postings=[], reservations=[], subtotals=[])
    req = execution(dep, batch=batch,
        claims=[dict(instance_id=i, claim_id='synthetic:claim', account_claim_id=i) for i in ('a', 'b')],
        allocations=[dict(id='shared', procedure='priority', claim_order=['a', 'b'],
            choices=[choice(i) for i in ('a', 'b')], mechanism_ref='selected:priority')])
    data = req.model_dump() | updates
    def callback(port, inputs):
        if port == 'synthetic:requested':
            return quantity(100)
        return quantity(parse(inputs['synthetic:allocated'].value))
    return ExecutionRequest.model_validate(data), host(d, callback)


def test_shared_supply_production_uses_actuals_and_accounts_reconcile():
    req, r = contention()
    before = req.model_dump_json()
    result = execute(req, r, world())
    v = values(result)
    assert v['output', 'a', 'synthetic:supported'] == '100'
    assert v['output', 'b', 'synthetic:supported'] == '0'
    assert sum(Decimal(v['output', i, 'synthetic:supported']) for i in ('a', 'b')) == 100
    final = AccountBatch.model_validate_json(result.batch_json)
    from poliscope_engine.accounts import AccountBook
    evaluation = AccountBook(final, r.units).evaluate()
    assert evaluation.accounts[0].closing == '0'
    assert [c.unmet for c in evaluation.claims] == ['0', '100']
    assert req.model_dump_json() == before
    with pytest.raises(FrozenInstanceError):
        result.operations = 0


@pytest.mark.parametrize('field', ['procedure', 'access', 'funding'])
def test_unknown_allocation_preserves_output_gap_and_no_final_accounts(field):
    req, r = contention()
    data = req.model_dump()
    if field == 'procedure':
        data['allocations'][0]['procedure'] = None
        data['allocations'][0]['claim_order'] = []
    elif field == 'access':
        data['allocations'][0]['choices'][0]['access'] = 'unknown'
    else:
        data['allocations'][0]['choices'][0]['funding_known'] = False
    result = execute(ExecutionRequest.model_validate(data), r, world())
    assert statuses(result)['allocation', 'shared'].startswith('allocation_unresolved:')
    assert statuses(result)['output', 'a', 'synthetic:supported'] == 'blocked'
    assert result.batch_json is None


def test_funding_caps_actual_production_and_debits_once():
    req, r = contention()
    data = req.model_dump()
    data['batch']['accounts'].append(account('funding', '30', scope_id='local', invariant='budget'))
    for c in data['allocations'][0]['choices']:
        c['requirements'] = [dict(account_id='funding', per_unit='2', kind='funding')]
    result = execute(ExecutionRequest.model_validate(data), r, world())
    assert values(result)['output', 'a', 'synthetic:supported'] == '15'
    final = AccountBatch.model_validate_json(result.batch_json)
    from poliscope_engine.accounts import AccountBook
    closes = {a.account_id: a.closing for a in AccountBook(final, r.units).evaluate().accounts}
    assert closes == {'account': '85', 'funding': '0'}


def test_feedback_allocation_remains_unresolved_without_applicable_solver():
    req, r = contention()
    dep, d = demand_request(True)
    req = req.model_copy(update={'dependencies': dep})
    result = execute(req, host(d, lambda *a: pytest.fail('cycle cannot execute')), world())
    assert statuses(result)['allocation', 'shared'] == 'missing_solver'
    assert result.batch_json is None


@pytest.mark.parametrize('mutate,code', [
    (lambda d: d['solvers'][0]['starting_state'].pop(), 'invalid_iteration_contract'),
    (lambda d: d['solvers'][0]['update_order'].append(I), 'invalid_iteration_contract'),
    (lambda d: d['solvers'][0]['nodes'].append(O), 'invalid_solver_component'),
    (lambda d: d['solvers'].append(deepcopy(d['solvers'][0])), 'invalid_solver_component'),
    (lambda d: d['solvers'][0].update(tolerance='-1'), 'invalid_tolerance'),
])
def test_invalid_solver_plan_rejected_before_execution(mutate, code):
    definition, dep = loop()
    data = execution(dep, solvers=[plan()]).model_dump()
    mutate(data)
    with pytest.raises(DependencyError, match=code):
        execute(ExecutionRequest.model_validate(data), host(definition, lambda *a: pytest.fail('invalid plan')), world())


def test_documentary_cycle_has_no_solver_and_still_executes():
    d = plain()
    dep = request(('a', 'b'), d, relationships=[dict(kind='documentary', source_instance_id=a,
        target_instance_id=b, relationship_ref='doc:' + a) for a, b in [('a', 'b'), ('b', 'a')]])
    result = execute(execution(dep), host(d, lambda *a: quantity(3)), world())
    assert set(statuses(result).values()) == {'known'}


def test_callback_failure_and_invalid_return_are_scoped():
    d = plain()
    def bad(*args):
        raise RuntimeError('private implementation detail')
    result = execute(execution(request()), host(d, bad), world())
    assert set(statuses(result).values()) == {'implementation_failure'}
    assert 'private' not in repr(result)


def test_linear_elimination_pivoting_independent_solution():
    # 2y=6; x+y=5 gives (2,3), requiring a first-column row swap.
    with localcontext(context()):
        assert linear_eliminate([[Decimal(0), Decimal(2)], [Decimal(1), Decimal(1)]],
            [Decimal(6), Decimal(5)], lambda: None) == [Decimal(2), Decimal(3)]


def test_actual_production_feeds_downstream_account_before_its_allocation():
    from poliscope_engine.contracts.world import EntityDTO
    req, r = contention()
    data = req.model_dump()
    data['dependencies']['instances'].append(dict(data['dependencies']['instances'][0], id='c'))
    data['dependencies']['claims'].append(dict(instance_id='c', claim_id='synthetic:claim', account_id='second', allocation_id='downstream'))
    data['dependencies']['account_producers'] = [dict(account_id='second', producer=dict(instance_id='a', port_id='synthetic:supported'))]
    data['claims'].append(dict(instance_id='c', claim_id='synthetic:claim', account_claim_id='c'))
    data['batch']['accounts'].append(account('second', '0', scope_id='local'))
    data['batch']['claims'].append(claim('c', '100', 'second'))
    data['allocations'].append(dict(id='downstream', procedure='priority', claim_order=['c'], choices=[choice('c')], mechanism_ref='selected:priority'))
    w = world()
    from poliscope_engine.world import WorldRegistry
    from test_mechanism_registry import PROVENANCE
    w = WorldRegistry('civ', entities=[*w.entities, EntityDTO(id='second', entity_kind='account', label='Synthetic', provenance=PROVENANCE)], scopes=w.scopes)
    result = execute(ExecutionRequest.model_validate(data), r, w)
    assert values(result)['output', 'c', 'synthetic:supported'] == '100'
    final = AccountBatch.model_validate_json(result.batch_json)
    from poliscope_engine.accounts import AccountBook
    assert {a.account_id: a.closing for a in AccountBook(final, r.units).evaluate().accounts} == {'account': '0', 'second': '0'}
    assert len([p for p in final.postings if p.kind == 'production']) == 1


@pytest.mark.parametrize('mode', ['simultaneous', 'sequential'])
def test_period_two_iteration_does_not_mistake_step_or_last_value_for_solution(mode):
    d, dep = loop()
    result = execute(execution(dep, solvers=[plan(update_mode=mode, tolerance='0', iteration_limit=8)]),
        host(d, lambda p, inputs: quantity(1 - parse(inputs['synthetic:in'].value))), world())
    assert set(statuses(result).values()) == {'nonconvergence'}
    assert not result.values


@pytest.mark.parametrize('mutation,code', [
    (lambda d: d['claims'].pop(), 'invalid_runtime_claims'),
    (lambda d: d['claims'][0].update(account_claim_id='b'), 'invalid_runtime_claims'),
    (lambda d: d['allocations'].append(deepcopy(d['allocations'][0])), 'invalid_finite_plans'),
    (lambda d: d['allocations'][0]['choices'].pop(), 'invalid_finite_choices'),
    (lambda d: d['allocations'][0].update(claim_order=['a','a']), 'invalid_claim_order'),
    (lambda d: d['batch']['accounts'][0].update(scope_id='elsewhere'), 'incompatible_runtime_account'),
    (lambda d: d.update(batch=None), 'missing_account_batch'),
])
def test_runtime_bindings_reject_ambiguous_or_incompatible_accounts(mutation, code):
    req, r = contention()
    data = req.model_dump()
    mutation(data)
    with pytest.raises(DependencyError, match=code):
        execute(ExecutionRequest.model_validate(data), r, world())


def test_physical_reservation_is_used_once_under_contention():
    req, r = contention()
    data = req.model_dump()
    data['batch']['reservations'] = [dict(id='hold:b', account_id='account', claim_id='b', amount='40')]
    result = execute(ExecutionRequest.model_validate(data), r, world())
    assert values(result)['output', 'a', 'synthetic:supported'] == '60'
    assert values(result)['output', 'b', 'synthetic:supported'] == '40'
    from poliscope_engine.accounts import AccountBook
    final = AccountBook(AccountBatch.model_validate_json(result.batch_json), r.units).evaluate()
    assert final.accounts[0].closing == final.accounts[0].outstanding_reserved == '0'


def test_declared_procedure_order_controls_distribution():
    req, r = contention()
    data = req.model_dump()
    data['allocations'][0]['claim_order'].reverse()
    result = execute(ExecutionRequest.model_validate(data), r, world())
    assert values(result)['output', 'a', 'synthetic:supported'] == '0'
    assert values(result)['output', 'b', 'synthetic:supported'] == '100'


def test_changed_or_bypassed_request_is_revalidated():
    req, r = contention()
    req = req.model_copy(update={'operation_limit': 0})
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        execute(req, r, world())


def test_fresh_review_required_on_every_execution():
    from poliscope_engine.mechanisms import MechanismError
    d = plain()
    with pytest.raises(MechanismError, match='review_required'):
        execute(execution(request()), registry([d], reviews=[]), world())


def test_finite_transformation_is_staged_from_actual_inputs():
    req, r = contention()
    data = req.model_dump()
    data['batch']['accounts'] += [account('product', '0', scope_id='local'), account('residual', '0', scope_id='local')]
    for c in data['allocations'][0]['choices']:
        c['outputs'] = [dict(account_id='product', per_unit='0.7', role='product'), dict(account_id='residual', per_unit='0.2', role='residual')]
        c['loss_per_unit'] = '0.1'
    result = execute(ExecutionRequest.model_validate(data), r, world())
    from poliscope_engine.accounts import AccountBook
    final = AccountBook(AccountBatch.model_validate_json(result.batch_json), r.units).evaluate()
    assert {a.account_id: a.closing for a in final.accounts} == {'account': '0', 'product': '70', 'residual': '20'}
    assert values(result)['output', 'b', 'synthetic:supported'] == '0'


def test_result_retains_full_solver_and_numeric_identity():
    from poliscope_engine.numeric import RUNTIME_ID
    d, dep = loop()
    req = execution(dep, solvers=[plan('linear')])
    result = execute(req, host(d, lambda p, i: quantity(1 + parse(i['synthetic:in'].value) / 2)), world())
    assert ExecutionRequest.model_validate_json(result.request_json) == req
    assert result.numeric_runtime_id == RUNTIME_ID
    assert result.model == ('synthetic:model', 'v1')
    assert result.compiler_digest.startswith('sha256:')


def test_optional_omission_is_not_an_invented_zero_or_failure():
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    d = plain(('synthetic:optional',))
    data = d.model_dump()
    data['inputs'][0].update(required=False, missing_behavior='omit')
    d = MechanismDefinition.model_validate(data)
    def callback(port, inputs):
        assert not inputs
        return quantity(4)
    result = execute(execution(request(('a',), d)), host(d, callback), world())
    assert set(statuses(result).values()) == {'known'}
    assert values(result)['output', 'a', 'synthetic:out'] == '4'


def test_unevaluated_precondition_is_visible_and_cannot_publish_accounts():
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    d = plain()
    data = d.model_dump()
    data['preconditions'] = [dict(id='synthetic:condition', input_refs=[], description='Needs orchestration', failure_behavior='conflict')]
    d = MechanismDefinition.model_validate(data)
    result = execute(execution(request(('a',), d)), host(d, lambda *a: pytest.fail('precondition not evaluated')), world())
    assert set(statuses(result).values()) == {'precondition_evaluation_required'}


def test_linear_elimination_independent_exhaustive_two_by_two_oracle():
    # Every small integer matrix, with RHS derived independently from x=2,y=3.
    for a, b, c, d in itertools.product(range(-2, 3), repeat=4):
        matrix = [[Decimal(a), Decimal(b)], [Decimal(c), Decimal(d)]]
        rhs = [Decimal(2*a + 3*b), Decimal(2*c + 3*d)]
        with localcontext(context()):
            if a*d - b*c == 0:
                with pytest.raises(Failure, match='singular_system'):
                    linear_eliminate(matrix, rhs, lambda: None)
            else:
                solution = linear_eliminate(matrix, rhs, lambda: None)
                assert abs(solution[0] - 2) < Decimal('1e-24')
                assert abs(solution[1] - 3) < Decimal('1e-24')


def split_contention():
    from poliscope_engine.contracts.world import EntityDTO
    from poliscope_engine.world import WorldRegistry
    from test_mechanism_registry import PROVENANCE
    req, r = contention()
    data = req.model_dump()
    data['dependencies']['claims'][1].update(account_id='second', allocation_id='separate')
    data['batch']['accounts'].append(account('second', '100', scope_id='local', invariant='budget'))
    data['batch']['claims'][1]['account_id'] = 'second'
    data['allocations'][0].update(claim_order=['a'], choices=[choice('a')])
    data['allocations'].append(dict(id='separate', procedure='priority', claim_order=['b'], choices=[choice('b')], mechanism_ref='selected:priority'))
    w = world()
    w = WorldRegistry('civ', entities=[*w.entities, EntityDTO(id='second', entity_kind='account', label='Synthetic', provenance=PROVENANCE)], scopes=w.scopes)
    return data, r, w


def test_separate_groups_do_not_choose_priority_over_contested_funding():
    data, r, w = split_contention()
    data['allocations'][0]['choices'][0]['requirements'] = [dict(account_id='second', per_unit='1', kind='funding')]
    result = execute(ExecutionRequest.model_validate(data), r, w)
    assert statuses(result)['allocation', 'shared'] == statuses(result)['allocation', 'separate'] == 'missing_joint_funding_procedure'
    assert result.batch_json is None


def test_separate_groups_keep_other_groups_outstanding_holds():
    data, r, w = split_contention()
    data['batch']['reservations'] = [dict(id='hold:b', account_id='second', claim_id='b', amount='50')]
    result = execute(ExecutionRequest.model_validate(data), r, w)
    assert values(result)['output', 'a', 'synthetic:supported'] == values(result)['output', 'b', 'synthetic:supported'] == '100'
    from poliscope_engine.accounts import AccountBook
    final = AccountBook(AccountBatch.model_validate_json(result.batch_json), r.units).evaluate()
    assert all(a.closing == a.outstanding_reserved == '0' for a in final.accounts)


def test_finite_transformation_dependency_precedes_downstream_account_use():
    data, r, w = split_contention()
    # Group a transforms source to group b's resource, initially empty.
    data['batch']['accounts'][1].update(opening='0', invariant='physical')
    data['allocations'][0]['choices'][0]['outputs'] = [dict(account_id='second', per_unit='1', role='product')]
    result = execute(ExecutionRequest.model_validate(data), r, w)
    assert values(result)['output', 'a', 'synthetic:supported'] == values(result)['output', 'b', 'synthetic:supported'] == '100'
    from poliscope_engine.accounts import AccountBook
    final = AccountBook(AccountBatch.model_validate_json(result.batch_json), r.units).evaluate()
    assert all(a.closing == '0' for a in final.accounts)


def test_finite_transformation_feedback_is_classified_before_execution():
    data, r, w = split_contention()
    data['batch']['accounts'][1].update(invariant='physical')
    data['allocations'][0]['choices'][0]['outputs'] = [dict(account_id='second', per_unit='1', role='product')]
    data['allocations'][1]['choices'][0]['outputs'] = [dict(account_id='account', per_unit='1', role='product')]
    result = execute(ExecutionRequest.model_validate(data), r, w)
    assert statuses(result)['allocation', 'shared'] == statuses(result)['allocation', 'separate'] == 'missing_solver'
    assert result.batch_json is None


@pytest.mark.parametrize('known', [True, False])
def test_registered_declarative_graph_uses_existing_reviewed_arithmetic(known):
    from test_expressions import setup
    r, _ = setup()
    d = r.definitions[0]
    fixed = [dict(consumer=dict(instance_id='a', port_id='synthetic:x'), value=quantity('1.25'))] if known else []
    dep = request(('a',), d, fixed_inputs=fixed)
    result = execute(execution(dep), r, world())
    if known:
        assert values(result)['output', 'a', 'synthetic:available'] == '3.75'
    else:
        assert statuses(result)['output', 'a', 'synthetic:available'] == 'blocked'
