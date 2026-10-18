"""Synthetic data-only declarations; activation and numerical graph checks deferred."""
import copy
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.mechanisms import MechanismDefinition


def fixture(index=1):
    return json.loads(Path('contracts/mechanism-fixtures.json').read_text())[index]


def parse(data):
    return MechanismDefinition.model_validate(data)


def test_two_domain_contract_round_trips_and_shared_port_type():
    producer, consumer = [parse(fixture(i)) for i in range(2)]
    assert producer.domain != consumer.domain
    assert producer.outputs[0].value_type == consumer.inputs[0].value_type
    assert not producer.write_state_refs and not consumer.write_state_refs
    for model in (producer, consumer):
        assert MechanismDefinition.model_validate_json(model.model_dump_json()) == model
        assert model.evidence == 'hypothetical'  # parsing does not promote evidence
    assert consumer.claims[0].dependent_output_refs == ['synthetic:supported']


@pytest.mark.parametrize('change,code', [
    (lambda p: p.update(contract_version=2), 'literal_error'),
    (lambda p: p.update(domain='invented'), 'literal_error'),
    (lambda p: p.update(id='unqualified'), 'string_pattern_mismatch'),
    (lambda p: p.update(scope_kinds=[]), 'too_short'),
    (lambda p: p.update(scope_kinds=['settlement']*2), 'duplicate_identity'),
    (lambda p: p['inputs'].append(copy.deepcopy(p['inputs'][0])), 'duplicate_identity'),
    (lambda p: p['outputs'][0].update(id=p['inputs'][0]['id']), 'duplicate_identity'),
    (lambda p: p['inputs'][0].update(required='true'), 'bool_type'),
    (lambda p: p['inputs'][0].update(missing_behavior='omit'), 'required_input_must_propagate'),
    (lambda p: p['outputs'][1].update(input_refs=['synthetic:absent']), 'missing_reference'),
    (lambda p: p['outputs'][1].update(input_refs=['synthetic:allocated']*2), 'duplicate_identity'),
    (lambda p: p['outputs'][1].update(missing_behavior='zero'), 'literal_error'),
    (lambda p: p['claims'][0].update(amount_output_ref='synthetic:absent'), 'missing_reference'),
    (lambda p: p['claims'][0].update(dependent_output_refs=[]), 'too_short'),
    (lambda p: p['claims'][0].update(dependent_output_refs=['synthetic:absent']), 'missing_reference'),
    (lambda p: p['inputs'][1]['value_type'].update(entity_kind='asset'), 'claim_account_type'),
    (lambda p: p['inputs'][1].update(required=False), 'claim_account_must_propagate'),
    (lambda p: p['inputs'][0]['value_type'].update(unit_id='litre'), 'claim_quantity_type'),
    (lambda p: p['inputs'][0]['value_type'].update(time_basis_id='day'), 'claim_quantity_type'),
    (lambda p: p['inputs'][0]['value_type'].update(denominator_scope_id='cohort:a'), 'claim_quantity_type'),
    (lambda p: p['inputs'][0].update(required=False), 'allocation_must_propagate'),
    (lambda p: p['outputs'][1].update(input_refs=[]), 'missing_allocation_dependency'),
    (lambda p: p.update(write_state_refs=['synthetic:foreign']), 'missing_reference'),
    (lambda p: p.update(modeling='qualitative'), 'qualitative_execution'),
    (lambda p: p['support'].update(static=None), 'missing_procedure'),
    (lambda p: p.update(policy=dict(semantics='composable',composition_rule=None)), 'missing_composition_rule'),
    (lambda p: p['traces'][0].update(state_refs=['synthetic:foreign']), 'missing_reference'),
    (lambda p: p['fixtures'][0].update(property_refs=['synthetic:absent']), 'missing_reference'),
    (lambda p: p.update(inputs=p['inputs']*101), 'too_long'),
])
def test_invalid_declaration(change, code):
    data = fixture()
    change(data)
    with pytest.raises(ValidationError, match=code):
        parse(data)


@pytest.mark.parametrize('field', ['python', 'shell', 'formula', 'code', 'operator'])
def test_execution_payloads_rejected_at_every_boundary(field):
    for target in ('root', 'procedure', 'port'):
        data = fixture()
        place = data if target == 'root' else (data['support']['static'] if target == 'procedure' else data['inputs'][0])
        place[field] = '__import__("os").system("false")'
        with pytest.raises(ValidationError, match='extra_forbidden'):
            parse(data)


def stateful():
    data = fixture()
    data['owned_state'] = [dict(id='synthetic:stock',owner_domain='economy',partition='dynamic_state',value_type=data['inputs'][0]['value_type'])]
    data['write_state_refs'] = ['synthetic:stock']
    data['support']['transition'] = dict(kind='trusted_python',implementation=dict(id='synthetic:transition',version='v1'))
    return data


def test_transition_declares_only_own_dynamic_state_proposals():
    data = stateful()
    assert parse(data).write_state_refs == ['synthetic:stock']
    data['owned_state'][0]['owner_domain'] = 'provisioning'
    with pytest.raises(ValidationError, match='foreign_state_owner'):
        parse(data)


@pytest.mark.parametrize('partition', ['conditions', 'design', 'assumptions', 'observations', 'goals'])
def test_mechanism_cannot_declare_other_partition_writes(partition):
    data = stateful()
    data['owned_state'][0]['partition'] = partition
    with pytest.raises(ValidationError, match='literal_error'):
        parse(data)


def test_static_cannot_declare_state_writes():
    data = stateful()
    data['support']['transition'] = None
    with pytest.raises(ValidationError, match='state_write_requires_transition'):
        parse(data)


@pytest.mark.parametrize('modeling', ['qualitative', 'unsupported', 'partial'])
def test_unsupported_drafts_retain_explicit_coverage_without_procedure(modeling):
    data = fixture()
    data.update(modeling=modeling, support=dict(static=None,transition=None))
    assert parse(data).coverage_limits
    assert parse(data).evidence == 'hypothetical'


def test_optional_input_omission_is_explicit_and_no_default_value_is_injected():
    data = fixture(0)
    data['inputs'] = [dict(id='synthetic:optional',value_type=dict(kind='label'),required=False,missing_behavior='omit')]
    result = parse(data)
    assert 'default' not in result.inputs[0].model_dump()


def test_all_policy_semantics_and_versioned_procedure_reference():
    for semantics in ('exclusive','composable','floor','ceiling','delegated'):
        data = fixture()
        data['policy'] = dict(semantics=semantics,composition_rule=dict(id='synthetic:compose',version='v2'))
        assert parse(data).policy.semantics == semantics
    data['support']['static']['kind'] = 'declarative_graph'
    assert parse(data).support.static.kind == 'declarative_graph'


def test_precondition_and_diagnostic_references_must_resolve():
    data = fixture()
    data['preconditions'] = [dict(id='synthetic:precondition',input_refs=['synthetic:account'],
                                 description='Account must be applicable',failure_behavior='conflict')]
    data['diagnostics'] = [dict(id='synthetic:diagnostic',severity='warning',description='Synthetic diagnostic',
                               input_refs=['synthetic:allocated'],output_refs=['synthetic:supported'])]
    assert parse(data).preconditions[0].failure_behavior == 'conflict'
    for collection, field in [('preconditions','input_refs'), ('diagnostics','input_refs'), ('diagnostics','output_refs')]:
        changed = copy.deepcopy(data)
        changed[collection][0][field] = ['synthetic:absent']
        with pytest.raises(ValidationError, match='missing_reference'):
            parse(changed)


def test_port_metadata_is_strict_but_external_unit_resolution_is_deferred():
    data = fixture(0)
    data['outputs'][0]['value_type']['unit_id'] = 1.5
    with pytest.raises(ValidationError, match='string_type'):
        parse(data)
    data['outputs'][0]['value_type'] = dict(kind='label',unit_id='kg')
    with pytest.raises(ValidationError, match='extra_forbidden'):
        parse(data)
    data['outputs'][0]['value_type'] = dict(kind='quantity',unit_id='uninstalled:unit',
                                          time_basis_id=None,denominator_scope_id=None)
    assert parse(data).outputs[0].value_type.unit_id == 'uninstalled:unit'
