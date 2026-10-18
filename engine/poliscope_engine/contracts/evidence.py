"""Bounded evaluation evidence projections; no evaluation or source execution."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import (RevisionContext, WorldVersions, EffectiveTime, References,
                    WorldValue, UnknownValue, QuantityValue, LabelValue, ReferenceValue, Page)

Text = Annotated[str, Field(min_length=1, max_length=4096)]
CoverageStatus = Literal['known', 'partial', 'missing_input', 'unmodeled', 'conflict', 'solver_failure', 'not_applicable']
EvidenceCollection = Literal['outputs', 'findings', 'sources', 'assumptions', 'traces']


class Coverage(Contract):
    status: CoverageStatus
    explanation: Text
    covered_scope_refs: References
    excluded_scope_refs: References
    missing_input_refs: References


class EvidenceLinks(Contract):
    source_refs: References
    assumption_refs: References
    trace_refs: References


class SourceRef(Contract):
    id: Identifier
    repository_id: Identifier
    document_id: Identifier
    revision_id: Identifier
    location: Text
    excerpt_digest: Annotated[str, Field(pattern=r'^sha256:[0-9a-f]{64}$')]
    license_id: Identifier
    historical_status: Literal['current', 'amended', 'superseded', 'disputed', 'unknown']
    supersedes_refs: References


class AssumptionRef(Contract):
    id: Identifier
    scope_id: Identifier
    definition_id: Identifier
    definition_version: Identifier
    origin: Literal['authored', 'imported', 'player_input', 'ai_proposed', 'derived']
    uncertainty_form: Literal['point', 'bounded_range', 'distribution', 'qualitative', 'unspecified']
    uncertainty_definition_ref: Identifier | None
    rationale: Text
    source_refs: References


class Finding(Contract):
    id: Identifier
    category: Literal['physical_shortage', 'selected_policy_breach', 'institutional_gap', 'uncertainty', 'player_target_observation']
    scope_id: Identifier
    effective_time: EffectiveTime
    message: Text
    rule_ref: Identifier | None
    affected_refs: References
    coverage: Coverage
    evidence: EvidenceLinks


class KnownObservation(Contract):
    status: Literal['known']
    value: Annotated[QuantityValue | LabelValue | ReferenceValue, Field(discriminator='kind')]


class PartialObservation(Contract):
    status: Literal['partial']
    value: WorldValue


class UnavailableObservation(Contract):
    status: Literal['missing_input', 'unmodeled', 'conflict', 'solver_failure', 'not_applicable']
    value: UnknownValue


class EvaluationOutput(Contract):
    id: Identifier
    indicator_id: Identifier
    scope_id: Identifier
    effective_time: EffectiveTime
    observation: Annotated[KnownObservation | PartialObservation | UnavailableObservation, Field(discriminator='status')]
    coverage: Coverage
    evidence: EvidenceLinks


class TracePort(Contract):
    port_id: Identifier
    value: WorldValue


class TraceNode(Contract):
    id: Identifier
    mechanism_id: Identifier
    mechanism_version: Identifier
    scope_id: Identifier
    effective_time: EffectiveTime
    inputs: Annotated[list[TracePort], Field(max_length=100)]
    outputs: Annotated[list[TracePort], Field(max_length=100)]
    child_refs: References
    evidence: EvidenceLinks


class EvaluationSummary(Contract):
    kind: Literal['evaluation']
    evidence_schema: Literal[1]
    context: RevisionContext
    versions: WorldVersions
    effective_time: EffectiveTime
    result_id: Identifier
    scope_id: Identifier
    outcome: Literal['complete', 'incomplete', 'infeasible', 'unresolved']
    coverage: Coverage
    finding_refs: References
    trace_refs: References


class EvidenceInspectParams(Contract):
    evidence_schema: Literal[1]
    context: RevisionContext
    result_id: Identifier
    collection: EvidenceCollection
    cursor: Identifier | None
    limit: Annotated[int, Field(ge=1, le=100)]


class OutputPage(Page):
    kind: Literal['outputs']
    items: Annotated[list[EvaluationOutput], Field(max_length=100)]


class FindingPage(Page):
    kind: Literal['findings']
    items: Annotated[list[Finding], Field(max_length=100)]


class SourcePage(Page):
    kind: Literal['sources']
    items: Annotated[list[SourceRef], Field(max_length=100)]


class AssumptionPage(Page):
    kind: Literal['assumptions']
    items: Annotated[list[AssumptionRef], Field(max_length=100)]


class TracePage(Page):
    kind: Literal['traces']
    items: Annotated[list[TraceNode], Field(max_length=100)]


class EvidencePageResult(Contract):
    kind: Literal['evidence_page']
    evidence_schema: Literal[1]
    context: RevisionContext
    versions: WorldVersions
    effective_time: EffectiveTime
    result_id: Identifier
    scope_id: Identifier
    page: Annotated[OutputPage | FindingPage | SourcePage | AssumptionPage | TracePage, Field(discriminator='kind')]
