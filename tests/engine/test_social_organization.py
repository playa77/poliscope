"""Independent finite-hour and overlapping-population oracles; synthetic only."""
from copy import deepcopy
from decimal import Decimal, localcontext
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.social_organization import CareRequest
from poliscope_engine.contracts.world import EntityDTO, ScopeDTO, RelationshipDTO, PartitionValueDTO
from poliscope_engine.domains.social_organization import evaluate_care
from poliscope_engine.domains.law_conflict import evaluate_adjudication
from poliscope_engine.numeric import Registry, Unit
from poliscope_engine.world import WorldRegistry, StateOwner, WorldError
from poliscope_engine.world.membership import WorldGraph
from test_governance import world as base_world
from test_policies import PROVENANCE, mechanisms
from test_economy import units as base_units, account, claim, holder, activity
from test_law_conflict import request as law_request


def units():
    return Registry((*base_units().units, Unit('people', (('population', 1),), 'count', Decimal(1))))


def world():
    base = base_world()
    entities = [*base.registry.entities, *[EntityDTO(id=i, entity_kind=k, label=i, provenance=PROVENANCE)
        for i, k in [('home', 'household_arrangement'), ('network', 'community_arrangement')]]]
    scopes = [*base.registry.scopes, *[ScopeDTO(id=i, scope_kind=k, label=i, provenance=PROVENANCE)
        for i, k in [('home:scope', 'household'), ('network:scope', 'community')]]]
    values = [PartitionValueDTO(id='population:a', entity_id='cohort:a', scope_id='local',
        partition='conditions', property_id='population',
        value=dict(kind='quantity', value='10', unit_id='people', time_basis_id=None, denominator_scope_id=None),
        effective_time=dict(tick=0, calendar_id='synthetic:calendar'), provenance=PROVENANCE)]
    registry = WorldRegistry('civ', entities=entities, scopes=scopes, values=values,
        populations=base.registry.populations,
        owners=[StateOwner('cohort:a', 'population', 'conditions', 'synthetic:host')])
    edges = [RelationshipDTO(id='member:' + scope, relationship_version='v1',
        relationship_kind='cohort_membership', from_id='cohort:a', to_id=scope,
        aggregation=dict(kind='partition', partition_id='canonical:a'), provenance=PROVENANCE)
        for scope in ('home:scope', 'network:scope')]
    return WorldGraph(registry, [*base.relationships, *edges])


def request(scope='local'):
    work = dict(contract_version=1, period_id='day:0', batch=dict(contract_version=1,
        accounts=[account('time:a', 5, scope, 'hours')],
        claims=[claim('care', 'time:a', 4, 'cohort:a'), claim('job', 'time:a', 3, 'cohort:a'),
                claim('learning', 'time:a', 2, 'cohort:a')], postings=[], reservations=[], subtotals=[]),
        holders=[holder('time:a', 'cohort:a', 'time')],
        activities=[activity('care', 'care'), activity('job', 'paid_work'), activity('learning', 'training')],
        procedure='priority', claim_order=['job', 'learning', 'care'], mechanism_ref='synthetic:care', source_refs=[])
    return dict(contract_version=1, scope_id=scope, population_property_id='population',
        population_partition='conditions', arrangements=[dict(id=i, scope_id=i + ':scope', source_refs=[])
        for i in ('home', 'network')], obligations=[dict(id='duty', arrangement_id='home',
        beneficiary_id='cohort:a', provider_id='cohort:a',
        authority_id='local-authority' if scope == 'local' else 'regional-authority',
        obligation_ref='synthetic:duty', claim_id='care', source_refs=['synthetic:source'])], work=work, source_refs=[])


def run(data=None, graph=None):
    return evaluate_care(CareRequest.model_validate(request() if data is None else data),
                         graph=graph or world(), units=units())


@pytest.mark.parametrize('scope', ['local', 'region'])
def test_overlap_does_not_duplicate_people_or_time(scope):
    data = request(scope); before = deepcopy(data)
    result = run(data)
    assert result.status == 'resolved' and result.evidence_status == 'hypothetical'
    assert [a.population.value for a in result.arrangements] == ['10', '10']
    assert result.population.value == '10'  # union, never twenty people
    assert [(i.kind, i.actual, i.unmet) for i in result.work.indicators] == [
        ('care', '0', '4'), ('paid_work', '3', '0'), ('training', '2', '0')]
    assert (result.results[0].beneficiary_id, result.results[0].actual, result.results[0].unmet) == ('cohort:a', '0', '4')
    assert data == before
    data['obligations'][0]['source_refs'].append('later')
    assert result.request.obligations[0].source_refs == ['synthetic:source']


def test_explicit_precedence_changes_unmet_care_with_same_five_hours():
    data = request(); data['work']['claim_order'] = ['care', 'job', 'learning']
    result = run(data)
    assert [(i.actual, i.unmet) for i in result.work.indicators] == [('4','0'), ('1','2'), ('0','2')]
    assert result.results[0].posting_ids == result.work.indicators[0].posting_ids
    assert result.results[0].unit_id == 'hours' and result.results[0].period_id == 'day:0'
    data['work']['batch'] = result.work.evaluation.batch.model_dump()
    repeated = run(data)
    assert repeated.results[0].actual_before == '4'
    assert repeated.results[0].actual == '0' and repeated.results[0].unmet == '0'
    assert repeated.work.evaluation.batch == result.work.evaluation.batch


@pytest.mark.parametrize('eligibility,actual,unmet', [('allowed','4','0'), ('denied','0','4'), ('unknown',None,None)])
def test_access_and_unknown_are_not_fabricated_capacity(eligibility, actual, unmet):
    data = request(); data['work']['claim_order'] = ['care','job','learning']
    data['work']['activities'][0]['eligibility'] = eligibility
    result = run(data)
    assert (result.results[0].actual, result.results[0].unmet) == (actual, unmet)
    assert result.status == ('unresolved' if actual is None else 'resolved')


def test_missing_population_withholds_population_without_erasing_work():
    data = request(); data['population_property_id'] = 'missing'
    result = run(data)
    assert result.population.kind == 'unknown' and result.status == 'unresolved'
    assert result.results[0].actual == '0' and result.results[0].unmet == '4'


def test_absent_procedure_is_unknown_not_zero():
    data = request(); data['work']['procedure'] = None
    result = run(data)
    assert result.status == 'unresolved' and result.results[0].actual is None
    assert result.work.evaluation.batch is None


@pytest.mark.parametrize('mutation', ['arrangement', 'arrangement_kind', 'scope', 'duplicate_scope',
    'duplicate_arrangement', 'beneficiary', 'provider', 'authority', 'claim', 'claim_kind', 'claim_owner',
    'zero', 'duplicate_duty', 'duplicate_claim', 'unmapped', 'work_scope', 'worker', 'second_time'])
def test_invalid_host_links_and_duplicate_work_rejected(mutation):
    data = request(); duty = data['obligations'][0]; work = data['work']
    if mutation == 'arrangement': duty['arrangement_id'] = 'missing'
    elif mutation == 'arrangement_kind': data['arrangements'][0]['id'] = 'cohort:a'
    elif mutation == 'scope': data['scope_id'] = 'home:scope'
    elif mutation == 'duplicate_scope': data['arrangements'][1]['scope_id'] = 'home:scope'
    elif mutation == 'duplicate_arrangement': data['arrangements'].append(data['arrangements'][0])
    elif mutation == 'beneficiary': duty['beneficiary_id'] = 'cohort:b'
    elif mutation == 'provider': duty['provider_id'] = 'home'
    elif mutation == 'authority': duty['authority_id'] = 'home'
    elif mutation == 'claim': duty['claim_id'] = 'missing'
    elif mutation == 'claim_kind': work['activities'][0]['kind'] = 'paid_work'
    elif mutation == 'claim_owner': duty['provider_id'] = 'cohort:b'
    elif mutation == 'zero': work['batch']['claims'][0]['requested'] = '0'
    elif mutation == 'duplicate_duty': data['obligations'].append(duty)
    elif mutation == 'duplicate_claim': data['obligations'].append(duty | {'id':'another'})
    elif mutation == 'unmapped': work['activities'][1]['kind'] = 'care'
    elif mutation == 'work_scope': work['batch']['accounts'][0]['scope_id'] = 'region'
    elif mutation == 'worker': work['batch']['claims'][1]['claimant_id'] = 'missing'
    elif mutation == 'second_time':
        work['batch']['accounts'].append(account('time:copy', 5, 'local', 'hours'))
        work['holders'].append(holder('time:copy', 'cohort:a', 'time'))
    with pytest.raises((AccountError, ValidationError)):
        run(data)


def test_authority_requires_direct_jurisdiction():
    base = world()
    graph = WorldGraph(base.registry, [r for r in base.relationships if r.id != 'local-j'])
    with pytest.raises(AccountError, match='invalid_care_authority'): run(graph=graph)
    data = request(); data['obligations'][0]['authority_id'] = None
    assert run(data, graph).status == 'resolved'


def test_partition_disagreement_and_overlapping_weights_rejected():
    base = world(); edges = list(base.relationships)
    edges[-1] = edges[-1].model_copy(update={'aggregation': edges[-1].aggregation.model_copy(update={'partition_id':'different'})})
    with pytest.raises(WorldError, match='ambiguous_membership'): run(graph=WorldGraph(base.registry, edges))
    raw = [r.model_dump() for r in base.relationships]
    for r in raw[-2:]: r['aggregation'] = dict(kind='weight', weight='0.75')
    with pytest.raises(WorldError, match='membership_overallocated'):
        run(graph=WorldGraph(base.registry, [RelationshipDTO.model_validate(r) for r in raw]))
    for r in raw[-2:]: r['aggregation']['weight'] = '0.5'
    result = run(graph=WorldGraph(base.registry, [RelationshipDTO.model_validate(r) for r in raw]))
    assert result.population.value == '10' and [a.population.value for a in result.arrangements] == ['5','5']


def test_actual_dom04_and_dom02_share_care_claim_and_postings():
    data = request(); law = law_request(); data['work'] = law['administration']
    # Law's two three-hour procedures compete with the same four-hour care duty.
    care = run(data)
    legal = evaluate_adjudication(type_from(law), graph=world(), mechanisms=mechanisms(), units=units())
    assert care.work == legal.administration
    assert care.results[0].unmet == '4'
    assert [r.outcome for r in legal.results] == ['upheld', 'capacity_blocked']
    data['work']['claim_order'] = ['care', 'admin', 'case:b']
    care = run(data); law['administration'] = data['work']
    legal = evaluate_adjudication(type_from(law), graph=world(), mechanisms=mechanisms(), units=units())
    assert care.work == legal.administration and care.results[0].actual == '4'
    assert [r.outcome for r in legal.results] == ['capacity_blocked', 'capacity_blocked']


def type_from(data):
    from poliscope_engine.contracts.law_conflict import AdjudicationRequest
    return AdjudicationRequest.model_validate(data)


def test_hostile_nested_dto_revalidated_and_context_independent():
    req = CareRequest.model_validate(request())
    req.obligations[0].__dict__['beneficiary_id'] = 123
    with pytest.raises(ValidationError): evaluate_care(req, graph=world(), units=units())
    with localcontext() as context:
        context.prec = 2
        assert run().population.value == '10'


def test_zero_capacity_retains_full_obligation():
    data = request(); data['work']['batch']['accounts'][0]['opening'] = '0'
    result = run(data)
    assert result.results[0].actual == '0' and result.results[0].unmet == '4'
    assert result.request.obligations[0].obligation_ref == 'synthetic:duty'


def test_provider_and_beneficiary_are_distinct_canonical_cohorts():
    data = request(); data['obligations'][0]['provider_id'] = 'cohort:b'
    data['work']['holders'][0]['holder_id'] = 'cohort:b'
    for c in data['work']['batch']['claims']: c['claimant_id'] = 'cohort:b'
    result = run(data)
    assert result.results[0].beneficiary_id == 'cohort:a'
    assert result.results[0].provider_id == 'cohort:b'
    assert result.population.value == '10'  # providers outside the selected membership aren't added


def test_reserved_care_time_cannot_be_spent_by_employment():
    data = request()
    data['work']['batch']['reservations'] = [dict(id='care:hold', account_id='time:a', claim_id='care', amount='4')]
    result = run(data)
    assert [(i.actual, i.unmet) for i in result.work.indicators] == [('4','0'),('1','2'),('0','2')]
    assert result.work.evaluation.batch.reservations == CareRequest.model_validate(data).work.batch.reservations


@pytest.mark.parametrize('value', ['-1', '-0.5'])
def test_negative_population_rejected(value):
    base = world()
    record = base.registry.values[0].model_dump(); record['value']['value'] = value
    registry = WorldRegistry('civ', entities=base.registry.entities, scopes=base.registry.scopes,
        values=[PartitionValueDTO.model_validate(record)], populations=base.registry.populations,
        owners=base.registry.owners)
    with pytest.raises(AccountError, match='invalid_arrangement_population'):
        run(graph=WorldGraph(registry, base.relationships))


def test_integer_capacity_oracle_across_demand_and_priorities():
    from itertools import permutations, product
    for supply, care_hours in product(range(6), range(1, 6)):
        for order in permutations(['care','job','learning']):
            data = request(); data['work']['batch']['accounts'][0]['opening'] = str(supply)
            data['work']['batch']['claims'][0]['requested'] = str(care_hours)
            data['work']['claim_order'] = list(order)
            left = supply; expected = {}
            demands = dict(care=care_hours, job=3, learning=2)
            for cid in order:
                served = min(left, demands[cid]); left -= served
                expected[cid] = (str(served), str(demands[cid] - served))
            result = run(data)
            assert {i.claim_id:(i.actual,i.unmet) for i in result.work.indicators} == expected
            assert result.results[0].unmet == expected['care'][1]


@pytest.mark.parametrize('field,value', [('unit_id','hours'), ('time_basis_id','day:0'),
                                       ('denominator_scope_id','local')])
def test_population_count_metadata_must_be_absolute(field, value):
    base = world(); record = base.registry.values[0].model_dump(); record['value'][field] = value
    registry = WorldRegistry('civ', entities=base.registry.entities, scopes=base.registry.scopes,
        values=[PartitionValueDTO.model_validate(record)], populations=base.registry.populations,
        owners=base.registry.owners)
    with pytest.raises(AccountError, match='invalid_arrangement_population'):
        run(graph=WorldGraph(registry, base.relationships))
