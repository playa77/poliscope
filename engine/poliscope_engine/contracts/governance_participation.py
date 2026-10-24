"""Private decision/accommodation prerequisites; no attendance or belief effects."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .governance import GovernanceRequest, GovernanceEvaluation
from .meaning_identity import ParticipationRequest, ParticipationEvaluation


class ParticipationDecisionPrerequisite(Contract):
    claim_id: Identifier
    requires_approval: bool
    # Dependent accommodations identify the exact subject of the decision. Independent
    # accommodations explicitly use null; proximity/identifier order cannot infer it.
    decision_target_id: Identifier | None


class GovernanceParticipationRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    participation: ParticipationRequest
    prerequisites: Annotated[list[ParticipationDecisionPrerequisite], Field(min_length=1, max_length=1000)]


class GovernanceParticipationCandidate(Contract):
    administration: AccountBatch
    participation: AccountBatch


class GovernanceParticipationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-participation-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: GovernanceParticipationRequest
    governance: GovernanceEvaluation
    # Original-term preflight remains inspectable when a decision is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: ParticipationEvaluation
    participation: ParticipationEvaluation | None
    candidate: GovernanceParticipationCandidate | None
