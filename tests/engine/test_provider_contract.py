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
