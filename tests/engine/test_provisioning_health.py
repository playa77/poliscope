"""Real health -> provisioning conformance; independently authored finite oracles."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.provisioning_health import ProvisioningHealthRequest
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import conformance_catalog, ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.provisioning.health import evaluate_pair
from poliscope_engine.domains.provisioning.health_counterpart import (
    binding, host_registry, policy_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from provisioning_health_fixture import fixture, setup, trusted


def run(data=None):
    request, inputs, graph, units = setup(data)
    registry, _ = trusted(request, inputs, graph, units)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=registry.reviews))


def work_inputs(data):
    req = data['request']
    return req['health']['work'], req['provisioning']['work'], req['provisioning']['chain']


def case_for(inputs):
    return ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output','work',WORK],status='partial'),
        dict(node=['output','provision',CANDIDATE],status='partial')),
        trace_edges=((('output','work',WORK),('input','provision',BOOK)),))


def test_literal_shared_time_supplies_facilities_and_mass():
    data=fixture();before=deepcopy(data);result=run(data)
    assert data==before and result.status=='resolved' and run(data)==result
    assert result.health.results[0].outcome=='capacity_ready'
    assert {a.account_id:a.closing for a in result.provisioning.accounts.accounts}==data['expected']['accounts']
    assert {c.claim_id:[c.actual,c.unmet] for c in result.provisioning.accounts.claims}==data['expected']['claims']
    assert len([a for a in result.batch.accounts if a.id=='labor'])==1
    assert sum(p.id=='prior:care' for p in result.batch.postings)==1
    assert all(p in result.batch.postings for p in result.health.work.evaluation.batch.postings)
    assert result.batch.reservations==result.request.health.work.batch.reservations
    assert result.batch.subtotals==result.request.health.work.batch.subtotals
    assert result.batch.accounts==result.request.provisioning.chain.batch.accounts
    assert all(p.source_refs and p.mechanism_ref for p in result.batch.postings)
    facilities=result.health.facility_allocation
    assert [(a.claim_id,a.allocated,a.unmet) for a in facilities.actuals]==[('other-seat','1','1'),('seat','1','0')]
    assert sum(p.id=='prior:seat' for p in facilities.batch.postings)==1
    assert facilities.accounts.accounts[0].closing=='0'
    assert 'clinic:slots' not in {a.id for a in result.batch.accounts}
    assert not any(p.source_id=='clinic:slots' for p in result.batch.postings)
    b={a.account_id:Fraction(a.closing) for a in result.provisioning.accounts.accounts}
    assert sum(b[a] for a in ['raw','product','residual','receiving','stored'])+2+1+1==20


def test_common_conformance_runs_actual_services_repeatedly():
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    case=case_for(inputs)
    result=run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert result==run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert result.accounts is None
    assert registry.bind(('authored:health-work-mechanism','v1'),
        ('authored:health-provisioning-mechanism','v1'),output_id=WORK,input_id=BOOK,
        world=graph.registry,scope_id='east',producer_entity_id='east-authority',
        consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('unknown',['policy','eligibility','qualification','work','materials','facility','production','use'])
def test_unknown_withholds_complete_candidate_but_retains_independent_commitments(unknown):
    data=fixture();edu=data['request']['health']
    if unknown=='policy':edu['bindings'][0]['value']=dict(kind='unknown',reason='Unknown permission')
    if unknown=='eligibility':edu['services'][0]['eligibility']='unknown'
    if unknown=='qualification':edu['services'][0]['staff'][0]['qualification']='unknown'
    if unknown in ('work','materials'):
        for w in work_inputs(data)[:2]:next(a for a in w['activities'] if a['claim_id']==('beneficiary-care' if unknown=='work' else 'materials'))['terms_known']=False
    if unknown=='facility':edu['facility_allocation']['choices'][0]['funding_known']=False
    if unknown=='production':data['request']['provisioning']['chain']['phases'][0]['choices'][0]['funding_known']=False
    if unknown=='use':data['request']['provisioning']['use_terms'][0]['activities'][0]['terms_known']=False
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    if unknown not in ('production','use'):assert result.provisioning is None
    if unknown in ('policy','eligibility','qualification','facility'):
        assert result.health.work.evaluation.batch is not None
        assert result.health.work.evaluation.batch.postings
    if unknown in ('work','materials'):
        assert result.health.facility_allocation.status=='resolved'


@pytest.mark.parametrize('blocked',['eligibility','qualification','materials','seat'])
def test_denied_or_short_prerequisite_is_resolved_and_does_not_refund_other_inputs(blocked):
    data=fixture();edu=data['request']['health']
    if blocked=='eligibility':edu['services'][0]['eligibility']='denied'
    if blocked=='qualification':edu['services'][0]['staff'][0]['qualification']='not_qualified'
    if blocked=='materials':
        for w in work_inputs(data)[:2]:next(a for a in w['activities'] if a['claim_id']=='materials')['eligibility']='denied'
    if blocked=='seat':edu['facility_allocation']['claim_order']=['other-seat','seat'];edu['facility_allocation']['batch']['reservations']=[];edu['facility_allocation']['batch']['postings'][0]['reservation_id']=None
    result=run(data);service=result.health.results[0]
    assert result.status=='resolved'
    assert service.outcome==dict(eligibility='ineligible',qualification='unqualified',materials='capacity_blocked',seat='capacity_blocked')[blocked]
    assert next(c for c in result.provisioning.accounts.claims if c.claim_id=='clinical-work').actual=='2'
    assert next(c for c in result.provisioning.accounts.claims if c.claim_id=='beneficiary-care').actual=='3'
    if blocked in ('materials','seat'):assert blocked in service.unmet_claim_ids
    if blocked=='materials':assert next(a for a in result.provisioning.accounts.accounts if a.account_id=='raw').closing=='10'


def test_actual_policy_conflict_retains_committed_inputs_and_withholds_chain():
    data=fixture();edu=data['request']['health']
    edu['bindings'].append(deepcopy(edu['bindings'][0])|{'id':'competing-policy','value':dict(kind='label',value='other_permission')})
    result=run(data)
    assert result.status=='unresolved' and result.provisioning is None
    assert result.health.policies.results[0].status=='conflict'
    assert result.health.results[0].findings==['institutional_conflict']
    assert result.health.work.status=='resolved'


def test_independent_time_material_and_facility_oracles():
    # Whole integer arithmetic; no calls to engine numeric/allocator helpers.
    # Beneficiary and staff are one cohort; all duties consume the same time budget.
    for care,staff,materials in product(range(1,5),range(1,4),range(1,4)):
        data=fixture()
        for w in work_inputs(data):
            for cid,n in [('beneficiary-care',care),('clinical-work',staff),('materials',materials)]:
                next(c for c in w['batch']['claims'] if c['id']==cid)['requested']=str(n)
        for w in work_inputs(data)[:2]:
            for cid,n in [('beneficiary-care',care),('clinical-work',staff),('materials',materials)]:next(a for a in w['activities'] if a['claim_id']==cid)['access_limit']=str(n)
        result=run(data)
        hours=14-3-care-staff
        raw=10*min((20-materials)//10,hours//5)
        delivered=min(raw*7//10,(hours-raw//2)*2,10)
        stored=min(3,delivered);used=min(1,stored)
        claims={c.claim_id:int(c.actual) for c in result.provisioning.accounts.claims}
        assert claims=={'care':3,'beneficiary-care':care,'clinical-work':staff,'materials':materials,
            'make-food':raw,'ship-food':delivered,'store-food':stored,'eat-food':used}
        b={a.account_id:Fraction(a.closing) for a in result.provisioning.accounts.accounts}
        assert b['labor']==hours-raw//2-Fraction(delivered,2)
        assert sum(b[a] for a in ['raw','product','residual','receiving','stored'])+materials+raw//10+used==20
        assert sum(int(p.amount) for p in result.health.facility_allocation.batch.postings)==3


@pytest.mark.parametrize('change,code',[
    ('work','health_counterpart_work_mismatch'),('book','counterpart_batch_mismatch'),
    ('period','counterpart_period_mismatch'),('authority','invalid_health_authority'),
    ('qualification','missing_health_qualification_reference'),
    ('duplicate_time','duplicate_cohort_time_budget'),('pool','health_counterpart_pool_collision'),
    ('facility_period','incompatible_health_scope_period'),
    ('resource','counterpart_resource_identity'),('remote_supply','health_counterpart_work_mismatch')])
def test_invalid_context_or_double_budget_rejects_purely(change,code):
    data=fixture();req=data['request'];edu=req['health']
    if change=='work':edu['work']['activities'][0]['access_limit']='2'
    if change=='book':req['provisioning']['chain']['batch']['postings'][0]['amount']='2'
    if change=='period':req['provisioning']['chain']['period_id']='day:1'
    if change=='authority':edu['services'][0]['authority_id']='region-authority'
    if change=='qualification':edu['services'][0]['staff'][0]['qualification_refs']=[]
    if change=='facility_period':edu['facility_allocation']['batch']['accounts'][0]['period_id']='day:1'
    if change=='resource':req['provisioning']['chain']['resources'][0]['resource_id']='labor'
    if change=='remote_supply':next(c for c in edu['work']['batch']['claims'] if c['id']=='materials')['account_id']='stored'
    if change=='pool':edu['facility_allocation']['batch']['claims'][0]['id']='make-food'
    if change=='duplicate_time':
        for w in work_inputs(data):w['batch']['accounts'].append(next(a for a in w['batch']['accounts'] if a['id']=='labor')|{'id':'duplicate:time'})
        for w in work_inputs(data)[:2]:w['holders'].append(dict(account_id='duplicate:time',holder_id='shared:cohort',role='time'))
        data['inputs']['entities'].append(data['inputs']['entities'][0]|{'id':'duplicate:time','entity_kind':'account'})
    before=deepcopy(data)
    with pytest.raises(ValueError,match=code):run(data)
    assert data==before


@pytest.mark.parametrize('change',['request','world','units','membership','policy_review'])
def test_stale_complete_context_rejects(change):
    from poliscope_engine.numeric import Registry
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    reviews=registry.reviews
    if change=='request':request.health.services[0].need_refs.append('later')
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
        unreviewed.activate('authored:health-work-mechanism','v1',phase='static',world=graph.registry,scope_id='east',entity_id='east-authority')
    # Reviewing the two data ports does not implicitly review the policy.
    with pytest.raises(MechanismError,match='review_required'):
        evaluate_pair(request,graph=graph,units=units,mechanisms=policy_registry(units=units,reviews=registry.reviews[:2]))
    callbacks={i.id:i.callback for i in registry.implementations}
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        callbacks['authored:health-work'](WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        callbacks['authored:health-provisioning'](CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    policy=policy_registry(units=units,reviews=registry.reviews)
    staged=callbacks['authored:health-work'](WORK,{CONTEXT:LabelValue(kind='label',value=binding(request,graph,units,policy))})
    first=callbacks['authored:health-provisioning'](CANDIDATE,{BOOK:LabelValue(**staged)})
    request.health.services.clear()
    assert callbacks['authored:health-provisioning'](CANDIDATE,{BOOK:LabelValue(**staged)})==first
    result=run();result.batch.postings.clear();assert run().batch.postings
    with pytest.raises(AccountError,match='policy_callback_not_executable'):callbacks['authored:health-policy']()


@pytest.mark.parametrize('field',['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_execution_identity_rejects(field):
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    inputs=inputs.model_copy(update={'versions':inputs.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=registry.reviews)


@pytest.mark.parametrize('unknown',['policy','work','use'])
def test_common_conformance_unknown_is_missing_input(unknown):
    data=fixture()
    if unknown=='policy':data['request']['health']['services'][0]['staff'][0]['qualification']='unknown'
    if unknown=='work':
        for w in work_inputs(data)[:2]:w['activities'][0]['terms_known']=False
    if unknown=='use':data['request']['provisioning']['use_terms'][0]['activities'][0]['terms_known']=False
    request,inputs,graph,units=setup(data);registry,inputs=trusted(request,inputs,graph,units)
    case=ConformanceCase(inputs=inputs,outcome='incomplete',observations=(dict(node=['output','provision',CANDIDATE],status='missing_input',value=None),))
    assert run_bound_case(case,request=request,units=units,reviews=registry.reviews).accounts is None


def test_nested_forged_dto_and_foreign_policy_units_reject():
    from pydantic import ValidationError
    from poliscope_engine.numeric import Registry
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    with pytest.raises(AccountError,match='health_counterpart_policy_units'):
        evaluate_pair(request,graph=graph,units=units,mechanisms=policy_registry(units=Registry(()),reviews=registry.reviews))
    request.health.services.append(dict(id='forged'))
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
    port=next(i for m in modules if m.domain=='provisioning' for i in m.interfaces if i.port_id==BOOK)
    if change=='port':
        module=next(m for m in modules if m.domain=='provisioning')
        module.interfaces[module.interfaces.index(port)]=port.model_copy(update={'value_type':ReferenceType(kind='reference',entity_kind='account')})
    if change=='reference':port.references.pop()
    if change=='fixture':next(p for p in pairs if p.id=='pair:DOM-01:DOM-06').fixture_refs[0]=Identity(id='forged',version='v1')
    with pytest.raises(ConformanceError,match=code):
        DomainRegistry(modules,pairs).validate(world=graph.registry,mechanisms=registry,branch_ids=[c.branch_id for m in modules for c in m.coverage])


@pytest.mark.parametrize('capacity',[2,3,4,5])
def test_independent_facility_capacity_oracle(capacity):
    data=fixture()
    data['request']['health']['facility_allocation']['batch']['accounts'][0]['opening']=str(capacity)
    result=run(data);facility=result.health.facility_allocation
    # Seat has one prior fulfillment and a 2-slot hold. It spends one more;
    # the other claimant can consume at most two of the remainder.
    other=min(2,capacity-2)
    assert {a.claim_id:(int(a.actual),int(a.unmet)) for a in facility.accounts.claims}=={
        'seat':(2,0),'other-seat':(other,2-other)}
    assert int(facility.accounts.accounts[0].closing)==capacity-2-other
    assert result.health.results[0].outcome=='capacity_ready'
    assert {a.account_id:a.closing for a in result.provisioning.accounts.accounts}==data['expected']['accounts']


@pytest.mark.parametrize('selected',['health:policy','competing-policy'])
def test_explicit_actual_policy_selection_is_retained(selected):
    data=fixture();edu=data['request']['health']
    edu['bindings'].append(deepcopy(edu['bindings'][0])|{'id':'competing-policy','value':dict(kind='label',value='other_permission')})
    edu['rules']=[dict(contract_version=1,identity=dict(id='authored:health-selection',version='v1'),
        authority_id='east-authority',scope_id='east',entity_id='food',parameter_id='health:permission',
        participant_ids=['health:policy','competing-policy'],operation='select',selected_id=selected,
        source_refs=['authored:provisioning-health-v1'])]
    result=run(data)
    assert result.health.policies.results[0].status=='known'
    assert result.health.policies.results[0].rule.selected_id==selected
    if selected=='health:policy':assert result.health.results[0].outcome=='capacity_ready'
    else:
        assert result.status=='unresolved' and result.batch is None
        assert result.health.results[0].findings==['health_binding_not_selected']
        assert result.health.work.status=='resolved'


@pytest.mark.parametrize('kind',['training','paid_work','unpaid_work'])
def test_beneficiary_time_cannot_be_replaced_by_other_work(kind):
    data=fixture()
    for work in work_inputs(data)[:2]:
        next(a for a in work['activities'] if a['claim_id']=='beneficiary-care')['kind']=kind
    with pytest.raises(AccountError,match='invalid_health_activity'):
        run(data)


def test_health_context_references_bind_without_inventing_effects():
    data=fixture();baseline=run(data)
    service=data['request']['health']['services'][0]
    service['need_refs']=['synthetic:different-need']
    service['exposure_refs']=['synthetic:different-exposure']
    service['health_state_refs']=['synthetic:different-health-state']
    result=run(data)
    assert result.baseline_digest!=baseline.baseline_digest
    assert result.batch==baseline.batch
    assert result.health.results==baseline.health.results
    assert set(result.model_dump())=={'contract_version','adapter_version','baseline_digest',
        'evidence_status','status','request','health','provisioning','batch'}


@pytest.mark.parametrize('access',['denied','unknown'])
def test_local_beneficiary_access_remains_distinct_from_shared_supply(access):
    data=fixture()
    for work in work_inputs(data)[:2]:
        next(a for a in work['activities'] if a['claim_id']=='beneficiary-care')['eligibility']=access
    result=run(data)
    assert result.health.facility_allocation.status=='resolved'
    if access=='unknown':
        assert result.status=='unresolved' and result.batch is None
        assert 'unknown_work_capacity' in result.health.results[0].findings
    else:
        assert result.status=='resolved'
        assert result.health.results[0].outcome=='capacity_blocked'
        assert 'beneficiary-care' in result.health.results[0].unmet_claim_ids
        assert next(c for c in result.provisioning.accounts.claims if c.claim_id=='materials').actual=='2'
