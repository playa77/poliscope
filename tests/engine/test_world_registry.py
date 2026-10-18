"""Synthetic identity/ownership invariants; no domain mechanism is certified."""
from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, PartitionValueDTO, EntityKind
from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration, WorldError
from typing import get_args

PROVENANCE = dict(origin='authored', source_refs=[], assumption_refs=[])


def entity(identity='civ', kind='civilization'):
    return EntityDTO(id=identity, entity_kind=kind, label='Synthetic', provenance=PROVENANCE)


def scope(identity='local'):
    return ScopeDTO(id=identity, scope_kind='community', label='Synthetic', provenance=PROVENANCE)


def value(identity='stock', partition='dynamic_state', amount='10', **updates):
    return PartitionValueDTO.model_validate(dict(
        id=identity, entity_id='asset', scope_id='local', partition=partition,
        property_id='water', value=dict(kind='quantity', value=amount, unit_id='litre',
                                      time_basis_id=None, denominator_scope_id=None),
        effective_time=dict(tick=0, calendar_id='synthetic'), provenance=PROVENANCE,
    ) | updates)


def registry(**updates):
    return WorldRegistry('civ', **(dict(
        entities=[entity(), entity('asset', 'asset')], scopes=[scope()],
        owners=[StateOwner('asset', 'water', 'dynamic_state', 'water-domain'),
                StateOwner('asset', 'water', 'goals', 'player')],
        values=[value()],
    ) | updates))


def fails(code, operation):
    with pytest.raises(WorldError) as error:
        operation()
    assert error.value.code == code


@pytest.mark.parametrize('kind', get_args(EntityKind))
def test_all_entity_kinds_have_stable_queryable_identity(kind):
    entities = [entity()] if kind == 'civilization' else [entity(), entity('item', kind)]
    populations = [PopulationDeclaration('item', 'fixed_input')] if kind == 'population_cohort' else []
    world = WorldRegistry('civ', entities=entities, scopes=[scope()], populations=populations)
    assert world.entity('civ' if kind == 'civilization' else 'item').entity_kind == kind
    assert world.scope('local').id == 'local'
    fails('missing_entity', lambda: world.entity('absent'))
    fails('missing_scope', lambda: world.scope('absent'))


def test_snapshot_detaches_inputs_and_queries_recursively():
    original = value()
    world = registry(values=[original])
    original.provenance.source_refs.append('later-edit')
    world.values[0].provenance.source_refs.append('query-edit')
    world.entities[0].provenance.assumption_refs.append('query-edit')
    assert world.values[0].provenance.source_refs == []
    assert world.entities[0].provenance.assumption_refs == []
    with pytest.raises(FrozenInstanceError):
        world.civilization_id = 'different'


@pytest.mark.parametrize('entities', [[entity(), entity()], [entity('other')],
                                     [entity(), entity('other')], []])
def test_invalid_civilization_or_duplicates(entities):
    with pytest.raises(WorldError):
        registry(entities=entities)


def test_identity_namespace_and_slot_uniqueness():
    fails('duplicate_identity', lambda: registry(scopes=[scope('asset')]))
    fails('duplicate_identity', lambda: registry(values=[value('asset')]))
    fails('duplicate_identity', lambda: registry(values=[value(), value()]))
    fails('duplicate_state_slot', lambda: registry(values=[value(), value('alias')]))
    fails('duplicate_state_slot', lambda: registry(
        scopes=[scope(), scope('watershed')],
        values=[value(), value('alias', scope_id='watershed')]))
    fails('duplicate_state_owner', lambda: registry(owners=[
        StateOwner('asset', 'water', 'dynamic_state', 'a'),
        StateOwner('asset', 'water', 'dynamic_state', 'b')]))


@pytest.mark.parametrize('updates', [dict(entity_id='absent'), dict(scope_id='absent'),
    dict(value=dict(kind='reference', entity_id='absent')),
    dict(value=dict(kind='quantity', value='1', unit_id='litre', time_basis_id=None,
                    denominator_scope_id='absent'))])
def test_foreign_references_fail(updates):
    fails('missing_reference', lambda: registry(values=[value(**updates)]))


def test_owner_and_population_declarations():
    fails('missing_state_owner', lambda: registry(owners=[]))
    fails('missing_entity', lambda: registry(owners=[StateOwner('absent', 'water', 'goals', 'a')]))
    cohorts = [entity(), entity('people', 'population_cohort')]
    fails('invalid_population_declarations', lambda: registry(entities=cohorts, values=[], owners=[]))
    for role in ('fixed_input', 'dynamic_state', 'solved_capacity_bound'):
        world = registry(entities=cohorts, values=[], owners=[],
                         populations=[PopulationDeclaration('people', role)])
        assert world.populations[0].role == role
    fails('invalid_population_declarations', lambda: registry(populations=[PopulationDeclaration('asset', 'fixed_input')]))
    fails('invalid_population_declarations', lambda: registry(entities=cohorts, values=[], owners=[],
        populations=[PopulationDeclaration('people', 'fixed_input'), PopulationDeclaration('people', 'dynamic_state')]))
    fails('invalid_population_role', lambda: PopulationDeclaration('people', 'implicit'))


def test_goal_change_only_changes_goal_and_failed_batch_is_atomic():
    world = registry()
    candidate = world.with_values(writer_id='player', partition='goals', changes=[value('target', 'goals', '100')])
    assert [(v.id, v.value.value) for v in candidate.values] == [('stock', '10'), ('target', '100')]
    assert len(world.values) == 1
    fails('state_write_denied', lambda: world.with_values(writer_id='player', partition='goals',
        changes=[value('target', 'goals'), value(amount='0')]))
    fails('state_write_denied', lambda: world.with_values(writer_id='other-domain', partition='dynamic_state', changes=[value(amount='0')]))
    assert world.values[0].value.value == '10'


def test_candidate_keeps_id_scope_and_slot_and_allows_authorized_update():
    world = registry(scopes=[scope(), scope('other')])
    candidate = world.with_values(writer_id='water-domain', partition='dynamic_state', changes=[value(amount='9')])
    assert candidate.values[0].id == 'stock'
    assert candidate.values[0].value.value == '9'
    assert world.values[0].value.value == '10'
    fails('identity_rebound', lambda: world.with_values(writer_id='water-domain', partition='dynamic_state',
                                                      changes=[value(scope_id='other')]))
    fails('identity_rebound', lambda: world.with_values(writer_id='player', partition='goals', changes=[value('stock', 'goals')]))
    fails('duplicate_identity', lambda: world.with_values(writer_id='water-domain', partition='dynamic_state', changes=[value(), value()]))
    fails('duplicate_state_slot', lambda: world.with_values(writer_id='water-domain', partition='dynamic_state', changes=[value('alias')]))


def test_bypassed_dto_validation_and_numeric_precision_fail_before_staging():
    with pytest.raises(ValidationError):
        registry(values=[value().model_copy(update={'partition': 'invented'})])
    with pytest.raises(ValueError):
        registry(values=[value(amount='12345678901234567890123456789')])
    with pytest.raises(ValidationError):
        StateOwner('', 'water', 'goals', 'player')


@pytest.mark.parametrize('partition', ['conditions', 'design', 'assumptions', 'dynamic_state', 'observations'])
def test_goal_batch_cannot_change_any_other_partition_even_for_shared_writer(partition):
    world = registry(values=[value(partition=partition)], owners=[
        StateOwner('asset', 'water', partition, 'player'),
        StateOwner('asset', 'water', 'goals', 'player')])
    before = world._values
    fails('state_write_denied', lambda: world.with_values(writer_id='player', partition='goals',
        changes=[value(partition=partition, amount='999')]))
    assert world._values == before
