"""Revision-bound, paginated world projections, not a persistence or solver model.

Reference existence, graph invariants, unit compatibility and mechanism semantics
are checked by their owning services. Decimal strings remain untouched here.
"""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier

SafeCount = Annotated[int, Field(ge=0, le=9007199254740991)]
DecimalString = Annotated[str, Field(
    min_length=1, max_length=256,
    pattern=r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$',
)]
References = Annotated[list[Identifier], Field(max_length=100)]
Partition = Literal['conditions', 'design', 'assumptions', 'dynamic_state', 'observations', 'goals']
ScopeKind = Literal['household', 'community', 'settlement', 'region', 'civilization', 'global_external']
EntityKind = Literal[
    'civilization', 'location', 'population_cohort', 'household_arrangement',
    'community_arrangement', 'institution', 'asset', 'network', 'resource',
    'service', 'account', 'external_interface', 'decision', 'event',
]
RelationshipKind = Literal[
    'containment', 'geographic_overlap', 'cohort_membership', 'jurisdiction',
    'ownership', 'obligation', 'supplies', 'consumes', 'access', 'connectivity',
    'information_channel', 'source_supersession',
]
WorldCollection = Literal['scopes', 'entities', 'relationships', 'values', 'mechanisms']


class WorldVersions(Contract):
    world_schema: Literal[1]
    catalog_id: Identifier
    model_id: Identifier
    numeric_runtime_id: Identifier


class RevisionContext(Contract):
    data_store_id: Identifier
    civilization_id: Identifier
    branch_id: Identifier
    revision_id: Identifier


class EffectiveTime(Contract):
    """Simulation time; no wall-clock timestamp participates in this identity."""
    tick: SafeCount
    calendar_id: Identifier


class WorldProvenance(Contract):
    origin: Literal['authored', 'imported', 'player_input', 'ai_proposed', 'derived']
    source_refs: References
    assumption_refs: References


class QuantityValue(Contract):
    kind: Literal['quantity']
    value: DecimalString
    unit_id: Identifier
    time_basis_id: Identifier | None
    denominator_scope_id: Identifier | None


class UnknownValue(Contract):
    kind: Literal['unknown']
    reason: Annotated[str, Field(min_length=1, max_length=1024)]


class LabelValue(Contract):
    kind: Literal['label']
    value: Annotated[str, Field(max_length=131072)]


class ReferenceValue(Contract):
    kind: Literal['reference']
    entity_id: Identifier


WorldValue = Annotated[QuantityValue | UnknownValue | LabelValue | ReferenceValue, Field(discriminator='kind')]


class ScopeDTO(Contract):
    id: Identifier
    scope_kind: ScopeKind
    label: Annotated[str, Field(min_length=1, max_length=256)]
    provenance: WorldProvenance


class EntityDTO(Contract):
    id: Identifier
    entity_kind: EntityKind
    label: Annotated[str, Field(min_length=1, max_length=256)]
    provenance: WorldProvenance


class MembershipWeight(Contract):
    """Explicit weight or partition; never implicit equal or duplicate membership."""
    kind: Literal['weight']
    weight: DecimalString


class MembershipPartition(Contract):
    kind: Literal['partition']
    partition_id: Identifier


class NonAggregating(Contract):
    kind: Literal['non_aggregating']


class RelationshipDTO(Contract):
    id: Identifier
    relationship_version: Identifier
    relationship_kind: RelationshipKind
    from_id: Identifier
    to_id: Identifier
    aggregation: Annotated[MembershipWeight | MembershipPartition | NonAggregating, Field(discriminator='kind')]
    provenance: WorldProvenance


class PartitionValueDTO(Contract):
    id: Identifier
    entity_id: Identifier
    scope_id: Identifier
    partition: Partition
    property_id: Identifier
    value: WorldValue
    effective_time: EffectiveTime
    provenance: WorldProvenance


class ParameterAssignment(Contract):
    parameter_id: Identifier
    value: WorldValue


class MechanismBindingDTO(Contract):
    instance_id: Identifier
    mechanism_id: Identifier
    mechanism_version: Identifier
    scope_id: Identifier
    inheritance: Literal['exclusive', 'composable', 'floor', 'ceiling', 'delegated']
    modeling_status: Literal['numerical', 'procedural', 'qualitative', 'partial', 'unsupported']
    parameters: Annotated[list[ParameterAssignment], Field(max_length=100)]
    provenance: WorldProvenance


class WorldInspectParams(Contract):
    world_schema: Literal[1]
    context: RevisionContext
    collection: WorldCollection
    cursor: Identifier | None
    limit: Annotated[int, Field(ge=1, le=100)]


class Page(Contract):
    next_cursor: Identifier | None


class ScopePage(Page):
    kind: Literal['scopes']
    items: Annotated[list[ScopeDTO], Field(max_length=100)]


class EntityPage(Page):
    kind: Literal['entities']
    items: Annotated[list[EntityDTO], Field(max_length=100)]


class RelationshipPage(Page):
    kind: Literal['relationships']
    items: Annotated[list[RelationshipDTO], Field(max_length=100)]


class ValuePage(Page):
    kind: Literal['values']
    items: Annotated[list[PartitionValueDTO], Field(max_length=100)]


class MechanismPage(Page):
    kind: Literal['mechanisms']
    items: Annotated[list[MechanismBindingDTO], Field(max_length=100)]


class WorldPageResult(Contract):
    kind: Literal['world_page']
    context: RevisionContext
    versions: WorldVersions
    effective_time: EffectiveTime
    page: Annotated[ScopePage | EntityPage | RelationshipPage | ValuePage | MechanismPage, Field(discriminator='kind')]
