"""Declared accommodation prerequisites; no assessment of inner experience."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, DecimalString, ScopeKind
from .packs import Definition, Digest
from .accounts import AccountBatch
from .allocations import AllocationEvaluation


class ParticipationFacility(Contract):
    asset_id: Identifier
    institution_id: Identifier
    ownership_relationship_id: Identifier
    account_id: Identifier
    availability: Literal['operating', 'offline', 'unknown']
    source_refs: References


class ParticipationDemand(Contract):
    claim_id: Identifier
    group_id: Identifier
    facility_asset_id: Identifier
    access_relationship_id: Identifier | None
    commitment_ref: Identifier
    accommodation_ref: Identifier
    participation: Literal['requested', 'declined', 'unknown']
    eligibility: Literal['eligible', 'ineligible', 'unknown']
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    obligation_status: Literal['compatible', 'conflict', 'unknown']
    obligation_refs: References
    source_refs: References


class ParticipationRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    facilities: Annotated[list[ParticipationFacility], Field(min_length=1, max_length=100)]
    demands: Annotated[list[ParticipationDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class ParticipationReadiness(Contract):
    claim_id: Identifier
    outcome: Literal['capacity_ready', 'blocked', 'unresolved']
    findings: Annotated[list[str], Field(max_length=20)]
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class ParticipationEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ParticipationRequest
    allocation: AllocationEvaluation
    results: Annotated[list[ParticipationReadiness], Field(min_length=1, max_length=1000)]


class ParticipationAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class ParticipationInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[ParticipationAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class ParticipationEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class ParticipationReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['participation-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: ParticipationEvaluation


class ParticipationPreview(Contract):
    contract_version: Literal[1]
    edit: ParticipationEdit
    candidate_digest: Digest
    report: ParticipationReport


class ParticipationCoverageEntry(Contract):
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


class ParticipationCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[ParticipationCoverageEntry], Field(min_length=1, max_length=100)]
