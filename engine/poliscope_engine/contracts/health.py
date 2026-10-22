"""Host-declared health input commitments, never treatment predictions."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References
from .economy import EconomyRequest, EconomyReport
from .allocations import AllocationRequest, AllocationEvaluation
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation

ClaimRefs = Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class HealthStaff(Contract):
    cohort_id: Identifier
    claim_id: Identifier
    qualification: Literal['declared', 'not_qualified', 'unknown']
    qualification_refs: References


class HealthParticipant(Contract):
    cohort_id: Identifier
    claim_id: Identifier


class HealthFacility(Contract):
    asset_id: Identifier
    account_id: Identifier
    source_refs: References


class HealthService(Contract):
    id: Identifier
    authority_id: Identifier
    binding_id: Identifier
    target_id: Identifier
    parameter_id: Identifier
    eligibility: Literal['allowed', 'denied', 'unknown']
    participants: Annotated[list[HealthParticipant], Field(min_length=1, max_length=100)]
    staff: Annotated[list[HealthStaff], Field(min_length=1, max_length=100)]
    supply_claim_ids: ClaimRefs
    facility_claim_ids: ClaimRefs
    # Declared context references; they do not activate health/exposure models.
    need_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    exposure_refs: References
    health_state_refs: References
    obligation_refs: References
    source_refs: References


class HealthRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    services: Annotated[list[HealthService], Field(min_length=1, max_length=100)]
    bindings: Annotated[list[PolicyBinding], Field(min_length=1, max_length=100)]
    rules: Annotated[list[ResolutionRule], Field(max_length=100)]
    work: EconomyRequest
    facilities: Annotated[list[HealthFacility], Field(min_length=1, max_length=100)]
    facility_allocation: AllocationRequest
    source_refs: References


class HealthResult(Contract):
    service_id: Identifier
    status: Literal['resolved', 'unresolved']
    outcome: Literal['capacity_ready', 'capacity_blocked', 'ineligible', 'unqualified'] | None
    findings: Annotated[list[str], Field(max_length=20)]
    unmet_claim_ids: Annotated[list[Identifier], Field(max_length=400)]


class HealthEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    evidence_status: Literal['hypothetical']
    request: HealthRequest
    results: Annotated[list[HealthResult], Field(min_length=1, max_length=100)]
    policies: PolicyEvaluation
    work: EconomyReport
    # Independent facility commitments, not a transactional service delivery.
    facility_allocation: AllocationEvaluation
