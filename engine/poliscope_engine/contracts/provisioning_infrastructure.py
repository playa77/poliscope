"""Explicit finite facility-reach prerequisites, separate from material throughput."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .accounts import AccountBatch
from .infrastructure import InfrastructureRequest, InfrastructureEvaluation
from .provisioning_economy import ProvisioningEconomyRequest, ProvisioningEconomyEvaluation
from .evaluation import Digest


class FacilityPrerequisite(Contract):
    phase_id: Identifier
    claim_id: Identifier
    # Full declared slot commitment is required; no inferred slot/kg conversion.
    demand_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class ProvisioningInfrastructureRequest(Contract):
    contract_version: Literal[1]
    infrastructure: InfrastructureRequest
    provisioning: ProvisioningEconomyRequest
    prerequisites: Annotated[list[FacilityPrerequisite], Field(min_length=1, max_length=1000)]


class ProvisioningInfrastructureEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-infrastructure-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningInfrastructureRequest
    infrastructure: InfrastructureEvaluation
    provisioning: ProvisioningEconomyEvaluation | None
    batch: AccountBatch | None
