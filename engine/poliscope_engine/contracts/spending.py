"""Private main-owned spending grants. Credentials and prompt text are forbidden."""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter
from .base import Contract

Id = Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,128}$')]
Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Money = Annotated[str, Field(pattern=r'^(0|[1-9][0-9]{0,6})(\.[0-9]{1,6})?$')]

class SpendBinding(Contract):
    dispatch_id: Id
    turn_id: Id
    session_id: Id
    profile_id: Id
    payload_sha256: Digest
    # Hash of endpoint, revision, selected/allowed models, context and limits.
    binding_sha256: Digest
    currency: Literal['USD']
    estimate_version: Literal['explicit-bounded-exposure-v1']

Cost = Annotated[str, Field(pattern=r'^(0|[1-9][0-9]{0,6})(\.[0-9]{1,18})?$')]
Tokens = Annotated[int, Field(ge=0, le=9007199254740991)]

class CatalogEstimate(Contract):
    input_bound: Tokens
    output_bound: Tokens
    prompt_rate: Cost
    completion_rate: Cost
    request_rate: Cost = '0'
    source: Annotated[str, Field(min_length=1, max_length=256)]
    observed_at: Annotated[str, Field(min_length=1, max_length=256)]

class UsageObservation(Contract):
    source: Literal['response', 'generation-metadata']
    outcome: Literal['complete', 'incomplete', 'cancelled'] | None = None
    generation_id: Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,256}$')] | None = None
    actual_model: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    actual_provider: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    normalized_input_tokens: Tokens | None = None
    normalized_output_tokens: Tokens | None = None
    input_tokens: Tokens | None = None
    output_tokens: Tokens | None = None
    total_tokens: Tokens | None = None
    cached_tokens: Tokens | None = None
    cache_write_tokens: Tokens | None = None
    reasoning_tokens: Tokens | None = None
    actual_cost: Cost | None = None
    currency: Literal['USD'] = 'USD'

class SpendObserve(Contract):
    action: Literal['observe']
    binding: SpendBinding
    observation: UsageObservation

class SpendConfigure(Contract):
    action: Literal['configure']
    binding: SpendBinding
    turn_limit: Money
    session_limit: Money
    profile_limit: Money

class SpendOrigin(Contract):
    endpoint: Annotated[str, Field(min_length=1, max_length=2048)]
    provider_kind: Literal['openrouter', 'openai-compatible']
    allowed_models: Annotated[list[Annotated[str, Field(min_length=1, max_length=256)]], Field(min_length=1, max_length=16)]

class SpendHistory(Contract):
    action: Literal['history']
    binding: SpendBinding
    before_dispatch: Id | None = None
    lookup_dispatch: Id | None = None

class SpendRecord(Contract):
    binding: SpendBinding
    state: Literal['reserved', 'uncertain', 'complete', 'no-send']
    exposure: Money
    origin: SpendOrigin | None = None
    usage: UsageObservation | None = None

class SpendReserve(Contract):
    action: Literal['reserve', 'amend']
    binding: SpendBinding
    exposure: Money
    catalog: CatalogEstimate | None = None
    origin: SpendOrigin | None = None
    turn_limit: Money
    session_limit: Money
    profile_limit: Money

class SpendTransition(Contract):
    action: Literal['uncertain', 'complete', 'no-send', 'status']
    binding: SpendBinding

class SpendReply(Contract):
    spending_contract: Literal[1] = 1
    dispatch_id: Id
    status: Literal['reserved', 'uncertain', 'complete', 'no-send', 'missing', 'denied', 'conflict', 'configured']
    exposure: Money
    records: Annotated[list[SpendRecord], Field(max_length=64)] = []
    legacy_requests: Annotated[int, Field(ge=0)] = 0
    history_before: Id | None = None
    reconciliation_conflict: bool = False
    actual_cost: Cost | None = None
    catalog_estimate: Cost | None = None
    usage: UsageObservation | None = None
    turn_total: str | None = None
    session_total: str | None = None
    profile_total: str | None = None
    unresolved_requests: Annotated[int, Field(ge=0)] = 0
    # Totals include retained bounded exposure where actual cost remains unknown.
    currency: Literal['USD'] = 'USD'

spending_adapter = TypeAdapter(Union[SpendReserve, SpendTransition, SpendObserve, SpendConfigure, SpendHistory, SpendReply])
spend_request_adapter = TypeAdapter(Union[SpendReserve, SpendTransition, SpendObserve, SpendConfigure, SpendHistory])
