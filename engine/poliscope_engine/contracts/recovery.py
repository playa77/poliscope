"""Path-free recovery requests; file and directory grants belong to main."""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext
from .archives import ArchiveDisplay
from .revisions import RevisionInputs

class ModelMigration(Contract):
    revision_contract: Literal[1] = 1
    operation_id: Identifier
    context: RevisionContext
    new_branch_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=256)]
    inputs: RevisionInputs

class RecoveryRequest(Contract):
    recovery_contract: Literal[1] = 1
    action: Literal['inspect', 'backup', 'restore', 'migrate-schema', 'read', 'migrate-model', 'archive-open', 'archive-read', 'archive-migrate']
    context: RevisionContext | None = None
    offset: Annotated[int, Field(ge=0, le=10000)] = 0
    detail_offset: Annotated[int, Field(ge=0, le=1000000)] = 0
    name: Annotated[str, Field(min_length=1, max_length=256)] = 'Migrated comparison'

class RecoveryBranch(Contract):
    context: RevisionContext
    name: Annotated[str, Field(max_length=256)]
    model_id: Identifier
    numeric_runtime_id: Identifier
    execution: Literal['requires_explicit_migration', 'unavailable']

class RecoveryReply(Contract):
    recovery_contract: Literal[1] = 1
    status: Literal['complete', 'cancelled', 'failed']
    diagnostic: Literal['ok', 'corrupt_database', 'corrupt_archive', 'unsupported_schema', 'save_failed', 'migration_failed', 'unreadable_source'] = 'ok'
    detail: Annotated[str, Field(max_length=1024)]
    schema_version: Literal[1, 2] | None = None
    branches: Annotated[list[RecoveryBranch], Field(max_length=1000)] = Field(default_factory=list)
    rows: Annotated[list[ArchiveDisplay], Field(max_length=25)] = Field(default_factory=list)
    next_offset: Annotated[int, Field(ge=0, le=1000000)] | None = None

recovery_adapter = TypeAdapter(Union[ModelMigration, RecoveryRequest, RecoveryReply])
