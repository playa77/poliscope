"""Detached explicit alternatives and exact source reconciliation."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.infrastructure import InfrastructureRequest, InfrastructureEdit
from poliscope_engine.domains.infrastructure.exploration import interview, preview
from poliscope_engine.domains.infrastructure.coverage import validate_coverage
from test_infrastructure import request, world, units, additional


def context():
    return dict(graph=world(), units=units())


def card(data, ctx):
    return interview(InfrastructureRequest.model_validate(data), scope_id=data['scope_id'], **ctx)


def edit(c, option=1):
    return InfrastructureEdit(baseline_digest=c.baseline_digest,scope_id=c.scope_id,option_id=c.alternatives[option].definition.id)


def test_explicit_competing_school_clinic_previews_are_detached():
    data=request(); before=deepcopy(data); ctx=context(); c=card(data,ctx)
    assert c.selected_option_id is None
    dto=InfrastructureRequest.model_validate(data)
    retained=preview(dto,edit=edit(c,0),**ctx)
    reversed_=preview(dto,edit=edit(c),**ctx)
    assert additional(retained.report.evaluation)=={'school:visit':'2','clinic:visit':'1'}
    assert additional(reversed_.report.evaluation)=={'school:visit':'1','clinic:visit':'2'}
    candidate=reversed_.report.evaluation.request.model_dump()
    candidate['claim_order']=before['claim_order']
    assert candidate==before==dto.model_dump()==data
    reversed_.report.evaluation.request.links[0].source_refs.append('detached')
    assert dto.model_dump()==before


@pytest.mark.parametrize('field',['path','access','availability','opening','queue','source','world','units','period'])
def test_complete_context_rejects_stale_preview(field):
    data=request();ctx=context();c=card(data,ctx)
    if field=='path':data['demands'][0]['path']=[]
    elif field=='access':data['demands'][0]['access']='unknown'
    elif field=='availability':data['links'][0]['availability']='planned'
    elif field=='opening':data['batch']['accounts'][0]['opening']='0'
    elif field=='queue':data['claim_order'].reverse()
    elif field=='source':data['source_refs']=['changed']
    elif field=='period':data['period_id']='day:1'
    elif field=='world':
        from poliscope_engine.world.membership import WorldGraph
        ctx['graph']=WorldGraph(ctx['graph'].registry,ctx['graph'].relationships[:-1])
    else:ctx['units']=replace(ctx['units'], units=tuple(replace(u,scale=Decimal(2)) if u.id=='slots' else u for u in ctx['units'].units))
    with pytest.raises(AccountError,match='stale_infrastructure_preview'):
        preview(InfrastructureRequest.model_validate(data),edit=edit(c),**ctx)


def test_scope_and_unknown_option():
    data=request();ctx=context();c=card(data,ctx);dto=InfrastructureRequest.model_validate(data)
    for changes,error in [({'scope_id':'region'},'incompatible_infrastructure_scope'),({'option_id':'unknown'},'unknown_infrastructure_option')]:
        with pytest.raises(AccountError,match=error):preview(dto,edit=edit(c).model_copy(update=changes),**ctx)


@pytest.mark.parametrize('mode',['disconnected','planned','unknown','hold','prior'])
def test_alternatives_preserve_constraints_and_commitments(mode):
    data=request();ctx=context()
    if mode=='disconnected':data['demands'][0].update(origin_id='island',path=[])
    elif mode=='planned':data['facilities'][0]['availability']='planned'
    elif mode=='unknown':data['links'][0]['availability']='unknown'
    elif mode=='hold':data['batch']['reservations']=[dict(id='school:hold',account_id='school:slots',claim_id='school:visit',amount='2')]
    else:
        from test_infrastructure import run
        data['batch']=run(data).allocation.batch.model_dump()
    before=deepcopy(data);c=card(data,ctx)
    result=preview(InfrastructureRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.batch==InfrastructureRequest.model_validate(before).batch
    if mode in ('disconnected','planned'):assert result.results[0].additional=='0'
    elif mode=='unknown':assert result.status=='unresolved' and all(r.additional is None for r in result.results)
    elif mode=='prior':assert all(r.additional=='0' for r in result.results)
    assert data==before


ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('corruption',[None,'missing','duplicate','extra','title','documents','options','activation','scope','availability','revision','digest','refs','transition'])
def test_exact_source_inventory(corruption):
    data=json.loads((ROOT/'content/infrastructure/coverage-v1.json').read_text())
    source=json.loads((ROOT/'content/release-v1/society.inventory.json').read_text())
    if corruption is None:
        result=validate_coverage(data,source)
        assert {r.source_id for r in result.entries if r.static_available}=={'society:domain/08/1','society:domain/08/1/2'}
        return
    if corruption=='missing':data['entries'].pop()
    elif corruption=='duplicate':data['entries'].append(data['entries'][0])
    elif corruption=='extra':data['entries'][0]['source_id']='extra'
    elif corruption=='title':data['entries'][0]['title']='changed'
    elif corruption=='documents':data['entries'][0]['documents']=['invented']
    elif corruption=='options':data['entries'][-1]['option_refs']=['invented']
    elif corruption=='activation':data['activation']='activated'
    elif corruption=='scope':data['entries'][0]['supported_scope_kinds']=['region']
    elif corruption=='availability':data['entries'][1]['static_available']=True
    elif corruption=='revision':data['source_revision']='changed'
    elif corruption=='digest':data['source_archive_digest']='sha256:'+'0'*64
    elif corruption=='refs':data['entries'][0]['implementation_refs']=[]
    else:data['entries'][0]['transition_available']=True
    with pytest.raises((AccountError,ValueError)):validate_coverage(data,source)


@pytest.mark.parametrize('procedure',['priority','all_or_nothing',None])
def test_regional_procedure_is_retained_without_defaulting(procedure):
    data=request();ctx=context();data['scope_id']='region';data['procedure']=procedure
    for a in data['batch']['accounts']:a['scope_id']='region'
    c=card(data,ctx)
    result=preview(InfrastructureRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.procedure==procedure
    if procedure is None:
        assert result.status=='unresolved' and all(r.additional is None for r in result.results)
    elif procedure=='priority':assert additional(result)=={'school:visit':'1','clinic:visit':'2'}
    else:assert additional(result)=={'school:visit':'0','clinic:visit':'2'}
