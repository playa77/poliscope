"""Bounded host-selected economy terms, with no implicit property or wage model."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString, References
from .accounts import AccountBatch
from .allocations import AllocationEvaluation, FundingRequirement


class BudgetHolder(Contract):
    account_id: Identifier
    holder_id: Identifier
    role: Literal['entitlement', 'funding', 'time']


class EconomyActivity(Contract):
    claim_id: Identifier
    kind: Literal['goods', 'paid_work', 'unpaid_work', 'care', 'training', 'participation']
    eligibility: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    terms_known: bool
    requirements: Annotated[list[FundingRequirement], Field(max_length=100)]
    mechanism_ref: Identifier
    source_refs: References


class EconomyRequest(Contract):
    contract_version: Literal[1]
    period_id: Identifier
    batch: AccountBatch
    holders: Annotated[list[BudgetHolder], Field(max_length=1000)]
    activities: Annotated[list[EconomyActivity], Field(max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class EconomyEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    request: EconomyRequest
    # Unresolved actuals in the underlying allocator are placeholders, not zeros
    # observed in the world. No complete candidate is exposed in that case.
    allocation: AllocationEvaluation
    batch: AccountBatch | None
