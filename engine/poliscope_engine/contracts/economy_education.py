"""Host-only education prerequisites and economy over one finite dated book."""
from typing import Literal
from .base import Contract
from .evaluation import Digest
from .accounts import AccountBatch
from .knowledge_culture import EducationRequest, EducationEvaluation
from .economy import EconomyRequest, EconomyEvaluation


class EconomyEducationRequest(Contract):
    contract_version: Literal[1]
    education: EducationRequest
    economy: EconomyRequest


class EconomyEducationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-education-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: EconomyEducationRequest
    education: EducationEvaluation
    economy: EconomyEvaluation | None
    batch: AccountBatch | None
