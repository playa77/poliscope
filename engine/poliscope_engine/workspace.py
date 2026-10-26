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
TIME = dict(tick=0, calendar_id='fixed-364-v1')


def registry():
    return MechanismRegistry(model=MODEL, units=Registry((
        Unit('people', (('people', 1),), 'stock', Decimal(1)),
        Unit('km2', (('area', 1),), 'stock', Decimal(1)))))


def starting_inputs(options, civilization_id):
    options = CreateOptions.model_validate(options)
    from poliscope_engine.content import bundled_release
    bundled_release().setup(options.setup, explicitly_selected=True)
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
    from poliscope_engine.content import bundled_release
    return WorkspaceCatalogue(workspace_contract=1, data_store_id=service.data_store_id, branches=service.catalogue(),
        domains=[DomainEntry(id='domain:' + str(i), name=name, status='unanswered') for i, name in enumerate(DOMAIN_NAMES, 1)],
        setups=[SetupEntry(id=s.id, name=s.name, reference=s.kind != 'neutral', population=s.population, land_area=s.land_area)
                for s in bundled_release().metadata.setups
                if s.id in ('blank', 'reference:small-settlement')])


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
    if operation == 'grounding':
        from poliscope_engine.grounding import assemble
        return assemble(service, data)
    if operation == 'grounding-tool':
        from poliscope_engine.grounding import tool
        if set(data) != {'manifest', 'query'}:
            raise ValueError('invalid_grounding_tool')
        return tool(service, data['manifest'], data['query'], identity)
    if operation in ('uncertainty', 'sensitivity', 'capacity'):
        from poliscope_engine import uncertainty_service
        return {'uncertainty': uncertainty_service.analyze, 'sensitivity': uncertainty_service.sensitivity, 'capacity': uncertainty_service.capacity}[operation](service, data)
    if operation == 'timeline':
        from poliscope_engine.timeline_workspace import page as timeline_page
        return timeline_page(service, data)
    if operation in ('workbench', 'preview-workbench', 'apply-workbench', 'delete-note'):
        from poliscope_engine import workbench
        if operation in ('preview-workbench', 'apply-workbench'):
            return (workbench.preview if operation == 'preview-workbench' else workbench.apply)(service, data, identity)
        return (workbench.page if operation == 'workbench' else workbench.delete)(service, data)
    if operation in ('exploration', 'preview-world', 'apply-world'):
        from poliscope_engine import exploration
        if operation == 'apply-world':
            return exploration.apply(service, data, identity)
        return (exploration.page if operation == 'exploration' else exploration.preview)(service, data)
    if operation in ('matrix', 'matrix-model'):
        from poliscope_engine import matrix
        return (matrix.page if operation == 'matrix' else matrix.model)(service, data)
    if operation in ('atlas', 'atlas-source'):
        from poliscope_engine import atlas
        return (atlas.page if operation == 'atlas' else atlas.source)(service, data)
    if operation in ('lineage', 'compare', 'history-action', 'rationale'):
        from poliscope_engine import comparison
        if operation == 'history-action':
            return comparison.action(service, data, identity)
        return {'lineage': comparison.lineage, 'compare': comparison.compare, 'rationale': comparison.rationale}[operation](service, data)
    if operation in ('overview', 'target', 'chart'):
        from poliscope_engine import overview
        return {'overview': overview.page, 'target': overview.target, 'chart': overview.chart}[operation](service, data)
    if operation in ('interview', 'preview-interview', 'apply-interview'):
        from poliscope_engine import interviews
        if operation == 'interview':
            return interviews.question(service, data)
        if operation == 'preview-interview':
            return interviews.stage(service, data, identity)[3]
        return interviews.apply(service, data, identity)
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
    parser.add_argument('--operation', choices=['grounding', 'grounding-tool', 'uncertainty', 'sensitivity', 'capacity', 'timeline', 'workbench', 'preview-workbench', 'apply-workbench', 'delete-note', 'exploration', 'preview-world', 'apply-world', 'matrix', 'matrix-model', 'atlas', 'atlas-source', 'rationale', 'lineage', 'compare', 'history-action', 'catalogue', 'create', 'select', 'page', 'interview', 'preview-interview', 'apply-interview', 'overview', 'target', 'chart'], required=True)
    parser.add_argument('--identity', default='unused')
    args = parser.parse_args()
    try:
        bound = 65536 if args.operation == 'grounding-tool' else 16384
        raw = sys.stdin.buffer.readline(bound + 1)
        if not raw.endswith(b'\n') or len(raw) > bound or sys.stdin.buffer.read(1):
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
