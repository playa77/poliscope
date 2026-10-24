"""Private static integration: explicit prerequisites, never service delivery."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .mechanisms import Domain
from .world import References
from .domains import SharedReference
from .provisioning_economy import ProvisioningEconomyRequest
from .economy import EconomyRequest
from .governance import GovernanceRequest
from .law_conflict import AdjudicationRequest
from .social_organization import CareRequest
from .knowledge_culture import EducationRequest
from .health import HealthRequest
from .infrastructure import InfrastructureRequest
from .communication import CommunicationRequest
from .environment import EnvironmentRequest
from .meaning_identity import ParticipationRequest
from .security_risk import ContinuityRequest

from .provisioning import ProvisioningEvaluation
from .economy import EconomyEvaluation
from .governance import GovernanceEvaluation
from .law_conflict import AdjudicationEvaluation
from .social_organization import CareEvaluation
from .knowledge_culture import EducationEvaluation
from .health import HealthEvaluation
from .infrastructure import InfrastructureEvaluation
from .communication import CommunicationEvaluation
from .environment import EnvironmentEvaluation
from .meaning_identity import ParticipationEvaluation
from .security_risk import ContinuityEvaluation
from .accounts import AccountBatch
from .packs import Digest


class StaticRequirement(Contract):
    id: Identifier
    source: Domain
    target: Domain
    source_result_id: Identifier
    target_result_id: Identifier
    # Explicit host-authored condition. It grants neither access nor authority.
    obligation_ref: Identifier
    shared_references: Annotated[list[SharedReference], Field(min_length=1, max_length=20)]
    source_refs: References


class StaticSystemRequest(Contract):
    contract_version: Literal[1]
    scope_id: Identifier
    period_id: Identifier
    provisioning: ProvisioningEconomyRequest | None = None
    economy: EconomyRequest | None = None
    governance: GovernanceRequest | None = None
    law_conflict: AdjudicationRequest | None = None
    social_organization: CareRequest | None = None
    knowledge_culture: EducationRequest | None = None
    health: HealthRequest | None = None
    infrastructure: InfrastructureRequest | None = None
    communication: CommunicationRequest | None = None
    environment: EnvironmentRequest | None = None
    meaning_identity: ParticipationRequest | None = None
    security_risk: ContinuityRequest | None = None
    requirements: Annotated[list[StaticRequirement], Field(min_length=1, max_length=100)]
    missing_effects: Annotated[list[Annotated[str, Field(min_length=1, max_length=4096)]], Field(min_length=1, max_length=100)]
    source_refs: References

    @model_validator(mode='after')
    def topology(self):
        from typing import get_args
        domains = {d for d in get_args(Domain) if getattr(self, d) is not None}
        if len(domains) < 2:
            raise ValueError('static_system_requires_counterparts')
        if len({r.id for r in self.requirements}) != len(self.requirements):
            raise ValueError('duplicate_static_requirement')
        if any(r.source == r.target or not {r.source, r.target} <= domains for r in self.requirements):
            raise ValueError('invalid_static_requirement_topology')
        return self


Readiness = Literal['ready', 'blocked', 'unresolved']
DomainEvaluation = (ProvisioningEvaluation | EconomyEvaluation | GovernanceEvaluation |
    AdjudicationEvaluation | CareEvaluation | EducationEvaluation | HealthEvaluation |
    InfrastructureEvaluation | CommunicationEvaluation | EnvironmentEvaluation |
    ParticipationEvaluation | ContinuityEvaluation)


class StaticRequirementResult(StaticRequirement):
    status: Readiness


class SnapshotPostingOrigin(Contract):
    id: Identifier
    original_id: Identifier
    account_ids: Annotated[list[Identifier], Field(min_length=1, max_length=1000)]


class StaticSystemEvaluation(Contract):
    contract_version: Literal[1]
    adapter_version: Literal['static-system-v1']
    baseline_digest: Digest
    scope_id: Identifier
    period_id: Identifier
    evidence_status: Literal['hypothetical']
    coverage_status: Literal['partial']
    status: Literal['resolved', 'unresolved']
    local_readiness: dict[Domain, dict[Identifier, Readiness]]
    integrated_readiness: dict[Domain, dict[Identifier, Readiness]]
    requirements: Annotated[list[StaticRequirementResult], Field(max_length=100)]
    evaluations: dict[Domain, DomainEvaluation]
    candidate_batch: AccountBatch | None
    posting_origins: Annotated[list[SnapshotPostingOrigin], Field(max_length=10000)]
    missing_effects: Annotated[list[Annotated[str, Field(min_length=1, max_length=4096)]], Field(min_length=1, max_length=100)]
    source_refs: References
