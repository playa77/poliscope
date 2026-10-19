"""Workspace v1: bounded player-facing projections, no paths or executable data."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext, WorldVersions, EffectiveTime, WorldPageResult
from .revisions import BranchState

class CreateOptions(Contract):
    name: Annotated[str, Field(min_length=1, max_length=256)]
    setup: Literal['blank', 'reference:small-settlement']
    scope_name: Annotated[str, Field(min_length=1, max_length=256)]
    population: Annotated[str, Field(min_length=1, max_length=256)] | None
    land_area: Annotated[str, Field(min_length=1, max_length=256)] | None

class DomainEntry(Contract):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=256)]
    status: Literal['unanswered']

class SetupEntry(Contract):
    id: Literal['blank', 'reference:small-settlement']
    name: Annotated[str, Field(min_length=1, max_length=256)]
    reference: bool
    population: str | None
    land_area: str | None

class WorkspaceCatalogue(Contract):
    workspace_contract: Literal[1]
    data_store_id: Identifier
    branches: Annotated[list[BranchState], Field(max_length=1000)]
    domains: Annotated[list[DomainEntry], Field(max_length=12)]
    setups: Annotated[list[SetupEntry], Field(max_length=10)]

class WorkspaceSelection(Contract):
    civilization_id: Identifier
    branch_id: Identifier
    revision_id: Identifier | None

class WorkspaceState(Contract):
    workspace_contract: Literal[1]
    branch: BranchState
    context: RevisionContext
    versions: WorldVersions
    effective_time: EffectiveTime
    goal_count: Annotated[int, Field(ge=0, le=1000)]
    policy_count: Annotated[int, Field(ge=0, le=1000)]
    mechanism_count: Annotated[int, Field(ge=0, le=100)]

class WorkspacePageRequest(Contract):
    context: RevisionContext
    scope_id: Identifier
    collection: Literal['scopes', 'entities', 'values', 'relationships']
    cursor: Identifier | None

class WorkspacePage(Contract):
    workspace_contract: Literal[1]
    scope_id: Identifier
    result: WorldPageResult

workspace_adapter = TypeAdapter(CreateOptions | WorkspaceCatalogue | WorkspaceSelection | WorkspaceState | WorkspacePageRequest | WorkspacePage)
