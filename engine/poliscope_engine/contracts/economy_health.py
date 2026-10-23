"""Host-only health prerequisites and economy over one finite dated book."""
from typing import Literal
from .base import Contract
from .evaluation import Digest
from .accounts import AccountBatch
from .health import HealthRequest, HealthEvaluation
from .economy import EconomyRequest, EconomyEvaluation


class EconomyHealthRequest(Contract):
    contract_version: Literal[1]
    health: HealthRequest
    economy: EconomyRequest


class EconomyHealthEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-health-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: EconomyHealthRequest
    health: HealthEvaluation
    economy: EconomyEvaluation | None
    batch: AccountBatch | None
