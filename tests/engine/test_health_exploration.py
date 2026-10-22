"""Host-only queue choices, shared care contention and exact source gaps."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.health import HealthRequest, HealthEdit
from poliscope_engine.domains.health.exploration import interview, preview
from poliscope_engine.domains.health.coverage import validate_coverage
from test_health import request, world, units, mechanisms


def context():
    return dict(graph=world(), units=units(), mechanisms=mechanisms())


def card(data, ctx):
    return interview(HealthRequest.model_validate(data), scope_id=data['scope_id'], **ctx)


def edit(c, option=1):
    return HealthEdit(baseline_digest=c.baseline_digest,scope_id=c.scope_id,option_id=c.alternatives[option].definition.id)


@pytest.mark.parametrize('scope',['local','region'])
def test_explicit_queue_competes_with_care_without_mutating_inputs(scope):
    data=request(scope); data['work']['claim_order']=['care','learning','job','teach','materials']
    ctx=context(); before=deepcopy(data); c=card(data,ctx)
    assert c.selected_option_id is None
    dto=HealthRequest.model_validate(data)
    retained=preview(dto,edit=edit(c,0),**ctx)
    preferred=preview(dto,edit=edit(c),**ctx)
    assert retained.report.evaluation.results[0].outcome=='capacity_blocked'
    assert preferred.report.evaluation.results[0].outcome=='capacity_ready'
    assert {i.claim_id:i.actual for i in preferred.report.evaluation.work.indicators}['care']=='3'
    candidate=preferred.report.evaluation.request.model_dump()
    candidate['work']['claim_order']=before['work']['claim_order']
    assert candidate==before and data==before and dto.model_dump()==before
    assert retained.report.evaluation.facility_allocation==preferred.report.evaluation.facility_allocation
    preferred.report.evaluation.request.services[0].source_refs.append('detached')
    assert dto.model_dump()==before


@pytest.mark.parametrize('field',['qualification','eligibility','facility','queue','source','policy','world','need','exposure','health_state','units'])
def test_complete_context_changes_reject_stale_previews(field):
    data=request(); ctx=context(); c=card(data,ctx)
    if field=='qualification': data['services'][0]['staff'][0]['qualification']='unknown'
    elif field=='eligibility': data['services'][0]['eligibility']='denied'
    elif field=='facility': data['facility_allocation']['batch']['accounts'][0]['opening']='0'
    elif field=='queue': data['work']['claim_order'].reverse()
    elif field=='source': data['source_refs']=['changed']
    elif field=='policy': data['bindings'][0]['choice_refs']=['changed']
    elif field in ('need','exposure','health_state'): data['services'][0][field + '_refs']=['changed']
    elif field=='units':
        from dataclasses import replace
        from decimal import Decimal
        ctx['units']=replace(ctx['units'], units=tuple(replace(u, scale=Decimal(2)) if u.id=='hours' else u for u in ctx['units'].units))
    else:
        from poliscope_engine.world.membership import WorldGraph
        ctx['graph']=WorldGraph(ctx['graph'].registry,ctx['graph'].relationships[:-1])
    with pytest.raises(AccountError,match='stale_health_preview'):
        preview(HealthRequest.model_validate(data),edit=edit(c),**ctx)


def test_unknown_option_scope_and_qualification_remain_explicit():
    data=request();ctx=context();c=card(data,ctx)
    with pytest.raises(AccountError,match='unknown_health_option'):
        preview(HealthRequest.model_validate(data),edit=edit(c).model_copy(update={'option_id':'unknown'}),**ctx)
    with pytest.raises(AccountError,match='incompatible_health_scope'):
        preview(HealthRequest.model_validate(data),edit=edit(c).model_copy(update={'scope_id':'region'}),**ctx)
    data['services'][0]['staff'][0]['qualification']='unknown'; c=card(data,ctx)
    assert preview(HealthRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation.results[0].outcome is None


ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('corruption',[None,'missing','duplicate','title','options','activation','scope','availability','revision'])
def test_exact_source_inventory(corruption):
    data=json.loads((ROOT/'content/health/coverage-v1.json').read_text())
    source=json.loads((ROOT/'content/release-v1/society.inventory.json').read_text())
    if corruption is None:
        result=validate_coverage(data,source)
        assert sum(r.static_available for r in result.entries)==2
        return
    if corruption=='missing':data['entries'].pop()
    elif corruption=='duplicate':data['entries'].append(data['entries'][0])
    elif corruption=='title':data['entries'][0]['title']='changed'
    elif corruption=='options':data['entries'][0]['option_refs']=['inferred']
    elif corruption=='activation':data['activation']='activated'
    elif corruption=='scope':data['entries'][0]['supported_scope_kinds']=['region']
    elif corruption=='availability':data['entries'][2]['static_available']=True
    else:data['source_revision']='changed'
    with pytest.raises((AccountError,ValueError)):validate_coverage(data,source)


def test_prior_commitments_and_reservations_survive_queue_choice():
    data=request(); ctx=context()
    data['work']['batch']['reservations']=[dict(id='care:hold',account_id='time:a',claim_id='care',amount='4')]
    c=card(data,ctx); result=preview(HealthRequest.model_validate(data),edit=edit(c),**ctx)
    assert result.report.evaluation.results[0].outcome=='capacity_blocked'
    assert result.report.evaluation.request.work.batch.reservations[0].amount=='4'
    data['work']['batch']=result.report.evaluation.work.evaluation.batch.model_dump()
    c=card(data,ctx); replay=preview(HealthRequest.model_validate(data),edit=edit(c),**ctx)
    assert all(i.actual=='0' for i in replay.report.evaluation.work.indicators)
    assert replay.report.evaluation.results==result.report.evaluation.results


def test_mechanism_context_is_bound_to_preview():
    from poliscope_engine.domains.health.exploration import baseline
    data=HealthRequest.model_validate(request()); ctx=context()
    original=baseline(data,**ctx)
    c=interview(data,scope_id=data.scope_id,**ctx)
    ctx['mechanisms']=mechanisms(source_ids=['synthetic:source','new:source'])
    assert baseline(data,**ctx)!=original
    with pytest.raises(AccountError,match='stale_health_preview'):
        preview(data,edit=edit(c),**ctx)


def test_health_queue_reallocates_shared_school_staff_without_creating_facilities():
    from test_health import request, education_request
    from poliscope_engine.contracts.knowledge_culture import EducationRequest
    from poliscope_engine.domains.knowledge_culture import evaluate_education
    from test_economy import activity, claim
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
    ctx=context(); c=card(health,ctx); before=deepcopy(health)
    retained=preview(HealthRequest.model_validate(health),edit=edit(c,0),**ctx)
    preferred=preview(HealthRequest.model_validate(health),edit=edit(c),**ctx)
    actual={i.claim_id:i.actual for i in preferred.report.evaluation.work.indicators}
    assert actual['clinic:staff']=='2' and actual['teach']=='1'
    assert preferred.report.evaluation.results[0].unmet_claim_ids==['clinic:seat']
    assert retained.report.evaluation.results[0].unmet_claim_ids==['clinic:staff','clinic:seat']
    assert preferred.report.evaluation.facility_allocation==retained.report.evaluation.facility_allocation
    school['work']=preferred.report.evaluation.request.work.model_dump()
    course=evaluate_education(EducationRequest.model_validate(school),**ctx)
    assert course.work==preferred.report.evaluation.work
    assert course.results[0].unmet_claim_ids==['teach']
    assert health==before
