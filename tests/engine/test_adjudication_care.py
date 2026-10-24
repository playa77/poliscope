"""Real DOM-04/05 composition with independent finite-book and legal prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.adjudication_care import AdjudicationCareRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.law_conflict.care import evaluate_pair, binding
from poliscope_engine.domains.law_conflict.care_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from adjudication_care_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-adjudication-care',
        'oracle:adjudication-care-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


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
        dict(node=['output','care',CANDIDATE],status='partial')),
        trace_edges=((('output','work',WORK),('input','care',BOOK)),))
    result=run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert result==run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert result.accounts is None
    assert reg.bind(('authored:ac-administration-mechanism','v1'),('authored:ac-care-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['adjudication']['cases'][0]['disposition']='dismissed';r=AdjudicationCareRequest.model_validate(data)
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
    work=callbacks['authored:ac-administration'];consumer=callbacks['authored:ac-care']
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
    omit={'administration':'authored:ac-administration-mechanism',
        'economy':'authored:ac-care-mechanism','policy':'authored:ac-policy-mechanism'}[missing]
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



def books(data):
    return data['request']['adjudication']['administration'], data['request']['care']['work']


def claims(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.care.work.evaluation.allocation.accounts.claims}


def balances(result):
    return {a.account_id: a.closing for a in result.care.work.evaluation.allocation.accounts.accounts}


def test_literal_book_population_lineage_and_detached_candidate():
    data = fixture(); before = deepcopy(data); result = run(data)
    assert result.status == 'resolved' and data == before
    assert data['identity'] == dict(id='synthetic:adjudication-care',version='v1')
    assert claims(result) == data['expected']['claims']
    assert balances(result) == data['expected']['closing']
    assert result.care.population.value == '10'
    assert [a.population.value for a in result.care.arrangements] == ['10', '10']
    duty = result.care.results[0]
    assert (duty.actual_before, duty.actual, duty.unmet) == ('1', '2', '0')
    assert result.care.request.work.batch == result.adjudication.administration.evaluation.batch
    assert result.batch.reservations == result.request.care.work.batch.reservations
    assert result.batch.subtotals == result.request.care.work.batch.subtotals
    assert all(sum(p.id == prior for p in result.batch.postings) == 1
               for prior in ['prior:admin', 'prior:care'])
    assert all(p.mechanism_ref and p.source_refs for p in result.batch.postings)
    assert run(data) == result
    result.batch.postings.clear()
    assert result.care.work.evaluation.batch.postings
    assert result.adjudication.administration.evaluation.batch.postings
    assert result.preflight.work.evaluation.batch.postings


def test_replay_and_later_rejection_preserve_prior_work_without_refund():
    first = run(); data = fixture()
    for phase in books(data): phase['batch'] = first.batch.model_dump()
    second = run(data)
    assert second.batch == first.batch
    assert second.care.results[0].actual == '0'
    data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    rejected = run(data)
    assert rejected.batch == first.batch
    assert rejected.care.results[0].actual_before == '3'
    assert rejected.care.results[0].actual == '0'


@pytest.mark.parametrize('outcome', ['upheld', 'dismissed', 'ineligible', 'capacity_blocked'])
@pytest.mark.parametrize('dependent', [True, False])
def test_case_outcomes_only_restrict_explicitly_dependent_new_care(outcome, dependent):
    data = fixture(); case = data['request']['adjudication']['cases'][0]
    if not dependent: data['request']['prerequisites'][0]['case_id'] = None
    if outcome == 'dismissed': case['disposition'] = 'dismissed'
    if outcome == 'ineligible': case['eligibility'] = 'ineligible'
    if outcome == 'capacity_blocked': books(data)[0]['activities'][0]['access_limit'] = '1'
    result = run(data)
    assert result.adjudication.results[0].outcome == outcome
    allowed = not dependent or outcome == 'upheld'
    assert claims(result)['care'] == (['3', '0'] if allowed else ['1', '2'])
    assert claims(result)['goods'] == ['4', '4']
    assert result.care.request.obligations == result.request.care.obligations
    assert result.adjudication.results[0].proposed_obligation_refs == case['obligation_refs']
    assert sum(p.id == 'prior:care' for p in result.batch.postings) == 1


@pytest.mark.parametrize('outcome', ['upheld', 'dismissed'])
@pytest.mark.parametrize('eligibility', ['denied', 'unknown'])
def test_original_care_access_is_never_granted_by_case(outcome, eligibility):
    data = fixture(); data['request']['adjudication']['cases'][0]['disposition'] = outcome
    books(data)[1]['activities'][1]['eligibility'] = eligibility
    result = run(data)
    if eligibility == 'unknown':
        assert result.status == 'unresolved' and result.batch is None
        assert result.care.results[0].actual is None
    else:
        assert claims(result)['care'] == ['1', '2']
        assert balances(result)['labor'] == '1'  # residual protected care hold


@pytest.mark.parametrize('missing', ['population','legal_eligibility','rights_conflict',
    'disposition','rationale','policy','admin_access','admin_terms','admin_procedure',
    'care_access','care_terms','care_procedure'])
def test_unknowns_withhold_direct_and_common_candidate(missing):
    data = fixture(); law = data['request']['adjudication']; case = law['cases'][0]
    admin, care = books(data)
    if missing == 'population': data['request']['care']['population_property_id'] = 'missing'
    elif missing == 'legal_eligibility': case['eligibility'] = 'unknown'
    elif missing == 'rights_conflict': case['incompatible_right_refs'] = ['synthetic:conflict']
    elif missing in ('disposition','rationale'): case[missing] = None
    elif missing == 'policy': law['bindings'][0]['value'] = dict(kind='unknown',reason='Missing declaration')
    else:
        phase = admin if missing.startswith('admin') else care
        if missing.endswith('procedure'): phase.update(procedure=None,claim_order=[])
        elif missing.endswith('access'): phase['activities'][0 if phase is admin else 1]['eligibility'] = 'unknown'
        else: phase['activities'][0 if phase is admin else 1]['terms_known'] = False
    result = run(data)
    assert result.status == 'unresolved' and result.batch is None
    if missing == 'population' or missing.startswith('care'):
        assert result.adjudication.results[0].outcome == 'upheld'
    else: assert result.care is None
    r,i,g,u = setup(data); reg,i = trusted(r,i,g,u)
    case = ConformanceCase(inputs=i,outcome='incomplete',observations=(
        dict(node=['output','care',CANDIDATE],status='missing_input',value=None),))
    assert run_bound_case(case,request=r,units=u,reviews=reg.reviews).accounts is None


@pytest.mark.parametrize('mutation,code', [
    ('book','book_mismatch'),('holders','book_mismatch'),('period','period_mismatch'),
    ('scope','scope_mismatch'),('mapping_missing','invalid_adjudication_care_mapping'),
    ('mapping_duplicate','invalid_adjudication_care_mapping'),('foreign_case','obligation_mapping'),
    ('beneficiary','obligation_mapping'),('target','obligation_mapping'),
    ('authority','obligation_mapping'),('obligation','obligation_mapping'),
    ('affected','obligation_mapping'),('open_future','open_phase_claim'),
    ('open_prior','open_phase_claim'),('missing_activity','invalid_economy_activities'),
    ('account','account_identity'),('claimant','claimant_identity'),('holder','holder_identity'),
    ('time_holder','time_holders'),('dated','period_mismatch'),
    ('membership','invalid_care_participants'),('care_authority','invalid_care_authority'),
    ('population_unit','invalid_arrangement_population')])
def test_invalid_inputs_reject_without_mutation(mutation, code):
    data = fixture(); req = data['request']; legal = req['adjudication']; care = req['care']
    admin, work = books(data); duty = care['obligations'][0]
    if mutation == 'book': work['batch']['accounts'][0]['opening'] = '19'
    elif mutation == 'holders': work['holders'] = []
    elif mutation == 'period': work['period_id'] = 'day:1'
    elif mutation == 'scope': care['scope_id'] = 'west'
    elif mutation == 'mapping_missing': req['prerequisites'][0]['obligation_id'] = 'missing'
    elif mutation == 'mapping_duplicate': req['prerequisites'].append(deepcopy(req['prerequisites'][0]))
    elif mutation == 'foreign_case': req['prerequisites'][0]['case_id'] = 'foreign'
    elif mutation == 'beneficiary': legal['cases'][0]['claimant_id'] = 'food'
    elif mutation == 'target': legal['cases'][0]['target_id'] = 'food'
    elif mutation == 'authority': legal['cases'][0]['authority_id'] = 'region-authority'
    elif mutation == 'obligation': legal['cases'][0]['obligation_refs'] = []
    elif mutation == 'affected': legal['bindings'][0]['account_refs'] = ['rights']
    elif mutation == 'open_future': admin['activities'][1]['eligibility'] = 'allowed'
    elif mutation == 'open_prior': work['activities'][0]['eligibility'] = 'allowed'
    elif mutation == 'missing_activity': admin['activities'].pop()
    elif mutation == 'membership': duty['beneficiary_id'] = 'food'; req['prerequisites'][0]['case_id'] = None
    elif mutation == 'care_authority': duty['authority_id'] = 'region-authority'; req['prerequisites'][0]['case_id'] = None
    elif mutation == 'account':
        next(e for e in data['inputs']['entities'] if e['id']=='raw')['entity_kind'] = 'resource'
    elif mutation == 'population_unit':
        for value in data['inputs']['values']:
            if value['property_id'] == 'population': value['value']['unit_id'] = 'kg'
    else:
        for phase in books(data):
            if mutation == 'account': phase['batch']['accounts'][0]['id'] = 'foreign'
            elif mutation == 'claimant': phase['batch']['claims'][0]['claimant_id'] = 'food'
            elif mutation == 'holder': phase['holders'][0]['holder_id'] = 'food'
            elif mutation == 'time_holder': phase['holders'] = [h for h in phase['holders'] if h['role'] != 'time']
            elif mutation == 'dated': phase['batch']['accounts'][1]['period_id'] = 'day:1'
    before = deepcopy(data)
    with pytest.raises((AccountError, ValueError),match=code): run(data)
    assert data == before


def test_invalid_original_membership_cannot_hide_behind_unknown_case():
    data = fixture(); data['request']['adjudication']['cases'][0]['disposition'] = None
    data['request']['care']['obligations'][0]['arrangement_id'] = 'missing'
    with pytest.raises(AccountError,match='invalid_care_participants'): run(data)


def test_exhaustive_independent_finite_time_and_held_budget_oracle():
    # Independent integer feasible sets; no allocator or Decimal implementation
    # supplies expected values. Two prior units, including one used care hold.
    for time, demand, dependent, disposition in product(range(3,11), range(2,6), [False,True], ['upheld','dismissed']):
        data = fixture(); req = data['request']
        req['prerequisites'][0]['case_id'] = 'case:access' if dependent else None
        req['adjudication']['cases'][0]['disposition'] = disposition
        for phase in books(data):
            next(a for a in phase['batch']['accounts'] if a['id']=='labor')['opening'] = str(time)
            next(c for c in phase['batch']['claims'] if c['id']=='care')['requested'] = str(demand)
        books(data)[1]['activities'][1]['access_limit'] = str(demand)
        result = run(data)
        # One residual reserved hour cannot finance case work, training or paid work.
        admin = max(a for a in range(1,4) if a+2 <= time)
        allowed = not dependent or (admin == 3 and disposition == 'upheld')
        care = max(c for c in range(1,demand+1) if admin+c <= time and (allowed or c==1))
        residual_hold = max(0,2-care)
        train, employment = max((t,w) for t,w in product(range(4),range(9))
            if admin+care+residual_hold+t+w <= time)
        expected = dict(admin=admin,care=care,training=train,employment=employment,goods=4)
        assert {cid:int(row[0]) for cid,row in claims(result).items()} == expected
        assert Fraction(balances(result)['labor']) + sum(Fraction(expected[c]) for c in ['admin','care','training','employment']) == time
        assert Fraction(balances(result)['raw']) + Fraction(expected['goods']) == 20
        assert Fraction(balances(result)['rights']) + Fraction(expected['goods']) == 4
        assert len(result.batch.accounts) == 3


@pytest.mark.parametrize('selected', [None, 'proposal', 'competing'])
def test_conflicting_authority_requires_explicit_selection_of_case_binding(selected):
    data = fixture(); law = data['request']['adjudication']
    other = deepcopy(law['bindings'][0]); other['id'] = 'competing'
    other['value']['value'] = 'different'; law['bindings'].append(other)
    if selected is not None:
        law['rules'] = [dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='east-authority',scope_id='east',entity_id='shared:cohort',parameter_id='ac:permission',
            participant_ids=['proposal','competing'],operation='select',selected_id=selected,
            source_refs=['authored:adjudication-care-v1'])]
    result = run(data)
    if selected == 'proposal':
        assert result.adjudication.results[0].outcome == 'upheld'
        assert claims(result) == data['expected']['claims']
    else:
        assert result.batch is None
        assert result.adjudication.results[0].findings == [
            'institutional_conflict' if selected is None else 'adjudication_binding_not_selected']


def test_multiple_obligations_retain_independent_care_and_canonical_population():
    data = fixture(); req = data['request']; care = req['care']
    duty = deepcopy(care['obligations'][0])
    duty.update(id='independent',arrangement_id='network',claim_id='training',
        authority_id=None,obligation_ref='synthetic:independent')
    care['obligations'].append(duty)
    req['prerequisites'].append(dict(obligation_id='independent',case_id=None))
    for phase in books(data):
        next(a for a in phase['activities'] if a['claim_id']=='training')['kind'] = 'care'
    req['adjudication']['cases'][0]['disposition'] = 'dismissed'
    result = run(data)
    assert result.care.population.value == '10'
    assert claims(result)['care'] == ['1', '2']
    assert claims(result)['training'] == ['3', '0']
    assert [(r.obligation_id,r.actual,r.unmet) for r in result.care.results] == [
        ('duty','0','2'), ('independent','3','0')]
    assert balances(result)['labor'] == '1'  # denied care's remaining hold is retained


def test_upheld_case_with_no_remaining_care_capacity_preserves_unmet_duty():
    data = fixture()
    for phase in books(data):
        next(a for a in phase['batch']['accounts'] if a['id']=='labor')['opening'] = '4'
        phase['batch']['reservations'] = []
        for posting in phase['batch']['postings']: posting['reservation_id'] = None
    result = run(data)
    assert result.adjudication.results[0].outcome == 'upheld'
    assert claims(result)['care'] == ['1', '2']
    assert result.care.results[0].unmet == '2'
    assert result.care.request.obligations == result.request.care.obligations


@pytest.mark.parametrize('field', ['eligibility', 'terms_known'])
def test_rejection_never_hides_unknown_original_care_terms(field):
    data = fixture(); data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    books(data)[1]['activities'][1][field] = 'unknown' if field=='eligibility' else False
    result = run(data)
    assert result.batch is None and result.status == 'unresolved'
    assert result.care.results[0].actual is None


def test_duplicate_case_work_and_duplicate_cohort_budgets_are_rejected():
    data = fixture(); law = data['request']['adjudication']
    case = deepcopy(law['cases'][0]); case['id'] = 'other:case'; law['cases'].append(case)
    with pytest.raises(AccountError,match='duplicate_case_work'): run(data)
    data = fixture()
    for phase in books(data):
        account = deepcopy(next(a for a in phase['batch']['accounts'] if a['id']=='labor'))
        account['id'] = 'duplicate:time'; phase['batch']['accounts'].append(account)
        holder = deepcopy(phase['holders'][0]); holder['account_id'] = account['id']; phase['holders'].append(holder)
    entity = deepcopy(data['inputs']['entities'][-1]); entity.update(id='duplicate:time',entity_kind='account')
    data['inputs']['entities'].append(entity)
    with pytest.raises(AccountError,match='duplicate_cohort_time_budget'): run(data)


def test_fractional_scaled_time_preserves_exact_conservation():
    data = fixture()
    data['units'].append(dict(id='days',dimension=[['time',1]],kind='capacity',scale='86400'))
    for phase in books(data):
        next(a for a in phase['batch']['accounts'] if a['id']=='labor').update(
            unit_id='days',opening='1.2',quantum='0.01')
        for c in phase['batch']['claims']:
            if c['account_id']=='labor': c['requested']={'admin':'0.3','care':'0.3','training':'0.3','employment':'0.8'}[c['id']]
        for posting in phase['batch']['postings']: posting['amount']='0.1'
        phase['batch']['reservations'][0]['amount']='0.2'
        for activity in phase['activities']:
            if activity['claim_id'] in ['admin','care','training','employment'] and activity['eligibility']=='allowed':
                activity['access_limit']={'admin':'0.3','care':'0.3','training':'0.3','employment':'0.8'}[activity['claim_id']]
    result = run(data)
    assert {c:claims(result)[c][0] for c in ['admin','care','training','employment']} == dict(
        admin='0.3',care='0.3',training='0.3',employment='0.3')
    assert sum(Fraction(claims(result)[c][0]) for c in ['admin','care','training','employment']) == Fraction('1.2')


def test_care_queue_alternative_does_not_reallocate_case_work():
    data = fixture(); work = books(data)[1]
    work['claim_order'] = ['admin','employment','training','care','goods']
    result = run(data)
    assert claims(result)['admin'] == ['3','0']
    assert claims(result)['employment'] == ['7','1']
    assert claims(result)['care'] == ['2','1']
    assert claims(result)['training'] == ['0','3']
    assert result.care.results[0].actual_before == '1'


def test_beneficiary_is_distinct_from_provider_and_legal_claimant_matches_beneficiary():
    data = fixture(); inputs = data['inputs']; care = data['request']['care']; law = data['request']['adjudication']
    entity = deepcopy(next(e for e in inputs['entities'] if e['id']=='shared:cohort'))
    entity.update(id='beneficiary',label='Synthetic beneficiary cohort'); inputs['entities'].append(entity)
    inputs['populations'].append(dict(entity_id='beneficiary',role='fixed_input'))
    inputs['owners'].append(dict(entity_id='beneficiary',partition='conditions',property_id='population',writer_id='fixture'))
    value = deepcopy(next(v for v in inputs['values'] if v['property_id']=='population'))
    value.update(id='population:beneficiary',entity_id='beneficiary'); value['value']['value']='4'; inputs['values'].append(value)
    for edge in inputs['relationships']:
        if edge['relationship_kind']=='cohort_membership': edge['from_id']='beneficiary'
    care['obligations'][0]['beneficiary_id']='beneficiary'
    law['cases'][0].update(claimant_id='beneficiary',target_id='beneficiary')
    law['bindings'][0]['entity_ids']=['beneficiary']
    result = run(data)
    assert result.status=='resolved' and result.care.population.value=='4'
    assert claims(result)==data['expected']['claims']
    assert result.care.results[0].beneficiary_id=='beneficiary'
    assert result.care.results[0].provider_id=='shared:cohort'
