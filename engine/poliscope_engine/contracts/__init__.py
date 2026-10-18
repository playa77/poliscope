"""Canonical protocol-1 runtime boundary. No simulation arithmetic lives here."""
from typing import Annotated, Literal
from pydantic import Field, TypeAdapter, ValidationError
from .base import Contract, Identifier
from .world import WorldInspectParams, WorldPageResult
from .evidence import EvidenceInspectParams, EvidencePageResult, EvaluationSummary
import json

MAX_FRAME_BYTES = 1_048_576
class Empty(Contract):
    pass

class HandshakeParams(Contract):
    supported_protocols: Annotated[list[Literal[1]], Field(min_length=1, max_length=1)]

class OperationParams(Contract):
    operation_id: Identifier

class Request(Contract):
    protocol: Literal[1]
    id: Identifier

class HandshakeRequest(Request):
    operation: Literal['runtime.handshake']
    params: HandshakeParams

class HealthRequest(Request):
    operation: Literal['runtime.health']
    params: Empty

class StatusRequest(Request):
    operation: Literal['runtime.operation_status']
    params: OperationParams

class CancelRequest(Request):
    operation: Literal['runtime.cancel']
    params: OperationParams

class ShutdownRequest(Request):
    operation: Literal['runtime.shutdown']
    params: Empty

class WorldInspectRequest(Request):
    operation: Literal['world.inspect']
    params: WorldInspectParams

class EvidenceInspectRequest(Request):
    operation: Literal['evidence.inspect']
    params: EvidenceInspectParams

class Versions(Contract):
    application: Identifier
    schema_version: Literal[1]
    protocol: Literal[1]

class HandshakeResult(Contract):
    kind: Literal['handshake']
    versions: Versions

class HealthResult(Contract):
    kind: Literal['health']
    state: Literal['ready', 'busy', 'stopping']

class StatusResult(Contract):
    kind: Literal['operation_status']
    operation_id: Identifier
    state: Literal['unknown', 'running', 'completed', 'failed', 'cancelled']

class CancelResult(Contract):
    kind: Literal['cancel']
    operation_id: Identifier
    state: Literal['requested', 'already_finished', 'unknown']

class ShutdownResult(Contract):
    kind: Literal['shutdown']
    state: Literal['stopping']

class Success(Contract):
    protocol: Literal[1]
    id: Identifier
    kind: Literal['result']
    result: Annotated[HandshakeResult | HealthResult | StatusResult | CancelResult | ShutdownResult | WorldPageResult | EvaluationSummary | EvidencePageResult, Field(discriminator='kind')]

class ErrorDetail(Contract):
    code: Literal['UNSUPPORTED_PROTOCOL', 'INVALID_MESSAGE', 'MESSAGE_TOO_LARGE', 'UNKNOWN_OPERATION', 'INTERNAL_ERROR', 'CANCELLED', 'STALE_REVISION', 'MODEL_UNAVAILABLE', 'DATABASE_FAILURE']
    message: Annotated[str, Field(min_length=1, max_length=1024)]

class Error(Contract):
    protocol: Literal[1]
    id: Identifier | None
    kind: Literal['error']
    error: ErrorDetail

class Progress(Contract):
    protocol: Literal[1]
    id: Identifier
    kind: Literal['progress']
    operation_id: Identifier
    completed: Annotated[int, Field(ge=0, le=9007199254740991)]
    total: Annotated[int, Field(ge=1, le=9007199254740991)] | None

WireMessage = HandshakeRequest | HealthRequest | StatusRequest | CancelRequest | ShutdownRequest | WorldInspectRequest | EvidenceInspectRequest | Success | Error | Progress
adapter = TypeAdapter(WireMessage)

class WireError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

def decode_frame(frame: bytes) -> WireMessage:
    if len(frame) > MAX_FRAME_BYTES:
        raise WireError('MESSAGE_TOO_LARGE')
    try:
        if not frame.endswith(b'\n') or b'\n' in frame[:-1] or b'\r' in frame:
            raise ValueError()
        raw = json.loads(frame.decode('utf-8'), parse_float=lambda _: (_ for _ in ()).throw(ValueError()), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(raw, dict):
            raise ValueError()
        if type(raw.get('protocol')) is not int or raw['protocol'] != 1:
            raise WireError('UNSUPPORTED_PROTOCOL')
        def reject_booleans(value):
            if isinstance(value, str):
                value.encode("utf-8")
            if isinstance(value, bool):
                raise ValueError()
            if isinstance(value, dict):
                for child in value.values():
                    reject_booleans(child)
            elif isinstance(value, list):
                for child in value:
                    reject_booleans(child)
        reject_booleans(raw)
        return adapter.validate_python(raw)
    except WireError:
        raise
    except (ValueError, UnicodeError, ValidationError, RecursionError):
        raise WireError('INVALID_MESSAGE') from None

def encode_frame(message: WireMessage) -> bytes:
    frame = (message.model_dump_json() + '\n').encode('utf-8')
    decode_frame(frame)
    return frame
