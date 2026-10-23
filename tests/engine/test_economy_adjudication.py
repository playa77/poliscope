"""Real DOM-02/04 composition with independent finite-book and legal prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.economy_adjudication import EconomyAdjudicationRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.economy.adjudication import evaluate_pair, binding
from poliscope_engine.domains.economy.adjudication_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from economy_adjudication_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-economy-adjudication',
        'oracle:economy-adjudication-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def books(data):
    return (data['request']['adjudication']['administration'], data['request']['economy'])


def balances(result):
    return {a.account_id: a.closing for a in result.economy.allocation.accounts.accounts}


def claims(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.economy.allocation.accounts.claims}


def actual(result, cid):
    return next(a for a in result.economy.allocation.actuals if a.claim_id == cid)


def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['adjudication']['cases'][0]['disposition']='dismissed'
    r2,_,_,_=setup(data)
    assert binding(r2,g,u,m)!=original
    data=fixture();data['inputs']['entities'][0]['label']='changed'
    _,_,g2,_=setup(data)
    assert binding(r,g2,u,m)!=original
    changed=[replace(reviews()[0],evidence_review_ref='review:other'),*reviews()[1:]]
    assert binding(r,g,u,policy_registry(units=u,reviews=changed))!=original
    data=fixture();data['units'][0]['scale']='2';_,_,_,u2=setup(data)
    assert binding(r,g,u2,m)!=original


def test_common_conformance_executes_real_pair_repeatedly_without_publication():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    case=ConformanceCase(inputs=i,outcome='incomplete',observations=(
        dict(node=['output','work',WORK],status='partial'),
        dict(node=['output','provision',CANDIDATE],status='partial')),
        trace_edges=((('output','work',WORK),('input','provision',BOOK)),))
    result=run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert result==run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert result.accounts is None
    assert reg.bind(('authored:ea-administration-mechanism','v1'),('authored:ea-economy-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['adjudication']['cases'][0]['disposition']='dismissed';r=EconomyAdjudicationRequest.model_validate(data)
    else:
        data=i.model_dump()
        if change=='world':data['entities'][0]['label']='changed'
        elif change=='version':data['versions']['catalog_id']='foreign:catalog'
        else:rs=(replace(rs[0],evidence_review_ref='other:review'),*rs[1:])
        i=RevisionInputs.model_validate(data)
    with pytest.raises(ConformanceError,match='stale_counterpart_context|counterpart_version_mismatch'):
        run_bound_case(ConformanceCase(inputs=i,outcome='incomplete',observations=()),request=r,units=u,reviews=rs)


def test_callbacks_reject_forged_tokens_and_snapshot_request():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    callbacks={x.id:x.callback for x in reg.implementations}
    work=callbacks['authored:ea-administration'];consumer=callbacks['authored:ea-economy']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.adjudication.cases[0] = r.adjudication.cases[0].model_copy(update={'disposition':'dismissed'})
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})


@pytest.mark.parametrize('missing', ['administration','economy','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:ea-administration-mechanism',
        'economy':'authored:ea-economy-mechanism','policy':'authored:ea-policy-mechanism'}[missing]
    ds={d.id:declaration_digest(d) for d in definitions()}
    rs=[review for review in reviews() if review.declaration_digest!=ds[omit]]
    reg=host_registry(r,graph=g,units=u,reviews=rs)
    with pytest.raises(MechanismError,match='review_required'):
        if missing=='policy':
            evaluate_pair(r,graph=g,units=u,mechanisms=policy_registry(units=u,reviews=rs))
        else:reg.activate(omit,'v1',phase='static',world=g.registry,scope_id='east',entity_id='east-authority')


def test_policy_callback_never_executes_and_nested_results_detach():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews())
    with pytest.raises(AccountError,match='policy_callback_not_executable'):
        m.implementations[0].callback()
    result=evaluate_pair(r,graph=g,units=u,mechanisms=m)
    r.adjudication.cases[0] = r.adjudication.cases[0].model_copy(update={'disposition':'dismissed'});result.batch.postings.clear()
    assert result.request.adjudication.cases[0].disposition=='upheld'
    assert run().batch.postings



def test_literal_shared_book_rights_and_retained_commitments():
    data=fixture(); before=deepcopy(data); result=run(data)
    assert result.status=='resolved' and result.adjudication.results[0].outcome=='upheld'
    assert balances(result)==data['expected']['accounts']
    assert claims(result)==data['expected']['claims']
    assert result.economy.request.batch==result.adjudication.administration.evaluation.batch
    assert result.batch.reservations==result.request.economy.batch.reservations
    assert result.batch.subtotals==result.request.economy.batch.subtotals
    assert sum(p.id=='prior:admin' for p in result.batch.postings)==1
    assert all(actual(result,c).allocated=='0' for c in ['admin','care'])
    assert data==before


def test_independent_finite_feasible_set_time_stock_and_rights_oracle():
    # Exhaustive independently authored integer feasibility sets. One prior hour
    # and a two-hour protected care hold remain in the finite budget throughout.
    for time,stock,rights in product(range(3,10),range(0,7,2),range(0,7,2)):
        data=fixture()
        for phase in books(data):
            for account,value in zip(phase['batch']['accounts'],[time,stock,rights]):
                account['opening']=str(value)
        result=run(data)
        admin=max(a for a in range(1,4) if a+2<=time)
        care=2
        work=max(w for w in range(8) if admin+care+w<=time)
        allowed=admin==3
        goods=max(q for q in range(9) if q<=stock and q<=rights and (allowed or q==0))
        assert {c:int(v[0]) for c,v in claims(result).items()}==dict(admin=admin,care=care,work=work,goods=goods)
        assert {a:int(v) for a,v in balances(result).items()}==dict(labor=time-admin-care-work,stored=stock-goods,rights=rights-goods)
        assert result.adjudication.results[0].outcome==('upheld' if allowed else 'capacity_blocked')


@pytest.mark.parametrize('outcome',['upheld','dismissed','ineligible','capacity_blocked'])
def test_actual_case_outcome_only_restricts_mapped_claim(outcome):
    data=fixture(); case=data['request']['adjudication']['cases'][0]
    if outcome=='dismissed':case['disposition']='dismissed'
    elif outcome=='ineligible':case['eligibility']='ineligible'
    elif outcome=='capacity_blocked':
        for p in books(data):p['batch']['accounts'][0]['opening']='4'
    result=run(data)
    assert result.adjudication.results[0].outcome==outcome
    assert claims(result)['goods'][0]==('5' if outcome=='upheld' else '0')
    assert claims(result)['work'][0]==('5' if outcome!='capacity_blocked' else '0')
    assert result.adjudication.results[0].proposed_obligation_refs==case['obligation_refs']
    assert result.request.adjudication.cases[0].right_ref==case['right_ref']
    assert balances(result)['rights']==('0' if outcome=='upheld' else '5')


@pytest.mark.parametrize('missing',['eligibility','rights_conflict','disposition','rationale','policy','admin_access','admin_terms','admin_procedure','economic_access','economic_terms','economic_procedure'])
def test_unknown_inputs_withhold_complete_candidate_without_fabricating_zero(missing):
    data=fixture(); law=data['request']['adjudication'];case=law['cases'][0];admin,econ=books(data)
    if missing=='eligibility':case['eligibility']='unknown'
    elif missing=='rights_conflict':case['incompatible_right_refs']=['hypothetical:right/conflicting']
    elif missing in ('disposition','rationale'):case[missing]=None
    elif missing=='policy':law['bindings'][0]['value']=dict(kind='unknown',reason='not declared')
    elif missing=='admin_access':admin['activities'][0]['eligibility']='unknown'
    elif missing=='admin_terms':admin['activities'][0]['terms_known']=False
    elif missing=='admin_procedure':admin['procedure']=None
    elif missing=='economic_access':econ['activities'][-1]['eligibility']='unknown'
    elif missing=='economic_terms':econ['activities'][-1]['terms_known']=False
    else:econ['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    if missing.startswith('economic'):
        assert result.adjudication.results[0].outcome=='upheld' and result.economy.batch is None
    else:
        assert result.economy is None and result.adjudication.results[0].outcome is None
        if not missing.startswith('admin'):
            assert result.adjudication.administration.indicators[0].actual=='2'


@pytest.mark.parametrize('disposition',['upheld','dismissed'])
@pytest.mark.parametrize('eligibility',['denied','unknown'])
def test_case_cannot_override_original_economic_access(disposition,eligibility):
    data=fixture();data['request']['adjudication']['cases'][0]['disposition']=disposition
    data['request']['economy']['activities'][-1]['eligibility']=eligibility
    result=run(data)
    if eligibility=='unknown':assert result.batch is None
    else:assert claims(result)['goods'][0]=='0' and balances(result)['rights']=='5'


@pytest.mark.parametrize('mutation,code',[
    ('book','book_mismatch'),('holders','book_mismatch'),('period','period_mismatch'),
    ('duplicate_economic','invalid_adjudication_counterpart_claims'),
    ('duplicate_mapping','invalid_adjudication_counterpart_claims'),
    ('foreign_economic','invalid_adjudication_counterpart_claims'),
    ('foreign_mapping','invalid_adjudication_counterpart_claims'),
    ('case_work_as_economic','invalid_adjudication_counterpart_claims'),
    ('foreign_case','right_mapping'),('unaffected','right_mapping'),
    ('no_entitlement','right_mapping'),('zero_entitlement_rate','right_mapping'),
    ('wrong_entitlement','right_mapping'),('wrong_claimant','right_mapping'),
    ('wrong_scope','right_mapping'),('not_goods','right_mapping'),
    ('open_future','open_phase_claim'),('open_prior','open_phase_claim'),
    ('missing_activity','invalid_economy_activities'),
    ('foreign_account','account_identity'),('foreign_claimant','claimant_identity'),
    ('foreign_holder','holder_identity'),('missing_time_holder','time_holders'),
    ('period_both','period_mismatch'),
])
def test_invalid_context_and_right_mappings_rejected_without_mutation(mutation,code):
    data=fixture();r=data['request'];law=r['adjudication'];admin,econ=books(data)
    if mutation=='book':econ['batch']['accounts'][0]['opening']='11'
    elif mutation=='holders':econ['holders'].pop()
    elif mutation=='period':econ['period_id']='day:1'
    elif mutation=='duplicate_economic':r['economic_claim_ids'].append('goods')
    elif mutation=='duplicate_mapping':r['prerequisites'].append(deepcopy(r['prerequisites'][0]))
    elif mutation=='foreign_economic':r['economic_claim_ids'].append('foreign')
    elif mutation=='foreign_mapping':r['prerequisites'][0]['claim_id']='care'
    elif mutation=='case_work_as_economic':r['economic_claim_ids'].append('admin')
    elif mutation=='foreign_case':r['prerequisites'][0]['case_id']='foreign'
    elif mutation=='unaffected':law['bindings'][0]['account_refs']=['stored']
    elif mutation=='no_entitlement':econ['activities'][-1]['requirements']=[]
    elif mutation=='zero_entitlement_rate':econ['activities'][-1]['requirements'][0]['per_unit']='0'
    elif mutation=='wrong_entitlement':r['prerequisites'][0]['entitlement_account_id']='labor'
    elif mutation=='wrong_claimant':law['cases'][0]['claimant_id']='east-authority'
    elif mutation=='wrong_scope':
        for p in books(data):p['batch']['accounts'][-1]['scope_id']='west'
    elif mutation=='not_goods':econ['activities'][-1]['kind']='paid_work'
    elif mutation=='open_future':admin['activities'][-1]['eligibility']='allowed'
    elif mutation=='open_prior':econ['activities'][0]['terms_known']=False
    elif mutation=='missing_activity':econ['activities'].pop(0)
    elif mutation=='foreign_account':data['inputs']['entities']=[e for e in data['inputs']['entities'] if e['id']!='rights']
    elif mutation=='foreign_claimant':
        for p in books(data):p['batch']['claims'][-1]['claimant_id']='foreign'
    elif mutation=='foreign_holder':
        for p in books(data):p['holders'][-1]['holder_id']='foreign'
    elif mutation=='missing_time_holder':
        for p in books(data):p['holders'].pop(0)
    else:
        for p in books(data):p['batch']['accounts'][0]['period_id']='day:1'
    before=deepcopy(data)
    with pytest.raises(AccountError,match=code):run(data)
    assert data==before


def test_replay_retains_prior_fulfillment_even_after_later_dismissal():
    data=fixture();first=run(data)
    for p in books(data):p['batch']=first.batch.model_dump()
    second=run(data)
    assert second.batch==first.batch
    data['request']['adjudication']['cases'][0]['disposition']='dismissed'
    rejected=run(data)
    assert rejected.batch==first.batch
    assert claims(rejected)['goods']==['5','3']
    assert actual(rejected,'goods').allocated=='0'


@pytest.mark.parametrize('scope',['east','region'])
def test_explicit_local_and_regional_scope(scope):
    data=fixture()
    if scope=='region':
        for p in books(data):
            for a in p['batch']['accounts']:a['scope_id']='region'
        law=data['request']['adjudication'];law['scope_id']='region'
        law['cases'][0]['authority_id']='region-authority'
        law['bindings'][0].update(scope_id='region',authority_id='region-authority')
    assert balances(run(data))==data['expected']['accounts']


@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('economic_claim_ids',[]),('economic_claim_ids','goods')])
def test_strict_pair_contract(field,value):
    data=fixture();data['request'][field]=value
    with pytest.raises(ValidationError):run(data)


def two_cases():
    data=fixture();r=data['request'];law=r['adjudication']
    c=deepcopy(law['cases'][0]);c.update(id='case:second',work_claim_ids=['case:work'],disposition='dismissed');law['cases'].append(c)
    for p in books(data):
        cl=deepcopy(p['batch']['claims'][0]);cl.update(id='case:work',requested='3');p['batch']['claims'].append(cl)
        cl=deepcopy(p['batch']['claims'][-2]);cl['id']='goods:second';p['batch']['claims'].append(cl)
        a=deepcopy(p['activities'][0]);a.update(claim_id='case:work');p['activities'].append(a)
        a=deepcopy(p['activities'][3]);a['claim_id']='goods:second';p['activities'].append(a)
        p['claim_order']=['admin','case:work','care','work','goods','goods:second']
    r['economic_claim_ids'].append('goods:second')
    r['prerequisites'].append(dict(claim_id='goods:second',case_id='case:second',entitlement_account_id='rights'))
    return data


def test_multiple_cases_keep_explicit_per_claim_disposition_and_shared_work():
    data=two_cases();result=run(data)
    assert [c.outcome for c in result.adjudication.results]==['upheld','dismissed']
    assert claims(result)['case:work']==['3','0']
    assert claims(result)['work']==['2','5']
    assert claims(result)['goods']==['5','3'] and claims(result)['goods:second']==['0','8']
    data['request']['adjudication']['cases'].reverse()
    assert balances(run(data))==balances(result) and claims(run(data))==claims(result)
    data['request']['adjudication']['cases'][0]['eligibility']='unknown'
    unresolved=run(data)
    assert unresolved.batch is None and unresolved.economy is None
    assert unresolved.adjudication.results[1].outcome=='upheld'


def test_shared_case_does_not_multiply_entitlements_or_case_work():
    data=two_cases();law=data['request']['adjudication']
    law['cases'].pop();data['request']['prerequisites'][-1]['case_id']='case:access'
    result=run(data)
    assert claims(result)['goods']==['5','3'] and claims(result)['goods:second']==['0','8']
    assert balances(result)['rights']=='0'
    data['request']['economy']['claim_order'][-2:]=['goods:second','goods']
    result=run(data)
    assert claims(result)['goods:second']==['5','3'] and claims(result)['goods']==['0','8']


def test_institutional_conflict_requires_explicit_selected_case_binding():
    data=fixture();law=data['request']['adjudication'];b=deepcopy(law['bindings'][0]);b['id']='competing'
    b['value']['value']='different';law['bindings'].append(b)
    result=run(data)
    assert result.batch is None and 'institutional_conflict' in result.adjudication.results[0].findings


@pytest.mark.parametrize('rate,rights,expected',[('2','5','2'),('0.5','3','6'),('3','0','0')])
def test_positive_entitlement_rates_constrain_goods_without_creating_supply(rate,rights,expected):
    data=fixture()
    for phase in books(data):phase['batch']['accounts'][-1]['opening']=rights
    data['request']['economy']['activities'][-1]['requirements'][0]['per_unit']=rate
    result=run(data)
    assert claims(result)['goods'][0]==expected
    assert Fraction(balances(result)['rights'])+Fraction(rate)*Fraction(expected)==Fraction(rights)
    assert Fraction(balances(result)['stored'])+Fraction(expected)==12


def test_funding_is_separate_from_entitlements_and_physical_supply():
    data=fixture()
    for phase in books(data):
        account=deepcopy(phase['batch']['accounts'][-1]);account.update(id='funding',opening='6')
        phase['batch']['accounts'].append(account)
        phase['holders'].append(dict(account_id='funding',holder_id='shared:cohort',role='funding'))
    entity=deepcopy(data['inputs']['entities'][-1]);entity.update(id='funding',entity_kind='account')
    data['inputs']['entities'].append(entity)
    data['request']['economy']['activities'][-1]['requirements'].append(dict(account_id='funding',per_unit='2',kind='funding'))
    result=run(data)
    assert claims(result)['goods']==['3','5']
    assert balances(result)==dict(labor='0',stored='9',rights='2',funding='0')


def test_future_stock_hold_survives_both_phases():
    data=fixture()
    for phase in books(data):
        c=deepcopy(phase['batch']['claims'][-1]);c.update(id='future',requested='9')
        phase['batch']['claims'].append(c)
        phase['batch']['reservations'].append(dict(id='hold:future',account_id='stored',claim_id='future',amount='9'))
        a=deepcopy(phase['activities'][-1]);a.update(claim_id='future',eligibility='denied',access_limit='0',requirements=[])
        phase['activities'].append(a);phase['claim_order'].append('future')
    result=run(data)
    assert claims(result)['goods']==['3','5'] and balances(result)['stored']=='9'
    assert result.batch.reservations==result.request.economy.batch.reservations


def test_scaled_time_unit_does_not_create_work():
    data=fixture()
    data['units'].append(dict(id='days',dimension=[['time',1]],kind='capacity',scale='86400'))
    # Independent one-day scenario uses exact decimal fractions of a capacity
    # unit with a different scale; prior work and care holds use that unit too.
    for phase in books(data):
        a=phase['batch']['accounts'][0];a.update(unit_id='days',opening='1',quantum='0.001')
        for c,v in zip(phase['batch']['claims'][:3],['0.375','0.25','0.875']):c['requested']=v
        phase['batch']['postings'][0]['amount']='0.125'
        phase['batch']['reservations'][0]['amount']='0.25'
    result=run(data)
    assert claims(result)['admin']==['0.375','0']
    assert claims(result)['care']==['0.25','0']
    assert claims(result)['work']==['0.375','0.5']
    assert sum(Fraction(claims(result)[c][0]) for c in ['admin','care','work'])==1
    assert claims(result)['goods']==['5','3']


def test_all_or_nothing_cannot_treat_partial_case_work_as_upheld():
    data=fixture()
    for phase in books(data):phase['batch']['accounts'][0]['opening']='4'
    data['request']['adjudication']['administration']['procedure']='all_or_nothing'
    result=run(data)
    assert result.adjudication.results[0].outcome=='capacity_blocked'
    assert claims(result)['admin']==['1','2'] and claims(result)['care']==['2','0']
    assert claims(result)['goods']==['0','8'] and claims(result)['work']==['1','6']


def test_prior_goods_debit_and_independent_import_are_preserved_once():
    data=fixture()
    for phase in books(data):
        phase['batch']['postings'].extend([
            dict(id='prior:goods',kind='use',source_id='stored',destination_id=None,amount='2',claim_id='goods',reservation_id=None,mechanism_ref='synthetic:prior',source_refs=['synthetic:prior']),
            dict(id='prior:rights',kind='use',source_id='rights',destination_id=None,amount='2',claim_id=None,reservation_id=None,mechanism_ref='synthetic:prior',source_refs=['synthetic:prior']),
            dict(id='prior:import',kind='import',source_id=None,destination_id='stored',amount='3',claim_id=None,reservation_id=None,mechanism_ref='synthetic:prior',source_refs=['synthetic:prior'])])
    result=run(data)
    assert claims(result)['goods']==['5','3']
    assert actual(result,'goods').allocated=='3'
    assert balances(result)['stored']=='10' and balances(result)['rights']=='0'
    assert all(sum(p.id==pid for p in result.batch.postings)==1 for pid in ['prior:goods','prior:rights','prior:import'])


@pytest.mark.parametrize('selected,outcome',[('proposal','upheld'),('competing',None)])
def test_explicit_conflict_resolution_cannot_substitute_another_ruling(selected,outcome):
    data=fixture();law=data['request']['adjudication'];b=deepcopy(law['bindings'][0]);b['id']='competing'
    b['value']['value']='different';law['bindings'].append(b)
    law['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
        authority_id='east-authority',scope_id='east',entity_id='stored',parameter_id='ea:permission',
        participant_ids=['proposal','competing'],operation='select',selected_id=selected,source_refs=['authored:economy-adjudication-v1'])]
    result=run(data)
    assert result.adjudication.results[0].outcome==outcome
    if outcome is None:
        assert result.batch is None and result.adjudication.results[0].findings==['adjudication_binding_not_selected']
    else:assert balances(result)==data['expected']['accounts']
