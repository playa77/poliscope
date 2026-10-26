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

class SpendReserve(Contract):
    action: Literal['reserve', 'amend']
    binding: SpendBinding
    exposure: Money
    turn_limit: Money
    session_limit: Money
    profile_limit: Money

class SpendTransition(Contract):
    action: Literal['uncertain', 'complete', 'no-send', 'status']
    binding: SpendBinding

class SpendReply(Contract):
    spending_contract: Literal[1] = 1
    dispatch_id: Id
    status: Literal['reserved', 'uncertain', 'complete', 'no-send', 'missing', 'denied', 'conflict']
    exposure: Money
    # Observations retain reserved exposure, even on completed provider output.
    currency: Literal['USD'] = 'USD'

spending_adapter = TypeAdapter(Union[SpendReserve, SpendTransition, SpendReply])
spend_request_adapter = TypeAdapter(Union[SpendReserve, SpendTransition])
