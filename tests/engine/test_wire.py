import json
from pathlib import Path
import pytest
from poliscope_engine.contracts import decode_frame, encode_frame, WireError

CASES = json.loads(Path('contracts/fixtures.json').read_text())

@pytest.mark.parametrize('case', CASES, ids=lambda c: c['name'])
def test_compatibility(case):
    frame = case['frame'].encode()
    if case['code']:
        with pytest.raises(WireError) as caught:
            decode_frame(frame)
        assert caught.value.code == case['code']
    else:
        assert json.loads(encode_frame(decode_frame(frame))) == json.loads(frame)

@pytest.mark.parametrize('frame,code', [(b'x' * 1_048_577, 'MESSAGE_TOO_LARGE'), (b'\xff\n', 'INVALID_MESSAGE')])
def test_frame_bounds(frame, code):
    with pytest.raises(WireError) as caught:
        decode_frame(frame)
    assert caught.value.code == code

@pytest.mark.parametrize('mutation', ['drift', 'extra', 'missing'])
def test_generated_artifacts_fail_closed(tmp_path, monkeypatch, mutation):
    import importlib.util
    import shutil
    import sys
    spec = importlib.util.spec_from_file_location('generate_wire', 'scripts/generate_contracts.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shutil.copytree('contracts', tmp_path / 'contracts')
    shutil.copytree('content', tmp_path / 'content')
    module.ROOT = tmp_path
    monkeypatch.setattr(sys, 'argv', ['generate_contracts.py', '--check'])
    module.main()
    target = tmp_path / 'contracts/wire.ts'
    if mutation == 'drift':
        target.write_text(target.read_text() + '// drift\n')
    elif mutation == 'missing':
        target.unlink()
    else:
        (tmp_path / 'contracts/unregistered.json').write_text('{}')
    with pytest.raises(SystemExit):
        module.main()
