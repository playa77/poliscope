"""Main-granted one-shot workspace service. Production revisions own all state."""
import argparse
import json
from pathlib import Path
import sys
from decimal import Decimal
from poliscope_engine.contracts.workspace import (CreateOptions, WorkspaceCatalogue,
    DomainEntry, SetupEntry, WorkspaceSelection, WorkspaceState, WorkspacePageRequest, WorkspacePage)
from poliscope_engine.contracts.revisions import CreateRequest, RevisionInputs
from poliscope_engine.contracts.world import WorldInspectParams
from poliscope_engine.mechanisms import MechanismRegistry
from poliscope_engine.numeric import Registry, Unit, RUNTIME_ID, parse
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store

DOMAIN_NAMES = (
    'Resource & Material Base', 'Economy & Exchange', 'Governance & Collective Decision-Making',
    'Law, Order & Conflict Resolution', 'Social Organization & Relationships',
    'Knowledge, Education & Culture', 'Health & Wellbeing', 'Infrastructure & Built Environment',
    'Communication & Information', 'Environment & Human–Nature Relationship',
    'Meaning, Values & Identity', 'Security & Risk Management')
MODEL = ('workspace:unmodeled', 'v1')
PROVENANCE = dict(origin='player_input', source_refs=[], assumption_refs=[])
TIME = dict(tick=0, calendar_id='sandbox:calendar')


def registry():
    return MechanismRegistry(model=MODEL, units=Registry((
        Unit('people', (('people', 1),), 'stock', Decimal(1)),
        Unit('km2', (('area', 1),), 'stock', Decimal(1)))))


def starting_inputs(options, civilization_id):
    options = CreateOptions.model_validate(options)
    for value in (options.population, options.land_area):
        if value is not None and parse(value) < 0:
            raise ValueError('negative_starting_condition')
    if options.population is not None and parse(options.population) != parse(options.population).to_integral_value():
        raise ValueError('population_must_be_integral')
    values = []
    for identity, entity, prop, unit, value in (
            ('population:value', 'population', 'people', 'people', options.population),
            ('land:value', 'land', 'area', 'km2', options.land_area)):
        values.append(dict(id=identity, entity_id=entity, scope_id='home', partition='conditions',
            property_id=prop, effective_time=TIME, provenance=PROVENANCE,
            value=dict(kind='unknown', reason='Starting condition unanswered') if value is None else
                dict(kind='quantity', value=value, unit_id=unit, time_basis_id=None, denominator_scope_id=None)))
    return RevisionInputs.model_validate(dict(
        versions=dict(world_schema=1, catalog_id='workspace:domains-v1', model_id=MODEL[0], numeric_runtime_id=RUNTIME_ID),
        entities=[dict(id=i, entity_kind=k, label=n, provenance=PROVENANCE) for i, k, n in (
            (civilization_id, 'civilization', options.name), ('population', 'population_cohort', 'Starting population'),
            ('land', 'resource', 'Starting land'))],
        scopes=[dict(id='home', scope_kind='settlement', label=options.scope_name, provenance=PROVENANCE)],
        values=values, owners=[dict(entity_id=v['entity_id'], property_id=v['property_id'],
            partition='conditions', writer_id='player') for v in values],
        populations=[dict(entity_id='population', role='fixed_input')], relationships=[],
        design=dict(contract_version=1, effective_time=TIME,
            execution=dict(contract_version=1, dependencies=dict(contract_version=1, instances=[],
                bindings=[], fixed_inputs=[], claims=[], account_producers=[], relationships=[]),
                batch=None, claims=[], allocations=[], solvers=[], operation_limit=100000),
            policies=[], policy_rules=[], policy_inputs=[], world_inputs=[], assumption_inputs=[], realization_inputs=[], conditions=[],
            realization=dict(identity=dict(id='sandbox:realization', version='v1'), seed=None, event_ids=[], values=[])),
        assumptions=[], measurements=[], goals=[], references=[]))


def catalogue(service):
    return WorkspaceCatalogue(workspace_contract=1, data_store_id=service.data_store_id, branches=service.catalogue(),
        domains=[DomainEntry(id='domain:' + str(i), name=name, status='unanswered') for i, name in enumerate(DOMAIN_NAMES, 1)],
        setups=[SetupEntry(id='blank', name='Unanswered starting conditions', reference=False, population=None, land_area=None),
                SetupEntry(id='reference:small-settlement', name='Synthetic small settlement (editable conditions only)',
                           reference=True, population='100', land_area='10')])


def select(service, options):
    selection = WorkspaceSelection.model_validate(options)
    branch = service.open(data_store_id=service.data_store_id, civilization_id=selection.civilization_id, branch_id=selection.branch_id)
    context = branch.context if selection.revision_id is None else branch.context.model_copy(update={'revision_id': selection.revision_id})
    record = service.read(context)
    return WorkspaceState(workspace_contract=1, branch=branch, context=context, versions=record.inputs.versions,
        effective_time=record.inputs.design.effective_time, goal_count=len(record.inputs.goals),
        policy_count=len(record.inputs.design.policies), mechanism_count=len(record.inputs.design.execution.dependencies.instances))


def page(service, options):
    query = WorkspacePageRequest.model_validate(options)
    # Scope must belong to this immutable revision. Never invent a zero/empty scope.
    record = service.read(query.context)
    if query.collection != 'scopes' and query.scope_id not in {s.id for s in record.inputs.scopes}:
        raise ValueError('unknown_scope')
    result = service.inspect(WorldInspectParams(world_schema=1, context=query.context,
        collection=query.collection, cursor=query.cursor, limit=25))
    # Retain the canonical context-bound pagination; filter only this page.
    if query.collection == 'values':
        result = result.model_copy(update={'page': result.page.model_copy(update={'items': [v for v in result.page.items if v.scope_id == query.scope_id]})})
    return WorkspacePage(workspace_contract=1, scope_id=query.scope_id, result=result)


def dispatch(service, operation, data, identity):
    if operation == 'catalogue':
        if data != {}:
            raise ValueError('invalid_catalogue')
        return catalogue(service)
    if operation == 'create':
        options = CreateOptions.model_validate(data)
        service.create(CreateRequest(revision_contract=1, data_store_id=service.data_store_id,
            civilization_id='civ:' + identity, branch_id='main', name=options.name,
            operation_id='create:' + identity, inputs=starting_inputs(options, 'civ:' + identity)))
        return select(service, dict(civilization_id='civ:' + identity, branch_id='main', revision_id=None))
    if operation == 'select':
        return select(service, data)
    if operation == 'page':
        return page(service, data)
    raise ValueError('unknown_workspace_operation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--operation', choices=['catalogue', 'create', 'select', 'page'], required=True)
    parser.add_argument('--identity', default='unused')
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.readline(16385)
        if not raw.endswith(b'\n') or len(raw) > 16384 or sys.stdin.buffer.read(1):
            raise ValueError('invalid_workspace_frame')
        data = json.loads(raw)
        with Store(Path(args.directory)) as store:
            reply = dispatch(Revisions(store, registry=registry()), args.operation, data, args.identity)
            frame = reply.model_dump_json().encode() + b'\n'
            if len(frame) > 1048576:
                raise ValueError('workspace_response_too_large')
        sys.stdout.buffer.write(frame)
        return 0
    except Exception:
        # Never expose user paths, saved private text, or arbitrary diagnostics.
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
