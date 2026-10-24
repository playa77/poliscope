"""Private hypothetical case prerequisites for host-declared care obligations."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation
from .social_organization import CareRequest, CareEvaluation


class CareLegalPrerequisite(Contract):
    obligation_id: Identifier
    # None explicitly declares independence from adjudication.
    case_id: Identifier | None


class AdjudicationCareRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    care: CareRequest
    prerequisites: Annotated[list[CareLegalPrerequisite], Field(min_length=1, max_length=100)]


class AdjudicationCareEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-care-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: AdjudicationCareRequest
    adjudication: AdjudicationEvaluation
    preflight: CareEvaluation
    care: CareEvaluation | None
    batch: AccountBatch | None
