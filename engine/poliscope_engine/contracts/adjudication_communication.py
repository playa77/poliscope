"""Private explicit legal message prerequisites; no rights or delivery inference."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation
from .communication import CommunicationRequest, CommunicationEvaluation


class MessageLegalPrerequisite(Contract):
    claim_id: Identifier
    case_id: Identifier | None


class AdjudicationCommunicationRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    communication: CommunicationRequest
    prerequisites: Annotated[list[MessageLegalPrerequisite], Field(min_length=1, max_length=1000)]


class AdjudicationCommunicationCandidate(Contract):
    administration: AccountBatch
    communication: AccountBatch


class AdjudicationCommunicationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-communication-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: AdjudicationCommunicationRequest
    adjudication: AdjudicationEvaluation
    # Original-term preflight remains inspectable when a case is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: CommunicationEvaluation
    communication: CommunicationEvaluation | None
    candidate: AdjudicationCommunicationCandidate | None
