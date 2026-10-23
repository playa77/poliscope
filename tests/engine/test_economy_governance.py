"""Real DOM-02/03 composition with independent finite-book and ballot oracles."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.economy_governance import EconomyGovernanceRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.economy.governance import evaluate_pair, binding
from poliscope_engine.domains.economy.governance_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from economy_governance_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-economy-governance',
        'oracle:economy-governance-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def books(data):
    return (data['request']['governance']['administration'], data['request']['economy'])


def balances(result):
    return {a.account_id: a.closing for a in result.economy.allocation.accounts.accounts}


def claims(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.economy.allocation.accounts.claims}


def actual(result, cid):
    return next(a for a in result.economy.allocation.actuals if a.claim_id == cid)


def test_literal_shared_time_goods_rights_and_retained_commitments():
    data = fixture(); before = deepcopy(data)
    result = run(data)
    assert (result.status, result.governance.outcome) == ('resolved', 'approved')
    assert balances(result) == data['expected']['accounts']
    assert claims(result) == data['expected']['claims']
    assert result.batch.postings[0].model_dump() == data['request']['economy']['batch']['postings'][0]
    assert result.batch.reservations == result.request.economy.batch.reservations
    assert result.batch.subtotals == result.request.economy.batch.subtotals
    assert sum(p.id == 'prior:admin' for p in result.batch.postings) == 1
    assert result.economy.request.batch == result.governance.administration.batch
    assert all(actual(result,c).allocated == '0' for c in ['admin','care'])
    assert Fraction(balances(result)['stored']) + Fraction(claims(result)['goods'][0]) == 12
    assert sum(Fraction(claims(result)[c][0]) for c in ['admin','care','work']) == 10
    assert all(p.mechanism_ref and p.source_refs for p in result.batch.postings)
    assert data == before


@pytest.mark.parametrize('votes,approval,quorum,outcome', [
    (['yes','yes','no'],'strict_majority',2,'approved'),
    (['yes','yes','no'],'unanimity',2,'rejected'),
    (['yes','yes','yes'],'unanimity',3,'approved'),
    (['yes','no'],'strict_majority',2,'rejected'),
    (['yes','abstain'],'strict_majority',2,'rejected'),
    (['yes'],'strict_majority',2,'no_quorum'),
    ([], 'strict_majority',2,'no_quorum'),
])
def test_actual_institutional_outcomes_restrict_economic_access(votes, approval, quorum, outcome):
    data=fixture();gov=data['request']['governance']
    gov.update(approval=approval,quorum=quorum)
    gov['ballots']=[dict(member_id=m,vote=v) for m,v in zip(gov['eligible_member_ids'],votes)]
    result=run(data)
    assert result.governance.outcome == outcome
    assert claims(result)['admin'] == ['3','0'] and claims(result)['care'] == ['2','0']
    if outcome == 'approved':
        assert balances(result) == data['expected']['accounts']
    else:
        assert balances(result) == {'labor':'5','stored':'12','rights':'5'}
        assert actual(result,'goods').reason == 'denied'
        assert actual(result,'work').reason == 'denied'


@pytest.mark.parametrize('supply', [1,2,3,4,5])
def test_care_competes_with_administration_before_economic_work(supply):
    data=fixture()
    for phase in books(data):
        phase['batch']['accounts'][0]['opening']=str(supply+2)
    data['request']['governance']['administration']['claim_order']=['care','admin','work','goods']
    result=run(data)
    expected_admin=min(3,supply)
    assert claims(result)['admin'][0] == str(expected_admin)
    assert claims(result)['care'][0] == '2'
    assert result.governance.outcome == ('approved' if expected_admin == 3 else 'capacity_blocked')
    assert Fraction(balances(result)['labor']) + sum(Fraction(claims(result)[c][0])
        for c in ['admin','care','work']) == supply+2
    if expected_admin < 3:
        assert actual(result,'work').allocated == actual(result,'goods').allocated == '0'


@pytest.mark.parametrize('where', ['ballot','approval','policy','admin_access','admin_terms',
    'admin_procedure','economic_access','economic_terms','economic_procedure'])
def test_unknown_never_becomes_rejection_or_zero(where):
    data=fixture();gov=data['request']['governance'];admin,econ=books(data)
    if where=='ballot':gov['ballots'][0]['vote']='unknown'
    elif where=='approval':gov['approval']=None
    elif where=='policy':gov['bindings'][0]['value']=dict(kind='unknown',reason='not declared')
    elif where=='admin_access':admin['activities'][0]['eligibility']='unknown'
    elif where=='admin_terms':admin['activities'][0]['terms_known']=False
    elif where=='admin_procedure':admin['procedure']=None
    elif where=='economic_access':econ['activities'][-1]['eligibility']='unknown'
    elif where=='economic_terms':econ['activities'][-1]['terms_known']=False
    else:econ['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    if where.startswith('economic'):
        assert result.governance.outcome=='approved' and result.economy.batch is None
        assert result.governance.administration.batch.postings
    else:
        assert result.governance.outcome is None and result.economy is None


@pytest.mark.parametrize('eligibility', ['denied','unknown'])
def test_approval_cannot_override_original_access(eligibility):
    data=fixture();data['request']['economy']['activities'][-1]['eligibility']=eligibility
    result=run(data)
    assert result.governance.outcome=='approved'
    if eligibility=='unknown':assert result.batch is None
    else:
        assert balances(result)['stored']=='12'
        assert actual(result,'goods').reason=='denied'


def test_rejection_preserves_unknown_economic_eligibility_and_independent_claims():
    data=fixture();data['request']['governance']['approval']='unanimity'
    data['request']['governed_claim_ids']=['goods']
    result=run(data)
    assert claims(result)['work']==['5','2'] and claims(result)['goods']==['0','8']
    data['request']['economy']['activities'][-1]['eligibility']='unknown'
    assert run(data).batch is None


def test_authority_conflict_and_explicit_selection_not_id_or_file_order():
    data=fixture();gov=data['request']['governance']
    other=deepcopy(gov['bindings'][0]);other.update(id='other',authority_id='region-authority',scope_id='region')
    gov['bindings'].append(other)
    # Both authorities have direct jurisdiction over this target's named scope.
    relation=deepcopy(data['inputs']['relationships'][0])
    relation.update(id='eg:regional-target',from_id='region-authority',to_id='stored',
        relationship_kind='jurisdiction',aggregation=dict(kind='non_aggregating'))
    data['inputs']['relationships'].append(relation)
    for order in [gov['bindings'],list(reversed(gov['bindings']))]:
        gov['bindings']=order
        result=run(data)
        assert result.governance.findings == ['institutional_conflict'] and result.batch is None
    gov['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
        authority_id='region-authority',scope_id='region',entity_id='stored',parameter_id='eg:permission',
        participant_ids=['other','proposal'],operation='select',selected_id='proposal',source_refs=['authored:economy-governance-v1'])]
    assert run(data).governance.outcome=='approved'
    gov['rules'][0]['selected_id']='other'
    assert run(data).governance.findings==['proposal_not_selected']


def test_independent_small_integer_time_stock_and_entitlement_oracle():
    # Enumerate feasible allocations independently. Admin=3 including a prior 1,
    # care=2 reserved. Subsequent work is <=7, goods <=8 and <=rights and <=stock.
    for time,stock,rights in product(range(5,9),range(4),range(4)):
        data=fixture()
        for phase in books(data):
            for account in phase['batch']['accounts']:
                account['opening']=str({'labor':time,'stored':stock,'rights':rights}[account['id']])
        expected=max((w,g) for w,g in product(range(8),range(9))
            if w+5<=time and g<=stock and g<=rights)
        result=run(data)
        assert tuple(int(actual(result,c).allocated) for c in ['work','goods'])==expected
        b=balances(result)
        assert Fraction(b['labor'])+5+expected[0]==time
        assert Fraction(b['stored'])+expected[1]==stock
        assert Fraction(b['rights'])+expected[1]==rights


def test_replay_prior_completion_is_not_spent_again():
    first=run();data=fixture()
    for phase in books(data):phase['batch']=first.batch.model_dump()
    second=run(data)
    assert second.batch==first.batch
    assert all(a.allocated=='0' for a in second.economy.allocation.actuals)
    assert all(a.allocated=='0' for a in second.governance.administration.allocation.actuals)


@pytest.mark.parametrize('mutation,code', [
    ('book','book_mismatch'),('holders','book_mismatch'),('period','period_mismatch'),
    ('duplicate_economic','invalid_governance_counterpart_claims'),
    ('duplicate_governed','invalid_governance_counterpart_claims'),
    ('foreign_economic','invalid_governance_counterpart_claims'),
    ('foreign_governed','invalid_governance_counterpart_claims'),
    ('admin_as_economic','invalid_governance_counterpart_claims'),
    ('unaffected','affected_account'),('open_future','open_phase_claim'),
    ('open_prior','open_phase_claim'),('missing_activity','invalid_economy_activities'),
    ('foreign_account','account_identity'),('foreign_claimant','claimant_identity'),
    ('foreign_holder','holder_identity'),('missing_time_holder','time_holders'),
    ('period_both','period_mismatch'),('missing_proposal','invalid_governance_proposal'),
])
def test_invalid_canonical_context_is_rejected_without_mutation(mutation,code):
    data=fixture();r=data['request'];admin,econ=books(data)
    if mutation=='book':econ['batch']['accounts'][0]['opening']='11'
    elif mutation=='holders':econ['holders'].pop()
    elif mutation=='period':econ['period_id']='day:1'
    elif mutation=='duplicate_economic':r['economic_claim_ids'].append('goods')
    elif mutation=='duplicate_governed':r['governed_claim_ids'].append('goods')
    elif mutation=='foreign_economic':r['economic_claim_ids'].append('foreign')
    elif mutation=='foreign_governed':r['governed_claim_ids'].append('care')
    elif mutation=='admin_as_economic':r['economic_claim_ids'].append('admin')
    elif mutation=='unaffected':r['governance']['bindings'][0]['account_refs']=['stored']
    elif mutation=='open_future':admin['activities'][-1]['eligibility']='allowed'
    elif mutation=='open_prior':econ['activities'][0]['terms_known']=False
    elif mutation=='missing_activity':econ['activities'].pop()
    elif mutation=='foreign_account':
        data['inputs']['entities']=[e for e in data['inputs']['entities'] if e['id']!='rights']
    elif mutation=='foreign_claimant':
        for p in books(data):p['batch']['claims'][-1]['claimant_id']='foreign'
    elif mutation=='foreign_holder':
        for p in books(data):p['holders'][-1]['holder_id']='foreign'
    elif mutation=='missing_time_holder':
        for p in books(data):p['holders'].pop(0)
    elif mutation=='period_both':
        for p in books(data):p['batch']['accounts'][0]['period_id']='day:1'
    else:r['governance']['proposal_binding_id']='foreign'
    before=deepcopy(data)
    with pytest.raises(AccountError,match=code):run(data)
    assert data==before


def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['governance']['approval']='unanimity'
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
    assert reg.bind(('authored:eg-administration-mechanism','v1'),('authored:eg-economy-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['governance']['approval']='unanimity';r=EconomyGovernanceRequest.model_validate(data)
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
    work=callbacks['authored:eg-administration'];consumer=callbacks['authored:eg-economy']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.governance.ballots.clear()
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})


@pytest.mark.parametrize('missing', ['administration','economy','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:eg-administration-mechanism',
        'economy':'authored:eg-economy-mechanism','policy':'authored:eg-policy-mechanism'}[missing]
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
    r.governance.ballots.clear();result.batch.postings.clear()
    assert result.request.governance.ballots
    assert run().batch.postings


@pytest.mark.parametrize('field,value', [('contract_version',2),('governed_claim_ids',[]),('economic_claim_ids',[]),('economic_claim_ids','goods')])
def test_strict_pair_contract(field,value):
    data=fixture();data['request'][field]=value
    with pytest.raises(ValidationError):run(data)


@pytest.mark.parametrize('scope', ['east','region'])
def test_explicit_local_and_regional_scope_use_same_canonical_book(scope):
    data=fixture()
    if scope=='region':
        for phase in books(data):
            for account in phase['batch']['accounts']:account['scope_id']='region'
        gov=data['request']['governance']
        gov.update(scope_id='region',authority_id='region-authority')
        gov['bindings'][0].update(scope_id='region',authority_id='region-authority')
    result=run(data)
    assert result.governance.outcome=='approved'
    assert balances(result)==data['expected']['accounts']


def test_storage_order_does_not_choose_precedence_or_change_numerical_result():
    data=fixture();expected=run(data)
    for phase in books(data):
        for key in ['accounts','claims','subtotals','reservations']:phase['batch'][key].reverse()
        phase['activities'].reverse();phase['holders'].reverse()
    data['request']['governance']['ballots'].reverse()
    result=run(data)
    assert balances(result)==balances(expected) and claims(result)==claims(expected)
    assert result.batch.postings==expected.batch.postings


def test_explicit_economic_priority_changes_distribution_without_new_stock():
    data=fixture();admin,econ=books(data)
    for phase in [admin,econ]:
        c=deepcopy(phase['batch']['claims'][-1]);c.update(id='other:goods',requested='8')
        phase['batch']['claims'].append(c)
        a=deepcopy(phase['activities'][-1]);a['claim_id']='other:goods'
        phase['activities'].append(a);phase['claim_order'].append('other:goods')
        phase['batch']['accounts'][2]['opening']='20'
    data['request']['economic_claim_ids'].append('other:goods')
    data['request']['governed_claim_ids'].append('other:goods')
    first=run(data)
    assert claims(first)['goods']==['8','0'] and claims(first)['other:goods']==['4','4']
    econ['claim_order']=['admin','care','work','other:goods','goods']
    second=run(data)
    assert claims(second)['goods']==['4','4'] and claims(second)['other:goods']==['8','0']
    assert balances(first)==balances(second)=={'labor':'0','stored':'0','rights':'8'}


def test_funding_is_an_independent_budget_not_goods_or_authority():
    data=fixture()
    for phase in books(data):
        a=deepcopy(phase['batch']['accounts'][2]);a.update(id='funds',opening='6')
        phase['batch']['accounts'].append(a)
        phase['holders'].append(dict(account_id='funds',holder_id='shared:cohort',role='funding'))
    e=deepcopy(data['inputs']['entities'][0]);e.update(id='funds',entity_kind='account',label='Synthetic funding units')
    data['inputs']['entities'].append(e)
    data['request']['economy']['activities'][-1]['requirements'].append(dict(account_id='funds',per_unit='2',kind='funding'))
    result=run(data)
    assert claims(result)['goods']==['3','5']
    assert balances(result)=={'labor':'0','stored':'9','rights':'2','funds':'0'}
    for phase in books(data):
        phase['batch']['accounts'][1]['opening']='0'
        phase['batch']['accounts'][-1]['opening']='1000'
    assert claims(run(data))['goods']==['0','8']


def test_unknown_downstream_preserves_resolved_first_stage_evidence():
    data=fixture();data['request']['economy']['activities'][-1]['terms_known']=False
    result=run(data)
    assert result.batch is None and result.economy.batch is None
    assert {c.claim_id:c.actual for c in result.governance.administration.allocation.accounts.claims}=={
        'admin':'3','care':'2','goods':'0','work':'0'}
    assert result.governance.administration.batch.reservations==result.request.economy.batch.reservations


def test_preexisting_economic_fulfillment_is_history_even_after_rejection():
    data=fixture()
    for phase in books(data):
        phase['batch']['postings'].append(dict(id='past:goods',kind='use',source_id='stored',
            destination_id=None,amount='2',claim_id='goods',reservation_id=None,
            mechanism_ref='synthetic:past',source_refs=['synthetic:past']))
    data['request']['governance']['approval']='unanimity'
    result=run(data)
    assert claims(result)['goods']==['2','6']
    assert actual(result,'goods').allocated=='0' and balances(result)['stored']=='10'
    assert sum(p.id=='past:goods' for p in result.batch.postings)==1


def test_unknown_decision_common_conformance_propagates_no_candidate():
    data=fixture();data['request']['governance']['ballots'][0]['vote']='unknown'
    r,i,g,u=setup(data);reg,i=trusted(r,i,g,u)
    case=ConformanceCase(inputs=i,outcome='incomplete',observations=(
        dict(node=['output','work',WORK],status='missing_input',reason='missing_input',value=None),
        dict(node=['output','provision',CANDIDATE],status='missing_input',reason='blocked',value=None)))
    result=run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert all(o.value is None for o in result.observations if o.node[0]=='output')
    assert result.accounts is None


def test_nested_forged_numeric_dto_is_revalidated():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews())
    r.economy.activities[-1].__dict__['access_limit']=0.1
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u,mechanisms=m)


def test_future_reservations_remain_effective_without_first_stage_spending():
    data=fixture()
    for phase in books(data):
        phase['batch']['reservations'].append(dict(id='hold:goods',account_id='stored',claim_id='goods',amount='4'))
    result=run(data)
    assert claims(result)['goods']==['5','3']
    assert [p.amount for p in result.batch.postings if p.reservation_id=='hold:goods']==['4']
    assert result.governance.administration.batch.reservations==result.batch.reservations
    assert not any(p.claim_id=='goods' for p in result.governance.administration.batch.postings)
    assert next(a for a in result.economy.allocation.accounts.accounts if a.account_id=='stored').outstanding_reserved=='0'


def test_scaled_units_preserve_independent_time_mass_and_rights_balances():
    data=fixture()
    next(u for u in data['units'] if u['id']=='hours')['scale']='3600'
    data['units'].extend([dict(id='minutes',dimension=[['time',1]],kind='capacity',scale='60'),
        dict(id='grams',dimension=[['mass',1]],kind='stock',scale='0.001')])
    for phase in books(data):
        phase['batch']['accounts'][0].update(unit_id='minutes',opening='600')
        phase['batch']['accounts'][1].update(unit_id='grams',opening='12000',maximum='1000000')
        for c in phase['batch']['claims']:
            c['requested']=str(int(c['requested'])*(1000 if c['id']=='goods' else 60))
        phase['batch']['postings'][0]['amount']='60'
        phase['batch']['reservations'][0]['amount']='120'
    data['request']['economy']['activities'][-1]['access_limit']='1000000'
    data['request']['economy']['activities'][-1]['requirements'][0]['per_unit']='0.001'
    result=run(data)
    assert balances(result)=={'labor':'0','stored':'7000','rights':'0'}
    assert claims(result)=={'admin':['180','0'],'care':['120','0'],
        'work':['300','120'],'goods':['5000','3000']}
    assert sum(Fraction(claims(result)[c][0])/60 for c in ['admin','care','work'])==10
    assert (Fraction(balances(result)['stored'])+Fraction(claims(result)['goods'][0]))/1000==12
