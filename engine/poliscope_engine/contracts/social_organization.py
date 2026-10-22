"""Host-declared aggregate arrangements and care; no demographic behavior model."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, QuantityValue, UnknownValue, DecimalString, Partition, ScopeKind
from .economy import EconomyRequest, EconomyReport
from .packs import Definition, Digest


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


class CareAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class CareInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[CareAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class CareEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class CareReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['care-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: CareEvaluation


class CarePreview(Contract):
    contract_version: Literal[1]
    edit: CareEdit
    candidate_digest: Digest
    report: CareReport


class CareCoverageEntry(Contract):
    source_id: Identifier
    classification: Literal['catalog', 'provenance']
    title: Annotated[str, Field(min_length=1, max_length=2048)]
    documents: Annotated[list[Identifier], Field(max_length=100)]
    option_refs: Annotated[list[Identifier], Field(max_length=100)]
    effect: Annotated[str, Field(min_length=1, max_length=2048)]
    status: Literal['partial', 'qualitative', 'unsupported']
    evidence_status: Literal['hypothetical', 'unreviewed']
    supported_scope_kinds: Annotated[list[ScopeKind], Field(max_length=6)]
    static_available: bool
    transition_available: Literal[False]
    implementation_refs: Annotated[list[Identifier], Field(max_length=10)]
    next_research_task: Annotated[str, Field(min_length=1, max_length=2048)]


class CareCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[CareCoverageEntry], Field(min_length=1, max_length=100)]
