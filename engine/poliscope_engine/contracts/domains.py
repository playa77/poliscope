"""Domain authoring/conformance contract v1; no code loading or authority grants."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier
from .evidence import Text
from .mechanisms import Domain, PortType, unique
from .packs import Identity
from .world import EntityKind, ScopeKind, Partition


class SharedReference(Contract):
    entity_id: Identifier
    entity_kind: EntityKind


class StateAuthority(Contract):
    entity_id: Identifier
    property_id: Identifier
    partition: Partition
    owner: Domain


class DomainInterface(Contract):
    id: Identifier
    mechanism: Identity
    port_id: Identifier
    direction: Literal['input', 'output']
    value_type: PortType
    # Exact authoritative objects; never per-domain copies of capacities.
    references: Annotated[list[SharedReference], Field(max_length=100)]


class BranchCoverage(Contract):
    branch_id: Identifier
    mechanism_refs: Annotated[list[Identity], Field(max_length=100)]
    status: Literal['implemented', 'partial', 'qualitative', 'unresolved', 'unsupported']
    evidence_status: Literal['unreviewed', 'hypothetical', 'supported', 'disputed']
    scope_kinds: Annotated[list[ScopeKind], Field(min_length=1, max_length=6)]
    static_available: bool
    transition_available: bool
    source_refs: Annotated[list[Identifier], Field(max_length=100)]
    limits: Text
    next_task: Text


class TransitionExpectation(Contract):
    mechanism: Identity
    entity_id: Identifier
    scope_id: Identifier
    property_refs: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    # This records proposal validation only, not scheduling/checkpoint acceptance.
    status: Literal['proposal_only', 'unavailable']


class DomainModule(Contract):
    contract_version: Literal[1]
    identity: Identity
    domain: Domain
    mechanisms: Annotated[list[Identity], Field(max_length=100)]
    interfaces: Annotated[list[DomainInterface], Field(max_length=100)]
    authorities: Annotated[list[StateAuthority], Field(max_length=100)]
    coverage: Annotated[list[BranchCoverage], Field(min_length=1, max_length=100)]
    transitions: Annotated[list[TransitionExpectation], Field(max_length=100)]
    # The only accepted architecture. Extra code/database configuration is forbidden.
    runtime: Literal['shared_engine']
    persistence: Literal['shared_store']

    @model_validator(mode='after')
    def references(self):
        keys = [(m.id, m.version) for m in self.mechanisms]
        unique(keys)
        unique([i.id for i in self.interfaces])
        unique([(i.mechanism.id, i.mechanism.version, i.direction, i.port_id) for i in self.interfaces])
        unique([c.branch_id for c in self.coverage])
        unique([(t.mechanism.id, t.mechanism.version, t.entity_id, t.scope_id) for t in self.transitions])
        for transition in self.transitions:
            unique(transition.property_refs)
        unique([(a.entity_id, a.property_id, a.partition) for a in self.authorities])
        for a in self.authorities:
            if a.owner != self.domain:
                raise ValueError('foreign_state_owner')
        for item in (*self.interfaces, *self.transitions):
            if (item.mechanism.id, item.mechanism.version) not in keys:
                raise ValueError('unlisted_mechanism')
        for interface in self.interfaces:
            unique([r.entity_id for r in interface.references])
        for coverage in self.coverage:
            unique([(m.id, m.version) for m in coverage.mechanism_refs])
            unique(coverage.scope_kinds)
            if any((m.id, m.version) not in keys for m in coverage.mechanism_refs):
                raise ValueError('unlisted_mechanism')
            if coverage.status in ('qualitative', 'unresolved', 'unsupported') and (
                    coverage.static_available or coverage.transition_available):
                raise ValueError('unsupported_execution_claim')
        return self


class PairedDomainContract(Contract):
    contract_version: Literal[1]
    id: Identifier
    domains: Annotated[list[Domain], Field(min_length=2, max_length=2)]
    integration_owner: Domain | None
    owner_status: Literal['designated', 'unresolved']
    shared_references: Annotated[list[SharedReference], Field(max_length=100)]
    interface_refs: Annotated[list[Identifier], Field(max_length=100)]
    fixture_refs: Annotated[list[Identity], Field(max_length=100)]
    status: Literal['pending_counterpart', 'ready_for_conformance']
    limits: Text

    @model_validator(mode='after')
    def ownership(self):
        unique(self.domains)
        unique([r.entity_id for r in self.shared_references])
        unique(self.interface_refs)
        unique([(f.id, f.version) for f in self.fixture_refs])
        if (self.owner_status == 'unresolved') != (self.integration_owner is None):
            raise ValueError('owner_status_mismatch')
        if self.integration_owner is not None and self.integration_owner not in self.domains:
            raise ValueError('foreign_integration_owner')
        if self.status == 'ready_for_conformance' and (
                not self.fixture_refs or not self.interface_refs or not self.shared_references or
                self.integration_owner is None):
            raise ValueError('incomplete_counterpart_contract')
        return self
