"""Host-only care -> finite provisioning counterpart; no publication grant."""
from typing import Literal
from .base import Contract
from .evaluation import Digest
from .accounts import AccountBatch
from .social_organization import CareRequest, CareEvaluation
from .provisioning_economy import ProvisioningEconomyRequest, ProvisioningEconomyEvaluation


class ProvisioningCareRequest(Contract):
    contract_version: Literal[1]
    care: CareRequest
    provisioning: ProvisioningEconomyRequest


class ProvisioningCareEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-care-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningCareRequest
    care: CareEvaluation
    provisioning: ProvisioningEconomyEvaluation | None
    batch: AccountBatch | None
