"""Revision service v1; internal trusted-host contracts, not renderer IPC grants."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import (WorldVersions, RevisionContext, EntityDTO, ScopeDTO,
                    PartitionValueDTO, RelationshipDTO, Partition)
from .evaluation import EvaluationDesign, AssumptionValue, Digest, NodeObservation
from .measurements import IndicatorDefinition, PlayerGoal, EvidenceReference, MeasurementReport

Rows = Field(max_length=1000)


class OwnerDTO(Contract):
    entity_id: Identifier
    property_id: Identifier
    partition: Partition
    writer_id: Identifier


class PopulationDTO(Contract):
    entity_id: Identifier
    role: Literal['fixed_input', 'dynamic_state', 'solved_capacity_bound']


class RevisionInputs(Contract):
    versions: WorldVersions
    entities: Annotated[list[EntityDTO], Rows]
    scopes: Annotated[list[ScopeDTO], Rows]
    values: Annotated[list[PartitionValueDTO], Rows]
    owners: Annotated[list[OwnerDTO], Rows]
    populations: Annotated[list[PopulationDTO], Rows]
    relationships: Annotated[list[RelationshipDTO], Rows]
    design: EvaluationDesign
    assumptions: Annotated[list[AssumptionValue], Rows]
    measurements: Annotated[list[IndicatorDefinition], Rows]
    goals: Annotated[list[PlayerGoal], Rows]
    references: Annotated[list[EvidenceReference], Rows]


class SetValues(Contract):
    kind: Literal['set_values']
    writer_id: Identifier
    partition: Partition
    values: Annotated[list[PartitionValueDTO], Rows]


class ReplaceInputs(Contract):
    # Complete typed structure/design edit, including explicit proposal promotion.
    kind: Literal['replace_inputs']
    inputs: RevisionInputs


Change = Annotated[SetValues | ReplaceInputs, Field(discriminator='kind')]


class Alternative(Contract):
    id: Identifier
    # Approved design content only. Private explanation stays in classified refs.
    changes: Annotated[list[Change], Field(max_length=100)]


class PrivateReference(Contract):
    id: Identifier
    visibility: Literal['private']
    status: Literal['available', 'redacted', 'deleted', 'unavailable']


class DecisionArchive(Contract):
    alternatives: Annotated[list[Alternative], Field(max_length=100)]
    selected_id: Identifier | None
    rationale_ref: PrivateReference | None


class PreviewRequest(Contract):
    revision_contract: Literal[1]
    context: RevisionContext
    changes: Annotated[list[Change], Field(min_length=1, max_length=100)]
    decision: DecisionArchive


class ObservationDifference(Contract):
    node: Annotated[list[Identifier], Field(min_length=1, max_length=10)]
    before: NodeObservation | None
    after: NodeObservation | None


class Candidate(Contract):
    revision_contract: Literal[1]
    request: PreviewRequest
    candidate_digest: Digest
    inputs_digest: Digest
    evidence_digest: Digest
    affected_scope_ids: Annotated[list[Identifier], Rows]
    changed_value_ids: Annotated[list[Identifier], Rows]
    report: MeasurementReport
    differences: Annotated[list[ObservationDifference], Field(max_length=50000)]


class ApplyRequest(Contract):
    revision_contract: Literal[1]
    operation_id: Identifier
    preview: PreviewRequest
    candidate_digest: Digest


class MutationOutcome(Contract):
    revision_contract: Literal[1]
    context: RevisionContext
    branch_sequence: Annotated[int, Field(ge=0, le=9007199254740991)]


class CreateRequest(Contract):
    revision_contract: Literal[1]
    data_store_id: Identifier
    civilization_id: Identifier
    branch_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=256)]
    operation_id: Identifier
    inputs: RevisionInputs


class BranchRequest(Contract):
    revision_contract: Literal[1]
    operation_id: Identifier
    context: RevisionContext
    expected_sequence: Annotated[int, Field(ge=0, le=9007199254740991)]
    action: Literal['undo', 'redo', 'fork', 'rename']
    new_branch_id: Identifier | None
    name: Annotated[str, Field(min_length=1, max_length=256)] | None


class BranchState(Contract):
    revision_contract: Literal[1]
    context: RevisionContext
    name: Annotated[str, Field(min_length=1, max_length=256)]
    sequence: Annotated[int, Field(ge=0, le=9007199254740991)]
    redo: Annotated[list[Identifier], Rows]
    forked_from: RevisionContext | None


class RevisionRecord(Contract):
    revision_contract: Literal[1]
    context: RevisionContext
    parent_id: Identifier | None
    inputs: RevisionInputs
    decision: DecisionArchive
    evidence_digest: Digest
    applied_preview: PreviewRequest | None


class HistoryQuery(Contract):
    context: RevisionContext
    cursor: Identifier | None
    limit: Annotated[int, Field(ge=1, le=100)]


class RevisionSummary(Contract):
    context: RevisionContext
    parent_id: Identifier | None
    evidence_digest: Digest


class HistoryPage(Contract):
    items: Annotated[list[RevisionSummary], Field(max_length=100)]
    next_cursor: Identifier | None
