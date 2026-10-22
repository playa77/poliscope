"""Synthetic health prerequisites, independent of treatment/health effects."""
from copy import deepcopy
from decimal import localcontext
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.health import HealthRequest
from poliscope_engine.contracts.knowledge_culture import EducationRequest
from poliscope_engine.contracts.social_organization import CareRequest
from poliscope_engine.domains.health import evaluate_health
from poliscope_engine.domains.knowledge_culture import evaluate_education
from poliscope_engine.domains.social_organization import evaluate_care
from test_knowledge_culture import request as education_request, world, units
from test_social_organization import request as care_request
from test_policies import mechanisms, overlap, rule
from test_economy import claim


def request(scope='local'):
    data = education_request(scope)
    service = data['services'][0]
    service.update(id='clinic', need_refs=['synthetic:care-need'],
        exposure_refs=['synthetic:exposure'], health_state_refs=['synthetic:state'])
    for field in ('knowledge_refs', 'skill_refs', 'technology_assumption_refs'):
        del service[field]
    data['work']['activities'][2]['kind'] = 'care'
    return data


def run(data=None, graph=None):
    return evaluate_health(HealthRequest.model_validate(request() if data is None else data),
        graph=world() if graph is None else graph, mechanisms=mechanisms(), units=units())


@pytest.mark.parametrize('scope', ['local', 'region'])
def test_ready_inputs_retain_context_without_claiming_treatment(scope):
    data = request(scope); before = deepcopy(data)
    result = run(data)
    assert result.results[0].outcome == 'capacity_ready'
    assert result.status == 'resolved' and result.evidence_status == 'hypothetical'
    assert result.request.services[0].need_refs == ['synthetic:care-need']
    assert result.request.scope_id == scope and result.work.evaluation.request.period_id == 'day:0'
    assert data == before
    data['services'][0]['exposure_refs'].append('later')
    assert result.request.services[0].exposure_refs == ['synthetic:exposure']
    assert 'treatment' not in result.model_dump() and 'population' not in result.model_dump()


@pytest.mark.parametrize('resource,cid', [('beneficiary','learning'),('staff','teach'),('supplies','materials'),('facility','seat')])
def test_shortages_retain_other_independent_commitments(resource, cid):
    data = request()
    if resource == 'facility': data['facility_allocation']['batch']['accounts'][0]['opening'] = '0'
    else:
        aid = dict(beneficiary='time:a',staff='time:b',supplies='supplies')[resource]
        next(a for a in data['work']['batch']['accounts'] if a['id'] == aid)['opening'] = '0'
    result = run(data)
    assert result.results[0].outcome == 'capacity_blocked'
    assert result.results[0].unmet_claim_ids == [cid]
    if resource == 'staff': assert result.facility_allocation.actuals[0].allocated == '1'


@pytest.mark.parametrize('change,finding', [('work','unknown_work_capacity'),('facility','unknown_facility_capacity'),
    ('eligibility','unknown_health_eligibility'),('qualification','unknown_staff_qualification'),('policy','missing_policy_input')])
def test_unknowns_withhold_readiness(change, finding):
    data = request()
    if change == 'work': data['work']['procedure'] = None
    elif change == 'facility': data['facility_allocation']['procedure'] = None
    elif change == 'eligibility': data['services'][0]['eligibility'] = 'unknown'
    elif change == 'qualification': data['services'][0]['staff'][0]['qualification'] = 'unknown'
    else: data['bindings'][0]['value'] = dict(kind='unknown',reason='unreviewed')
    result = run(data)
    assert result.status == 'unresolved' and result.results[0].outcome is None
    assert finding in result.results[0].findings


@pytest.mark.parametrize('field,value,outcome', [('eligibility','denied','ineligible'),('qualification','not_qualified','unqualified')])
def test_entitlement_and_qualification_are_distinct_from_capacity(field,value,outcome):
    data = request()
    if field == 'eligibility': data['services'][0][field] = value
    else: data['services'][0]['staff'][0][field] = value
    result = run(data)
    assert result.results[0].outcome == outcome
    assert result.facility_allocation.actuals[0].allocated == '1'


def test_actual_care_and_education_share_identical_budget_and_postings():
    data = request(); care = care_request(); care['work'] = data['work']
    care['obligations'].append(dict(care['obligations'][0],id='patient-duty',claim_id='learning'))
    health = run(data)
    social = evaluate_care(CareRequest.model_validate(care),graph=world(),units=units())
    # Shared service orchestration preserves the same allocation regardless of its
    # domain label; the activity role remains an explicit input to each adapter.
    education = education_request()
    school = evaluate_education(EducationRequest.model_validate(education),graph=world(),mechanisms=mechanisms(),units=units())
    assert health.work == social.work
    assert health.work.evaluation.batch == school.work.evaluation.batch
    assert social.results[0].unmet == '4'
    data['work']['claim_order'] = ['care','learning','job','teach','materials']
    care['work'] = data['work']
    health = run(data)
    assert health.work == evaluate_care(CareRequest.model_validate(care),graph=world(),units=units()).work
    assert health.results[0].unmet_claim_ids == ['learning']


def test_policy_conflict_and_exact_selected_binding():
    data = request('region'); data['bindings'] = [b.model_dump() for b in overlap()]
    data['services'][0]['binding_id'] = 'b'
    assert run(data).results[0].findings == ['institutional_conflict']
    data['rules'] = [rule().model_dump()]
    assert run(data).results[0].outcome == 'capacity_ready'
    data['rules'] = [rule(selected_id='a').model_dump()]
    assert run(data).results[0].findings == ['health_binding_not_selected']


def test_prior_postings_and_reservations_replay_once():
    data = request()
    data['work']['batch']['reservations'] = [dict(id='hold',account_id='time:a',claim_id='care',amount='4')]
    first = run(data)
    data['work']['batch'] = first.work.evaluation.batch.model_dump()
    data['facility_allocation']['batch'] = first.facility_allocation.batch.model_dump()
    second = run(data)
    assert second.results == first.results
    assert second.work.evaluation.batch == first.work.evaluation.batch
    assert second.facility_allocation.batch == first.facility_allocation.batch
    assert all(i.actual == '0' for i in second.work.indicators)


@pytest.mark.parametrize('change', ['beneficiary_kind','beneficiary_owner','staff_kind','supply_kind','duplicate_claim',
    'zero','authority','qualification_ref','pool_overlap','facility_kind','facility_period','scope','binding','target',
    'second_time','missing_need','duplicate_asset','unmapped_asset','facility_conversion','facility_claimant'])
def test_malformed_context_rejects_without_mutation(change):
    data = request(); service = data['services'][0]; work = data['work']; facility = data['facility_allocation']
    if change == 'beneficiary_kind': work['activities'][2]['kind'] = 'training'
    elif change == 'beneficiary_owner': service['participants'][0]['cohort_id'] = 'cohort:b'
    elif change == 'staff_kind': work['activities'][3]['kind'] = 'training'
    elif change == 'supply_kind': work['activities'][4]['kind'] = 'care'
    elif change == 'duplicate_claim': service['participants'] *= 2
    elif change == 'zero': work['batch']['claims'][2]['requested'] = '0'
    elif change == 'authority': service['authority_id'] = 'school'
    elif change == 'qualification_ref': service['staff'][0]['qualification_refs'] = []
    elif change == 'pool_overlap': work['batch']['accounts'].append(facility['batch']['accounts'][0])
    elif change == 'facility_kind': facility['batch']['accounts'][0]['unit_id'] = 'hours'
    elif change == 'facility_period': facility['batch']['accounts'][0]['period_id'] = 'day:1'
    elif change == 'scope': data['scope_id'] = 'home:scope'
    elif change == 'binding': service['binding_id'] = 'missing'
    elif change == 'target': service['target_id'] = 'food'
    elif change == 'second_time':
        work['batch']['accounts'].append(dict(work['batch']['accounts'][0],id='copy'))
        work['holders'].append(dict(work['holders'][0],account_id='copy'))
    elif change == 'missing_need': service['need_refs'] = []
    elif change == 'duplicate_asset': data['facilities'] *= 2
    elif change == 'unmapped_asset': facility['batch']['accounts'].append(dict(facility['batch']['accounts'][0],id='extra'))
    elif change == 'facility_conversion': facility['choices'][0]['loss_per_unit'] = '1'
    elif change == 'facility_claimant': facility['batch']['claims'][0]['claimant_id'] = 'cohort:b'
    before = deepcopy(data)
    with pytest.raises((AccountError,ValidationError)): run(data)
    assert data == before


def test_forged_dto_and_decimal_context():
    dto = HealthRequest.model_validate(request()); dto.services[0].staff[0].__dict__['qualification'] = 'forged'
    with pytest.raises(ValidationError): evaluate_health(dto,graph=world(),mechanisms=mechanisms(),units=units())
    with localcontext() as context:
        context.prec = 2
        assert run().results[0].outcome == 'capacity_ready'


def test_independent_integer_resource_oracle():
    # Independently reasoned: beneficiary-first needs two hours; care-first
    # consumes up to four. Staff and supplies each need two; facility needs one.
    for beneficiary,staff,supplies,slots,care_first in product(range(3),range(3),range(3),range(2),[False,True]):
        data = request()
        data['work']['batch']['accounts'][0]['opening'] = str(beneficiary)
        data['work']['batch']['accounts'][1]['opening'] = str(staff)
        data['work']['batch']['accounts'][2]['opening'] = str(supplies)
        data['facility_allocation']['batch']['accounts'][0]['opening'] = str(slots)
        data['work']['claim_order'] = ['care','learning','job','teach','materials'] if care_first else ['learning','care','job','teach','materials']
        result = run(data)
        expected = beneficiary >= 2 and not care_first and staff >= 2 and supplies >= 2 and slots >= 1
        assert result.results[0].outcome == ('capacity_ready' if expected else 'capacity_blocked')
        actual = {i.claim_id:i.actual for i in result.work.indicators}
        assert actual['learning'] == str(0 if care_first else min(beneficiary,2))
        assert actual['teach'] == str(min(staff,2))
        assert actual['materials'] == str(min(supplies,2))
        assert result.facility_allocation.actuals[0].allocated == str(slots)


def test_local_facility_access_blocks_despite_sufficient_stock():
    data = request(); facility = data['facility_allocation']
    facility['choices'][0]['access'] = 'denied'
    result = run(data)
    assert result.results[0].outcome == 'capacity_blocked'
    assert result.results[0].unmet_claim_ids == ['seat']
    assert next(a for a in result.facility_allocation.accounts.accounts if a.account_id == 'school:slots').closing == '1'
    facility['choices'][0]['access'] = 'unknown'
    assert run(data).results[0].outcome is None


def test_remaining_supplies_cannot_be_reused_by_actual_provisioning():
    from poliscope_engine.contracts.provisioning import ProvisioningRequest
    from poliscope_engine.domains.provisioning.chain import evaluate_chain
    health = run()
    plan = dict(contract_version=1,period_id='day:0',batch=health.work.evaluation.batch.model_dump(),
        resources=[dict(account_id='supplies',resource_id='food')],phases=[dict(id='other-use',kind='use',
            claims=[claim('other:materials','supplies',4,'cohort:c')],reservations=[],procedure='priority',
            claim_order=['other:materials'],choices=[dict(claim_id='other:materials',access='allowed',access_limit='4',
                funding_known=True,requirements=[],outputs=[],loss_per_unit='0',mechanism_ref='synthetic:other',source_refs=[])],
            mechanism_ref='synthetic:other',source_refs=[])])
    result = evaluate_chain(ProvisioningRequest.model_validate(plan),units())
    assert {c.claim_id:(c.actual,c.unmet) for c in result.accounts.claims}['other:materials'] == ('3','1')
    assert result.batch.postings[:len(health.work.evaluation.batch.postings)] == health.work.evaluation.batch.postings


def test_actual_school_and_clinic_contend_in_one_shared_batch():
    from test_economy import activity
    school = education_request(); health = request()
    work = school['work']
    work['batch']['claims'] += [claim('patient','time:a',2,'cohort:a'),
        claim('clinic:staff','time:b',2,'cohort:b'),claim('clinic:supply','supplies',2,'cohort:a')]
    work['activities'] += [activity('patient','care'),activity('clinic:staff','paid_work'),activity('clinic:supply')]
    work['claim_order'] = ['learning','patient','teach','clinic:staff','materials','clinic:supply','care','job']
    facility = school['facility_allocation']
    facility['batch']['claims'].append(claim('clinic:seat','school:slots',1,'cohort:a'))
    facility['choices'].append(dict(facility['choices'][0],claim_id='clinic:seat'))
    facility['claim_order'].append('clinic:seat')
    health['work'] = work; health['facility_allocation'] = facility
    service = health['services'][0]
    service['participants'][0]['claim_id'] = 'patient'
    service['staff'][0]['claim_id'] = 'clinic:staff'
    service['supply_claim_ids'] = ['clinic:supply']; service['facility_claim_ids'] = ['clinic:seat']
    clinic = run(health)
    course = evaluate_education(EducationRequest.model_validate(school),graph=world(),mechanisms=mechanisms(),units=units())
    assert clinic.work == course.work and clinic.facility_allocation == course.facility_allocation
    assert course.results[0].outcome == 'capacity_ready'
    assert clinic.results[0].unmet_claim_ids == ['clinic:staff','clinic:seat']
    actual = {i.claim_id:i.actual for i in clinic.work.indicators}
    assert actual['teach'] == '2' and actual['clinic:staff'] == '1'
    assert actual['learning'] == '2' and actual['patient'] == '2'
