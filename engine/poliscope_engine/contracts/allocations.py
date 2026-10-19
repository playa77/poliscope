"""Host-selected finite procedures; imported declarations never execute code."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import DecimalString, References
from .accounts import AccountBatch, AccountEvaluation


class FundingRequirement(Contract):
    account_id: Identifier
    per_unit: DecimalString
    kind: Literal['funding', 'entitlement']


class TransformationOutput(Contract):
    account_id: Identifier
    per_unit: DecimalString
    role: Literal['product', 'residual']


class AllocationChoice(Contract):
    claim_id: Identifier
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    funding_known: bool
    requirements: Annotated[list[FundingRequirement], Field(max_length=100)]
    outputs: Annotated[list[TransformationOutput], Field(max_length=100)]
    loss_per_unit: DecimalString
    mechanism_ref: Identifier
    source_refs: References


class AllocationRequest(Contract):
    contract_version: Literal[1]
    batch: AccountBatch
    procedure: Literal['priority', 'all_or_nothing'] | None
    # This is a declared political/procedural order, never an ID-based fallback.
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    choices: Annotated[list[AllocationChoice], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class AllocationActual(Contract):
    claim_id: Identifier
    allocated: DecimalString
    unmet: DecimalString
    reason: Literal['satisfied', 'denied', 'limited', 'unresolved']
    outputs: Annotated[list[DecimalString], Field(max_length=100)]
    loss: DecimalString


class AllocationEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    missing: Annotated[list[Literal['procedure', 'access', 'funding']], Field(max_length=3)]
    # Retain the complete selected procedure, coefficients and provenance.
    request: AllocationRequest
    actuals: Annotated[list[AllocationActual], Field(max_length=1000)]
    batch: AccountBatch
    accounts: AccountEvaluation
