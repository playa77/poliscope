"""Explicit host legal claims; no inferred rights, merits or enforcement."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, ScopeKind
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation
from .economy import EconomyRequest, EconomyReport
from .packs import Definition, Digest


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


class AdjudicationAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]


class AdjudicationInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[AdjudicationAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class AdjudicationEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class AdjudicationReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: AdjudicationEvaluation
    administration: EconomyReport


class AdjudicationPreview(Contract):
    contract_version: Literal[1]
    edit: AdjudicationEdit
    candidate_digest: Digest
    report: AdjudicationReport


class AdjudicationCoverageEntry(Contract):
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



class AdjudicationCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[AdjudicationCoverageEntry], Field(min_length=1, max_length=100)]
