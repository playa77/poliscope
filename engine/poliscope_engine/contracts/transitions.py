"""Transition data v1. Only reviewed host implementations can produce effects."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .accounts import AccountClaim
from .allocations import AllocationRequest, AllocationChoice, AllocationEvaluation
from .dependencies import MechanismInstance
from .evaluation import Digest, AssumptionValue
from .mechanisms import Domain
from .policies import PolicyEvaluation
from .world import (PartitionValueDTO, DecimalString, SafeCount, References, WorldValue,
                    WorldVersions, EffectiveTime, EntityDTO, ScopeDTO, RelationshipDTO, Partition)

TransitionClass = Literal['construction', 'maintenance', 'education_skills', 'service_queue',
                         'population_health', 'ecological', 'institutional', 'response_capacity',
                         'resource_processing']


class AccountStateBinding(Contract):
    account_id: Identifier
    value_id: Identifier


class TransitionPlan(Contract):
    contract_version: Literal[1]
    opening: AllocationRequest | None
    account_bindings: Annotated[list[AccountStateBinding], Field(max_length=1000)]
    # Explicit host/player choices, never inferred from domain names or IDs.
    instance_order: Annotated[list[Identifier], Field(max_length=1000)]
    carry_priority: Literal['existing_first', 'new_first']
    operation_limit: Annotated[int, Field(ge=1, le=1000000)]
    # Explicit transition-only instances need no fictitious static implementation.
    instances: Annotated[list[MechanismInstance], Field(max_length=1000)] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_bindings(self):
        for keys in ([b.account_id for b in self.account_bindings],
                     [b.value_id for b in self.account_bindings], self.instance_order,
                     [i.id for i in self.instances]):
            if len(set(keys)) != len(keys):
                raise ValueError('duplicate_transition_identity')
        if self.opening is None and self.account_bindings:
            raise ValueError('transition_book_required')
        return self


class TransitionDemand(Contract):
    claim: AccountClaim
    choice: AllocationChoice

    @model_validator(mode='after')
    def matching_claim(self):
        if self.claim.id != self.choice.claim_id:
            raise ValueError('transition_claim_mismatch')
        return self


class TransitionClaimOwner(Contract):
    instance_id: Identifier
    claim_id: Identifier
    # Preserved terms for a retained pending claim. Only explicit, bound
    # refinements of unknown fields can evolve them; known rights/coefficients stay.
    choice: AllocationChoice
    original_requested: DecimalString
    fulfilled_prior: DecimalString


class PendingClaimRefinement(Contract):
    claim_id: Identifier
    expected_digest: Digest
    replacement: AllocationChoice

    @model_validator(mode='after')
    def matching_claim(self):
        if self.replacement.claim_id != self.claim_id:
            raise ValueError('pending_claim_mismatch')
        return self


class TransitionProposal(Contract):
    transition_class: TransitionClass
    status: Literal['ready', 'unresolved']
    reason: Identifier
    demands: Annotated[list[TransitionDemand], Field(max_length=100)]
    source_refs: References
    refinements: Annotated[list[PendingClaimRefinement], Field(max_length=100)] = Field(default_factory=list)


class TransitionFact(Contract):
    scope_id: Identifier
    condition_id: Identifier
    value: WorldValue


class TransitionReadView(Contract):
    """Physical data only; no player goals, notes, diagnostics or execution grants."""
    versions: WorldVersions
    effective_time: EffectiveTime
    entities: Annotated[list[EntityDTO], Field(max_length=1000)]
    scopes: Annotated[list[ScopeDTO], Field(max_length=1000)]
    relationships: Annotated[list[RelationshipDTO], Field(max_length=1000)]
    values: Annotated[list[PartitionValueDTO], Field(max_length=1000)]
    policies: PolicyEvaluation | None
    assumptions: Annotated[list[AssumptionValue], Field(max_length=1000)] | None
    read_partitions: Annotated[list[Partition], Field(max_length=6)]


class TransitionInvocation(Contract):
    inputs: TransitionReadView
    instance: MechanismInstance
    opening_day: SafeCount
    day: SafeCount
    conditions: Annotated[list[TransitionFact], Field(max_length=1000)]
    # Allocation is absent during proposal and contains solved actuals thereafter.
    allocation: AllocationEvaluation | None
    claim_ids: Annotated[list[Identifier], Field(max_length=1000)]
    pending_claims: Annotated[list[TransitionClaimOwner], Field(max_length=1000)]


class TransitionStep(Contract):
    instance_id: Identifier
    domain: Domain
    transition_class: TransitionClass | None
    status: Literal['applied', 'not_applicable', 'unresolved', 'coverage_gap']
    reason: Identifier
    claim_ids: Annotated[list[Identifier], Field(max_length=1000)]
    refined_claim_ids: Annotated[list[Identifier], Field(max_length=1000)] = Field(default_factory=list)
    changes: Annotated[list[PartitionValueDTO], Field(max_length=100)]
    source_refs: References
    assumption_refs: References


class AccountBalanceWitness(Contract):
    account_id: Identifier
    unit_id: Identifier
    scope_id: Identifier
    period_id: Identifier | None
    opening: DecimalString
    inflow: DecimalString
    outflow: DecimalString
    closing: DecimalString


class TransitionReceipt(Contract):
    transition_contract: Literal[1]
    reducer_id: Literal['atomic-transitions-v1']
    opening_digest: Digest
    plan_digest: Digest
    day: SafeCount
    coverage: Literal['complete', 'partial', 'unresolved']
    request: AllocationRequest | None
    allocation: AllocationEvaluation | None
    steps: Annotated[list[TransitionStep], Field(max_length=1000)]
    balances: Annotated[list[AccountBalanceWitness], Field(max_length=1000)]
    claim_owners: Annotated[list[TransitionClaimOwner], Field(max_length=1000)]
    receipt_digest: Digest


class ChunkProgress(Contract):
    day: SafeCount
    sequence: SafeCount
    boundary_digest: Digest
    completed: SafeCount
    status: Literal['confirmed', 'cancelled', 'quota', 'complete']
    coverage: Literal['not_assessed', 'complete', 'partial', 'unresolved']
