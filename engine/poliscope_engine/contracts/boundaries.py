"""Trusted-host confirmed-boundary storage v1, not renderer mutation authority."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .evaluation import Digest
from .measurements import AcceptedEvidence
from .revisions import RevisionInputs
from .timeline import TimelinePlan, BoundaryChanges, ScheduledBoundary
from .world import SafeCount, WorldValue


class ExperimentContext(Contract):
    data_store_id: Identifier
    civilization_id: Identifier
    experiment_id: Identifier


class BoundaryCondition(Contract):
    scope_id: Identifier
    condition_id: Identifier
    value: WorldValue


class BoundaryState(Contract):
    inputs: RevisionInputs
    conditions: Annotated[list[BoundaryCondition], Field(max_length=1000)]

    @model_validator(mode='after')
    def unique_conditions(self):
        keys = [(c.scope_id, c.condition_id) for c in self.conditions]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate_boundary_condition')
        return self


class CreateExperiment(Contract):
    boundary_contract: Literal[1]
    context: ExperimentContext
    operation_id: Identifier
    plan: TimelinePlan
    conditions: Annotated[list[BoundaryCondition], Field(max_length=1000)]


class BoundaryOutcome(Contract):
    boundary_contract: Literal[1]
    context: ExperimentContext
    sequence: SafeCount
    day: SafeCount
    boundary_digest: Digest


class BoundaryCandidate(Contract):
    # The transition host owns dynamic conservation, capacity and model checks.
    inputs: RevisionInputs
    evidence: AcceptedEvidence


class ConfirmBoundary(Contract):
    boundary_contract: Literal[1]
    expected: BoundaryOutcome
    operation_id: Identifier
    candidate: BoundaryCandidate


class BoundaryRecord(Contract):
    boundary_contract: Literal[1]
    context: ExperimentContext
    sequence: SafeCount
    day: SafeCount
    parent_digest: Digest | None
    plan_digest: Digest
    state_digest: Digest
    evidence_digest: Digest
    validator_id: Identifier
    due: ScheduledBoundary | None
    changes: BoundaryChanges | None
    boundary_digest: Digest


class ConfirmedBoundary(Contract):
    record: BoundaryRecord
    state: BoundaryState
    evidence: AcceptedEvidence


class ExperimentRecord(Contract):
    boundary_contract: Literal[1]
    context: ExperimentContext
    plan: TimelinePlan
    plan_digest: Digest
    opening_digest: Digest


class BoundaryValidation(Contract):
    """Detached inputs to a trusted WP-034 validator; not a content callback."""
    opening: ConfirmedBoundary
    due: ScheduledBoundary
    changes: BoundaryChanges
    closing: BoundaryState
    evidence: AcceptedEvidence
