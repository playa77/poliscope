"""Main-only request DTOs remain bounded data and never enter engine commands."""
import pytest
from pydantic import ValidationError
from poliscope_engine.contracts.generation import GenerationPlan, GenerationResult
from poliscope_engine.contracts.providers import ProviderGeneration, ProviderRouting


def plan():
    return dict(generation_contract=1, profile_id='synthetic', expected_revision=1,
                messages=[dict(role='user', content='fictional data')], stream=True,
                response_format=dict(type='text'))


@pytest.mark.parametrize('field,value', [('url', 'https://sink.example'), ('key', 'synthetic'),
    ('headers', {}), ('expected_revision', 0), ('messages', []), ('stream', 'true')])
def test_generation_contract_rejects_unbounded_or_ambient_authority(field, value):
    with pytest.raises(ValidationError):
        GenerationPlan(**{**plan(), field: value})


def test_old_profiles_have_no_implicit_model_fallback_or_new_privacy_preference():
    routing = ProviderRouting(order=[], only=[], ignore=[], allow_fallbacks=True,
                              require_parameters=True, data_collection='deny')
    assert routing.model_fallbacks == [] and routing.zdr is None
    generation = ProviderGeneration(temperature=None, top_p=None, max_output_tokens=128)
    assert generation.reasoning is None and generation.seed is None
    assert GenerationPlan(**plan()).stream is True


@pytest.mark.parametrize('field,value', [('seed', -1), ('frequency_penalty', 0.1),
    ('reasoning', {'effort': 'invented'}), ('stop', []), ('max_output_tokens', 0)])
def test_generation_options_are_bounded_typed_preferences(field, value):
    with pytest.raises(ValidationError):
        ProviderGeneration(**{**dict(temperature=None, top_p=None, max_output_tokens=128),field:value})


def test_generation_reply_has_no_key_header_or_executable_proposal_field():
    base = dict(generation_contract=1, selected_model='future/open:model', actual_model=None,
                actual_provider=None, finish_reason=None, status='incomplete',
                validated_json=None, text=None)
    assert GenerationResult(**base).actual_model is None
    for key in ('key', 'headers', 'apply'):
        with pytest.raises(ValidationError):
            GenerationResult(**base, **{key:'synthetic'})
