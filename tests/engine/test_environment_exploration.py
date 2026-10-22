"""Detached explicit alternatives and exact source reconciliation."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.environment import EnvironmentRequest, EnvironmentEdit
from poliscope_engine.domains.environment.exploration import interview, preview
from poliscope_engine.domains.environment.coverage import validate_coverage
from test_environment import request, world, units

def additional(result):
    return {r.claim_id:r.additional for r in result.results}


def context():
    return dict(graph=world(), units=units())


def card(data, ctx):
    return interview(EnvironmentRequest.model_validate(data), scope_id=data['scope_id'], **ctx)


def edit(c, option=1):
    return EnvironmentEdit(baseline_digest=c.baseline_digest,scope_id=c.scope_id,option_id=c.alternatives[option].definition.id)


def test_explicit_competing_farm_clinic_previews_are_detached():
    data=request(); before=deepcopy(data); ctx=context(); c=card(data,ctx)
    assert c.selected_option_id is None
    dto=EnvironmentRequest.model_validate(data)
    retained=preview(dto,edit=edit(c,0),**ctx)
    reversed_=preview(dto,edit=edit(c),**ctx)
    assert additional(retained.report.evaluation)=={'water:farm':'4','water:clinic':'1','sink:farm':'3','sink:clinic':'0'}
    assert additional(reversed_.report.evaluation)=={'water:farm':'1','water:clinic':'4','sink:farm':'0','sink:clinic':'3'}
    candidate=reversed_.report.evaluation.request.model_dump()
    candidate['claim_order']=before['claim_order']
    assert candidate==before==dto.model_dump()==data
    reversed_.report.evaluation.request.boundaries[0].source_refs.append('detached')
    assert dto.model_dump()==before


@pytest.mark.parametrize('field',['access','access_limit','capacity','limit','policy','opening','queue','source','world','units','period','procedure'])
def test_complete_context_rejects_stale_preview(field):
    data=request();ctx=context();c=card(data,ctx)
    if field=='access':data['demands'][0]['access']='denied'
    elif field=='access_limit':data['demands'][0]['access_limit']='1'
    elif field=='capacity':data['boundaries'][0]['capacity_status']='unknown'
    elif field=='limit':data['boundaries'][0]['selected_limit']='2'
    elif field=='policy':data['boundaries'][0]['policy_ref']='changed'
    elif field=='opening':data['batch']['accounts'][0]['opening']='0'
    elif field=='queue':data['claim_order'].reverse()
    elif field=='source':data['source_refs']=['changed']
    elif field=='period':data['period_id']='day:1'
    elif field=='procedure':data['procedure']='all_or_nothing'
    elif field=='world':
        from poliscope_engine.world.membership import WorldGraph
        ctx['graph']=WorldGraph(ctx['graph'].registry,ctx['graph'].relationships[:-1])
    else:ctx['units']=replace(ctx['units'], units=tuple(replace(u,scale=Decimal(2)) if u.id=='kg' else u for u in ctx['units'].units))
    with pytest.raises(AccountError,match='stale_environment_preview'):
        preview(EnvironmentRequest.model_validate(data),edit=edit(c),**ctx)


def test_scope_and_unknown_option():
    data=request();ctx=context();c=card(data,ctx);dto=EnvironmentRequest.model_validate(data)
    for changes,error in [({'scope_id':'east'},'incompatible_environment_scope'),({'option_id':'unknown'},'unknown_environment_option')]:
        with pytest.raises(AccountError,match=error):preview(dto,edit=edit(c).model_copy(update=changes),**ctx)


@pytest.mark.parametrize('mode',['denied','unknown','hold','prior'])
def test_alternatives_preserve_constraints_and_commitments(mode):
    data=request();ctx=context()
    if mode=='denied':data['demands'][0]['access']='denied'
    elif mode=='unknown':data['boundaries'][0]['capacity_status']='unknown'
    elif mode=='hold':data['batch']['reservations']=[dict(id='water:hold',account_id='water:stock',claim_id='water:farm',amount='2')]
    else:
        from test_environment import run
        data['batch']=run(data).allocation.batch.model_dump()
    before=deepcopy(data);c=card(data,ctx)
    result=preview(EnvironmentRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.batch==EnvironmentRequest.model_validate(before).batch
    if mode=='denied':assert result.results[0].additional=='0'
    elif mode=='unknown':assert result.status=='unresolved' and all(r.additional is None for r in result.results)
    elif mode=='prior':assert all(r.additional=='0' for r in result.results)
    else:assert additional(result)['water:farm']=='2' and additional(result)['water:clinic']=='3'
    assert data==before


ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('corruption',[None,'missing','duplicate','extra','title','documents','options','activation','scope','availability','revision','digest','refs','transition'])
def test_exact_source_inventory(corruption):
    data=json.loads((ROOT/'content/environment/coverage-v1.json').read_text())
    source=json.loads((ROOT/'content/release-v1/society.inventory.json').read_text())
    if corruption is None:
        result=validate_coverage(data,source)
        assert {r.source_id for r in result.entries if r.static_available}=={'society:domain/10/1','society:domain/10/1/3','society:domain/10/2','society:domain/10/2/1'}
        return
    if corruption=='missing':data['entries'].pop()
    elif corruption=='duplicate':data['entries'].append(data['entries'][0])
    elif corruption=='extra':data['entries'][0]['source_id']='extra'
    elif corruption=='title':data['entries'][0]['title']='changed'
    elif corruption=='documents':data['entries'][0]['documents']=['invented']
    elif corruption=='options':data['entries'][-1]['option_refs']=['invented']
    elif corruption=='activation':data['activation']='activated'
    elif corruption=='scope':data['entries'][0]['supported_scope_kinds']=['region']
    elif corruption=='availability':data['entries'][0]['static_available']=False
    elif corruption=='revision':data['source_revision']='changed'
    elif corruption=='digest':data['source_archive_digest']='sha256:'+'0'*64
    elif corruption=='refs':data['entries'][0]['implementation_refs']=[]
    else:data['entries'][0]['transition_available']=True
    with pytest.raises((AccountError,ValueError)):validate_coverage(data,source)


@pytest.mark.parametrize('scope',['east','region'])
@pytest.mark.parametrize('procedure',['priority','all_or_nothing',None])
def test_scope_procedure_and_limit_diagnostics_are_retained(scope,procedure):
    data=request();ctx=context();data['scope_id']=scope;data['procedure']=procedure
    c=card(data,ctx)
    result=preview(EnvironmentRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.procedure==procedure
    assert result.request.boundaries==EnvironmentRequest.model_validate(data).boundaries
    if procedure is None:assert result.status=='unresolved'
    elif procedure=='priority':
        assert additional(result)=={'water:farm':'1','water:clinic':'4','sink:farm':'0','sink:clinic':'3'}
        assert result.boundaries[0].limit_status=='limit_breached'
    else:assert additional(result)=={'water:farm':'0','water:clinic':'4','sink:farm':'0','sink:clinic':'0'}


@pytest.mark.parametrize('identity',['VERSION','MODEL','RUNTIME_ID','EVALUATOR_ID'])
def test_implementation_identity_invalidates_preview(monkeypatch, identity):
    from poliscope_engine.domains.environment import exploration
    data=request();ctx=context();c=card(data,ctx)
    monkeypatch.setattr(exploration,identity,'changed')
    with pytest.raises(AccountError,match='stale_environment_preview'):
        preview(EnvironmentRequest.model_validate(data),edit=edit(c),**ctx)


@pytest.mark.parametrize('limit,policy,status',[(None,None,'not_selected'),(None,'explicit:unknown','unknown'),('9','explicit:limit','within_limit'),('0','explicit:limit','limit_breached')])
def test_selected_limits_never_change_finite_allocations(limit,policy,status):
    data=request();ctx=context()
    for boundary in data['boundaries']:
        boundary.update(selected_limit=limit,policy_ref=policy)
    c=card(data,ctx)
    result=preview(EnvironmentRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert additional(result)=={'water:farm':'1','water:clinic':'4','sink:farm':'0','sink:clinic':'3'}
    assert all(b.limit_status==status for b in result.boundaries)
