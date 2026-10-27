"""Pure identity/state registry. Persistence and membership are separate services."""
from dataclasses import dataclass
from types import MappingProxyType
from hashlib import sha256
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
        # Derived immutable indexes stay outside dataclass fields/canonical data.
        object.__setattr__(self, '_entity_index', MappingProxyType({
            e.id: raw for e, raw in zip(entity_map.values(), entity_data, strict=True)}))
        object.__setattr__(self, '_scope_index', MappingProxyType({
            s.id: raw for s, raw in zip(scope_map.values(), scope_data, strict=True)}))
        shape = sha256()
        for part in (civilization_id, *entity_data, *scope_data, repr(owner_data), repr(population_data)):
            encoded = part.encode()
            shape.update(len(encoded).to_bytes(8, 'big'))
            shape.update(encoded)
        object.__setattr__(self, '_shape_token', shape.hexdigest())
        from poliscope_engine.evaluation.canonical import Fragment
        for name, rows in (('entities', tuple(entity_map.values())), ('scopes', tuple(scope_map.values())),
                           ('owners', owner_data), ('populations', population_data)):
            object.__setattr__(self, '_canonical_' + name, Fragment(rows, name))
        object.__setattr__(self, '_entity_kinds', MappingProxyType({k: v.entity_kind for k, v in entity_map.items()}))
        object.__setattr__(self, '_scope_kinds', MappingProxyType({k: v.scope_kind for k, v in scope_map.items()}))

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

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
        raw = self._entity_index.get(identity)
        if raw is None:
            raise WorldError('missing_entity')
        return EntityDTO.model_validate_json(raw)

    def scope(self, identity: str):
        raw = self._scope_index.get(identity)
        if raw is None:
            raise WorldError('missing_scope')
        return ScopeDTO.model_validate_json(raw)

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
        return self._replace_values(old.values())

    def _replace_values(self, values):
        """Constructor-equivalent value validation over a verified static shape."""
        values = tuple(PartitionValueDTO.model_validate_json(v.model_dump_json()) for v in values)
        # Static identities/ownership were already validated and are immutable.
        # Validate the resulting value namespace without reparsing every entity
        # and scope once per domain write.
        seen_ids = set(self._entity_index) | set(self._scope_index)
        seen_slots = set()
        ownership = {o.key: o.writer_id for o in self.owners}
        for value in values:
            if value.id in seen_ids:
                raise WorldError('duplicate_identity')
            seen_ids.add(value.id)
            slot = value.entity_id, value.property_id, value.partition
            if slot in seen_slots:
                raise WorldError('duplicate_state_slot')
            seen_slots.add(slot)
            if value.entity_id not in self._entity_index or value.scope_id not in self._scope_index:
                raise WorldError('missing_reference')
            if slot not in ownership:
                raise WorldError('missing_state_owner')
            if isinstance(value.value, ReferenceValue) and value.value.entity_id not in self._entity_index:
                raise WorldError('missing_reference')
            if isinstance(value.value, QuantityValue):
                parse(value.value.value)
                if value.value.denominator_scope_id is not None and value.value.denominator_scope_id not in self._scope_index:
                    raise WorldError('missing_reference')
        result = object.__new__(WorldRegistry)
        for field in ('civilization_id', '_entities', '_scopes', 'owners', 'populations',
                      '_entity_index', '_scope_index', '_shape_token', '_entity_kinds', '_scope_kinds',
                      '_canonical_entities', '_canonical_scopes', '_canonical_owners', '_canonical_populations'):
            object.__setattr__(result, field, getattr(self, field))
        object.__setattr__(result, '_values', tuple(v.model_dump_json() for v in values))
        return result
