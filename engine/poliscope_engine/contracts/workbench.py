"""Bounded evidence inspection and player-authorized revision edits."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, WorldVersions, EffectiveTime, WorldValue
from .evaluation import AssumptionValue, Digest
from .evidence import AssumptionRef
from .measurements import PlayerGoal, GoalObservation, EvidenceReference
from .annotations import NoteReference
from .revisions import PrivateReference
from .interview import InterviewApply, InterviewCommit

Text = Annotated[str, Field(min_length=1, max_length=2048)]
NoteKind = Literal['inquiry', 'expectation', 'observation', 'model_gap', 'proposal']

class WorkbenchQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    collection: Literal['assumptions', 'goals', 'notes', 'references', 'models', 'rationale']
    cursor: Identifier | None = None

class WorkbenchRow(Contract):
    id: Identifier
    model_id: Identifier | None = None
    model_version: Identifier | None = None
    assumption: AssumptionValue | None = None
    definition: AssumptionRef | None = None
    editable: bool = False
    goal: PlayerGoal | None = None
    observation: GoalObservation | None = None
    reference: EvidenceReference | None = None
    rationale: PrivateReference | None = None
    note: NoteReference | None = None
    note_kind: NoteKind | None = None
    text: Text | None = None
    status: Literal['available', 'deleted', 'unavailable'] | None = None

class WorkbenchPage(Contract):
    workbench_contract: Literal[1]
    query: WorkbenchQuery
    versions: WorldVersions
    effective_time: EffectiveTime
    physical_output_digest: Digest | None
    items: Annotated[list[WorkbenchRow], Field(max_length=25)]
    next_cursor: Identifier | None

class AssumptionEdit(Contract):
    kind: Literal['assumption']
    id: Identifier
    value: WorldValue

class GoalEdit(Contract):
    kind: Literal['goal']
    goal: PlayerGoal
    remove: bool = False

class NoteEdit(Contract):
    kind: Literal['note']
    id: Identifier | None = None
    note_kind: NoteKind
    text: Text

class WorkbenchEdit(Contract):
    context: RevisionContext
    scope_id: Identifier
    change: Annotated[AssumptionEdit | GoalEdit | NoteEdit, Field(discriminator='kind')]

class WorkbenchPreview(Contract):
    workbench_contract: Literal[1]
    edit: WorkbenchEdit
    candidate_digest: Digest
    physical_before: Digest | None
    physical_after: Digest
    changed_observations: Annotated[int, Field(ge=0)]
    disclosure: Annotated[str, Field(max_length=4096)]

class DeleteNote(Contract):
    context: RevisionContext
    scope_id: Identifier
    id: Identifier

class DeleteNoteReply(Contract):
    workbench_contract: Literal[1]
    query: DeleteNote
    status: Literal['deleted']

workbench_adapter = TypeAdapter(WorkbenchQuery | WorkbenchPage | WorkbenchEdit | WorkbenchPreview | DeleteNote | DeleteNoteReply | InterviewApply | InterviewCommit)
