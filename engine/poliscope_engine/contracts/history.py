"""Historical interface 1, independent of the numerical runtime protocol."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter
from .base import Contract, Identifier
from .world import RevisionContext
from .evidence import (EvaluationSummary, EvidencePageResult, EvaluationOutput,
                       Finding, SourceRef, AssumptionRef, TraceNode, EvidenceCollection)

class SavedEvidence(Contract):
    history_schema: Literal[1]
    summary: EvaluationSummary
    outputs: Annotated[list[EvaluationOutput], Field(max_length=100)]
    findings: Annotated[list[Finding], Field(max_length=100)]
    sources: Annotated[list[SourceRef], Field(max_length=100)]
    assumptions: Annotated[list[AssumptionRef], Field(max_length=100)]
    traces: Annotated[list[TraceNode], Field(max_length=100)]

class HistoryRequest(Contract):
    history_protocol: Literal[1]
    context: RevisionContext
    result_id: Identifier
    collection: Literal['summary'] | EvidenceCollection
    offset: Annotated[int, Field(ge=0, le=100)]
    limit: Annotated[int, Field(ge=1, le=100)]

class HistoryResult(Contract):
    history_protocol: Literal[1]
    mode: Literal['stored_historical']
    result: EvaluationSummary | EvidencePageResult

class HistoryError(Contract):
    history_protocol: Literal[1]
    error: Literal['INVALID_REQUEST', 'ACCESS_DENIED', 'UNREADABLE_HISTORY', 'NOT_FOUND', 'INVALID_EVIDENCE', 'RESPONSE_TOO_LARGE']

history_adapter = TypeAdapter(HistoryRequest | HistoryResult | HistoryError)
