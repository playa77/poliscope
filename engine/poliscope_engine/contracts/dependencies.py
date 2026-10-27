"""Data-only static dependency compilation request. No solver authority is implied."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier
from .world import WorldValue


class MechanismInstance(Contract):
    id: Identifier
    mechanism_id: Identifier
    mechanism_version: Identifier
    scope_id: Identifier
    entity_id: Identifier


class PortRef(Contract):
    instance_id: Identifier
    port_id: Identifier


class NumericalBinding(Contract):
    producer: PortRef
    consumer: PortRef


class FixedInput(Contract):
    consumer: PortRef
    value: WorldValue


class ClaimBinding(Contract):
    instance_id: Identifier
    claim_id: Identifier
    account_id: Identifier
    allocation_id: Identifier


class AccountProducer(Contract):
    producer: PortRef
    account_id: Identifier


class ContextRelationship(Contract):
    kind: Literal['institutional', 'documentary']
    source_instance_id: Identifier
    target_instance_id: Identifier
    relationship_ref: Identifier


class DependencyRequest(Contract):
    contract_version: Literal[1]
    instances: Annotated[list[MechanismInstance], Field(max_length=3000)]
    bindings: Annotated[list[NumericalBinding], Field(max_length=30000)]
    fixed_inputs: Annotated[list[FixedInput], Field(max_length=10000)]
    claims: Annotated[list[ClaimBinding], Field(max_length=1000)]
    account_producers: Annotated[list[AccountProducer], Field(max_length=1000)]
    relationships: Annotated[list[ContextRelationship], Field(max_length=30000)]
