"""Canonical topology projections and constrained revision edits."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import (RevisionContext, WorldVersions, EffectiveTime, EntityDTO,
    RelationshipDTO, ScopeDTO, PartitionValueDTO, WorldValue)
from .overview import OverviewQuery
from .interview import InterviewApply, InterviewCommit
from .evaluation import Digest

class ExplorationQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    projection: Literal['geography', 'membership', 'authority', 'networks', 'all'] = 'all'
    identity: Identifier | None = None
    cursor: Identifier | None = None

class ExplorationRow(Contract):
    id: Identifier
    entity: EntityDTO | None
    scope: ScopeDTO | None
    relationship: RelationshipDTO | None
    value: PartitionValueDTO | None
    inspector: OverviewQuery | None

class ExplorationPage(Contract):
    exploration_contract: Literal[1]
    query: ExplorationQuery
    versions: WorldVersions
    effective_time: EffectiveTime
    items: Annotated[list[ExplorationRow], Field(max_length=25)]
    total: Annotated[int, Field(ge=0)]
    next_cursor: Identifier | None

class EntityEdit(Contract):
    kind: Literal['entity']
    entity: EntityDTO
    population_role: Literal['fixed_input', 'dynamic_state', 'solved_capacity_bound'] | None = None

class RelationshipEdit(Contract):
    kind: Literal['relationship']
    relationship: RelationshipDTO
    terms: Annotated[str, Field(max_length=4096)] | None = None

class ValueEdit(Contract):
    kind: Literal['value']
    value_id: Identifier
    value: WorldValue

class ExplorationEdit(Contract):
    context: RevisionContext
    scope_id: Identifier
    change: Annotated[EntityEdit | RelationshipEdit | ValueEdit, Field(discriminator='kind')]

class ExplorationPreview(Contract):
    exploration_contract: Literal[1]
    edit: ExplorationEdit
    candidate_digest: Digest
    before: Annotated[str, Field(max_length=16384)]
    after: Annotated[str, Field(max_length=16384)]
    coverage: Annotated[str, Field(max_length=4096)]

exploration_adapter = TypeAdapter(ExplorationQuery | ExplorationPage | ExplorationEdit | ExplorationPreview | InterviewApply | InterviewCommit)
