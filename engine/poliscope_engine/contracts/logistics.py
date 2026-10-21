"""Host-selected, lossless static transport; declarations never authorize routes."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString, References
from .accounts import AccountBatch, AccountEvaluation
from .allocations import AllocationEvaluation, FundingRequirement


class StockResource(Contract):
    account_id: Identifier
    resource_id: Identifier


class TransportRoute(Contract):
    # The existing claim names its source stock and recipient. Capacity belongs
    # to the source scope; routes cannot infer connectivity from a global total.
    claim_id: Identifier
    destination_id: Identifier
    capacity_id: Identifier
    capacity_per_unit: DecimalString
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    funding_known: bool
    requirements: Annotated[list[FundingRequirement], Field(max_length=99)]
    mechanism_ref: Identifier
    source_refs: References


class LogisticsRequest(Contract):
    contract_version: Literal[1]
    batch: AccountBatch
    period_id: Identifier
    resources: Annotated[list[StockResource], Field(max_length=1000)]
    routes: Annotated[list[TransportRoute], Field(max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class TransportActual(Contract):
    claim_id: Identifier
    source_id: Identifier
    destination_id: Identifier
    resource_id: Identifier
    delivered: DecimalString
    export_posting_ids: Annotated[list[Identifier], Field(max_length=10000)]
    import_posting_id: Identifier | None
    mechanism_ref: Identifier
    source_refs: References


class LogisticsEvaluation(Contract):
    contract_version: Literal[1]
    request: LogisticsRequest
    allocation: AllocationEvaluation
    movements: Annotated[list[TransportActual], Field(max_length=1000)]
    batch: AccountBatch
    accounts: AccountEvaluation
