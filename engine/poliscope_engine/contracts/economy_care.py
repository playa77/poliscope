"""Host-only canonical care and economy over one finite dated book."""
from typing import Literal
from .base import Contract
from .evaluation import Digest
from .accounts import AccountBatch
from .social_organization import CareRequest, CareEvaluation
from .economy import EconomyRequest, EconomyEvaluation


class EconomyCareRequest(Contract):
    contract_version: Literal[1]
    care: CareRequest
    economy: EconomyRequest


class EconomyCareEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-care-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: EconomyCareRequest
    care: CareEvaluation
    economy: EconomyEvaluation | None
    batch: AccountBatch | None
