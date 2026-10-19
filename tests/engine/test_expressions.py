"""Synthetic arithmetic oracles and hostile graph boundaries, no scientific claim."""
from dataclasses import replace
import pytest
from pydantic import ValidationError
from test_mechanism_registry import definitions, registry, world, owned_world, stateful, change
from poliscope_engine.contracts.expressions import ExpressionGraph
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.world import UnknownValue
from poliscope_engine.mechanisms import MechanismRegistry, MechanismError, Review, declaration_digest
from poliscope_engine.mechanisms.expressions import graph_digest
from poliscope_engine.numeric import Registry, Unit, parse, NumericError


def setup(nodes=None, outputs=None, state=None, transition=False):
    d = (stateful() if transition else registry()).definitions[0].model_dump()
    # Simple input-output synthetic mechanism; claims remain runtime's concern.
    value_type = d['outputs'][0]['value_type']
    d['inputs'] = [dict(id='synthetic:x', value_type=value_type, required=True, missing_behavior='propagate')]
    d['outputs'][0]['input_refs'] = ['synthetic:x']
    d['support']['transition' if transition else 'static'] = dict(kind='declarative_graph', implementation=dict(id='graph', version='v1'))
    d = MechanismDefinition.model_validate(d)
    g = ExpressionGraph.model_validate(dict(contract_version=1, id='graph', version='v1', nodes=nodes or [
        dict(kind='input', id='x', input_id='synthetic:x'),
        dict(kind='constant', id='c', value='2.5', value_type=value_type),
        dict(kind='operator', id='sum', operator=dict(id='add', version='v1'), arguments=['x', 'c'])],
        outputs=outputs if outputs is not None else {d.outputs[0].id: 'sum'},
        state=state if state is not None else ({'synthetic:stock': 'sum'} if transition else {})))
    base = registry([d])
    r = MechanismRegistry(model=base.model, units=base.units, times=base.times, source_ids=base.source_ids,
        fixture_ids=base.fixture_ids, implementations=base.implementations, definitions=[d], graphs=[g],
        reviews=[Review(declaration_digest(d), *base.model, 'synthetic:evidence', 'synthetic:fixture', graph_digest(g))])
    return r, g


def evaluate(r, value='1.25', transition=False, inputs=None):
    return r.evaluate_graph('synthetic:supply', 'v1', phase='transition' if transition else 'static',
        world=owned_world() if transition else world(), scope_id='local', entity_id='supply',
        inputs={'synthetic:x': None if value is None else change().value.model_copy(update={'value': value})}
        if inputs is None else inputs)


def test_exact_chain_and_diamond_with_stable_order():
    r, g = setup()
    nodes = g.model_dump()['nodes'] + [
        dict(kind='operator', id='difference', operator=dict(id='subtract', version='v1'), arguments=['sum', 'x']),
        dict(kind='operator', id='diamond', operator=dict(id='add', version='v1'), arguments=['difference', 'sum'])]
    r, g = setup(nodes=list(reversed(nodes)), outputs={'synthetic:available': 'diamond'})
    # (1.25 + 2.5 - 1.25) + (1.25 + 2.5) = 6.25, independent oracle.
    assert evaluate(r)[0]['synthetic:available'].value == '6.25'
    assert evaluate(r)[1] == {}


@pytest.mark.parametrize('value', [None, UnknownValue(kind='unknown', reason='Not observed')])
def test_unknown_is_never_zero(value):
    r, _ = setup()
    assert evaluate(r, inputs={'synthetic:x': value})[0]['synthetic:available'] is None
    assert evaluate(r, inputs={})[0]['synthetic:available'] is None


def test_transition_proposals_are_pure_and_stage_through_existing_guard():
    r, _ = setup(transition=True)
    outputs, state = evaluate(r, transition=True)
    assert state['synthetic:stock'].value == '3.75'
    original = owned_world()
    staged = r.stage_changes('synthetic:supply', 'v1', world=original, scope_id='local', entity_id='supply',
                             changes=[change(value=state['synthetic:stock'].model_dump())])
    assert original.values == ()
    assert staged.values[0].value.value == '3.75'


@pytest.mark.parametrize('edit,code', [
    (lambda n: n[2]['operator'].update(id='__import__'), 'unknown_operator'),
    (lambda n: n[2]['operator'].update(version='v2'), 'unknown_operator'),
    (lambda n: n[2].update(arguments=['x', 'missing']), 'missing_node'),
    (lambda n: n[2].update(arguments=['sum', 'x']), 'graph_cycle'),
    (lambda n: n.append(n[0].copy()), 'duplicate_node'),
    (lambda n: n[0].update(input_id='missing'), 'unknown_input'),
    (lambda n: n[1]['value_type'].update(unit_id='missing'), 'unknown_unit'),
    (lambda n: n[1]['value_type'].update(unit_id='rate', time_basis_id='day'), 'incompatible_operator_units'),
    (lambda n: n[1].update(value='1e257'), 'precision_unsupported'),
])
def test_invalid_graphs_fail_before_execution(edit, code):
    _, graph = setup()
    nodes = graph.model_dump()['nodes']
    edit(nodes)
    r, _ = setup(nodes=nodes)
    with pytest.raises((MechanismError, NumericError), match=code):
        evaluate(r)


@pytest.mark.parametrize('field,value,code', [('outputs', {}, 'graph_output_mismatch'),
    ('outputs', {'synthetic:available': 'missing'}, 'missing_node'),
    ('outputs', {'synthetic:available': 'c'}, 'graph_input_dependencies_mismatch'),
    ('state', {'foreign': 'sum'}, 'graph_state_mismatch')])
def test_graph_cannot_change_declared_interface(field, value, code):
    r, _ = setup(**{field: value})
    with pytest.raises(MechanismError, match=code):
        evaluate(r)


def test_size_depth_and_executable_payload_bounds():
    _, g = setup()
    data = g.model_dump()
    for payload in [dict(data, python='print(1)'), dict(data, nodes=data['nodes'] * 100),
                    dict(data, nodes=[dict(kind='python', id='code', text='import os')])]:
        with pytest.raises(ValidationError):
            ExpressionGraph.model_validate(payload)
    nodes = data['nodes'][:2]
    previous = 'x'
    for i in range(33):
        name = f'op{i}'
        nodes.append(dict(kind='operator', id=name, operator=dict(id='add', version='v1'), arguments=[previous, 'c']))
        previous = name
    r, _ = setup(nodes=nodes, outputs={'synthetic:available': previous})
    with pytest.raises(MechanismError, match='graph_depth_exceeded'):
        evaluate(r)


def test_graph_and_model_reviews_are_exact_and_snapshots_detached():
    r, g = setup()
    g.nodes.clear()
    r.graphs[0].outputs.clear()
    assert evaluate(r)[0]['synthetic:available'].value == '3.75'
    for updates in [dict(reviews=[]), dict(model=('synthetic:model', 'v2')),
                    dict(reviews=[replace(r.reviews[0], graph_digest=None)])]:
        with pytest.raises(MechanismError, match='review_required'):
            evaluate(replace_registry(r, **updates))
    altered = r.graphs[0].model_dump()
    altered['nodes'][1]['value'] = '9'
    with pytest.raises(MechanismError, match='review_required'):
        evaluate(replace_registry(r, graphs=[ExpressionGraph.model_validate(altered)]))


def replace_registry(r, **updates):
    options = {k: getattr(r, k) for k in ('model', 'units', 'times', 'source_ids', 'assumption_ids',
        'fixture_ids', 'implementations', 'reviews', 'definitions', 'graphs')}
    return MechanismRegistry(**(options | updates))


@pytest.mark.parametrize('operation,expected', [('subtract', '-1.25'), ('minimum', '1.25'), ('maximum', '2.5')])
def test_registered_same_unit_operators(operation, expected):
    _, g = setup()
    nodes = g.model_dump()['nodes']
    nodes[2]['operator']['id'] = operation
    r, _ = setup(nodes=nodes)
    assert evaluate(r)[0]['synthetic:available'].value == expected


@pytest.mark.parametrize('operation,expected', [('multiply', '3.125'), ('divide', '0.5')])
def test_dimensionless_scaling(operation, expected):
    _, g = setup()
    nodes = g.model_dump()['nodes']
    nodes[1]['value_type']['unit_id'] = 'ratio'
    nodes[2]['operator']['id'] = operation
    r, _ = setup(nodes=nodes)
    r = replace_registry(r, units=Registry((*r.units.units, Unit('ratio', (), 'indicator', parse('1')))))
    assert evaluate(r)[0]['synthetic:available'].value == expected


@pytest.mark.parametrize('operation', ['multiply', 'divide'])
def test_dimensioned_scaling_rejected(operation):
    _, g = setup()
    nodes = g.model_dump()['nodes']
    nodes[2]['operator']['id'] = operation
    r, _ = setup(nodes=nodes)
    with pytest.raises(MechanismError, match='dimensionless_factor_required'):
        evaluate(r)


def test_division_by_zero_and_inexact_results_fail_honestly():
    _, g = setup()
    for divisor, code in [('0', 'invalid_denominator'), ('3', 'precision_unsupported')]:
        nodes = g.model_dump()['nodes']
        nodes[1]['value_type']['unit_id'] = 'ratio'
        nodes[1]['value'] = divisor
        nodes[2]['operator']['id'] = 'divide'
        r, _ = setup(nodes=nodes)
        r = replace_registry(r, units=Registry((*r.units.units, Unit('ratio', (), 'indicator', parse('1')))))
        with pytest.raises(NumericError, match=code):
            evaluate(r, value='1')


def test_input_validation_and_unknown_input_keys():
    r, _ = setup()
    with pytest.raises(MechanismError, match='unknown_input'):
        evaluate(r, inputs={'foreign': change().value})
    with pytest.raises(MechanismError, match='incompatible_value'):
        evaluate(r, inputs={'synthetic:x': change().value.model_copy(update={'unit_id': 'rate'})})
    with pytest.raises(NumericError, match='precision_unsupported'):
        evaluate(r, value='1e257')


def test_unused_nodes_cannot_hide_invalid_operators():
    _, g = setup()
    nodes = g.model_dump()['nodes']
    nodes.append(dict(kind='operator', id='unused', operator=dict(id='eval', version='v1'), arguments=['x', 'c']))
    r, _ = setup(nodes=nodes)
    with pytest.raises(MechanismError, match='unknown_operator'):
        evaluate(r)


def test_missing_input_on_one_branch_does_not_hide_known_independent_output():
    r, _ = setup()
    data = r.definitions[0].model_dump()
    data['outputs'].append(dict(id='synthetic:constant', value_type=data['outputs'][0]['value_type'],
                                input_refs=[], missing_behavior='propagate'))
    definition = MechanismDefinition.model_validate(data)
    data = r.graphs[0].model_dump()
    data['outputs']['synthetic:constant'] = 'c'
    graph = ExpressionGraph.model_validate(data)
    r = replace_registry(r, definitions=[definition], graphs=[graph],
        reviews=[Review(declaration_digest(definition), *r.model, 'synthetic:evidence', 'synthetic:fixture', graph_digest(graph))])
    outputs, _ = evaluate(r, inputs={})
    assert outputs['synthetic:available'] is None
    assert outputs['synthetic:constant'].value == '2.5'


@pytest.mark.parametrize('kind', ['label', 'reference'])
def test_non_numeric_passthrough_still_validates_type_and_reference(kind):
    from poliscope_engine.contracts.world import LabelValue, ReferenceValue
    r, _ = setup()
    data = r.definitions[0].model_dump()
    value_type = {'kind': 'label'} if kind == 'label' else {'kind': 'reference', 'entity_kind': 'resource'}
    data['inputs'][0]['value_type'] = data['outputs'][0]['value_type'] = value_type
    definition = MechanismDefinition.model_validate(data)
    graph = ExpressionGraph(contract_version=1, id='graph', version='v1',
        nodes=[dict(kind='input', id='x', input_id='synthetic:x')], outputs={'synthetic:available': 'x'}, state={})
    r = replace_registry(r, definitions=[definition], graphs=[graph],
        reviews=[Review(declaration_digest(definition), *r.model, 'synthetic:evidence', 'synthetic:fixture', graph_digest(graph))])
    value = LabelValue(kind='label', value='Synthetic') if kind == 'label' else ReferenceValue(kind='reference', entity_id='supply')
    assert evaluate(r, inputs={'synthetic:x': value})[0]['synthetic:available'] == value
    with pytest.raises(MechanismError, match='incompatible_value'):
        evaluate(r)


def test_unknown_dto_is_structurally_validated_and_duplicate_graphs_rejected():
    r, g = setup()
    with pytest.raises(ValidationError):
        evaluate(r, inputs={'synthetic:x': UnknownValue(kind='unknown', reason='valid').model_copy(update={'reason': ''})})
    with pytest.raises(MechanismError, match='duplicate_identity'):
        replace_registry(r, graphs=[g, g])
    assert r.with_definition(definitions()[1]).graphs == r.graphs


def test_graph_output_types_and_transition_ownership_cannot_be_bypassed():
    r, _ = setup(transition=True)
    with pytest.raises(MechanismError, match='foreign_state_owner'):
        r.evaluate_graph('synthetic:supply', 'v1', phase='transition', world=owned_world('economy'),
            scope_id='local', entity_id='supply', inputs={})
    r, _ = setup()
    d = r.definitions[0].model_dump()
    d['outputs'][0]['value_type'] = dict(kind='label')
    definition = MechanismDefinition.model_validate(d)
    with pytest.raises(MechanismError, match='graph_result_type_mismatch'):
        evaluate(replace_registry(r, definitions=[definition]))
