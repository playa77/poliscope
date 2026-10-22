"""Synthetic finite reach; independent feasibility oracle and real consumers."""
from copy import deepcopy
from decimal import localcontext
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.infrastructure import InfrastructureRequest
from poliscope_engine.contracts.world import EntityDTO, RelationshipDTO
from poliscope_engine.contracts.health import HealthRequest
from poliscope_engine.contracts.knowledge_culture import EducationRequest
from poliscope_engine.domains.infrastructure import evaluate_infrastructure
from poliscope_engine.domains.health import evaluate_health
from poliscope_engine.domains.knowledge_culture import evaluate_education
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_knowledge_culture import request as school_request, units, world as school_world
from test_health import request as clinic_request
from test_economy import account, claim
from test_policies import PROVENANCE, mechanisms


def world():
    base = school_world()
    entities = [*base.registry.entities, *[EntityDTO(id=eid, entity_kind=kind, label=eid, provenance=PROVENANCE)
        for eid, kind in [('clinic','asset'),('bridge','asset'),('road','asset'),
                          ('village','location'),('junction','location'),('center','location'),('island','location')]]]
    relations = [RelationshipDTO(id=rid, relationship_version='v1', relationship_kind=kind,
        from_id=source, to_id=target, aggregation={'kind':'non_aggregating'}, provenance=PROVENANCE)
        for rid, kind, source, target in [('school:location','containment','school','center'),
            ('clinic:location','containment','clinic','center'),
            ('bridge:edge','connectivity','village','junction'),('road:edge','connectivity','junction','center')]]
    return WorldGraph(WorldRegistry('civ',entities=entities,scopes=base.registry.scopes,
        values=base.registry.values,populations=base.registry.populations,owners=base.registry.owners),
        [*base.relationships,*relations])


def capacity(aid, opening):
    return account(aid,opening,'local','hours') | {'unit_id':'slots'}


def request():
    return dict(contract_version=1,scope_id='local',period_id='day:0',
        batch=dict(contract_version=1,accounts=[capacity('school:slots',5),capacity('clinic:slots',5),
            capacity('bridge:slots',3),capacity('road:slots',4)],
            claims=[claim('school:visit','school:slots',2,'cohort:a'),claim('clinic:visit','clinic:slots',2,'cohort:b')],
            reservations=[],postings=[],subtotals=[]),
        facilities=[dict(asset_id=f,location_id='center',location_relationship_id=f+':location',
            account_id=f+':slots',availability='operating',source_refs=['synthetic:facility']) for f in ('school','clinic')],
        links=[dict(asset_id=a,from_id=s,to_id=t,relationship_id=a+':edge',account_id=a+':slots',
            availability='operating',source_refs=['synthetic:link'])
            for a,s,t in [('bridge','village','junction'),('road','junction','center')]],
        demands=[dict(claim_id=f+':visit',facility_asset_id=f,origin_id='village',path=['bridge','road'],
            access='allowed',access_limit='2',source_refs=['synthetic:demand']) for f in ('school','clinic')],
        procedure='priority',claim_order=['school:visit','clinic:visit'],
        mechanism_ref='authored:infrastructure-reach-v1',source_refs=['synthetic:network'])


def run(data=None, graph=None):
    return evaluate_infrastructure(InfrastructureRequest.model_validate(request() if data is None else data),
        graph=world() if graph is None else graph,units=units())


def additional(result):
    return {r.claim_id:r.additional for r in result.results}


def test_shared_school_clinic_link_and_detached_evidence():
    data = request(); before = deepcopy(data)
    result = run(data)
    assert additional(result) == {'school:visit':'2','clinic:visit':'1'}
    assert result.results[1].findings == ['capacity_shortfall']
    assert result.request.model_dump() == data == before
    assert (result.results[1].unit_id,result.results[1].period_id,result.results[1].scope_id) == ('slots','day:0','local')
    assert result.evidence_status == 'hypothetical'
    data['links'][0]['source_refs'].append('later')
    assert result.request.links[0].source_refs == ['synthetic:link']
    assert {a.account_id:a.closing for a in result.allocation.accounts.accounts} == {
        'bridge:slots':'0','road:slots':'1','school:slots':'3','clinic:slots':'4'}


def test_explicit_order_changes_shared_link_distribution():
    data = request(); data['claim_order'].reverse()
    assert additional(run(data)) == {'school:visit':'1','clinic:visit':'2'}
    data['procedure'] = 'all_or_nothing'
    assert additional(run(data)) == {'school:visit':'0','clinic:visit':'2'}


def test_disconnected_surplus_and_local_use():
    data = request(); data['demands'][0].update(origin_id='island',path=[])
    result = run(data)
    assert result.results[0].findings == ['disconnected']
    assert result.results[0].additional == '0' and result.results[0].unmet == '2'
    assert additional(result)['clinic:visit'] == '2'
    data['demands'][0]['origin_id'] = 'center'
    result = run(data)
    assert result.results[0].additional == '2' and result.results[0].findings == []
    assert additional(result)['clinic:visit'] == '2'


@pytest.mark.parametrize('owner', ['facility','link'])
@pytest.mark.parametrize('state', ['planned','offline','retired'])
def test_nonoperating_assets_supply_no_new_capacity(owner,state):
    data = request(); data['facilities' if owner=='facility' else 'links'][0]['availability'] = state
    result = run(data)
    assert result.results[0].additional == '0'
    assert result.results[0].findings == ['nonoperating_asset']
    assert additional(result)['clinic:visit'] == ('2' if owner=='facility' else '0')


@pytest.mark.parametrize('change', ['facility','link','access','procedure'])
def test_unknowns_withhold_all_competitors_without_zero_claims(change):
    data = request()
    if change in ('facility','link'): data['facilities' if change=='facility' else 'links'][0]['availability'] = 'unknown'
    if change == 'access': data['demands'][0]['access'] = 'unknown'
    if change == 'procedure': data['procedure'] = None
    result = run(data)
    assert result.status == 'unresolved' and result.allocation.batch.postings == []
    assert all(r.additional is None and r.unmet is None for r in result.results)
    assert all('unknown_capacity_allocation' in r.findings for r in result.results)


def test_access_denial_is_not_disconnection_or_zero_supply():
    data = request(); data['demands'][0]['access'] = 'denied'
    result = run(data)
    assert result.results[0].findings == ['access_denied']
    assert result.results[0].additional == '0'
    assert result.results[1].additional == '2'


def test_prior_holds_and_replay_are_not_spent_twice():
    data = request(); data['batch']['accounts'][0]['opening'] = '2'
    data['batch']['claims'].append(claim('school:second','school:slots',2,'cohort:b'))
    data['demands'].append(dict(data['demands'][0],claim_id='school:second'))
    data['claim_order'].append('school:second')
    data['batch']['reservations'] = [dict(id='held',account_id='school:slots',claim_id='school:second',amount='1')]
    first = run(data)
    assert additional(first) == {'school:visit':'1','clinic:visit':'2','school:second':'0'}
    assert next(a for a in first.allocation.accounts.accounts if a.account_id=='school:slots').outstanding_reserved == '1'
    data['batch'] = first.allocation.batch.model_dump()
    second = run(data)
    assert second.allocation.batch == first.allocation.batch
    assert all(r.additional == '0' for r in second.results)
    assert [r.prior for r in second.results] == ['1','2','0']
    # Changed declarations do not retroactively erase existing commitments.
    data['facilities'][0]['availability'] = 'retired'
    assert run(data).allocation.batch == first.allocation.batch


@pytest.mark.parametrize('change,code', [
    ('duplicate_facility','duplicate_or_unmapped'),('duplicate_link','duplicate_or_unmapped'),
    ('duplicate_account','duplicate_or_unmapped'),('role_alias','duplicate_or_unmapped'),
    ('unmapped','duplicate_or_unmapped'),('duplicate_demand','invalid_infrastructure_demands'),
    ('missing_demand','invalid_infrastructure_demands'),('period','invalid_infrastructure_capacity'),
    ('scope','invalid_infrastructure_capacity'),('unit','invalid_infrastructure_capacity'),
    ('location','invalid_infrastructure_location'),('edge','duplicate_infrastructure_connectivity'),
    ('backward','invalid_infrastructure_path'),('missing_link','invalid_infrastructure_path'),
    ('cycle','invalid_infrastructure_path'),('short_path','incomplete_infrastructure_path'),
    ('omitted_path','incomplete_infrastructure_path'),('claim_account','invalid_infrastructure_facility_claim'),
    ('claimant','invalid_infrastructure_entity'),('origin','invalid_infrastructure_entity'),
    ('asset','invalid_infrastructure_entity'),('zero_claim','invalid_infrastructure_facility_claim'),
    ('unknown_facility','invalid_infrastructure_facility_claim')])
def test_invalid_interfaces_reject_whole_candidate(change,code):
    data = request()
    if change == 'duplicate_facility': data['facilities'].append(deepcopy(data['facilities'][0]))
    if change == 'duplicate_link': data['links'].append(deepcopy(data['links'][0]))
    if change == 'duplicate_account': data['links'][0]['account_id'] = 'school:slots'
    if change == 'role_alias': data['links'][0]['asset_id'] = 'school'
    if change == 'unmapped': data['batch']['accounts'].append(capacity('extra',2))
    if change == 'duplicate_demand': data['demands'].append(deepcopy(data['demands'][0]))
    if change == 'missing_demand': data['demands'].pop()
    if change == 'period': data['batch']['accounts'][0]['period_id'] = 'day:1'
    if change == 'scope': data['batch']['accounts'][0]['scope_id'] = 'region'
    if change == 'unit': data['batch']['accounts'][0]['unit_id'] = 'hours'
    if change == 'location': data['facilities'][0]['location_relationship_id'] = 'clinic:location'
    if change == 'edge': data['links'][0]['relationship_id'] = 'road:edge'
    if change == 'backward': data['demands'][0]['path'].reverse()
    if change == 'missing_link': data['demands'][0]['path'] = ['missing']
    if change == 'cycle': data['demands'][0]['path'] = ['bridge','bridge']
    if change == 'short_path': data['demands'][0]['path'] = ['bridge']
    if change == 'omitted_path': data['demands'][0]['path'] = []
    if change == 'claim_account': data['batch']['claims'][0]['account_id'] = 'bridge:slots'
    if change == 'claimant': data['batch']['claims'][0]['claimant_id'] = 'school'
    if change == 'origin': data['demands'][0]['origin_id'] = 'cohort:a'
    if change == 'asset': data['facilities'][0]['asset_id'] = 'cohort:a'
    if change == 'zero_claim': data['batch']['claims'][0]['requested'] = '0'
    if change == 'unknown_facility': data['demands'][0]['facility_asset_id'] = 'missing'
    before = deepcopy(data)
    with pytest.raises(AccountError,match=code): run(data)
    assert data == before


@pytest.mark.parametrize('value', [0.1,'NaN','Infinity'])
def test_decimal_dtos_reject_binary_and_nonfinite_values(value):
    data = request(); data['demands'][0]['access_limit'] = value
    with pytest.raises(ValidationError): run(data)


def test_dto_mutation_revalidation():
    dto = InfrastructureRequest.model_validate(request())
    dto.demands[0].path.append(None)
    with pytest.raises(ValidationError): evaluate_infrastructure(dto,graph=world(),units=units())


def test_fractional_quantum_and_ambient_decimal_context():
    data = request()
    for a in data['batch']['accounts']: a['quantum'] = '0.1'
    data['batch']['accounts'][2]['opening'] = '0.3'
    with localcontext() as ctx:
        ctx.prec = 1
        result = run(data)
    assert additional(result) == {'school:visit':'0.3','clinic:visit':'0'}
    assert sum(Fraction(r.additional) for r in result.results) == Fraction(3,10)


def test_integer_feasibility_oracle_for_two_facilities_and_shared_path():
    for school,clinic,bridge,road in product(range(3),repeat=4):
        data = request()
        for account,value in zip(data['batch']['accounts'],(school,clinic,bridge,road)):
            account['opening'] = str(value)
        # Exhaust all feasible integer pairs independently of engine arithmetic.
        feasible = [(a,b) for a in range(3) for b in range(3)
            if a<=school and b<=clinic and a+b<=bridge and a+b<=road]
        result = run(data)
        assert tuple(int(r.additional) for r in result.results) == max(feasible)


def test_real_education_and_health_read_same_staged_facility_commitments():
    school,clinic = school_request(),clinic_request()
    data = request()
    # Both real domains use one canonical school building. Infrastructure also
    # sees the exact same competing claim IDs, beneficiaries and single slot.
    data['facilities'] = data['facilities'][:1]
    data['batch']['accounts'] = [data['batch']['accounts'][0],*data['batch']['accounts'][2:]]
    data['batch']['accounts'][0]['opening'] = '1'
    data['batch']['claims'] = [claim('seat','school:slots',1,'cohort:a'),claim('clinic:seat','school:slots',1,'cohort:a')]
    for demand,cid in zip(data['demands'],('seat','clinic:seat')):
        demand.update(claim_id=cid,facility_asset_id='school')
    data['claim_order'] = ['seat','clinic:seat']
    infra = run(data)
    # Pass the retained canonical facility sub-book; link commitments remain
    # retained in infrastructure evidence. Close the completed phase explicitly.
    staged = infra.allocation.batch.model_dump()
    staged['accounts'] = [a for a in staged['accounts'] if a['id']=='school:slots']
    staged['postings'] = [p for p in staged['postings'] if p['source_id']=='school:slots']
    facility = school['facility_allocation']
    facility['batch'] = staged; facility['claim_order'] = data['claim_order']
    facility['choices'] = [dict(facility['choices'][0],claim_id=cid,access='denied',access_limit='0') for cid in data['claim_order']]
    clinic['facility_allocation'] = facility
    clinic['services'][0]['facility_claim_ids'] = ['clinic:seat']
    course = evaluate_education(EducationRequest.model_validate(school),graph=world(),mechanisms=mechanisms(),units=units())
    health = evaluate_health(HealthRequest.model_validate(clinic),graph=world(),mechanisms=mechanisms(),units=units())
    assert course.facility_allocation == health.facility_allocation
    assert course.results[0].outcome == 'capacity_ready'
    assert health.results[0].outcome == 'capacity_blocked'
    assert health.results[0].unmet_claim_ids == ['clinic:seat']
    assert course.facility_allocation.batch.postings == [p for p in infra.allocation.batch.postings if p.source_id=='school:slots']


@pytest.mark.parametrize('change,code', [('order','invalid_claim_order'),('unknown_scope','invalid_infrastructure_scope'),
    ('invalid_edge','invalid_infrastructure_connectivity'),('invalid_origin','invalid_infrastructure_path')])
def test_scope_order_and_direction_are_explicit(change,code):
    data = request()
    if change == 'order': data['claim_order'] = []
    if change == 'unknown_scope': data['scope_id'] = 'missing'
    if change == 'invalid_edge': data['links'][0]['relationship_id'] = 'school:location'
    if change == 'invalid_origin': data['demands'][0]['origin_id'] = 'center'
    with pytest.raises(AccountError,match=code): run(data)


def test_connectivity_is_directed_and_empty_disconnected_path_consumes_nothing():
    data = request()
    data['facilities'][0].update(location_id='village',location_relationship_id='school:location')
    base = world()
    rels = [r.model_copy(update={'to_id':'village'}) if r.id=='school:location' else r for r in base.relationships]
    graph = WorldGraph(base.registry,rels)
    data['demands'][0].update(origin_id='center',path=[])
    result = run(data,graph)
    assert result.results[0].findings == ['disconnected']
    assert result.results[0].additional == '0'


def test_same_dimension_with_different_unit_scale_cannot_silently_convert_slots():
    from decimal import Decimal
    from poliscope_engine.numeric import Registry, Unit
    data = request(); data['batch']['accounts'][2]['unit_id'] = 'double_slots'
    registry = Registry((*units().units,Unit('double_slots',(('facility_slot',1),),'capacity',Decimal(2))))
    with pytest.raises(AccountError,match='incompatible_infrastructure_units'):
        evaluate_infrastructure(InfrastructureRequest.model_validate(data),graph=world(),units=registry)


@pytest.mark.parametrize('mode', ['disconnected','planned'])
def test_real_health_cannot_reallocate_withheld_network_phase(mode):
    data = request(); clinic = clinic_request()
    data['facilities'] = data['facilities'][:1]
    data['batch']['accounts'] = [data['batch']['accounts'][0],*data['batch']['accounts'][2:]]
    data['batch']['claims'] = [claim('seat','school:slots',1,'cohort:a')]
    data['demands'] = [dict(data['demands'][0],claim_id='seat')]
    data['claim_order'] = ['seat']
    if mode == 'disconnected': data['demands'][0].update(origin_id='island',path=[])
    else: data['facilities'][0]['availability'] = 'planned'
    infra = run(data)
    assert infra.results[0].unmet == '1'
    staged = infra.allocation.batch.model_dump()
    staged['accounts'] = [a for a in staged['accounts'] if a['id']=='school:slots']
    staged['postings'] = [p for p in staged['postings'] if p['source_id']=='school:slots']
    clinic['facility_allocation']['batch'] = staged
    clinic['facility_allocation']['choices'][0].update(access='denied',access_limit='0')
    health = evaluate_health(HealthRequest.model_validate(clinic),graph=world(),mechanisms=mechanisms(),units=units())
    assert health.results[0].outcome == 'capacity_blocked'
    assert health.results[0].unmet_claim_ids == ['seat']
    assert health.facility_allocation.batch == infra.allocation.batch.model_copy(update={
        'accounts': health.facility_allocation.batch.accounts})
