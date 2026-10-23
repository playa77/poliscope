"""Private decision/message prerequisites; neither delivery nor publication."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .governance import GovernanceRequest, GovernanceEvaluation
from .communication import CommunicationRequest, CommunicationEvaluation


class MessageDecisionPrerequisite(Contract):
    claim_id: Identifier
    requires_approval: bool
    # Required messages identify the exact subject of the decision. Independent
    # messages explicitly use null; proximity/identifier order cannot infer it.
    decision_target_id: Identifier | None


class GovernanceCommunicationRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    communication: CommunicationRequest
    prerequisites: Annotated[list[MessageDecisionPrerequisite], Field(min_length=1, max_length=1000)]


class GovernanceCommunicationCandidate(Contract):
    administration: AccountBatch
    communication: AccountBatch


class GovernanceCommunicationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-communication-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: GovernanceCommunicationRequest
    governance: GovernanceEvaluation
    # Original-term preflight remains inspectable when a decision is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: CommunicationEvaluation
    communication: CommunicationEvaluation | None
    candidate: GovernanceCommunicationCandidate | None
