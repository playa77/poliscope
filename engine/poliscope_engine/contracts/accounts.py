"""Data-only accounts and already-solved postings; never allocation instructions."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .world import DecimalString, References

Items = Annotated[list[Identifier], Field(min_length=1, max_length=1000)]


class AccountDefinition(Contract):
    contract_version: Literal[1]
    id: Identifier
    kind: Literal['stock', 'flow', 'capacity']
    unit_id: Identifier
    scope_id: Identifier
    period_id: Identifier | None
    invariant: Literal['physical', 'budget', 'ledger']
    quantum: DecimalString
    maximum: DecimalString
    opening: DecimalString
    source_refs: References

    @model_validator(mode='after')
    def period(self):
        if self.kind != 'stock' and self.period_id is None:
            raise ValueError('period_required')
        return self


class AccountPosting(Contract):
    id: Identifier
    kind: Literal['supply', 'import', 'production', 'use', 'export', 'loss', 'transfer', 'residual']
    source_id: Identifier | None
    destination_id: Identifier | None
    amount: DecimalString
    reservation_id: Identifier | None
    claim_id: Identifier | None
    mechanism_ref: Identifier
    source_refs: References

    @model_validator(mode='after')
    def endpoints(self):
        if self.kind in ('supply', 'import', 'production'):
            valid = self.source_id is None and self.destination_id is not None
        elif self.kind in ('use', 'export', 'loss'):
            valid = self.source_id is not None and self.destination_id is None
        else:
            valid = self.source_id is not None and self.destination_id is not None
        if not valid or (self.source_id is not None and self.source_id == self.destination_id):
            raise ValueError('invalid_posting_endpoints')
        if (self.reservation_id is not None or self.claim_id is not None) and self.kind not in ('use', 'export', 'transfer'):
            raise ValueError('invalid_fulfillment')
        return self


class AccountClaim(Contract):
    id: Identifier
    account_id: Identifier
    claimant_id: Identifier
    requested: DecimalString
    source_refs: References


class AccountReservation(Contract):
    id: Identifier
    account_id: Identifier
    claim_id: Identifier
    amount: DecimalString


class AccountSubtotal(Contract):
    id: Identifier
    member_ids: Items


class AccountBatch(Contract):
    contract_version: Literal[1]
    accounts: Annotated[list[AccountDefinition], Field(min_length=1, max_length=1000)]
    postings: Annotated[list[AccountPosting], Field(max_length=10000)]
    claims: Annotated[list[AccountClaim], Field(max_length=1000)]
    reservations: Annotated[list[AccountReservation], Field(max_length=1000)]
    subtotals: Annotated[list[AccountSubtotal], Field(max_length=1000)]


class AccountResult(Contract):
    account_id: Identifier
    closing: DecimalString
    outstanding_reserved: DecimalString
    available: DecimalString
    posting_ids: Annotated[list[Identifier], Field(max_length=10000)]


class ClaimResult(Contract):
    claim_id: Identifier
    actual: DecimalString
    unmet: DecimalString


class AccountEvaluation(Contract):
    contract_version: Literal[1]
    accounts: Annotated[list[AccountResult], Field(max_length=1000)]
    claims: Annotated[list[ClaimResult], Field(max_length=1000)]
