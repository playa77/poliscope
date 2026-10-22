"""Host-only finite ecological boundary prerequisites; no ecological effects."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString, References
from .accounts import AccountBatch
from .allocations import AllocationEvaluation


class EcologicalBoundary(Contract):
    resource_id: Identifier
    role: Literal['extraction_stock', 'sink_allowance']
    account_id: Identifier
    capacity_status: Literal['known', 'unknown']
    # Limit is a diagnostic on gross outward postings in the retained batch.
    # A reference without a value means an unknown selected limit.
    selected_limit: DecimalString | None
    policy_ref: Identifier | None
    source_refs: References


class EnvironmentalDemand(Contract):
    claim_id: Identifier
    scope_id: Identifier
    scope_relationship_id: Identifier
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    source_refs: References


class EnvironmentRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    boundaries: Annotated[list[EcologicalBoundary], Field(min_length=1, max_length=100)]
    demands: Annotated[list[EnvironmentalDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class EnvironmentalReadiness(Contract):
    claim_id: Identifier
    outcome: Literal['capacity_ready', 'blocked', 'unresolved']
    findings: Annotated[list[str], Field(max_length=10)]
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class EcologicalBoundaryResult(Contract):
    account_id: Identifier
    gross_debit: DecimalString
    limit_status: Literal['not_selected', 'unknown', 'within_limit', 'limit_breached']
    # On unresolved allocation this describes retained postings only.
    candidate_complete: bool


class EnvironmentEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: EnvironmentRequest
    allocation: AllocationEvaluation
    results: Annotated[list[EnvironmentalReadiness], Field(min_length=1, max_length=1000)]
    boundaries: Annotated[list[EcologicalBoundaryResult], Field(min_length=1, max_length=100)]
