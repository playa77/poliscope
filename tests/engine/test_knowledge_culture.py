"""Synthetic capacity readiness; no empirical learning claims."""
from copy import deepcopy
from decimal import Decimal, localcontext
from itertools import product
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.knowledge_culture import EducationRequest
from poliscope_engine.contracts.social_organization import CareRequest
from poliscope_engine.contracts.world import EntityDTO
from poliscope_engine.domains.knowledge_culture import evaluate_education
from poliscope_engine.domains.social_organization import evaluate_care
from poliscope_engine.numeric import Registry, Unit
from poliscope_engine.world import WorldRegistry
from poliscope_engine.world.membership import WorldGraph
from test_social_organization import world as care_world, request as care_request, units as care_units
from test_economy import account, claim, activity, holder
from test_policies import binding, mechanisms, PROVENANCE, overlap, rule


def units():
    return Registry((*care_units().units, Unit('slots', (('facility_slot', 1),), 'capacity', Decimal(1))))


def world():
    base = care_world()
    return WorldGraph(WorldRegistry('civ', entities=[*base.registry.entities,
        EntityDTO(id='school', entity_kind='asset', label='school', provenance=PROVENANCE)],
        scopes=base.registry.scopes, values=base.registry.values, populations=base.registry.populations,
        owners=base.registry.owners), base.relationships)


def request(scope='local'):
    work = care_request(scope)['work']
    # A is simultaneously student and carer; B supplies staff time.
    work['batch']['accounts'] += [account('time:b', 3, scope, 'hours'), account('supplies', 5, scope)]
    work['batch']['claims'] += [claim('teach', 'time:b', 2, 'cohort:b'), claim('materials', 'supplies', 2, 'cohort:a')]
    work['holders'].append(holder('time:b', 'cohort:b', 'time'))
    work['activities'] += [activity('teach', 'paid_work'), activity('materials')]
    work['claim_order'] += ['teach','materials']
    authority = 'local-authority' if scope == 'local' else 'regional-authority'
    facility = account('school:slots', 1, scope, 'hours')
    facility['unit_id'] = 'slots'
    return dict(contract_version=1, scope_id=scope, services=[dict(id='course', authority_id=authority,
        binding_id='a', target_id='water', parameter_id='synthetic:parameter', eligibility='allowed',
        participants=[dict(cohort_id='cohort:a', claim_id='learning')],
        staff=[dict(cohort_id='cohort:b', claim_id='teach', qualification='declared', qualification_refs=['synthetic:certificate'])],
        supply_claim_ids=['materials'], facility_claim_ids=['seat'], knowledge_refs=['synthetic:archive'],
        skill_refs=['synthetic:skill'], technology_assumption_refs=[], obligation_refs=['synthetic:care-duty'], source_refs=[] )],
        bindings=[binding(scope_id=scope, authority_id=authority).model_dump()], rules=[], work=work,
        facilities=[dict(asset_id='school', account_id='school:slots', source_refs=[])],
        facility_allocation=dict(contract_version=1,
            batch=dict(contract_version=1, accounts=[facility], claims=[claim('seat','school:slots',1,'cohort:a')],
                       postings=[], reservations=[], subtotals=[]),
            procedure='priority', claim_order=['seat'], choices=[dict(claim_id='seat',access='allowed',access_limit='1',
                funding_known=True, requirements=[], outputs=[], loss_per_unit='0', mechanism_ref='synthetic:slots', source_refs=[])],
            mechanism_ref='synthetic:slots', source_refs=[]), source_refs=[])


def run(data=None, graph=None):
    return evaluate_education(EducationRequest.model_validate(request() if data is None else data),
        graph=world() if graph is None else graph, mechanisms=mechanisms(), units=units())


@pytest.mark.parametrize('scope', ['local','region'])
def test_all_prerequisites_ready_but_no_learning_or_completion(scope):
    data = request(scope); before = deepcopy(data)
    result = run(data)
    assert data == before and result.status == 'resolved'
    assert result.results[0].outcome == 'capacity_ready'
    assert result.results[0].unmet_claim_ids == []
    assert result.request.services[0].knowledge_refs == ['synthetic:archive']
    assert result.work.indicators[2].actual == '2'
    assert result.work.indicators[0].unmet == '4'  # care is not silently funded
    data['services'][0]['staff'][0]['qualification_refs'].append('later')
    assert result.request.services[0].staff[0].qualification_refs == ['synthetic:certificate']


@pytest.mark.parametrize('resource,claim_id', [('student','learning'),('staff','teach'),('supplies','materials'),('facility','seat')])
def test_independent_shortages_preserve_unmet_requirements(resource, claim_id):
    data = request()
    if resource == 'facility': data['facility_allocation']['batch']['accounts'][0]['opening'] = '0'
    else:
        aid = dict(student='time:a', staff='time:b', supplies='supplies')[resource]
        next(a for a in data['work']['batch']['accounts'] if a['id'] == aid)['opening'] = '0'
    result = run(data)
    assert result.results[0].outcome == 'capacity_blocked'
    assert result.results[0].unmet_claim_ids == [claim_id]
    # Input commitments in other pools remain inspectable; no fake refund.
    if resource == 'staff': assert result.facility_allocation.actuals[0].allocated == '1'


def test_actual_care_evaluator_uses_identical_claims_and_postings():
    data = request(); care = care_request(); care['work'] = data['work']
    education = run(data)
    social = evaluate_care(CareRequest.model_validate(care), graph=world(), units=units())
    assert education.work == social.work and social.results[0].unmet == '4'
    data['work']['claim_order'] = ['care','learning','job','teach','materials']
    care['work'] = data['work']
    education = run(data)
    social = evaluate_care(CareRequest.model_validate(care), graph=world(), units=units())
    assert education.work == social.work and social.results[0].actual == '4'
    assert education.results[0].outcome == 'capacity_blocked'
    assert education.results[0].unmet_claim_ids == ['learning']


@pytest.mark.parametrize('change,finding', [('work','unknown_work_capacity'),('facility','unknown_facility_capacity'),
    ('eligibility','unknown_education_eligibility'),('qualification','unknown_staff_qualification'),('policy','missing_policy_input')])
def test_unknowns_do_not_become_zero_or_completed_service(change, finding):
    data = request()
    if change == 'work': data['work']['procedure'] = None
    elif change == 'facility': data['facility_allocation']['procedure'] = None
    elif change == 'eligibility': data['services'][0]['eligibility'] = 'unknown'
    elif change == 'qualification': data['services'][0]['staff'][0]['qualification'] = 'unknown'
    else: data['bindings'][0]['value'] = dict(kind='unknown', reason='unreviewed')
    result = run(data)
    assert result.status == 'unresolved' and result.results[0].outcome is None
    assert finding in result.results[0].findings
    if change == 'work': assert all(i.actual is None for i in result.work.indicators)


@pytest.mark.parametrize('field,value,outcome', [('eligibility','denied','ineligible'),('qualification','not_qualified','unqualified')])
def test_known_ineligibility_and_qualification_are_distinct(field,value,outcome):
    data = request()
    if field == 'eligibility': data['services'][0][field] = value
    else: data['services'][0]['staff'][0][field] = value
    assert run(data).results[0].outcome == outcome


def test_policy_conflicts_and_exact_selection_use_shared_resolver():
    data = request('region'); data['bindings'] = [b.model_dump() for b in overlap()]
    data['services'][0]['binding_id'] = 'b'
    for bindings in (data['bindings'], list(reversed(data['bindings']))):
        data['bindings'] = bindings
        assert run(data).results[0].findings == ['institutional_conflict']
    data['rules'] = [rule().model_dump()]
    assert run(data).results[0].outcome == 'capacity_ready'
    data['rules'] = [rule(selected_id='a').model_dump()]
    assert run(data).results[0].findings == ['education_binding_not_selected']


def test_prior_actuals_and_reservations_replay_without_double_spending():
    data = request()
    data['work']['batch']['reservations'] = [dict(id='hold', account_id='time:a', claim_id='care', amount='4')]
    data['facility_allocation']['batch']['reservations'] = [dict(id='slot:hold',account_id='school:slots',claim_id='seat',amount='1')]
    first = run(data)
    assert first.results[0].outcome == 'capacity_blocked'
    data['work']['batch'] = first.work.evaluation.batch.model_dump()
    data['facility_allocation']['batch'] = first.facility_allocation.batch.model_dump()
    second = run(data)
    assert second.results == first.results
    assert second.work.evaluation.batch == first.work.evaluation.batch
    assert second.facility_allocation.batch == first.facility_allocation.batch
    assert all(i.actual == '0' for i in second.work.indicators)


@pytest.mark.parametrize('change', ['scope','period','worker','participant','staff_kind','student_kind','supply_kind',
    'missing_claim','zero','duplicate_claim','duplicate_service','duplicate_asset','unmapped_asset','asset_kind',
    'slot_dimension','physical_capacity','pool_overlap','facility_requirement','facility_output','authority',
    'binding','target','qualification_ref','facility_claimant','facility_period','missing_activity','copied_time'])
def test_invalid_links_and_budget_copies_reject_without_mutation(change):
    data = request(); service = data['services'][0]; work = data['work']; facility = data['facility_allocation']
    if change == 'scope': data['scope_id'] = 'home:scope'
    elif change == 'period': work['batch']['accounts'][0]['period_id'] = 'day:1'
    elif change == 'worker': work['batch']['claims'][0]['claimant_id'] = 'missing'
    elif change == 'participant': service['participants'][0]['cohort_id'] = 'cohort:b'
    elif change == 'staff_kind': work['activities'][3]['kind'] = 'care'
    elif change == 'student_kind': work['activities'][2]['kind'] = 'participation'
    elif change == 'supply_kind': work['activities'][4]['kind'] = 'training'
    elif change == 'missing_claim': service['supply_claim_ids'] = ['missing']
    elif change == 'zero': work['batch']['claims'][2]['requested'] = '0'
    elif change == 'duplicate_claim': service['participants'] *= 2
    elif change == 'duplicate_service': data['services'].append(service)
    elif change == 'duplicate_asset': data['facilities'] *= 2
    elif change == 'unmapped_asset': facility['batch']['accounts'].append(dict(facility['batch']['accounts'][0], id='extra'))
    elif change == 'asset_kind': data['facilities'][0]['asset_id'] = 'water'
    elif change == 'slot_dimension': facility['batch']['accounts'][0]['unit_id'] = 'hours'
    elif change == 'physical_capacity': facility['batch']['accounts'][0]['invariant'] = 'physical'
    elif change == 'pool_overlap': work['batch']['accounts'].append(facility['batch']['accounts'][0])
    elif change == 'facility_requirement': facility['choices'][0]['requirements'] = [dict(account_id='school:slots',per_unit='1',kind='funding')]
    elif change == 'facility_output': facility['choices'][0]['loss_per_unit'] = '1'
    elif change == 'authority': service['authority_id'] = 'school'
    elif change == 'binding': service['binding_id'] = 'missing'
    elif change == 'target': service['target_id'] = 'food'
    elif change == 'qualification_ref': service['staff'][0]['qualification_refs'] = []
    elif change == 'facility_claimant': facility['batch']['claims'][0]['claimant_id'] = 'cohort:b'
    elif change == 'facility_period': facility['batch']['accounts'][0]['period_id'] = 'day:1'
    elif change == 'missing_activity': work['activities'].pop()
    elif change == 'copied_time':
        work['batch']['accounts'].append(account('copy', 5, 'local','hours'))
        work['holders'].append(holder('copy','cohort:a','time'))
    before = deepcopy(data)
    with pytest.raises((AccountError,ValidationError)): run(data)
    assert data == before


def test_direct_jurisdiction_required():
    base = world()
    with pytest.raises(AccountError,match='invalid_education_authority'):
        run(graph=WorldGraph(base.registry,[r for r in base.relationships if r.id != 'local-j']))


def test_nested_dto_revalidation_and_ambient_context_independence():
    dto = EducationRequest.model_validate(request()); dto.services[0].staff[0].__dict__['qualification'] = 'forged'
    with pytest.raises(ValidationError): evaluate_education(dto,graph=world(),mechanisms=mechanisms(),units=units())
    with localcontext() as context:
        context.prec = 2
        assert run().results[0].outcome == 'capacity_ready'


def test_independent_integer_prerequisite_oracle():
    # Five finite resources, no implementation-derived expected quantities.
    for student, staff, supplies, slots, care_first in product(range(3),range(3),range(3),range(2),[False,True]):
        data = request()
        data['work']['batch']['accounts'][0]['opening'] = str(student)
        data['work']['batch']['accounts'][1]['opening'] = str(staff)
        data['work']['batch']['accounts'][2]['opening'] = str(supplies)
        data['facility_allocation']['batch']['accounts'][0]['opening'] = str(slots)
        data['work']['claim_order'] = ['care','learning','job','teach','materials'] if care_first else ['learning','care','job','teach','materials']
        result = run(data)
        expected = 'capacity_ready' if student >= 2 and not care_first and staff >= 2 and supplies >= 2 and slots >= 1 else 'capacity_blocked'
        assert result.results[0].outcome == expected
        actual = {i.claim_id: i.actual for i in result.work.indicators}
        assert actual['learning'] == str(0 if care_first else min(student, 2))
        assert actual['teach'] == str(min(staff, 2))
        assert actual['materials'] == str(min(supplies, 2))
        assert result.facility_allocation.actuals[0].allocated == str(slots)


def test_competing_facility_claim_and_storage_order_do_not_create_slots():
    data = request(); facility = data['facility_allocation']
    facility['batch']['claims'].append(claim('other:seat','school:slots',1,'cohort:c'))
    facility['choices'].append(dict(facility['choices'][0],claim_id='other:seat'))
    facility['claim_order'] = ['other:seat','seat']
    result = run(data)
    assert result.results[0].unmet_claim_ids == ['seat']
    facility['batch']['claims'].reverse(); facility['choices'].reverse()
    permuted = run(data)
    assert permuted.facility_allocation.batch.postings == result.facility_allocation.batch.postings
    assert permuted.facility_allocation.actuals == result.facility_allocation.actuals
    assert permuted.results == result.results


def test_actual_provisioning_cannot_reuse_education_supplies():
    from poliscope_engine.contracts.provisioning import ProvisioningRequest
    from poliscope_engine.domains.provisioning.chain import evaluate_chain
    education = run()
    # Five kg before education, two committed to materials; only three remain.
    plan = dict(contract_version=1, period_id='day:0', batch=education.work.evaluation.batch.model_dump(),
        resources=[dict(account_id='supplies',resource_id='food')], phases=[dict(id='other-use',kind='use',
            claims=[claim('other:materials','supplies',4,'cohort:c')], reservations=[], procedure='priority',
            claim_order=['other:materials'],choices=[dict(claim_id='other:materials',access='allowed',access_limit='4',
                funding_known=True,requirements=[],outputs=[],loss_per_unit='0',mechanism_ref='synthetic:other',source_refs=[])],
            mechanism_ref='synthetic:other',source_refs=[])])
    result = evaluate_chain(ProvisioningRequest.model_validate(plan), units())
    assert result.status == 'resolved'
    assert {c.claim_id:(c.actual,c.unmet) for c in result.accounts.claims}['other:materials'] == ('3','1')
    assert result.batch.postings[:len(education.work.evaluation.batch.postings)] == education.work.evaluation.batch.postings
    assert next(a for a in result.accounts.accounts if a.account_id == 'supplies').closing == '0'


@pytest.mark.parametrize('pool,field,value', [('work','eligibility','unknown'), ('work','terms_known',False),
    ('facility','access','unknown'), ('facility','funding_known',False)])
def test_unknown_access_or_terms_withhold_readiness(pool, field, value):
    data = request()
    if pool == 'work': data['work']['activities'][2][field] = value
    else: data['facility_allocation']['choices'][0][field] = value
    result = run(data)
    assert result.results[0].outcome is None and result.status == 'unresolved'
    assert ('unknown_work_capacity' if pool == 'work' else 'unknown_facility_capacity') in result.results[0].findings


def test_same_people_as_staff_and_students_do_not_gain_a_second_day():
    data = request(); work = data['work']
    work['batch']['accounts'].pop(1); work['holders'].pop(1)
    work['batch']['claims'][3].update(account_id='time:a',claimant_id='cohort:a')
    data['services'][0]['staff'][0]['cohort_id'] = 'cohort:a'
    work['claim_order'] = ['learning','teach','care','job','materials']
    result = run(data)
    assert result.results[0].outcome == 'capacity_ready'
    by_claim = {i.claim_id:i.actual for i in result.work.indicators}
    assert by_claim == dict(learning='2',teach='2',care='1',job='0',materials='2')
    assert next(a for a in result.work.evaluation.allocation.accounts.accounts if a.account_id == 'time:a').closing == '0'


def test_whole_claim_procedure_retains_partial_shortage_without_fabricating_service():
    data = request(); data['work']['procedure'] = 'all_or_nothing'
    data['work']['batch']['accounts'][1]['opening'] = '1'
    result = run(data)
    assert result.results[0].unmet_claim_ids == ['teach']
    assert result.work.indicators[3].actual == '0'
    assert next(a for a in result.work.evaluation.allocation.accounts.accounts if a.account_id == 'time:b').closing == '1'


def test_facility_hold_protects_slot_against_competing_use():
    data = request(); facility = data['facility_allocation']
    facility['batch']['claims'].append(claim('other:seat','school:slots',1,'cohort:c'))
    facility['choices'].append(dict(facility['choices'][0],claim_id='other:seat'))
    facility['claim_order'] = ['other:seat','seat']
    facility['batch']['reservations'] = [dict(id='hold:seat',account_id='school:slots',claim_id='seat',amount='1')]
    result = run(data)
    assert result.results[0].outcome == 'capacity_ready'
    assert {a.claim_id:a.allocated for a in result.facility_allocation.actuals} == {'seat':'1','other:seat':'0'}
