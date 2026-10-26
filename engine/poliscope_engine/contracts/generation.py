"""Main-only data contracts, not engine commands or dispatch authorization."""
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter
from .base import Contract
from .providers import ProfileId, Revision, Text


class GenerationMessage(Contract):
    role: Literal['system', 'user', 'assistant']
    content: Annotated[str, Field(min_length=1, max_length=262144)]


class GenerationFormat(Contract):
    type: Literal['text', 'json_object', 'json_schema']
    name: Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')] | None = None
    # Bounded supported local JSON Schema dialect; never loaded as code or URL.
    schema_text: Annotated[str, Field(min_length=2, max_length=32768)] | None = None


class GenerationTool(Contract):
    name: Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')]
    description: Annotated[str, Field(max_length=4096)]
    parameters_json: Annotated[str, Field(min_length=2, max_length=32768)]


class GenerationPlan(Contract):
    generation_contract: Literal[1]
    profile_id: ProfileId
    expected_revision: Revision
    messages: Annotated[list[GenerationMessage], Field(min_length=1, max_length=128)]
    stream: bool
    response_format: GenerationFormat
    tools: Annotated[list[GenerationTool], Field(max_length=32)] = []
    tool_choice: Annotated[str, Field(max_length=64)] = 'auto'


class GenerationResult(Contract):
    generation_contract: Literal[1]
    selected_model: Text
    actual_model: Text | None
    actual_provider: Text | None
    finish_reason: Text | None
    status: Literal['complete', 'incomplete', 'refused', 'structured-invalid',
                    'provider-rejected', 'unsupported-parameter', 'response-invalid']
    # Only complete, locally validated schema/object data populates this field.
    validated_json: Annotated[str, Field(max_length=1048576)] | None
    text: Annotated[str, Field(max_length=1048576)] | None
    parameter: Text | None = None


generation_adapter = TypeAdapter(Union[GenerationPlan, GenerationResult])
