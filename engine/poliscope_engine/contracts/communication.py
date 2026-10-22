"""Host-only message prerequisite evidence; no payloads or delivery transitions."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, SafeCount, DecimalString, ScopeKind
from .packs import Definition, Digest
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


class CommunicationAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class CommunicationInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[CommunicationAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class CommunicationEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class CommunicationReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['communication-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: CommunicationEvaluation


class CommunicationPreview(Contract):
    contract_version: Literal[1]
    edit: CommunicationEdit
    candidate_digest: Digest
    report: CommunicationReport


class CommunicationCoverageEntry(Contract):
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


class CommunicationCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[CommunicationCoverageEntry], Field(min_length=1, max_length=100)]
