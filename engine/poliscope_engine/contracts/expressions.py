"""Bounded, data-only arithmetic graph v1. References are never executable text."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .mechanisms import PortType
from .packs import Identity


class InputNode(Contract):
    kind: Literal['input']
    id: Identifier
    input_id: Identifier


class ConstantNode(Contract):
    kind: Literal['constant']
    id: Identifier
    value: Annotated[str, Field(min_length=1, max_length=256)]
    value_type: PortType


class OperatorNode(Contract):
    kind: Literal['operator']
    id: Identifier
    operator: Identity
    arguments: Annotated[list[Identifier], Field(min_length=2, max_length=2)]


Node = Annotated[InputNode | ConstantNode | OperatorNode, Field(discriminator='kind')]


class ExpressionGraph(Contract):
    contract_version: Literal[1]
    id: Identifier
    version: Identifier
    nodes: Annotated[list[Node], Field(min_length=1, max_length=256)]
    outputs: Annotated[dict[Identifier, Identifier], Field(max_length=100)]
    state: Annotated[dict[Identifier, Identifier], Field(max_length=100)]
