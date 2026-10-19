"""Synthetic compiler boundaries; independently specified graph expectations."""
from dataclasses import FrozenInstanceError
import itertools
import json

import pytest
from pydantic import ValidationError

from poliscope_engine.contracts.dependencies import DependencyRequest
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.world import ScopeDTO
from poliscope_engine.dependencies import compile_dependencies, DependencyError, _components
from poliscope_engine.mechanisms import MechanismError
from test_mechanism_registry import definitions, registry, world, PROVENANCE

Q = dict(kind='quantity', unit_id='kg', time_basis_id=None, denominator_scope_id=None)


def plain(inputs=(), outputs=None):
    d = definitions()[0].model_dump(mode='json')
    d['inputs'] = [dict(id=p, value_type=Q, required=True, missing_behavior='propagate') for p in inputs]
    d['outputs'] = [dict(id=p, value_type=Q, input_refs=refs, missing_behavior='propagate')
                    for p, refs in (outputs or {'synthetic:out': list(inputs)}).items()]
    d['traces'] = []
    return MechanismDefinition.model_validate(d)


def instance(identity, definition=None):
    d = plain() if definition is None else definition
    return dict(id=identity, mechanism_id=d.id, mechanism_version=d.version,
                scope_id='local', entity_id='account' if d.claims else 'supply')


def request(ids=('a',), definition=None, **updates):
    data = dict(contract_version=1, instances=[instance(i, definition) for i in ids],
                bindings=[], fixed_inputs=[], claims=[], account_producers=[], relationships=[])
    return DependencyRequest.model_validate(data | updates)


def binding(a, b, target='synthetic:in', source='synthetic:out'):
    return dict(producer=dict(instance_id=a, port_id=source),
                consumer=dict(instance_id=b, port_id=target))


def compile(req, definition=None, **options):
    return compile_dependencies(req, registry([plain() if definition is None else definition]),
                                options.get('world', world()))


def order(result):
    return {n: i for i, c in enumerate(result.components) for n in c.nodes}


def test_chain_and_diamond_all_permutations_have_independent_topological_constraints():
    d = plain(('synthetic:left', 'synthetic:right'))
    links = [binding('a', 'b', 'synthetic:left'), binding('a', 'c', 'synthetic:left'),
             binding('b', 'd', 'synthetic:left'), binding('c', 'd', 'synthetic:right')]
    fixed = [dict(consumer=dict(instance_id=i, port_id=p), value=dict(Q, value='1'))
             for i, p in [('a', 'synthetic:left'), ('a', 'synthetic:right'), ('b', 'synthetic:right'), ('c', 'synthetic:right')]]
    expected = None
    for ids in itertools.permutations('abcd'):
        result = compile(request(ids, d, bindings=links, fixed_inputs=fixed), d)
        rank = order(result)
        assert rank['output', 'a', 'synthetic:out'] < rank['output', 'b', 'synthetic:out'] < rank['output', 'd', 'synthetic:out']
        assert rank['output', 'a', 'synthetic:out'] < rank['output', 'c', 'synthetic:out'] < rank['output', 'd', 'synthetic:out']
        assert all(c.status == 'ready' and not c.cyclic for c in result.components)
        if expected is None:
            expected = result
        assert result == expected
        links.reverse()
        fixed.reverse()


def test_missing_inputs_propagate_only_to_dependent_outputs():
    d = plain(('synthetic:in',), {'synthetic:out': ['synthetic:in'], 'synthetic:independent': []})
    result = compile(request(('a', 'b'), d, bindings=[binding('a', 'b')]), d)
    status = {n: c.status for c in result.components for n in c.nodes}
    assert result.missing_inputs == (('input', 'a', 'synthetic:in'),)
    assert status['input', 'a', 'synthetic:in'] == 'missing_input'
    assert status['output', 'a', 'synthetic:out'] == status['output', 'b', 'synthetic:out'] == 'blocked'
    assert status['output', 'b', 'synthetic:independent'] == 'ready'


@pytest.mark.parametrize('size', [1, 2, 5])
def test_numerical_cycles_are_explicitly_unresolved_and_block_dependents(size):
    d = plain(('synthetic:in',))
    ids = [str(i) for i in range(size)]
    links = [binding(ids[i], ids[(i+1) % size]) for i in range(size)]
    links.append(binding(ids[-1], 'downstream'))
    result = compile(request([*ids, 'downstream'], d, bindings=links), d)
    cycles = [c for c in result.components if c.cyclic]
    assert len(cycles) == 1 and len(cycles[0].nodes) == 2 * size
    assert cycles[0].status == 'solver_required'
    assert result.components[-1].status == 'blocked'


def test_institutional_documentary_cycles_never_create_numerical_edges():
    links = [dict(kind=kind, source_instance_id=a, target_instance_id=b, relationship_ref=f'{kind}:{a}')
             for kind in ('institutional', 'documentary') for a, b in [('a', 'b'), ('b', 'a')]]
    result = compile(request(('a', 'b'), relationships=links))
    assert len(result.context_edges) == 4
    assert not result.edges
    assert all(not c.cyclic and c.status == 'ready' for c in result.components)


def demands(feedback=False):
    d = definitions()[1].model_dump(mode='json')
    if feedback:
        d['outputs'][0]['input_refs'] = ['synthetic:allocated']
    return MechanismDefinition.model_validate(d)


def demand_request(feedback=False):
    d = demands(feedback)
    claims = [dict(instance_id=i, claim_id='synthetic:claim', account_id='account', allocation_id='shared')
              for i in ('a', 'b')]
    return request(('a', 'b'), d, claims=claims), d


def test_shared_contention_has_one_allocator_and_outputs_depend_on_actuals():
    req, d = demand_request()
    result = compile(req, d)
    rank = order(result)
    assert [n.key for n in result.nodes if n.key[0] == 'allocation'] == [('allocation', 'shared')]
    for i in ('a', 'b'):
        assert rank['output', i, 'synthetic:requested'] < rank['claim', i, 'synthetic:claim']
        assert rank['claim', i, 'synthetic:claim'] < rank['allocation', 'shared']
        assert rank['allocation', 'shared'] < rank['actual_consumption', i, 'synthetic:claim']
        assert rank['actual_consumption', i, 'synthetic:claim'] < rank['output', i, 'synthetic:supported']
    assert not result.missing_inputs
    assert all(c.status == 'ready' for c in result.components)


def test_allocation_feedback_classified_after_expansion_includes_both_competitors():
    req, d = demand_request(True)
    result = compile(req, d)
    cycles = [c for c in result.components if c.cyclic]
    assert len(cycles) == 1
    assert cycles[0].status == 'solver_required'
    assert ('allocation', 'shared') in cycles[0].nodes
    for i in ('a', 'b'):
        assert ('actual_consumption', i, 'synthetic:claim') in cycles[0].nodes
        assert ('claim', i, 'synthetic:claim') in cycles[0].nodes
    assert all(c.status == 'blocked' for c in result.components
               if any(n[0] == 'output' and n[-1] == 'synthetic:supported' for n in c.nodes))


@pytest.mark.parametrize('mutation,code', [
    (lambda r: r['instances'].append(r['instances'][0]), 'duplicate_instance'),
    (lambda r: r['claims'].pop(), 'unbound_claim'),
    (lambda r: r['claims'].append(r['claims'][0]), 'unknown_or_duplicate_claim'),
    (lambda r: r['claims'][0].update(claim_id='absent'), 'unknown_or_duplicate_claim'),
    (lambda r: r['claims'][0].update(account_id='supply'), 'claim_requires_account'),
    (lambda r: r['claims'][0].update(allocation_id='separate'), 'split_shared_account'),
    (lambda r: r['fixed_inputs'].append(dict(consumer=dict(instance_id='a', port_id='synthetic:account'),
                                          value=dict(kind='reference', entity_id='civ'))), 'incompatible_reference'),
    (lambda r: r['bindings'].append(binding('a', 'b', 'synthetic:allocated', 'synthetic:requested')),
     'multiple_input_producers'),
])
def test_claim_boundaries(mutation, code):
    req, d = demand_request()
    data = req.model_dump(mode='json')
    mutation(data)
    with pytest.raises((DependencyError, MechanismError), match=code):
        compile(DependencyRequest.model_validate(data), d)


@pytest.mark.parametrize('link,code', [
    (binding('missing', 'a'), 'unknown_output'),
    (binding('a', 'missing'), 'unknown_input'),
    (binding('a', 'a', source='missing'), 'unknown_output'),
    (binding('a', 'a', target='missing'), 'unknown_input'),
])
def test_unknown_ports(link, code):
    d = plain(('synthetic:in',))
    with pytest.raises(DependencyError, match=code):
        compile(request(definition=d, bindings=[link]), d)


def test_duplicate_producers_fixed_inputs_and_unknowns():
    d = plain(('synthetic:in',))
    fixed = dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value=dict(Q, value='3'))
    with pytest.raises(DependencyError, match='multiple_input_producers'):
        compile(request(definition=d, fixed_inputs=[fixed, fixed]), d)
    fixed['value'] = dict(kind='unknown', reason='Unobserved')
    result = compile(request(definition=d, fixed_inputs=[fixed]), d)
    assert result.missing_inputs == (('input', 'a', 'synthetic:in'),)


def test_trust_required_and_no_callbacks_executed():
    d = plain()
    r = registry([d], reviews=[])
    with pytest.raises(MechanismError, match='review_required'):
        compile_dependencies(request(), r, world())
    # Fixture callbacks fail the test if called; ordinary compile must succeed.
    compile(request())


def test_detachment_revalidation_and_content_identity():
    req = request()
    result = compile(req)
    req.instances.clear()
    assert len(json.loads(result.request_json)['instances']) == 1
    with pytest.raises(FrozenInstanceError):
        result.digest = 'changed'
    # An unanswered sandbox now legitimately has no mechanism instances.
    compile(req)
    req.instances.append(request().instances[0].model_copy(update={'id': ''}))
    with pytest.raises(ValidationError):
        compile(req)
    d = plain()
    assert compile(request()).digest != compile(request(('different',))).digest
    edited = d.model_copy(update={'coverage_limits': 'Changed declaration'})
    assert compile(request(), edited).digest != result.digest


def test_cross_scope_rejected_without_adapter():
    d = plain(('synthetic:in',))
    req = request(('a', 'b'), d, bindings=[binding('a', 'b')])
    data = req.model_dump(mode='json')
    data['instances'][1]['scope_id'] = 'other'
    w = world()
    from poliscope_engine.world import WorldRegistry
    w = WorldRegistry('civ', entities=w.entities, scopes=[*w.scopes,
        ScopeDTO(id='other', scope_kind='settlement', label='Synthetic', provenance=PROVENANCE)])
    with pytest.raises(DependencyError, match='cross_scope_requires_adapter'):
        compile(DependencyRequest.model_validate(data), d, world=w)


def test_iterative_scc_handles_long_chain_and_exact_independent_cycle_partition():
    keys = [(str(i),) for i in range(5000)]
    edges = set(zip(keys, keys[1:]))
    result = _components(keys, edges, set())
    assert tuple(c.nodes[0] for c in result) == tuple(keys)
    edges.add((keys[3999], keys[3000]))
    result = _components(keys, edges, set())
    cycle = next(c for c in result if c.cyclic)
    assert set(cycle.nodes) == set(keys[3000:4000])
    assert len(result) == 4001


def test_all_small_directed_graphs_match_independent_reachability_oracle():
    keys = [('a',), ('b',), ('c',)]
    possible = list(itertools.product(keys, repeat=2))
    for mask in range(1 << len(possible)):
        edges = {e for i, e in enumerate(possible) if mask & (1 << i)}
        reach = {(a, a) for a in keys} | edges
        for via in keys:
            reach |= {(a, b) for a in keys for b in keys if (a, via) in reach and (via, b) in reach}
        expected = {frozenset(b for b in keys if (a, b) in reach and (b, a) in reach) for a in keys}
        components = _components(keys, edges, set())
        assert {frozenset(c.nodes) for c in components} == expected
        rank = {n: i for i, c in enumerate(components) for n in c.nodes}
        assert all(rank[a] <= rank[b] for a, b in edges)
        assert all(c.cyclic == (len(c.nodes) > 1 or (c.nodes[0], c.nodes[0]) in edges) for c in components)


def test_optional_omission_and_explicit_unknown_have_same_compilation_status():
    data = plain(('synthetic:in',)).model_dump(mode='json')
    data['inputs'][0].update(required=False, missing_behavior='omit')
    d = MechanismDefinition.model_validate(data)
    absent = compile(request(definition=d), d)
    unknown = compile(request(definition=d, fixed_inputs=[dict(
        consumer=dict(instance_id='a', port_id='synthetic:in'),
        value=dict(kind='unknown', reason='Unobserved'))]), d)
    assert all(c.status == 'ready' for r in (absent, unknown) for c in r.components)


def test_incompatible_units_rejected_before_graph_is_returned():
    data = plain(('synthetic:in',)).model_dump(mode='json')
    data['outputs'][0]['value_type'].update(unit_id='rate', time_basis_id='day')
    d = MechanismDefinition.model_validate(data)
    with pytest.raises(DependencyError, match='incompatible_port'):
        compile(request(('a', 'b'), d, bindings=[binding('a', 'b')]), d)


@pytest.mark.parametrize('duplicate', [False, True])
def test_context_links_validate_references_and_duplicates(duplicate):
    link = dict(kind='documentary', source_instance_id='a',
                target_instance_id='a' if duplicate else 'missing', relationship_ref='synthetic:link')
    with pytest.raises(DependencyError, match='duplicate_context' if duplicate else 'unknown_context'):
        compile(request(relationships=[link, link] if duplicate else [link]))


def test_nested_bypass_and_contract_bounds_revalidated():
    req = request()
    bad = req.instances[0].model_copy(update={'id': 123})
    bypassed = req.model_copy(update={'instances': [bad]})
    with pytest.warns(UserWarning, match='Pydantic serializer'), pytest.raises(ValidationError):
        compile(bypassed)
    data = req.model_dump(mode='json')
    data['instances'] *= 101
    with pytest.raises(ValidationError):
        DependencyRequest.model_validate(data)


def test_budget_returns_explicit_error_instead_of_partial_schedule():
    # 100 outputs each depend on 100 ports: 10,000 edges per instance.
    ports = [f'synthetic:p{i}' for i in range(100)]
    d = plain(ports, {f'synthetic:o{i}': ports for i in range(100)})
    with pytest.raises(DependencyError, match='dependency_budget_exhausted'):
        compile(request([str(i) for i in range(6)], d), d)


def test_tuple_namespaces_do_not_alias_punctuated_instance_ids():
    result = compile(request(('a:output', 'a', 'output:a')))
    assert len(result.nodes) == 3
    assert len({n.key for n in result.nodes}) == 3


def test_production_to_shared_account_feedback_is_present_before_scc_detection():
    req, d = demand_request()
    producer = dict(producer=dict(instance_id='a', port_id='synthetic:supported'), account_id='account')
    req = DependencyRequest.model_validate(req.model_dump(mode='json') | dict(account_producers=[producer]))
    result = compile(req, d)
    cycle = next(c for c in result.components if c.cyclic)
    assert cycle.status == 'solver_required'
    assert ('account', 'account') in cycle.nodes
    assert ('output', 'a', 'synthetic:supported') in cycle.nodes
    assert ('claim', 'b', 'synthetic:claim') in cycle.nodes
    assert ('actual_consumption', 'b', 'synthetic:claim') not in cycle.nodes
    assert ('output', 'b', 'synthetic:supported') not in cycle.nodes
    assert next(c for c in result.components if ('output', 'b', 'synthetic:supported') in c.nodes).status == 'blocked'


@pytest.mark.parametrize('account,port,duplicate,code', [
    ('other', 'synthetic:supported', False, 'unbound_produced_account'),
    ('account', 'absent', False, 'unknown_output'),
    ('account', 'synthetic:supported', True, 'duplicate_account_producer'),
])
def test_account_producers_validate_targets_and_duplicates(account, port, duplicate, code):
    req, d = demand_request()
    producer = dict(producer=dict(instance_id='a', port_id=port), account_id=account)
    data = req.model_dump(mode='json') | dict(account_producers=[producer] * (2 if duplicate else 1))
    with pytest.raises(DependencyError, match=code):
        compile(DependencyRequest.model_validate(data), d)
