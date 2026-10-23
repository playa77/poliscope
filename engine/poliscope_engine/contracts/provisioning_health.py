"""Host-only health commitments -> provisioning; no health change or publication."""
from typing import Literal
from .base import Contract
from .evaluation import Digest
from .accounts import AccountBatch
from .health import HealthRequest, HealthEvaluation
from .provisioning_economy import ProvisioningEconomyRequest
from .provisioning import ProvisioningEvaluation


class ProvisioningHealthRequest(Contract):
    contract_version: Literal[1]
    health: HealthRequest
    provisioning: ProvisioningEconomyRequest


class ProvisioningHealthEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-health-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningHealthRequest
    health: HealthEvaluation
    provisioning: ProvisioningEvaluation | None
    # Facilities stay in health.facility_allocation; never merge local posting IDs.
    batch: AccountBatch | None
