"""Data-only mechanism boundary v1; validation never authorizes execution.

References to units, entities, sources and trusted implementations resolve in the
registry. Local references and ownership declarations are checked here.
"""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .evidence import Text
from .packs import GameID, Identity, Refs
from .world import ScopeKind, EntityKind, Partition

Items = Field(max_length=100)
Domain = Literal[
    'provisioning', 'economy', 'governance', 'law_conflict',
    'social_organization', 'knowledge_culture', 'health', 'infrastructure',
    'communication', 'environment', 'meaning_identity', 'security_risk',
]


def unique(values):
    if len(values) != len(set(values)):
        raise ValueError('duplicate_identity')


class QuantityType(Contract):
    kind: Literal['quantity']
    unit_id: Identifier
    time_basis_id: Identifier | None
    denominator_scope_id: Identifier | None


class LabelType(Contract):
    kind: Literal['label']


class ReferenceType(Contract):
    kind: Literal['reference']
    entity_kind: EntityKind


PortType = Annotated[QuantityType | LabelType | ReferenceType, Field(discriminator='kind')]


class InputPort(Contract):
    id: GameID
    value_type: PortType
    required: bool
    missing_behavior: Literal['propagate', 'omit']

    @model_validator(mode='after')
    def required_propagates(self):
        if self.required and self.missing_behavior != 'propagate':
            raise ValueError('required_input_must_propagate')
        return self


class OutputPort(Contract):
    id: GameID
    value_type: PortType
    input_refs: Refs
    missing_behavior: Literal['propagate']


class OwnedState(Contract):
    id: GameID
    owner_domain: Domain
    partition: Literal['dynamic_state']
    value_type: PortType


class Procedure(Contract):
    """Versioned reference only: no Python module path, formula or graph here."""
    kind: Literal['trusted_python', 'declarative_graph']
    implementation: Identity


class Support(Contract):
    static: Procedure | None
    transition: Procedure | None


class Precondition(Contract):
    id: GameID
    input_refs: Refs
    description: Text
    failure_behavior: Literal['not_applicable', 'conflict']


class Claim(Contract):
    id: GameID
    kind: Literal['resource', 'service', 'population', 'time']
    amount_output_ref: GameID
    account_input_ref: GameID
    allocation_input_ref: GameID
    dependent_output_refs: Annotated[list[GameID], Field(min_length=1, max_length=100)]


class Policy(Contract):
    semantics: Literal['exclusive', 'composable', 'floor', 'ceiling', 'delegated']
    composition_rule: Identity | None

    @model_validator(mode='after')
    def explicit_rule(self):
        if self.semantics != 'exclusive' and self.composition_rule is None:
            raise ValueError('missing_composition_rule')
        return self


class Diagnostic(Contract):
    id: GameID
    severity: Literal['info', 'warning', 'error']
    description: Text
    input_refs: Refs
    output_refs: Refs


class TraceDefinition(Contract):
    id: GameID
    input_refs: Refs
    output_refs: Refs
    state_refs: Refs
    description: Text


class ValidationFixture(Contract):
    fixture: Identity
    purpose: Literal['positive', 'invalid_input', 'missing_input', 'conservation', 'boundedness']
    property_refs: Refs


class MechanismDefinition(Contract):
    contract_version: Literal[1]
    id: GameID
    version: Identifier
    domain: Domain
    scope_kinds: Annotated[list[ScopeKind], Field(min_length=1, max_length=6)]
    entity_kinds: Annotated[list[EntityKind], Field(min_length=1, max_length=15)]
    inputs: Annotated[list[InputPort], Items]
    outputs: Annotated[list[OutputPort], Items]
    owned_state: Annotated[list[OwnedState], Items]
    write_state_refs: Refs
    read_partitions: Annotated[list[Partition], Field(max_length=6)]
    preconditions: Annotated[list[Precondition], Items]
    support: Support
    claims: Annotated[list[Claim], Items]
    policy: Policy | None
    origin: Literal['authored', 'imported', 'player_proposed', 'ai_proposed']
    modeling: Literal['numerical', 'procedural', 'qualitative', 'partial', 'unsupported']
    evidence: Literal['unreviewed', 'hypothetical', 'supported', 'disputed']
    source_refs: Refs
    assumption_refs: Refs
    coverage_limits: Text
    diagnostics: Annotated[list[Diagnostic], Items]
    traces: Annotated[list[TraceDefinition], Items]
    fixtures: Annotated[list[ValidationFixture], Items]
    properties: Refs

    @model_validator(mode='after')
    def local_consistency(self):
        collections = (self.inputs, self.outputs, self.owned_state, self.preconditions,
                       self.claims, self.diagnostics, self.traces)
        unique([item.id for collection in collections for item in collection])
        for values in (self.scope_kinds, self.entity_kinds, self.read_partitions,
                       self.write_state_refs, self.source_refs, self.assumption_refs,
                       self.properties):
            unique(values)
        unique([(f.fixture.id, f.fixture.version, f.purpose) for f in self.fixtures])
        inputs = {p.id: p for p in self.inputs}
        outputs = {p.id: p for p in self.outputs}
        states = {s.id: s for s in self.owned_state}

        def refs(values, available):
            unique(values)
            if not set(values) <= set(available):
                raise ValueError('missing_reference')

        for output in self.outputs:
            refs(output.input_refs, inputs)
        for state in self.owned_state:
            if state.owner_domain != self.domain:
                raise ValueError('foreign_state_owner')
        refs(self.write_state_refs, states)
        if self.write_state_refs and self.support.transition is None:
            raise ValueError('state_write_requires_transition')
        if self.modeling in ('qualitative', 'unsupported') and (
                self.support.static is not None or self.support.transition is not None):
            raise ValueError('qualitative_execution')
        if self.modeling in ('numerical', 'procedural') and (
                self.support.static is None and self.support.transition is None):
            raise ValueError('missing_procedure')
        for precondition in self.preconditions:
            refs(precondition.input_refs, inputs)
        for diagnostic in self.diagnostics:
            refs(diagnostic.input_refs, inputs)
            refs(diagnostic.output_refs, outputs)
        for trace in self.traces:
            refs(trace.input_refs, inputs)
            refs(trace.output_refs, outputs)
            refs(trace.state_refs, states)
        for fixture in self.fixtures:
            refs(fixture.property_refs, self.properties)
        for claim in self.claims:
            refs([claim.amount_output_ref], outputs)
            refs([claim.account_input_ref, claim.allocation_input_ref], inputs)
            refs(claim.dependent_output_refs, outputs)
            if inputs[claim.account_input_ref].value_type.kind != 'reference':
                raise ValueError('claim_account_type')
            if inputs[claim.account_input_ref].value_type.entity_kind != 'account':
                raise ValueError('claim_account_type')
            if not inputs[claim.account_input_ref].required:
                raise ValueError('claim_account_must_propagate')
            amount = outputs[claim.amount_output_ref].value_type
            allocated = inputs[claim.allocation_input_ref].value_type
            if amount.kind != 'quantity' or amount != allocated:
                raise ValueError('claim_quantity_type')
            if not inputs[claim.allocation_input_ref].required:
                raise ValueError('allocation_must_propagate')
            for output in claim.dependent_output_refs:
                if claim.allocation_input_ref not in outputs[output].input_refs:
                    raise ValueError('missing_allocation_dependency')
        return self
