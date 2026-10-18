"""Pure identity/state registry. Persistence and membership are separate services."""
from dataclasses import dataclass
from typing import Literal

from pydantic import TypeAdapter

from poliscope_engine.contracts.base import Identifier
from poliscope_engine.contracts.world import (
    EntityDTO, ScopeDTO, PartitionValueDTO, Partition, QuantityValue, ReferenceValue,
)
from poliscope_engine.numeric import parse

_IDENTIFIER = TypeAdapter(Identifier)
_PARTITION = TypeAdapter(Partition)
PopulationRole = Literal['fixed_input', 'dynamic_state', 'solved_capacity_bound']


class WorldError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class StateOwner:
    """One writer per canonical entity/property/partition, across every scope."""
    entity_id: str
    property_id: str
    partition: Partition
    writer_id: str

    def __post_init__(self):
        for value in (self.entity_id, self.property_id, self.writer_id):
            _IDENTIFIER.validate_python(value, strict=True)
        _PARTITION.validate_python(self.partition, strict=True)

    @property
    def key(self):
        return self.entity_id, self.property_id, self.partition


@dataclass(frozen=True)
class PopulationDeclaration:
    entity_id: str
    role: PopulationRole

    def __post_init__(self):
        _IDENTIFIER.validate_python(self.entity_id, strict=True)
        if self.role not in ('fixed_input', 'dynamic_state', 'solved_capacity_bound'):
            raise WorldError('invalid_population_role')


@dataclass(frozen=True, init=False)
class WorldRegistry:
    """Immutable normalized snapshots; DTO queries return detached copies.

    IDs are caller-supplied and never inferred from labels or array positions.
    Ownership is structural, not authentication: a trusted caller selects writer
    and partition. No database publication or public IPC is provided here.
    """
    civilization_id: str
    _entities: tuple[str, ...]
    _scopes: tuple[str, ...]
    _values: tuple[str, ...]
    owners: tuple[StateOwner, ...]
    populations: tuple[PopulationDeclaration, ...]

    def __init__(self, civilization_id: str, *, entities=(), scopes=(), values=(),
                 owners=(), populations=()):
        _IDENTIFIER.validate_python(civilization_id, strict=True)
        # Reparse even model instances: frozen DTOs can contain mutable lists and
        # model_copy(update=...) bypasses Pydantic validation.
        def snapshot(model, items):
            return tuple(model.model_validate_json(item.model_dump_json()).model_dump_json()
                         for item in items)
        entity_data = snapshot(EntityDTO, entities)
        scope_data = snapshot(ScopeDTO, scopes)
        value_data = snapshot(PartitionValueDTO, values)
        entity_map = {e.id: e for e in map(EntityDTO.model_validate_json, entity_data)}
        scope_map = {s.id: s for s in map(ScopeDTO.model_validate_json, scope_data)}
        if len(entity_map) != len(entity_data) or len(scope_map) != len(scope_data):
            raise WorldError('duplicate_identity')
        if entity_map.keys() & scope_map.keys():
            raise WorldError('duplicate_identity')
        civs = [e.id for e in entity_map.values() if e.entity_kind == 'civilization']
        if civs != [civilization_id]:
            raise WorldError('invalid_civilization')
        owner_data = tuple(StateOwner(o.entity_id, o.property_id, o.partition, o.writer_id)
                           for o in owners)
        ownership = {o.key: o.writer_id for o in owner_data}
        if len(ownership) != len(owner_data):
            raise WorldError('duplicate_state_owner')
        if any(o.entity_id not in entity_map for o in owner_data):
            raise WorldError('missing_entity')
        population_data = tuple(PopulationDeclaration(p.entity_id, p.role) for p in populations)
        roles = {p.entity_id: p.role for p in population_data}
        cohorts = {e.id for e in entity_map.values() if e.entity_kind == 'population_cohort'}
        if len(roles) != len(population_data) or roles.keys() != cohorts:
            raise WorldError('invalid_population_declarations')
        seen_ids, seen_slots = set(entity_map) | set(scope_map), set()
        for value in map(PartitionValueDTO.model_validate_json, value_data):
            if value.id in seen_ids:
                raise WorldError('duplicate_identity')
            seen_ids.add(value.id)
            if value.entity_id not in entity_map or value.scope_id not in scope_map:
                raise WorldError('missing_reference')
            slot = value.entity_id, value.property_id, value.partition
            if slot in seen_slots:
                raise WorldError('duplicate_state_slot')
            seen_slots.add(slot)
            if slot not in ownership:
                raise WorldError('missing_state_owner')
            if isinstance(value.value, ReferenceValue) and value.value.entity_id not in entity_map:
                raise WorldError('missing_reference')
            if isinstance(value.value, QuantityValue):
                parse(value.value.value)
                denominator = value.value.denominator_scope_id
                if denominator is not None and denominator not in scope_map:
                    raise WorldError('missing_reference')
        object.__setattr__(self, 'civilization_id', civilization_id)
        object.__setattr__(self, '_entities', entity_data)
        object.__setattr__(self, '_scopes', scope_data)
        object.__setattr__(self, '_values', value_data)
        object.__setattr__(self, 'owners', owner_data)
        object.__setattr__(self, 'populations', population_data)

    @property
    def entities(self):
        return tuple(map(EntityDTO.model_validate_json, self._entities))

    @property
    def scopes(self):
        return tuple(map(ScopeDTO.model_validate_json, self._scopes))

    @property
    def values(self):
        return tuple(map(PartitionValueDTO.model_validate_json, self._values))

    def entity(self, identity: str):
        for entity in self.entities:
            if entity.id == identity:
                return entity
        raise WorldError('missing_entity')

    def scope(self, identity: str):
        for scope in self.scopes:
            if scope.id == identity:
                return scope
        raise WorldError('missing_scope')

    def with_values(self, *, writer_id: str, partition: Partition, changes):
        """Stage a full validated candidate; failed batches leave the base intact."""
        _IDENTIFIER.validate_python(writer_id, strict=True)
        _PARTITION.validate_python(partition, strict=True)
        changes = tuple(PartitionValueDTO.model_validate_json(v.model_dump_json()) for v in changes)
        ownership = {o.key: o.writer_id for o in self.owners}
        old = {v.id: v for v in self.values}
        seen = set()
        for value in changes:
            if value.id in seen:
                raise WorldError('duplicate_identity')
            seen.add(value.id)
            slot = value.entity_id, value.property_id, value.partition
            if value.partition != partition or ownership.get(slot) != writer_id:
                raise WorldError('state_write_denied')
            previous = old.get(value.id)
            if previous is not None and (
                previous.entity_id, previous.property_id, previous.partition, previous.scope_id
            ) != (*slot, value.scope_id):
                raise WorldError('identity_rebound')
            old[value.id] = value
        return WorldRegistry(self.civilization_id, entities=self.entities, scopes=self.scopes,
                             values=old.values(), owners=self.owners, populations=self.populations)
