"""Protocol-only, bounded stdio producer. EOF never commits application work."""
import argparse
import sys
from poliscope_engine.contracts import (
    MAX_FRAME_BYTES, Request, WireError, decode_frame, encode_frame, adapter,
)


def serve(source, sink):
    negotiated = False
    while True:
        frame = source.readline(MAX_FRAME_BYTES + 1)
        if not frame:
            return 0
        request_id = None
        stopping = False
        try:
            message = decode_frame(frame)
            if not isinstance(message, Request):
                raise WireError('INVALID_MESSAGE')
            request_id = message.id
            operation = message.operation
            if operation == 'runtime.handshake':
                negotiated = True
                result = dict(kind='handshake', versions=dict(application='0.1.0', schema_version=1, protocol=1))
            elif not negotiated:
                raise WireError('INVALID_MESSAGE')
            elif operation == 'runtime.health':
                result = dict(kind='health', state='ready')
            elif operation in ('runtime.cancel', 'runtime.operation_status'):
                result = dict(kind='cancel' if operation == 'runtime.cancel' else 'operation_status',
                              operation_id=message.params.operation_id, state='unknown')
            elif operation == 'runtime.shutdown':
                result = dict(kind='shutdown', state='stopping')
                stopping = True
            else:
                raise WireError('MODEL_UNAVAILABLE')
            response = dict(protocol=1, id=request_id, kind='result', result=result)
        except WireError as error:
            response = dict(protocol=1, id=request_id, kind='error',
                            error=dict(code=error.code, message='Request could not be served'))
            # Malformed streams fail closed; service unavailability is an ordinary error.
            stopping = error.code != 'MODEL_UNAVAILABLE'
        sink.write(encode_frame(adapter.validate_python(response)))
        sink.flush()
        if stopping:
            return 0


def main():
    argparse.ArgumentParser(description='Poliscope protocol runtime').parse_args()
    try:
        return serve(sys.stdin.buffer, sys.stdout.buffer)
    except (BrokenPipeError, OSError):
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
