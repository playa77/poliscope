"""Private explicit legal education prerequisites; no rights or learning inference."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest
from .accounts import AccountBatch
from .law_conflict import AdjudicationRequest, AdjudicationEvaluation
from .knowledge_culture import EducationRequest, EducationEvaluation


class EducationLegalPrerequisite(Contract):
    service_id: Identifier
    case_id: Identifier | None


class AdjudicationEducationRequest(Contract):
    contract_version: Literal[1]
    adjudication: AdjudicationRequest
    education: EducationRequest
    prerequisites: Annotated[list[EducationLegalPrerequisite], Field(min_length=1, max_length=100)]


class AdjudicationEducationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['adjudication-education-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: AdjudicationEducationRequest
    adjudication: AdjudicationEvaluation
    preflight: EducationEvaluation
    education: EducationEvaluation | None
    batch: AccountBatch | None
