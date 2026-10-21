"""Explicit, bounded host-selected static provisioning phases."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References
from .accounts import AccountBatch, AccountClaim, AccountReservation, AccountEvaluation
from .allocations import AllocationChoice, AllocationEvaluation
from .logistics import StockResource, TransportRoute, LogisticsEvaluation


class PhasePlan(Contract):
    id: Identifier
    claims: Annotated[list[AccountClaim], Field(min_length=1, max_length=1000)]
    reservations: Annotated[list[AccountReservation], Field(max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class AllocationPhase(PhasePlan):
    kind: Literal['production', 'storage', 'use']
    choices: Annotated[list[AllocationChoice], Field(max_length=1000)]


class FreightPhase(PhasePlan):
    kind: Literal['freight']
    routes: Annotated[list[TransportRoute], Field(max_length=1000)]


Phase = Annotated[AllocationPhase | FreightPhase, Field(discriminator='kind')]


class ProvisioningRequest(Contract):
    contract_version: Literal[1]
    batch: AccountBatch
    period_id: Identifier
    resources: Annotated[list[StockResource], Field(max_length=1000)]
    # Order is an explicit host-selected dependency plan, never inferred policy.
    phases: Annotated[list[Phase], Field(min_length=1, max_length=32)]


class PhaseEvaluation(Contract):
    phase_id: Identifier
    kind: Literal['production', 'freight', 'storage', 'use']
    evidence: AllocationEvaluation | LogisticsEvaluation


class ProvisioningEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    request: ProvisioningRequest
    phases: Annotated[list[PhaseEvaluation], Field(max_length=32)]
    blocked_phase_id: Identifier | None
    # Earlier phase evidence is staging only; unresolved plans have no candidate.
    batch: AccountBatch | None
    accounts: AccountEvaluation | None
