"""Read-only, context-bound decision discovery and archived source projections."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext
from .packs import Definition, ArchivedSource, Digest
from .interview import InterviewQuery

class AtlasQuery(Contract):
    context: RevisionContext
    scope_id: Identifier
    search: Annotated[str, Field(max_length=256)] = ''
    domain_ref: Identifier | None = None
    branch_ref: Identifier | None = None
    source_ref: Identifier | None = None
    selection: Literal['any', 'selected', 'unanswered', 'proposed'] = 'any'
    modeling: Literal['numerical', 'procedural', 'qualitative', 'partial', 'unsupported'] | None = None
    evidence: Literal['unreviewed', 'hypothetical', 'supported', 'disputed'] | None = None
    issues: Literal['any', 'open', 'none'] = 'any'
    cursor: Identifier | None = None

class AtlasEntry(Contract):
    question: Definition
    options: Annotated[list[Definition], Field(max_length=100)]
    domain_refs: Annotated[list[Identifier], Field(max_length=12)]
    branch_refs: Annotated[list[Identifier], Field(max_length=200)]
    selected_id: Identifier | None
    archive: Literal['retained', 'current_catalog']
    issues: Annotated[list[str], Field(max_length=100)]
    interview: InterviewQuery | None

class AtlasLabel(Contract):
    id: Identifier
    label: Annotated[str, Field(max_length=131072)]

class AtlasPage(Contract):
    atlas_contract: Literal[1]
    query: AtlasQuery
    catalog_digest: Digest
    items: Annotated[list[AtlasEntry], Field(max_length=5)]
    total: Annotated[int, Field(ge=0)]
    next_cursor: Identifier | None
    domains: Annotated[list[AtlasLabel], Field(max_length=12)]
    branches: Annotated[list[AtlasLabel], Field(max_length=200)]
    sources: Annotated[list[AtlasLabel], Field(max_length=100)]

class AtlasSourceQuery(Contract):
    context: RevisionContext
    source_ref: Identifier
    offset: Annotated[int, Field(ge=0, le=131072)] = 0

class AtlasSourcePage(Contract):
    atlas_contract: Literal[1]
    query: AtlasSourceQuery
    source: ArchivedSource
    text: Annotated[str, Field(max_length=12000)]
    license_text: Annotated[str, Field(max_length=131072)]
    next_offset: Annotated[int, Field(ge=0, le=131072)] | None

atlas_adapter = TypeAdapter(AtlasQuery | AtlasPage | AtlasSourceQuery | AtlasSourcePage)
