"""Credential request DTOs are schema-only; no Python provider handler exists."""
import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.providers import ProviderReplaceKey, ProviderReply


@pytest.mark.parametrize('key', ['', 'x\nInjected: header', 'x\rInjected: header', 'a b', 'é', 'x' * 4097])
def test_key_transfer_rejects_empty_non_ascii_whitespace_and_unbounded_values(key):
    with pytest.raises(ValidationError):
        ProviderReplaceKey(action='replace-key', profile_id='fixture', expected_revision=1, key=key)


def test_reply_has_no_credential_or_blob_field():
    with pytest.raises(ValidationError):
        ProviderReply(provider_contract=1, profiles=[], protection='session-only', status='ready', key='synthetic')


def test_metadata_request_has_no_url_header_or_credential_override():
    from poliscope_engine.contracts.providers import MetadataAction
    query = dict(action='refresh-catalog', profile_id='catalog', expected_revision=1)
    assert MetadataAction(**query).search == ''
    for field, value in [('url', 'https://sink.example'), ('key', 'synthetic'), ('headers', {}), ('offset', -1)]:
        with pytest.raises(ValidationError):
            MetadataAction(**query, **{field: value})


def test_model_metadata_requires_explicit_unknowns_and_preserves_open_strings():
    from poliscope_engine.contracts.providers import ModelMetadata
    model = dict(id='vendor/future:variant', name='Future', available=True,
                 observed_at='2026-10-26T10:00:00Z', source='synthetic', context_length=None,
                 max_output_tokens=None, input_modalities=['future_sensor'], output_modalities=None,
                 supported_parameters=None, capabilities={k: 'unknown' for k in
                 ['text', 'image', 'audio', 'video', 'tools', 'structured_output', 'reasoning']},
                 pricing=None, routing='unknown', raw_json='{"future":true}')
    assert ModelMetadata(**model).id == 'vendor/future:variant'
    with pytest.raises(ValidationError):
        ModelMetadata(**{**model, 'context_length': 0})
    with pytest.raises(ValidationError):
        ModelMetadata(**{**model, 'capabilities': {}})
