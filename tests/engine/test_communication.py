"""Synthetic messages: finite channel/verification slots, no truth or delivery claim."""
from copy import deepcopy
from decimal import Decimal, localcontext
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.communication import CommunicationRequest
from poliscope_engine.contracts.world import RelationshipDTO
from poliscope_engine.domains.communication import evaluate_communication
from poliscope_engine.numeric import Registry, Unit
from poliscope_engine.world.membership import WorldGraph
from test_infrastructure import world as base_world, capacity
from test_economy import claim
from test_policies import PROVENANCE


def world():
    base = base_world()
    relationships = [RelationshipDTO(id=rid, relationship_version='v1', relationship_kind=kind,
        from_id=sender, to_id=recipient, aggregation={'kind':'non_aggregating'}, provenance=PROVENANCE)
        for rid,kind,sender,recipient in [('channel:owner','ownership','local-authority','bridge'),
            ('school:message','information_channel','local-authority','cohort:a'),
            ('clinic:message','information_channel','local-authority','cohort:b')]]
    return WorldGraph(base.registry, [*base.relationships, *relationships])


def units():
    return Registry((Unit('messages', (('message_slot',1),), 'capacity', Decimal(1)),))


def request():
    return dict(contract_version=1, scope_id='local', period_id='day:0',
        batch=dict(contract_version=1,
            accounts=[capacity(a,n) | {'unit_id':'messages'} for a,n in [('channel',3),('verification',2)]],
            claims=[claim('school:notice','channel',2,'cohort:a'), claim('clinic:notice','channel',2,'cohort:b')],
            postings=[], reservations=[], subtotals=[]),
        channels=[dict(asset_id='bridge',controller_id='local-authority',ownership_relationship_id='channel:owner',
            account_id='channel',availability='operating',source_refs=['synthetic:channel'])],
        demands=[dict(claim_id=f+':notice',message_ref='synthetic:'+f+':notice',channel_asset_id='bridge',
            sender_id='local-authority',recipient_id=c,channel_relationship_id=f+':message',
            recorded=True,available=True,publish_access='allowed',receive_access='allowed',disclosure='allowed',
            access_limit='2',verification_account_id='verification',verification_procedure_ref='synthetic:check',
            delay_ticks=3,obligation_refs=['synthetic:disclosure-duty'],source_refs=['synthetic:message'])
            for f,c in [('school','cohort:a'),('clinic','cohort:b')]],
        procedure='priority',claim_order=['school:notice','clinic:notice'],
        mechanism_ref='authored:communication-prerequisites-v1',source_refs=['synthetic:communication'])


def run(data=None, graph=None, registry=None):
    return evaluate_communication(CommunicationRequest.model_validate(request() if data is None else data),
        graph=world() if graph is None else graph,units=units() if registry is None else registry)


def test_shared_channel_and_verification_with_detached_evidence():
    data=request(); before=deepcopy(data); result=run(data)
    assert [r.additional for r in result.results] == ['2','0']
    assert [r.outcome for r in result.results] == ['capacity_ready','blocked']
    assert result.results[1].findings == ['capacity_shortfall']
    assert {a.account_id:a.closing for a in result.allocation.accounts.accounts} == {'channel':'1','verification':'0'}
    assert result.request.model_dump() == data == before
    data['demands'][0]['obligation_refs'].append('later')
    assert result.request.demands[0].obligation_refs == ['synthetic:disclosure-duty']
    assert result.request.demands[0].delay_ticks == 3
    assert 'delivered' not in result.model_dump() and 'verified' not in result.model_dump()


def test_independent_exhaustive_finite_integer_oracle():
    for channel,verification,school,clinic in product(range(3),range(3),range(1,4),range(1,4)):
        data=request()
        data['batch']['accounts'][0]['opening']=str(channel)
        data['batch']['accounts'][1]['opening']=str(verification)
        data['batch']['claims'][0]['requested']=str(school)
        data['batch']['claims'][1]['requested']=str(clinic)
        for demand in data['demands']:
            demand['access_limit']='3'
        feasible=[(s,c) for s in range(school+1) for c in range(clinic+1)
            if s+c <= channel and s+c <= verification]
        expected=max(feasible)
        assert tuple(int(r.additional) for r in run(data).results) == expected


@pytest.mark.parametrize('field', ['publish_access','receive_access','disclosure'])
def test_denial_distinct_from_absent_reach(field):
    data=request(); data['demands'][0][field]='denied'
    result=run(data)
    assert result.results[0].findings == [field+'_denied']
    assert result.results[1].additional == '2'
    data['demands'][0]['channel_relationship_id']=None
    assert run(data).results[0].findings == ['no_declared_channel_reach',field+'_denied']


@pytest.mark.parametrize('field', ['recorded','available','publish_access','receive_access','disclosure','delay_ticks','availability','procedure'])
def test_unknowns_withhold_all_competitors(field):
    data=request()
    if field == 'availability': data['channels'][0][field]='unknown'
    elif field == 'procedure': data[field]=None
    else: data['demands'][0][field]='unknown' if 'access' in field or field=='disclosure' else None
    result=run(data)
    assert result.status == 'unresolved' and result.allocation.batch.postings == []
    assert all(r.additional is None and r.unmet is None for r in result.results)


@pytest.mark.parametrize('field', ['recorded','available'])
def test_recorded_and_available_are_independent_prerequisites(field):
    data=request(); data['demands'][0][field]=False
    assert run(data).results[0].findings == ['not_'+field]
    assert run(data).results[1].additional == '2'


def test_explicit_priority_and_all_or_nothing():
    data=request(); data['claim_order'].reverse()
    assert [r.additional for r in run(data).results] == ['0','2']
    data['batch']['accounts'][1]['opening']='3'
    assert [r.additional for r in run(data).results] == ['1','2']
    data['procedure']='all_or_nothing'
    assert [r.additional for r in run(data).results] == ['0','2']


def test_verification_is_optional_but_never_inferred():
    data=request()
    for d in data['demands']:
        d['verification_account_id']=None; d['verification_procedure_ref']=None
    data['batch']['accounts'].pop()
    assert [r.additional for r in run(data).results] == ['2','1']
    data['demands'][0]['verification_procedure_ref']='synthetic:check'
    with pytest.raises(AccountError,match='incomplete_communication_verification'): run(data)


def test_reservations_replay_and_changed_declarations_preserve_commitments():
    data=request()
    data['batch']['reservations']=[dict(id='hold',account_id='channel',claim_id='clinic:notice',amount='2')]
    first=run(data)
    assert [r.additional for r in first.results] == ['1','1']
    data['batch']=first.allocation.batch.model_dump()
    second=run(data)
    assert second.allocation.batch == first.allocation.batch
    assert [r.additional for r in second.results] == ['0','0']
    assert [r.prior for r in second.results] == ['1','1']
    data['channels'][0]['availability']='offline'
    assert run(data).allocation.batch == first.allocation.batch


@pytest.mark.parametrize('change,error', [
    ('duplicate_channel','duplicate_or_unmapped'),('duplicate_demand','invalid_communication_demands'),
    ('control','invalid_communication_control'),('reach','invalid_communication_reach'),
    ('recipient','invalid_communication_claim'),('period','invalid_communication_capacity'),
    ('scope','invalid_communication_capacity'),
    ('role_overlap','duplicate_or_unmapped'),('zero','invalid_communication_claim')])
def test_invalid_inputs(change,error):
    data=request()
    if change=='duplicate_channel': data['channels'].append(deepcopy(data['channels'][0]))
    if change=='duplicate_demand': data['demands'].append(deepcopy(data['demands'][0]))
    if change=='control': data['channels'][0]['ownership_relationship_id']='school:message'
    if change=='reach': data['demands'][0]['channel_relationship_id']='clinic:message'
    if change=='recipient': data['demands'][0]['recipient_id']='cohort:b'
    if change=='period': data['batch']['accounts'][0]['period_id']='day:1'
    if change=='scope': data['batch']['accounts'][0]['scope_id']='region'
    if change=='role_overlap': data['demands'][0]['verification_account_id']='channel'
    if change=='zero': data['batch']['claims'][0]['requested']='0'
    with pytest.raises(AccountError,match=error): run(data)


def test_wrong_dimension_scale_and_decimal_context():
    data=request()
    wrong=Registry((Unit('messages', (('time',1),), 'capacity', Decimal(1)),))
    with pytest.raises(AccountError,match='invalid_communication_capacity'): run(data,registry=wrong)
    scaled=Registry((*units().units,Unit('scaled',(('message_slot',1),),'capacity',Decimal(2))))
    data['batch']['accounts'][1]['unit_id']='scaled'
    with pytest.raises(AccountError,match='incompatible_communication_units'): run(data,registry=scaled)
    with localcontext() as context:
        context.prec=2
        assert [r.additional for r in run().results] == ['2','0']


def test_negative_delay_and_payload_fields_rejected_and_mutable_dto_revalidated():
    data=request(); data['demands'][0]['delay_ticks']=-1
    with pytest.raises(ValidationError): run(data)
    data=request(); data['demands'][0]['payload']='private message'
    with pytest.raises(ValidationError): run(data)
    dto=CommunicationRequest.model_validate(request()); dto.demands[0].__dict__['delay_ticks']=-1
    with pytest.raises(ValidationError): evaluate_communication(dto,graph=world(),units=units())


def test_nonmatching_quantum_retains_unspent_capacity():
    data=request()
    data['batch']['accounts'][0].update(opening='3',quantum='0.1')
    data['batch']['accounts'][1].update(opening='3',quantum='1')
    for claim_dto in data['batch']['claims']:
        claim_dto['requested']='1.5'
    result=run(data)
    assert [r.additional for r in result.results] == ['1','1']
    assert [r.unmet for r in result.results] == ['0.5','0.5']


def test_known_offline_and_unknown_even_when_denied():
    data=request(); data['channels'][0]['availability']='offline'
    assert all(r.additional=='0' and r.findings==['channel_offline'] for r in run(data).results)
    data['demands'][0]['disclosure']='unknown'
    assert run(data).status=='unresolved'


def test_no_implicit_precedence_or_unmapped_accounts():
    data=request(); data['claim_order']=[]
    with pytest.raises(AccountError,match='invalid_claim_order'): run(data)
    data=request(); data['batch']['accounts'].append(capacity('extra',2) | {'unit_id':'messages'})
    with pytest.raises(AccountError,match='duplicate_or_unmapped'): run(data)
