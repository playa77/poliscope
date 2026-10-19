"""Read-only, bounded projections of revision-owned observations and evidence."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, WorldVersions, EffectiveTime, PartitionValueDTO, WorldValue, QuantityValue
from .evidence import CoverageStatus
from .measurements import (IndicatorDefinition, MeasurementObservation, ObservationFinding,
    CalculationTrace, EvidenceReference, PlayerGoal, GoalObservation)
from .accounts import AccountDefinition, AccountResult
from .policies import PolicyBinding
from .evaluation import Digest

Collection = Literal['indicators', 'conditions', 'accounts', 'findings', 'policies', 'goals', 'references', 'traces']

class OverviewQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    collection: Collection
    # None means all items; trace IDs select a transitive dependency graph.
    item_id: Identifier | None
    cursor: Identifier | None
    all_scopes: bool

class IndicatorRow(Contract):
    kind: Literal['indicator']
    id: Identifier
    definition: IndicatorDefinition
    observation: MeasurementObservation
    tone: Literal['green', 'orange', 'red', 'gray', 'neutral']

class ConditionRow(Contract):
    kind: Literal['condition']
    id: Identifier
    condition: PartitionValueDTO
    writer_id: Identifier | None

class AccountRow(Contract):
    kind: Literal['account']
    id: Identifier
    definition: AccountDefinition
    result: AccountResult
    trace_refs: Annotated[list[Identifier], Field(max_length=100)]

class FindingRow(Contract):
    kind: Literal['finding']
    id: Identifier
    finding: ObservationFinding
    message: Annotated[str, Field(min_length=1, max_length=4096)]

class PolicyRow(Contract):
    kind: Literal['policy']
    id: Identifier
    policy: PolicyBinding

class CommitmentRow(Contract):
    kind: Literal['commitment']
    id: Identifier
    label: Annotated[str, Field(min_length=1, max_length=256)]
    condition: PartitionValueDTO

class GoalRow(Contract):
    kind: Literal['goal']
    id: Identifier
    definition: PlayerGoal
    observation: GoalObservation

class ReferenceRow(Contract):
    kind: Literal['reference']
    id: Identifier
    reference: EvidenceReference

class TraceRow(Contract):
    kind: Literal['trace']
    id: Identifier
    trace: CalculationTrace

OverviewRow = Annotated[IndicatorRow | ConditionRow | AccountRow | FindingRow | PolicyRow | CommitmentRow | GoalRow | ReferenceRow | TraceRow, Field(discriminator='kind')]

class OverviewPage(Contract):
    overview_contract: Literal[1]
    query: OverviewQuery
    versions: WorldVersions
    effective_time: EffectiveTime
    evidence_state: Literal['complete', 'unavailable']
    report_digest: Digest | None
    physical_output_digest: Digest | None
    coverage: CoverageStatus
    # No whole-society sufficiency claim is inferred from this projection.
    items: Annotated[list[OverviewRow], Field(max_length=25)]
    next_cursor: Identifier | None

class TargetQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    indicator_id: Identifier
    operation: Literal['lt', 'le', 'eq', 'ne', 'ge', 'gt']
    threshold: QuantityValue

class TargetReply(Contract):
    overview_contract: Literal[1]
    query: TargetQuery
    report_digest: Digest
    physical_output_digest: Digest
    observation: GoalObservation

class ChartQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    indicator_id: Identifier

class ChartPoint(Contract):
    label: Identifier
    # Display-only binary approximation; exact values remain decimal strings.
    exact: str
    approximate: str | None

class ChartReply(Contract):
    overview_contract: Literal[1]
    query: ChartQuery
    unit_id: Identifier
    time_basis_id: Identifier | None
    points: Annotated[list[ChartPoint], Field(max_length=100)]

overview_adapter = TypeAdapter(OverviewQuery | OverviewPage | TargetQuery | TargetReply | ChartQuery | ChartReply)
