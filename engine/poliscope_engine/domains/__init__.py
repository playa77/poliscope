"""Immutable domain catalog layered over the canonical engine, never a second engine."""
from dataclasses import dataclass
from poliscope_engine.contracts.domains import DomainModule, PairedDomainContract
from poliscope_engine.contracts.mechanisms import unique


class ConformanceError(ValueError):
    pass


def detached(model, value):
    return model.model_validate_json(value.model_dump_json())


@dataclass(frozen=True, init=False)
class DomainRegistry:
    _modules: tuple[str, ...]
    _pairs: tuple[str, ...]

    def __init__(self, modules=(), pairs=()):
        modules = tuple(detached(DomainModule, m) for m in modules)
        pairs = tuple(detached(PairedDomainContract, p) for p in pairs)
        unique([m.domain for m in modules])
        unique([(m.identity.id, m.identity.version) for m in modules])
        unique([p.id for p in pairs])
        unique([i.id for m in modules for i in m.interfaces])
        # Even two declarations for the same owner cannot independently own a cell.
        unique([(a.entity_id, a.property_id, a.partition) for m in modules for a in m.authorities])
        object.__setattr__(self, '_modules', tuple(m.model_dump_json() for m in modules))
        object.__setattr__(self, '_pairs', tuple(p.model_dump_json() for p in pairs))

    @property
    def modules(self):
        return tuple(DomainModule.model_validate_json(m) for m in self._modules)

    @property
    def pairs(self):
        return tuple(PairedDomainContract.model_validate_json(p) for p in self._pairs)

    def validate(self, *, world, mechanisms, branch_ids):
        """Resolve declarations against actual authorities; never grant activation."""
        ownership = {o.key: o.writer_id for o in world.owners}
        branch_ids = set(branch_ids)
        interfaces = {}
        covered = []
        for module in self.modules:
            definitions = {(m.id, m.version): mechanisms.definition(m.id, m.version) for m in module.mechanisms}
            if any(d.domain != module.domain for d in definitions.values()):
                raise ConformanceError('foreign_mechanism_domain')
            for a in module.authorities:
                world.entity(a.entity_id)
                if ownership.get((a.entity_id, a.property_id, a.partition)) != a.owner:
                    raise ConformanceError('state_authority_mismatch')
            for interface in module.interfaces:
                d = definitions[(interface.mechanism.id, interface.mechanism.version)]
                ports = d.inputs if interface.direction == 'input' else d.outputs
                port = next((p for p in ports if p.id == interface.port_id), None)
                if port is None or port.value_type != interface.value_type:
                    raise ConformanceError('interface_type_mismatch')
                mechanisms._type(interface.value_type, world)
                for ref in interface.references:
                    if world.entity(ref.entity_id).entity_kind != ref.entity_kind:
                        raise ConformanceError('shared_reference_kind')
                interfaces[interface.id] = (module.domain, interface)
            declared_ports = {(i.mechanism.id, i.mechanism.version, i.direction, i.port_id) for i in module.interfaces}
            expected_ports = {(d.id, d.version, direction, p.id) for d in definitions.values()
                              for direction, ports in [('input', d.inputs), ('output', d.outputs)] for p in ports}
            if declared_ports != expected_ports:
                raise ConformanceError('incomplete_interface_catalog')
            authority_keys = {(a.entity_id, a.property_id, a.partition) for a in module.authorities}
            for hook in module.transitions:
                d = definitions[(hook.mechanism.id, hook.mechanism.version)]
                if any((hook.entity_id, state.id, 'dynamic_state') not in authority_keys for state in d.owned_state):
                    raise ConformanceError('missing_state_authority')
            if {(r.id, r.version) for c in module.coverage for r in c.mechanism_refs} != set(definitions):
                raise ConformanceError('uncovered_mechanism')
            for coverage in module.coverage:
                covered.append(coverage.branch_id)
                if coverage.branch_id not in branch_ids:
                    raise ConformanceError('unknown_branch')
                defs = [definitions[(m.id, m.version)] for m in coverage.mechanism_refs]
                for phase in ('static', 'transition'):
                    available = getattr(coverage, phase + '_available')
                    if available and not any(getattr(d.support, phase) is not None for d in defs):
                        raise ConformanceError('unsupported_execution_claim')
                if coverage.evidence_status == 'supported' and (not defs or any(d.evidence != 'supported' for d in defs)):
                    raise ConformanceError('unsupported_evidence_claim')
                if coverage.status == 'implemented' and (not defs or any(d.modeling in ('partial', 'qualitative', 'unsupported') for d in defs)):
                    raise ConformanceError('missing_implementation')
                if any(not set(coverage.scope_kinds) <= set(d.scope_kinds) for d in defs):
                    raise ConformanceError('coverage_scope_mismatch')
                if not set(coverage.source_refs) <= mechanisms.source_ids:
                    raise ConformanceError('unresolved_provenance')
            for hook in module.transitions:
                d = definitions[(hook.mechanism.id, hook.mechanism.version)]
                world.entity(hook.entity_id)
                world.scope(hook.scope_id)
                if not set(hook.property_refs) <= set(d.write_state_refs):
                    raise ConformanceError('undeclared_transition_write')
                if hook.status == 'proposal_only':
                    mechanisms.activate(d.id, d.version, phase='transition', world=world,
                                        scope_id=hook.scope_id, entity_id=hook.entity_id)
        if set(covered) != branch_ids or len(covered) != len(set(covered)):
            raise ConformanceError('incomplete_branch_coverage')
        for pair in self.pairs:
            for ref in pair.shared_references:
                if world.entity(ref.entity_id).entity_kind != ref.entity_kind:
                    raise ConformanceError('shared_reference_kind')
            if pair.status == 'ready_for_conformance':
                if not set(pair.domains) <= {m.domain for m in self.modules}:
                    raise ConformanceError('missing_counterpart')
                ports = []
                for identity in pair.interface_refs:
                    if identity not in interfaces or interfaces[identity][0] not in pair.domains:
                        raise ConformanceError('missing_counterpart_interface')
                    ports.append(interfaces[identity])
                if {d for d, _ in ports} != set(pair.domains):
                    raise ConformanceError('missing_counterpart_interface')
                if {p.direction for _, p in ports} != {'input', 'output'} or len({p.value_type.model_dump_json() for _, p in ports}) != 1:
                    raise ConformanceError('incompatible_counterpart_ports')
                shared = {r.entity_id for r in pair.shared_references}
                if any(not shared <= {r.entity_id for r in p.references} for _, p in ports):
                    raise ConformanceError('counterpart_identity_mismatch')
                if not {(f.id, f.version) for f in pair.fixture_refs} <= mechanisms.fixture_ids:
                    raise ConformanceError('unresolved_counterpart_fixture')
        return self


def templates():
    """Detached, unactivated branch/counterpart templates for all DOM authors."""
    import json
    from pathlib import Path
    data = json.loads(Path(__file__).with_name('catalog-v1.json').read_text())
    return DomainRegistry([DomainModule.model_validate(m) for m in data['modules']],
                          [PairedDomainContract.model_validate(p) for p in data['pairs']])


def conformance_catalog(directory=None):
    """Retained authored declarations layered over unactivated templates.

    Only this fixed application-owned file is read; content cannot select code.
    Readiness is a conformance disposition, not mechanism activation or a gate.
    """
    import json
    from pathlib import Path
    directory = Path(__file__).parent if directory is None else directory
    base = json.loads((directory / 'catalog-v1.json').read_text())
    authored = json.loads((directory / 'provisioning/counterpart-catalog-v1.json').read_text())
    if base['contract_version'] != 1 or authored['contract_version'] != 1:
        raise ConformanceError('unsupported_catalog_version')
    modules = {m.domain: m for m in map(DomainModule.model_validate, base['modules'])}
    pairs = {p.id: p for p in map(PairedDomainContract.model_validate, base['pairs'])}
    if len(modules) != len(base['modules']) or len(pairs) != len(base['pairs']):
        raise ConformanceError('duplicate_catalog_identity')
    seen = set()
    for value in authored['modules']:
        module = DomainModule.model_validate(value)
        if module.domain in seen or module.domain not in modules:
            raise ConformanceError('unknown_or_duplicate_authored_module')
        seen.add(module.domain)
        if {c.branch_id for c in module.coverage} != {c.branch_id for c in modules[module.domain].coverage}:
            raise ConformanceError('authored_branch_inventory_mismatch')
        modules[module.domain] = module
    seen = set()
    for value in authored['pairs']:
        pair = PairedDomainContract.model_validate(value)
        if (pair.id in seen or pair.id not in pairs
                or pair.domains != pairs[pair.id].domains
                or pair.integration_owner != pairs[pair.id].integration_owner):
            raise ConformanceError('unknown_or_changed_authored_pair')
        seen.add(pair.id)
        pairs[pair.id] = pair
    return DomainRegistry(modules.values(), pairs.values())
