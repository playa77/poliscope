"""Private continuity queue alternatives and pinned source reconciliation."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.security_risk import ContinuityRequest, ContinuityEdit
from poliscope_engine.domains.security_risk.exploration import interview, preview
from poliscope_engine.domains.security_risk.coverage import validate_coverage
from test_security_risk import request, world, units, run


def context():
    return dict(graph=world(), units=units())


def card(data, ctx):
    return interview(ContinuityRequest.model_validate(data), scope_id=data['scope_id'], **ctx)


def edit(c, option=1):
    return ContinuityEdit(baseline_digest=c.baseline_digest, scope_id=c.scope_id,
        option_id=c.alternatives[option].definition.id)


def amounts(result):
    return [r.additional for r in result.results]


def test_groups_compete_without_changing_declarations_or_inputs():
    data=request(); before=deepcopy(data); ctx=context(); c=card(data,ctx)
    assert c.selected_option_id is None
    dto=ContinuityRequest.model_validate(data)
    retained=preview(dto,edit=edit(c,0),**ctx)
    reversed_=preview(dto,edit=edit(c),**ctx)
    assert amounts(retained.report.evaluation)==['2','1']
    assert amounts(reversed_.report.evaluation)==['1','2']
    assert reversed_.candidate_digest==reversed_.report.baseline_digest
    candidate=reversed_.report.evaluation.request.model_dump()
    candidate['claim_order']=before['claim_order']
    assert candidate==before==dto.model_dump()==data
    reversed_.report.evaluation.request.demands[0].source_refs.append('detached')
    c.alternatives[0].claim_order.reverse()
    assert dto.model_dump()==before


@pytest.mark.parametrize('field',['participation','eligibility','access','access_limit','obligation_status',
    'obligation_refs','hazard_ref','exposure_refs','authority','disclosure','aid_condition','vulnerability','availability','opening','queue',
    'source','world','units','period','procedure'])
def test_complete_context_rejects_stale_preview(field):
    data=request();ctx=context();c=card(data,ctx)
    if field in ('participation','eligibility','access','obligation_status'):data['demands'][0][field]='unknown'
    elif field=='access_limit':data['demands'][0][field]='1'
    elif field=='obligation_refs':data['demands'][0][field]=['changed']
    elif field=='hazard_ref':data['demands'][0][field]='changed'
    elif field=='exposure_refs':data['demands'][0][field]=['changed']
    elif field in ('authority','disclosure','aid_condition','vulnerability'):data['demands'][0][field]='unknown'
    elif field=='availability':data['facilities'][0][field]='offline'
    elif field=='opening':data['batch']['accounts'][0]['opening']='0'
    elif field=='queue':data['claim_order'].reverse()
    elif field=='source':data['source_refs']=['changed']
    elif field=='period':data['period_id']='day:1'
    elif field=='procedure':data['procedure']='all_or_nothing'
    elif field=='world':
        from poliscope_engine.world.membership import WorldGraph
        ctx['graph']=WorldGraph(ctx['graph'].registry,ctx['graph'].relationships[:-1])
    else:ctx['units']=replace(ctx['units'],units=tuple(replace(u,scale=Decimal(2)) for u in ctx['units'].units))
    with pytest.raises(AccountError,match='stale_continuity_preview'):
        preview(ContinuityRequest.model_validate(data),edit=edit(c),**ctx)


def test_scope_and_unknown_option():
    data=request();ctx=context();c=card(data,ctx);dto=ContinuityRequest.model_validate(data)
    for changes,error in [({'scope_id':'region'},'incompatible_continuity_scope'),({'option_id':'unknown'},'unknown_continuity_option')]:
        with pytest.raises(AccountError,match=error):preview(dto,edit=edit(c).model_copy(update=changes),**ctx)


@pytest.mark.parametrize('mode',['declined','ineligible','denied','unknown','conflict','offline','ceiling','hold','prior'])
def test_alternatives_retain_constraints_and_commitments(mode):
    data=request();ctx=context()
    if mode=='declined':data['demands'][0]['participation']='declined'
    elif mode=='ineligible':data['demands'][0]['eligibility']='ineligible'
    elif mode=='denied':data['demands'][0]['access']='denied'
    elif mode=='unknown':data['demands'][0]['eligibility']='unknown'
    elif mode=='conflict':data['demands'][0]['obligation_status']='conflict'
    elif mode=='offline':data['facilities'][0]['availability']='offline'
    elif mode=='ceiling':data['demands'][0]['access_limit']='0'
    elif mode=='hold':data['batch']['reservations']=[dict(id='hold',account_id='depot',claim_id='response',amount='2')]
    else:data['batch']=run(data).allocation.batch.model_dump()
    before=deepcopy(data);c=card(data,ctx)
    result=preview(ContinuityRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.batch==ContinuityRequest.model_validate(before).batch
    if mode in ('unknown','conflict'):assert result.status=='unresolved' and amounts(result)==[None,None]
    elif mode=='hold':assert amounts(result)==['2','1']
    elif mode=='prior':assert amounts(result)==['0','0']
    else:assert result.results[0].additional=='0'
    assert data==before


@pytest.mark.parametrize('scope',['local','region'])
@pytest.mark.parametrize('procedure',['priority','all_or_nothing',None])
def test_scopes_and_procedures(scope,procedure):
    data=request();data['scope_id']=scope;data['procedure']=procedure
    for a in data['batch']['accounts']:a['scope_id']=scope
    ctx=context();c=card(data,ctx)
    result=preview(ContinuityRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert result.request.procedure==procedure
    assert amounts(result)==({'priority':['1','2'],'all_or_nothing':['0','2'],None:[None,None]}[procedure])


@pytest.mark.parametrize('identity',['VERSION','MODEL','RUNTIME_ID','EVALUATOR_ID'])
def test_implementation_identity_invalidates_preview(monkeypatch,identity):
    from poliscope_engine.domains.security_risk import exploration
    data=request();ctx=context();c=card(data,ctx)
    monkeypatch.setattr(exploration,identity,'changed')
    with pytest.raises(AccountError,match='stale_continuity_preview'):
        preview(ContinuityRequest.model_validate(data),edit=edit(c),**ctx)


ROOT=Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('corruption',[None,'missing','duplicate','extra','title','documents','options','activation','scope','availability','revision','digest','refs','transition','status','evidence'])
def test_exact_source_inventory(corruption):
    data=json.loads((ROOT/'content/security-risk/coverage-v1.json').read_text())
    source=json.loads((ROOT/'content/release-v1/society.inventory.json').read_text())
    if corruption is None:
        result=validate_coverage(data,source)
        assert {r.source_id for r in result.entries if r.static_available}=={'society:domain/12/1','society:domain/12/1/3','society:domain/12/2','society:domain/12/2/1','society:domain/12/2/2'}
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
    elif corruption=='status':data['entries'][0]['status']='unsupported'
    elif corruption=='evidence':data['entries'][0]['evidence_status']='unreviewed'
    else:data['entries'][0]['transition_available']=True
    with pytest.raises((AccountError,ValueError)):validate_coverage(data,source)


@pytest.mark.parametrize('field,value,expected', [
    ('authority','delayed',['0','2']),
    ('disclosure','withheld',['0','2']),
    ('vulnerability','unknown',[None,None]),
    ('obligation_status','conflict',[None,None]),
    ('aid_condition','unavailable',['0','2']),
    ('aid_condition','unknown',[None,None]),
])
def test_external_aid_and_authority_remain_constraints(field,value,expected):
    data=request(); data['facilities'][0]['origin']='external'
    for demand in data['demands']: demand['purpose']='external_aid'
    data['demands'][0][field]=value
    before=deepcopy(data);ctx=context();c=card(data,ctx)
    result=preview(ContinuityRequest.model_validate(data),edit=edit(c),**ctx).report.evaluation
    assert amounts(result)==expected
    candidate=result.request.model_dump();candidate['claim_order']=before['claim_order']
    assert candidate==before==data


def test_preparedness_hold_survives_delayed_authority_in_both_queues():
    data=request();data['demands'][0]['purpose']='preparedness'
    data['demands'][0]['authority']='delayed'
    data['batch']['reservations']=[dict(id='hold',account_id='depot',claim_id='response',amount='2')]
    ctx=context();c=card(data,ctx)
    for option in (0,1):
        result=preview(ContinuityRequest.model_validate(data),edit=edit(c,option),**ctx).report.evaluation
        assert amounts(result)==['0','1']
        assert result.request.batch.reservations[0].amount=='2'


@pytest.mark.parametrize('target',['request','edit'])
def test_forged_nested_contracts_revalidate_before_preview(target):
    from pydantic import ValidationError
    data=request();ctx=context();c=card(data,ctx)
    dto=ContinuityRequest.model_validate(data);choice=edit(c)
    if target=='request':
        dto=dto.model_copy(update={'demands':[dto.demands[0].model_copy(update={'authority':'invented'}),dto.demands[1]]})
    else:
        choice=choice.model_copy(update={'option_id':17})
    with pytest.raises(ValidationError):preview(dto,edit=choice,**ctx)
