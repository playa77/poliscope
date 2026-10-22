"""Host-only message prerequisite evidence; no payloads or delivery transitions."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, SafeCount, DecimalString
from .accounts import AccountBatch
from .allocations import AllocationEvaluation


class CommunicationChannel(Contract):
    asset_id: Identifier
    controller_id: Identifier
    ownership_relationship_id: Identifier
    account_id: Identifier
    availability: Literal['operating', 'offline', 'unknown']
    source_refs: References


class MessageDemand(Contract):
    claim_id: Identifier
    message_ref: Identifier
    channel_asset_id: Identifier
    sender_id: Identifier
    recipient_id: Identifier
    channel_relationship_id: Identifier | None
    recorded: bool | None
    available: bool | None
    publish_access: Literal['allowed', 'denied', 'unknown']
    receive_access: Literal['allowed', 'denied', 'unknown']
    disclosure: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    # An optional, explicit finite slot prerequisite; never a truth assessment.
    verification_account_id: Identifier | None
    verification_procedure_ref: Identifier | None
    delay_ticks: SafeCount | None
    obligation_refs: References
    source_refs: References


class CommunicationRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    channels: Annotated[list[CommunicationChannel], Field(min_length=1, max_length=100)]
    demands: Annotated[list[MessageDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class MessageReadiness(Contract):
    claim_id: Identifier
    outcome: Literal['capacity_ready', 'blocked', 'unresolved']
    findings: Annotated[list[str], Field(max_length=20)]
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class CommunicationEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: CommunicationRequest
    allocation: AllocationEvaluation
    results: Annotated[list[MessageReadiness], Field(min_length=1, max_length=1000)]
