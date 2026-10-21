"""Explicit hypothetical equal-member decision procedure; no legitimacy score."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation
from .economy import EconomyRequest, EconomyEvaluation


class Ballot(Contract):
    member_id: Identifier
    vote: Literal['yes', 'no', 'abstain', 'unknown']


class GovernanceRequest(Contract):
    contract_version: Literal[1]
    authority_id: Identifier
    scope_id: Identifier
    proposal_binding_id: Identifier
    target_id: Identifier
    parameter_id: Identifier
    eligible_member_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]
    ballots: Annotated[list[Ballot], Field(max_length=1000)]
    quorum: Annotated[int, Field(ge=1, le=1000)]
    approval: Literal['strict_majority', 'unanimity'] | None
    bindings: Annotated[list[PolicyBinding], Field(min_length=1, max_length=100)]
    rules: Annotated[list[ResolutionRule], Field(max_length=100)]
    administration: EconomyRequest
    administrative_claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    source_refs: References


class GovernanceEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    outcome: Literal['approved', 'rejected', 'no_quorum', 'capacity_blocked'] | None
    findings: Annotated[list[str], Field(max_length=20)]
    request: GovernanceRequest
    policies: PolicyEvaluation
    administration: EconomyEvaluation
    # Always a private preview. Approval does not apply a policy or spend time.
    evidence_status: Literal['hypothetical']
