"""Real DOM-04/06 composition with independent finite-book and education prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.adjudication_education import AdjudicationEducationRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.law_conflict.education import evaluate_pair, binding
from poliscope_engine.domains.law_conflict.education_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from adjudication_education_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-adjudication-education',
        'oracle:adjudication-education-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def books(data):
    return (data['request']['adjudication']['administration'], data['request']['education']['work'])


def balances(result):
    return {a.account_id: a.closing for a in result.education.work.evaluation.allocation.accounts.accounts}


def claims(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.education.work.evaluation.allocation.accounts.claims}


def actual(result, cid):
    return next(a for a in result.education.work.evaluation.allocation.actuals if a.claim_id == cid)


def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['education']['services'][0]['eligibility']='denied'
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
    assert reg.bind(('authored:ae-administration-mechanism','v1'),('authored:ae-education-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['education']['services'][0]['eligibility']='denied';r=AdjudicationEducationRequest.model_validate(data)
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
    work=callbacks['authored:ae-administration'];consumer=callbacks['authored:ae-education']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.education.services[0] = r.education.services[0].model_copy(update={'eligibility':'denied'})
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})


@pytest.mark.parametrize('missing', ['administration','economy','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:ae-administration-mechanism',
        'economy':'authored:ae-education-mechanism','policy':'authored:ae-policy-mechanism'}[missing]
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
    r.education.services[0] = r.education.services[0].model_copy(update={'eligibility':'denied'});result.batch.postings.clear()
    assert result.request.education.services[0].eligibility=='allowed'
    assert run().batch.postings



def test_literal_finite_book_retains_prior_work_and_facility_commitments():
    data=fixture();before=deepcopy(data);result=run(data)
    assert result.status=='resolved' and result.adjudication.results[0].outcome=='upheld'
    assert result.education.results[0].outcome=='capacity_ready'
    assert balances(result)==data['expected']['closing']
    assert claims(result)==data['expected']['claims']
    assert {a.claim_id:[a.actual,a.unmet] for a in result.education.facility_allocation.accounts.claims}==data['expected']['facility']
    assert result.education.request.work.batch==result.adjudication.administration.evaluation.batch
    assert result.batch.reservations==result.request.education.work.batch.reservations
    assert result.batch.subtotals==result.request.education.work.batch.subtotals
    assert sum(p.id=='prior:admin' for p in result.batch.postings)==1
    assert sum(p.id=='prior:care' for p in result.batch.postings)==1
    assert data==before and run(data)==result


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_independent_integer_feasible_set(procedure):
    # Independently enumerate finite feasible case-work allocations then the ordered service
    # claims. Care's hold 2 includes prior 1; admin's prior 1 is retained.
    for time in range(4,21):
        data=fixture()
        for phase in books(data):
            next(a for a in phase['batch']['accounts'] if a['id']=='labor')['opening']=str(time)
            phase['procedure']=procedure
        result=run(data)
        admin=max(x for x in range(1,4) if x+2<=time and (procedure=='priority' or x in (1,3)))
        care=max(x for x in range(1,4) if x+admin<=time and (procedure=='priority' or x in (1,3)))
        remaining=time-admin-care-max(0,2-care)
        training=max(x for x in range(4) if x<=remaining and (admin==3 or x==0) and (procedure=='priority' or x in (0,3)))
        remaining-=training
        teach=max(x for x in range(3) if x<=remaining and (admin==3 or x==0) and (procedure=='priority' or x in (0,2)))
        remaining-=teach
        employment=max(x for x in range(9) if x<=remaining and (procedure=='priority' or x in (0,8)))
        expected={'admin':admin,'care':care,'training':training,'teach':teach,'employment':employment}
        for cid,value in expected.items():assert Fraction(claims(result)[cid][0])==value
        assert Fraction(balances(result)['labor'])==time-sum(expected.values())


@pytest.mark.parametrize('outcome',['upheld','dismissed','ineligible','capacity_blocked'])
@pytest.mark.parametrize('independent',[False,True])
def test_case_only_restricts_explicit_dependent_services(outcome,independent):
    data=fixture();legal=data['request']['adjudication'];case=legal['cases'][0]
    if outcome=='dismissed':case['disposition']='dismissed'
    elif outcome=='ineligible':case['eligibility']='ineligible'
    elif outcome=='capacity_blocked':legal['administration']['activities'][0]['access_limit']='1'
    data['request']['prerequisites'][0]['case_id']=None if independent else 'case:education'
    result=run(data);allowed=independent or outcome=='upheld'
    assert result.adjudication.results[0].outcome==outcome
    for cid,amount in [('training','3'),('teach','2'),('materials','2')]:
        assert claims(result)[cid][0]==(amount if allowed else '0')
    slots={a.claim_id:a.actual for a in result.education.facility_allocation.accounts.claims}
    assert slots['seat']==('2' if allowed else '1')
    assert result.education.results[0].outcome==('capacity_ready' if allowed else 'ineligible')
    assert result.request.education.services[0].knowledge_refs==['synthetic:archive']


@pytest.mark.parametrize('missing',['disposition','eligibility','rights','legal_policy','legal_access',
    'legal_terms','legal_procedure','service','qualification','education_policy','work_access',
    'work_terms','work_procedure','facility_access','facility_funding','facility_procedure'])
def test_unknowns_withhold_candidate_without_erasing_evidence(missing):
    data=fixture();legal=data['request']['adjudication'];edu=data['request']['education'];case=legal['cases'][0]
    if missing=='disposition':case['disposition']=None
    elif missing=='eligibility':case['eligibility']='unknown'
    elif missing=='rights':case['incompatible_right_refs']=['synthetic:competing']
    elif missing=='legal_policy':legal['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='legal_access':legal['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='legal_terms':legal['administration']['activities'][0]['terms_known']=False
    elif missing=='legal_procedure':legal['administration']['procedure']=None
    elif missing=='service':edu['services'][0]['eligibility']='unknown'
    elif missing=='qualification':edu['services'][0]['staff'][0]['qualification']='unknown'
    elif missing=='education_policy':edu['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='work_access':edu['work']['activities'][1]['eligibility']='unknown'
    elif missing=='work_terms':edu['work']['activities'][1]['terms_known']=False
    elif missing=='work_procedure':edu['work']['procedure']=None
    elif missing=='facility_access':edu['facility_allocation']['choices'][0]['access']='unknown'
    elif missing=='facility_funding':edu['facility_allocation']['choices'][0]['funding_known']=False
    else:edu['facility_allocation']['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    assert result.preflight is not None
    if missing.startswith('legal') or missing in ('disposition','eligibility','rights'):assert result.education is None
    else:assert result.education is not None and result.adjudication.results[0].outcome=='upheld'


@pytest.mark.parametrize('approved',[True,False])
@pytest.mark.parametrize('kind',['access','terms','eligibility','qualification','facility'])
def test_upheld_never_replaces_original_unknowns(approved,kind):
    data=fixture();edu=data['request']['education']
    if not approved:data['request']['adjudication']['cases'][0]['disposition']='dismissed'
    if kind=='access':edu['work']['activities'][2]['eligibility']='unknown'
    elif kind=='terms':edu['work']['activities'][2]['terms_known']=False
    elif kind=='eligibility':edu['services'][0]['eligibility']='unknown'
    elif kind=='qualification':edu['services'][0]['staff'][0]['qualification']='unknown'
    else:edu['facility_allocation']['choices'][0]['access']='unknown'
    assert run(data).batch is None


@pytest.mark.parametrize('mutation,code',[
    ('book','book_mismatch'),('holders','book_mismatch'),('period','period_mismatch'),
    ('scope','scope_mismatch'),('missing_mapping','invalid_adjudication_education_mapping'),
    ('duplicate_mapping','invalid_adjudication_education_mapping'),('foreign_mapping','invalid_adjudication_education_mapping'),
    ('target','affected_mapping'),('unaffected','affected_mapping'),('facility_unaffected','affected_mapping'),
    ('open_future','open_phase_claim'),('open_prior','open_phase_claim'),
    ('foreign_account','account_identity'),('foreign_facility','account_identity'),
    ('foreign_claimant','claimant_identity'),('foreign_holder','holder_identity'),
    ('missing_activity','invalid_economy_activities'),('duplicate_work','invalid_adjudication_education_mapping'),
    ('facility_overlap','overlapping_education_pools'),('facility_conversion','invalid_education_facility_choice'),
    ('qualification_refs','missing_education_qualification_reference'),
])
def test_adversarial_contexts_and_original_terms_reject(mutation,code):
    data=fixture();gov=data['request']['adjudication'];edu=data['request']['education'];work=edu['work'];service=edu['services'][0]
    if mutation=='book':work['batch']['accounts'][0]['opening']='21'
    elif mutation=='holders':work['holders']=work['holders'][:1]
    elif mutation=='period':work['period_id']='day:1'
    elif mutation=='scope':edu['scope_id']='west'
    elif mutation=='missing_mapping':data['request']['prerequisites'][0]['service_id']='missing'
    elif mutation=='duplicate_mapping':data['request']['prerequisites']*=2
    elif mutation=='foreign_mapping':data['request']['prerequisites'][0]['service_id']='foreign'
    elif mutation=='target':service['target_id']='water'
    elif mutation=='unaffected':gov['bindings'][0]['account_refs'].remove('labor')
    elif mutation=='facility_unaffected':gov['bindings'][0]['account_refs'].remove('school:slots')
    elif mutation=='open_future':gov['administration']['activities'][2].update(eligibility='allowed',access_limit='3')
    elif mutation=='open_prior':work['activities'][0].update(eligibility='allowed',access_limit='3')
    elif mutation=='foreign_account':
        for p in books(data):p['batch']['accounts'].append(dict(p['batch']['accounts'][0],id='foreign'))
    elif mutation=='foreign_facility':edu['facility_allocation']['batch']['accounts'][0]['id']='foreign'
    elif mutation=='foreign_claimant':
        for p in books(data):p['batch']['claims'][0]['claimant_id']='foreign'
    elif mutation=='foreign_holder':
        for p in books(data):p['holders'][0]['holder_id']='foreign'
    elif mutation=='missing_activity':work['activities'].pop()
    elif mutation=='duplicate_work':service['staff'][0]['claim_id']=service['participants'][0]['claim_id']
    elif mutation=='facility_overlap':
        edu['facility_allocation']['batch']['claims'][0]['id']='admin';service['facility_claim_ids']=['admin']
    elif mutation=='facility_conversion':edu['facility_allocation']['choices'][0]['loss_per_unit']='1'
    else:service['staff'][0]['qualification_refs']=[]
    with pytest.raises((AccountError,ValidationError),match=code):run(data)


def test_replay_retains_all_completed_work_and_seats_once_even_after_rejection():
    first=run();data=fixture()
    for phase in books(data):phase['batch']=first.batch.model_dump()
    data['request']['education']['facility_allocation']['batch']=first.education.facility_allocation.batch.model_dump()
    second=run(data)
    assert second.batch==first.batch
    assert second.education.facility_allocation.batch==first.education.facility_allocation.batch
    data['request']['adjudication']['cases'][0]['disposition']='dismissed'
    rejected=run(data)
    assert rejected.adjudication.results[0].outcome=='dismissed'
    assert rejected.batch==first.batch
    assert rejected.education.facility_allocation.batch==first.education.facility_allocation.batch


@pytest.mark.parametrize('phase',['adjudication','education'])
@pytest.mark.parametrize('selection',[None,'original','competing'])
def test_overlapping_authority_requires_explicit_resolution(phase,selection):
    data=fixture();req=data['request'][phase];original=req['bindings'][0]['id']
    competing=deepcopy(req['bindings'][0]);competing.update(id='competing',authority_id='region-authority',scope_id='region');req['bindings'].append(competing)
    if selection is not None:
        req['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='ae:permission',
            entity_id='shared:cohort',operation='select',participant_ids=[original,'competing'],
            selected_id=original if selection=='original' else 'competing',source_refs=['authored:adjudication-education-v1'])]
    result=run(data)
    if selection=='original':assert result.status=='resolved'
    else:
        assert result.status=='unresolved' and result.batch is None
        findings=result.adjudication.results[0].findings if phase=='adjudication' else result.education.results[0].findings
        assert findings==(['institutional_conflict'] if selection is None else
            ['adjudication_binding_not_selected'] if phase=='adjudication' else ['education_binding_not_selected'])


@pytest.mark.parametrize('approved',[True,False])
def test_multiple_services_declare_independence_and_compete_for_same_resources(approved):
    data=fixture();edu=data['request']['education'];service=deepcopy(edu['services'][0])
    service.update(id='independent',participants=[dict(cohort_id='shared:cohort',claim_id='student:other')],
        staff=[dict(cohort_id='shared:cohort',claim_id='staff:other',qualification='declared',qualification_refs=['synthetic:certificate'])],
        supply_claim_ids=['supply:other'],facility_claim_ids=['other-seat'])
    edu['services'].append(service);data['request']['prerequisites'].append(dict(service_id='independent',case_id=None))
    if not approved:data['request']['adjudication']['cases'][0]['disposition']='dismissed'
    for n,phase in enumerate(books(data)):
        for new,old in [('student:other','training'),('staff:other','teach'),('supply:other','materials')]:
            claim=deepcopy(next(c for c in phase['batch']['claims'] if c['id']==old));claim.update(id=new,requested='1');phase['batch']['claims'].append(claim)
            activity=deepcopy(next(a for a in phase['activities'] if a['claim_id']==old));activity.update(claim_id=new,eligibility='denied' if n==0 else 'allowed',access_limit='0' if n==0 else '1',requirements=[]);phase['activities'].append(activity)
        phase['claim_order'][4:4]=['student:other','staff:other','supply:other']
    result=run(data)
    assert result.status=='resolved'
    assert claims(result)['student:other']==['1','0']
    assert claims(result)['staff:other']==(['1','0'] if not approved else ['0','1'])
    assert claims(result)['training'][0]==('3' if approved else '0')
    total=sum(Fraction(claims(result)[cid][0]) for cid in ['admin','care','training','teach','employment','student:other','staff:other'])
    assert total+Fraction(balances(result)['labor'])==12
    assert result.education.results[0].outcome==('capacity_ready' if approved else 'ineligible')
    assert result.education.results[1].outcome=='capacity_blocked' # shared slots remain finite


@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('prerequisites','service')])
def test_private_contract_is_strict(field,value):
    data=fixture();data['request'][field]=value
    with pytest.raises(ValidationError):run(data)


def test_no_duplicate_same_cohort_dated_time_pool():
    data=fixture()
    for phase in books(data):
        account=deepcopy(next(a for a in phase['batch']['accounts'] if a['id']=='labor'));account.update(id='labor:duplicate');phase['batch']['accounts'].append(account)
        phase['holders'].append(dict(account_id='labor:duplicate',holder_id='shared:cohort',role='time'))
    data['inputs']['entities'].append(dict(id='labor:duplicate',entity_kind='account',label='Invalid duplicate time',provenance=dict(origin='authored',source_refs=[],assumption_refs=[])))
    with pytest.raises(AccountError,match='duplicate.*time|time.*duplicate'):run(data)


@pytest.mark.parametrize('mutation',['case','claimant','authority','obligation','empty_obligation','phase_overlap','duplicate_case_work'])
def test_exact_legal_prerequisites_reject_foreign_or_ambiguous_mapping(mutation):
    data=fixture();legal=data['request']['adjudication'];case=legal['cases'][0];service=data['request']['education']['services'][0]
    if mutation=='case':data['request']['prerequisites'][0]['case_id']='foreign'
    elif mutation=='claimant':case['claimant_id']='foreign'
    elif mutation=='authority':case['authority_id']='region-authority'
    elif mutation=='obligation':service['obligation_refs']=['foreign:duty']
    elif mutation=='empty_obligation':service['obligation_refs']=[]
    elif mutation=='phase_overlap':case['work_claim_ids']=['training']
    else:legal['cases'].append(dict(case,id='duplicate'))
    with pytest.raises(AccountError,match='affected_mapping|invalid_adjudication_education_mapping|duplicate_case_work'):
        run(data)


@pytest.mark.parametrize('field',['target_id','qualification_refs'])
def test_original_malformed_education_still_rejects_after_unresolved_case(field):
    data=fixture();data['request']['adjudication']['cases'][0]['disposition']=None
    service=data['request']['education']['services'][0]
    data['request']['prerequisites'][0]['case_id']=None
    if field=='target_id':service['target_id']='foreign'
    else:service['staff'][0]['qualification_refs']=[]
    with pytest.raises((AccountError,ValueError)):
        run(data)


@pytest.mark.parametrize('disposition',['upheld','dismissed'])
@pytest.mark.parametrize('capacity',[1,2,3])
def test_upheld_never_creates_facility_capacity_or_refunds_prior_seats(disposition,capacity):
    data=fixture();data['request']['adjudication']['cases'][0]['disposition']=disposition
    pool=data['request']['education']['facility_allocation']['batch']
    pool['accounts'][0]['opening']=str(capacity)
    pool['reservations'][0]['amount']=str(min(2,capacity))
    result=run(data);slots=next(c for c in result.education.facility_allocation.accounts.claims if c.claim_id=='seat')
    expected=2 if disposition=='upheld' and capacity>=2 else 1
    assert Fraction(slots.actual)==expected
    assert Fraction(slots.unmet)==2-expected
    assert result.education.results[0].outcome==('ineligible' if disposition=='dismissed' else 'capacity_ready' if capacity>=2 else 'capacity_blocked')


def test_candidate_and_both_phase_books_are_detached():
    result=run();original=deepcopy(result.education.work.evaluation.batch)
    result.batch.postings.clear()
    assert result.education.work.evaluation.batch==original
    assert result.adjudication.administration.evaluation.batch.postings
    assert result.preflight.work.evaluation.batch.postings


def test_fixture_identity_and_unqualified_terms_remain_explicit():
    data=fixture();assert data['identity']==dict(id='synthetic:adjudication-education',version='v1')
    data['request']['education']['services'][0]['staff'][0]['qualification']='not_qualified'
    result=run(data)
    assert result.education.results[0].outcome=='unqualified'
    assert claims(result)['training'][0]=='3' # prerequisite commitments are not delivered learning


@pytest.mark.parametrize('scope',['west','region'])
def test_pair_validates_actual_local_and_regional_jurisdiction(scope):
    data=fixture();authority='region-authority' if scope=='region' else 'west-authority'
    if scope=='west':
        e=deepcopy(next(e for e in data['inputs']['entities'] if e['id']=='east-authority'))
        e['id']=authority;data['inputs']['entities'].append(e)
    text=__import__('json').dumps(data['request']).replace('"east"',f'"{scope}"').replace('"east-authority"',f'"{authority}"')
    data['request']=__import__('json').loads(text)
    relation=deepcopy(next(r for r in data['inputs']['relationships'] if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority'))
    relation.update(id='scope:jurisdiction',from_id=authority,to_id=scope);data['inputs']['relationships'].append(relation)
    assert run(data).status=='resolved'


@pytest.mark.parametrize('disposition',['upheld',None])
def test_distinct_cases_share_administration_and_unresolved_cases_withhold_candidate(disposition):
    data=fixture();legal=data['request']['adjudication'];other=deepcopy(legal['cases'][0])
    other.update(id='other:case',work_claim_ids=['other:admin'],disposition=disposition)
    legal['cases'].append(other)
    for n,phase in enumerate(books(data)):
        claim=deepcopy(next(c for c in phase['batch']['claims'] if c['id']=='admin'))
        claim.update(id='other:admin',requested='2');phase['batch']['claims'].append(claim)
        activity=deepcopy(next(a for a in phase['activities'] if a['claim_id']=='admin'))
        activity.update(claim_id='other:admin',eligibility='allowed' if n==0 else 'denied',access_limit='2' if n==0 else '0',requirements=[])
        phase['activities'].append(activity);phase['claim_order'].insert(1,'other:admin')
    result=run(data)
    assert len(result.adjudication.results)==2
    if disposition is None:
        assert result.batch is None and result.education is None
        assert result.preflight.status=='resolved'
    else:
        assert claims(result)['other:admin']==['2','0']
        assert claims(result)['teach']==['1','1']
        assert result.education.results[0].outcome=='capacity_blocked'
        assert sum(Fraction(claims(result)[c][0]) for c in ['admin','other:admin','care','training','teach','employment'])==12
