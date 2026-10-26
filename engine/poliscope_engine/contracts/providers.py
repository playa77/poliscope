"""Provider settings IPC only. Secrets are never persisted or consumed by Python."""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter
from .base import Contract

ProfileId = Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')]
Text = Annotated[str, Field(min_length=1, max_length=256)]
Revision = Annotated[int, Field(ge=1, le=9007199254740991)]
Support = Literal['unknown', 'supported', 'unsupported']


class ProviderCapabilities(Contract):
    text: Support
    image: Support
    audio: Support
    video: Support
    tools: Support
    structured_output: Support
    reasoning: Support


class ProviderRouting(Contract):
    order: Annotated[list[Text], Field(max_length=32)]
    only: Annotated[list[Text], Field(max_length=32)]
    ignore: Annotated[list[Text], Field(max_length=32)]
    allow_fallbacks: bool
    require_parameters: bool
    data_collection: Literal['unknown', 'allow', 'deny']


class ProviderGeneration(Contract):
    # Preferences only; later request builders validate provider support and ranges.
    temperature: Annotated[str, Field(pattern=r'^[0-9]{1,3}(\.[0-9]{1,6})?$')] | None
    top_p: Annotated[str, Field(pattern=r'^[0-9]{1,3}(\.[0-9]{1,6})?$')] | None
    max_output_tokens: Annotated[int, Field(ge=1, le=2147483647)] | None


class ProviderProfile(Contract):
    id: ProfileId
    name: Text
    kind: Literal['openrouter', 'openai-compatible']
    endpoint: Annotated[str, Field(min_length=1, max_length=2048)]
    model: Annotated[str, Field(max_length=256)]
    generation: ProviderGeneration
    routing: ProviderRouting
    capabilities: ProviderCapabilities


class ProviderList(Contract):
    action: Literal['list']


class ProviderSave(Contract):
    action: Literal['save']
    profile: ProviderProfile
    expected_revision: Revision | None


class ProviderKeyAction(Contract):
    action: Literal['remove-key', 'test-key', 'delete']
    profile_id: ProfileId
    expected_revision: Revision


class ProviderReplaceKey(Contract):
    action: Literal['replace-key']
    profile_id: ProfileId
    expected_revision: Revision
    # One temporary transfer into main; never a result field or engine request.
    key: Annotated[str, Field(min_length=1, max_length=4096, pattern=r'^[!-~]+$')]




class MetadataAction(Contract):
    action: Literal['catalog', 'refresh-catalog', 'model-endpoints', 'key-status']
    profile_id: ProfileId
    expected_revision: Revision
    search: Annotated[str, Field(max_length=256)] = ''
    offset: Annotated[int, Field(ge=0, le=10000)] = 0
    model_id: Annotated[str, Field(max_length=256)] = ''


class ModelMetadata(Contract):
    id: Text
    name: Text
    available: bool
    observed_at: Text
    source: Text
    context_length: Annotated[int, Field(ge=1, le=9007199254740991)] | None
    max_output_tokens: Annotated[int, Field(ge=1, le=9007199254740991)] | None
    input_modalities: Annotated[list[Text], Field(max_length=64)] | None
    output_modalities: Annotated[list[Text], Field(max_length=64)] | None
    supported_parameters: Annotated[list[Text], Field(max_length=128)] | None
    capabilities: ProviderCapabilities
    pricing: Annotated[dict[Text, Text], Field(max_length=64)] | None
    routing: Support
    # Open metadata survives schema evolution; bounded JSON data, never code.
    raw_json: Annotated[str, Field(max_length=32768)]


class CatalogPage(Contract):
    profile_id: ProfileId
    endpoint: Annotated[str, Field(max_length=2048)]
    fetched_at: Text | None
    state: Literal['fresh', 'cached', 'stale', 'empty']
    total: Annotated[int, Field(ge=0, le=10000)]
    offset: Annotated[int, Field(ge=0, le=10000)]
    models: Annotated[list[ModelMetadata], Field(max_length=20)]


class ProviderEndpointMetadata(Contract):
    provider_name: Text
    context_length: Annotated[int, Field(ge=1, le=9007199254740991)] | None
    max_output_tokens: Annotated[int, Field(ge=1, le=9007199254740991)] | None
    supported_parameters: Annotated[list[Text], Field(max_length=128)] | None
    capabilities: ProviderCapabilities
    pricing: Annotated[dict[Text, Text], Field(max_length=64)] | None


class EndpointMetadata(Contract):
    model_id: Text
    observed_at: Text
    source: Text
    providers: Annotated[list[ProviderEndpointMetadata], Field(max_length=256)]
    # Preserves per-provider prices, context, parameter and future fields.
    raw_json: Annotated[str, Field(max_length=262144)]


class KeyMetadata(Contract):
    observed_at: Text
    source: Text
    limit: Annotated[str, Field(max_length=64)] | None
    limit_remaining: Annotated[str, Field(max_length=64)] | None
    usage: Annotated[str, Field(max_length=64)] | None
    is_free_tier: bool | None
    # Provider-reported metadata, not a local spending authorization.


ProviderRequest = Annotated[Union[ProviderList, ProviderSave, ProviderKeyAction, ProviderReplaceKey, MetadataAction], Field(discriminator='action')]


class ProviderView(Contract):
    profile: ProviderProfile
    revision: Revision
    key_status: Literal['missing', 'protected', 'session-only', 'unavailable']


class ProviderReply(Contract):
    provider_contract: Literal[1]
    profiles: Annotated[list[ProviderView], Field(max_length=64)]
    protection: Literal['os-protected', 'session-only']
    status: Literal['ready', 'saved', 'removed', 'test-accepted', 'unauthorized', 'redirect-blocked', 'cancelled', 'network-failed', 'provider-rejected', 'key-unavailable', 'storage-failed', 'stale-profile', 'metadata-ready', 'metadata-invalid', 'metadata-unsupported', 'rate-limited', 'credits-required', 'model-unavailable']

    catalog: CatalogPage | None = None
    endpoints: EndpointMetadata | None = None
    key_metadata: KeyMetadata | None = None


provider_adapter = TypeAdapter(Union[ProviderRequest, ProviderReply])
