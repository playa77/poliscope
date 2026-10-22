"""Synthetic ecological prerequisites; integer oracles do not use the allocator."""
from copy import deepcopy
from decimal import Decimal, localcontext
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.environment import EnvironmentRequest
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, RelationshipDTO
from poliscope_engine.domains.environment import evaluate_environment
from poliscope_engine.numeric import Registry, Unit, NumericError
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_economy import account, claim
from test_policies import PROVENANCE


def world():
    entities = [EntityDTO(id=i, entity_kind=k, label=i, provenance=PROVENANCE)
        for i,k in [('civ','civilization'), ('water','resource'), ('sink','resource'),
                    ('farm','institution'), ('clinic','institution')]]
    scopes = [ScopeDTO(id=i, scope_kind=k, label=i, provenance=PROVENANCE)
        for i,k in [('east','settlement'),('west','settlement'),('watershed','region'),('region','region')]]
    relationships = [RelationshipDTO(id=r+':'+s, relationship_version='v1',
        relationship_kind='access', from_id=r, to_id=s,
        aggregation=dict(kind='weight', weight='0.5'), provenance=PROVENANCE)
        for r in ('water','sink') for s in ('east','west','region')]
    return WorldGraph(WorldRegistry('civ', entities=entities, scopes=scopes), relationships)


def units():
    return Registry((Unit('kg', (('mass',1),), 'stock', Decimal(1)),
                     Unit('sink-kg', (('mass',1),), 'capacity', Decimal(1))))


def request():
    return dict(contract_version=1, scope_id='region', period_id='day:0',
        batch=dict(contract_version=1,
            accounts=[account('water:stock',5,'watershed'),
                      account('sink:slots',3,'watershed','hours') | {'unit_id':'sink-kg'}],
            claims=[claim(r+':'+c,a,4,c) for r,a in [('water','water:stock'),('sink','sink:slots')]
                    for c in ('farm','clinic')], postings=[], reservations=[], subtotals=[]),
        boundaries=[dict(resource_id=r, role=role, account_id=a, capacity_status='known',
            selected_limit=limit, policy_ref='synthetic:'+r+':limit', source_refs=['synthetic:boundary'])
            for r,role,a,limit in [('water','extraction_stock','water:stock','4'),
                                  ('sink','sink_allowance','sink:slots','4')]],
        demands=[dict(claim_id=r+':'+c, scope_id=s, scope_relationship_id=r+':'+s,
            access='allowed', access_limit='4', source_refs=['synthetic:demand'])
            for r in ('water','sink') for c,s in [('farm','east'),('clinic','west')]],
        procedure='priority', claim_order=['water:farm','water:clinic','sink:farm','sink:clinic'],
        mechanism_ref='authored:ecological-prerequisites-v1', source_refs=['synthetic:environment'])


def run(data=None, graph=None, registry=None):
    return evaluate_environment(EnvironmentRequest.model_validate(request() if data is None else data),
        graph=world() if graph is None else graph, units=units() if registry is None else registry)


def quantities(result):
    return {r.claim_id:r.additional for r in result.results}


def test_two_local_groups_share_physical_boundary_and_separate_limits():
    data=request(); before=deepcopy(data); result=run(data)
    assert quantities(result) == {'water:farm':'4','water:clinic':'1','sink:farm':'3','sink:clinic':'0'}
    assert result.results[1].findings == ['finite_boundary_shortfall']
    assert [(b.gross_debit,b.limit_status) for b in result.boundaries] == [('5','limit_breached'),('3','within_limit')]
    assert all(a.closing == '0' for a in result.allocation.accounts.accounts)
    assert all(a.scope_id == 'watershed' for a in result.allocation.batch.accounts)
    assert result.request.model_dump() == data == before
    data['boundaries'][0]['source_refs'].append('later')
    assert result.request.boundaries[0].source_refs == ['synthetic:boundary']


def test_exhaustive_independent_integer_feasibility():
    # 81 combinations; the oracle enumerates joint feasible commitments.
    for stock,sink,farm,clinic in product(range(3), range(3), range(1,4), range(1,4)):
        data=request()
        for a,n in zip(data['batch']['accounts'],(stock,sink)):
            a['opening']=str(n)
        for c,n in zip(data['batch']['claims'],(farm,clinic,farm,clinic)):
            c['requested']=str(n)
        result=quantities(run(data))
        for resource,capacity in [('water',stock),('sink',sink)]:
            feasible=[(a,b) for a in range(farm+1) for b in range(clinic+1) if a+b<=capacity]
            assert (int(result[resource+':farm']),int(result[resource+':clinic'])) == max(feasible)


def test_overlapping_views_and_order_never_copy_supply():
    data=request()
    data['demands'][1].update(scope_id='region',scope_relationship_id='water:region')
    assert quantities(run(data))['water:clinic'] == '1'
    data['claim_order'].reverse()
    assert quantities(run(data))['water:clinic'] == '4'
    data['procedure']='all_or_nothing'
    assert quantities(run(data))['water:farm'] == '0'
    assert sum(int(v) for k,v in quantities(run(data)).items() if k.startswith('water:')) == 4


def test_access_denial_and_ceiling_distinct_from_capacity_and_policy():
    data=request(); data['demands'][0]['access']='denied'
    result=run(data)
    assert result.results[0].findings == ['access_denied']
    assert result.results[1].additional == '4'
    data=request(); data['demands'][0]['access_limit']='1'
    assert run(data).results[0].findings == ['access_limit_shortfall']
    data['batch']['accounts'][0]['opening']='0'
    assert run(data).results[0].findings == ['access_limit_shortfall','finite_boundary_shortfall']


@pytest.mark.parametrize('unknown', ['capacity','access','procedure'])
def test_unknown_withholds_competitors_and_preserves_prior_book(unknown):
    data=request()
    if unknown == 'capacity': data['boundaries'][0]['capacity_status']='unknown'
    if unknown == 'access': data['demands'][0]['access']='unknown'
    if unknown == 'procedure': data['procedure']=None
    result=run(data)
    assert result.status == 'unresolved'
    assert all(r.additional is None and r.unmet is None for r in result.results)
    assert result.allocation.batch == result.request.batch
    assert all(not b.candidate_complete for b in result.boundaries)


def test_policy_unset_unknown_and_zero_are_distinct_not_allocation_controls():
    data=request(); data['boundaries'][0].update(selected_limit=None,policy_ref=None)
    assert run(data).boundaries[0].limit_status == 'not_selected'
    data['boundaries'][0]['policy_ref']='synthetic:unknown-limit'
    assert run(data).boundaries[0].limit_status == 'unknown'
    assert run(data).status == 'resolved'
    data['boundaries'][0]['selected_limit']='0'
    assert run(data).boundaries[0].limit_status == 'limit_breached'
    assert quantities(run(data))['water:farm'] == '4'


def test_prior_postings_holds_replay_and_unknown_do_not_refund():
    data=request()
    data['batch']['reservations']=[dict(id='hold', account_id='water:stock',claim_id='water:clinic',amount='2')]
    data['batch']['postings']=[dict(id='prior',kind='use', source_id='water:stock',destination_id=None,
        amount='1',reservation_id=None,claim_id='water:farm',mechanism_ref='synthetic:prior',source_refs=[])]
    result=run(data)
    assert quantities(result)['water:farm'] == '2'
    assert quantities(result)['water:clinic'] == '2'
    assert result.results[0].prior == '1'
    assert result.boundaries[0].gross_debit == '5'
    data['batch']=result.allocation.batch.model_dump()
    replay=run(data)
    assert all(r.additional=='0' for r in replay.results)
    assert replay.allocation.batch == result.allocation.batch
    data['boundaries'][0]['capacity_status']='unknown'
    assert run(data).boundaries[0].gross_debit == '5'
    assert not run(data).boundaries[0].candidate_complete


def test_limits_count_unclaimed_prior_debits_not_holds_or_net_refills():
    data=request()
    data['batch']['postings']=[dict(id='out',kind='export',source_id='water:stock',destination_id=None,
        amount='2',reservation_id=None,claim_id=None,mechanism_ref='synthetic:export',source_refs=[]),
        dict(id='in',kind='import',source_id=None,destination_id='water:stock',amount='2',
        reservation_id=None,claim_id=None,mechanism_ref='synthetic:import',source_refs=[])]
    assert run(data).boundaries[0].gross_debit == '7'
    data['procedure']=None
    data['batch']['reservations']=[dict(id='hold',account_id='water:stock',claim_id='water:farm',amount='2')]
    assert run(data).boundaries[0].gross_debit == '2'


def test_exact_quantums_under_hostile_decimal_context():
    data=request()
    data['batch']['accounts'][0].update(opening='0.5',quantum='0.1')
    for c in data['batch']['claims'][:2]: c['requested']='0.4'
    for d in data['demands'][:2]: d['access_limit']='0.4'
    with localcontext() as ctx:
        ctx.prec=2
        assert list(quantities(run(data)).values())[:2] == ['0.4','0.1']
    data['batch']['accounts'][0]['opening']='0.55'
    with pytest.raises(NumericError): run(data)


def test_all_or_nothing_access_ceiling_does_not_invent_physical_shortage():
    data=request(); data['procedure']='all_or_nothing'
    data['demands'][0]['access_limit']='1'
    assert run(data).results[0].findings == ['access_limit_shortfall']


def test_area_units_and_scaled_units_remain_explicit_host_declarations():
    data=request()
    data['batch']['accounts'][0]['unit_id']='hectares'
    data['batch']['accounts'][1]['unit_id']='grams-per-period'
    registry=Registry((Unit('hectares', (('area',1),), 'stock', Decimal('10000')),
                       Unit('grams-per-period', (('mass',1),), 'capacity', Decimal('0.001'))))
    # No conversion or cross-account sum: selected limits remain in exact units.
    result=run(data,registry=registry)
    assert result.boundaries[0].gross_debit == '5'
    assert result.boundaries[1].gross_debit == '3'
    dimensionless=Registry((Unit('hectares', (), 'stock', Decimal(1)), registry.units[1]))
    with pytest.raises(AccountError,match='dimensionless_environment_account'):
        run(data,registry=dimensionless)


def test_wrong_relationship_kind_and_request_scope_rejected():
    graph=world()
    rows=[r.model_copy(update={'relationship_kind':'jurisdiction'}) if r.id=='water:east' else r
          for r in graph.relationships]
    with pytest.raises(AccountError,match='invalid_environment_scope_reference'):
        run(graph=WorldGraph(graph.registry,rows))
    data=request(); data['scope_id']='missing'
    with pytest.raises(AccountError,match='invalid_environment_scope'):
        run(data)


@pytest.mark.parametrize('corruption', ['duplicate_boundary','duplicate_resource','unmapped_account',
    'missing_resource','wrong_resource_kind','stock_period','sink_period','sink_invariant','stock_kind',
    'scope','boundary_scope','claimant','duplicate_demand','missing_demand','wrong_endpoint',
    'wrong_relationship','missing_relationship','negative_limit','unreferenced_limit','negative_access',
    'duplicate_order','unknown_unit'])
def test_rejects_malformed_host_references(corruption):
    data=request()
    if corruption=='duplicate_boundary': data['boundaries'].append(deepcopy(data['boundaries'][0]))
    if corruption=='duplicate_resource':
        data['boundaries'][1].update(resource_id='water',role='extraction_stock')
    if corruption=='unmapped_account': data['boundaries'].pop()
    if corruption=='missing_resource': data['boundaries'][0]['resource_id']='absent'
    if corruption=='wrong_resource_kind': data['boundaries'][0]['resource_id']='farm'
    if corruption=='stock_period': data['batch']['accounts'][0]['period_id']='day:0'
    if corruption=='sink_period': data['batch']['accounts'][1]['period_id']='day:1'
    if corruption=='sink_invariant': data['batch']['accounts'][1]['invariant']='physical'
    if corruption=='stock_kind': data['batch']['accounts'][0]['kind']='capacity'
    if corruption=='scope': data['demands'][0]['scope_id']='missing'
    if corruption=='boundary_scope': data['batch']['accounts'][0]['scope_id']='missing'
    if corruption=='claimant': data['batch']['claims'][0]['claimant_id']='water'
    if corruption=='duplicate_demand': data['demands'].append(deepcopy(data['demands'][0]))
    if corruption=='missing_demand': data['demands'].pop()
    if corruption=='wrong_endpoint': data['demands'][0]['scope_relationship_id']='water:west'
    if corruption=='wrong_relationship': data['demands'][0]['scope_relationship_id']='sink:east'
    if corruption=='missing_relationship': data['demands'][0]['scope_relationship_id']='missing'
    if corruption=='negative_limit': data['boundaries'][0]['selected_limit']='-1'
    if corruption=='unreferenced_limit': data['boundaries'][0]['policy_ref']=None
    if corruption=='negative_access': data['demands'][0]['access_limit']='-1'
    if corruption=='duplicate_order': data['claim_order'][0]=data['claim_order'][1]
    if corruption=='unknown_unit': data['batch']['accounts'][0]['unit_id']='missing'
    with pytest.raises((AccountError,NumericError,ValidationError)): run(data)


def test_revalidation_of_forged_nested_dto_and_detached_world():
    graph=world(); before=(graph.registry.entities,graph.registry.scopes),graph.relationships
    dto=EnvironmentRequest.model_validate(request())
    object.__setattr__(dto.demands[0],'access','forged')
    with pytest.raises(ValidationError): evaluate_environment(dto,graph=graph,units=units())
    run(graph=graph)
    assert ((graph.registry.entities,graph.registry.scopes),graph.relationships)==before
