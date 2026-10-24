"""Private care and education evidence over one original shared work book."""
from typing import Literal
from .base import Contract
from .packs import Digest
from .accounts import AccountBatch
from .social_organization import CareRequest, CareEvaluation
from .knowledge_culture import EducationRequest, EducationEvaluation


class CareEducationRequest(Contract):
    contract_version: Literal[1]
    care: CareRequest
    education: EducationRequest


class CareEducationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['care-education-v1']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    status: Literal['resolved', 'unresolved']
    request: CareEducationRequest
    care: CareEvaluation
    education: EducationEvaluation
    batch: AccountBatch | None
