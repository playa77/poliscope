"""Trusted-host experiment controller; no renderer or content authority."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .boundaries import BoundaryOutcome, CreateExperiment, ExperimentContext
from .timeline import TimelinePlan, Interval
from .world import SafeCount
from .evaluation import Digest
from .stochastic import Seed


class ExperimentManifest(Contract):
    contract_version: Literal[1] = 1
    checkpoint_interval: Interval
    origin: BoundaryOutcome | None = None
    realization_policy: Literal['opening', 'preserve', 'new_realization']


class StartExperiment(Contract):
    request: CreateExperiment
    checkpoint_interval: Interval

    @property
    def operation_id(self):
        return self.request.operation_id


class ForkExperiment(Contract):
    operation_id: Identifier
    source: BoundaryOutcome
    context: ExperimentContext
    plan: TimelinePlan
    checkpoint_interval: Interval
    realization_policy: Literal['preserve', 'new_realization']
    seed: Seed | None = None


class ExperimentControl(Contract):
    sequence: SafeCount
    state: Literal['ready', 'paused', 'cancelled']


class ControlExperiment(Contract):
    context: ExperimentContext
    operation_id: Identifier
    expected: ExperimentControl
    state: Literal['ready', 'paused', 'cancelled']


class AdvanceExperiment(Contract):
    expected: BoundaryOutcome
    operation_id: Identifier
    target_day: SafeCount
    max_boundaries: Annotated[int, Field(ge=1, le=1000)]


class ExperimentProgress(Contract):
    head: BoundaryOutcome
    completed: SafeCount
    status: Literal['complete', 'quota', 'paused', 'cancelled', 'running']


class Checkpoint(Contract):
    boundary: BoundaryOutcome
    state_digest: Digest
    evidence_digest: Digest


class ReplayExperiment(Contract):
    context: ExperimentContext
    sequence: SafeCount
    mode: Literal['recorded', 'verify']
    max_boundaries: Annotated[int, Field(ge=1, le=1000)] = 1000
