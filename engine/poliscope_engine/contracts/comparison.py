"""Bounded history and reusable retained-result comparisons; schema 1."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, WorldValue, WorldVersions
from .revisions import BranchState, PrivateReference
from .workspace import WorkspaceState
from .measurements import IndicatorDefinition, MeasurementObservation

class LineageQuery(Contract):
    context: RevisionContext
    cursor: Identifier | None

class ChoiceSummary(Contract):
    id: Identifier
    wording: Annotated[list[str], Field(max_length=1000)]

class LineageRow(Contract):
    context: RevisionContext
    parent_id: Identifier | None
    selected_id: Identifier | None
    alternatives: Annotated[list[ChoiceSummary], Field(max_length=100)]
    rationale: PrivateReference | None

class LineagePage(Contract):
    comparison_contract: Literal[1]
    query: LineageQuery
    can_undo: bool
    branch: BranchState
    items: Annotated[list[LineageRow], Field(max_length=10)]
    next_cursor: Identifier | None

class HistoryAction(Contract):
    context: RevisionContext
    expected_sequence: Annotated[int, Field(ge=0, le=9007199254740991)]
    action: Literal['undo', 'redo', 'fork', 'rename', 'restore']
    target_revision_id: Identifier | None
    name: Annotated[str, Field(min_length=1, max_length=256)] | None

class CompareQuery(Contract):
    context: RevisionContext
    other: RevisionContext
    cursor: Identifier | None

class ComparisonValue(Contract):
    origin: Literal['retained_evidence', 'unavailable']
    definition: IndicatorDefinition | None
    observation: MeasurementObservation | None
    trace_state: Literal['complete', 'incomplete', 'unavailable']

class ComparisonRow(Contract):
    id: Identifier
    left: ComparisonValue
    right: ComparisonValue
    delta: WorldValue | None
    reasons: Annotated[list[str], Field(max_length=30)]

class DesignDifference(Contract):
    kind: Literal['value', 'assumption', 'policy', 'goal', 'reference']
    id: Identifier
    before: str | None
    after: str | None

class ComparePage(Contract):
    comparison_contract: Literal[1]
    query: CompareQuery
    left_evidence: Literal['complete', 'unavailable']
    right_evidence: Literal['complete', 'unavailable']
    left_versions: WorldVersions
    right_versions: WorldVersions
    items: Annotated[list[ComparisonRow], Field(max_length=10)]
    changes: Annotated[list[DesignDifference], Field(max_length=10)]
    next_cursor: Identifier | None

class RationaleQuery(Contract):
    context: RevisionContext

class RationaleReply(Contract):
    comparison_contract: Literal[1]
    query: RationaleQuery
    classification: Literal['private']
    reference: PrivateReference | None
    text: Annotated[str, Field(max_length=2048)] | None

comparison_adapter = TypeAdapter(RationaleQuery | RationaleReply | LineageQuery | LineagePage | HistoryAction | CompareQuery | ComparePage | WorkspaceState)
