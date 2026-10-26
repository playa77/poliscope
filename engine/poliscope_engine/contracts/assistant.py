"""Bounded assistant IPC; explicit text sharing, never arbitrary engine operations."""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter
from .base import Contract
from .spending import Id, Money, SpendReply
from .generation import GenerationResult, Attachment
from .providers import Revision
from .grounding import GroundingSelection
from .workbench import WorkbenchPreview

class AssistantPrepare(Contract):
    action: Literal['prepare']
    profile_id: Id
    expected_revision: Revision
    text: Annotated[str, Field(min_length=1, max_length=8192)]
    stream: bool
    grounding: GroundingSelection | None = None
    output: Literal['text', 'image', 'audio'] = 'text'
    attachments: Annotated[list[Attachment], Field(max_length=4)] = []
    exposure: Money
    turn_limit: Money
    session_limit: Money
    profile_limit: Money

class AssistantAction(Contract):
    action: Literal['send', 'cancel', 'status', 'revoke', 'continue', 'preview-proposal', 'delete', 'save-artifact', 'usage', 'reconcile', 'configure-spending', 'usage-history', 'reconcile-history']
    request_id: Id
    lookup_dispatch: Id | None = None
    before_dispatch: Id | None = None
    turn_limit: Money | None = None
    session_limit: Money | None = None
    profile_limit: Money | None = None
    artifact_index: Annotated[int, Field(ge=0, le=1)] = 0
    proposal_index: Annotated[int, Field(ge=0, le=7)] = 0

class AssistantReply(Contract):
    assistant_contract: Literal[1] = 1
    request_id: Id
    status: Literal['prepared', 'pending', 'streaming', 'complete', 'tool-calls', 'incomplete', 'cancelled', 'failed', 'revoked']
    context_json: Annotated[str, Field(max_length=2048)]
    # Exact serialized provider payload; shown before any user-approved dispatch.
    sharing_json: Annotated[str, Field(max_length=4096)]
    payload_json: Annotated[str, Field(max_length=196608)]
    text: Annotated[str, Field(max_length=1048576)] = ''
    reasoning: Annotated[str, Field(max_length=1048576)] = ''
    tools_json: Annotated[str, Field(max_length=1048576)] = '[]'
    usage_json: Annotated[str, Field(max_length=16384)] | None = None
    result: GenerationResult | None = None
    diagnostic: Literal['none', 'authentication', 'credits', 'rate-limit', 'model', 'provider', 'network', 'invalid-response', 'budget', 'sharing', 'configuration', 'redirect'] = 'none'
    grounding_json: Annotated[str, Field(max_length=40000)] | None = None
    proposal_preview: WorkbenchPreview | None = None
    proposals_json: Annotated[str, Field(max_length=40000)] = '[]'
    attachments_json: Annotated[str, Field(max_length=8192)] = '[]'
    artifacts_json: Annotated[str, Field(max_length=196608)] = '[]'
    round: Annotated[int, Field(ge=0, le=3)] = 0
    spending: SpendReply | None = None
    exposure: Money
    exposure_status: Literal['not-reserved', 'reserved', 'unresolved', 'no-send']

assistant_adapter = TypeAdapter(Union[AssistantPrepare, AssistantAction, AssistantReply])
