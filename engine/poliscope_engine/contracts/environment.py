"""Host-only finite ecological boundary prerequisites; no ecological effects."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString, References, ScopeKind
from .packs import Definition, Digest
from .accounts import AccountBatch
from .allocations import AllocationEvaluation


class EcologicalBoundary(Contract):
    resource_id: Identifier
    role: Literal['extraction_stock', 'sink_allowance']
    account_id: Identifier
    capacity_status: Literal['known', 'unknown']
    # Limit is a diagnostic on gross outward postings in the retained batch.
    # A reference without a value means an unknown selected limit.
    selected_limit: DecimalString | None
    policy_ref: Identifier | None
    source_refs: References


class EnvironmentalDemand(Contract):
    claim_id: Identifier
    scope_id: Identifier
    scope_relationship_id: Identifier
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    source_refs: References


class EnvironmentRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    boundaries: Annotated[list[EcologicalBoundary], Field(min_length=1, max_length=100)]
    demands: Annotated[list[EnvironmentalDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class EnvironmentalReadiness(Contract):
    claim_id: Identifier
    outcome: Literal['capacity_ready', 'blocked', 'unresolved']
    findings: Annotated[list[str], Field(max_length=10)]
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class EcologicalBoundaryResult(Contract):
    account_id: Identifier
    gross_debit: DecimalString
    limit_status: Literal['not_selected', 'unknown', 'within_limit', 'limit_breached']
    # On unresolved allocation this describes retained postings only.
    candidate_complete: bool


class EnvironmentEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: EnvironmentRequest
    allocation: AllocationEvaluation
    results: Annotated[list[EnvironmentalReadiness], Field(min_length=1, max_length=1000)]
    boundaries: Annotated[list[EcologicalBoundaryResult], Field(min_length=1, max_length=100)]


class EnvironmentAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class EnvironmentInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[EnvironmentAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class EnvironmentEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class EnvironmentReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['environment-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: EnvironmentEvaluation


class EnvironmentPreview(Contract):
    contract_version: Literal[1]
    edit: EnvironmentEdit
    candidate_digest: Digest
    report: EnvironmentReport


class EnvironmentCoverageEntry(Contract):
    source_id: Identifier
    classification: Literal['catalog', 'provenance']
    title: Annotated[str, Field(min_length=1, max_length=2048)]
    documents: Annotated[list[Identifier], Field(max_length=100)]
    option_refs: Annotated[list[Identifier], Field(max_length=100)]
    effect: Annotated[str, Field(min_length=1, max_length=2048)]
    status: Literal['partial', 'qualitative', 'unsupported']
    evidence_status: Literal['hypothetical', 'unreviewed']
    supported_scope_kinds: Annotated[list[ScopeKind], Field(max_length=6)]
    static_available: bool
    transition_available: Literal[False]
    implementation_refs: Annotated[list[Identifier], Field(max_length=10)]
    next_research_task: Annotated[str, Field(min_length=1, max_length=2048)]


class EnvironmentCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[EnvironmentCoverageEntry], Field(min_length=1, max_length=100)]
