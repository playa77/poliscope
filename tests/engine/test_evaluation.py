"""Synthetic integration and independent identity/purity expectations."""
from dataclasses import replace
from copy import deepcopy
import json
import builtins
import random
import socket
import sqlite3
import time
from itertools import permutations
import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.evaluation import EvaluationDesign, AssumptionValue
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.world import PartitionValueDTO, QuantityValue
from poliscope_engine.evaluation import evaluate, EvaluationCache, EvaluationError
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.dependencies import DependencyError
from poliscope_engine.mechanisms import MechanismRegistry, MechanismError
from poliscope_engine.world import WorldRegistry, StateOwner
from poliscope_engine.world.membership import WorldGraph
from test_mechanism_registry import world, registry, PROVENANCE
from test_dependencies import plain, request, binding as numerical_binding
from test_solvers import host, quantity, execution, plan, loop, split_contention

MODEL = ('synthetic:model', 'v1')


@pytest.mark.parametrize('limit', [0, -1, True, 1.5, 256 * 1024 * 1024 + 1])
def test_cache_rejects_invalid_byte_quota(limit):
    with pytest.raises(EvaluationError, match='invalid_cache_byte_limit'):
        EvaluationCache(max_bytes=limit)


def test_byte_quota_eviction_and_clear_preserve_complete_result_identity():
    d = plain(('synthetic:in',))
    calls = []
    def implementation(port, values):
        calls.append(port)
        return values['synthetic:in']
    host_registry = host(d, implementation)
    w, des = WorldGraph(world()), design()
    expected = evaluate(w, des, (), MODEL, registry=host_registry)
    size = len(expected.model_dump_json().encode('utf-8'))
    tiny = EvaluationCache(max_bytes=size-1)
    assert tiny.evaluate(w, des, (), MODEL, registry=host_registry) == expected
    assert tiny._entries == {}  # a complete result, never a truncated cache entry
    cache = EvaluationCache(capacity=3, max_bytes=size+100)
    assert cache.evaluate(w, des, (), MODEL, registry=host_registry) == expected
    calls.clear()
    assert cache.evaluate(w, des, (), MODEL, registry=host_registry) == expected
    assert calls == []
    changed = des.model_copy(update={'effective_time': des.effective_time.model_copy(update={'tick': 1})})
    cache.evaluate(w, changed, (), MODEL, registry=host_registry)
    calls.clear()
    assert cache.evaluate(w, des, (), MODEL, registry=host_registry) == expected
    assert calls  # byte quota evicted the older identity despite spare entry capacity
    cache.clear()
    calls.clear()
    assert cache.evaluate(w, des, (), MODEL, registry=host_registry) == expected
    assert calls


def design(dep=None, **updates):
    d = plain(('synthetic:in',))
    if dep is None:
        dep = request(('a',), d, fixed_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=quantity('2'))])
    data = dict(contract_version=1, effective_time=dict(tick=0, calendar_id='calendar'),
        execution=execution(dep).model_dump(), policies=[], policy_rules=[], policy_inputs=[],
        world_inputs=[], assumption_inputs=[], realization_inputs=[], conditions=[],
        realization=dict(identity=dict(id='realization', version='v1'), seed=None, event_ids=[], values=[]))
    return EvaluationDesign.model_validate(data | updates)


def run(d=None, r=None, w=None, assumptions=()):
    if r is None:
        r = host(plain(('synthetic:in',)), lambda p, i: quantity(str(int(i['synthetic:in'].value) * 3)))
    return evaluate(w or WorldGraph(world()), d or design(), assumptions, MODEL, registry=r)


def outputs(result):
    return {tuple(o.node): o for o in result.observations if o.node[0] == 'output'}


def test_complete_deterministic_typed_result_and_retained_identity():
    a, b = run(), run()
    assert a == b
    assert a.outcome == 'complete'
    assert outputs(a)['output', 'a', 'synthetic:out'].value.value == '6'
    assert a.identities.output_digest == digest(a.model_dump(mode='json', exclude={'identities'}))
    assert a.identities.input_digest == digest(json.loads(a.input_json))
    assert a.identities.model_digest == digest(json.loads(a.model_json))
    assert a.identities.realization_digest == digest(json.loads(a.realization_json))
    assert a.identities.cache_key == digest(a.identities.model_dump(exclude={'cache_key', 'output_digest'}))
    assert outputs(a)['output', 'a', 'synthetic:out'].source_refs == ['synthetic:source']


def test_closed_time_claim_semantics_have_a_distinct_cache_identity(monkeypatch):
    import poliscope_engine.evaluation as module
    current = run()
    assert json.loads(current.model_json)['evaluator'] == 'pure-static-v3'
    monkeypatch.setattr(module, 'EVALUATOR_ID', 'pure-static-v2')
    prior = run()
    assert outputs(prior) == outputs(current)
    assert prior.identities.input_digest == current.identities.input_digest
    assert prior.identities.model_digest != current.identities.model_digest
    assert prior.identities.cache_key != current.identities.cache_key


@pytest.mark.parametrize('number', ['2.0', '2.000', '2e0'])
def test_decimal_spelling_is_semantically_identical(number):
    data = design().model_dump()
    data['execution']['dependencies']['fixed_inputs'][0]['value']['value'] = number
    assert run(EvaluationDesign.model_validate(data)) == run()


def test_all_unordered_input_permutations_have_same_results_and_digests():
    d = plain(('synthetic:in',))
    r = host(d, lambda p, i: i['synthetic:in'])
    result = None
    for ids in permutations('abc'):
        fixed = [dict(consumer=dict(instance_id=i, port_id='synthetic:in'), value=quantity('2')) for i in ids]
        out = run(design(request(ids, d, fixed_inputs=fixed)), r)
        if result is None:
            result = out
        assert out == result


@pytest.mark.parametrize('field', ['effective_time', 'operation_limit', 'unused_assumption', 'seed', 'event_order'])
def test_meaningful_hidden_inputs_change_identity(field):
    base = design().model_dump()
    assumptions = ()
    if field == 'effective_time':
        base['effective_time']['tick'] = 1
    elif field == 'operation_limit':
        base['execution']['operation_limit'] = 999
    elif field == 'unused_assumption':
        assumptions = [AssumptionValue(id='unused', value=QuantityValue(**quantity('9')))]
    elif field == 'seed':
        base['realization']['seed'] = 'different'
    else:
        first = deepcopy(base)
        first['realization']['event_ids'] = ['first', 'second']
        base['realization']['event_ids'] = ['second', 'first']
        assert run(EvaluationDesign.model_validate(first)).identities.realization_digest != run(EvaluationDesign.model_validate(base)).identities.realization_digest
    changed = run(EvaluationDesign.model_validate(base), assumptions=assumptions)
    assert changed.identities.cache_key != run().identities.cache_key
    # Visible value remains identical; equal bars are never cache identity.
    assert outputs(changed) == outputs(run())


def test_unknown_and_zero_are_different_and_independent_outputs_continue():
    d = plain(('synthetic:in',))
    dep = request(('a', 'b', 'c'), d, fixed_inputs=[
        dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=dict(kind='unknown', reason='not supplied')),
        dict(consumer=dict(instance_id='b', port_id='synthetic:in'), value=quantity('0'))],
        bindings=[numerical_binding('a', 'c')])
    out = run(design(dep), host(d, lambda p, i: i['synthetic:in']))
    assert out.outcome == 'incomplete'
    assert outputs(out)['output', 'a', 'synthetic:out'].status == 'missing_input'
    assert outputs(out)['output', 'c', 'synthetic:out'].status == 'missing_input'
    assert outputs(out)['output', 'b', 'synthetic:out'].value.value == '0'


def test_structural_invalidity_raises_instead_of_successful_insufficiency():
    data = design().model_dump()
    data['execution']['dependencies']['instances'][0]['scope_id'] = 'missing'
    with pytest.raises(ValueError):
        run(EvaluationDesign.model_validate(data))
    data = design().model_dump()
    data['request_id'] = 'not a semantic input'
    with pytest.raises(ValidationError):
        EvaluationDesign.model_validate(data)
    with pytest.raises(EvaluationError, match='model_identity_mismatch'):
        evaluate(WorldGraph(world()), design(), (), ('other', 'v2'), registry=host(plain(('synthetic:in',)), lambda p, i: quantity('0')))


def condition_design(value='2', failure='not_applicable', operation='ge'):
    d = plain(('synthetic:in',))
    data = d.model_dump()
    data['preconditions'] = [dict(id='synthetic:positive', input_refs=['synthetic:in'], description='Synthetic threshold', failure_behavior=failure)]
    d = MechanismDefinition.model_validate(data)
    dep = request(('a',), d, fixed_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=quantity(value))])
    c = dict(identity=dict(id='host:positive', version='v1'), instance_id='a', precondition_id='synthetic:positive', input_id='synthetic:in', operation=operation, value=quantity('1'))
    return d, design(dep, conditions=[c])


@pytest.mark.parametrize('value,status', [('2', 'known'), ('0', 'not_applicable')])
def test_precondition_is_explicit_and_controls_execution(value, status):
    d, des = condition_design(value)
    calls = []
    result = run(des, host(d, lambda p, i: calls.append(True) or i['synthetic:in']))
    assert outputs(result)['output', 'a', 'synthetic:out'].status == status
    assert bool(calls) == (status == 'known')


def test_precondition_conflict_missing_rule_and_invalid_binding():
    d, des = condition_design('0', failure='conflict')
    assert run(des, host(d, lambda p, i: quantity('99'))).outcome == 'unresolved'
    data = des.model_dump()
    data['conditions'] = []
    out = run(EvaluationDesign.model_validate(data), host(d, lambda p, i: quantity('99')))
    assert out.outcome == 'incomplete'
    assert outputs(out)['output', 'a', 'synthetic:out'].reason == 'precondition_evaluation_required'
    data = des.model_dump()
    data['conditions'][0]['input_id'] = 'wrong'
    with pytest.raises(DependencyError, match='unsupported_condition_inputs'):
        run(EvaluationDesign.model_validate(data), host(d, lambda p, i: quantity('99')))


def test_finite_contention_returns_insufficiency_and_exact_group_distributions():
    req, r = __import__('test_solvers').contention()
    data, w = req.model_dump(), world()
    # Existing solver fixture uses synthetic claimant IDs; bind to real entities.
    for c in data['batch']['claims']:
        c['claimant_id'] = 'supply'
    des = design(execution=execution(request(('a',), plain())).model_dump())
    des = EvaluationDesign.model_validate(des.model_dump() | {'execution': data})
    out = run(des, r, WorldGraph(w))
    assert out.outcome == 'insufficient'
    assert out.accounts is not None
    assert sum(int(c.actual) for c in out.accounts.claims) == 100
    assert sum(int(c.unmet) for c in out.accounts.claims) == 100
    assert all(int(a.available) >= 0 for a in out.accounts.accounts)
    retained = json.loads(out.final_batch_json)
    assert all(c['claimant_id'] == 'supply' for c in retained['claims'])


@pytest.mark.parametrize('kind', ['linear', 'iterative'])
def test_global_orchestration_uses_reviewed_solvers(kind):
    d, dep = loop()
    r = host(d, lambda p, i: quantity(str(1 + float(i['synthetic:in'].value) / 2)))
    out = run(design(dep, execution=execution(dep, solvers=[plan(kind)]).model_dump()), r)
    assert out.outcome == 'complete'
    assert outputs(out)['output', 'a', 'synthetic:out'].status == 'known'


def test_solver_failure_propagates_to_dependents_without_losing_cause():
    d, dep = loop()
    data = dep.model_dump()
    data['instances'].append(dict(data['instances'][0], id='b'))
    data['bindings'].append(numerical_binding('a', 'b'))
    dep = type(dep).model_validate(data)
    out = run(design(dep, execution=execution(dep, solvers=[plan(iteration_limit=2)]).model_dump()),
              host(d, lambda p, i: quantity(str(int(i['synthetic:in'].value) + 1))))
    assert out.outcome == 'unresolved'
    assert outputs(out)['output', 'b', 'synthetic:out'].status == 'solver_failure'


@pytest.mark.parametrize('modeling,expected', [('partial', 'partial'), ('qualitative', 'unmodeled'), ('unsupported', 'unmodeled')])
def test_declared_coverage_never_becomes_false_complete(modeling, expected):
    d = plain(('synthetic:in',))
    data = d.model_dump()
    data['modeling'] = modeling
    if modeling != 'partial':
        data['support'] = dict(static=None, transition=None)
    d = MechanismDefinition.model_validate(data)
    dep = request(('a',), d, fixed_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=quantity('2'))])
    out = run(design(dep), host(d, lambda p, i: quantity('7')) if modeling == 'partial' else registry([d]))
    assert out.outcome == 'incomplete'
    assert outputs(out)['output', 'a', 'synthetic:out'].status == expected


def test_assumptions_and_realizations_are_bound_once_and_retained():
    d = plain(('synthetic:in',))
    dep = request(('a', 'b'), d)
    binding = lambda i: dict(consumer=dict(instance_id=i, port_id='synthetic:in'), value_id='shared')
    des = design(dep, assumption_inputs=[binding('a'), binding('b')])
    assumptions = [AssumptionValue(id='shared', value=QuantityValue(**quantity('4')))]
    out = run(des, host(d, lambda p, i: i['synthetic:in']), assumptions=assumptions)
    assert all(o.value.value == '4' for o in outputs(out).values())
    data = des.model_dump()
    data['realization_inputs'] = data.pop('assumption_inputs')
    data['assumption_inputs'] = []
    data['realization']['values'] = [a.model_dump() for a in assumptions]
    second = run(EvaluationDesign.model_validate(data), host(d, lambda p, i: i['synthetic:in']))
    assert outputs(out) == outputs(second)
    assert out.identities.cache_key != second.identities.cache_key


def test_world_input_requires_declared_partition_and_exact_context():
    d = plain(('synthetic:in',))
    data = d.model_dump()
    data['read_partitions'] = ['conditions']
    d = MechanismDefinition.model_validate(data)
    base = world()
    value = PartitionValueDTO(id='property', entity_id='supply', scope_id='local', property_id='quantity',
        partition='conditions', value=quantity('5'), effective_time=dict(tick=0, calendar_id='calendar'), provenance=PROVENANCE)
    w = WorldGraph(WorldRegistry('civ', entities=base.entities, scopes=base.scopes, values=[value],
        owners=[StateOwner('supply', 'quantity', 'conditions', 'provisioning')]))
    des = design(request(('a',), d), world_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value_id='property')])
    assert next(iter(outputs(run(des, host(d, lambda p, i: i['synthetic:in']), w)).values())).value.value == '5'
    data = des.model_dump()
    data['world_inputs'][0]['value_id'] = 'absent'
    with pytest.raises(EvaluationError, match='missing_value_reference'):
        run(EvaluationDesign.model_validate(data), host(d, lambda p, i: i['synthetic:in']), w)


def test_policy_composition_drives_input_and_conflict_stays_visible():
    from test_policies import definition, graph, mechanisms, binding, overlap, rule
    d = definition()
    dep = request(('a',), d).model_dump()
    dep['instances'][0]['entity_id'] = 'water'
    dep = type(request(('a',), d)).model_validate(dep)
    data = design(dep).model_dump()
    data.update(policies=[binding().model_dump()], policy_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:parameter'),
        entity_id='water', parameter_id='synthetic:parameter', selection='value')])
    # The fixture's output does not consume the policy parameter; assert resolved input.
    out = run(EvaluationDesign.model_validate(data), mechanisms(), graph())
    observation = next(o for o in out.observations if o.node == ['input', 'a', 'synthetic:parameter'])
    assert observation.status == 'known' and observation.value.value == '2'
    data['policies'] = [b.model_dump() for b in overlap()]
    out = run(EvaluationDesign.model_validate(data), mechanisms(), graph())
    assert out.outcome == 'unresolved'
    assert next(o for o in out.observations if o.node == observation.node).status == 'conflict'
    data['policy_rules'] = [rule().model_dump()]
    out = run(EvaluationDesign.model_validate(data), mechanisms(), graph())
    assert next(o for o in out.observations if o.node == observation.node).value.value == '7'


def test_cache_hits_are_detached_bounded_and_model_bound():
    calls = []
    d = plain(('synthetic:in',))
    r = host(d, lambda p, i: calls.append(True) or quantity('6'))
    cache = EvaluationCache(capacity=1)
    w, des = WorldGraph(world()), design()
    a = cache.evaluate(w, des, (), MODEL, registry=r)
    a.observations.clear()
    b = cache.evaluate(w, des, (), MODEL, registry=r)
    assert b.observations and len(calls) == 1
    changed = des.model_copy(update={'effective_time': des.effective_time.model_copy(update={'tick': 1})})
    cache.evaluate(w, changed, (), MODEL, registry=r)
    assert len(cache._entries) == 1 and len(calls) == 2
    cache.evaluate(w, des, (), MODEL, registry=r)
    assert len(calls) == 3
    # New host callback objects cannot borrow old entries under copied version IDs.
    r2 = host(d, lambda p, i: quantity('99'))
    result = cache.evaluate(w, des, (), MODEL, registry=r2)
    assert next(iter(outputs(result).values())).value.value == '99'


def test_cache_never_bypasses_fresh_review_or_structural_validation():
    d = plain(('synthetic:in',))
    r = host(d, lambda p, i: quantity('6'))
    cache = EvaluationCache()
    cache.evaluate(WorldGraph(world()), design(), (), MODEL, registry=r)
    bad = registry([d], implementations=r.implementations, reviews=[])
    with pytest.raises(MechanismError, match='review_required'):
        cache.evaluate(WorldGraph(world()), design(), (), MODEL, registry=bad)


@pytest.mark.parametrize('module,name,args', [(builtins, 'open', ('/no-read',)),
    (sqlite3, 'connect', (':memory:',)), (socket, 'socket', ()),
    (time, 'time', ()), (random, 'random', ())])
def test_pure_evaluation_tripwires_detect_injected_io_clock_or_randomness(monkeypatch, module, name, args):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise RuntimeError('pure evaluation attempted external effect')
    d = plain(('synthetic:in',))
    callback = lambda p, i: getattr(module, name)(*args)
    r = host(d, callback)
    monkeypatch.setattr(module, name, forbidden)
    out = run(design(), r)
    assert calls
    assert out.outcome == 'unresolved'
    assert next(iter(outputs(out).values())).status == 'solver_failure'


def test_normal_evaluator_needs_no_external_effects(monkeypatch):
    d = plain(('synthetic:in',))
    r = host(d, lambda p, i: i['synthetic:in'])
    w, des = WorldGraph(world()), design()
    def forbidden(*args, **kwargs):
        pytest.fail('external effect attempted')
    for module, name in [(builtins, 'open'), (sqlite3, 'connect'), (socket, 'socket'), (time, 'time'), (random, 'random')]:
        monkeypatch.setattr(module, name, forbidden)
    assert run(des, r, w).outcome == 'complete'


@pytest.mark.parametrize('change', ['sources', 'units', 'times', 'review', 'implementation'])
def test_complete_model_manifest_invalidates_even_when_output_is_unchanged(change):
    from poliscope_engine.numeric import Registry, Unit, TimeBasis, parse
    d = plain(('synthetic:in',))
    r = host(d, lambda p, i: quantity('6'))
    options = dict(implementations=r.implementations, reviews=r.reviews, units=r.units,
                   times=r.times, source_ids=r.source_ids)
    if change == 'sources':
        options['source_ids'] = [*r.source_ids, 'unused-source']
    elif change == 'units':
        options['units'] = Registry(tuple(replace(u, scale=parse('2')) if u.id == 'kg' else u for u in r.units.units))
    elif change == 'times':
        options['times'] = (TimeBasis('day', parse('86401')),)
    elif change == 'review':
        options['reviews'] = [replace(review, evidence_review_ref='updated-review') for review in r.reviews]
    else:
        # Additional trusted code availability is part of the host manifest.
        options['implementations'] = (*r.implementations, replace(r.implementations[0], id='unused-implementation'))
    updated = registry([d], **options)
    base, changed = run(design(), r), run(design(), updated)
    assert outputs(base) == outputs(changed)
    assert base.identities.model_digest != changed.identities.model_digest
    assert base.identities.cache_key != changed.identities.cache_key


@pytest.mark.parametrize('case,outcome', [('zero', 'insufficient'), ('denied', 'insufficient'), ('no-procedure', 'unresolved'), ('unknown-access', 'unresolved')])
def test_playable_shortage_differs_from_unknown_allocation(case, outcome):
    from test_solvers import contention
    req, r = contention()
    data = req.model_dump()
    for c in data['batch']['claims']:
        c['claimant_id'] = 'supply'
    if case == 'zero':
        data['batch']['accounts'][0]['opening'] = '0'
    elif case == 'denied':
        for c in data['allocations'][0]['choices']:
            c['access'] = 'denied'
    elif case == 'no-procedure':
        data['allocations'][0]['procedure'] = None
        data['allocations'][0]['claim_order'] = []
    else:
        data['allocations'][0]['choices'][0]['access'] = 'unknown'
    out = run(design(execution=data), r)
    assert out.outcome == outcome
    if outcome == 'insufficient':
        assert sum(int(c.actual) for c in out.accounts.claims) == 0
        assert sum(int(c.unmet) for c in out.accounts.claims) == 200
    else:
        assert out.accounts is None
        assert out.final_batch_json is None
        assert outputs(out)['output', 'b', 'synthetic:supported'].status == 'conflict'


def test_claim_priority_is_semantic_and_never_canonicalized_away():
    from test_solvers import contention
    req, r = contention()
    data = req.model_dump()
    for c in data['batch']['claims']:
        c['claimant_id'] = 'supply'
    first = run(design(execution=data), r)
    data['allocations'][0]['claim_order'].reverse()
    second = run(design(execution=data), r)
    assert first.identities.input_digest != second.identities.input_digest
    assert first.identities.output_digest != second.identities.output_digest
    assert {c.claim_id: c.actual for c in first.accounts.claims} == {'a': '100', 'b': '0'}
    assert {c.claim_id: c.actual for c in second.accounts.claims} == {'a': '0', 'b': '100'}


def test_duplicate_input_authorities_and_realization_identities_are_rejected():
    des = design().model_dump()
    des['assumption_inputs'] = [dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value_id='extra')]
    with pytest.raises(EvaluationError, match='multiple_input_producers'):
        run(EvaluationDesign.model_validate(des), assumptions=[AssumptionValue(id='extra', value=QuantityValue(**quantity('2')))])
    des = design().model_dump()
    des['realization']['event_ids'] = ['same', 'same']
    with pytest.raises(EvaluationError, match='duplicate_event_identity'):
        run(EvaluationDesign.model_validate(des))


def test_partial_coverage_flows_downstream_and_trace_links_retained():
    d = plain(('synthetic:in',))
    data = d.model_dump()
    data['modeling'] = 'partial'
    d = MechanismDefinition.model_validate(data)
    dep = request(('a', 'b'), d, bindings=[numerical_binding('a', 'b')],
        fixed_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=quantity('2'))])
    out = run(design(dep), host(d, lambda p, i: i['synthetic:in']))
    assert all(o.status == 'partial' for o in outputs(out).values())
    assert any(e.source == ['output', 'a', 'synthetic:out'] and e.target == ['input', 'b', 'synthetic:in'] for e in out.trace_edges)


def test_returned_inputs_and_results_cannot_mutate_source_or_cached_entries():
    des = design()
    before = des.model_dump_json()
    a = run(des)
    a.observations[0].source_refs.clear()
    assert des.model_dump_json() == before
    assert run(des).identities.output_digest == run().identities.output_digest


def test_cache_detects_corrupt_local_entry_before_reuse():
    d = plain(('synthetic:in',))
    calls = []
    r = host(d, lambda p, i: calls.append(True) or quantity('6'))
    cache = EvaluationCache()
    out = cache.evaluate(WorldGraph(world()), design(), (), MODEL, registry=r)
    raw = out.model_dump()
    raw['outcome'] = 'unresolved'
    cache._entries[out.identities.cache_key] = r, json.dumps(raw)
    result = cache.evaluate(WorldGraph(world()), design(), (), MODEL, registry=r)
    assert len(calls) == 2 and result.outcome == 'complete'
