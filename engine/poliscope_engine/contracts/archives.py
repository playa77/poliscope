"""Portable archive projection v1. Imported data never grants execution authority."""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .evaluation import Digest, NodeObservation, TraceEdge
from .measurements import AcceptedEvidence
from .revisions import RevisionInputs, Alternative
from .world import SafeCount
from .timeline import TimelinePlan, BoundaryChanges
from .boundaries import BoundaryCondition
from .transitions import TransitionPlan, TransitionStep, AccountBalanceWitness, TransitionClaimOwner
from .allocations import AllocationRequest, AllocationEvaluation
from .stochastic import RealizedDraw

class ArchiveOptions(Contract):
    include_private_notes: bool = False
    include_private_rationale: bool = False
    include_transcripts: bool = False
    include_attachments: bool = False
    evidence: Literal['complete', 'reduced'] = 'complete'

class ArchiveEvidence(Contract):
    # Full data-only accepted closure with projected identities after redaction.
    identity: Literal['privacy_projection'] = 'privacy_projection'
    saved: AcceptedEvidence

class ArchiveRevision(Contract):
    kind: Literal['revision'] = 'revision'
    id: Identifier
    civilization_id: Identifier
    branch_id: Identifier
    parent_id: Identifier | None
    inputs: RevisionInputs
    alternatives: Annotated[list[Alternative], Field(max_length=100)]
    selected_id: Identifier | None
    evidence: ArchiveEvidence | None

class ArchiveBranch(Contract):
    kind: Literal['branch'] = 'branch'
    civilization_id: Identifier
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=256)]
    revision_id: Identifier
    redo: Annotated[list[Identifier], Field(max_length=1000)]
    fork_branch_id: Identifier | None
    fork_revision_id: Identifier | None

class ArchiveTransition(Contract):
    transition_contract: Literal[1]
    reducer_id: Literal['atomic-transitions-v1']
    coverage: Literal['complete','partial','unresolved']
    request: AllocationRequest | None
    allocation: AllocationEvaluation | None
    claim_owners: Annotated[list[TransitionClaimOwner], Field(max_length=1000)]
    draws: Annotated[list[RealizedDraw], Field(max_length=1000)]
    steps: Annotated[list[TransitionStep], Field(max_length=1000)]
    balances: Annotated[list[AccountBalanceWitness], Field(max_length=1000)]

class ArchiveBoundary(Contract):
    sequence: SafeCount
    day: SafeCount
    inputs: RevisionInputs
    conditions: Annotated[list[BoundaryCondition], Field(max_length=1000)]
    changes: BoundaryChanges | None
    transition: ArchiveTransition | None
    evidence: ArchiveEvidence | None

class ArchiveExperiment(Contract):
    kind: Literal['experiment'] = 'experiment'
    civilization_id: Identifier
    id: Identifier
    plan: TimelinePlan
    transition_plan: TransitionPlan | None
    origin_id: Identifier | None
    origin_sequence: SafeCount | None
    checkpoint_sequences: Annotated[list[SafeCount], Field(max_length=10000)]
    control: Literal['ready', 'paused', 'cancelled']
    boundaries: Annotated[list[ArchiveBoundary], Field(min_length=1, max_length=10000)]

class ArchivePrivate(Contract):
    kind: Literal['private'] = 'private'
    category: Literal['note', 'rationale', 'transcript', 'attachment']
    revision_id: Identifier
    status: Literal['available', 'deleted', 'unavailable']
    text: Annotated[str, Field(max_length=30000)] | None

ArchiveItem = Union[ArchiveRevision, ArchiveBranch, ArchiveExperiment, ArchivePrivate]
archive_item_adapter = TypeAdapter(ArchiveItem)

class ArchiveEntry(Contract):
    path: Annotated[str, Field(pattern=r'^data/[0-9]{6}\.json$')]
    size: Annotated[int, Field(ge=1, le=67108864)]
    sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]

class ArchiveManifest(Contract):
    format: Literal['poliscope-portable']
    version: Literal[1]
    data_schema: Literal[1]
    options: ArchiveOptions
    entries: Annotated[list[ArchiveEntry], Field(min_length=1, max_length=10000)]
    redactions: Annotated[list[Literal['private_notes', 'private_rationale', 'transcripts', 'attachments', 'private_references', 'private_identifiers']], Field(max_length=6)]
    omitted_evidence: Annotated[list[Identifier], Field(max_length=10000)]
    projection_digest: Digest

class ArchiveRequest(Contract):
    action: Literal['export', 'import', 'list', 'read']
    options: ArchiveOptions = Field(default_factory=ArchiveOptions)
    archive_id: Digest | None = None
    offset: Annotated[int, Field(ge=0, le=10000)] = 0
    detail_offset: Annotated[int, Field(ge=0, le=1000000)] = 0

class ArchiveSummary(Contract):
    id: Digest
    revisions: SafeCount
    branches: SafeCount
    experiments: SafeCount
    evidence: Literal['complete', 'reduced']
    mode: Literal['stored_historical'] = 'stored_historical'
    execution: Literal['unavailable', 'compatible_requires_explicit_migration']
    redactions: Annotated[list[str], Field(max_length=6)]

class ArchiveDisplay(Contract):
    label: Annotated[str, Field(max_length=512)]
    detail: Annotated[str, Field(max_length=8192)]

class ArchiveReply(Contract):
    status: Literal['complete', 'cancelled']
    summaries: Annotated[list[ArchiveSummary], Field(max_length=1000)]
    heading: Annotated[str, Field(max_length=512)] = ''
    rows: Annotated[list[ArchiveDisplay], Field(max_length=25)] = Field(default_factory=list)
    next_detail_offset: SafeCount | None = None
    next_offset: SafeCount | None = None


# Nested JSON snapshots are schemas too; data-only is not permission for arbitrary
# dictionaries, formulas, import paths, callbacks or executable metadata.
from .mechanisms import MechanismDefinition
from .expressions import ExpressionGraph
from .world import DecimalString

class ArchiveImplementation(Contract):
    id: Identifier
    version: Identifier
    phase: Literal['static','transition','composition']

class ArchiveReview(Contract):
    declaration_digest: Identifier
    model_id: Identifier
    model_version: Identifier
    evidence_review_ref: Identifier
    independent_fixture_review_ref: Identifier
    graph_digest: Identifier | None

class ArchiveUnit(Contract):
    id: Identifier
    dimension: Annotated[list[tuple[Identifier, Annotated[int, Field(ge=-1000,le=1000)]]], Field(max_length=100)]
    kind: Literal['stock','flow','capacity','count','time','entitlement','money','indicator']
    scale: DecimalString

class ArchiveTime(Contract):
    id: Identifier
    seconds: DecimalString

class ArchiveModelSnapshot(Contract):
    identity: Annotated[list[Identifier],Field(min_length=2,max_length=2)]
    evaluator: Identifier
    numeric: Identifier
    python: Annotated[list[SafeCount],Field(min_length=3,max_length=3)]
    decimal_library: Identifier
    pydantic: Identifier
    definitions: Annotated[list[MechanismDefinition],Field(max_length=1000)]
    graphs: Annotated[list[ExpressionGraph],Field(max_length=1000)]
    reviews: Annotated[list[ArchiveReview],Field(max_length=10000)]
    implementations: Annotated[list[ArchiveImplementation],Field(max_length=10000)]
    units: Annotated[list[ArchiveUnit],Field(max_length=10000)]
    times: Annotated[list[ArchiveTime],Field(max_length=10000)]
    source_ids: Annotated[list[Identifier],Field(max_length=10000)]
    assumption_ids: Annotated[list[Identifier],Field(max_length=10000)]
    fixture_ids: Annotated[list[tuple[Identifier, Identifier]],Field(max_length=10000)]

archive_adapter = TypeAdapter(Union[ArchiveOptions, ArchiveManifest, ArchiveRequest, ArchiveReply, ArchiveModelSnapshot, ArchiveRevision, ArchiveBranch, ArchiveExperiment, ArchivePrivate])
