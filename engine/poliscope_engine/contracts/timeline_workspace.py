"""Bounded timeline presentation and named player commands."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, SafeCount
from .boundaries import BoundaryOutcome
from .experiments import ExperimentControl
from .comparison import ComparisonRow
from .stochastic import DrawSpec, RealizedDraw, Seed


class TimelineRequest(Contract):
    context: RevisionContext
    action: Literal['read', 'create', 'advance', 'pause', 'resume', 'cancel', 'fork', 'schedule', 'preview_schedule']
    experiment_id: Identifier
    operation_id: Identifier
    sequence: SafeCount = 0
    target_day: SafeCount = 0
    other_id: Identifier | None = None
    source_revision_id: Identifier | None = None
    expected: BoundaryOutcome | None = None
    control: ExperimentControl | None = None
    after: SafeCount | None = None
    indicator_id: Identifier | None = None
    trace_offset: SafeCount = 0
    realization_policy: Literal['preserve', 'new_realization'] = 'preserve'
    seed: Seed | None = None


class TimelineEntry(Contract):
    sequence: SafeCount
    day: SafeCount
    digest: Identifier
    coverage: str
    consequences: Annotated[list[str], Field(max_length=3000)]
    trace_count: SafeCount
    traces: Annotated[list[str], Field(max_length=100)]
    draws: Annotated[list[RealizedDraw], Field(max_length=1000)]
    values: Annotated[list[ComparisonRow], Field(max_length=10)]


class TimelineReply(Contract):
    query: TimelineRequest
    experiments: Annotated[list[Identifier], Field(max_length=100)]
    head: BoundaryOutcome | None
    checkpoint: BoundaryOutcome | None
    opening: BoundaryOutcome | None
    origin: BoundaryOutcome | None
    control: ExperimentControl | None
    entries: Annotated[list[TimelineEntry], Field(max_length=10)]
    next_after: SafeCount | None
    schedule: Annotated[list[str], Field(max_length=3000)]
    assumptions: Annotated[list[str], Field(max_length=1001)]
    differences: Annotated[list[str], Field(max_length=1000)]
    indicators: Annotated[list[Identifier], Field(max_length=1000)]
    distributions: Annotated[list[DrawSpec], Field(max_length=1000)]
    comparisons: Annotated[list[ComparisonRow], Field(max_length=10)]
    notice: str


timeline_workspace_adapter = TypeAdapter(TimelineRequest | TimelineReply)
