"""Synthetic trust, reference and state-authority boundaries; no scientific claim."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, PartitionValueDTO, ReferenceValue
from poliscope_engine.mechanisms import MechanismRegistry, MechanismError, Implementation, Review, declaration_digest
from poliscope_engine.numeric import Registry, Unit, TimeBasis, parse, NumericError
from poliscope_engine.world import WorldRegistry, StateOwner, WorldError

PROVENANCE = dict(origin='authored', source_refs=[], assumption_refs=[])


def definitions():
    return [MechanismDefinition.model_validate(d) for d in json.loads(Path('contracts/mechanism-fixtures.json').read_text())]


def world(owners=()):
    return WorldRegistry('civ', entities=[
        EntityDTO(id='civ', entity_kind='civilization', label='Synthetic', provenance=PROVENANCE),
        EntityDTO(id='supply', entity_kind='resource', label='Synthetic', provenance=PROVENANCE),
        EntityDTO(id='account', entity_kind='account', label='Synthetic', provenance=PROVENANCE)],
        scopes=[ScopeDTO(id='local', scope_kind='settlement', label='Synthetic', provenance=PROVENANCE)], owners=owners)


def registry(defs=None, **updates):
    defs = definitions() if defs is None else defs
    implementations = [Implementation(p.implementation.id, p.implementation.version, phase,
                                      lambda: pytest.fail('registration must not execute'))
                       for d in defs for phase in ('static', 'transition')
                       if (p := getattr(d.support, phase)) is not None]
    reviews = [Review(declaration_digest(d), 'synthetic:model', 'v1', 'synthetic:evidence-review',
                      'synthetic:independent-fixture-review') for d in defs]
    options = dict(model=('synthetic:model', 'v1'),
                   units=Registry((Unit('kg', (('mass', 1),), 'stock', parse('1')),
                                   Unit('rate', (('mass', 1),), 'flow', parse('1')))),
                   times=(TimeBasis('day', parse('86400')),), source_ids=['synthetic:source'],
                   fixture_ids=[('synthetic:positive', 'v1')], implementations=implementations,
                   reviews=reviews, definitions=defs)
    return MechanismRegistry(**(options | updates))


def activate(r, index=0, **options):
    d = r.definitions[index]
    return r.activate(d.id, d.version, **(dict(phase='static', world=world(), scope_id='local',
                                             entity_id='supply' if index == 0 else 'account') | options))


def test_two_domains_bind_exact_typed_references_and_never_execute():
    r = registry()
    result = r.bind(('synthetic:supply', 'v1'), ('synthetic:demand', 'v1'),
                    output_id='synthetic:available', input_id='synthetic:allocated', world=world(),
                    scope_id='local', producer_entity_id='supply', consumer_entity_id='account')
    assert result.unit_id == 'kg'
    assert activate(r).evidence == 'hypothetical'  # host review does not rewrite scientific status


def test_definitions_reviews_and_catalog_inputs_are_detached():
    defs = definitions()
    sources = ['synthetic:source']
    r = registry(defs, source_ids=sources)
    sources.clear()
    defs[0].outputs.clear()
    r.definitions[0].source_refs.clear()
    assert len(activate(r).outputs) == 1
    with pytest.raises(FrozenInstanceError):
        r.model = ('other', 'v2')


def test_lookup_decodes_only_the_selected_version_and_stays_detached(monkeypatch):
    r = registry()
    wanted = r.definitions[-1]
    decode = MechanismDefinition.model_validate_json
    decoded = []

    def counted(encoded):
        decoded.append(encoded)
        return decode(encoded)

    monkeypatch.setattr(MechanismDefinition, 'model_validate_json', counted)
    found = r.definition(wanted.id, wanted.version)
    assert found == wanted and len(decoded) == 1
    found.source_refs.clear()
    assert r.definition(wanted.id, wanted.version) == wanted
    assert len(decoded) == 2
    with pytest.raises(MechanismError, match='unknown_mechanism'):
        r.definition(wanted.id, 'absent-version')
    assert len(decoded) == 2


@pytest.mark.parametrize('updates,code', [
    (dict(implementations=[]), 'unknown_implementation'),
    (dict(reviews=[]), 'review_required'),
    (dict(source_ids=[]), 'unresolved_evidence'),
    (dict(fixture_ids=[]), 'unresolved_fixtures'),
    (dict(model=('synthetic:model', 'v2')), 'review_required'),
    (dict(units=Registry(())), 'unknown_unit'),
])
def test_activation_requires_all_independent_prerequisites(updates, code):
    with pytest.raises((MechanismError, NumericError), match=code):
        activate(registry(**updates))


def test_changed_definition_same_identity_cannot_reuse_review():
    defs = definitions()
    old = registry().reviews
    defs[0] = defs[0].model_copy(update={'coverage_limits': 'Edited assumption.'})
    with pytest.raises(MechanismError, match='review_required'):
        activate(registry(defs, reviews=old))


@pytest.mark.parametrize('field,value,code', [
    ('unit_id', 'unknown', 'unknown_unit'),
    ('time_basis_id', 'unknown', 'unknown_time_basis'),
    ('time_basis_id', 'day', 'invalid_time_basis'),
    ('denominator_scope_id', 'absent', 'missing_scope'),
])
def test_external_quantity_metadata(field, value, code):
    defs = definitions()
    data = defs[0].model_dump()
    data['outputs'][0]['value_type'][field] = value
    defs[0] = MechanismDefinition.model_validate(data)
    with pytest.raises((MechanismError, NumericError, WorldError), match=code):
        activate(registry(defs))


def test_flow_requires_registered_time_basis():
    defs = definitions()
    data = defs[0].model_dump()
    data['outputs'][0]['value_type']['unit_id'] = 'rate'
    defs[0] = MechanismDefinition.model_validate(data)
    with pytest.raises(MechanismError, match='invalid_time_basis'):
        activate(registry(defs))
    data['outputs'][0]['value_type']['time_basis_id'] = 'day'
    defs[0] = MechanismDefinition.model_validate(data)
    assert activate(registry(defs)).outputs[0].value_type.time_basis_id == 'day'


@pytest.mark.parametrize('options,code', [
    (dict(phase='transition'), 'unsupported_phase'),
    (dict(phase='shell'), 'invalid_phase'),
    (dict(entity_id='account'), 'unsupported_context'),
    (dict(scope_id='absent'), 'missing_scope'),
])
def test_scope_entity_and_phase_authority(options, code):
    with pytest.raises((MechanismError, WorldError), match=code):
        activate(registry(), **options)


def test_qualitative_drafts_are_inspectable_without_external_resolution():
    defs = definitions()
    data = defs[0].model_dump()
    data.update(modeling='qualitative', support=dict(static=None, transition=None))
    data['outputs'][0]['value_type']['unit_id'] = 'uninstalled'
    draft = MechanismDefinition.model_validate(data)
    r = registry([], implementations=[], reviews=[]).with_definition(draft)
    assert r.definition(draft.id, draft.version).modeling == 'qualitative'
    with pytest.raises(NumericError, match='unknown_unit'):
        activate(r)


def test_graph_content_never_resolves_to_trusted_python_by_same_name():
    defs = definitions()
    data = defs[0].model_dump()
    data['support']['static']['kind'] = 'declarative_graph'
    defs[0] = MechanismDefinition.model_validate(data)
    with pytest.raises(MechanismError, match='graph_validation_required'):
        activate(registry(defs))


def test_policy_resolution_and_fixture_versions_are_exact():
    defs = definitions()
    data = defs[0].model_dump()
    data['policy'] = dict(semantics='floor', composition_rule=dict(id='synthetic:compose', version='v1'))
    defs[0] = MechanismDefinition.model_validate(data)
    r = registry(defs)
    with pytest.raises(MechanismError, match='unknown_composition_rule'):
        activate(r)
    assert activate(registry(defs, implementations=(*r.implementations,
        Implementation('synthetic:compose', 'v1', 'composition', lambda: None)))).policy.semantics == 'floor'
    with pytest.raises(MechanismError, match='unresolved_fixtures'):
        activate(registry(fixture_ids=[('synthetic:positive', 'v2')]))


def test_duplicate_version_rejected_but_new_version_can_be_inspected():
    r = registry()
    with pytest.raises(MechanismError, match='duplicate_identity'):
        r.with_definition(r.definitions[0])
    changed = r.definitions[0].model_copy(update={'version': 'v2'})
    assert r.with_definition(changed).definition(changed.id, 'v2').version == 'v2'
    with pytest.raises(MechanismError, match='unknown_mechanism'):
        r.definition(changed.id, 'v2')


def stateful():
    defs = definitions()
    data = defs[0].model_dump()
    data['owned_state'] = [dict(id='synthetic:stock', owner_domain='provisioning', partition='dynamic_state',
                                value_type=data['outputs'][0]['value_type'])]
    data['write_state_refs'] = ['synthetic:stock']
    data['support']['transition'] = data['support']['static']
    defs[0] = MechanismDefinition.model_validate(data)
    return registry(defs)


def change(**updates):
    return PartitionValueDTO.model_validate(dict(id='stock-value', entity_id='supply', scope_id='local',
        property_id='synthetic:stock', partition='dynamic_state', value=dict(kind='quantity', value='1.25',
            unit_id='kg', time_basis_id=None, denominator_scope_id=None),
        effective_time=dict(tick=0, calendar_id='synthetic'), provenance=PROVENANCE) | updates)


def owned_world(writer='provisioning'):
    return world([StateOwner('supply', 'synthetic:stock', 'dynamic_state', writer)])


def test_state_candidates_are_pure_and_owned_only():
    base = owned_world()
    result = stateful().stage_changes('synthetic:supply', 'v1', world=base,
                                      scope_id='local', entity_id='supply', changes=[change()])
    assert result.values[0].value.value == '1.25'
    assert base.values == ()
    with pytest.raises(MechanismError, match='foreign_state_owner'):
        activate(stateful(), phase='transition', world=owned_world('economy'))


@pytest.mark.parametrize('updates', [dict(entity_id='account'), dict(scope_id='foreign'),
    dict(property_id='undeclared'), dict(partition='goals')])
def test_foreign_and_undeclared_state_batches_leave_base_intact(updates):
    base = owned_world()
    with pytest.raises(MechanismError, match='undeclared_state_write'):
        stateful().stage_changes('synthetic:supply', 'v1', world=base,
            scope_id='local', entity_id='supply', changes=[change(), change(id='bad', **updates)])
    assert not base.values


def test_typed_values_require_exact_units_and_canonical_entity_kind():
    r = registry()
    quantity_type = r.definitions[0].outputs[0].value_type
    r.validate_value(quantity_type, change().value, world())
    with pytest.raises(MechanismError, match='incompatible_value'):
        r.validate_value(quantity_type, change().value.model_copy(update={'unit_id': 'rate'}), world())
    ref_type = r.definitions[1].inputs[1].value_type
    r.validate_value(ref_type, ReferenceValue(kind='reference', entity_id='account'), world())
    with pytest.raises(MechanismError, match='incompatible_reference'):
        r.validate_value(ref_type, ReferenceValue(kind='reference', entity_id='supply'), world())
    with pytest.raises(MechanismError, match='incompatible_value'):
        r.validate_value(quantity_type, ReferenceValue(kind='reference', entity_id='account'), world())


def test_incompatible_cross_domain_ports_rejected():
    with pytest.raises(MechanismError, match='incompatible_port'):
        registry().bind(('synthetic:supply', 'v1'), ('synthetic:demand', 'v1'),
            output_id='synthetic:available', input_id='synthetic:account', world=world(), scope_id='local',
            producer_entity_id='supply', consumer_entity_id='account')


def pack_payload(text=None, **metadata):
    from hashlib import sha256
    from poliscope_engine.packs import PackArchive
    definition = definitions()[0]
    text = definition.model_dump_json() if text is None else text
    digest = 'sha256:' + sha256(text.encode()).hexdigest()
    data = dict(manifest=dict(format_version=1, id='synthetic:pack', version='v1',
        identities={key: dict(id='synthetic:model' if key == 'model' else key, version='v1')
                    for key in ('application', 'schema_identity', 'catalog', 'model', 'numeric')},
        engine_versions=['v1'], dependencies=[], files={'mechanism.json': digest}),
        files=[dict(path='mechanism.json', text=text)], licenses=[], sources=[], assumptions=[],
        definitions=[dict(id=definition.id, version='v1', kind='mechanism', parent_ref=None,
            original_text='Synthetic only', source_decision_id=None, source_refs=[], assumption_refs=[],
            supersedes_refs=[], mechanism_refs=[], variable_refs=[], origin='authored', modeling='numerical',
            evidence='hypothetical', historical_status='unspecified') | metadata],
        variables=[], distributions=[], dependence=[])
    return PackArchive(json.dumps(data).encode())


def attach(r, archive, **options):
    return r.with_pack_definition(archive, **(dict(path='mechanism.json', identity='synthetic:supply', version='v1') | options))


def test_exact_pack_attachment_does_not_grant_activation_or_implicit_evidence():
    data = definitions()[0].model_dump()
    data['source_refs'] = []
    d = MechanismDefinition.model_validate(data)
    r = attach(registry([], reviews=[]), pack_payload(d.model_dump_json()))
    assert r.definitions == (d,)
    with pytest.raises(MechanismError, match='unknown_implementation'):
        activate(r)
    # Trusted implementation availability alone still needs digest-bound host review.
    r = attach(registry([], implementations=registry().implementations), pack_payload(d.model_dump_json()))
    with pytest.raises(MechanismError, match='review_required'):
        activate(r)


@pytest.mark.parametrize('options', [dict(path='absent'), dict(identity='synthetic:foreign'), dict(version='v2')])
def test_pack_attachment_requires_exact_file_and_declared_identity(options):
    with pytest.raises(MechanismError, match='missing_pack_mechanism'):
        attach(registry([]), pack_payload(), **options)


def test_pack_identity_metadata_and_duplicate_json_keys_rejected():
    with pytest.raises(MechanismError, match='pack_model_mismatch'):
        attach(registry([], model=('other', 'v1')), pack_payload())
    with pytest.raises(MechanismError, match='pack_declaration_mismatch'):
        attach(registry([]), pack_payload())  # archived source differs from metadata
    data = definitions()[0].model_dump()
    data['source_refs'] = []
    text = json.dumps(data)
    duplicate = text[:-1] + ', "version":"v1"}'
    with pytest.raises(MechanismError, match='duplicate_json_key'):
        attach(registry([]), pack_payload(duplicate))


def test_reviewed_pack_attachment_activates_only_exact_reviewed_content():
    data = definitions()[0].model_dump()
    data['source_refs'] = []
    d = MechanismDefinition.model_validate(data)
    trusted = registry([d])
    r = attach(registry([], implementations=trusted.implementations, reviews=trusted.reviews),
               pack_payload(d.model_dump_json()))
    assert activate(r).id == d.id
    data['coverage_limits'] = 'Changed archived definition with same identity.'
    edited = attach(registry([], implementations=trusted.implementations, reviews=trusted.reviews),
                    pack_payload(json.dumps(data)))
    with pytest.raises(MechanismError, match='review_required'):
        activate(edited)


@pytest.mark.parametrize('value', [dict(kind='label', value='wrong'),
    dict(kind='quantity', value='1', unit_id='rate', time_basis_id=None, denominator_scope_id=None),
    dict(kind='quantity', value='1e257', unit_id='kg', time_basis_id=None, denominator_scope_id=None)])
def test_invalid_state_values_cannot_enter_candidate(value):
    base = owned_world()
    with pytest.raises((MechanismError, NumericError)):
        stateful().stage_changes('synthetic:supply', 'v1', world=base, scope_id='local',
                                  entity_id='supply', changes=[change(value=value)])
    assert not base.values


def test_trusted_implementation_version_and_phase_cannot_be_substituted():
    for implementation in (Implementation('synthetic:supply-implementation', 'v2', 'static', lambda: None),
                           Implementation('synthetic:supply-implementation', 'v1', 'transition', lambda: None)):
        with pytest.raises(MechanismError, match='unknown_implementation'):
            activate(registry(implementations=[implementation]))
    with pytest.raises(MechanismError, match='duplicate_identity'):
        registry(implementations=[implementation, implementation])


def test_absent_assumption_blocks_activation_even_with_review():
    defs = definitions()
    defs[0].assumption_refs.append('synthetic:assumption')
    with pytest.raises(MechanismError, match='unresolved_evidence'):
        activate(registry(defs))
    assert activate(registry(defs, assumption_ids=['synthetic:assumption'])).assumption_refs
