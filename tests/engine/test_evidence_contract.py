"""Evidence meaning at the transport boundary, independent of producer services."""
import json
from pathlib import Path
import pytest
from poliscope_engine.contracts import adapter, decode_frame, encode_frame, WireError


def message(name):
    return json.loads(next(c['frame'] for c in json.loads(Path('contracts/fixtures.json').read_text())
                           if c['name'] == 'evidence:' + name))


def test_incomplete_and_infeasible_are_successes_not_operation_errors():
    for outcome in ('incomplete', 'infeasible', 'unresolved'):
        model = decode_frame((json.dumps(message(outcome)) + '\n').encode())
        assert model.kind == 'result'
        assert model.result.outcome == outcome
        assert model.result.coverage.status == 'partial'
        assert model.result.finding_refs
    for name in ('STALE_REVISION', 'MODEL_UNAVAILABLE', 'DATABASE_FAILURE'):
        assert adapter.validate_python(message(name)).kind == 'error'


def test_outputs_preserve_precision_and_unavailability():
    outputs = adapter.validate_python(message('outputs')).result.page.items
    assert outputs[0].observation.value.value == '125.0000000000000000000000001'
    for item in outputs[2:]:
        assert item.observation.value.kind == 'unknown'
        assert 'value' not in item.observation.value.model_dump()
    assert adapter.validate_python(message('zero')).result.page.items[0].observation.value.value == '0'


def test_trace_and_source_identity_survive_round_trip():
    for name in ('traces', 'sources', 'assumptions', 'continuation'):
        payload = message(name)
        assert json.loads(encode_frame(adapter.validate_python(payload))) == payload
    trace = adapter.validate_python(message('traces')).result
    assert trace.result_id == 'result:synthetic:17'
    assert trace.context.revision_id == 'revision:17'
    assert trace.versions.numeric_runtime_id == 'numeric:fixture@3'
    assert trace.page.items[0].child_refs == ['trace:child']


def test_combined_evidence_size_is_bounded_and_outbound_revalidated():
    payload = message('traces')
    item = payload['result']['page']['items'][0]
    item['child_refs'] = ['trace:' + 'x' * 250] * 100
    payload['result']['page']['items'] = [item] * 100
    with pytest.raises(WireError, match='MESSAGE_TOO_LARGE'):
        encode_frame(adapter.validate_python(payload))
    model = adapter.validate_python(message('zero'))
    model.result.page.items[0].observation.value.__dict__['value'] = 'NaN'
    with pytest.raises(WireError, match='INVALID_MESSAGE'):
        encode_frame(model)
