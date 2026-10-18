"""World projection boundaries, independent of future world/storage services."""
import json
from pathlib import Path
import pytest
from poliscope_engine.contracts import adapter, decode_frame, encode_frame, WireError


def message(name):
    cases = json.loads(Path('contracts/fixtures.json').read_text())
    return json.loads(next(c['frame'] for c in cases if c['name'] == 'world:' + name))


def test_unknown_and_zero_remain_different_successful_results():
    unknown = decode_frame((json.dumps(message('unknown')) + '\n').encode())
    zero = decode_frame((json.dumps(message('zero')) + '\n').encode())
    assert unknown.kind == zero.kind == 'result'
    assert unknown.result.page.items[0].value.kind == 'unknown'
    assert zero.result.page.items[0].value.value == '0'
    assert 'value' not in unknown.result.page.items[0].value.model_dump()


def test_read_context_is_explicit_not_replaced_by_current_head():
    payload = message('continuation')
    decoded = decode_frame((json.dumps(payload) + '\n').encode())
    assert decoded.params.context.revision_id == 'revision:17'
    assert decoded.params.cursor == 'cursor:revision17:page2'
    assert decoded.params.context.data_store_id == 'store:synthetic'
    assert json.loads(encode_frame(decoded)) == payload


def test_effective_time_and_version_axes_are_preserved_independently():
    payload = message('empty-terminal-page')
    payload['result']['effective_time']['tick'] = 9007199254740991
    decoded = decode_frame((json.dumps(payload) + '\n').encode())
    assert decoded.result.effective_time.tick == 9007199254740991
    assert decoded.result.versions.model_id == 'model:fixture@2'
    assert decoded.result.versions.numeric_runtime_id == 'numeric:fixture@3'
    assert decoded.result.page.items == []
    assert decoded.result.page.next_cursor is None


def test_structurally_valid_page_still_obeys_frame_byte_limit():
    # Individual fields and 100-item cap pass; combined UTF-8 payload exceeds 1 MiB.
    payload = message('bounded-full-page')
    for item in payload['result']['page']['items']:
        item['provenance']['source_refs'] = ['source:' + 'x' * 249] * 100
    model = adapter.validate_python(payload)
    with pytest.raises(WireError) as caught:
        encode_frame(model)
    assert caught.value.code == 'MESSAGE_TOO_LARGE'


def test_outbound_revalidation_rejects_unchecked_mutation():
    model = adapter.validate_python(message('zero'))
    # Pydantic frozen models have mutable child containers; never trust construction.
    model.result.page.items[0].value.__dict__['value'] = 'NaN'
    with pytest.raises(WireError) as caught:
        encode_frame(model)
    assert caught.value.code == 'INVALID_MESSAGE'
