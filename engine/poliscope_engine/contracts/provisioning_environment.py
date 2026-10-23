"""Host-only extraction/transformation with exact residual sink allowances."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .accounts import AccountBatch
from .environment import EcologicalBoundary, EnvironmentalDemand, EnvironmentEvaluation
from .provisioning_economy import ProvisioningEconomyRequest
from .economy import EconomyEvaluation
from .provisioning import ProvisioningEvaluation
from .evaluation import Digest
from .world import DecimalString


class ResidualSink(Contract):
    claim_id: Identifier
    account_id: Identifier
    scope_relationship_id: Identifier
    access: Literal['allowed', 'denied', 'unknown']
    # In sink units per input unit, validated against every residual and loss.
    per_unit: DecimalString


class ProvisioningEnvironmentRequest(Contract):
    contract_version: Literal[1]
    provisioning: ProvisioningEconomyRequest
    # Exact canonical accounts already present in the provisioning book.
    boundaries: Annotated[list[EcologicalBoundary], Field(min_length=2, max_length=100)]
    demands: Annotated[list[EnvironmentalDemand], Field(min_length=1, max_length=1000)]
    sinks: Annotated[list[ResidualSink], Field(min_length=1, max_length=1000)]


class ProvisioningEnvironmentEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['provisioning-environment-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: ProvisioningEnvironmentRequest
    work: EconomyEvaluation
    environment: EnvironmentEvaluation | None
    provisioning: ProvisioningEvaluation | None
    batch: AccountBatch | None
