"""Fixed reviewed callbacks for the retained twelve-domain synthetic fixture.

This is a trusted host adapter, not content-selected code or public IPC. Complete
requests, policy reviews and world identity bind every result and upstream port.
"""
import json
from functools import cache
from pathlib import Path
from poliscope_engine.accounts import fail
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.static_system import StaticSystemRequest
from poliscope_engine.domains.counterpart_declarations import definitions as all_definitions
from poliscope_engine.domains.counterpart_declarations import sources, fixtures
from poliscope_engine.domains.static_system import evaluate_system, DOMAINS
from poliscope_engine.domains.provisioning.context import binding, digest, policy_evidence
from poliscope_engine.mechanisms import Implementation, MechanismRegistry

MODEL = ('authored:static-system', 'v1')


def ledger_definitions():
    return tuple(MechanismDefinition.model_validate(v) for v in json.loads(
        Path(__file__).with_name('static-ledger-v1.json').read_text()))


def definitions():
    return (*ledger_definitions(), *tuple(MechanismDefinition.model_validate(v) for v in json.loads(
        Path(__file__).with_name('static-system-v1.json').read_text())))


def context_digest(request, *, graph, units, mechanisms):
    return digest(dict(context=binding(request, graph, units, adapter='static-system-v1', model=MODEL),
        policies=policy_evidence(mechanisms)))


def projection(result, domain):
    return json.dumps(dict(domain=domain, baseline_digest=result['baseline_digest'],
        scope_id=result['scope_id'],period_id=result['period_id'],
        local_readiness=result['local_readiness'][domain],
        integrated_readiness=result['integrated_readiness'][domain],
        evaluation=result['evaluations'][domain],missing_effects=result['missing_effects'],
        requirements=[r for r in result['requirements'] if domain in (r['source'],r['target'])],
        source_refs=result['source_refs'],
        evidence_status='hypothetical',coverage_status='partial'), sort_keys=True, separators=(',', ':'))


def host_registry(request, *, graph, units, mechanisms, reviews):
    request = StaticSystemRequest.model_validate_json(request.model_dump_json())
    if any(getattr(request, d) is None for d in DOMAINS):
        fail('static_host_requires_twelve_domains')
    encoded = request.model_dump_json()
    context = context_digest(request, graph=graph, units=units, mechanisms=mechanisms)

    @cache
    def evaluation():
        # Immutable host context; callers receive only fresh values or strings.
        return evaluate_system(StaticSystemRequest.model_validate_json(encoded),
            graph=graph, units=units, mechanisms=mechanisms)

    def callback(domain):
        def execute(port, inputs):
            if (port != 'system:evidence' or inputs['system:context'].kind != 'label'
                    or inputs['system:context'].value != context):
                fail('stale_static_system_context')
            result = evaluation()
            for upstream in incoming(domain):
                value = inputs['system:from/' + upstream]
                if value.kind != 'label' or value.value != projection(result, upstream):
                    fail('stale_static_system_evidence')
            return dict(kind='label', value=projection(result, domain))
        return execute

    def ledger(port, inputs):
        if port == 'system:additional':
            return inputs['system:allocated'].model_dump(mode='json')
        if inputs['system:context'].kind != 'label' or inputs['system:context'].value != context:
            fail('stale_static_system_context')
        result = evaluation()
        if result['candidate_batch'] is None:
            return dict(kind='unknown', reason='Unresolved static system; no complete account snapshot')
        claims = {c['id']:c for c in result['candidate_batch']['claims']}
        value = inputs['system:claim']
        if port != 'system:requested' or value.kind != 'label' or value.value not in claims:
            fail('invalid_static_system_claim')
        claim = claims[value.value]
        account = next(a for a in result['candidate_batch']['accounts'] if a['id'] == claim['account_id'])
        return dict(kind='quantity',value=claim['requested'],unit_id=account['unit_id'],
            time_basis_id=account['period_id'] if units.unit(account['unit_id']).kind in ('flow','capacity') else None,denominator_scope_id=None)

    return MechanismRegistry(model=MODEL, units=units, times=mechanisms.times,
        definitions=[*all_definitions(), *ledger_definitions(), *mechanisms.definitions],
        source_ids=set(sources()) | set(mechanisms.source_ids),
        fixture_ids=set(fixtures()) | set(mechanisms.fixture_ids),
        assumption_ids=mechanisms.assumption_ids,
        implementations=[*mechanisms.implementations, *[
            Implementation(d.support.static.implementation.id, 'v1', 'static', ledger) for d in ledger_definitions()], *[
            Implementation('authored:system/'+d+'/implementation', 'v1', 'static', callback(d)) for d in DOMAINS]],
        reviews=reviews)


def conformance_catalog():
    """Include the private typed ledger adapter for this fixture only.

    Earlier bounded hosts retain their own unit registries; the source catalog
    does not claim those hosts can execute the all-domain snapshot.
    """
    from . import conformance_catalog as retained_catalog, DomainRegistry
    from poliscope_engine.contracts.domains import DomainModule
    base = retained_catalog()
    modules = []
    for module in base.modules:
        if module.domain != 'economy':
            modules.append(module); continue
        raw = module.model_dump(mode='json')
        for definition in ledger_definitions():
            identity = dict(id=definition.id,version=definition.version)
            raw['mechanisms'].append(identity)
            row = next(c for c in raw['coverage'] if c['status'] == 'partial')
            row['mechanism_refs'].append(identity)
            for direction,ports in [('input',definition.inputs),('output',definition.outputs)]:
                for port in ports:
                    raw['interfaces'].append(dict(id=definition.id+'/'+port.id,
                        mechanism=identity,port_id=port.id,direction=direction,
                        value_type=port.value_type.model_dump(mode='json'),references=[]))
        modules.append(DomainModule.model_validate(raw))
    return DomainRegistry(modules, base.pairs)


def incoming(domain):
    definition = next(d for d in definitions() if d.id == 'authored:system/'+domain)
    return tuple(p.id.removeprefix('system:from/') for p in definition.inputs
        if p.id.startswith('system:from/'))


def run_bound_case(case, *, request, units, mechanisms, reviews):
    """Rebind the fixture to the actual case world; reject stale snapshot imports."""
    from poliscope_engine.contracts.revisions import RevisionInputs
    from poliscope_engine.domains import ConformanceError
    from poliscope_engine.domains.conformance import run_case
    from poliscope_engine.world import WorldRegistry, StateOwner, PopulationDeclaration
    from poliscope_engine.world.membership import WorldGraph
    from poliscope_engine.numeric import RUNTIME_ID
    data = RevisionInputs.model_validate_json(case.inputs.model_dump_json())
    if (data.versions.model_id != MODEL[0] or data.versions.numeric_runtime_id != RUNTIME_ID
            or data.versions.catalog_id != 'authored:static-system-catalog-v1'):
        raise ConformanceError('static_system_version_mismatch')
    civs = [e.id for e in data.entities if e.entity_kind == 'civilization']
    if len(civs) != 1:
        raise ConformanceError('static_system_civilization_identity')
    world = WorldRegistry(civs[0],entities=data.entities,scopes=data.scopes,values=data.values,
        owners=[StateOwner(**o.model_dump()) for o in data.owners],
        populations=[PopulationDeclaration(**p.model_dump()) for p in data.populations])
    graph = WorldGraph(world,data.relationships)
    actual_system = [(i.id,i.mechanism_id) for i in data.design.execution.dependencies.instances
        if i.mechanism_id.startswith('authored:system/')]
    if set(actual_system) != {(d,'authored:system/'+d) for d in DOMAINS} or len(actual_system) != len(DOMAINS):
        raise ConformanceError('static_system_incomplete_modules')
    context = context_digest(request,graph=graph,units=units,mechanisms=mechanisms)
    supplied = {(f.consumer.instance_id,f.consumer.port_id) for f in data.design.execution.dependencies.fixed_inputs}
    if not {(d,'system:context') for d in DOMAINS} <= supplied:
        raise ConformanceError('static_system_missing_context')
    fixed = [f.value for f in data.design.execution.dependencies.fixed_inputs
        if f.consumer.port_id == 'system:context']
    if not fixed or any(v.kind != 'label' or v.value != context for v in fixed):
        raise ConformanceError('stale_static_system_context')
    result = evaluate_system(request,graph=graph,units=units,mechanisms=mechanisms)
    expected = result['candidate_batch']
    actual = data.design.execution.batch
    if (None if actual is None else actual.model_dump(mode='json')) != expected:
        raise ConformanceError('static_system_snapshot_mismatch')
    host = host_registry(request,graph=graph,units=units,mechanisms=mechanisms,reviews=reviews)
    catalog = conformance_catalog()
    return run_case(case,catalog=catalog,mechanisms=host,
        branch_ids=[c.branch_id for m in catalog.modules for c in m.coverage])
