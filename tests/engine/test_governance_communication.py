"""Real DOM-03/09 composition with independent finite-book and message prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.governance_communication import GovernanceCommunicationRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.governance.communication import evaluate_pair, binding
from poliscope_engine.domains.governance.communication_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from governance_communication_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-governance-communication',
        'oracle:governance-communication-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def messages(result):
    return {r.claim_id: [r.prior,r.additional,r.unmet] for r in result.communication.results}


def balances(result):
    return {a.account_id:a.closing for a in result.communication.allocation.accounts.accounts}


def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['communication']['demands'][0]['disclosure']='denied'
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
    assert reg.bind(('authored:gc-administration-mechanism','v1'),('authored:gc-communication-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['communication']['demands'][0]['disclosure']='denied';r=GovernanceCommunicationRequest.model_validate(data)
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
    work=callbacks['authored:gc-administration'];consumer=callbacks['authored:gc-communication']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.communication.demands[0] = r.communication.demands[0].model_copy(update={'disclosure':'denied'})
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})


@pytest.mark.parametrize('missing', ['administration','economy','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:gc-administration-mechanism',
        'economy':'authored:gc-communication-mechanism','policy':'authored:gc-policy-mechanism'}[missing]
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
    r.communication.demands[0] = r.communication.demands[0].model_copy(update={'disclosure':'denied'});result.candidate.communication.postings.clear()
    assert result.request.communication.demands[0].disclosure=='allowed'
    assert run().candidate.communication.postings



def test_literal_finite_books_detach_prior_holds_subtotals_and_obligations():
    data=fixture();before=deepcopy(data);result=run(data)
    assert result.status=='resolved' and result.governance.outcome=='approved'
    assert balances(result)==data['expected']['communication_closing']
    assert messages(result)==data['expected']['messages']
    assert {a.account_id:a.closing for a in result.governance.administration.allocation.accounts.accounts}==data['expected']['administration_closing']
    assert result.candidate.administration==result.governance.administration.batch
    assert result.candidate.communication==result.communication.allocation.batch
    assert result.candidate.communication.reservations==result.request.communication.batch.reservations
    assert result.candidate.communication.subtotals==result.request.communication.batch.subtotals
    assert result.communication.request.demands[0].obligation_refs==['synthetic:disclosure-duty']
    assert result.communication.request.demands[0].delay_ticks==3
    assert data==before and run(data)==result
    result.candidate.communication.postings.clear()
    result.candidate.administration.postings.clear()
    assert result.communication.allocation.batch.postings
    assert result.governance.administration.batch.postings


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_independent_integer_feasible_sets_for_both_finite_slot_budgets(procedure):
    # Exact integer enumeration, retaining one prior slot in each budget and
    # two channel slots reserved for B. A has requested 3, with 1 already done.
    for channel in range(3,9):
        for verification in range(1,8):
            data=fixture();comm=data['request']['communication'];comm['procedure']=procedure
            comm['batch']['accounts'][0]['opening']=str(channel)
            comm['batch']['accounts'][1]['opening']=str(verification)
            feasible_a=[a for a in range(3) if a<=channel-3 and a<=verification-1
                and (procedure=='priority' or a in (0,2))]
            a=max(feasible_a)
            feasible_b=[b for b in range(4) if a+b<=channel-1 and a+b<=verification-1
                and (procedure=='priority' or b in (0,3))]
            b=max(feasible_b);result=run(data)
            assert messages(result)=={'notice:a':['1',str(a),str(2-a)],'notice:b':['0',str(b),str(3-b)]}
            assert Fraction(balances(result)['channel'])+1+a+b==channel
            assert Fraction(balances(result)['verification'])+1+a+b==verification


@pytest.mark.parametrize('outcome',['approved','rejected','no_quorum','capacity_blocked'])
@pytest.mark.parametrize('independent',[False,True])
def test_only_explicit_dependent_new_messages_are_restricted(outcome,independent):
    data=fixture();gov=data['request']['governance']
    if outcome=='rejected':gov['approval']='unanimity'
    elif outcome=='no_quorum':gov['ballots']=gov['ballots'][:1]
    elif outcome=='capacity_blocked':gov['administration']['activities'][0]['access_limit']='1'
    data['request']['prerequisites'][0].update(requires_approval=not independent,
        decision_target_id=None if independent else 'food')
    result=run(data);allowed=independent or outcome=='approved'
    assert result.status=='resolved' and result.governance.outcome==outcome
    assert messages(result)['notice:a']==(['1','2','0'] if allowed else ['1','0','2'])
    assert messages(result)['notice:b']==(['0','1','2'] if allowed else ['0','3','0'])
    assert result.communication.request.demands[0].publish_access==('allowed' if allowed else 'denied')
    assert result.request.communication.demands[0].publish_access=='allowed'


@pytest.mark.parametrize('field',['publish_access','receive_access','disclosure','recorded','available','delay_ticks','availability','procedure'])
@pytest.mark.parametrize('approved',[True,False])
def test_unknown_message_inputs_stay_unknown_under_approval_or_rejection(field,approved):
    data=fixture();comm=data['request']['communication']
    if not approved:data['request']['governance']['approval']='unanimity'
    if field=='availability':comm['channels'][0][field]='unknown'
    elif field=='procedure':comm[field]=None
    else:comm['demands'][0][field]='unknown' if field in ('publish_access','receive_access','disclosure') else None
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None
    assert result.preflight.status=='unresolved' and result.communication.status=='unresolved'
    assert result.communication.allocation.batch==result.request.communication.batch
    assert all(r.additional is None and r.unmet is None for r in result.communication.results)


@pytest.mark.parametrize('missing',['ballot','approval','policy','access','terms','procedure'])
def test_unknown_decision_retains_preflight_but_no_candidate(missing):
    data=fixture();gov=data['request']['governance']
    if missing=='ballot':gov['ballots'][0]['vote']='unknown'
    elif missing=='approval':gov['approval']=None
    elif missing=='policy':gov['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='access':gov['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='terms':gov['administration']['activities'][0]['terms_known']=False
    else:gov['administration']['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None and result.communication is None
    assert result.preflight.status=='resolved' and result.preflight.results[0].additional=='2'
    assert result.request.communication.batch.model_dump()['postings']==data['request']['communication']['batch']['postings']


@pytest.mark.parametrize('field',['publish_access','receive_access','disclosure','recorded','available','channel_relationship_id','availability'])
def test_approval_preserves_original_restrictions(field):
    data=fixture();comm=data['request']['communication']
    if field=='availability':comm['channels'][0][field]='offline'
    else:comm['demands'][0][field]=False if field in ('recorded','available') else None if field=='channel_relationship_id' else 'denied'
    result=run(data)
    assert result.governance.outcome=='approved'
    assert messages(result)['notice:a']==['1','0','2']
    assert result.communication.request==result.request.communication
    assert result.communication.results[0].outcome=='blocked'


def test_replay_then_rejection_never_refunds_or_double_spends():
    first=run();data=fixture()
    data['request']['governance']['administration']['batch']=first.candidate.administration.model_dump()
    data['request']['communication']['batch']=first.candidate.communication.model_dump()
    second=run(data)
    assert second.candidate==first.candidate
    assert all(m.additional=='0' for m in second.communication.results)
    data['request']['governance']['approval']='unanimity'
    rejected=run(data)
    assert rejected.governance.outcome=='rejected' and rejected.candidate==first.candidate
    assert messages(rejected)['notice:a']==['3','0','0']


@pytest.mark.parametrize('mutation,code',[
    ('period','period_mismatch'),('scope','scope_mismatch'),('missing','invalid_decision_communication_mapping'),
    ('duplicate','invalid_decision_communication_mapping'),('foreign','invalid_decision_communication_mapping'),
    ('target','affected_mapping'),('channel_affected','affected_mapping'),('verification_affected','affected_mapping'),
    ('independent_target','independent_target'),('foreign_account','account_identity'),
    ('foreign_claimant','claimant_identity'),('foreign_holder','holder_identity'),('missing_holder','time_holders'),
    ('overlap','overlapping_books'),('claim_overlap','overlapping_books'),('subtotal_overlap','overlapping_books'),
    ('verification_pair','incomplete_communication_verification'),('ownership','invalid_communication_control'),
    ('reach','invalid_communication_reach'),('account_period','period_mismatch'),
])
def test_invalid_original_context_is_rejected_even_with_unknown_decision(mutation,code):
    data=fixture();gov=data['request']['governance'];comm=data['request']['communication']
    gov['ballots'][0]['vote']='unknown'
    if mutation=='period':comm['period_id']='day:1'
    elif mutation=='scope':comm['scope_id']='west'
    elif mutation=='missing':data['request']['prerequisites'].pop()
    elif mutation=='duplicate':data['request']['prerequisites']*=2
    elif mutation=='foreign':data['request']['prerequisites'][0]['claim_id']='foreign'
    elif mutation=='target':data['request']['prerequisites'][0]['decision_target_id']='water'
    elif mutation=='channel_affected':gov['bindings'][0]['account_refs'].remove('channel')
    elif mutation=='verification_affected':gov['bindings'][0]['account_refs'].remove('verification')
    elif mutation=='independent_target':data['request']['prerequisites'][1]['decision_target_id']='food'
    elif mutation=='foreign_account':comm['batch']['accounts'][0]['id']='foreign'
    elif mutation=='foreign_claimant':gov['administration']['batch']['claims'][0]['claimant_id']='foreign'
    elif mutation=='foreign_holder':gov['administration']['holders'][0]['holder_id']='foreign'
    elif mutation=='missing_holder':gov['administration']['holders'].pop(0)
    elif mutation=='overlap':
        gov['administration']['batch']['accounts'].append(deepcopy(comm['batch']['accounts'][0]))
    elif mutation=='claim_overlap':comm['batch']['claims'][0]['id']='admin'
    elif mutation=='subtotal_overlap':comm['batch']['subtotals'][0]['id']='east:stock-view'
    elif mutation=='verification_pair':comm['demands'][0]['verification_procedure_ref']=None
    elif mutation=='ownership':comm['channels'][0]['ownership_relationship_id']='message:reach:a'
    elif mutation=='reach':comm['demands'][0]['channel_relationship_id']='message:reach:b'
    else:comm['batch']['accounts'][0]['period_id']='day:1'
    with pytest.raises((AccountError,ValidationError),match=code):run(data)


@pytest.mark.parametrize('selection',[None,'original','competing'])
def test_overlapping_authority_needs_explicit_selection(selection):
    data=fixture();gov=data['request']['governance'];competing=deepcopy(gov['bindings'][0])
    competing.update(id='competing',authority_id='region-authority',scope_id='region');gov['bindings'].append(competing)
    if selection is not None:
        gov['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='gc:permission',
            entity_id='food',operation='select',participant_ids=['proposal','competing'],
            selected_id='proposal' if selection=='original' else 'competing',source_refs=['authored:governance-communication-v1'])]
    result=run(data)
    if selection=='original':assert result.status=='resolved'
    else:
        assert result.status=='unresolved' and result.candidate is None
        assert result.governance.findings==(['institutional_conflict'] if selection is None else ['proposal_not_selected'])


@pytest.mark.parametrize('scope',['east','west','region'])
def test_actual_local_and_regional_scope(scope):
    import json
    data=fixture()
    if scope!='east':
        authority='region-authority' if scope=='region' else 'west-authority'
        if scope=='west':
            entity=deepcopy(next(e for e in data['inputs']['entities'] if e['id']=='east-authority'));entity['id']=authority;data['inputs']['entities'].append(entity)
        data['request']=json.loads(json.dumps(data['request']).replace('"east"',f'"{scope}"').replace('"east-authority"',f'"{authority}"'))
        if scope=='region':
            gov=data['request']['governance'];gov['eligible_member_ids']=['shared:cohort','region-authority']
            gov['ballots']=[dict(member_id=m,vote='yes') for m in gov['eligible_member_ids']]
        for relation in data['inputs']['relationships']:
            if relation['id'] in ('message:owner','message:reach:a','message:reach:b'):relation['from_id']=authority
        relation=deepcopy(next(r for r in data['inputs']['relationships'] if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority'))
        relation.update(id='scope:jurisdiction',from_id=authority,to_id=scope);data['inputs']['relationships'].append(relation)
    assert run(data).status=='resolved'


@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('prerequisites','message'),('payload','private')])
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
        assert messages(result)['notice:a'][1]==('2' if admin==3 else '0')


def test_optional_verification_and_host_delay_are_never_inferred():
    data=fixture();comm=data['request']['communication']
    comm['batch']['accounts'].pop()
    comm['batch']['postings'].pop()
    comm['batch']['subtotals'][0]['member_ids']=['channel']
    for demand in comm['demands']:
        demand.update(verification_account_id=None,verification_procedure_ref=None,delay_ticks=0)
    result=run(data)
    assert messages(result)=={'notice:a':['1','2','0'],'notice:b':['0','2','1']}
    assert balances(result)=={'channel':'0'}
    assert all(d.delay_ticks==0 for d in result.communication.request.demands)
    assert result.request.communication.demands[0].verification_procedure_ref is None


def test_explicit_reversed_queue_competes_in_same_finite_message_book():
    data=fixture();data['request']['communication']['claim_order'].reverse()
    result=run(data)
    assert messages(result)=={'notice:a':['1','0','2'],'notice:b':['0','3','0']}
    assert balances(result)=={'channel':'1','verification':'0'}


def test_two_channels_compete_for_shared_verification_slots_without_duplication():
    data=fixture();comm=data['request']['communication'];inputs=data['inputs']
    account=deepcopy(comm['batch']['accounts'][0]);account.update(id='channel:other',opening='5')
    comm['batch']['accounts'].append(account)
    channel=deepcopy(comm['channels'][0]);channel.update(asset_id='network:other',account_id='channel:other',ownership_relationship_id='owner:other');comm['channels'].append(channel)
    comm['batch']['claims'][1]['account_id']='channel:other'
    comm['batch']['reservations'][0]['account_id']='channel:other'
    comm['demands'][1]['channel_asset_id']='network:other'
    provenance=dict(origin='authored',source_refs=[],assumption_refs=[])
    inputs['entities'].extend([dict(id='channel:other',entity_kind='account',label='Other channel',provenance=provenance),dict(id='network:other',entity_kind='asset',label='Other network',provenance=provenance)])
    relation=deepcopy(next(r for r in inputs['relationships'] if r['id']=='message:owner'));relation.update(id='owner:other',to_id='network:other');inputs['relationships'].append(relation)
    result=run(data)
    assert messages(result)==data['expected']['messages']
    assert balances(result)=={'channel':'2','channel:other':'4','verification':'0'}


def test_decimal_context_does_not_change_independent_budgets():
    from decimal import localcontext
    expected=run()
    with localcontext() as context:
        context.prec=2
        assert run()==expected


@pytest.mark.parametrize('mutation',['forged_dto','wrong_units','policy_units','payload'])
def test_host_inputs_are_revalidated_and_no_payload_interface_added(mutation):
    from poliscope_engine.numeric import Registry,Unit
    from decimal import Decimal
    data=fixture()
    if mutation=='payload':
        data['request']['communication']['demands'][0]['payload']='private application data'
        with pytest.raises(ValidationError):run(data)
        return
    r,i,g,u=setup(data);m=policy_registry(units=u,reviews=reviews())
    if mutation=='forged_dto':
        r.communication.demands[0].__dict__['delay_ticks']=-1
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u,mechanisms=m)
    else:
        changed=Registry(tuple(Unit(x.id,(('time',1),) if mutation=='wrong_units' and x.id=='messages' else x.dimension,x.kind,x.scale*Decimal(2) if mutation=='policy_units' else x.scale) for x in u.units))
        if mutation=='wrong_units':m=policy_registry(units=changed,reviews=reviews())
        with pytest.raises(AccountError,match='invalid_communication_capacity|policy_units'):
            evaluate_pair(r,graph=g,units=changed,mechanisms=m)
