"""Bounded host-selected economy terms, with no implicit property or wage model."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString, References, ScopeKind
from .packs import Definition, Digest
from .accounts import AccountBatch
from .allocations import AllocationEvaluation, FundingRequirement


class BudgetHolder(Contract):
    account_id: Identifier
    holder_id: Identifier
    role: Literal['entitlement', 'funding', 'time']


class EconomyActivity(Contract):
    claim_id: Identifier
    kind: Literal['goods', 'paid_work', 'unpaid_work', 'care', 'training', 'participation']
    eligibility: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    terms_known: bool
    requirements: Annotated[list[FundingRequirement], Field(max_length=100)]
    mechanism_ref: Identifier
    source_refs: References


class EconomyRequest(Contract):
    contract_version: Literal[1]
    period_id: Identifier
    batch: AccountBatch
    holders: Annotated[list[BudgetHolder], Field(max_length=1000)]
    activities: Annotated[list[EconomyActivity], Field(max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class EconomyEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    request: EconomyRequest
    # Unresolved actuals in the underlying allocator are placeholders, not zeros
    # observed in the world. No complete candidate is exposed in that case.
    allocation: AllocationEvaluation
    batch: AccountBatch | None


# Pure host exploration; these records grant no publication authority.
class EconomyAlternative(Contract):
    definition: Definition
    procedure: Literal['priority', 'all_or_nothing']


class EconomyInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[EconomyAlternative], Field(min_length=2, max_length=2)]
    claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class EconomyEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier
    claim_order: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]


class EconomyBudgetIndicator(Contract):
    account_id: Identifier
    holder_id: Identifier
    role: Literal['entitlement', 'funding', 'time']
    per_unit: DecimalString
    scope_id: Identifier
    period_id: Identifier | None
    unit_id: Identifier
    available_before: DecimalString
    available_after: DecimalString | None


class EconomyClaimIndicator(Contract):
    claim_id: Identifier
    claimant_id: Identifier
    kind: Literal['goods', 'paid_work', 'unpaid_work', 'care', 'training', 'participation']
    account_id: Identifier
    scope_id: Identifier
    period_id: Identifier | None
    unit_id: Identifier
    requested: DecimalString
    actual_before: DecimalString
    actual: DecimalString | None
    unmet: DecimalString | None
    available_before: DecimalString
    eligibility: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    terms_known: bool
    budgets: Annotated[list[EconomyBudgetIndicator], Field(max_length=101)]
    posting_ids: Annotated[list[Identifier], Field(max_length=10000)]
    source_refs: Annotated[list[Identifier], Field(max_length=300)]


class EconomyReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    indicators: Annotated[list[EconomyClaimIndicator], Field(max_length=1000)]
    evaluation: EconomyEvaluation


class EconomyPreview(Contract):
    contract_version: Literal[1]
    edit: EconomyEdit
    candidate_digest: Digest
    report: EconomyReport


class EconomyCoverageEntry(Contract):
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


class EconomyCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[EconomyCoverageEntry], Field(min_length=1, max_length=100)]
