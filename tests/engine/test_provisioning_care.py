"""Real care -> provisioning conformance and independent finite-book oracles."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.provisioning_care import ProvisioningCareRequest
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import conformance_catalog, ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.provisioning.care import evaluate_pair
from poliscope_engine.domains.provisioning.care_counterpart import (
    binding, host_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from provisioning_care_fixture import fixture, setup, trusted


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units)


def work_inputs(data):
    req = data['request']
    return req['care']['work'], req['provisioning']['work'], req['provisioning']['chain']


def test_literal_population_time_mass_and_retained_lineage():
    data = fixture(); before = deepcopy(data)
    result = run(data)
    assert result.status == 'resolved' and data == before
    expected = data['expected']['care']
    assert result.care.population.value == expected['population']
    assert [r.population.value for r in result.care.arrangements] == ['10', '10']
    duty = result.care.results[0]
    assert (duty.actual_before, duty.actual, duty.unmet) == (
        expected['actual_before'], expected['actual'], expected['unmet'])
    assert duty.beneficiary_id == duty.provider_id == 'shared:cohort'
    assert duty.period_id == 'day:0' and duty.unit_id == 'hours'
    accounts = result.provisioning.provisioning.accounts
    assert {a.account_id:a.closing for a in accounts.accounts} == data['expected']['accounts']
    assert {c.claim_id:[c.actual,c.unmet] for c in accounts.claims} == data['expected']['claims']
    assert sum(p.id == 'prior:care' for p in result.batch.postings) == 1
    assert result.batch.postings[0] == result.request.care.work.batch.postings[0]
    assert result.batch.reservations == result.request.care.work.batch.reservations
    assert result.batch.subtotals == result.request.care.work.batch.subtotals
    assert all(p.source_refs and p.mechanism_ref for p in result.batch.postings)
    assert result.care.work.evaluation == result.provisioning.work
    assert result.provisioning.provisioning.request.batch == result.care.work.evaluation.batch
    assert len([a for a in result.batch.accounts if a.id == 'labor']) == 1
    assert all(p in result.batch.postings for p in result.care.work.evaluation.batch.postings)
    b = {a.account_id:Fraction(a.closing) for a in accounts.accounts}
    assert sum(b[a] for a in ['raw','product','residual','receiving','stored']) + 1 + 1 == 20
    assert run(data) == result


def case_for(inputs):
    return ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output','work',WORK],status='partial'),
        dict(node=['output','provision',CANDIDATE],status='partial')),
        trace_edges=((('output','work',WORK),('input','provision',BOOK)),))


def test_common_conformance_runs_real_care_and_provisioning_repeatedly():
    request, inputs, graph, units = setup()
    registry, inputs = trusted(request, inputs, graph, units)
    case = case_for(inputs)
    first = run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert first == run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert first.accounts is None
    assert registry.bind(('authored:care-work-mechanism','v1'),
        ('authored:care-provisioning-mechanism','v1'),output_id=WORK,input_id=BOOK,
        world=graph.registry,scope_id='east',producer_entity_id='east-authority',
        consumer_entity_id='east-authority').kind == 'label'


@pytest.mark.parametrize('unknown',['population','procedure','care','training','production','use'])
def test_unknown_inputs_withhold_complete_candidate(unknown):
    data = fixture(); req = data['request']
    if unknown == 'population': req['care']['population_property_id'] = 'missing'
    elif unknown in ('procedure','care','training'):
        for work in work_inputs(data)[:2]:
            if unknown == 'procedure': work.update(procedure=None,claim_order=[])
            else: next(a for a in work['activities'] if a['claim_id']==unknown)['eligibility']='unknown'
    elif unknown == 'production': req['provisioning']['chain']['phases'][0]['choices'][0]['funding_known']=False
    else: req['provisioning']['use_terms'][0]['activities'][0]['terms_known']=False
    result = run(data)
    assert result.status == 'unresolved' and result.batch is None
    if unknown in ('population','procedure','care','training'):
        assert result.provisioning is None
    if unknown == 'population':
        assert result.care.population.kind == 'unknown'
        assert result.care.results[0].actual == '2'
    elif unknown in ('procedure','care','training'):
        assert result.care.results[0].actual is None


def test_care_denial_and_goods_denial_leave_distinct_unmet_evidence():
    data = fixture()
    for work in work_inputs(data)[:2]: work['activities'][0]['eligibility']='denied'
    data['request']['provisioning']['use_terms'][0]['activities'][0]['eligibility']='denied'
    result = run(data)
    assert result.status == 'resolved'
    assert (result.care.results[0].actual_before,result.care.results[0].actual,result.care.results[0].unmet)==('1','0','2')
    use = next(a for a in result.provisioning.provisioning.phases[-1].evidence.actuals if a.claim_id == 'eat-food')
    assert use.reason == 'denied' and use.allocated == '0' and use.unmet == '6'


@pytest.mark.parametrize('change,code',[
    ('work','care_counterpart_work_mismatch'),('period','counterpart_period_mismatch'),
    ('beneficiary','invalid_care_participants'),('authority','invalid_care_authority'),
    ('mapping','unmapped_care_claim'),('duplicate_duty','duplicate_care_work'),
    ('duplicate_time','duplicate_cohort_time_budget'),('population_unit','invalid_arrangement_population'),
    ('prior_book','counterpart_batch_mismatch'),('claimant','counterpart_claimant_identity')])
def test_invalid_authority_membership_or_book_rejects_without_mutation(change,code):
    data=fixture();req=data['request']
    if change=='work': req['care']['work']['activities'][0]['access_limit']='2'
    if change=='period': req['provisioning']['chain']['period_id']='day:1'
    if change=='beneficiary': req['care']['obligations'][0]['beneficiary_id']='food'
    if change=='authority': req['care']['obligations'][0]['authority_id']='region-authority'
    if change=='mapping':
        for work in work_inputs(data)[:2]: work['activities'][1]['kind']='care'
    if change=='duplicate_duty':req['care']['obligations'].append(req['care']['obligations'][0]|{'id':'duty:2'})
    if change=='population_unit':data['inputs']['values'][-1]['value']['unit_id']='kg'
    if change=='prior_book':req['provisioning']['chain']['batch']['postings'][0]['amount']='2'
    if change=='claimant':req['provisioning']['chain']['phases'][0]['claims'][0]['claimant_id']='food'
    if change=='duplicate_time':
        for work in work_inputs(data):work['batch']['accounts'].append(work['batch']['accounts'][5]|{'id':'duplicate:time'})
        for work in work_inputs(data)[:2]:work['holders'].append(dict(account_id='duplicate:time',holder_id='shared:cohort',role='time'))
        data['inputs']['entities'].append(data['inputs']['entities'][0]|{'id':'duplicate:time','entity_kind':'account'})
    before=deepcopy(data)
    with pytest.raises(ValueError,match=code):run(data)
    assert data==before


def test_independent_care_training_time_and_mass_oracle():
    # 12 h total, including 1 h already posted. Integer arithmetic is independent
    # of the Decimal allocator. One 10 kg batch costs 5 h and yields 7+2+1 kg.
    for care, training in product(range(2,6),range(4)):
        data=fixture()
        for work in work_inputs(data):
            work['batch']['claims'][0]['requested']=str(care)
            work['batch']['claims'][1]['requested']=str(training)
        for work in work_inputs(data)[:2]:
            work['activities'][0]['access_limit']=str(care)
        result=run(data)
        duty=result.care.results[0]
        assert (int(duty.actual_before)+int(duty.actual),int(duty.unmet))==(care,0)
        hours=12-care-training
        raw=10*(hours//5)
        delivered=min(raw*7//10,(hours-raw//2)*2,10)
        stored=min(3,delivered); used=min(1,stored)
        claims={c.claim_id:int(c.actual) for c in result.provisioning.provisioning.accounts.claims}
        assert claims==dict(care=care,training=training,**{'make-food':raw,'ship-food':delivered,'store-food':stored,'eat-food':used})
        b={a.account_id:Fraction(a.closing) for a in result.provisioning.provisioning.accounts.accounts}
        assert sum(b[a] for a in ['raw','product','residual','receiving','stored'])+raw//10+used==20
        assert b['labor']==12-care-training-raw//2-Fraction(delivered,2)


@pytest.mark.parametrize('change',['request','world','units','membership'])
def test_stale_bound_context_rejects(change):
    from poliscope_engine.numeric import Registry
    request,inputs,graph,units=setup()
    registry,inputs=trusted(request,inputs,graph,units)
    if change=='request':request.care.obligations[0]=request.care.obligations[0].model_copy(update={'obligation_ref':'changed'})
    if change=='world':inputs=inputs.model_copy(update={'entities':[inputs.entities[0].model_copy(update={'label':'changed'}),*inputs.entities[1:]]})
    if change=='membership':inputs=inputs.model_copy(update={'relationships':inputs.relationships[:-1]})
    if change=='units':units=Registry(tuple(replace(u,scale=u.scale*2) if u.id=='people' else u for u in units.units))
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=registry.reviews)


def test_opaque_books_forgery_detachment_and_explicit_reviews():
    request,inputs,graph,units=setup()
    unreviewed=host_registry(request,graph=graph,units=units,reviews=[])
    with pytest.raises(MechanismError,match='review_required'):
        unreviewed.activate('authored:care-work-mechanism','v1',phase='static',world=graph.registry,scope_id='east',entity_id='east-authority')
    registry,_=trusted(request,inputs,graph,units)
    callbacks={i.id:i.callback for i in registry.implementations}
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        callbacks['authored:care-work'](WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        callbacks['authored:care-provisioning'](CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    staged=callbacks['authored:care-work'](WORK,{CONTEXT:LabelValue(kind='label',value=binding(request,graph,units))})
    first=callbacks['authored:care-provisioning'](CANDIDATE,{BOOK:LabelValue(**staged)})
    request.care.obligations.clear()
    assert callbacks['authored:care-provisioning'](CANDIDATE,{BOOK:LabelValue(**staged)})==first
    result=run();result.batch.postings.clear()
    assert run().batch.postings


@pytest.mark.parametrize('field',['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_execution_identity_rejects(field):
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    inputs=inputs.model_copy(update={'versions':inputs.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=registry.reviews)


@pytest.mark.parametrize('population',['0','1','17','1000'])
def test_population_union_does_not_multiply_people_or_time(population):
    data=fixture();data['inputs']['values'][-1]['value']['value']=population
    result=run(data)
    assert result.care.population.value==population
    assert [r.population.value for r in result.care.arrangements]==[population,population]
    assert result.care.results[0].actual=='2'
    assert len([a for a in result.batch.accounts if a.id=='labor'])==1


def test_nested_forged_dto_is_revalidated():
    from pydantic import ValidationError
    request,_,graph,units=setup()
    request.care.obligations.append(dict(id='forged'))
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):evaluate_pair(request,graph=graph,units=units)


@pytest.mark.parametrize('change,code',[
    ('port','interface_type_mismatch'),('reference','counterpart_identity_mismatch'),
    ('fixture','unresolved_counterpart_fixture')])
def test_care_catalog_rejects_forged_declarations(change,code):
    from poliscope_engine.domains import DomainRegistry
    from poliscope_engine.contracts.mechanisms import ReferenceType
    from poliscope_engine.contracts.packs import Identity
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    catalog=conformance_catalog();modules,pairs=list(catalog.modules),list(catalog.pairs)
    module=next(m for m in modules if m.domain=='provisioning')
    port=next(i for i in module.interfaces if i.port_id==BOOK)
    if change=='port':module.interfaces[module.interfaces.index(port)]=port.model_copy(update={'value_type':ReferenceType(kind='reference',entity_kind='account')})
    if change=='reference':port.references.pop()
    if change=='fixture':next(p for p in pairs if p.id=='pair:DOM-01:DOM-05').fixture_refs[0]=Identity(id='forged',version='v1')
    with pytest.raises(ConformanceError,match=code):
        DomainRegistry(modules,pairs).validate(world=graph.registry,mechanisms=registry,branch_ids=[c.branch_id for m in modules for c in m.coverage])


@pytest.mark.parametrize('unknown',['population','work','use'])
def test_common_conformance_propagates_unknown_without_candidate(unknown):
    data=fixture()
    if unknown=='population':data['request']['care']['population_property_id']='missing'
    if unknown=='work':
        for work in work_inputs(data)[:2]:work['activities'][0]['terms_known']=False
    if unknown=='use':data['request']['provisioning']['use_terms'][0]['activities'][0]['terms_known']=False
    request,inputs,graph,units=setup(data);registry,inputs=trusted(request,inputs,graph,units)
    case=ConformanceCase(inputs=inputs,outcome='incomplete',observations=(dict(node=['output','provision',CANDIDATE],status='missing_input',value=None),))
    result=run_bound_case(case,request=request,units=units,reviews=registry.reviews)
    assert result.accounts is None
