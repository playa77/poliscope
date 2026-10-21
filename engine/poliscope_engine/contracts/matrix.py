"""Bounded read-only sparse relationships; counts never imply effect strength."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, WorldVersions, EffectiveTime, WorldValue
from .evidence import CoverageStatus
from .interview import InterviewQuery
from .atlas import AtlasSourceQuery
from .overview import OverviewQuery
from .packs import Digest
from .mechanisms import MechanismDefinition
from .policies import ResolutionRule
from .solvers import FinitePlan
from .evaluation import ConditionRule

RelationshipType = Literal['requires', 'supplies', 'competes', 'conflicts', 'influences', 'supersedes']
Axis = Literal['domain', 'branch', 'decision', 'scope', 'selected_alternative']

class MatrixQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    axis: Axis = 'domain'
    relationship_type: RelationshipType | None = None
    provenance: Literal['any', 'documentary', 'model', 'retained_execution'] = 'any'
    row_id: Identifier | None = None
    column_id: Identifier | None = None
    cursor: Identifier | None = None
    detail_cursor: Identifier | None = None

class MatrixEndpoint(Contract):
    id: Identifier
    label: Annotated[str, Field(min_length=1, max_length=256)]
    # Empty tags mean unresolved mapping, never inferred membership.
    domains: Annotated[list[Identifier], Field(max_length=12)]
    branches: Annotated[list[Identifier], Field(max_length=200)]
    decisions: Annotated[list[Identifier], Field(max_length=100)]
    alternatives: Annotated[list[Identifier], Field(max_length=100)]
    scopes: Annotated[list[Identifier], Field(max_length=1000)]

class MatrixRelationship(Contract):
    id: Identifier
    relationship_type: RelationshipType
    row: MatrixEndpoint
    column: MatrixEndpoint
    provenance: Literal['documentary', 'model', 'retained_execution']
    activation: Literal['documentary', 'declared', 'observed', 'unavailable']
    coverage: CoverageStatus
    magnitude: WorldValue | None
    explanation: Annotated[str, Field(min_length=1, max_length=4096)]
    world_refs: Annotated[list[Identifier], Field(max_length=2)] = []
    mechanism_refs: Annotated[list[Identifier], Field(max_length=100)]
    rule_refs: Annotated[list[Identifier], Field(max_length=100)]
    interviews: Annotated[list[InterviewQuery], Field(max_length=100)]
    sources: Annotated[list[AtlasSourceQuery], Field(max_length=100)]
    inspectors: Annotated[list[OverviewQuery], Field(max_length=100)]

class MatrixCell(Contract):
    row_id: Identifier
    column_id: Identifier
    relationship_type: RelationshipType
    provenance: Literal['documentary', 'model', 'retained_execution']
    activation: Literal['documentary', 'declared', 'observed', 'unavailable']
    coverage: CoverageStatus
    count: Annotated[int, Field(ge=1)]

class MatrixPage(Contract):
    matrix_contract: Literal[1]
    query: MatrixQuery
    versions: WorldVersions
    effective_time: EffectiveTime
    catalog_digest: Digest
    evidence_digest: Digest
    evidence_state: Literal['complete', 'unavailable']
    # Aggregate cells and detailed edges have independent bounded pages.
    cells: Annotated[list[MatrixCell], Field(max_length=25)]
    relationships: Annotated[list[MatrixRelationship], Field(max_length=10)]
    cell_total: Annotated[int, Field(ge=0)]
    relationship_total: Annotated[int, Field(ge=0)]
    next_cursor: Identifier | None
    detail_next_cursor: Identifier | None
    unmapped_count: Annotated[int, Field(ge=0)]


class MatrixModelQuery(Contract):
    context: RevisionContext
    kind: Literal['mechanism', 'rule']
    identity: Identifier

class MatrixModelReply(Contract):
    matrix_contract: Literal[1]
    query: MatrixModelQuery
    status: Literal['retained', 'unavailable']
    mechanism: MechanismDefinition | None
    policy_rule: ResolutionRule | None
    allocation_rule: FinitePlan | None
    condition_rule: ConditionRule | None

matrix_adapter = TypeAdapter(MatrixQuery | MatrixPage | MatrixModelQuery | MatrixModelReply)
