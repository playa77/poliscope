"""Actual finite reach and chain gates; independent slot and mass/time oracles."""
from copy import deepcopy
from fractions import Fraction
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.provisioning.infrastructure import evaluate_pair
from poliscope_engine.domains.provisioning.infrastructure_counterpart import (
    binding, host_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from provisioning_infrastructure_fixture import fixture, setup, trusted


def run(data=None):
    r,_,g,u=setup(data)
    return evaluate_pair(r,graph=g,units=u)


def case_for(inputs, status='partial'):
    return ConformanceCase(inputs=inputs,outcome='incomplete',observations=(
        dict(node=['output','provision',CANDIDATE],status=status),),
        trace_edges=((('output','work',WORK),('input','provision',BOOK)),))


def test_literal_chain_and_separate_slot_book_are_pure_and_repeatable():
    data=fixture();before=deepcopy(data);result=run(data)
    assert data==before and result==run(data) and result.status=='resolved'
    assert {a.account_id:a.closing for a in result.provisioning.provisioning.accounts.accounts}==data['expected']['accounts']
    assert {c.claim_id:[c.actual,c.unmet] for c in result.provisioning.provisioning.accounts.claims}==data['expected']['claims']
    assert {r.claim_id:r.additional for r in result.infrastructure.results}=={f'reach:{p}':'1' for p in ['make','deliver','store','eat']}
    assert {a.account_id:a.closing for a in result.infrastructure.allocation.accounts.accounts}=={a:'1' for a in ['depot:slots','bridge:slots','road:slots']}
    assert sum(p.id=='prior:care' for p in result.batch.postings)==1
    assert result.batch.reservations==result.request.provisioning.work.batch.reservations
    assert result.batch.subtotals==result.request.provisioning.work.batch.subtotals
    assert not {a.id for a in result.infrastructure.allocation.batch.accounts}&{a.id for a in result.batch.accounts}
    b={a.account_id:Fraction(a.closing) for a in result.provisioning.provisioning.accounts.accounts}
    assert sum(b[a] for a in ['raw','product','residual','receiving','stored'])+1+1==20
    result.infrastructure.request.demands.clear();result.batch.postings.clear()
    assert run().infrastructure.request.demands and run().batch.postings


@pytest.mark.parametrize('capacity',range(0,8))
@pytest.mark.parametrize('reverse',[False,True])
def test_independent_shared_path_and_material_oracle(capacity,reverse):
    data=fixture();infra=data['request']['infrastructure']
    next(a for a in infra['batch']['accounts'] if a['id']=='bridge:slots')['opening']=str(capacity)
    if reverse:infra['claim_order'].reverse()
    result=run(data)
    remaining=capacity;expected={}
    for cid in infra['claim_order']:
        expected[cid]=min(1,remaining);remaining-=expected[cid]
    assert {r.claim_id:int(r.additional) for r in result.infrastructure.results}==expected
    assert {a.account_id:int(a.closing) for a in result.infrastructure.allocation.accounts.accounts}=={
        'depot:slots':5-min(capacity,4),'bridge:slots':max(0,capacity-4),'road:slots':5-min(capacity,4)}
    # Independent integer oracle: care/training leave 6 h; production uses 5 h,
    # freight uses 1/2 h per kg, storage max 3 kg, entitlement permits 1 kg use.
    made=10 if expected['reach:make'] else 0
    shipped=min(made*7//10,2) if expected['reach:deliver'] else 0
    stored=min(3,shipped) if expected['reach:store'] else 0
    used=min(1,stored) if expected['reach:eat'] else 0
    actual={c.claim_id:int(c.actual) for c in result.provisioning.provisioning.accounts.claims}
    assert actual=={'care':3,'training':3,'make-food':made,'ship-food':shipped,'store-food':stored,'eat-food':used}
    b={a.account_id:Fraction(a.closing) for a in result.provisioning.provisioning.accounts.accounts}
    assert b['labor']==6-Fraction(made,2)-Fraction(shipped,2)
    assert sum(b[a] for a in ['raw','product','residual','receiving','stored'])+made//10+used==20


@pytest.mark.parametrize('unknown',['availability','access','procedure','work','production','freight','storage','use'])
def test_unknowns_withhold_complete_candidate(unknown):
    data=fixture();r=data['request'];infra=r['infrastructure'];p=r['provisioning']
    if unknown=='availability':infra['links'][0]['availability']='unknown'
    if unknown=='access':infra['demands'][0]['access']='unknown'
    if unknown=='procedure':infra['procedure']=None;infra['claim_order']=[]
    if unknown=='work':p['work']['activities'][0]['terms_known']=False
    if unknown in ('production','freight','storage'):
        phase=next(x for x in p['chain']['phases'] if x['kind']==unknown)
        phase['routes' if unknown=='freight' else 'choices'][0]['funding_known']=False
    if unknown=='use':p['use_terms'][0]['activities'][0]['eligibility']='unknown'
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    if unknown in ('availability','access','procedure'):assert result.provisioning is None
    else:assert result.infrastructure.status=='resolved'


@pytest.mark.parametrize('blocked',['denied','planned','offline','retired','disconnected'])
def test_blocked_reach_preserves_named_evidence_and_independent_work(blocked):
    data=fixture();infra=data['request']['infrastructure']
    if blocked=='denied':infra['demands'][0]['access']='denied'
    elif blocked=='disconnected':infra['demands'][0].update(origin_id='island',path=[])
    else:infra['facilities'][0]['availability']=blocked
    result=run(data)
    assert result.status=='resolved'
    assert result.infrastructure.results[0].findings==[{'denied':'access_denied','disconnected':'disconnected'}.get(blocked,'nonoperating_asset')]
    assert next(c for c in result.provisioning.provisioning.accounts.claims if c.claim_id=='make-food').actual=='0'
    assert next(c for c in result.provisioning.work.allocation.accounts.claims if c.claim_id=='care').actual=='3'


def test_prior_commitment_and_hold_survive_once_but_do_not_prove_current_reach():
    data=fixture();infra=data['request']['infrastructure'];b=infra['batch']
    # Use an authentic allocation posting as a retained prior event. The fixture
    # quantities and expected balances are independent of the allocator result.
    first=run(data).infrastructure.allocation.batch
    b['postings']=[p.model_dump(mode='json') for p in first.postings if p.id in ['allocation:0','allocation:1','allocation:2']]
    result=run(data)
    assert result.infrastructure.results[0].prior=='1' and result.infrastructure.results[0].additional=='0'
    assert len(result.infrastructure.allocation.batch.postings)==12
    assert {a.account_id:a.closing for a in result.infrastructure.allocation.accounts.accounts}=={a:'1' for a in ['depot:slots','bridge:slots','road:slots']}
    infra['demands'][0]['access']='denied';result=run(data)
    assert result.infrastructure.results[0].prior=='1'
    assert next(c for c in result.provisioning.provisioning.accounts.claims if c.claim_id=='make-food').actual=='0'


@pytest.mark.parametrize('change,code',[
    ('period','infrastructure_counterpart_period_mismatch'),('pool','infrastructure_counterpart_pool_collision'),
    ('account','infrastructure_counterpart_account_identity'),('missing','incomplete_infrastructure_counterpart_prerequisites'),
    ('duplicate','invalid_infrastructure_counterpart_prerequisite'),('claim','invalid_infrastructure_counterpart_prerequisite'),
    ('phase','invalid_infrastructure_counterpart_prerequisite'),('demand','unknown_infrastructure_counterpart_demand'),
    ('duplicate_demand','invalid_infrastructure_counterpart_prerequisite'),('book','counterpart_batch_mismatch'),
    ('path','incomplete_infrastructure_path')])
def test_invalid_bindings_reject_without_mutation(change,code):
    data=fixture();r=data['request'];infra=r['infrastructure'];req=r['prerequisites']
    if change=='period':infra['period_id']='day:1'
    if change=='pool':infra['batch']['claims'][0]['id']='make-food'
    if change=='account':infra['batch']['accounts'][0]['id']='unregistered'
    if change=='missing':req.pop()
    if change=='duplicate':req.append(deepcopy(req[0]))
    if change=='claim':req[0]['claim_id']='unknown'
    if change=='phase':req[0]['phase_id']='unknown'
    if change=='demand':req[0]['demand_ids']=['unknown']
    if change=='duplicate_demand':req[0]['demand_ids']*=2
    if change=='book':r['provisioning']['chain']['batch']['postings'][0]['amount']='2'
    if change=='path':infra['demands'][0]['path']=[]
    before=deepcopy(data)
    with pytest.raises(AccountError,match=code):run(data)
    assert data==before


def test_common_conformance_is_repeatable_and_review_gated():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);case=case_for(i)
    first=run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert first==run_bound_case(case,request=r,units=u,reviews=reg.reviews) and first.accounts is None
    unreviewed=host_registry(r,graph=g,units=u,reviews=[])
    with pytest.raises(MechanismError,match='review_required'):
        unreviewed.activate('authored:infrastructure-pair-work-mechanism','v1',phase='static',world=g.registry,scope_id='east',entity_id='east-authority')


@pytest.mark.parametrize('unknown',['access','use'])
def test_common_unknown_propagates(unknown):
    data=fixture()
    if unknown=='access':data['request']['infrastructure']['demands'][0]['access']='unknown'
    else:data['request']['provisioning']['use_terms'][0]['activities'][0]['terms_known']=False
    r,i,g,u=setup(data);reg,i=trusted(r,i,g,u)
    assert run_bound_case(case_for(i,'missing_input'),request=r,units=u,reviews=reg.reviews).accounts is None


def test_opaque_host_rejects_stale_tokens_and_snapshots_request():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);callbacks={x.id:x.callback for x in reg.implementations}
    work=callbacks['authored:infrastructure-pair-work'];provision=callbacks['authored:infrastructure-pair-provisioning']
    with pytest.raises(AccountError,match='stale_counterpart_context'):work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'):provision(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=binding(r,g,u))})
    first=provision(CANDIDATE,{BOOK:LabelValue(**token)})
    r.infrastructure.demands.clear()
    assert provision(CANDIDATE,{BOOK:LabelValue(**token)})==first


@pytest.mark.parametrize('field',['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_runtime_identity_rejects(field):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    i=i.model_copy(update={'versions':i.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):
        run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)


def test_changed_request_cannot_reuse_bound_conformance_context():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);r.infrastructure.demands[0]=r.infrastructure.demands[0].model_copy(update={'access':'denied'})
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)


def test_forged_nested_dto_rejects():
    r,_,g,u=setup();r.prerequisites.append({'forged':True})
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u)


def test_reach_never_overrides_unknown_or_denied_goods_access():
    for eligibility in ['denied','unknown']:
        data=fixture();data['request']['provisioning']['use_terms'][0]['activities'][0]['eligibility']=eligibility
        result=run(data)
        if eligibility=='unknown':assert result.batch is None
        else:assert next(c for c in result.provisioning.provisioning.accounts.claims if c.claim_id=='eat-food').actual=='0'


def test_multiple_explicit_prerequisites_all_required():
    data=fixture();data['request']['prerequisites'][0]['demand_ids'].append('reach:eat')
    data['request']['infrastructure']['demands'][-1]['access']='denied'
    result=run(data)
    assert result.infrastructure.results[0].additional=='1'
    assert next(c for c in result.provisioning.provisioning.accounts.claims if c.claim_id=='make-food').actual=='0'


def test_holds_survive_and_protect_later_reach_from_earlier_competitors():
    data=fixture();b=data['request']['infrastructure']['batch']
    next(a for a in b['accounts'] if a['id']=='depot:slots')['opening']='2'
    b['reservations']=[dict(id='hold:eat',account_id='depot:slots',claim_id='reach:eat',amount='1')]
    result=run(data)
    assert {r.claim_id:r.additional for r in result.infrastructure.results}=={
        'reach:make':'1','reach:deliver':'0','reach:store':'0','reach:eat':'1'}
    assert result.infrastructure.allocation.batch.reservations==result.request.infrastructure.batch.reservations
    assert sum(p.reservation_id=='hold:eat' for p in result.infrastructure.allocation.batch.postings)==1
    assert next(a for a in result.infrastructure.allocation.accounts.accounts if a.account_id=='depot:slots').closing=='0'


def test_missing_capacity_is_rejected_instead_of_coerced_to_zero():
    data=fixture();data['request']['infrastructure']['batch']['accounts'][0]['opening']=None
    with pytest.raises(ValidationError):run(data)


@pytest.mark.parametrize('where',['production','freight','storage','use'])
def test_blocked_reach_cannot_erase_an_independent_unknown(where):
    data=fixture();r=data['request'];p=r['provisioning']
    r['infrastructure']['facilities'][0]['availability']='offline'
    if where=='use':p['use_terms'][0]['activities'][0]['eligibility']='unknown'
    else:
        phase=next(x for x in p['chain']['phases'] if x['kind']==where)
        phase['routes' if where=='freight' else 'choices'][0]['access']='unknown'
    result=run(data)
    assert result.infrastructure.status=='resolved'
    assert result.status=='unresolved' and result.batch is None


def test_partial_slot_commitment_cannot_scale_or_enable_material_throughput():
    data=fixture();infra=data['request']['infrastructure']
    infra['batch']['claims'][0]['requested']='2';infra['demands'][0]['access_limit']='2'
    next(a for a in infra['batch']['accounts'] if a['id']=='bridge:slots')['opening']='1'
    result=run(data);reach=result.infrastructure.results[0]
    assert (reach.additional,reach.unmet,reach.findings)==('1','1',['capacity_shortfall'])
    assert next(c for c in result.provisioning.provisioning.accounts.claims if c.claim_id=='make-food').actual=='0'
    assert next(a for a in result.provisioning.provisioning.accounts.accounts if a.account_id=='raw').closing=='20'


def test_changed_world_cannot_reuse_authored_context():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    entities=list(i.entities)
    entities[0]=entities[0].model_copy(update={'label':'Changed world label'})
    i=i.model_copy(update={'entities':entities})
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)
