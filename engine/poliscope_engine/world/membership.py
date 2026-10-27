"""Pure relationship snapshots and explicit direct-membership aggregation."""
from dataclasses import dataclass
from types import MappingProxyType
from fractions import Fraction

from poliscope_engine.contracts.world import RelationshipDTO, QuantityValue, UnknownValue
from poliscope_engine.numeric import parse, exact, canonical
from poliscope_engine.world import WorldRegistry, WorldError, _PARTITION, _IDENTIFIER


@dataclass(frozen=True, init=False)
class WorldGraph:
    registry: WorldRegistry
    _relationships: tuple[str, ...]

    def __init__(self, registry: WorldRegistry, relationships=()):
        rows = tuple(RelationshipDTO.model_validate_json(r.model_dump_json()) for r in relationships)
        entities = {e.id: e for e in registry.entities}
        scopes = {s.id for s in registry.scopes}
        endpoints = entities.keys() | scopes
        namespace = set(entities) | scopes | {v.id for v in registry.values}
        edges = {}
        memberships = set()
        for row in rows:
            if row.id in namespace:
                raise WorldError('duplicate_identity')
            namespace.add(row.id)
            if row.from_id not in endpoints or row.to_id not in endpoints:
                raise WorldError('missing_reference')
            if row.relationship_kind == 'containment':
                edges.setdefault(row.from_id, []).append(row.to_id)
            if row.aggregation.kind != 'non_aggregating':
                if row.from_id not in entities or row.to_id not in scopes:
                    raise WorldError('invalid_membership_endpoints')
                key = row.from_id, row.to_id
                if key in memberships:
                    raise WorldError('duplicate_membership')
                memberships.add(key)
                if row.aggregation.kind == 'weight' and not 0 < parse(row.aggregation.weight) <= 1:
                    raise WorldError('invalid_membership_weight')
            if row.relationship_kind == 'cohort_membership':
                if row.from_id not in entities or entities[row.from_id].entity_kind != 'population_cohort' or row.to_id not in scopes:
                    raise WorldError('invalid_membership_endpoints')
                if row.aggregation.kind == 'non_aggregating':
                    raise WorldError('missing_membership_rule')
        # Iterative DFS avoids recursion limits on long valid containment chains.
        done, active = set(), set()
        for root in edges:
            stack = [(root, False)]
            while stack:
                node, leaving = stack.pop()
                if leaving:
                    active.remove(node)
                    done.add(node)
                elif node in active:
                    raise WorldError('containment_cycle')
                elif node not in done:
                    active.add(node)
                    stack.append((node, True))
                    stack.extend((child, False) for child in edges.get(node, ()))
        object.__setattr__(self, 'registry', registry)
        object.__setattr__(self, '_relationships', tuple(r.model_dump_json() for r in rows))
        object.__setattr__(self, '_relationship_ids', frozenset(r.id for r in rows))
        from poliscope_engine.evaluation.canonical import Fragment
        object.__setattr__(self, '_canonical_relationships', Fragment(rows, 'relationships'))
        object.__setattr__(self, '_jurisdiction', frozenset((r.from_id, r.to_id) for r in rows
            if r.relationship_kind == 'jurisdiction'))
        member_index = {scope: set() for scope in scopes}
        for row in rows:
            if row.aggregation.kind != 'non_aggregating':
                member_index[row.to_id].add(row.from_id)
        object.__setattr__(self, '_members', MappingProxyType({k: frozenset(v) for k, v in member_index.items()}))
        adjacency = {identity: [] for identity in entities.keys() | scopes}
        for index, row in enumerate(rows):
            for identity in {row.from_id, row.to_id}:
                adjacency[identity].append(index)
        # Derived index deliberately stays outside dataclass fields, so generic
        # canonical serialization and equality retain the original world identity.
        object.__setattr__(self, '_adjacency', MappingProxyType(
            {identity: tuple(indices) for identity, indices in adjacency.items()}))

    def with_registry(self, registry):
        if registry._shape_token != self.registry._shape_token:
            return WorldGraph(registry, self.relationships)
        if any(v.id in self._relationship_ids for v in registry.values):
            raise WorldError('duplicate_identity')
        result = object.__new__(WorldGraph)
        object.__setattr__(result, 'registry', registry)
        for name in ('_relationships', '_relationship_ids', '_adjacency',
                     '_canonical_relationships', '_jurisdiction', '_members'):
            object.__setattr__(result, name, getattr(self, name))
        return result

    def __deepcopy__(self, memo):
        # All stored snapshots/index entries are immutable; DTO reads detach.
        return self

    @property
    def relationships(self):
        return tuple(map(RelationshipDTO.model_validate_json, self._relationships))

    def related(self, identity, *, kind=None):
        if identity not in self._adjacency:
            raise WorldError('missing_reference')
        rows = (RelationshipDTO.model_validate_json(self._relationships[i])
                for i in self._adjacency[identity])
        return tuple(r for r in rows if kind is None or r.relationship_kind == kind)

    def with_relationships(self, relationships):
        """Validate an entire replacement snapshot before returning a candidate."""
        return WorldGraph(self.registry, relationships)

    def aggregate(self, scope_ids, *, property_id, partition):
        """Sum direct members only; never traverse containment or infer weights.

        Partition IDs identify the same indivisible canonical member across views.
        Weighted memberships represent disjoint declared shares; their selected
        total must not exceed one. Mixing partition and weight rules is ambiguous.
        Missing data is unknown, and incompatible metadata fails closed.
        """
        _PARTITION.validate_python(partition, strict=True)
        _IDENTIFIER.validate_python(property_id, strict=True)
        selected = set(scope_ids)
        if not selected or not selected <= {s.id for s in self.registry.scopes}:
            raise WorldError('invalid_aggregation_scopes')
        members = {}
        for row in self.relationships:
            if row.to_id in selected and row.aggregation.kind != 'non_aggregating':
                members.setdefault(row.from_id, []).append(row.aggregation)
        coefficients = {}
        for identity, rules in members.items():
            kinds = {r.kind for r in rules}
            if len(kinds) != 1:
                raise WorldError('ambiguous_membership')
            if kinds == {'partition'}:
                if len({r.partition_id for r in rules}) != 1:
                    raise WorldError('ambiguous_membership')
                coefficients[identity] = Fraction(1)
            else:
                coefficient = sum((Fraction(parse(r.weight)) for r in rules), Fraction())
                if coefficient > 1:
                    raise WorldError('membership_overallocated')
                coefficients[identity] = coefficient
        if not coefficients:
            return UnknownValue(kind='unknown', reason='No declared aggregating members')
        values = {(v.entity_id, v.property_id, v.partition): v for v in self.registry.values}
        total, metadata = Fraction(), None
        unknown = False
        for identity, coefficient in coefficients.items():
            record = values.get((identity, property_id, partition))
            value = record.value if record is not None else None
            if value is None or isinstance(value, UnknownValue):
                unknown = True
                continue
            if not isinstance(value, QuantityValue):
                raise WorldError('non_quantity_aggregation')
            signature = (value.unit_id, value.time_basis_id, value.denominator_scope_id,
                         record.effective_time.tick, record.effective_time.calendar_id)
            if metadata is not None and signature != metadata:
                raise WorldError('incompatible_aggregation')
            metadata = signature
            total += Fraction(parse(value.value)) * coefficient
        if unknown:
            return UnknownValue(kind='unknown', reason='A canonical member has unknown or missing data')
        return QuantityValue(kind='quantity', value=canonical(exact(total)), unit_id=metadata[0],
                             time_basis_id=metadata[1], denominator_scope_id=metadata[2])
