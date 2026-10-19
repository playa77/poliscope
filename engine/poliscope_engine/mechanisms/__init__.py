"""Trusted, immutable registration. Content never supplies executable authority."""
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable

from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.world import PartitionValueDTO, QuantityValue, ReferenceValue
from poliscope_engine.numeric import Registry as Units, TimeBasis, parse
from poliscope_engine.world import WorldRegistry
from poliscope_engine.packs import PackArchive


class MechanismError(ValueError):
    pass


def snapshot(definition):
    return MechanismDefinition.model_validate_json(definition.model_dump_json())


def declaration_digest(definition):
    data = snapshot(definition).model_dump(mode='json')
    return 'sha256:' + sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class Implementation:
    """Application-owned code reference, never an import path from a pack."""
    id: str
    version: str
    phase: str
    callback: Callable

    def __post_init__(self):
        if not self.id or not self.version or self.phase not in ('static', 'transition', 'composition') or not callable(self.callback):
            raise MechanismError('invalid_implementation')

    @property
    def key(self):
        return self.id, self.version, self.phase


@dataclass(frozen=True)
class Review:
    """Trusted host's review disposition; never parsed from pack metadata.

    The host verifies actual review/fixture evidence before constructing this
    record. IDs are durable references, not a claim this registry ran a review.
    """
    declaration_digest: str
    model_id: str
    model_version: str
    evidence_review_ref: str
    independent_fixture_review_ref: str
    graph_digest: str | None = None

    def __post_init__(self):
        required = (self.declaration_digest, self.model_id, self.model_version,
                    self.evidence_review_ref, self.independent_fixture_review_ref)
        if (not all(type(v) is str and v for v in required) or
                self.graph_digest is not None and
                (type(self.graph_digest) is not str or not self.graph_digest)):
            raise MechanismError('invalid_review')


@dataclass(frozen=True, init=False)
class MechanismRegistry:
    model: tuple[str, str]
    units: Units
    times: tuple[TimeBasis, ...]
    source_ids: frozenset[str]
    assumption_ids: frozenset[str]
    fixture_ids: frozenset[tuple[str, str]]
    implementations: tuple[Implementation, ...]
    reviews: tuple[Review, ...]
    _definitions: tuple[str, ...]
    _graphs: tuple[str, ...]

    def __init__(self, *, model, units, times=(), source_ids=(), assumption_ids=(),
                 fixture_ids=(), implementations=(), reviews=(), definitions=(), graphs=()):
        model = tuple(model)
        if len(model) != 2 or not all(type(v) is str and v for v in model):
            raise MechanismError('invalid_model')
        times, implementations, reviews = tuple(times), tuple(implementations), tuple(reviews)
        from .expressions import snapshot as graph_snapshot
        graphs = tuple(graph_snapshot(g) for g in graphs)
        definitions = tuple(snapshot(d) for d in definitions)
        for keys in ([t.id for t in times], [i.key for i in implementations],
                     [(r.declaration_digest, r.graph_digest) for r in reviews],
                     [(g.id, g.version) for g in graphs],
                     [(d.id, d.version) for d in definitions]):
            if len(keys) != len(set(keys)):
                raise MechanismError('duplicate_identity')
        for name, value in dict(model=model, units=units, times=times,
                source_ids=frozenset(source_ids), assumption_ids=frozenset(assumption_ids),
                fixture_ids=frozenset(fixture_ids), implementations=implementations, reviews=reviews,
                _definitions=tuple(d.model_dump_json() for d in definitions),
                _graphs=tuple(g.model_dump_json() for g in graphs)).items():
            object.__setattr__(self, name, value)

    @property
    def definitions(self):
        return tuple(map(MechanismDefinition.model_validate_json, self._definitions))

    def definition(self, identity, version):
        for definition in self.definitions:
            if (definition.id, definition.version) == (identity, version):
                return definition
        raise MechanismError('unknown_mechanism')

    @property
    def graphs(self):
        from poliscope_engine.contracts.expressions import ExpressionGraph
        return tuple(map(ExpressionGraph.model_validate_json, self._graphs))

    def _graph(self, procedure):
        graph = next((g for g in self.graphs if (g.id, g.version) ==
                     (procedure.implementation.id, procedure.implementation.version)), None)
        if graph is None:
            raise MechanismError('graph_validation_required')
        return graph

    def with_definition(self, definition):
        return MechanismRegistry(model=self.model, units=self.units, times=self.times,
            source_ids=self.source_ids, assumption_ids=self.assumption_ids,
            fixture_ids=self.fixture_ids, implementations=self.implementations,
            reviews=self.reviews, definitions=(*self.definitions, definition), graphs=self.graphs)

    def with_pack_definition(self, archive: PackArchive, *, path, identity, version):
        """Attach exact validated archived JSON, never a separately supplied DTO."""
        pack = archive.pack
        if (pack.manifest.identities.model.id, pack.manifest.identities.model.version) != self.model:
            raise MechanismError('pack_model_mismatch')
        declared = next((d for d in pack.definitions if (d.id, d.version, d.kind) ==
                         (identity, version, 'mechanism')), None)
        file = next((f for f in pack.files if f.path == path), None)
        if declared is None or file is None:
            raise MechanismError('missing_pack_mechanism')
        # Same strict duplicate-key policy as PackArchive.
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise MechanismError('duplicate_json_key')
                result[key] = value
            return result
        definition = MechanismDefinition.model_validate(json.loads(file.text, object_pairs_hook=unique))
        fields = ('id', 'version', 'source_refs', 'assumption_refs', 'origin', 'modeling', 'evidence')
        if any(getattr(definition, field) != getattr(declared, field) for field in fields):
            raise MechanismError('pack_declaration_mismatch')
        return self.with_definition(definition)

    def _type(self, value_type, world):
        if value_type.kind != 'quantity':
            return
        unit = self.units.unit(value_type.unit_id)
        time = value_type.time_basis_id
        if time is not None and time not in {t.id for t in self.times}:
            raise MechanismError('unknown_time_basis')
        if (unit.kind in ('flow', 'capacity') and time is None or
                unit.kind not in ('flow', 'capacity', 'indicator') and time is not None):
            raise MechanismError('invalid_time_basis')
        if value_type.denominator_scope_id is not None:
            world.scope(value_type.denominator_scope_id)

    def activate(self, identity, version, *, phase, world: WorldRegistry, scope_id, entity_id):
        """Validate an activation context; no callback or numerical rule runs."""
        definition = self.definition(identity, version)
        if phase not in ('static', 'transition'):
            raise MechanismError('invalid_phase')
        if world.scope(scope_id).scope_kind not in definition.scope_kinds or world.entity(entity_id).entity_kind not in definition.entity_kinds:
            raise MechanismError('unsupported_context')
        if not set(definition.source_refs) <= self.source_ids or not set(definition.assumption_refs) <= self.assumption_ids:
            raise MechanismError('unresolved_evidence')
        for port in (*definition.inputs, *definition.outputs, *definition.owned_state):
            self._type(port.value_type, world)
        procedure = getattr(definition.support, phase)
        if procedure is None:
            raise MechanismError('unsupported_phase')
        digest = None
        if procedure.kind == 'declarative_graph':
            from .expressions import compile_graph, graph_digest
            graph = self._graph(procedure)
            compile_graph(graph, definition, phase, self, world)
            digest = graph_digest(graph)
        else:
            key = procedure.implementation.id, procedure.implementation.version, phase
            if key not in {i.key for i in self.implementations}:
                raise MechanismError('unknown_implementation')
        if definition.policy and definition.policy.composition_rule:
            rule = definition.policy.composition_rule
            if (rule.id, rule.version, 'composition') not in {i.key for i in self.implementations}:
                raise MechanismError('unknown_composition_rule')
        fixtures = {(f.fixture.id, f.fixture.version) for f in definition.fixtures}
        if not fixtures or not fixtures <= self.fixture_ids:
            raise MechanismError('unresolved_fixtures')
        review = next((r for r in self.reviews if r.declaration_digest == declaration_digest(definition) and r.graph_digest == digest), None)
        if review is None or (review.model_id, review.model_version) != self.model:
            raise MechanismError('review_required')
        ownership = {o.key: o.writer_id for o in world.owners}
        for state in definition.owned_state:
            if ownership.get((entity_id, state.id, 'dynamic_state')) != definition.domain:
                raise MechanismError('foreign_state_owner')
        return definition  # detached inspection result, not a transferable capability

    def evaluate_graph(self, identity, version, *, phase, world, scope_id, entity_id, inputs):
        """Review-gated local arithmetic; outputs/state values do not commit effects."""
        definition = self.activate(identity, version, phase=phase, world=world,
                                   scope_id=scope_id, entity_id=entity_id)
        procedure = getattr(definition.support, phase)
        if procedure.kind != 'declarative_graph':
            raise MechanismError('not_a_graph')
        from .expressions import evaluate_graph
        return evaluate_graph(self._graph(procedure), definition, phase, self, world, inputs)

    def bind(self, producer, consumer, *, output_id, input_id, world,
             scope_id, producer_entity_id, consumer_entity_id):
        source = self.activate(*producer, phase='static', world=world, scope_id=scope_id, entity_id=producer_entity_id)
        target = self.activate(*consumer, phase='static', world=world, scope_id=scope_id, entity_id=consumer_entity_id)
        output = next((p for p in source.outputs if p.id == output_id), None)
        input_port = next((p for p in target.inputs if p.id == input_id), None)
        if output is None or input_port is None or output.value_type != input_port.value_type:
            raise MechanismError('incompatible_port')
        # Exact types only: conversions require an explicit future adapter.
        return output.value_type.model_copy(deep=True)

    def stage_changes(self, identity, version, *, world, scope_id, entity_id, changes):
        definition = self.activate(identity, version, phase='transition', world=world,
                                   scope_id=scope_id, entity_id=entity_id)
        states = {s.id: s for s in definition.owned_state}
        changes = tuple(PartitionValueDTO.model_validate_json(c.model_dump_json()) for c in changes)
        for change in changes:
            if (change.entity_id != entity_id or change.scope_id != scope_id or
                    change.partition != 'dynamic_state' or change.property_id not in definition.write_state_refs):
                raise MechanismError('undeclared_state_write')
            self.validate_value(states[change.property_id].value_type, change.value, world)
        return world.with_values(writer_id=definition.domain, partition='dynamic_state', changes=changes)

    def validate_value(self, value_type, value, world):
        """Known typed values only. Unknown is handled by future evaluation coverage."""
        self._type(value_type, world)
        if value_type.kind != value.kind:
            raise MechanismError('incompatible_value')
        if isinstance(value, QuantityValue):
            parse(value.value)
            if any(getattr(value_type, f) != getattr(value, f) for f in
                   ('unit_id', 'time_basis_id', 'denominator_scope_id')):
                raise MechanismError('incompatible_value')
        if isinstance(value, ReferenceValue) and world.entity(value.entity_id).entity_kind != value_type.entity_kind:
            raise MechanismError('incompatible_reference')
