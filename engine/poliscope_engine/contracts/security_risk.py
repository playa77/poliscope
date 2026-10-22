"""Declared finite continuity slots; no hazard or damage prediction."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, DecimalString, ScopeKind
from .packs import Definition, Digest
from .accounts import AccountBatch
from .allocations import AllocationEvaluation


class ContinuityFacility(Contract):
    asset_id: Identifier
    institution_id: Identifier
    ownership_relationship_id: Identifier
    account_id: Identifier
    origin: Literal['local', 'external']
    availability: Literal['operating', 'offline', 'unknown']
    source_refs: References


class ContinuityDemand(Contract):
    claim_id: Identifier
    group_id: Identifier
    facility_asset_id: Identifier
    access_relationship_id: Identifier | None
    purpose: Literal['ordinary', 'preparedness', 'response', 'external_aid']
    hazard_ref: Identifier
    exposure_refs: References
    vulnerability: Literal['declared', 'unknown']
    authority: Literal['authorized', 'delayed', 'denied', 'unknown']
    disclosure: Literal['satisfied', 'withheld', 'unknown']
    aid_condition: Literal['satisfied', 'unavailable', 'unknown']
    participation: Literal['requested', 'declined', 'unknown']
    eligibility: Literal['eligible', 'ineligible', 'unknown']
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    obligation_status: Literal['compatible', 'conflict', 'unknown']
    obligation_refs: References
    source_refs: References


class ContinuityRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    facilities: Annotated[list[ContinuityFacility], Field(min_length=1, max_length=100)]
    demands: Annotated[list[ContinuityDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class ContinuityReadiness(Contract):
    claim_id: Identifier
    outcome: Literal['capacity_ready', 'blocked', 'unresolved']
    findings: Annotated[list[str], Field(max_length=20)]
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class ContinuityEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ContinuityRequest
    allocation: AllocationEvaluation
    results: Annotated[list[ContinuityReadiness], Field(min_length=1, max_length=1000)]


class ContinuityAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class ContinuityInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[ContinuityAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class ContinuityEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class ContinuityReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['continuity-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: ContinuityEvaluation


class ContinuityPreview(Contract):
    contract_version: Literal[1]
    edit: ContinuityEdit
    candidate_digest: Digest
    report: ContinuityReport


class ContinuityCoverageEntry(Contract):
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


class ContinuityCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[ContinuityCoverageEntry], Field(min_length=1, max_length=100)]
