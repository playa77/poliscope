"""Synthetic accommodation procedure; no empirical belief or identity model."""
from copy import deepcopy
from decimal import Decimal
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.meaning_identity import ParticipationRequest
from poliscope_engine.contracts.world import RelationshipDTO
from poliscope_engine.domains.meaning_identity import evaluate_participation
from poliscope_engine.numeric import Registry, Unit
from poliscope_engine.world.membership import WorldGraph
from test_communication import world as base_world
from test_infrastructure import capacity
from test_economy import claim
from test_policies import PROVENANCE


def world():
    base = base_world()
    relations = [RelationshipDTO(id='access:'+g, relationship_version='v1',
        relationship_kind='access', from_id='cohort:'+g, to_id='bridge',
        aggregation={'kind':'non_aggregating'}, provenance=PROVENANCE) for g in ('a','b')]
    return WorldGraph(base.registry, [*base.relationships, *relations])


def units():
    return Registry((Unit('participation', (('participation_slot',1),), 'capacity', Decimal(1)),))


def request():
    return dict(contract_version=1, scope_id='local', period_id='day:0',
        batch=dict(contract_version=1,
            accounts=[capacity('hall',3) | {'unit_id':'participation'}],
            claims=[claim('ritual','hall',2,'cohort:a'),claim('meeting','hall',2,'cohort:b')],
            postings=[],reservations=[],subtotals=[]),
        facilities=[dict(asset_id='bridge', institution_id='local-authority',
            ownership_relationship_id='channel:owner', account_id='hall',
            availability='operating',source_refs=['synthetic:hall'])],
        demands=[dict(claim_id=c,group_id='cohort:'+g,facility_asset_id='bridge',
            access_relationship_id='access:'+g,commitment_ref='synthetic:commitment:'+g,
            accommodation_ref='synthetic:accommodation:'+g,participation='requested',
            eligibility='eligible', access='allowed', access_limit='3',
            obligation_status='compatible',obligation_refs=['synthetic:obligation:'+g],
            source_refs=['synthetic:group:'+g]) for c,g in [('ritual','a'),('meeting','b')]],
        procedure='priority',claim_order=['ritual','meeting'],
        mechanism_ref='authored:participation-prerequisites-v1',source_refs=['synthetic:participation'])


def run(data=None, graph=None, registry=None):
    return evaluate_participation(ParticipationRequest.model_validate(request() if data is None else data),
        graph=world() if graph is None else graph, units=units() if registry is None else registry)


def test_two_groups_share_capacity_without_mutation():
    data=request(); before=deepcopy(data); result=run(data)
    assert [r.additional for r in result.results] == ['2','1']
    assert result.results[1].findings == ['capacity_shortfall']
    assert result.allocation.accounts.accounts[0].closing == '0'
    assert result.request.model_dump() == data == before
    data['demands'][0]['source_refs'].append('later')
    assert result.request.demands[0].source_refs == ['synthetic:group:a']
    assert result.evidence_status == 'hypothetical'


@pytest.mark.parametrize('procedure', ['priority','all_or_nothing'])
def test_independent_exhaustive_integer_oracle(procedure):
    for supply,first,second in product(range(5),range(1,4),range(1,4)):
        data=request(); data['procedure']=procedure
        data['batch']['accounts'][0]['opening']=str(supply)
        for c,n in zip(data['batch']['claims'],(first,second)): c['requested']=str(n)
        feasible=[(a,b) for a in range(first+1) for b in range(second+1) if a+b <= supply
            and (procedure=='priority' or (a in (0,first) and b in (0,second)))]
        expected=max(feasible)
        assert tuple(int(r.additional) for r in run(data).results)==expected


@pytest.mark.parametrize('field,value,finding', [
    ('participation','declined','participation_declined'),
    ('eligibility','ineligible','eligibility_ineligible'),('access','denied','access_denied'),
    ('access_relationship_id',None,'no_declared_access')])
def test_distinct_blocking_rules(field,value,finding):
    data=request(); data['demands'][0][field]=value
    result=run(data)
    assert result.results[0].additional=='0' and result.results[0].findings==[finding]
    assert result.results[1].additional=='2'


@pytest.mark.parametrize('field', ['participation','eligibility','access','obligation_status','facility','procedure'])
def test_unknowns_withhold_all_competitors(field):
    data=request()
    if field=='facility': data['facilities'][0]['availability']='unknown'
    elif field=='procedure': data['procedure']=None
    else: data['demands'][0][field]='unknown'
    result=run(data)
    assert result.status=='unresolved' and result.allocation.batch.postings==[]
    assert all(r.additional is None and r.unmet is None for r in result.results)


def test_conflicting_obligations_are_unresolved_not_a_capacity_choice():
    data=request(); data['demands'][0]['obligation_status']='conflict'
    result=run(data)
    assert result.status=='unresolved' and result.allocation.batch.postings==[]
    assert result.results[0].findings==['obligation_conflict','unresolved_capacity_allocation']
    data['demands'][0]['obligation_refs']=[]
    with pytest.raises(AccountError): run(data)


def test_prior_commitments_replay_and_survive_declined_participation():
    first=run(); data=request(); data['batch']=first.allocation.batch.model_dump()
    replay=run(data)
    assert [r.additional for r in replay.results]==['0','0']
    assert replay.allocation.batch==first.allocation.batch
    data['demands'][0]['participation']='declined'
    result=run(data)
    assert result.results[0].prior=='2' and result.results[0].additional=='0'
    data['demands'][0]['obligation_status']='unknown'
    assert run(data).allocation.batch==first.allocation.batch


def test_reverse_order_and_access_ceiling():
    data=request(); data['claim_order'].reverse()
    assert [r.additional for r in run(data).results]==['1','2']
    data=request(); data['demands'][0]['access_limit']='1'
    assert [r.additional for r in run(data).results]==['1','2']


@pytest.mark.parametrize('mutation', ['scope','period','unit','kind','owner','group','reach','asset','claimant',
    'duplicate_facility','duplicate_demand','missing_demand','unmapped','negative','order'])
def test_invalid_canonical_context_and_mappings(mutation):
    data=request()
    if mutation=='scope': data['scope_id']='missing'
    elif mutation=='period': data['period_id']='day:1'
    elif mutation=='unit': data['batch']['accounts'][0]['unit_id']='messages'
    elif mutation=='kind': data['batch']['accounts'][0]['kind']='stock'
    elif mutation=='owner': data['facilities'][0]['institution_id']='cohort:a'
    elif mutation=='group': data['demands'][0]['group_id']='local-authority'
    elif mutation=='reach': data['demands'][0]['access_relationship_id']='access:b'
    elif mutation=='asset': data['demands'][0]['facility_asset_id']='clinic'
    elif mutation=='claimant': data['batch']['claims'][0]['claimant_id']='cohort:b'
    elif mutation=='duplicate_facility': data['facilities'].append(deepcopy(data['facilities'][0]))
    elif mutation=='duplicate_demand': data['demands'].append(deepcopy(data['demands'][0]))
    elif mutation=='missing_demand': data['demands'].pop()
    elif mutation=='unmapped': data['batch']['accounts'].append(capacity('other',2)|{'unit_id':'participation'})
    elif mutation=='negative': data['demands'][0]['access_limit']='-1'
    elif mutation=='order': data['claim_order']=['ritual','ritual']
    with pytest.raises((AccountError,ValueError)): run(data)


def test_forged_nested_contract_is_revalidated():
    data=ParticipationRequest.model_validate(request())
    object.__setattr__(data.demands[0], 'access', 'forged')
    with pytest.raises(ValidationError): evaluate_participation(data,graph=world(),units=units())


def test_offline_facility_and_wrong_relationship_kind():
    data=request(); data['facilities'][0]['availability']='offline'
    assert all(r.findings==['facility_offline'] for r in run(data).results)
    data=request(); data['demands'][0]['access_relationship_id']='school:message'
    with pytest.raises(AccountError): run(data)


def test_reservations_deduct_once_and_replay():
    data=request()
    data['batch']['reservations']=[dict(id='hold',account_id='hall',claim_id='meeting',amount='2')]
    first=run(data)
    assert [r.additional for r in first.results]==['1','2']
    data['batch']=first.allocation.batch.model_dump()
    assert run(data).allocation.batch==first.allocation.batch
    assert [r.additional for r in run(data).results]==['0','0']


def test_quantum_and_wrong_dimension():
    data=request(); data['batch']['accounts'][0].update(opening='3',quantum='1')
    for c in data['batch']['claims']: c['requested']='1.5'
    assert [r.additional for r in run(data).results]==['1','1']
    wrong=Registry((Unit('participation', (('time',1),), 'capacity', Decimal(1)),))
    with pytest.raises(AccountError,match='invalid_participation_capacity'): run(registry=wrong)


def test_access_ceiling_does_not_invent_physical_shortage():
    data=request(); data['procedure']='all_or_nothing'; data['demands'][0]['access_limit']='1'
    assert run(data).results[0].findings==['access_limit_shortfall']


def test_no_implicit_precedence_or_player_goals():
    data=request(); data['claim_order']=[]
    with pytest.raises(AccountError,match='invalid_claim_order'): run(data)
    data=request(); data['player_goals']=['mandatory:belief']
    with pytest.raises(ValidationError): run(data)


def test_region_scope_is_explicit_and_cannot_reuse_local_capacity():
    data=request(); data['scope_id']='region'
    with pytest.raises(AccountError,match='invalid_participation_capacity'): run(data)
    data['batch']['accounts'][0]['scope_id']='region'
    assert [r.additional for r in run(data).results]==['2','1']


def test_two_views_cannot_duplicate_one_asset_or_one_account():
    data=request(); other=deepcopy(data['facilities'][0])
    other['account_id']='extra'
    data['facilities'].append(other)
    data['batch']['accounts'].append(capacity('extra',3)|{'unit_id':'participation'})
    with pytest.raises(AccountError,match='duplicate_or_unmapped'): run(data)
    data=request(); other=deepcopy(data['facilities'][0]); other['asset_id']='clinic'
    data['facilities'].append(other)
    with pytest.raises(AccountError,match='duplicate_or_unmapped'): run(data)
