"""Pure static evaluation v1. Host-selected rules are not imported authority."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import WorldValue, EffectiveTime
from .dependencies import PortRef
from .solvers import ExecutionRequest, NodeKey
from .policies import PolicyBinding, ResolutionRule, PolicyEvaluation
from .evidence import CoverageStatus
from .accounts import AccountEvaluation
from .packs import Identity

Items = Field(max_length=1000)
Digest = Annotated[str, Field(pattern=r'^sha256:[0-9a-f]{64}$')]


class AssumptionValue(Contract):
    id: Identifier
    value: WorldValue


class ValueInput(Contract):
    consumer: PortRef
    value_id: Identifier


class PolicyInput(Contract):
    consumer: PortRef
    entity_id: Identifier
    parameter_id: Identifier
    # Bounds are constraints, never silently substituted for a point value.
    selection: Literal['value', 'floor', 'ceiling']


class ConditionRule(Contract):
    identity: Identity
    instance_id: Identifier
    precondition_id: Identifier
    input_id: Identifier
    operation: Literal['eq', 'ne', 'lt', 'le', 'gt', 'ge', 'known']
    value: WorldValue | None


class Realization(Contract):
    identity: Identity
    seed: Identifier | None
    # Semantic event order retained. Stable IDs, not mutable global positions.
    event_ids: Annotated[list[Identifier], Items]
    values: Annotated[list[AssumptionValue], Items]


class EvaluationDesign(Contract):
    contract_version: Literal[1]
    effective_time: EffectiveTime
    execution: ExecutionRequest
    policies: Annotated[list[PolicyBinding], Field(max_length=100)]
    policy_rules: Annotated[list[ResolutionRule], Field(max_length=100)]
    policy_inputs: Annotated[list[PolicyInput], Items]
    world_inputs: Annotated[list[ValueInput], Items]
    assumption_inputs: Annotated[list[ValueInput], Items]
    realization_inputs: Annotated[list[ValueInput], Items]
    conditions: Annotated[list[ConditionRule], Items]
    realization: Realization


class NodeObservation(Contract):
    node: NodeKey
    scope_id: Identifier | None
    entity_id: Identifier | None
    status: CoverageStatus
    reason: Annotated[str, Field(min_length=1, max_length=4096)]
    value: WorldValue | None
    source_refs: Annotated[list[Identifier], Field(max_length=100)]
    assumption_refs: Annotated[list[Identifier], Field(max_length=100)]


class TraceEdge(Contract):
    source: NodeKey
    target: NodeKey


class EvaluationIdentities(Contract):
    canonical_version: Literal[1]
    input_digest: Digest
    model_digest: Digest
    realization_digest: Digest
    cache_key: Digest
    output_digest: Digest


class EvaluationResult(Contract):
    contract_version: Literal[1]
    effective_time: EffectiveTime
    identities: EvaluationIdentities
    outcome: Literal['complete', 'incomplete', 'insufficient', 'unresolved']
    observations: Annotated[list[NodeObservation], Field(max_length=25000)]
    policies: PolicyEvaluation
    trace_edges: Annotated[list[TraceEdge], Field(max_length=50000)]
    accounts: AccountEvaluation | None
    # Full snapshots retain scope/time/claim/provenance alongside distributions.
    final_batch_json: str | None
    input_json: str
    model_json: str
    realization_json: str
