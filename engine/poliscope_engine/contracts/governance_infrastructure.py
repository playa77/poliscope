"""Private decision/facility-access prerequisites; no maintenance or lifecycle model."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .governance import GovernanceRequest, GovernanceEvaluation
from .infrastructure import InfrastructureRequest, InfrastructureEvaluation


class InfrastructureDecisionPrerequisite(Contract):
    claim_id: Identifier
    requires_approval: bool
    # Dependent demands identify the exact subject of the decision. Independent
    # demands explicitly use null; proximity/identifier order cannot infer it.
    decision_target_id: Identifier | None


class GovernanceInfrastructureRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    infrastructure: InfrastructureRequest
    prerequisites: Annotated[list[InfrastructureDecisionPrerequisite], Field(min_length=1, max_length=1000)]


class GovernanceInfrastructureCandidate(Contract):
    administration: AccountBatch
    infrastructure: AccountBatch


class GovernanceInfrastructureEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-infrastructure-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: GovernanceInfrastructureRequest
    governance: GovernanceEvaluation
    # Original-term preflight remains inspectable when a decision is unresolved.
    # Its independent preview allocations are never staged or published.
    preflight: InfrastructureEvaluation
    infrastructure: InfrastructureEvaluation | None
    candidate: GovernanceInfrastructureCandidate | None
