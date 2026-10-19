"""Data-only policy inputs/results; resolution rules are registered by the host."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .mechanisms import PortType, unique
from .packs import Identity
from .world import WorldValue, References


class PolicyBinding(Contract):
    contract_version: Literal[1]
    id: Identifier
    mechanism: Identity
    scope_id: Identifier
    authority_id: Identifier
    # Empty selects declared direct members; nonempty explicitly selects entities.
    entity_ids: References
    parameter_id: Identifier
    value: WorldValue
    conflict_kind: Literal['parameter', 'allocation']
    account_refs: References
    choice_refs: References

    @model_validator(mode='after')
    def distinct(self):
        for values in (self.entity_ids, self.account_refs, self.choice_refs):
            unique(values)
        return self


class ResolutionRule(Contract):
    """Host-selected, versioned rule; content metadata cannot register itself.

    Exact participants prevent a rule silently extending to newly added policies.
    Authority and scope identify the institution authorizing this resolution.
    """
    contract_version: Literal[1]
    identity: Identity
    authority_id: Identifier
    scope_id: Identifier
    entity_id: Identifier
    parameter_id: Identifier
    participant_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    operation: Literal['select', 'sum', 'bounds']
    selected_id: Identifier | None
    source_refs: References

    @model_validator(mode='after')
    def selection(self):
        unique(self.participant_ids)
        unique(self.source_refs)
        if self.operation == 'select':
            if self.selected_id not in self.participant_ids:
                raise ValueError('missing_selected_policy')
        elif self.selected_id is not None:
            raise ValueError('unexpected_selected_policy')
        return self


class PolicyFinding(Contract):
    kind: Literal['authority_conflict', 'parameter_conflict', 'unresolved_allocation',
                  'missing_parameter', 'incompatible_bounds', 'resolution_conflict']
    entity_id: Identifier
    parameter_id: Identifier
    participant_ids: References
    authority_ids: References
    scope_ids: References
    account_refs: References
    choice_refs: References
    source_refs: References
    requirements: Annotated[list[str], Field(min_length=1, max_length=100)]


class PolicyResult(Contract):
    entity_id: Identifier
    parameter_id: Identifier
    participant_ids: References
    status: Literal['known', 'conflict', 'missing_input']
    value_type: PortType
    value: WorldValue | None
    floor: WorldValue | None
    ceiling: WorldValue | None
    rule: ResolutionRule | None
    source_refs: References
    findings: Annotated[list[PolicyFinding], Field(max_length=100)]


class PolicyEvaluation(Contract):
    contract_version: Literal[1]
    results: Annotated[list[PolicyResult], Field(max_length=10000)]
    not_applicable_ids: References
