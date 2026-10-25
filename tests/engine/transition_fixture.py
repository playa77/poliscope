"""Hypothetical transition inputs; literal finite material/work oracle, no science."""
from copy import deepcopy
from fractions import Fraction
from poliscope_engine.numeric import Registry, Unit, TimeBasis, parse

from poliscope_engine.contracts.boundaries import CreateExperiment
from poliscope_engine.contracts.mechanisms import MechanismDefinition
from poliscope_engine.contracts.revisions import CreateRequest, RevisionInputs
from poliscope_engine.contracts.transitions import TransitionPlan, TransitionProposal
from poliscope_engine.contracts.world import PartitionValueDTO
from poliscope_engine.domains import DomainRegistry
from poliscope_engine.contracts.domains import DomainModule
from poliscope_engine.mechanisms import Implementation
from poliscope_engine.simulation import TransitionAdapter, TransitionReducer
from poliscope_engine.revisions import Revisions
from poliscope_engine.numeric import canonical, exact
from test_dependencies import plain, Q
from test_mechanism_registry import registry as mechanism_registry, PROVENANCE
from test_allocations import units, account, choice, claim
from test_revisions import inputs

CALENDAR = 'fixed-364-v1'


def adapter(*, requested='8', access='allowed', invalid=False, no_demand=False):
    def propose(invocation):
        demands = [] if no_demand else [dict(claim=claim('work', requested,
            account_id='material') | {'claimant_id': invocation.instance.entity_id}, choice=choice('work',
                access=access, mechanism_ref=invocation.instance.mechanism_id, source_refs=['synthetic:source'],
                requirements=[dict(account_id='labor', per_unit='1',kind='funding')],
                outputs=[dict(account_id='product', per_unit='0.7', role='product'),
                         dict(account_id='residual', per_unit='0.2', role='residual')],loss_per_unit='0.1'))]
        return TransitionProposal.model_validate(dict(transition_class='resource_processing',status='ready',reason='synthetic:processing',
            demands=demands,source_refs=['synthetic:source']))
    def resolve(invocation, proposal):
        row = next(v for v in invocation.inputs.values if v.entity_id == invocation.instance.entity_id)
        actuals = {} if invocation.allocation is None else {a.claim_id: Fraction(a.allocated) for a in invocation.allocation.actuals}
        amount = sum((actuals[c] for c in invocation.claim_ids), Fraction())
        return [row.model_copy(update={'value': row.value.model_copy(update={
            'value': canonical(exact(Fraction(row.value.value) + amount + int(invalid)))}),
            'effective_time': invocation.inputs.effective_time})]
    def validate(invocation, proposal, writes, closing):
        old = next(v for v in invocation.inputs.values if v.entity_id == invocation.instance.entity_id)
        actuals = {} if invocation.allocation is None else {a.claim_id: Fraction(a.allocated) for a in invocation.allocation.actuals}
        expected = Fraction(old.value.value) + sum((actuals[c] for c in invocation.claim_ids), Fraction())
        assert len(writes) == 1 and Fraction(writes[0].value.value) == expected, 'synthetic model invariant'
        assert next(v for v in closing.values if v.id == old.id) == writes[0]
    return TransitionAdapter(propose,resolve,validate)


def fixture(domains=('infrastructure','knowledge_culture'), *, adapters=None, missing=(), order=None, operation_limit=10000,
            state_units=None, state_openings=None):
    definitions, callbacks, modules, entities, values, owners = [], {}, [], [], [], []
    for index, domain in enumerate(domains):
        name = chr(ord('a')+index)
        state_type = Q | {'unit_id': 'kg' if state_units is None else state_units.get(name, 'kg')}
        d = plain().model_dump()
        d.update(id='synthetic:model/'+domain, domain=domain,
            owned_state=[dict(id='synthetic:processed',owner_domain=domain,partition='dynamic_state',value_type=state_type)],
            write_state_refs=['synthetic:processed'],read_partitions=['dynamic_state'])
        d['support']['transition'] = dict(kind='trusted_python',implementation=dict(id='synthetic:transition/'+domain,version='v1'))
        if name in missing:
            d.update(owned_state=[],write_state_refs=[])
            d['support']['transition'] = None
        definition = MechanismDefinition.model_validate(d)
        definitions.append(definition)
        static = definition.support.static.implementation
        callbacks[static.id,static.version,'static'] = Implementation(static.id,static.version,'static',lambda p,i: dict(Q,value='0'))
        if name not in missing:
            identity = definition.support.transition.implementation
            cb = adapter() if adapters is None or name not in adapters else adapters[name]
            callbacks[identity.id,identity.version,'transition'] = Implementation(identity.id,identity.version,'transition',cb)
        entities.append(dict(id='service-'+name,entity_kind='resource',label='Synthetic processing '+name,provenance=PROVENANCE))
        values.append(dict(id='processed-'+name,entity_id='service-'+name,property_id='synthetic:processed',
            scope_id='local',partition='dynamic_state',value=dict(state_type,value='0' if state_openings is None else state_openings.get(name,'0')),
            effective_time=dict(tick=0,calendar_id=CALENDAR),provenance=PROVENANCE))
        owners.append(dict(entity_id='service-'+name,property_id='synthetic:processed',partition='dynamic_state',writer_id=domain))
        modules.append(DomainModule.model_validate(dict(contract_version=1,identity=dict(id='domain:'+domain,version='v1'),
            domain=domain,mechanisms=[dict(id=definition.id,version=definition.version)],
            interfaces=[dict(id=domain+':out',mechanism=dict(id=definition.id,version=definition.version),
                port_id='synthetic:out',direction='output',value_type=Q,references=[dict(entity_id='material',entity_kind='account')])],
            authorities=[] if name in missing else [dict(entity_id='service-'+name,property_id='synthetic:processed',partition='dynamic_state',owner=domain)],
            transitions=[] if name in missing else [dict(mechanism=dict(id=definition.id,version=definition.version),
                entity_id='service-'+name,scope_id='local',property_refs=['synthetic:processed'],status='proposal_only')],
            runtime='shared_engine',persistence='shared_store',coverage=[dict(branch_id='synthetic:'+domain,
                mechanism_refs=[dict(id=definition.id,version=definition.version)],status='partial',evidence_status='hypothetical',
                scope_kinds=['settlement'],static_available=True,transition_available=name not in missing,
                source_refs=['synthetic:source'],limits='Synthetic finite processing only.',next_task='Source transitions remain unsupported.') ])))
    all_units = Registry((*units().units, Unit('count', (('count', 1),), 'count', parse('1')),
        Unit('index', (('index', 1),), 'indicator', parse('1'))))
    mechanisms = mechanism_registry(definitions,implementations=list(callbacks.values()),units=all_units,
        times=(TimeBasis('day', parse('86400')), TimeBasis('opening-day:0', parse('86400'))))
    raw = inputs().model_dump()
    raw['entities'] += entities
    raw['values'] += values
    raw['owners'] += owners
    raw['design']['effective_time'] = dict(tick=0,calendar_id=CALENDAR)
    raw['design']['world_inputs'] = []
    dep = raw['design']['execution']['dependencies']
    dep.update(instances=[dict(id=chr(97+i),mechanism_id=d.id,mechanism_version=d.version,
        entity_id='service-'+chr(97+i),scope_id='local') for i,d in enumerate(definitions)],bindings=[],fixed_inputs=[])
    book = dict(contract_version=1,batch=dict(contract_version=1,accounts=[
        account('material','20',scope_id='local'),account('product','0',scope_id='local'),
        account('residual','0',scope_id='local'),account('labor','10',scope_id='local',kind='capacity',
            unit_id='hours',invariant='ledger',period_id='opening-day:0')],postings=[],claims=[],reservations=[],subtotals=[]),
        procedure='priority',claim_order=[],choices=[],mechanism_ref='synthetic:selected-order',source_refs=[])
    for a in book['batch']['accounts']:
        raw['entities'].append(dict(id=a['id'],entity_kind='account',label=a['id'],provenance=PROVENANCE))
        raw['values'].append(dict(id='balance:'+a['id'],entity_id=a['id'],property_id='balance',scope_id='local',
            partition='dynamic_state',value=dict(Q,value=a['opening'],unit_id=a['unit_id'],time_basis_id=a['period_id']),
            effective_time=dict(tick=0,calendar_id=CALENDAR),provenance=PROVENANCE))
        raw['owners'].append(dict(entity_id=a['id'],property_id='balance',partition='dynamic_state',writer_id='shared_accounts'))
    plan = TransitionPlan.model_validate(dict(contract_version=1,opening=book,
        account_bindings=[dict(account_id=a['id'],value_id='balance:'+a['id']) for a in book['batch']['accounts']],
        instance_order=order or [chr(97+i) for i in range(len(domains))],carry_priority='existing_first',operation_limit=operation_limit))
    return mechanisms, DomainRegistry(modules), RevisionInputs.model_validate(raw), plan


def setup(store, **options):
    return start(store, *fixture(**options))


def start(store, mechanisms, catalog, initial, plan):
    revisions = Revisions(store,registry=mechanisms)
    created = revisions.create(CreateRequest(revision_contract=1,data_store_id=revisions.data_store_id,
        civilization_id='civ',branch_id='main',name='Synthetic transitions',operation_id='create',inputs=initial))
    reducer = TransitionReducer(revisions,catalog=catalog)
    request = CreateExperiment.model_validate(dict(boundary_contract=1,
        context=dict(data_store_id=revisions.data_store_id,civilization_id='civ',experiment_id='run'),
        operation_id='experiment',plan=dict(contract_version=1,calendar={},opening_revision=created.context,
            opening_day=0,schedules=[dict(instance_id=i.id,interval_days=1,first_day=1) for i in [*initial.design.execution.dependencies.instances,*plan.instances]],
            events=[],adoptions=[]),conditions=[],transition_plan=plan))
    return reducer, reducer.store.create(request), request
