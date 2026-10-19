"""Versioned host-authored observations and data-only accepted evidence closure."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .world import WorldValue, QuantityValue, EffectiveTime, References
from .evidence import CoverageStatus, SourceRef, AssumptionRef
from .solvers import NodeKey
from .evaluation import EvaluationResult, NodeObservation, Digest

Text = Annotated[str, Field(min_length=1, max_length=4096)]


class MeasurementInput(Contract):
    node: NodeKey
    scope_id: Identifier


class DiagnosticRule(Contract):
    id: Identifier
    version: Identifier
    name: Text
    operation: Literal['lt', 'le', 'eq', 'ne', 'ge', 'gt']
    threshold: QuantityValue
    category: Literal['physical_shortage', 'selected_policy_breach', 'institutional_gap', 'uncertainty']
    interpretation: Text
    source_refs: References
    assumption_refs: References


class IndicatorDefinition(Contract):
    id: Identifier
    version: Identifier
    name: Text
    procedure: Literal['identity', 'sum', 'mean', 'minimum', 'maximum', 'difference', 'ratio']
    inputs: Annotated[list[MeasurementInput], Field(min_length=1, max_length=100)]
    unit_id: Identifier
    scope_id: Identifier
    aggregation: Literal['same_scope']
    time_basis_id: Identifier | None
    denominator_scope_id: Identifier | None
    coverage: CoverageStatus
    interpretation: Text
    source_refs: References
    assumption_refs: References
    diagnostics: Annotated[list[DiagnosticRule], Field(max_length=100)]


class PlayerGoal(Contract):
    id: Identifier
    kind: Literal['narrative', 'comparison']
    question: Text
    indicator_id: Identifier | None
    operation: Literal['lt', 'le', 'eq', 'ne', 'ge', 'gt'] | None
    threshold: QuantityValue | None


class MeasurementObservation(Contract):
    indicator_id: Identifier
    definition_version: Identifier
    scope_id: Identifier
    effective_time: EffectiveTime
    status: CoverageStatus
    reason: Text
    value: WorldValue
    diagnostic: Literal['neutral', 'within_named_thresholds', 'flagged', 'unavailable']
    trace_refs: Annotated[list[Identifier], Field(max_length=100)]
    source_refs: References
    assumption_refs: References


class GoalObservation(Contract):
    goal_id: Identifier
    status: Literal['observed', 'unavailable', 'narrative']
    matched: bool | None
    indicator_id: Identifier | None
    reason: Text


class ObservationFinding(Contract):
    id: Identifier
    category: Literal['physical_shortage', 'selected_policy_breach', 'institutional_gap', 'uncertainty', 'player_target_observation']
    scope_id: Identifier | None
    effective_time: EffectiveTime
    status: CoverageStatus
    template_id: Identifier
    rule_ref: Identifier | None
    indicator_id: Identifier | None
    trace_refs: Annotated[list[Identifier], Field(max_length=100)]
    source_refs: References
    assumption_refs: References
    # Structured data only; no generated prose or embedded private source text.
    values: Annotated[list[WorldValue], Field(max_length=100)]


class MechanismRef(Contract):
    instance_id: Identifier
    mechanism_id: Identifier
    mechanism_version: Identifier
    scope_id: Identifier
    entity_id: Identifier


class CalculationTrace(Contract):
    id: Identifier
    kind: Literal['node', 'solved_component']
    members: Annotated[list[NodeObservation], Field(min_length=1, max_length=25000)]
    mechanisms: Annotated[list[MechanismRef], Field(max_length=100)]
    effective_time: EffectiveTime
    dependency_refs: Annotated[list[Identifier], Field(max_length=25000)]
    # Internal SCC edges are preserved instead of silently dropping feedback.
    internal_edges: Annotated[list[tuple[NodeKey, NodeKey]], Field(max_length=50000)]


class MeasurementReport(Contract):
    measurement_schema: Literal[1]
    physical_output_digest: Digest
    report_digest: Digest
    definitions: Annotated[list[IndicatorDefinition], Field(max_length=1000)]
    goal_definitions: Annotated[list[PlayerGoal], Field(max_length=1000)]
    measurements: Annotated[list[MeasurementObservation], Field(max_length=1000)]
    goals: Annotated[list[GoalObservation], Field(max_length=1000)]
    findings: Annotated[list[ObservationFinding], Field(max_length=10000)]
    traces: Annotated[list[CalculationTrace], Field(max_length=40000)]
    coverage: CoverageStatus
    # A qualified model never implies whole-system sufficiency.
    sufficient: bool | None


class EvidenceReference(Contract):
    id: Identifier
    kind: Literal['source', 'assumption']
    visibility: Literal['public', 'private']
    availability: Literal['available', 'unavailable', 'redacted']
    description: Text | None
    source: SourceRef | None = None
    assumption: AssumptionRef | None = None

    @model_validator(mode='after')
    def descriptor(self):
        record = self.source if self.kind == 'source' else self.assumption
        other = self.assumption if self.kind == 'source' else self.source
        if other is not None or record is not None and record.id != self.id:
            raise ValueError('evidence_descriptor_mismatch')
        if self.availability == 'available' and record is None:
            raise ValueError('available_evidence_requires_descriptor')
        return self


class AcceptedEvidence(Contract):
    evidence_version: Literal[1]
    state: Literal['complete', 'unavailable']
    evaluation: EvaluationResult | None
    report: MeasurementReport | None
    references: Annotated[list[EvidenceReference], Field(max_length=10000)]
    closure_digest: Digest


class TraceQuery(Contract):
    report_digest: Digest
    root_id: Identifier | None
    cursor: Identifier | None
    limit: Annotated[int, Field(ge=1, le=100)]


class CalculationTracePage(Contract):
    report_digest: Digest
    items: Annotated[list[CalculationTrace], Field(max_length=100)]
    next_cursor: Identifier | None


class PublicObservationReport(Contract):
    measurement_schema: Literal[1]
    physical_output_digest: Digest
    definitions: Annotated[list[IndicatorDefinition], Field(max_length=1000)]
    measurements: Annotated[list[MeasurementObservation], Field(max_length=1000)]
    findings: Annotated[list[ObservationFinding], Field(max_length=10000)]
    traces: Annotated[list[CalculationTrace], Field(max_length=40000)]
    coverage: CoverageStatus
    sufficient: bool | None


class PublicEvidenceProjection(Contract):
    projection_version: Literal[1]
    state: Literal['unavailable', 'projected']
    report: PublicObservationReport | None
    references: Annotated[list[EvidenceReference], Field(max_length=10000)]
    omitted_references: Annotated[int, Field(ge=0, le=10000)]
    goals_included: Literal[False]
    input_snapshots_included: Literal[False]
    projection_digest: Digest
