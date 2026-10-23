"""Real DOM-03/04 composition with independent finite-book and legal prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.governance_adjudication import GovernanceAdjudicationRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.governance.adjudication import evaluate_pair, binding
from poliscope_engine.domains.governance.adjudication_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from governance_adjudication_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-governance-adjudication',
        'oracle:governance-adjudication-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def books(data):
    return (data['request']['governance']['administration'], data['request']['adjudication']['administration'])


def balances(result):
    return {a.account_id: a.closing for a in result.adjudication.administration.evaluation.allocation.accounts.accounts}


def claims(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.adjudication.administration.evaluation.allocation.accounts.claims}


def actual(result, cid):
    return next(a for a in result.adjudication.administration.evaluation.allocation.actuals if a.claim_id == cid)


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
    assert reg.bind(('authored:ga-administration-mechanism','v1'),('authored:ga-adjudication-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['adjudication']['cases'][0]['disposition']='dismissed';r=GovernanceAdjudicationRequest.model_validate(data)
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
    work=callbacks['authored:ga-administration'];consumer=callbacks['authored:ga-adjudication']
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
    omit={'administration':'authored:ga-administration-mechanism',
        'economy':'authored:ga-adjudication-mechanism','policy':'authored:ga-policy-mechanism'}[missing]
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



def test_literal_shared_book_retains_commitments_without_publication():
    data=fixture();before=deepcopy(data);result=run(data)
    assert result.status=='resolved' and result.governance.outcome=='approved'
    assert result.adjudication.results[0].outcome=='capacity_blocked'
    assert balances(result)==data['expected']['accounts']
    assert claims(result)==data['expected']['claims']
    assert result.adjudication.request.administration.batch==result.governance.administration.batch
    assert result.batch.reservations==result.request.governance.administration.batch.reservations
    assert result.batch.subtotals==result.request.governance.administration.batch.subtotals
    assert sum(p.id=='prior:admin' for p in result.batch.postings)==1
    assert data==before


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_independent_finite_feasible_set(procedure):
    # Independent integer constraints: prior 1 h, protected care 2 h,
    # decision requires 3 h, then legal work requests 7 h on the same book.
    for time in range(3,17):
        data=fixture()
        for phase in books(data):
            phase['batch']['accounts'][0]['opening']=str(time)
            phase['procedure']=procedure
        result=run(data)
        decision=max(x for x in range(1,4) if x+2<=time and
                     (procedure=='priority' or x in (1,3)))
        allowed=decision==3
        legal=max(x for x in range(8) if x+decision+2<=time and
                  (allowed or x==0) and (procedure=='priority' or x in (0,7)))
        assert claims(result)['admin']==[str(decision),str(3-decision)]
        assert claims(result)['work']==[str(legal),str(7-legal)]
        assert Fraction(balances(result)['labor'])==time-decision-2-legal
        assert result.adjudication.results[0].outcome==('upheld' if legal==7 else 'capacity_blocked')


@pytest.mark.parametrize('outcome',['approved','rejected','no_quorum','capacity_blocked'])
@pytest.mark.parametrize('independent',[False,True])
def test_actual_decision_only_restricts_explicit_case_work(outcome,independent):
    data=fixture();gov=data['request']['governance']
    for p in books(data):p['batch']['accounts'][0]['opening']='16'
    if outcome=='rejected':gov['approval']='unanimity'
    elif outcome=='no_quorum':gov['ballots']=gov['ballots'][:1]
    elif outcome=='capacity_blocked':gov['administration']['activities'][0]['access_limit']='1'
    data['request']['prerequisites'][0]['requires_approval']=not independent
    result=run(data)
    assert result.governance.outcome==outcome
    permitted=independent or outcome=='approved'
    assert claims(result)['work'][0]==('7' if permitted else '0')
    assert result.adjudication.results[0].outcome==('upheld' if permitted else 'capacity_blocked')
    assert balances(result)['rights']=='5' and balances(result)['stored']=='12'
    assert result.adjudication.results[0].proposed_obligation_refs==['hypothetical:duty/access']


@pytest.mark.parametrize('missing',['ballot','approval','decision_policy','decision_access','decision_terms',
    'decision_procedure','legal_eligibility','legal_policy','disposition','rationale','conflicting_right',
    'legal_access','legal_terms','legal_procedure'])
def test_unknown_prerequisites_retain_evidence_without_complete_candidate(missing):
    data=fixture();gov=data['request']['governance'];law=data['request']['adjudication'];case=law['cases'][0]
    if missing=='ballot':gov['ballots'][0]['vote']='unknown'
    elif missing=='approval':gov['approval']=None
    elif missing=='decision_policy':gov['bindings'][0]['value']=dict(kind='unknown',reason='not provided')
    elif missing=='decision_access':gov['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='decision_terms':gov['administration']['activities'][0]['terms_known']=False
    elif missing=='decision_procedure':gov['administration']['procedure']=None
    elif missing=='legal_eligibility':case['eligibility']='unknown'
    elif missing=='legal_policy':law['bindings'][0]['value']=dict(kind='unknown',reason='not provided')
    elif missing in ('disposition','rationale'):case[missing]=None
    elif missing=='conflicting_right':case['incompatible_right_refs']=['right:conflicting']
    elif missing=='legal_access':law['administration']['activities'][2]['eligibility']='unknown'
    elif missing=='legal_terms':law['administration']['activities'][2]['terms_known']=False
    else:law['administration']['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    if missing.startswith('decision') or missing in ('ballot','approval'):
        assert result.adjudication is None
    else:
        assert result.governance.outcome=='approved'
        assert result.adjudication.results[0].outcome is None


@pytest.mark.parametrize('eligibility',['denied','unknown'])
@pytest.mark.parametrize('approved',[True,False])
def test_decision_never_overrides_original_unknown_or_denied_work(eligibility,approved):
    data=fixture();data['request']['adjudication']['administration']['activities'][2]['eligibility']=eligibility
    if not approved:data['request']['governance']['approval']='unanimity'
    result=run(data)
    if eligibility=='unknown':assert result.batch is None
    else:assert claims(result)['work']==['0','7']


@pytest.mark.parametrize('mutation,code',[
    ('book','book_mismatch'),('holders','book_mismatch'),('period','period_mismatch'),
    ('scope','scope_mismatch'),('duplicate_mapping','invalid_decision_case_mapping'),
    ('foreign_mapping','invalid_decision_case_mapping'),('missing_mapping','invalid_decision_case_mapping'),
    ('shared_work','invalid_decision_case_mapping'),('duplicate_work','invalid_decision_case_mapping'),
    ('foreign_work','invalid_decision_case_mapping'),('target','affected_mapping'),('unaffected','affected_mapping'),
    ('open_future','open_phase_claim'),('open_prior','open_phase_claim'),('missing_activity','invalid_economy_activities'),
    ('foreign_account','account_identity'),('foreign_claimant','claimant_identity'),
    ('foreign_holder','holder_identity'),('missing_time_holder','time_holders'),('period_both','period_mismatch')])
def test_invalid_context_rejects_without_mutation(mutation,code):
    data=fixture();r=data['request'];gov=r['governance'];law=r['adjudication'];first,second=books(data)
    if mutation=='book':second['batch']['accounts'][0]['opening']='11'
    elif mutation=='holders':second['holders'].pop()
    elif mutation=='period':second['period_id']='day:1'
    elif mutation=='scope':law['scope_id']='west'
    elif mutation=='duplicate_mapping':r['prerequisites'].append(deepcopy(r['prerequisites'][0]))
    elif mutation=='foreign_mapping':r['prerequisites'][0]['case_id']='foreign'
    elif mutation=='missing_mapping':
        c=deepcopy(law['cases'][0]);c['id']='other';law['cases'].append(c)
    elif mutation=='shared_work':law['cases'][0]['work_claim_ids']=['admin']
    elif mutation=='duplicate_work':law['cases'][0]['work_claim_ids']=['work','work']
    elif mutation=='foreign_work':law['cases'][0]['work_claim_ids']=['foreign']
    elif mutation=='target':law['cases'][0]['target_id']='rights'
    elif mutation=='unaffected':gov['bindings'][0]['account_refs']=['stored']
    elif mutation=='open_future':first['activities'][2]['eligibility']='allowed'
    elif mutation=='open_prior':second['activities'][0]['terms_known']=False
    elif mutation=='missing_activity':second['activities'].pop()
    elif mutation=='foreign_account':data['inputs']['entities']=[e for e in data['inputs']['entities'] if e['id']!='rights']
    elif mutation=='foreign_claimant':
        for p in books(data):p['batch']['claims'][2]['claimant_id']='foreign'
    elif mutation=='foreign_holder':
        for p in books(data):p['holders'][0]['holder_id']='foreign'
    elif mutation=='missing_time_holder':
        for p in books(data):p['holders'].pop(0)
    else:
        for p in books(data):p['batch']['accounts'][0]['period_id']='day:1'
    before=deepcopy(data)
    with pytest.raises(AccountError,match=code):run(data)
    assert data==before


def test_replay_and_later_rejection_preserve_prior_case_work():
    data=fixture();first=run(data)
    for p in books(data):p['batch']=first.batch.model_dump()
    assert run(data).batch==first.batch
    data['request']['governance']['approval']='unanimity'
    rejected=run(data)
    assert rejected.batch==first.batch
    assert claims(rejected)['work']==['5','2']
    assert actual(rejected,'work').allocated=='0'


@pytest.mark.parametrize('scope',['east','west','region'])
def test_local_and_regional_scopes_share_canonical_overlap(scope):
    data=fixture();r=data['request'];gov=r['governance'];law=r['adjudication']
    if scope!='east':
        authority='region-authority' if scope=='region' else 'west-authority'
        # Existing fixture has east and regional authorities. West uses the
        # regional authority's explicitly authored jurisdiction, never containment inference.
        if scope=='west':
            authority='region-authority'
            edge=deepcopy(next(e for e in data['inputs']['relationships'] if e['relationship_kind']=='jurisdiction'))
            edge.update(id='jurisdiction:west',from_id=authority,to_id='west')
            data['inputs']['relationships'].append(edge)
        for p in books(data):
            for a in p['batch']['accounts']:a['scope_id']=scope
        for request in [gov,law]:
            request['scope_id']=scope
            for b in request['bindings']:b.update(scope_id=scope,authority_id=authority)
        gov['authority_id']=authority;law['cases'][0]['authority_id']=authority
    assert claims(run(data))==data['expected']['claims']


@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('prerequisites','case')])
def test_strict_private_contract(field,value):
    data=fixture();data['request'][field]=value
    with pytest.raises(ValidationError):run(data)


def test_multiple_cases_keep_independence_and_finite_competition():
    data=fixture();law=data['request']['adjudication'];case=deepcopy(law['cases'][0])
    case.update(id='case:independent',work_claim_ids=['work:independent'],disposition='dismissed')
    law['cases'].append(case)
    data['request']['prerequisites'].append(dict(case_id=case['id'],requires_approval=False))
    data['request']['governance']['approval']='unanimity'
    for n,p in enumerate(books(data)):
        c=deepcopy(p['batch']['claims'][2]);c.update(id='work:independent',requested='3');p['batch']['claims'].append(c)
        a=deepcopy(p['activities'][2]);a['claim_id']=c['id'];p['activities'].append(a)
        p['claim_order'].append(c['id'])
    result=run(data)
    assert result.governance.outcome=='rejected'
    assert [c.outcome for c in result.adjudication.results]==['capacity_blocked','dismissed']
    assert claims(result)['work']==['0','7']
    assert claims(result)['work:independent']==['3','0']
    assert balances(result)['labor']=='2'


@pytest.mark.parametrize('phase',['governance','adjudication'])
@pytest.mark.parametrize('selection',[None,'proposal','competing'])
def test_conflicting_authority_needs_explicit_resolution(phase,selection):
    data=fixture();req=data['request'][phase];b=deepcopy(req['bindings'][0]);b.update(id='competing',authority_id='region-authority',scope_id='region')
    req['bindings'].append(b)
    original=req['bindings'][0]['id']
    if selection is not None:
        req['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='ga:permission',
            entity_id='stored',operation='select',participant_ids=[original,'competing'],
            selected_id=original if selection=='proposal' else 'competing',
            source_refs=['authored:governance-adjudication-v1'])]
    result=run(data)
    if selection=='proposal':assert result.status=='resolved'
    else:
        assert result.batch is None and result.status=='unresolved'
        findings=result.governance.findings if phase=='governance' else result.adjudication.results[0].findings
        assert findings==(['institutional_conflict'] if selection is None else
            ['proposal_not_selected'] if phase=='governance' else ['adjudication_binding_not_selected'])


@pytest.mark.parametrize('phase',['governance','adjudication'])
def test_jurisdiction_is_explicit(phase):
    data=fixture();req=data['request'][phase]
    if phase=='governance':req['authority_id']='shared:cohort'
    else:req['cases'][0]['authority_id']='shared:cohort'
    with pytest.raises(AccountError,match='authority'):run(data)


def test_duplicate_cohort_time_pool_rejected():
    data=fixture()
    entity=deepcopy(next(e for e in data['inputs']['entities'] if e['id']=='labor'));entity['id']='labor:duplicate'
    data['inputs']['entities'].append(entity)
    for p in books(data):
        a=deepcopy(p['batch']['accounts'][0]);a.update(id='labor:duplicate',scope_id='west');p['batch']['accounts'].append(a)
        h=deepcopy(p['holders'][0]);h['account_id']=a['id'];p['holders'].append(h)
    with pytest.raises(AccountError,match='duplicate_cohort_time_budget'):run(data)


def test_completed_case_survives_later_nonapproval_without_refund():
    data=fixture()
    for p in books(data):p['batch']['accounts'][0]['opening']='16'
    first=run(data)
    assert first.adjudication.results[0].outcome=='upheld'
    for p in books(data):p['batch']=first.batch.model_dump()
    data['request']['governance']['approval']='unanimity'
    replay=run(data)
    assert replay.governance.outcome=='rejected'
    assert replay.adjudication.results[0].outcome=='upheld'
    assert replay.batch==first.batch
    assert actual(replay,'work').allocated=='0'


@pytest.mark.parametrize('identity',['RUNTIME_ID','EVALUATOR_ID'])
def test_runtime_identity_changes_stale_context(identity,monkeypatch):
    from poliscope_engine.domains.provisioning import context
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    monkeypatch.setattr(context,identity,'changed:runtime')
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(ConformanceCase(inputs=i,outcome='incomplete',observations=()),
            request=r,units=u,reviews=reg.reviews)


def test_mismatched_policy_unit_registry_rejected():
    r,i,g,u=setup();data=fixture();data['units'][0]['scale']='2';_,_,_,u2=setup(data)
    with pytest.raises(AccountError,match='policy_units'):
        evaluate_pair(r,graph=g,units=u,mechanisms=policy_registry(units=u2,reviews=reviews()))
