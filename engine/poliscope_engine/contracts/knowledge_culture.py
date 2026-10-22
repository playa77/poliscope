"""Host-declared education input commitments, never learning predictions."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Definition, Digest
from .world import References, ScopeKind
from .economy import EconomyRequest, EconomyReport
from .allocations import AllocationRequest, AllocationEvaluation
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation

ClaimRefs = Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class EducationStaff(Contract):
    cohort_id: Identifier
    claim_id: Identifier
    qualification: Literal['declared', 'not_qualified', 'unknown']
    qualification_refs: References


class EducationParticipant(Contract):
    cohort_id: Identifier
    claim_id: Identifier


class EducationFacility(Contract):
    asset_id: Identifier
    account_id: Identifier
    source_refs: References


class EducationService(Contract):
    id: Identifier
    authority_id: Identifier
    binding_id: Identifier
    target_id: Identifier
    parameter_id: Identifier
    eligibility: Literal['allowed', 'denied', 'unknown']
    participants: Annotated[list[EducationParticipant], Field(min_length=1, max_length=100)]
    staff: Annotated[list[EducationStaff], Field(min_length=1, max_length=100)]
    supply_claim_ids: ClaimRefs
    facility_claim_ids: ClaimRefs
    knowledge_refs: References
    skill_refs: References
    technology_assumption_refs: References
    obligation_refs: References
    source_refs: References


class EducationRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    services: Annotated[list[EducationService], Field(min_length=1, max_length=100)]
    bindings: Annotated[list[PolicyBinding], Field(min_length=1, max_length=100)]
    rules: Annotated[list[ResolutionRule], Field(max_length=100)]
    work: EconomyRequest
    facilities: Annotated[list[EducationFacility], Field(min_length=1, max_length=100)]
    facility_allocation: AllocationRequest
    source_refs: References


class EducationResult(Contract):
    service_id: Identifier
    status: Literal['resolved', 'unresolved']
    outcome: Literal['capacity_ready', 'capacity_blocked', 'ineligible', 'unqualified'] | None
    findings: Annotated[list[str], Field(max_length=20)]
    unmet_claim_ids: Annotated[list[Identifier], Field(max_length=400)]


class EducationEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    evidence_status: Literal['hypothetical']
    request: EducationRequest
    results: Annotated[list[EducationResult], Field(min_length=1, max_length=100)]
    policies: PolicyEvaluation
    work: EconomyReport
    # Independent facility commitments, not a transactional service delivery.
    facility_allocation: AllocationEvaluation


class EducationAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class EducationInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[EducationAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class EducationEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class EducationReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['education-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: EducationEvaluation


class EducationPreview(Contract):
    contract_version: Literal[1]
    edit: EducationEdit
    candidate_digest: Digest
    report: EducationReport


class EducationCoverageEntry(Contract):
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


class EducationCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[EducationCoverageEntry], Field(min_length=1, max_length=100)]
