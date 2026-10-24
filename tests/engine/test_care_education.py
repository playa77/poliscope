"""Real beneficiary care / education conformance; independently authored finite oracles."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.care_education import CareEducationRequest
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import conformance_catalog, ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.social_organization.education import evaluate_pair
from poliscope_engine.domains.social_organization.education_counterpart import (
    binding, host_registry, policy_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from care_education_fixture import fixture, setup, trusted


def run(data=None):
    request, inputs, graph, units = setup(data)
    registry, _ = trusted(request, inputs, graph, units)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=registry.reviews))


def work_inputs(data):
    req = data['request']
    return req['education']['work'], req['care']['work']


def case_for(inputs):
    return ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output','work',WORK],status='partial'),
        dict(node=['output','economy',CANDIDATE],status='partial')),
        trace_edges=((('output','work',WORK),('input','economy',BOOK)),))


def test_literal_shared_time_supplies_facilities_and_mass():
    data=fixture();before=deepcopy(data);result=run(data)
    assert data==before and result.status=='resolved' and run(data)==result
    assert result.education.results[0].outcome=='capacity_ready'
    assert closing(result)==data['expected']['closing']
    assert totals(result)==data['expected']['claims']
    assert result.care.work.evaluation==result.education.work.evaluation
    assert sum(p.id=='prior:care' for p in result.batch.postings)==1
    assert result.batch.postings[0]==result.request.care.work.batch.postings[0]
    assert result.batch.reservations==result.request.care.work.batch.reservations
    assert result.batch.subtotals==result.request.care.work.batch.subtotals
    assert all(p.source_refs and p.mechanism_ref for p in result.batch.postings)
    facilities=result.education.facility_allocation
    assert {a.claim_id:[a.actual,a.unmet] for a in facilities.accounts.claims}==data['expected']['facility']
    assert sum(p.id=='prior:seat' for p in facilities.batch.postings)==1
    assert facilities.accounts.accounts[0].closing=='0'
    assert 'school:slots' not in {a.id for a in result.batch.accounts}
    assert not any(p.source_id=='school:slots' for p in result.batch.postings)
    assert sum(Fraction(totals(result)[c][0]) for c in ('care','training','teach','employment'))==12
    assert Fraction(closing(result)['raw'])+sum(Fraction(totals(result)[c][0]) for c in ('materials','goods'))==20


def totals(result):
    return {c.claim_id:[c.actual,c.unmet] for c in result.care.work.evaluation.allocation.accounts.claims}


def closing(result):
    return {a.account_id:a.closing for a in result.care.work.evaluation.allocation.accounts.accounts}


def test_common_conformance_runs_actual_services_repeatedly():
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    case=case_for(inputs)
    result=run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert result==run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert result.accounts is None
    assert registry.bind(('authored:ce-work-mechanism','v1'),
        ('authored:ce-education-mechanism','v1'),output_id=WORK,input_id=BOOK,
        world=graph.registry,scope_id='east',producer_entity_id='east-authority',
        consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('unknown',['policy','eligibility','qualification','work','materials','facility'])
def test_unknown_withholds_complete_candidate_but_retains_independent_commitments(unknown):
    data=fixture();edu=data['request']['education']
    if unknown=='policy':edu['bindings'][0]['value']=dict(kind='unknown',reason='Unknown permission')
    if unknown=='eligibility':edu['services'][0]['eligibility']='unknown'
    if unknown=='qualification':edu['services'][0]['staff'][0]['qualification']='unknown'
    if unknown in ('work','materials'):
        for w in work_inputs(data)[:2]:next(a for a in w['activities'] if a['claim_id']==('training' if unknown=='work' else 'materials'))['terms_known']=False
    if unknown=='facility':edu['facility_allocation']['choices'][0]['funding_known']=False
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    assert result.batch is None
    if unknown in ('policy','eligibility','qualification','facility'):
        assert result.education.work.evaluation.batch is not None
        assert result.education.work.evaluation.batch.postings
    if unknown in ('work','materials'):
        assert result.education.facility_allocation.status=='resolved'


@pytest.mark.parametrize('blocked',['eligibility','qualification','materials','seat'])
def test_denied_or_short_prerequisite_is_resolved_and_does_not_refund_other_inputs(blocked):
    data=fixture();edu=data['request']['education']
    if blocked=='eligibility':edu['services'][0]['eligibility']='denied'
    if blocked=='qualification':edu['services'][0]['staff'][0]['qualification']='not_qualified'
    if blocked=='materials':
        for w in work_inputs(data)[:2]:next(a for a in w['activities'] if a['claim_id']=='materials')['eligibility']='denied'
    if blocked=='seat':edu['facility_allocation']['claim_order']=['other-seat','seat'];edu['facility_allocation']['batch']['reservations']=[];edu['facility_allocation']['batch']['postings'][0]['reservation_id']=None
    result=run(data);service=result.education.results[0]
    assert result.status=='resolved'
    assert service.outcome==dict(eligibility='ineligible',qualification='unqualified',materials='capacity_blocked',seat='capacity_blocked')[blocked]
    assert next(c for c in result.care.work.evaluation.allocation.accounts.claims if c.claim_id=='teach').actual=='2'
    assert next(c for c in result.care.work.evaluation.allocation.accounts.claims if c.claim_id=='training').actual=='3'
    if blocked in ('materials','seat'):assert blocked in service.unmet_claim_ids
    if blocked=='materials':assert totals(result)['goods']==['4','4']


def test_actual_policy_conflict_retains_committed_inputs_and_withholds_chain():
    data=fixture();edu=data['request']['education']
    edu['bindings'].append(deepcopy(edu['bindings'][0])|{'id':'competing-policy','value':dict(kind='label',value='other_permission')})
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    assert result.education.policies.results[0].status=='conflict'
    assert result.education.results[0].findings==['institutional_conflict']
    assert result.education.work.status=='resolved'


@pytest.mark.parametrize('order', [('care','training','teach','employment','materials','goods'),('employment','teach','training','care','goods','materials')])
def test_independent_shared_cohort_time_oracle(order):
    # Enumerate final integer commitments independently: care includes one prior
    # hour and its remaining held hour cannot be spent by another activity.
    for training,staff,employment in product((1,3,5),(1,2,4),(4,8)):
        data=fixture(); demands=dict(care=3,training=training,teach=staff,employment=employment)
        for w in work_inputs(data):
            w['claim_order']=list(order)
            for cid,n in demands.items():
                next(c for c in w['batch']['claims'] if c['id']==cid)['requested']=str(n)
                next(a for a in w['activities'] if a['claim_id']==cid)['access_limit']=str(n)
        feasible=[dict(zip(demands,v)) for v in product(range(2,4),range(training+1),range(staff+1),range(employment+1)) if sum(v)<=12]
        expected=max(feasible,key=lambda v:tuple(v[c] for c in order if c in v))
        result=run(data)
        assert {c:int(totals(result)[c][0]) for c in demands}==expected
        assert int(closing(result)['labor'])==12-sum(expected.values())
        service=result.education.results[0]
        assert service.outcome==('capacity_ready' if expected['training']==training and expected['teach']==staff and order[0]=='care' else 'capacity_blocked')
        assert {c:totals(result)[c][0] for c in ('goods','materials')}==({'materials':'2','goods':'2'} if order[0]=='care' else {'materials':'0','goods':'4'})


@pytest.mark.parametrize('change,code',[
    ('work','care_education_work_mismatch'),('period','counterpart_period_mismatch'),
    ('authority','invalid_education_authority'),('qualification','missing_education_qualification_reference'),
    ('duplicate_time','duplicate_cohort_time_budget'),('pool','overlapping_education_pools'),
    ('facility_period','incompatible_education_scope_period'),('holder','counterpart_holder_identity'),
    ('claimant','counterpart_claimant_identity'),('account','counterpart_account_identity'),
    ('missing_time','counterpart_time_holders'),('staff','unmapped_care_claim'),
    ('facility_asset','invalid_education_facility'),('scope','incompatible_care_work_scope')])
def test_invalid_context_or_double_budget_rejects_purely(change,code):
    data=fixture();edu=data['request']['education']
    if change=='work':edu['work']['activities'][0]['access_limit']='2'
    if change=='authority':edu['services'][0]['authority_id']='region-authority'
    if change=='qualification':edu['services'][0]['staff'][0]['qualification_refs']=[]
    if change=='facility_period':edu['facility_allocation']['batch']['accounts'][0]['period_id']='day:1'
    if change=='facility_asset':edu['facilities'][0]['asset_id']='raw'
    if change=='pool':edu['facility_allocation']['batch']['claims'][0]['id']='materials'
    for w in work_inputs(data):
        if change=='period':w['period_id']='day:1'
        if change=='holder':w['holders'][0]['holder_id']='food'
        if change=='claimant':w['batch']['claims'][0]['claimant_id']='food'
        if change=='account':next(a for a in w['batch']['accounts'] if a['id']=='raw')['id']='missing:account'
        if change=='missing_time':w['holders']=w['holders'][1:]
        if change=='scope':w['batch']['accounts'][0]['scope_id']='west'
        if change=='staff':next(a for a in w['activities'] if a['claim_id']=='teach')['kind']='care'
        if change=='duplicate_time':
            w['batch']['accounts'].append(next(a for a in w['batch']['accounts'] if a['id']=='labor')|{'id':'duplicate:time'})
            w['holders'].append(dict(account_id='duplicate:time',holder_id='shared:cohort',role='time'))
    if change=='duplicate_time':data['inputs']['entities'].append(data['inputs']['entities'][0]|{'id':'duplicate:time','entity_kind':'account'})
    before=deepcopy(data)
    with pytest.raises(ValueError,match=code):run(data)
    assert data==before


@pytest.mark.parametrize('change',['request','world','units','membership','policy_review'])
def test_stale_complete_context_rejects(change):
    from poliscope_engine.numeric import Registry
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    reviews=registry.reviews
    if change=='request':request.education.services[0].knowledge_refs.append('later')
    if change=='world':inputs=inputs.model_copy(update={'entities':[inputs.entities[0].model_copy(update={'label':'later'}),*inputs.entities[1:]]})
    if change=='membership':inputs=inputs.model_copy(update={'relationships':inputs.relationships[:-1]})
    if change=='units':units=Registry(tuple(replace(u,scale=u.scale*2) if u.id=='slots' else u for u in units.units))
    if change=='policy_review':reviews=(*reviews[:-1],replace(reviews[-1],evidence_review_ref='different-review'))
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=reviews)


def test_opaque_books_explicit_policy_reviews_and_detached_snapshots():
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    unreviewed=host_registry(request,graph=graph,units=units,reviews=[])
    with pytest.raises(MechanismError,match='review_required'):
        unreviewed.activate('authored:ce-work-mechanism','v1',phase='static',world=graph.registry,scope_id='east',entity_id='east-authority')
    # Reviewing the two data ports does not implicitly review the policy.
    with pytest.raises(MechanismError,match='review_required'):
        evaluate_pair(request,graph=graph,units=units,mechanisms=policy_registry(units=units,reviews=registry.reviews[:2]))
    callbacks={i.id:i.callback for i in registry.implementations}
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        callbacks['authored:ce-work'](WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        callbacks['authored:ce-education'](CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    policy=policy_registry(units=units,reviews=registry.reviews)
    staged=callbacks['authored:ce-work'](WORK,{CONTEXT:LabelValue(kind='label',value=binding(request,graph,units,policy))})
    first=callbacks['authored:ce-education'](CANDIDATE,{BOOK:LabelValue(**staged)})
    request.education.services.clear()
    assert callbacks['authored:ce-education'](CANDIDATE,{BOOK:LabelValue(**staged)})==first
    result=run();result.batch.postings.clear();assert run().batch.postings
    with pytest.raises(AccountError,match='policy_callback_not_executable'):callbacks['authored:ce-policy']()


@pytest.mark.parametrize('field',['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_execution_identity_rejects(field):
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    inputs=inputs.model_copy(update={'versions':inputs.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=registry.reviews)


@pytest.mark.parametrize('unknown',['policy','work','facility'])
def test_common_conformance_unknown_is_missing_input(unknown):
    data=fixture()
    if unknown=='policy':data['request']['education']['services'][0]['staff'][0]['qualification']='unknown'
    if unknown=='facility':data['request']['education']['facility_allocation']['choices'][0]['funding_known']=False
    if unknown=='work':
        for w in work_inputs(data)[:2]:w['activities'][0]['terms_known']=False
    request,inputs,graph,units=setup(data);registry,inputs=trusted(request,inputs,graph,units)
    case=ConformanceCase(inputs=inputs,outcome='incomplete',observations=(dict(node=['output','economy',CANDIDATE],status='missing_input',value=None),))
    assert run_bound_case(case,request=request,units=units,reviews=registry.reviews).accounts is None


def test_nested_forged_dto_and_foreign_policy_units_reject():
    from pydantic import ValidationError
    from poliscope_engine.numeric import Registry
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    with pytest.raises(AccountError,match='care_education_policy_units'):
        evaluate_pair(request,graph=graph,units=units,mechanisms=policy_registry(units=Registry(()),reviews=registry.reviews))
    request.education.services.append(dict(id='forged'))
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):evaluate_pair(request,graph=graph,units=units,mechanisms=registry)


@pytest.mark.parametrize('change,code',[
    ('port','interface_type_mismatch'),('reference','counterpart_identity_mismatch'),
    ('fixture','unresolved_counterpart_fixture')])
def test_catalog_rejects_forged_counterpart_readiness(change,code):
    from poliscope_engine.domains import DomainRegistry
    from poliscope_engine.contracts.mechanisms import ReferenceType
    from poliscope_engine.contracts.packs import Identity
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    catalog=conformance_catalog();modules,pairs=list(catalog.modules),list(catalog.pairs)
    port=next(i for m in modules if m.domain=='knowledge_culture' for i in m.interfaces if i.port_id==BOOK)
    if change=='port':
        module=next(m for m in modules if m.domain=='knowledge_culture')
        module.interfaces[module.interfaces.index(port)]=port.model_copy(update={'value_type':ReferenceType(kind='reference',entity_kind='account')})
    if change=='reference':port.references.pop()
    if change=='fixture':next(p for p in pairs if p.id=='pair:DOM-05:DOM-06').fixture_refs[0]=Identity(id='forged',version='v1')
    with pytest.raises(ConformanceError,match=code):
        DomainRegistry(modules,pairs).validate(world=graph.registry,mechanisms=registry,branch_ids=[c.branch_id for m in modules for c in m.coverage])


@pytest.mark.parametrize('capacity',[2,3,4,5])
def test_independent_facility_capacity_oracle(capacity):
    data=fixture()
    data['request']['education']['facility_allocation']['batch']['accounts'][0]['opening']=str(capacity)
    result=run(data);facility=result.education.facility_allocation
    # Seat has one prior fulfillment and a 2-slot hold. It spends one more;
    # the other claimant can consume at most two of the remainder.
    other=min(2,capacity-2)
    assert {a.claim_id:(int(a.actual),int(a.unmet)) for a in facility.accounts.claims}=={
        'seat':(2,0),'other-seat':(other,2-other)}
    assert int(facility.accounts.accounts[0].closing)==capacity-2-other
    assert result.education.results[0].outcome=='capacity_ready'
    assert {a.account_id:a.closing for a in result.care.work.evaluation.allocation.accounts.accounts}==data['expected']['closing']


@pytest.mark.parametrize('selected',['education:policy','competing-policy'])
def test_explicit_actual_policy_selection_is_retained(selected):
    data=fixture();edu=data['request']['education']
    edu['bindings'].append(deepcopy(edu['bindings'][0])|{'id':'competing-policy','value':dict(kind='label',value='other_permission')})
    edu['rules']=[dict(contract_version=1,identity=dict(id='authored:ce-selection',version='v1'),
        authority_id='east-authority',scope_id='east',entity_id='food',parameter_id='education:permission',
        participant_ids=['education:policy','competing-policy'],operation='select',selected_id=selected,
        source_refs=['authored:care-education-v1'])]
    result=run(data)
    assert result.education.policies.results[0].status=='known'
    assert result.education.policies.results[0].rule.selected_id==selected
    if selected=='education:policy':assert result.education.results[0].outcome=='capacity_ready'
    else:
        assert result.status=='unresolved' and result.batch is None
        assert result.education.results[0].findings==['education_binding_not_selected']
        assert result.education.work.status=='resolved'


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
@pytest.mark.parametrize('goods_first',[False,True])
def test_independent_stock_and_entitlement_oracle(procedure,goods_first):
    # Enumerate feasible integer materials/goods quantities against independent
    # physical and institutional constraints. Neither supplies time or facilities.
    for stock,rights,rate in product((0,3,20),(0,3,8),('0.5','1','2')):
        data=fixture();order=['goods','materials'] if goods_first else ['materials','goods']
        for w in work_inputs(data):
            w['procedure']=procedure
            w['claim_order']=['care','training','teach','employment',*order]
            next(a for a in w['batch']['accounts'] if a['id']=='raw')['opening']=str(stock)
            next(a for a in w['batch']['accounts'] if a['id']=='rights').update(opening=str(rights),quantum='0.1')
            for a in w['activities']:
                if a['claim_id'] in order:a['requirements'][0]['per_unit']=rate
        demands=dict(materials=2,goods=8)
        feasible=[dict(zip(order,v)) for v in product(*[range(demands[k]+1) if procedure=='priority' else (0,demands[k]) for k in order])
                  if sum(v)<=stock and sum(v)*Fraction(rate)<=rights]
        expected=max(feasible,key=lambda v:tuple(v[k] for k in order))
        result=run(data)
        assert {k:int(totals(result)[k][0]) for k in order}==expected
        assert Fraction(closing(result)['raw'])==stock-sum(expected.values())
        assert Fraction(closing(result)['rights'])==rights-sum(expected.values())*Fraction(rate)
        assert totals(result)['employment']==(['4','4'] if procedure=='priority' else ['0','8'])
        assert result.education.results[0].outcome==('capacity_ready' if expected['materials']==2 else 'capacity_blocked')


def test_reusing_both_staged_pools_does_not_spend_twice():
    data=fixture();result=run(data)
    for w in work_inputs(data):w['batch']=result.batch.model_dump(mode='json')
    data['request']['education']['facility_allocation']['batch']=result.education.facility_allocation.batch.model_dump(mode='json')
    replay=run(data)
    assert replay.batch==result.batch
    assert replay.education.facility_allocation.batch==result.education.facility_allocation.batch
    assert totals(replay)==totals(result) and closing(replay)==closing(result)
    assert all(a.allocated=='0' for a in replay.education.facility_allocation.actuals)


def test_no_other_pair_callbacks_or_reviews_are_granted():
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    assert {i.id for i in registry.implementations}=={'authored:ce-work','authored:ce-education','authored:ce-policy'}
    assert len(registry.reviews)==3
    with pytest.raises(MechanismError,match='unknown_implementation'):
        registry.activate('authored:ec-work-mechanism','v1',phase='static',world=graph.registry,scope_id='east',entity_id='east-authority')


@pytest.mark.parametrize('change',['service','policy_review','facility'])
def test_book_token_from_different_context_is_rejected(change):
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    callbacks={i.id:i.callback for i in registry.implementations}
    policy=policy_registry(units=units,reviews=registry.reviews)
    token=callbacks['authored:ce-work'](WORK,{CONTEXT:LabelValue(kind='label',value=binding(request,graph,units,policy))})
    reviews=registry.reviews
    if change=='service':request.education.services[0].knowledge_refs.append('changed')
    if change=='facility':
        request.education.facility_allocation.batch.accounts[0]=request.education.facility_allocation.batch.accounts[0].model_copy(update={'opening':'4'})
    if change=='policy_review':reviews=(*reviews[:-1],replace(reviews[-1],evidence_review_ref='changed'))
    new=host_registry(request,graph=graph,units=units,reviews=reviews)
    consumer=next(i.callback for i in new.implementations if i.id=='authored:ce-education')
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(**token)})


def test_facility_account_requires_canonical_account_identity():
    data=fixture();next(e for e in data['inputs']['entities'] if e['id']=='school:slots')['entity_kind']='resource'
    with pytest.raises(AccountError,match='counterpart_facility_account_identity'):run(data)


def test_beneficiary_obligation_and_overlapping_membership_are_actual_evidence():
    result=run()
    assert result.care.population.value=='10'
    assert [a.population.value for a in result.care.arrangements]==['10','10']
    duty=result.care.results[0]
    assert (duty.beneficiary_id,duty.provider_id,duty.obligation_id)==('shared:cohort','shared:cohort','duty')
    assert (duty.actual_before,duty.actual,duty.unmet)==('1','2','0')
    assert result.care.work==result.education.work


def test_education_precedence_can_leave_inspectable_unmet_care_without_default():
    data=fixture()
    for w in work_inputs(data):w['claim_order']=['employment','training','teach','care','materials','goods']
    result=run(data);duty=result.care.results[0]
    # Prior care 1 plus remaining protected hold 1 survives the other claims.
    assert (duty.actual_before,duty.actual,duty.unmet)==('1','1','1')
    assert totals(result)['employment']==['8','0']
    assert totals(result)['training']==['2','1']
    assert totals(result)['teach']==['0','2']
    assert result.education.results[0].outcome=='capacity_blocked'
    assert result.care.work==result.education.work
    assert fixture()['request']['care']['work']['claim_order'][0]=='care'


@pytest.mark.parametrize('change,code',[
    ('beneficiary','invalid_care_participants'),('provider','invalid_care_participants'),
    ('authority','invalid_care_authority'),('duty','duplicate_care_work'),
    ('arrangement','invalid_social_arrangement'),('scope','care_education_scope_mismatch')])
def test_invalid_original_care_declarations_reject_even_with_unknown_education(change,code):
    data=fixture();care=data['request']['care']
    data['request']['education']['services'][0]['eligibility']='unknown'
    if change=='beneficiary':care['obligations'][0]['beneficiary_id']='food'
    if change=='provider':care['obligations'][0]['provider_id']='west:cohort'
    if change=='authority':care['obligations'][0]['authority_id']='region-authority'
    if change=='duty':care['obligations'].append(care['obligations'][0]|{'id':'duplicate:duty'})
    if change=='arrangement':care['arrangements'][0]['id']='school'
    if change=='scope':care['scope_id']='west'
    with pytest.raises(ValueError,match=code):run(data)


def test_unknown_population_withholds_pair_and_retains_education_inputs():
    data=fixture()
    for value in data['inputs']['values']:
        if value['property_id']=='population':value['value']=dict(kind='unknown',reason='Unknown population')
    result=run(data)
    assert result.care.status=='unresolved' and result.batch is None
    assert result.education.status=='resolved'
    assert result.education.work.evaluation.batch.postings


@pytest.mark.parametrize('key', ['claim_order','holders','procedure','batch','activities'])
def test_complete_shared_work_input_must_match(key):
    data=fixture();w=data['request']['care']['work']
    if key=='claim_order':w[key]=list(reversed(w[key]))
    if key=='holders':w[key]=[]
    if key=='procedure':w[key]='all_or_nothing'
    if key=='batch':w[key]['reservations']=[]
    if key=='activities':w[key][0]['eligibility']='denied'
    with pytest.raises(AccountError,match='care_education_work_mismatch'):run(data)


@pytest.mark.parametrize('scope',['west','region'])
def test_real_pair_in_another_local_or_regional_scope(scope):
    # Retain household/network population overlap; move actual activity scope and
    # jurisdiction without changing canonical cohort or any account quantity.
    data=fixture()
    for req in (data['request']['care'],data['request']['education']):req['scope_id']=scope
    for w in work_inputs(data):
        for a in w['batch']['accounts']:a['scope_id']=scope
    edu=data['request']['education']
    for a in edu['facility_allocation']['batch']['accounts']:a['scope_id']=scope
    edu['bindings'][0]['scope_id']=scope
    for r in data['inputs']['relationships']:
        if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority' and r['to_id']=='east':r['to_id']=scope
    result=run(data)
    assert result.status=='resolved' and totals(result)==data['expected']['claims']
    assert result.care.population.value=='10'
