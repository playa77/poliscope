"""File-sized output stays in Python; IPC carries a bounded receipt only."""
from typing import Literal, Annotated
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .archives import ArchiveOptions
from .evaluation import Digest
from .world import SafeCount

class ReportRequest(Contract):
    format: Literal['markdown', 'csv']
    options: ArchiveOptions = Field(default_factory=ArchiveOptions)
    archive_id: Digest | None = None
    scope_id: Identifier | None = None

class ReportReply(Contract):
    report_schema: Literal[1] = 1
    status: Literal['complete', 'cancelled']
    format: Literal['markdown', 'csv']
    rows: SafeCount = 0
    bytes_written: SafeCount = 0
    projection_digest: Digest | None = None
    redactions: Annotated[list[str], Field(max_length=6)] = Field(default_factory=list)

report_adapter = TypeAdapter(ReportRequest | ReportReply)
