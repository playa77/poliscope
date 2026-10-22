"""Detached explicit alternatives and exact source reconciliation."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.communication import CommunicationRequest, CommunicationEdit
from poliscope_engine.domains.communication.exploration import interview, preview
from poliscope_engine.domains.communication.coverage import validate_coverage
from test_communication import request, world, units

def additional(result):
    return {r.claim_id:r.additional for r in result.results}


def context():
    return dict(graph=world(), units=units())


def card(data, ctx):
    return interview(CommunicationRequest.model_validate(data), scope_id=data['scope_id'], **ctx)


def edit(c, option=1):
    return CommunicationEdit(baseline_digest=c.baseline_digest,scope_id=c.scope_id,option_id=c.alternatives[option].definition.id)


def test_explicit_competing_school_clinic_previews_are_detached():
    data=request(); before=deepcopy(data); ctx=context(); c=card(data,ctx)
    assert c.selected_option_id is None
    dto=CommunicationRequest.model_validate(data)
    retained=preview(dto,edit=edit(c,0),**ctx)
    reversed_=preview(dto,edit=edit(c),**ctx)
    assert additional(retained.report.evaluation)=={'school:notice':'2','clinic:notice':'0'}
    assert additional(reversed_.report.evaluation)=={'school:notice':'0','clinic:notice':'2'}
    candidate=reversed_.report.evaluation.request.model_dump()
    candidate['claim_order']=before['claim_order']
    assert candidate==before==dto.model_dump()==data
    reversed_.report.evaluation.request.channels[0].source_refs.append('detached')
    assert dto.model_dump()==before


@pytest.mark.parametrize('field',['reach','disclosure','recorded','available','verification','delay','availability','opening','queue','source','world','units','period'])
def test_complete_context_rejects_stale_preview(field):
    data=request();ctx=context();c=card(data,ctx)
    if field=='reach':data['demands'][0]['channel_relationship_id']=None
    elif field=='disclosure':data['demands'][0]['disclosure']='unknown'
    elif field in ('recorded','available'):data['demands'][0][field]=False
    elif field=='verification':data['demands'][0]['verification_procedure_ref']='changed'
    elif field=='delay':data['demands'][0]['delay_ticks']=4
    elif field=='availability':data['channels'][0]['availability']='offline'
    elif field=='opening':data['batch']['accounts'][0]['opening']='0'
    elif field=='queue':data['claim_order'].reverse()
    elif field=='source':data['source_refs']=['changed']
    elif field=='period':data['period_id']='day:1'
    elif field=='world':
        from poliscope_engine.world.membership import WorldGraph
        ctx['graph']=WorldGraph(ctx['graph'].registry,ctx['graph'].relationships[:-1])
    else:ctx['units']=replace(ctx['units'], units=tuple(replace(u,scale=Decimal(2)) if u.id=='messages' else u for u in ctx['units'].units))
    with pytest.raises(AccountError,match='stale_communication_preview'):
        preview(CommunicationRequest.model_validate(data),edit=edit(c),**ctx)


def test_scope_and_unknown_option():
    data=request();ctx=context();c=card(data,ctx);dto=CommunicationRequest.model_validate(data)
    for changes,error in [({'scope_id':'region'},'incompatible_communication_scope'),({'option_id':'unknown'},'unknown_communication_option')]:
        with pytest.raises(AccountError,match=error):preview(dto,edit=edit(c).model_copy(update=changes),**ctx)


@pytest.mark.parametrize('mode',['disconnected','offline','unknown','hold','prior'])
def test_alternatives_preserve_constraints_and_commitments(mode):
    data=request();ctx=context()
    if mode=='disconnected':data['demands'][0]['channel_relationship_id']=None
    elif mode=='offline':data['channels'][0]['availability']='offline'
    elif mode=='unknown':data['channels'][0]['availability']='unknown'
    elif mode=='hold':data['batch']['reservations']=[dict(id='school:hold',account_id='channel',claim_id='school:notice',amount='2')]
    else:
        from test_communication import run
        data['batch']=run(data).allocation.batch.model_dump()
    before=deepcopy(data);c=card(data,ctx)
    result=preview(CommunicationRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.batch==CommunicationRequest.model_validate(before).batch
    if mode in ('disconnected','offline'):assert result.results[0].additional=='0'
    elif mode=='unknown':assert result.status=='unresolved' and all(r.additional is None for r in result.results)
    elif mode=='prior':assert all(r.additional=='0' for r in result.results)
    assert data==before


ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('corruption',[None,'missing','duplicate','extra','title','documents','options','activation','scope','availability','revision','digest','refs','transition'])
def test_exact_source_inventory(corruption):
    data=json.loads((ROOT/'content/communication/coverage-v1.json').read_text())
    source=json.loads((ROOT/'content/release-v1/society.inventory.json').read_text())
    if corruption is None:
        result=validate_coverage(data,source)
        assert {r.source_id for r in result.entries if r.static_available}=={'society:domain/09/1','society:domain/09/1/1','society:domain/09/1/2'}
        return
    if corruption=='missing':data['entries'].pop()
    elif corruption=='duplicate':data['entries'].append(data['entries'][0])
    elif corruption=='extra':data['entries'][0]['source_id']='extra'
    elif corruption=='title':data['entries'][0]['title']='changed'
    elif corruption=='documents':data['entries'][0]['documents']=['invented']
    elif corruption=='options':data['entries'][-1]['option_refs']=['invented']
    elif corruption=='activation':data['activation']='activated'
    elif corruption=='scope':data['entries'][0]['supported_scope_kinds']=['region']
    elif corruption=='availability':data['entries'][1]['static_available']=False
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
    result=preview(CommunicationRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.procedure==procedure
    if procedure is None:
        assert result.status=='unresolved' and all(r.additional is None for r in result.results)
    elif procedure=='priority':assert additional(result)=={'school:notice':'0','clinic:notice':'2'}
    else:assert additional(result)=={'school:notice':'0','clinic:notice':'2'}


@pytest.mark.parametrize('identity',['VERSION','MODEL','RUNTIME_ID','EVALUATOR_ID'])
def test_implementation_identity_invalidates_preview(monkeypatch, identity):
    from poliscope_engine.domains.communication import exploration
    data=request();ctx=context();c=card(data,ctx)
    monkeypatch.setattr(exploration,identity,'changed')
    with pytest.raises(AccountError,match='stale_communication_preview'):
        preview(CommunicationRequest.model_validate(data),edit=edit(c),**ctx)


def test_optional_verification_and_disclosure_remain_explicit():
    data=request();ctx=context()
    for demand in data['demands']:
        demand.update(verification_account_id=None,verification_procedure_ref=None)
    data['batch']['accounts'].pop()
    c=card(data,ctx)
    result=preview(CommunicationRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert additional(result)=={'school:notice':'1','clinic:notice':'2'}
    assert all(d.verification_procedure_ref is None for d in result.request.demands)
    data['demands'][1]['disclosure']='denied'
    c=card(data,ctx)
    result=preview(CommunicationRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert additional(result)=={'school:notice':'2','clinic:notice':'0'}
    assert result.results[1].findings==['disclosure_denied']
