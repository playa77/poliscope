"""Explicit facility prerequisites for host-selected finite economic claims."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .accounts import AccountBatch
from .economy import EconomyRequest, EconomyEvaluation
from .infrastructure import InfrastructureRequest, InfrastructureEvaluation
from .evaluation import Digest


class EconomyFacilityPrerequisite(Contract):
    claim_id: Identifier
    # Empty explicitly declares independence; an omitted claim is invalid.
    demand_ids: Annotated[list[Identifier], Field(max_length=100)]


class EconomyInfrastructureRequest(Contract):
    contract_version: Literal[1]
    infrastructure: InfrastructureRequest
    economy: EconomyRequest
    prerequisites: Annotated[list[EconomyFacilityPrerequisite], Field(min_length=1, max_length=1000)]


class EconomyInfrastructureEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['economy-infrastructure-v1']
    baseline_digest: Digest
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: EconomyInfrastructureRequest
    infrastructure: InfrastructureEvaluation
    economy: EconomyEvaluation | None
    batch: AccountBatch | None
