"""Real DOM-03/08 composition with independent finite-book and response prerequisites."""

from copy import deepcopy

from dataclasses import replace

from fractions import Fraction

import pytest

from pydantic import ValidationError

from poliscope_engine.accounts import AccountError

from poliscope_engine.contracts.governance_infrastructure import GovernanceInfrastructureRequest

from poliscope_engine.contracts.revisions import RevisionInputs

from poliscope_engine.contracts.world import LabelValue

from poliscope_engine.domains import ConformanceError

from poliscope_engine.domains.conformance import ConformanceCase

from poliscope_engine.domains.governance.infrastructure import evaluate_pair, binding

from poliscope_engine.domains.governance.infrastructure_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)

from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest

from governance_infrastructure_fixture import fixture, setup, trusted

def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-governance-infrastructure',
        'oracle:governance-infrastructure-literal-v1') for d in definitions()]

def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))

def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['infrastructure']['demands'][0]['access']='denied'
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
        dict(node=['output','provision',CANDIDATE],status='partial')),
        trace_edges=((('output','work',WORK),('input','provision',BOOK)),))
    result=run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert result==run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert result.accounts is None
    assert reg.bind(('authored:gi-administration-mechanism','v1'),('authored:gi-infrastructure-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'

@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['infrastructure']['demands'][0]['access']='denied';r=GovernanceInfrastructureRequest.model_validate(data)
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
    work=callbacks['authored:gi-administration'];consumer=callbacks['authored:gi-infrastructure']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.infrastructure.demands[0] = r.infrastructure.demands[0].model_copy(update={'access':'denied'})
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})

@pytest.mark.parametrize('missing', ['administration','economy','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:gi-administration-mechanism',
        'economy':'authored:gi-infrastructure-mechanism','policy':'authored:gi-policy-mechanism'}[missing]
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
    r.infrastructure.demands[0] = r.infrastructure.demands[0].model_copy(update={'access':'denied'});result.candidate.infrastructure.postings.clear()
    assert result.request.infrastructure.demands[0].access=='allowed'
    assert run().candidate.infrastructure.postings

def test_replay_then_rejection_never_refunds_or_double_spends():
    first=run();data=fixture()
    data['request']['governance']['administration']['batch']=first.candidate.administration.model_dump()
    data['request']['infrastructure']['batch']=first.candidate.infrastructure.model_dump()
    second=run(data)
    assert second.candidate==first.candidate
    assert all(m.additional=='0' for m in second.infrastructure.results)
    data['request']['governance']['approval']='unanimity'
    rejected=run(data)
    assert rejected.governance.outcome=='rejected' and rejected.candidate==first.candidate
    assert amounts(rejected)['reach:make']==['3','0','0']

@pytest.mark.parametrize('selection',[None,'original','competing'])
def test_overlapping_authority_needs_explicit_selection(selection):
    data=fixture();gov=data['request']['governance'];competing=deepcopy(gov['bindings'][0])
    competing.update(id='competing',authority_id='region-authority',scope_id='region');gov['bindings'].append(competing)
    if selection is not None:
        gov['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='gi:permission',
            entity_id='food',operation='select',participant_ids=['proposal','competing'],
            selected_id='proposal' if selection=='original' else 'competing',source_refs=['authored:governance-infrastructure-v1'])]
    result=run(data)
    if selection=='original':assert result.status=='resolved'
    else:
        assert result.status=='unresolved' and result.candidate is None
        assert result.governance.findings==(['institutional_conflict'] if selection is None else ['proposal_not_selected'])

@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('prerequisites','reach:make'),('payload','private')])
def test_private_contract_strict(field,value):
    data=fixture();data['request'][field]=value
    with pytest.raises(ValidationError):run(data)

def test_duplicate_dated_time_pool_rejected():
    data=fixture();work=data['request']['governance']['administration']
    account=deepcopy(next(a for a in work['batch']['accounts'] if a['id']=='labor'));account['id']='labor:duplicate';work['batch']['accounts'].append(account)
    work['holders'].append(dict(account_id='labor:duplicate',holder_id='shared:cohort',role='time'))
    data['inputs']['entities'].append(dict(id='labor:duplicate',entity_kind='account',label='Invalid duplicate time',provenance=dict(origin='authored',source_refs=[],assumption_refs=[])))
    with pytest.raises(AccountError,match='duplicate.*time|time.*duplicate'):run(data)

@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_administration_uses_one_dated_time_book_with_competing_prior_care(procedure):
    for time in range(4,17):
        data=fixture();work=data['request']['governance']['administration']
        next(a for a in work['batch']['accounts'] if a['id']=='labor')['opening']=str(time)
        work['procedure']=procedure
        # These enumerate total fulfilled work, including each prior hour.
        admin=max(a for a in range(1,4) if a+2<=time and (procedure=='priority' or a in (1,3)))
        care=max(c for c in range(1,4) if admin+c<=time and (procedure=='priority' or c in (1,3)))
        result=run(data);accounts=result.governance.administration.allocation.accounts
        assert {c.claim_id:c.actual for c in accounts.claims if c.claim_id in ('admin','care')}=={'admin':str(admin),'care':str(care)}
        assert Fraction(next(a.closing for a in accounts.accounts if a.account_id=='labor'))+admin+care==time
        assert result.governance.outcome==('approved' if admin==3 else 'capacity_blocked')
        assert amounts(result)['reach:make'][1]==('2' if admin==3 else '0')

def test_decimal_context_does_not_change_independent_budgets():
    from decimal import localcontext
    expected=run()
    with localcontext() as context:
        context.prec=2
        assert run()==expected

def amounts(result):
    return {r.claim_id: [r.prior, r.additional, r.unmet] for r in result.infrastructure.results}

def balances(result):
    return {a.account_id: a.closing for a in result.infrastructure.allocation.accounts.accounts}

def test_literal_books_and_detached_candidates():
    data=fixture();before=deepcopy(data);result=run(data)
    assert result.status=='resolved' and result.governance.outcome=='approved'
    assert amounts(result)==data['expected']['infrastructure']
    assert balances(result)==data['expected']['infrastructure_closing']
    assert {a.account_id:a.closing for a in result.governance.administration.allocation.accounts.accounts}==data['expected']['administration_closing']
    assert result.candidate.infrastructure==result.infrastructure.allocation.batch
    assert result.candidate.administration==result.governance.administration.batch
    assert result.candidate.infrastructure.reservations==result.request.infrastructure.batch.reservations
    assert result.candidate.infrastructure.subtotals==result.request.infrastructure.batch.subtotals
    assert result.infrastructure.request==result.request.infrastructure
    assert before==data and run(data)==result
    result.candidate.infrastructure.postings.clear();result.candidate.administration.postings.clear()
    assert result.infrastructure.allocation.batch.postings and result.governance.administration.batch.postings

@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_independent_finite_facility_and_path_oracle(procedure):
    # One prior use in each pool; B's protected two-slot facility hold cannot
    # become A's capacity. Independently enumerate feasible additional uses.
    for facility,bridge,road in [(5,5,5),(4,5,6),(6,3,5),(6,5,3),(3,3,3),(7,7,7)]:
        for first in range(1,4):
            for second in range(1,4):
                data=fixture();p=data['request']['infrastructure'];p['procedure']=procedure
                for account,opening in zip(p['batch']['accounts'],[facility,bridge,road]):account['opening']=str(opening)
                p['batch']['claims'][0]['requested']=str(first+1);p['batch']['claims'][1]['requested']=str(second)
                reserve=min(2,second);p['batch']['reservations'][0]['amount']=str(reserve)
                for demand in p['demands']:demand['access_limit']='9'
                feasible=[(a,b) for a in range(first+1) for b in range(second+1)
                    if 1+a+b<=min(facility,bridge,road) and a<=facility-1-reserve
                    and (procedure=='priority' or a in (0,first) and b in (0,second))]
                a,b=max(feasible);result=run(data)
                assert amounts(result)=={'reach:make':['1',str(a),str(first-a)],'reach:deliver':['0',str(b),str(second-b)]}
                for account,opening in zip(p['batch']['accounts'],[facility,bridge,road]):
                    assert Fraction(balances(result)[account['id']])+1+a+b==opening

@pytest.mark.parametrize('outcome',['approved','rejected','no_quorum','capacity_blocked'])
@pytest.mark.parametrize('independent',[False,True])
def test_only_explicit_dependent_new_access_is_restricted(outcome,independent):
    data=fixture();gov=data['request']['governance']
    if outcome=='rejected':gov['approval']='unanimity'
    elif outcome=='no_quorum':gov['ballots']=gov['ballots'][:1]
    elif outcome=='capacity_blocked':gov['administration']['activities'][0]['access_limit']='1'
    data['request']['prerequisites'][0].update(requires_approval=not independent,decision_target_id=None if independent else 'food')
    result=run(data);allowed=independent or outcome=='approved'
    assert result.status=='resolved' and result.governance.outcome==outcome
    assert amounts(result)['reach:make']==(['1','2','0'] if allowed else ['1','0','2'])
    assert amounts(result)['reach:deliver']==(['0','2','1'] if allowed else ['0','3','0'])
    assert result.infrastructure.request.demands[0].access==('allowed' if allowed else 'denied')
    assert result.request.infrastructure.demands[0].access=='allowed'

@pytest.mark.parametrize('field',['access','facility','link','procedure'])
@pytest.mark.parametrize('approved',[True,False])
def test_unknown_facility_inputs_survive_any_decision(field,approved):
    data=fixture();p=data['request']['infrastructure']
    if not approved:data['request']['governance']['approval']='unanimity'
    if field=='facility':p['facilities'][0]['availability']='unknown'
    elif field=='link':p['links'][0]['availability']='unknown'
    elif field=='procedure':p['procedure']=None
    else:p['demands'][0]['access']='unknown'
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None
    assert result.preflight.status=='unresolved' and result.infrastructure.status=='unresolved'
    assert result.infrastructure.allocation.batch==result.request.infrastructure.batch
    assert all(r.additional is None and r.unmet is None for r in result.infrastructure.results)

@pytest.mark.parametrize('missing',['ballot','approval','policy','access','terms','procedure'])
def test_unknown_decision_retains_original_preflight(missing):
    data=fixture();gov=data['request']['governance']
    if missing=='ballot':gov['ballots'][0]['vote']='unknown'
    elif missing=='approval':gov['approval']=None
    elif missing=='policy':gov['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='access':gov['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='terms':gov['administration']['activities'][0]['terms_known']=False
    else:gov['administration']['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None and result.infrastructure is None
    assert result.preflight.status=='resolved' and result.preflight.results[0].additional=='2'
    assert result.request.infrastructure.batch.model_dump()['postings']==data['request']['infrastructure']['batch']['postings']

@pytest.mark.parametrize('field,value,finding',[
    ('access','denied','access_denied'),('facility','offline','nonoperating_asset'),
    ('facility','planned','nonoperating_asset'),('facility','retired','nonoperating_asset'),
    ('link','offline','nonoperating_asset'),('access_limit','1','capacity_shortfall'),
    ('disconnected',None,'disconnected')])
def test_approval_preserves_original_restrictions(field,value,finding):
    data=fixture();p=data['request']['infrastructure']
    if field=='facility':p['facilities'][0]['availability']=value
    elif field=='link':p['links'][0]['availability']=value
    elif field=='disconnected':
        data['inputs']['entities'].append(dict(id='isolated',entity_kind='location',label='Disconnected origin',provenance=dict(origin='authored',source_refs=[],assumption_refs=[])))
        p['demands'][0].update(origin_id='isolated',path=[])
    else:p['demands'][0][field]=value
    result=run(data)
    assert result.status=='resolved' and result.governance.outcome=='approved'
    assert result.infrastructure.request==result.request.infrastructure
    assert finding in result.infrastructure.results[0].findings
    assert amounts(result)['reach:make']==(['1','1','1'] if field=='access_limit' else ['1','0','2'])

@pytest.mark.parametrize('mutation,code',[
    ('period','period_mismatch'),('scope','scope_mismatch'),('missing','invalid_decision_infrastructure_mapping'),
    ('duplicate','invalid_decision_infrastructure_mapping'),('foreign','invalid_decision_infrastructure_mapping'),
    ('target','affected_mapping'),('affected_facility','affected_mapping'),('affected_path','affected_mapping'),
    ('independent_target','independent_target'),('foreign_account','account_identity'),
    ('foreign_claimant','claimant_identity'),('foreign_holder','holder_identity'),('missing_holder','time_holders'),
    ('overlap','overlapping_books'),('claim_overlap','overlapping_books'),('subtotal_overlap','overlapping_books'),
    ('account_period','period_mismatch'),('reversed_path','invalid_infrastructure_path'),
    ('omitted_path','incomplete_infrastructure_path'),('wrong_relation','invalid_infrastructure_connectivity'),
    ('duplicate_facility','duplicate_or_unmapped_infrastructure_capacity'),('wrong_units','invalid_infrastructure_capacity')])
def test_invalid_original_context_rejected_even_with_unknown_decision(mutation,code):
    data=fixture();gov=data['request']['governance'];p=data['request']['infrastructure'];gov['ballots'][0]['vote']='unknown'
    if mutation=='period':p['period_id']='day:1'
    elif mutation=='scope':p['scope_id']='west'
    elif mutation=='missing':data['request']['prerequisites'].pop()
    elif mutation=='duplicate':data['request']['prerequisites']*=2
    elif mutation=='foreign':data['request']['prerequisites'][0]['claim_id']='foreign'
    elif mutation=='target':data['request']['prerequisites'][0]['decision_target_id']='water'
    elif mutation=='affected_facility':gov['bindings'][0]['account_refs'].remove('depot:slots')
    elif mutation=='affected_path':gov['bindings'][0]['account_refs'].remove('bridge:slots')
    elif mutation=='independent_target':data['request']['prerequisites'][1]['decision_target_id']='food'
    elif mutation=='foreign_account':p['batch']['accounts'][0]['id']='foreign'
    elif mutation=='foreign_claimant':gov['administration']['batch']['claims'][0]['claimant_id']='foreign'
    elif mutation=='foreign_holder':gov['administration']['holders'][0]['holder_id']='foreign'
    elif mutation=='missing_holder':gov['administration']['holders'].pop(0)
    elif mutation=='overlap':gov['administration']['batch']['accounts'].append(deepcopy(p['batch']['accounts'][0]))
    elif mutation=='claim_overlap':p['batch']['claims'][0]['id']='admin'
    elif mutation=='subtotal_overlap':p['batch']['subtotals'][0]['id']='east:stock-view'
    elif mutation=='account_period':p['batch']['accounts'][0]['period_id']='day:1'
    elif mutation=='reversed_path':p['demands'][0]['path'].reverse()
    elif mutation=='omitted_path':p['demands'][0]['path']=[]
    elif mutation=='wrong_relation':p['links'][0]['relationship_id']='depot:location'
    elif mutation=='duplicate_facility':p['facilities']*=2
    else:
        for account in p['batch']['accounts']:account['unit_id']='hours'
    with pytest.raises((AccountError,ValidationError),match=code):run(data)

@pytest.mark.parametrize('scope',['west','region'])
def test_two_scopes_and_regional_authority(scope):
    import json
    data=fixture();authority='region-authority' if scope=='region' else 'west-authority'
    if scope=='west':
        entity=deepcopy(next(e for e in data['inputs']['entities'] if e['id']=='east-authority'));entity['id']=authority;data['inputs']['entities'].append(entity)
    data['request']=json.loads(json.dumps(data['request']).replace('"east"',f'"{scope}"').replace('"east-authority"',f'"{authority}"'))
    if scope=='region':
        gov=data['request']['governance'];gov['eligible_member_ids']=['shared:cohort','region-authority'];gov['ballots']=[dict(member_id=m,vote='yes') for m in gov['eligible_member_ids']]
    relation=deepcopy(next(r for r in data['inputs']['relationships'] if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority'))
    relation.update(id='scope:jurisdiction',from_id=authority,to_id=scope);data['inputs']['relationships'].append(relation)
    assert run(data).status=='resolved'

def test_explicit_reverse_queue_preserves_prior_path_use():
    data=fixture();data['request']['infrastructure']['claim_order'].reverse()
    result=run(data)
    assert amounts(result)=={'reach:make':['1','1','1'],'reach:deliver':['0','3','0']}
    assert balances(result)=={'bridge:slots':'0','depot:slots':'0','road:slots':'0'}

@pytest.mark.parametrize('mutation',['forged_dto','policy_units','payload'])
def test_nested_contract_revalidation(mutation):
    from poliscope_engine.numeric import Registry,Unit
    from decimal import Decimal
    data=fixture()
    if mutation=='payload':
        data['request']['infrastructure']['demands'][0]['payload']='private'
        with pytest.raises(ValidationError):run(data)
        return
    r,i,g,u=setup(data);m=policy_registry(units=u,reviews=reviews())
    if mutation=='forged_dto':
        r.infrastructure.demands[0].__dict__['access']='forced'
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u,mechanisms=m)
    else:
        changed=Registry(tuple(Unit(x.id,x.dimension,x.kind,x.scale*Decimal(2)) for x in u.units))
        with pytest.raises(AccountError,match='policy_units'):evaluate_pair(r,graph=g,units=changed,mechanisms=m)

def test_denied_independent_demand_keeps_its_protected_hold():
    data=fixture();p=data['request']['infrastructure']
    p['demands'][1]['access']='denied';p['batch']['claims'][0]['requested']='5';p['demands'][0]['access_limit']='5'
    result=run(data)
    assert amounts(result)=={'reach:make':['1','2','2'],'reach:deliver':['0','0','3']}
    assert balances(result)=={'depot:slots':'2','bridge:slots':'2','road:slots':'2'}
    data['request']['governance']['administration']['batch']=result.candidate.administration.model_dump()
    p['batch']=result.candidate.infrastructure.model_dump()
    assert run(data).candidate==result.candidate


def test_local_independent_claim_does_not_consume_remote_path_capacity():
    data=fixture();p=data['request']['infrastructure']
    p['demands'][1].update(origin_id='destination',path=[])
    p['batch']['claims'][1]['claimant_id']='cohort:b'
    result=run(data)
    assert amounts(result)=={'reach:make':['1','2','0'],'reach:deliver':['0','2','1']}
    assert balances(result)=={'depot:slots':'0','bridge:slots':'2','road:slots':'2'}
    assert result.infrastructure.results[1].claimant_id=='cohort:b'
    assert result.infrastructure.results[1].path==[]


def test_host_consumer_withholds_unknown_and_rejects_wrong_port_or_kind():
    data=fixture();data['request']['infrastructure']['links'][0]['availability']='unknown'
    r,i,g,u=setup(data);reg,i=trusted(r,i,g,u);callbacks={x.id:x.callback for x in reg.implementations}
    work=callbacks['authored:gi-administration'];consumer=callbacks['authored:gi-infrastructure']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='unknown'
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work('wrong:port',{CONTEXT:LabelValue(kind='label',value=context)})
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer('wrong:port',{BOOK:LabelValue.model_validate(token)})


def test_unknown_governance_never_exposes_a_staged_host_book():
    data=fixture();data['request']['governance']['ballots'][0]['vote']='unknown'
    r,i,g,u=setup(data);reg,i=trusted(r,i,g,u);work=next(x.callback for x in reg.implementations if x.id=='authored:gi-administration')
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})['kind']=='unknown'
