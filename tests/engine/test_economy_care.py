"""Actual DOM-02/05 allocation, independent finite oracles and host boundaries."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import conformance_catalog, ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.economy.care import evaluate_pair
from poliscope_engine.domains.economy.care_counterpart import (
    binding, host_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from economy_care_fixture import fixture, setup, trusted


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units)


def work_inputs(data):
    return data['request']['care']['work'], data['request']['economy']


def totals(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.economy.allocation.accounts.claims}


def closing(result):
    return {a.account_id: a.closing for a in result.economy.allocation.accounts.accounts}


def test_literal_shared_time_entitlements_and_retained_lineage():
    data = fixture(); before = deepcopy(data)
    result = run(data)
    assert result.status == 'resolved' and data == before
    assert result.care.population.value == data['expected']['population']
    assert [r.population.value for r in result.care.arrangements] == ['10', '10']
    duty = result.care.results[0]
    assert (duty.actual_before, duty.actual, duty.unmet) == ('1', '2', '0')
    assert duty.beneficiary_id == duty.provider_id == 'shared:cohort'
    assert duty.period_id == 'day:0' and duty.unit_id == 'hours'
    assert totals(result) == data['expected']['claims']
    assert closing(result) == data['expected']['closing']
    assert sum(p.id == 'prior:care' for p in result.batch.postings) == 1
    assert result.batch.postings[0] == result.request.economy.batch.postings[0]
    assert result.batch.reservations == result.request.economy.batch.reservations
    assert result.batch.subtotals == result.request.economy.batch.subtotals
    assert all(p.source_refs and p.mechanism_ref for p in result.batch.postings)
    assert result.care.work.evaluation == result.economy
    assert len([a for a in result.batch.accounts if a.id == 'labor']) == 1
    assert Fraction(closing(result)['raw']) + Fraction(totals(result)['goods'][0]) == 20
    assert run(data) == result


def case_for(inputs):
    return ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output','work',WORK], status='partial'),
        dict(node=['output','economy',CANDIDATE], status='partial')),
        trace_edges=((('output','work',WORK),('input','economy',BOOK)),))


def test_common_conformance_repeats_and_retains_private_book():
    request, inputs, graph, units = setup()
    registry, inputs = trusted(request, inputs, graph, units)
    case = case_for(inputs)
    first = run_bound_case(case, request=request, units=units, reviews=registry.reviews)
    assert first == run_bound_case(case, request=request, units=units, reviews=registry.reviews)
    assert first.accounts is None
    assert registry.bind(('authored:ec-work-mechanism','v1'),
        ('authored:ec-economy-mechanism','v1'), output_id=WORK, input_id=BOOK,
        world=graph.registry, scope_id='east', producer_entity_id='east-authority',
        consumer_entity_id='east-authority').kind == 'label'


@pytest.mark.parametrize('unknown', ['population','procedure','care','training','employment','goods','terms'])
def test_unknown_withholds_direct_and_common_candidate(unknown):
    data = fixture()
    if unknown == 'population': data['request']['care']['population_property_id'] = 'missing'
    else:
        for work in work_inputs(data):
            if unknown == 'procedure': work.update(procedure=None, claim_order=[])
            else:
                activity = next(a for a in work['activities'] if a['claim_id'] == ('goods' if unknown == 'terms' else unknown))
                activity.update(terms_known=False) if unknown == 'terms' else activity.update(eligibility='unknown')
    result = run(data)
    assert result.status == 'unresolved' and result.batch is None and result.economy is None
    if unknown == 'population':
        assert result.care.population.kind == 'unknown'
        assert result.care.results[0].actual == '2'
    else: assert result.care.results[0].actual is None
    request, inputs, graph, units = setup(data)
    registry, inputs = trusted(request, inputs, graph, units)
    case = ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output','economy',CANDIDATE],status='missing_input',value=None),))
    assert run_bound_case(case,request=request,units=units,reviews=registry.reviews).accounts is None


@pytest.mark.parametrize('claim', ['care','goods'])
def test_denial_preserves_prior_work_and_inspectable_unmet(claim):
    data = fixture()
    for work in work_inputs(data): next(a for a in work['activities'] if a['claim_id']==claim)['eligibility']='denied'
    result = run(data)
    assert result.status == 'resolved'
    if claim == 'care':
        assert totals(result)['care'] == ['1','2']
        assert (result.care.results[0].actual_before,result.care.results[0].actual,result.care.results[0].unmet)==('1','0','2')
        # The unused 1 h remaining care hold remains protected after denial.
        assert totals(result)['employment'] == ['7','1']
        assert closing(result)['labor'] == '1'
    else:
        assert totals(result)['goods'] == ['0','8'] and closing(result)['raw']=='20'


@pytest.mark.parametrize('change,code', [
    ('work','care_counterpart_work_mismatch'), ('period','counterpart_period_mismatch'),
    ('beneficiary','invalid_care_participants'), ('authority','invalid_care_authority'),
    ('mapping','unmapped_care_claim'), ('duplicate_duty','duplicate_care_work'),
    ('duplicate_time','duplicate_cohort_time_budget'), ('population_unit','invalid_arrangement_population'),
    ('claimant','counterpart_claimant_identity'), ('holder','counterpart_holder_identity'),
    ('account','counterpart_account_identity'), ('missing_time','counterpart_time_holders'),
    ('scope','incompatible_care_work_scope')])
def test_invalid_membership_identity_or_book_rejects(change,code):
    data = fixture(); req = data['request']
    if change == 'work': req['care']['work']['activities'][0]['access_limit']='2'
    if change == 'beneficiary': req['care']['obligations'][0]['beneficiary_id']='food'
    if change == 'authority': req['care']['obligations'][0]['authority_id']='region-authority'
    if change == 'duplicate_duty': req['care']['obligations'].append(req['care']['obligations'][0]|{'id':'duty:2'})
    if change == 'population_unit': data['inputs']['values'][-1]['value']['unit_id']='kg'
    for work in work_inputs(data):
        if change == 'period': work['period_id']='day:1'
        if change == 'mapping': work['activities'][1]['kind']='care'
        if change == 'claimant': work['batch']['claims'][0]['claimant_id']='food'
        if change == 'holder': work['holders'][0]['holder_id']='food'
        if change == 'account': next(a for a in data['inputs']['entities'] if a['id']=='raw')['entity_kind']='resource'
        if change == 'missing_time': work['holders']=work['holders'][1:]
        if change == 'scope': work['batch']['accounts'][0]['scope_id']='west'
        if change == 'duplicate_time':
            work['batch']['accounts'].append(next(a for a in work['batch']['accounts'] if a['id']=='labor')|{'id':'duplicate:time'})
            work['holders'].append(dict(account_id='duplicate:time',holder_id='shared:cohort',role='time'))
    if change=='duplicate_time': data['inputs']['entities'].append(data['inputs']['entities'][0]|{'id':'duplicate:time','entity_kind':'account'})
    before=deepcopy(data)
    with pytest.raises(ValueError,match=code): run(data)
    assert data==before


@pytest.mark.parametrize('order', [('care','training','employment','goods'),('employment','training','care','goods')])
def test_independent_finite_feasibility_oracle(order):
    # Enumerate feasible final care/training/employment totals independently of
    # allocator code. 1 h is already spent on care; its remaining 1 h hold is
    # protected from other work. Lexicographic maxima implement authored order.
    for care, training, employment in product((2,4,6), (1,4), (4,8)):
        data=fixture()
        for work in work_inputs(data):
            work['claim_order']=list(order)
            for c in work['batch']['claims']:
                if c['id'] in ('care','training','employment'): c['requested']=str(dict(care=care,training=training,employment=employment)[c['id']])
            for a in work['activities']:
                if a['claim_id'] in ('care','training','employment'): a['access_limit']=str(dict(care=care,training=training,employment=employment)[a['claim_id']])
        feasible=[dict(care=c,training=t,employment=e) for c,t,e in product(range(2,care+1),range(training+1),range(employment+1)) if c+t+e<=12]
        expected=max(feasible,key=lambda v:tuple(v[k] for k in order if k!='goods'))
        result=run(data); observed=totals(result)
        assert {k:int(observed[k][0]) for k in expected}==expected
        assert int(closing(result)['labor'])==12-sum(expected.values())
        assert observed['goods']==['4','4'] and closing(result)['raw']=='16'
        assert int(result.care.results[0].unmet)==care-expected['care']


@pytest.mark.parametrize('population',['0','1','17','1000'])
def test_population_union_creates_neither_people_nor_time(population):
    data=fixture();data['inputs']['values'][-1]['value']['value']=population
    result=run(data)
    assert result.care.population.value==population
    assert [r.population.value for r in result.care.arrangements]==[population,population]
    assert totals(result)==data['expected']['claims']


@pytest.mark.parametrize('change',['request','world','units','membership'])
def test_stale_bound_context_rejects(change):
    from poliscope_engine.numeric import Registry
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    if change=='request':request.care.obligations[0]=request.care.obligations[0].model_copy(update={'obligation_ref':'changed'})
    if change=='world':inputs=inputs.model_copy(update={'entities':[inputs.entities[0].model_copy(update={'label':'changed'}),*inputs.entities[1:]]})
    if change=='membership':inputs=inputs.model_copy(update={'relationships':inputs.relationships[:-1]})
    if change=='units':units=Registry(tuple(replace(u,scale=u.scale*2) if u.id=='people' else u for u in units.units))
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=registry.reviews)


def test_opaque_book_forgery_detachment_and_explicit_reviews():
    request,inputs,graph,units=setup()
    unreviewed=host_registry(request,graph=graph,units=units,reviews=[])
    with pytest.raises(MechanismError,match='review_required'):
        unreviewed.activate('authored:ec-work-mechanism','v1',phase='static',world=graph.registry,scope_id='east',entity_id='east-authority')
    registry,_=trusted(request,inputs,graph,units); callbacks={i.id:i.callback for i in registry.implementations}
    with pytest.raises(AccountError,match='stale_counterpart_context'):callbacks['authored:ec-work'](WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'):callbacks['authored:ec-economy'](CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    staged=callbacks['authored:ec-work'](WORK,{CONTEXT:LabelValue(kind='label',value=binding(request,graph,units))})
    first=callbacks['authored:ec-economy'](CANDIDATE,{BOOK:LabelValue(**staged)})
    request.care.obligations.clear()
    assert callbacks['authored:ec-economy'](CANDIDATE,{BOOK:LabelValue(**staged)})==first
    result=run(); result.batch.postings.clear(); assert run().batch.postings


@pytest.mark.parametrize('field',['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_execution_identity_rejects(field):
    request,inputs,graph,units=setup();registry,inputs=trusted(request,inputs,graph,units)
    inputs=inputs.model_copy(update={'versions':inputs.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):
        run_bound_case(case_for(inputs),request=request,units=units,reviews=registry.reviews)


def test_nested_forged_dto_revalidated():
    from pydantic import ValidationError
    request,_,graph,units=setup();request.care.obligations.append(dict(id='forged'))
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):evaluate_pair(request,graph=graph,units=units)


@pytest.mark.parametrize('procedure', ['priority','all_or_nothing'])
def test_independent_goods_stock_entitlement_oracle(procedure):
    for stock, rights, rate in product((0,3,20),(0,2,5),('0.5','1','2')):
        data=fixture()
        for work in work_inputs(data):
            work['procedure']=procedure
            next(a for a in work['batch']['accounts'] if a['id']=='raw')['opening']=str(stock)
            right=next(a for a in work['batch']['accounts'] if a['id']=='rights')
            right.update(opening=str(rights),quantum='0.1')
            next(a for a in work['activities'] if a['claim_id']=='goods')['requirements'][0]['per_unit']=rate
        # Feasible integer goods quantities; physical stock and institutional
        # capacity are independent constraints. No allocator or Decimal helper.
        feasible=[n for n in range(9) if n<=stock and n*Fraction(rate)<=rights]
        expected=max(feasible) if procedure=='priority' else (8 if 8 in feasible else 0)
        result=run(data)
        assert totals(result)['goods']==[str(expected),str(8-expected)]
        assert Fraction(closing(result)['raw'])==stock-expected
        assert Fraction(closing(result)['rights'])==rights-expected*Fraction(rate)
        assert result.care.results[0].actual=='2'


@pytest.mark.parametrize('kind', ['paid_work','unpaid_work','participation'])
def test_work_categories_share_time_without_inferred_income(kind):
    data=fixture()
    for work in work_inputs(data):work['activities'][2]['kind']=kind
    result=run(data)
    assert totals(result)==data['expected']['claims']
    assert next(i for i in result.care.work.indicators if i.claim_id=='employment').kind==kind
    assert {a.id for a in result.batch.accounts}=={'raw','labor','rights'}


def test_second_beneficiary_and_obligation_share_canonical_time():
    data=fixture()
    for work in work_inputs(data):
        claim=deepcopy(work['batch']['claims'][0]); claim.update(id='care:network',requested='5')
        work['batch']['claims'].append(claim)
        activity=deepcopy(work['activities'][0]);activity.update(claim_id='care:network',access_limit='5')
        work['activities'].append(activity)
        work['claim_order'].insert(1,'care:network')
    care=data['request']['care']; care['obligations'].append(care['obligations'][0]|dict(id='duty:network',claim_id='care:network',arrangement_id='network'))
    result=run(data)
    assert [r.actual for r in result.care.results]==['2','5']
    assert totals(result)['employment']==['1','7']
    assert result.care.population.value=='10' and closing(result)['labor']=='0'


def test_funding_does_not_create_goods_or_time():
    data=fixture()
    for work in work_inputs(data):
        right=next(a for a in work['batch']['accounts'] if a['id']=='rights')
        work['batch']['accounts'].append(right|dict(id='funds',opening='2'))
        work['holders'].append(dict(account_id='funds',holder_id='shared:cohort',role='funding'))
        work['activities'][-1]['requirements'].append(dict(account_id='funds',kind='funding',per_unit='1'))
    data['inputs']['entities'].append(data['inputs']['entities'][0]|dict(id='funds',entity_kind='account'))
    result=run(data)
    assert totals(result)['goods']==['2','6']
    assert closing(result)['raw']=='18' and closing(result)['funds']=='0'
    assert totals(result)['employment']==['6','2']


@pytest.mark.parametrize('change,code', [('port','interface_type_mismatch'),('reference','counterpart_identity_mismatch'),('fixture','unresolved_counterpart_fixture')])
def test_catalog_rejects_forged_pair_declarations(change,code):
    from poliscope_engine.domains import DomainRegistry
    from poliscope_engine.contracts.mechanisms import ReferenceType
    from poliscope_engine.contracts.packs import Identity
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    catalog=conformance_catalog();modules,pairs=list(catalog.modules),list(catalog.pairs)
    module=next(m for m in modules if m.domain=='economy')
    port=next(i for i in module.interfaces if i.port_id==BOOK)
    if change=='port':module.interfaces[module.interfaces.index(port)]=port.model_copy(update={'value_type':ReferenceType(kind='reference',entity_kind='account')})
    if change=='reference':port.references.pop()
    if change=='fixture':next(p for p in pairs if p.id=='pair:DOM-02:DOM-05').fixture_refs[0]=Identity(id='forged',version='v1')
    with pytest.raises(ConformanceError,match=code):
        DomainRegistry(modules,pairs).validate(world=graph.registry,mechanisms=registry,branch_ids=[c.branch_id for m in modules for c in m.coverage])


def test_no_other_pair_callbacks_or_reviews_are_granted():
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    assert {i.id for i in registry.implementations}=={'authored:ec-work','authored:ec-economy'}
    assert len(registry.reviews) == 2
    with pytest.raises(MechanismError,match='unknown_implementation'):
        registry.activate('authored:ea-administration-mechanism','v1',phase='static',world=graph.registry,scope_id='east',entity_id='east-authority')


def test_book_token_from_different_obligation_is_rejected():
    request,inputs,graph,units=setup();registry,_=trusted(request,inputs,graph,units)
    old={i.id:i.callback for i in registry.implementations}
    token=old['authored:ec-work'](WORK,{CONTEXT:LabelValue(kind='label',value=binding(request,graph,units))})
    request.care.obligations[0]=request.care.obligations[0].model_copy(update={'obligation_ref':'different'})
    new_registry=host_registry(request,graph=graph,units=units,reviews=registry.reviews)
    new={i.id:i.callback for i in new_registry.implementations}
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        new['authored:ec-economy'](CANDIDATE,{BOOK:LabelValue(**token)})
