"""Host-declared education input commitments, never learning predictions."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References
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
