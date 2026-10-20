"""Release metadata is data, never a grant of executable authority."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .packs import Digest, GameID, Path, Identity, Definition
from .evidence import Text

Rows = Field(max_length=2000)


class Artifact(Contract):
    path: Path
    digest: Digest


class Catalog(Contract):
    artifact: Path
    pack_digest: Digest
    role: Literal['reference', 'authored']


class ReviewFixture(Contract):
    identity: Identity
    artifact: Path
    digest: Digest
    purpose: Literal['positive', 'invalid_input', 'missing_input', 'conservation', 'boundedness']


class ModelReview(Contract):
    id: GameID
    candidate_refs: Annotated[list[GameID], Rows]
    mechanism_ref: GameID | None
    mechanism_version: Identifier | None
    mechanism_artifact: Path | None
    declaration_digest: Digest | None
    graph_digest: Digest | None
    model: Identity | None
    disposition: Literal['blocked', 'hypothetical', 'approved']
    operational_definition: Text
    formula_or_procedure: Text
    denominator_time_scope: Text
    basis: Literal['empirical', 'hypothetical', 'unresolved']
    uncertainty: Text
    evidence_refs: Annotated[list[GameID], Rows]
    evidence_digests: Annotated[dict[GameID, Digest], Field(max_length=2000)]
    fixtures: Annotated[list[ReviewFixture], Field(max_length=100)]
    invariants: Text
    validity_limits: Text
    unsupported_extrapolation: Text
    review_notes: Text


class InterviewTemplate(Contract):
    domain_ref: GameID
    question: Definition
    options: Annotated[list[Definition], Field(min_length=3, max_length=4)]
    labels: Annotated[list[Text], Field(min_length=3, max_length=4)]
    mechanisms: Annotated[list[Text], Field(min_length=3, max_length=4)]
    benefits: Annotated[list[Text], Field(min_length=3, max_length=4)]
    costs: Annotated[list[Text], Field(min_length=3, max_length=4)]
    coverage: Text


class Setup(Contract):
    id: Identifier
    name: Text
    kind: Literal['neutral', 'synthetic', 'historical']
    description: Text
    population: str | None
    land_area: str | None
    selected_option_refs: Annotated[list[GameID], Rows]
    goals: Annotated[list[GameID], Field(max_length=0)]
    source_refs: Annotated[list[GameID], Rows]
    limitations: Text


class Inquiry(Contract):
    id: GameID
    domain_refs: Annotated[list[GameID], Field(min_length=1, max_length=12)]
    prompt: Text


class Coverage(Contract):
    branch_ref: GameID
    source_status: Literal['map_only', 'source_design_only']
    model_status: Literal['unsupported']
    reason: Text


class ContentRelease(Contract):
    format_version: Literal[1]
    id: GameID
    version: Identifier
    artifacts: Annotated[list[Artifact], Field(max_length=500)]
    catalogs: Annotated[list[Catalog], Field(min_length=1, max_length=100)]
    reviews: Annotated[list[ModelReview], Field(max_length=500)]
    activated_review_refs: Annotated[list[GameID], Field(max_length=500)]
    templates: Annotated[list[InterviewTemplate], Field(max_length=100)]
    setups: Annotated[list[Setup], Field(min_length=1, max_length=100)]
    inquiries: Annotated[list[Inquiry], Field(max_length=100)]
    coverage: Annotated[list[Coverage], Rows]
