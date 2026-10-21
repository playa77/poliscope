"""Explicit, bounded host-selected static provisioning phases."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, DecimalString, ScopeKind
from .evaluation import Digest
from .packs import Definition
from .accounts import AccountBatch, AccountClaim, AccountReservation, AccountEvaluation
from .allocations import AllocationChoice, AllocationEvaluation
from .logistics import StockResource, TransportRoute, LogisticsEvaluation


class PhasePlan(Contract):
    id: Identifier
    claims: Annotated[list[AccountClaim], Field(min_length=1, max_length=1000)]
    reservations: Annotated[list[AccountReservation], Field(max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class AllocationPhase(PhasePlan):
    kind: Literal['production', 'storage', 'use']
    choices: Annotated[list[AllocationChoice], Field(max_length=1000)]


class FreightPhase(PhasePlan):
    kind: Literal['freight']
    routes: Annotated[list[TransportRoute], Field(max_length=1000)]


Phase = Annotated[AllocationPhase | FreightPhase, Field(discriminator='kind')]


class ProvisioningRequest(Contract):
    contract_version: Literal[1]
    batch: AccountBatch
    period_id: Identifier
    resources: Annotated[list[StockResource], Field(max_length=1000)]
    # Order is an explicit host-selected dependency plan, never inferred policy.
    phases: Annotated[list[Phase], Field(min_length=1, max_length=32)]


class PhaseEvaluation(Contract):
    phase_id: Identifier
    kind: Literal['production', 'freight', 'storage', 'use']
    evidence: AllocationEvaluation | LogisticsEvaluation


class ProvisioningEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    request: ProvisioningRequest
    phases: Annotated[list[PhaseEvaluation], Field(max_length=32)]
    blocked_phase_id: Identifier | None
    # Earlier phase evidence is staging only; unresolved plans have no candidate.
    batch: AccountBatch | None
    accounts: AccountEvaluation | None


# Host-only scoped exploration. These DTOs grant no execution/publication authority.
class ProcedureAlternative(Contract):
    definition: Definition
    procedure: Literal['priority', 'all_or_nothing']


class ProvisioningInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    phase_id: Identifier
    question: Definition
    alternatives: Annotated[list[ProcedureAlternative], Field(min_length=2, max_length=2)]
    claim_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class ProcedureEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    phase_id: Identifier
    option_id: Identifier
    claim_order: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]


class CapacityIndicator(Contract):
    account_id: Identifier
    kind: Literal['funding', 'entitlement', 'transport']
    per_unit: DecimalString
    unit_id: Identifier
    scope_id: Identifier
    period_id: Identifier | None
    available_before: DecimalString | None
    available_after: DecimalString | None


class ClaimIndicator(Contract):
    phase_id: Identifier
    kind: Literal['production', 'freight', 'storage', 'use']
    claim_id: Identifier
    claimant_id: Identifier
    account_id: Identifier
    resource_id: Identifier
    scope_id: Identifier
    unit_id: Identifier
    period_id: Identifier
    status: Literal['resolved', 'unresolved', 'not_evaluated']
    requested: DecimalString
    available_before: DecimalString | None
    actual: DecimalString | None
    unmet: DecimalString | None
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    missing: Annotated[list[Literal['procedure', 'access', 'funding']], Field(max_length=3)]
    constraints: Annotated[list[CapacityIndicator], Field(max_length=101)]
    posting_ids: Annotated[list[Identifier], Field(max_length=10000)]
    # Union of claim, choice and phase provenance, each bounded at 100.
    source_refs: Annotated[list[Identifier], Field(max_length=300)]


class ProvisioningReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-exploration-v1', 'provisioning-exploration-v2']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    indicators: Annotated[list[ClaimIndicator], Field(max_length=1000)]
    # Complete phase evidence retains yields/loss, holds, output and movement links.
    evaluation: ProvisioningEvaluation


class ProvisioningPreview(Contract):
    contract_version: Literal[1]
    edit: ProcedureEdit
    candidate_digest: Digest
    report: ProvisioningReport


class ProvisioningCoverageEntry(Contract):
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


class ProvisioningCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[ProvisioningCoverageEntry], Field(min_length=1, max_length=100)]
