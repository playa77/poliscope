"""Host-only education commitments -> provisioning; no learning or publication."""
from typing import Literal
from .base import Contract
from .evaluation import Digest
from .accounts import AccountBatch
from .knowledge_culture import EducationRequest, EducationEvaluation
from .provisioning_economy import ProvisioningEconomyRequest
from .provisioning import ProvisioningEvaluation


class ProvisioningEducationRequest(Contract):
    contract_version: Literal[1]
    education: EducationRequest
    provisioning: ProvisioningEconomyRequest


class ProvisioningEducationEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-education-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningEducationRequest
    education: EducationEvaluation
    provisioning: ProvisioningEvaluation | None
    # Facilities stay in education.facility_allocation; never merge local posting IDs.
    batch: AccountBatch | None
