"""Explicit hypothetical equal-member decision procedure; no legitimacy score."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, ScopeKind
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation
from .economy import EconomyRequest, EconomyEvaluation, EconomyReport
from .packs import Definition, Digest


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


class GovernanceAlternative(Contract):
    definition: Definition
    approval: Literal['strict_majority', 'unanimity']


class GovernanceInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[GovernanceAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class GovernanceEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class GovernanceReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: GovernanceEvaluation
    administration: EconomyReport


class GovernancePreview(Contract):
    contract_version: Literal[1]
    edit: GovernanceEdit
    candidate_digest: Digest
    report: GovernanceReport


class GovernanceCoverageEntry(Contract):
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



class GovernanceCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[GovernanceCoverageEntry], Field(min_length=1, max_length=100)]
