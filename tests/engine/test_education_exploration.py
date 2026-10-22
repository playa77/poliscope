"""Host-only queue choices, shared care contention and exact source gaps."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.knowledge_culture import EducationRequest, EducationEdit
from poliscope_engine.domains.knowledge_culture.exploration import interview, preview
from poliscope_engine.domains.knowledge_culture.coverage import validate_coverage
from test_knowledge_culture import request, world, units, mechanisms


def context():
    return dict(graph=world(), units=units(), mechanisms=mechanisms())


def card(data, ctx):
    return interview(EducationRequest.model_validate(data), scope_id=data['scope_id'], **ctx)


def edit(c, option=1):
    return EducationEdit(baseline_digest=c.baseline_digest,scope_id=c.scope_id,option_id=c.alternatives[option].definition.id)


@pytest.mark.parametrize('scope',['local','region'])
def test_explicit_queue_competes_with_care_without_mutating_inputs(scope):
    data=request(scope); data['work']['claim_order']=['care','learning','job','teach','materials']
    ctx=context(); before=deepcopy(data); c=card(data,ctx)
    assert c.selected_option_id is None
    dto=EducationRequest.model_validate(data)
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


@pytest.mark.parametrize('field',['qualification','eligibility','facility','queue','source','policy','world'])
def test_complete_context_changes_reject_stale_previews(field):
    data=request(); ctx=context(); c=card(data,ctx)
    if field=='qualification': data['services'][0]['staff'][0]['qualification']='unknown'
    elif field=='eligibility': data['services'][0]['eligibility']='denied'
    elif field=='facility': data['facility_allocation']['batch']['accounts'][0]['opening']='0'
    elif field=='queue': data['work']['claim_order'].reverse()
    elif field=='source': data['source_refs']=['changed']
    elif field=='policy': data['bindings'][0]['choice_refs']=['changed']
    else:
        from poliscope_engine.world.membership import WorldGraph
        ctx['graph']=WorldGraph(ctx['graph'].registry,ctx['graph'].relationships[:-1])
    with pytest.raises(AccountError,match='stale_education_preview'):
        preview(EducationRequest.model_validate(data),edit=edit(c),**ctx)


def test_unknown_option_scope_and_qualification_remain_explicit():
    data=request();ctx=context();c=card(data,ctx)
    with pytest.raises(AccountError,match='unknown_education_option'):
        preview(EducationRequest.model_validate(data),edit=edit(c).model_copy(update={'option_id':'unknown'}),**ctx)
    with pytest.raises(AccountError,match='incompatible_education_scope'):
        preview(EducationRequest.model_validate(data),edit=edit(c).model_copy(update={'scope_id':'region'}),**ctx)
    data['services'][0]['staff'][0]['qualification']='unknown'; c=card(data,ctx)
    assert preview(EducationRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation.results[0].outcome is None


ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('corruption',[None,'missing','duplicate','title','options','activation','scope','availability','revision'])
def test_exact_source_inventory(corruption):
    data=json.loads((ROOT/'content/knowledge-culture/coverage-v1.json').read_text())
    source=json.loads((ROOT/'content/release-v1/society.inventory.json').read_text())
    if corruption is None:
        result=validate_coverage(data,source)
        assert sum(r.static_available for r in result.entries)==3
        return
    if corruption=='missing':data['entries'].pop()
    elif corruption=='duplicate':data['entries'].append(data['entries'][0])
    elif corruption=='title':data['entries'][0]['title']='changed'
    elif corruption=='options':data['entries'][0]['option_refs']=['inferred']
    elif corruption=='activation':data['activation']='activated'
    elif corruption=='scope':data['entries'][0]['supported_scope_kinds']=['region']
    elif corruption=='availability':data['entries'][0]['static_available']=True
    else:data['source_revision']='changed'
    with pytest.raises((AccountError,ValueError)):validate_coverage(data,source)


def test_prior_commitments_and_reservations_survive_queue_choice():
    data=request(); ctx=context()
    data['work']['batch']['reservations']=[dict(id='care:hold',account_id='time:a',claim_id='care',amount='4')]
    c=card(data,ctx); result=preview(EducationRequest.model_validate(data),edit=edit(c),**ctx)
    assert result.report.evaluation.results[0].outcome=='capacity_blocked'
    assert result.report.evaluation.request.work.batch.reservations[0].amount=='4'
    data['work']['batch']=result.report.evaluation.work.evaluation.batch.model_dump()
    c=card(data,ctx); replay=preview(EducationRequest.model_validate(data),edit=edit(c),**ctx)
    assert all(i.actual=='0' for i in replay.report.evaluation.work.indicators)
    assert replay.report.evaluation.results==result.report.evaluation.results


def test_mechanism_context_is_bound_to_preview():
    from poliscope_engine.domains.knowledge_culture.exploration import baseline
    data=EducationRequest.model_validate(request()); ctx=context()
    original=baseline(data,**ctx)
    c=interview(data,scope_id=data.scope_id,**ctx)
    ctx['mechanisms']=mechanisms(source_ids=['synthetic:source','new:source'])
    assert baseline(data,**ctx)!=original
    with pytest.raises(AccountError,match='stale_education_preview'):
        preview(data,edit=edit(c),**ctx)
