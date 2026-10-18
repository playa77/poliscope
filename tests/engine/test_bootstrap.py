"""Real producer integration; data is synthetic and no database is opened."""
import json
import subprocess
import sys
import pytest
from poliscope_engine.contracts import MAX_FRAME_BYTES


def request(operation, params=None, id='r:1'):
    return (json.dumps(dict(protocol=1, id=id, operation=operation, params=params or {}))+'\n').encode()


HANDSHAKE = request('runtime.handshake', {'supported_protocols': [1]})


def run(data=b'', *args):
    return subprocess.run([sys.executable, '-I', '-m', 'poliscope_engine', *args],
                          input=data, capture_output=True, timeout=10)


def test_eof_has_no_unsolicited_output():
    result = run()
    assert result.returncode == 0 and result.stdout == result.stderr == b''


def test_real_batched_lifecycle():
    operations = [HANDSHAKE, request('runtime.health', id='r:2'),
                  request('runtime.cancel', {'operation_id': 'op:1'}, 'r:3'),
                  request('runtime.operation_status', {'operation_id': 'op:1'}, 'r:4'),
                  request('runtime.shutdown', id='r:5'), request('runtime.health', id='r:6')]
    result = run(b''.join(operations))
    messages = [json.loads(line) for line in result.stdout.splitlines()]
    assert [m['id'] for m in messages] == ['r:1', 'r:2', 'r:3', 'r:4', 'r:5']
    assert [m['result']['kind'] for m in messages] == ['handshake', 'health', 'cancel', 'operation_status', 'shutdown']
    assert messages[2]['result']['state'] == messages[3]['result']['state'] == 'unknown'
    assert result.returncode == 0 and result.stderr == b''


@pytest.mark.parametrize(('data', 'code'), [
    (b'garbage\n', 'INVALID_MESSAGE'), (b'\xff\n', 'INVALID_MESSAGE'),
    (b'{"protocol":2}\n', 'UNSUPPORTED_PROTOCOL'),
    (b'x' * (MAX_FRAME_BYTES + 1) + b'\n' + HANDSHAKE, 'MESSAGE_TOO_LARGE'),
    (request('runtime.health'), 'INVALID_MESSAGE'),
    (HANDSHAKE[:-1], 'INVALID_MESSAGE'),
], ids=['malformed', 'utf8', 'protocol', 'oversize', 'pre-handshake', 'truncated'])
def test_fail_closed(data, code):
    result = run(data)
    messages = result.stdout.splitlines()
    assert len(messages) == 1
    assert json.loads(messages[0])['error']['code'] == code
    assert b'garbage' not in result.stdout and result.stderr == b''


def test_fragmented_real_pipe():
    child = subprocess.Popen([sys.executable, '-I', '-m', 'poliscope_engine'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for byte in HANDSHAKE:
            child.stdin.write(bytes([byte]))
            child.stdin.flush()
        child.stdin.close()
        child.wait(timeout=10)
        assert json.loads(child.stdout.read())['result']['kind'] == 'handshake'
        assert child.stderr.read() == b''
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)


def test_unknown_arguments_fail():
    result = run(b'', '--arbitrary')
    assert result.returncode == 2 and result.stdout == b''


def test_unavailable_provider_does_not_destroy_healthy_session():
    from pathlib import Path
    fixtures = json.loads(Path('contracts/fixtures.json').read_text())
    world = next(f['frame'].encode() for f in fixtures
                 if f['code'] is None and '"operation":"world.inspect"' in f['frame'])
    messages = [json.loads(line) for line in run(
        HANDSHAKE + world + request('runtime.health', id='r:3')).stdout.splitlines()]
    assert messages[1]['error']['code'] == 'MODEL_UNAVAILABLE'
    assert messages[2]['result']['state'] == 'ready'
