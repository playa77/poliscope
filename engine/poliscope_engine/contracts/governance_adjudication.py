"""Private explicit procedural prerequisites; no adoption or enforcement."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .governance import GovernanceRequest, GovernanceEvaluation
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation


class CaseDecisionPrerequisite(Contract):
    case_id: Identifier
    requires_approval: bool


class GovernanceAdjudicationRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    adjudication: AdjudicationRequest
    prerequisites: Annotated[list[CaseDecisionPrerequisite], Field(min_length=1, max_length=100)]


class GovernanceAdjudicationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-adjudication-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: GovernanceAdjudicationRequest
    governance: GovernanceEvaluation
    adjudication: AdjudicationEvaluation | None
    batch: AccountBatch | None
