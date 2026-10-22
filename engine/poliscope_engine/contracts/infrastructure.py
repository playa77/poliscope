"""Host-declared facility reach over canonical locations and finite shared pools."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import References, DecimalString, ScopeKind
from .packs import Definition, Digest
from .accounts import AccountBatch
from .allocations import AllocationEvaluation

Availability = Literal['operating', 'planned', 'offline', 'retired', 'unknown']


class Facility(Contract):
    asset_id: Identifier
    location_id: Identifier
    location_relationship_id: Identifier
    account_id: Identifier
    availability: Availability
    source_refs: References


class InfrastructureLink(Contract):
    asset_id: Identifier
    from_id: Identifier
    to_id: Identifier
    relationship_id: Identifier
    account_id: Identifier
    availability: Availability
    source_refs: References


class FacilityDemand(Contract):
    claim_id: Identifier
    facility_asset_id: Identifier
    origin_id: Identifier
    # Ordered directed link asset IDs, empty only for local or disconnected use.
    path: Annotated[list[Identifier], Field(max_length=100)]
    access: Literal['allowed', 'denied', 'unknown']
    access_limit: DecimalString
    source_refs: References


class InfrastructureRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    batch: AccountBatch
    facilities: Annotated[list[Facility], Field(min_length=1, max_length=100)]
    links: Annotated[list[InfrastructureLink], Field(max_length=100)]
    demands: Annotated[list[FacilityDemand], Field(min_length=1, max_length=1000)]
    procedure: Literal['priority', 'all_or_nothing'] | None
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]
    mechanism_ref: Identifier
    source_refs: References


class FacilityReachResult(Contract):
    claim_id: Identifier
    claimant_id: Identifier
    facility_asset_id: Identifier
    account_id: Identifier
    origin_id: Identifier
    destination_id: Identifier
    path: Annotated[list[Identifier], Field(max_length=100)]
    scope_id: Identifier
    period_id: Identifier
    unit_id: Identifier
    status: Literal['resolved', 'unresolved']
    findings: Annotated[list[str], Field(max_length=10)]
    requested: DecimalString
    prior: DecimalString
    additional: DecimalString | None
    unmet: DecimalString | None


class InfrastructureEvaluation(Contract):
    contract_version: Literal[1]
    evidence_status: Literal['hypothetical']
    status: Literal['resolved', 'unresolved']
    request: InfrastructureRequest
    allocation: AllocationEvaluation
    results: Annotated[list[FacilityReachResult], Field(min_length=1, max_length=1000)]


class InfrastructureAlternative(Contract):
    definition: Definition
    claim_order: Annotated[list[Identifier], Field(max_length=1000)]


class InfrastructureInterview(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    question: Definition
    alternatives: Annotated[list[InfrastructureAlternative], Field(min_length=2, max_length=2)]
    selected_option_id: Identifier | None
    limits: Annotated[str, Field(min_length=1, max_length=2048)]


class InfrastructureEdit(Contract):
    baseline_digest: Digest
    scope_id: Identifier
    option_id: Identifier


class InfrastructureReport(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['infrastructure-exploration-v1']
    coverage_status: Literal['partial']
    evidence_status: Literal['hypothetical']
    baseline_digest: Digest
    evaluation: InfrastructureEvaluation


class InfrastructurePreview(Contract):
    contract_version: Literal[1]
    edit: InfrastructureEdit
    candidate_digest: Digest
    report: InfrastructureReport


class InfrastructureCoverageEntry(Contract):
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


class InfrastructureCoverage(Contract):
    contract_version: Literal[1]
    source_revision: Identifier
    source_archive_digest: Digest
    activation: Literal['not_activated']
    entries: Annotated[list[InfrastructureCoverageEntry], Field(min_length=1, max_length=100)]
