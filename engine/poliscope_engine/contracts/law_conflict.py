"""Explicit host legal claims; no inferred rights, merits or enforcement."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation
from .economy import EconomyRequest, EconomyReport


class LegalCase(Contract):
    id: Identifier
    right_ref: Identifier
    claimant_id: Identifier
    authority_id: Identifier
    binding_id: Identifier
    target_id: Identifier
    parameter_id: Identifier
    eligibility: Literal['eligible', 'ineligible', 'unknown']
    incompatible_right_refs: References
    disposition: Literal['upheld', 'dismissed'] | None
    rationale: Annotated[str, Field(min_length=1, max_length=2048)] | None
    # Required procedural work, never a transfer to the legal claimant.
    work_claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    obligation_refs: References
    source_refs: References


class AdjudicationRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    cases: Annotated[list[LegalCase], Field(min_length=1, max_length=100)]
    bindings: Annotated[list[PolicyBinding], Field(min_length=1, max_length=100)]
    rules: Annotated[list[ResolutionRule], Field(max_length=100)]
    administration: EconomyRequest
    source_refs: References


class CaseResult(Contract):
    case_id: Identifier
    status: Literal['resolved', 'unresolved']
    outcome: Literal['upheld', 'dismissed', 'ineligible', 'capacity_blocked'] | None
    findings: Annotated[list[str], Field(max_length=20)]
    # Report only: these references authorize neither service nor enforcement.
    proposed_obligation_refs: References


class AdjudicationEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    evidence_status: Literal['hypothetical']
    request: AdjudicationRequest
    results: Annotated[list[CaseResult], Field(min_length=1, max_length=100)]
    policies: PolicyEvaluation
    administration: EconomyReport
