"""Private decision/response prerequisites; no hazard prediction or delivered rescue."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .governance import GovernanceRequest, GovernanceEvaluation
from .security_risk import ContinuityRequest, ContinuityEvaluation


class ContinuityDecisionPrerequisite(Contract):
    claim_id: Identifier
    requires_approval: bool
    # Dependent responses identify the exact subject of the decision. Independent
    # responses explicitly use null; proximity/identifier order cannot infer it.
    decision_target_id: Identifier | None


class GovernanceContinuityRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    continuity: ContinuityRequest
    prerequisites: Annotated[list[ContinuityDecisionPrerequisite], Field(min_length=1, max_length=1000)]


class GovernanceContinuityCandidate(Contract):
    administration: AccountBatch
    continuity: AccountBatch


class GovernanceContinuityEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-continuity-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: GovernanceContinuityRequest
    governance: GovernanceEvaluation
    # Original-term preflight remains inspectable when a decision is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: ContinuityEvaluation
    continuity: ContinuityEvaluation | None
    candidate: GovernanceContinuityCandidate | None
