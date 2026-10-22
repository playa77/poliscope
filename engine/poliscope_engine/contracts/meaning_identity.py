"""Declared accommodation prerequisites; no assessment of inner experience."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, DecimalString
from .accounts import AccountBatch
from .allocations import AllocationEvaluation


class ParticipationFacility(Contract):
    asset_id: Identifier
    institution_id: Identifier
    ownership_relationship_id: Identifier
    account_id: Identifier
    availability: Literal['operating', 'offline', 'unknown']
    source_refs: References


class ParticipationDemand(Contract):
    claim_id: Identifier
    group_id: Identifier
    facility_asset_id: Identifier
    access_relationship_id: Identifier | None
    commitment_ref: Identifier
    accommodation_ref: Identifier
    participation: Literal['requested', 'declined', 'unknown']
    eligibility: Literal['eligible', 'ineligible', 'unknown']
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    obligation_status: Literal['compatible', 'conflict', 'unknown']
    obligation_refs: References
    source_refs: References


class ParticipationRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    facilities: Annotated[list[ParticipationFacility], Field(min_length=1, max_length=100)]
    demands: Annotated[list[ParticipationDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class ParticipationReadiness(Contract):
    claim_id: Identifier
    outcome: Literal['capacity_ready', 'blocked', 'unresolved']
    findings: Annotated[list[str], Field(max_length=20)]
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class ParticipationEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ParticipationRequest
    allocation: AllocationEvaluation
    results: Annotated[list[ParticipationReadiness], Field(min_length=1, max_length=1000)]
