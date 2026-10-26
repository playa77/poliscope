"""Bounded interview projections; renderer never supplies engine changes or paths."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, PartitionValueDTO
from .packs import Definition
from .evaluation import Digest
from .workspace import WorkspaceState

Text = Annotated[str, Field(min_length=1, max_length=1024)]

class InterviewQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    domain_id: Identifier
    question_id: Identifier | None = None

class InterviewOption(Contract):
    definition: Definition
    label: Text
    benefit: Text
    cost: Text
    mechanism: Text

class InterviewQuestion(Contract):
    interview_contract: Literal[1]
    query: InterviewQuery
    definition: Definition
    options: Annotated[list[InterviewOption], Field(min_length=1, max_length=100)]
    clarification: Text
    dependencies: Annotated[list[Text], Field(max_length=12)]
    conditions: Annotated[list[PartitionValueDTO], Field(max_length=2)]
    current_commitment: Annotated[str, Field(max_length=131072)] | None

class ProposalPromotion(Contract):
    source_request_id: Identifier
    manifest_digest: Digest
    coverage: Literal['unverified qualitative assistant excerpt'] = 'unverified qualitative assistant excerpt'

class InterviewEdit(Contract):
    promotion: ProposalPromotion | None = None
    query: InterviewQuery
    choice_id: Identifier
    proposal: Annotated[str, Field(max_length=1024)] | None
    # Only the resource template permits exact starting-condition edits.
    population: Annotated[str, Field(min_length=1, max_length=256)] | None
    land_area: Annotated[str, Field(min_length=1, max_length=256)] | None
    rationale: Annotated[str, Field(max_length=2048)]

class InterviewPreview(Contract):
    interview_contract: Literal[1]
    query: InterviewQuery
    candidate_digest: Digest
    affected_scope_ids: Annotated[list[Identifier], Field(max_length=1000)]
    changed_value_ids: Annotated[list[Identifier], Field(max_length=1000)]
    coverage: Text
    findings: Annotated[list[Text], Field(max_length=100)]
    dependencies: Annotated[list[Text], Field(max_length=12)]
    accounts: Annotated[list[Identifier], Field(max_length=100)]
    alternatives: Annotated[list[Identifier], Field(min_length=1, max_length=101)]
    selected_id: Identifier
    before: Annotated[list[PartitionValueDTO], Field(max_length=2)]
    after: Annotated[list[PartitionValueDTO], Field(max_length=2)]

class InterviewApply(Contract):
    candidate_digest: Digest

class InterviewCommit(Contract):
    interview_contract: Literal[1]
    status: Literal['applied', 'stale']
    state: WorkspaceState

interview_adapter = TypeAdapter(InterviewQuery | InterviewQuestion | InterviewEdit | InterviewPreview | InterviewApply | InterviewCommit)
