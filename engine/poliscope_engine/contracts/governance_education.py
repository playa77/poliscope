"""Private explicit education prerequisites; no adoption or learning inference."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .governance import GovernanceRequest, GovernanceEvaluation
from .knowledge_culture import EducationRequest, EducationEvaluation


class EducationDecisionPrerequisite(Contract):
    service_id: Identifier
    requires_approval: bool


class GovernanceEducationRequest(Contract):
    contract_version: Literal[1]
    governance: GovernanceRequest
    education: EducationRequest
    prerequisites: Annotated[list[EducationDecisionPrerequisite], Field(min_length=1, max_length=100)]


class GovernanceEducationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['governance-education-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: GovernanceEducationRequest
    governance: GovernanceEvaluation
    education: EducationEvaluation | None
    batch: AccountBatch | None
