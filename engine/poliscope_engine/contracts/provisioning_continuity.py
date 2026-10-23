"""Explicit finite continuity-slot prerequisites, separate from material throughput."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .accounts import AccountBatch
from .security_risk import ContinuityRequest, ContinuityEvaluation
from .provisioning_economy import ProvisioningEconomyRequest, ProvisioningEconomyEvaluation
from .evaluation import Digest


class ContinuityPrerequisite(Contract):
    phase_id: Identifier
    claim_id: Identifier
    # Full declared slot commitment is required; no inferred slot/kg conversion.
    demand_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]


class ProvisioningContinuityRequest(Contract):
    contract_version: Literal[1]
    continuity: ContinuityRequest
    provisioning: ProvisioningEconomyRequest
    prerequisites: Annotated[list[ContinuityPrerequisite], Field(min_length=1, max_length=1000)]


class ProvisioningContinuityEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-continuity-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningContinuityRequest
    continuity: ContinuityEvaluation
    provisioning: ProvisioningEconomyEvaluation | None
    batch: AccountBatch | None
