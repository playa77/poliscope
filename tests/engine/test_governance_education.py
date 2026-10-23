"""Real DOM-03/06 composition with independent finite-book and education prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.governance_education import GovernanceEducationRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.governance.education import evaluate_pair, binding
from poliscope_engine.domains.governance.education_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from governance_education_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-governance-education',
        'oracle:governance-education-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def books(data):
    return (data['request']['governance']['administration'], data['request']['education']['work'])


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
    assert reg.bind(('authored:ge-administration-mechanism','v1'),('authored:ge-education-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['education']['services'][0]['eligibility']='denied';r=GovernanceEducationRequest.model_validate(data)
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
    work=callbacks['authored:ge-administration'];consumer=callbacks['authored:ge-education']
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
    omit={'administration':'authored:ge-administration-mechanism',
        'economy':'authored:ge-education-mechanism','policy':'authored:ge-policy-mechanism'}[missing]
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
    assert result.status=='resolved' and result.governance.outcome=='approved'
    assert result.education.results[0].outcome=='capacity_ready'
    assert balances(result)==data['expected']['closing']
    assert claims(result)==data['expected']['claims']
    assert {a.claim_id:[a.actual,a.unmet] for a in result.education.facility_allocation.accounts.claims}==data['expected']['facility']
    assert result.education.request.work.batch==result.governance.administration.batch
    assert result.batch.reservations==result.request.education.work.batch.reservations
    assert result.batch.subtotals==result.request.education.work.batch.subtotals
    assert sum(p.id=='prior:admin' for p in result.batch.postings)==1
    assert sum(p.id=='prior:care' for p in result.batch.postings)==1
    assert data==before and run(data)==result


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_independent_integer_feasible_set(procedure):
    # Independently enumerate finite feasible decisions then the ordered service
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


@pytest.mark.parametrize('outcome',['approved','rejected','no_quorum','capacity_blocked'])
@pytest.mark.parametrize('independent',[False,True])
def test_decision_only_restricts_explicit_dependent_services(outcome,independent):
    data=fixture();gov=data['request']['governance']
    if outcome=='rejected':gov['approval']='unanimity'
    elif outcome=='no_quorum':gov['ballots']=gov['ballots'][:1]
    elif outcome=='capacity_blocked':gov['administration']['activities'][0]['access_limit']='1'
    data['request']['prerequisites'][0]['requires_approval']=not independent
    result=run(data);allowed=independent or outcome=='approved'
    assert result.governance.outcome==outcome
    assert claims(result)['training'][0]==('3' if allowed else '0')
    assert claims(result)['teach'][0]==('2' if allowed else '0')
    assert claims(result)['materials'][0]==('2' if allowed else '0')
    slots={a.claim_id:a.actual for a in result.education.facility_allocation.accounts.claims}
    assert slots['seat']==('2' if allowed else '1') # prior seat never refunded
    assert result.education.results[0].outcome==('capacity_ready' if allowed else 'ineligible')
    assert result.request.education.services[0].knowledge_refs==['synthetic:archive']


@pytest.mark.parametrize('missing',['ballot','approval','decision_policy','decision_access','decision_terms',
    'decision_procedure','eligibility','qualification','education_policy','work_access','work_terms',
    'work_procedure','facility_access','facility_funding','facility_procedure'])
def test_unknowns_withhold_candidate_without_erasing_phase_evidence(missing):
    data=fixture();gov=data['request']['governance'];edu=data['request']['education']
    if missing=='ballot':gov['ballots'][0]['vote']='unknown'
    elif missing=='approval':gov['approval']=None
    elif missing=='decision_policy':gov['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='decision_access':gov['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='decision_terms':gov['administration']['activities'][0]['terms_known']=False
    elif missing=='decision_procedure':gov['administration']['procedure']=None
    elif missing=='eligibility':edu['services'][0]['eligibility']='unknown'
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
    if missing.startswith('decision') or missing in ('ballot','approval'):assert result.education is None
    else:assert result.education is not None and result.governance.outcome=='approved'


@pytest.mark.parametrize('approved',[True,False])
@pytest.mark.parametrize('kind',['access','terms','eligibility','qualification','facility'])
def test_approval_never_replaces_original_unknowns(approved,kind):
    data=fixture();edu=data['request']['education']
    if not approved:data['request']['governance']['approval']='unanimity'
    if kind=='access':edu['work']['activities'][2]['eligibility']='unknown'
    elif kind=='terms':edu['work']['activities'][2]['terms_known']=False
    elif kind=='eligibility':edu['services'][0]['eligibility']='unknown'
    elif kind=='qualification':edu['services'][0]['staff'][0]['qualification']='unknown'
    else:edu['facility_allocation']['choices'][0]['access']='unknown'
    assert run(data).batch is None


@pytest.mark.parametrize('mutation,code',[
    ('book','book_mismatch'),('holders','book_mismatch'),('period','period_mismatch'),
    ('scope','scope_mismatch'),('missing_mapping','invalid_decision_education_mapping'),
    ('duplicate_mapping','invalid_decision_education_mapping'),('foreign_mapping','invalid_decision_education_mapping'),
    ('target','affected_mapping'),('unaffected','affected_mapping'),('facility_unaffected','affected_mapping'),
    ('open_future','open_phase_claim'),('open_prior','open_phase_claim'),
    ('foreign_account','account_identity'),('foreign_facility','account_identity'),
    ('foreign_claimant','claimant_identity'),('foreign_holder','holder_identity'),
    ('missing_activity','invalid_economy_activities'),('duplicate_work','invalid_decision_education_mapping'),
    ('facility_overlap','overlapping_education_pools'),('facility_conversion','invalid_education_facility_choice'),
    ('qualification_refs','missing_education_qualification_reference'),
])
def test_adversarial_contexts_and_original_terms_reject(mutation,code):
    data=fixture();gov=data['request']['governance'];edu=data['request']['education'];work=edu['work'];service=edu['services'][0]
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
    data['request']['governance']['approval']='unanimity'
    rejected=run(data)
    assert rejected.governance.outcome=='rejected'
    assert rejected.batch==first.batch
    assert rejected.education.facility_allocation.batch==first.education.facility_allocation.batch


@pytest.mark.parametrize('scope',['east','west','region'])
def test_actual_pair_local_and_regional_scopes(scope):
    data=fixture()
    if scope!='east':
        authority='region-authority' if scope=='region' else 'west-authority'
        if scope=='west':
            entity=deepcopy(next(e for e in data['inputs']['entities'] if e['id']=='east-authority'));entity['id']=authority;data['inputs']['entities'].append(entity)
        # Change only scoped request references, preserving the actual world tree.
        text=__import__('json').dumps(data['request']).replace('"east"',f'"{scope}"').replace('"east-authority"',f'"{authority}"')
        data['request']=__import__('json').loads(text)
        if scope=='region':
            data['request']['governance']['eligible_member_ids']=['shared:cohort','region-authority']
            data['request']['governance']['ballots']=[dict(member_id=m,vote='yes') for m in ['shared:cohort','region-authority']]
        relation=deepcopy(next(r for r in data['inputs']['relationships'] if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority'))
        relation.update(id='scope:jurisdiction',from_id=authority,to_id=scope);data['inputs']['relationships'].append(relation)
    assert run(data).status=='resolved'

@pytest.mark.parametrize('phase',['governance','education'])
@pytest.mark.parametrize('selection',[None,'original','competing'])
def test_overlapping_authority_requires_explicit_resolution(phase,selection):
    data=fixture();req=data['request'][phase];original=req['bindings'][0]['id']
    competing=deepcopy(req['bindings'][0]);competing.update(id='competing',authority_id='region-authority',scope_id='region');req['bindings'].append(competing)
    if selection is not None:
        req['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='ge:permission',
            entity_id='food',operation='select',participant_ids=[original,'competing'],
            selected_id=original if selection=='original' else 'competing',source_refs=['authored:governance-education-v1'])]
    result=run(data)
    if selection=='original':assert result.status=='resolved'
    else:
        assert result.status=='unresolved' and result.batch is None
        findings=result.governance.findings if phase=='governance' else result.education.results[0].findings
        assert findings==(['institutional_conflict'] if selection is None else
            ['proposal_not_selected'] if phase=='governance' else ['education_binding_not_selected'])


@pytest.mark.parametrize('approved',[True,False])
def test_multiple_services_declare_independence_and_compete_for_same_resources(approved):
    data=fixture();edu=data['request']['education'];service=deepcopy(edu['services'][0])
    service.update(id='independent',participants=[dict(cohort_id='shared:cohort',claim_id='student:other')],
        staff=[dict(cohort_id='shared:cohort',claim_id='staff:other',qualification='declared',qualification_refs=['synthetic:certificate'])],
        supply_claim_ids=['supply:other'],facility_claim_ids=['other-seat'])
    edu['services'].append(service);data['request']['prerequisites'].append(dict(service_id='independent',requires_approval=False))
    if not approved:data['request']['governance']['approval']='unanimity'
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
