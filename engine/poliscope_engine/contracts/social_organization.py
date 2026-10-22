"""Host-declared aggregate arrangements and care; no demographic behavior model."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, QuantityValue, UnknownValue, DecimalString, Partition
from .economy import EconomyRequest, EconomyReport


class SocialArrangement(Contract):
    id: Identifier
    scope_id: Identifier
    # Population comes from direct canonical graph members, never this record.
    source_refs: References


class CareObligation(Contract):
    id: Identifier
    arrangement_id: Identifier
    beneficiary_id: Identifier
    provider_id: Identifier
    authority_id: Identifier | None
    obligation_ref: Identifier
    claim_id: Identifier
    source_refs: References


class CareRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    population_property_id: Identifier
    population_partition: Partition
    arrangements: Annotated[list[SocialArrangement], Field(min_length=1, max_length=100)]
    obligations: Annotated[list[CareObligation], Field(min_length=1, max_length=100)]
    work: EconomyRequest
    source_refs: References


class ArrangementPopulation(Contract):
    arrangement_id: Identifier
    population: QuantityValue | UnknownValue


class CareResult(Contract):
    obligation_id: Identifier
    beneficiary_id: Identifier
    provider_id: Identifier
    claim_id: Identifier
    status: Literal['resolved', 'unresolved']
    requested: DecimalString
    unit_id: Identifier
    period_id: Identifier
    actual_before: DecimalString
    # Additional work in this invocation; prior fulfilled work is above.
    actual: DecimalString | None
    unmet: DecimalString | None
    posting_ids: Annotated[list[Identifier], Field(max_length=10000)]


class CareEvaluation(Contract):
    contract_version: Literal[1]
    status: Literal['resolved', 'unresolved']
    evidence_status: Literal['hypothetical']
    request: CareRequest
    population: QuantityValue | UnknownValue
    arrangements: Annotated[list[ArrangementPopulation], Field(min_length=1, max_length=100)]
    results: Annotated[list[CareResult], Field(min_length=1, max_length=100)]
    work: EconomyReport
