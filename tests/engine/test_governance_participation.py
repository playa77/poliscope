"""Real DOM-03/11 composition with independent finite-book and accommodation prerequisites."""


from copy import deepcopy


from dataclasses import replace


from fractions import Fraction


import pytest


from pydantic import ValidationError


from poliscope_engine.accounts import AccountError


from poliscope_engine.contracts.governance_participation import GovernanceParticipationRequest


from poliscope_engine.contracts.revisions import RevisionInputs


from poliscope_engine.contracts.world import LabelValue


from poliscope_engine.domains import ConformanceError


from poliscope_engine.domains.conformance import ConformanceCase


from poliscope_engine.domains.governance.participation import evaluate_pair, binding


from poliscope_engine.domains.governance.participation_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)


from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest


from governance_participation_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-governance-participation',
        'oracle:governance-participation-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['participation']['demands'][0]['access']='denied'
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
    assert reg.bind(('authored:gp-administration-mechanism','v1'),('authored:gp-participation-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['participation']['demands'][0]['access']='denied';r=GovernanceParticipationRequest.model_validate(data)
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
    work=callbacks['authored:gp-administration'];consumer=callbacks['authored:gp-participation']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.participation.demands[0] = r.participation.demands[0].model_copy(update={'access':'denied'})
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})


@pytest.mark.parametrize('missing', ['administration','economy','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:gp-administration-mechanism',
        'economy':'authored:gp-participation-mechanism','policy':'authored:gp-policy-mechanism'}[missing]
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
    r.participation.demands[0] = r.participation.demands[0].model_copy(update={'access':'denied'});result.candidate.participation.postings.clear()
    assert result.request.participation.demands[0].access=='allowed'
    assert run().candidate.participation.postings


def test_replay_then_rejection_never_refunds_or_double_spends():
    first=run();data=fixture()
    data['request']['governance']['administration']['batch']=first.candidate.administration.model_dump()
    data['request']['participation']['batch']=first.candidate.participation.model_dump()
    second=run(data)
    assert second.candidate==first.candidate
    assert all(m.additional=='0' for m in second.participation.results)
    data['request']['governance']['approval']='unanimity'
    rejected=run(data)
    assert rejected.governance.outcome=='rejected' and rejected.candidate==first.candidate
    assert amounts(rejected)['ritual']==['3','0','0']


@pytest.mark.parametrize('selection',[None,'original','competing'])
def test_overlapping_authority_needs_explicit_selection(selection):
    data=fixture();gov=data['request']['governance'];competing=deepcopy(gov['bindings'][0])
    competing.update(id='competing',authority_id='region-authority',scope_id='region');gov['bindings'].append(competing)
    if selection is not None:
        gov['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='gp:permission',
            entity_id='food',operation='select',participant_ids=['proposal','competing'],
            selected_id='proposal' if selection=='original' else 'competing',source_refs=['authored:governance-participation-v1'])]
    result=run(data)
    if selection=='original':assert result.status=='resolved'
    else:
        assert result.status=='unresolved' and result.candidate is None
        assert result.governance.findings==(['institutional_conflict'] if selection is None else ['proposal_not_selected'])


@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('prerequisites','accommodation'),('payload','private')])
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
        assert amounts(result)['ritual'][1]==('2' if admin==3 else '0')


def test_decimal_context_does_not_change_independent_budgets():
    from decimal import localcontext
    expected=run()
    with localcontext() as context:
        context.prec=2
        assert run()==expected


def amounts(result):
    return {r.claim_id: [r.prior, r.additional, r.unmet] for r in result.participation.results}


def balances(result):
    return {a.account_id: a.closing for a in result.participation.allocation.accounts.accounts}


def test_literal_books_preserve_prior_holds_subtotals_and_voluntary_declarations():
    data=fixture(); before=deepcopy(data); result=run(data)
    assert result.status=='resolved' and result.governance.outcome=='approved'
    assert amounts(result)==data['expected']['participation']
    assert balances(result)==data['expected']['participation_closing']
    assert {a.account_id:a.closing for a in result.governance.administration.allocation.accounts.accounts}==data['expected']['administration_closing']
    assert result.candidate.administration==result.governance.administration.batch
    assert result.candidate.participation==result.participation.allocation.batch
    assert result.candidate.participation.reservations==result.request.participation.batch.reservations
    assert result.candidate.participation.subtotals==result.request.participation.batch.subtotals
    assert result.participation.request==result.request.participation
    assert data==before and run(data)==result
    result.candidate.participation.postings.clear();result.candidate.administration.postings.clear()
    assert result.participation.allocation.batch.postings and result.governance.administration.batch.postings


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_independent_integer_feasible_sets_for_finite_accommodation_capacity(procedure):
    # One prior slot for A, two reserved for B. Priority is lexicographic over
    # feasible integer allocations; all-or-nothing requires each remaining claim.
    for supply in range(3,10):
        for first in range(1,5):
            for second in range(1,5):
                data=fixture();p=data['request']['participation'];p['procedure']=procedure
                p['batch']['accounts'][0]['opening']=str(supply)
                p['batch']['claims'][0]['requested']=str(first+1)
                p['batch']['claims'][1]['requested']=str(second)
                p['batch']['reservations'][0]['amount']=str(min(2,second))
                for demand in p['demands']:demand['access_limit']='9'
                reserve=min(2,second)
                feasible=[(a,b) for a in range(first+1) for b in range(second+1)
                    if 1+a+b<=supply and a<=supply-1-reserve
                    and (procedure=='priority' or a in (0,first) and b in (0,second))]
                a,b=max(feasible);result=run(data)
                assert amounts(result)=={'ritual':['1',str(a),str(first-a)],'meeting':['0',str(b),str(second-b)]}
                assert Fraction(balances(result)['hall'])+1+a+b==supply


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
    assert amounts(result)['ritual']==(['1','2','0'] if allowed else ['1','0','2'])
    assert amounts(result)['meeting']==(['0','2','1'] if allowed else ['0','3','0'])
    assert result.participation.request.demands[0].access==('allowed' if allowed else 'denied')
    assert result.request.participation.demands[0].access=='allowed'


@pytest.mark.parametrize('field',['participation','eligibility','access','obligation_status','conflict','availability','procedure'])
@pytest.mark.parametrize('approved',[True,False])
def test_unknowns_and_obligation_conflict_remain_unresolved_under_any_decision(field,approved):
    data=fixture();p=data['request']['participation']
    if not approved:data['request']['governance']['approval']='unanimity'
    if field=='availability':p['facilities'][0][field]='unknown'
    elif field=='procedure':p[field]=None
    elif field=='conflict':p['demands'][0]['obligation_status']='conflict'
    else:p['demands'][0][field]='unknown'
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None
    assert result.preflight.status=='unresolved' and result.participation.status=='unresolved'
    assert result.participation.allocation.batch==result.request.participation.batch
    assert all(r.additional is None and r.unmet is None for r in result.participation.results)
    if field=='conflict':assert 'obligation_conflict' in result.participation.results[0].findings


@pytest.mark.parametrize('missing',['ballot','approval','policy','access','terms','procedure'])
def test_unknown_decision_retains_preflight_without_candidate(missing):
    data=fixture();gov=data['request']['governance']
    if missing=='ballot':gov['ballots'][0]['vote']='unknown'
    elif missing=='approval':gov['approval']=None
    elif missing=='policy':gov['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='access':gov['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='terms':gov['administration']['activities'][0]['terms_known']=False
    else:gov['administration']['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None and result.participation is None
    assert result.preflight.status=='resolved' and result.preflight.results[0].additional=='2'
    assert result.request.participation.batch.model_dump()['postings']==data['request']['participation']['batch']['postings']


@pytest.mark.parametrize('field,value,finding',[
    ('participation','declined','participation_declined'),('eligibility','ineligible','eligibility_ineligible'),
    ('access','denied','access_denied'),('access_relationship_id',None,'no_declared_access'),
    ('availability','offline','facility_offline'),('access_limit','1','access_limit_shortfall')])
def test_approval_preserves_original_restrictions(field,value,finding):
    data=fixture();p=data['request']['participation']
    if field=='availability':p['facilities'][0][field]=value
    else:p['demands'][0][field]=value
    result=run(data)
    assert result.governance.outcome=='approved' and result.status=='resolved'
    assert result.participation.request==result.request.participation
    assert finding in result.participation.results[0].findings
    assert amounts(result)['ritual'][1]==('1' if field=='access_limit' else '0')


@pytest.mark.parametrize('mutation,code',[
    ('period','period_mismatch'),('scope','scope_mismatch'),('missing','invalid_decision_participation_mapping'),
    ('duplicate','invalid_decision_participation_mapping'),('foreign','invalid_decision_participation_mapping'),
    ('target','affected_mapping'),('affected','affected_mapping'),('independent_target','independent_target'),
    ('foreign_account','account_identity'),('foreign_claimant','claimant_identity'),('foreign_holder','holder_identity'),
    ('missing_holder','time_holders'),('overlap','overlapping_books'),('claim_overlap','overlapping_books'),
    ('subtotal_overlap','overlapping_books'),('ownership','invalid_participation_authority'),
    ('reach','invalid_participation_access_reference'),('account_period','period_mismatch'),
    ('claimant','invalid_participation_claim'),('missing_obligation','missing_participation_obligation_reference'),
    ('duplicate_facility','duplicate_or_unmapped_participation_capacity'),('wrong_units','invalid_participation_capacity')])
def test_invalid_original_context_rejected_even_with_unknown_decision(mutation,code):
    data=fixture();gov=data['request']['governance'];p=data['request']['participation']
    gov['ballots'][0]['vote']='unknown'
    if mutation=='period':p['period_id']='day:1'
    elif mutation=='scope':p['scope_id']='west'
    elif mutation=='missing':data['request']['prerequisites'].pop()
    elif mutation=='duplicate':data['request']['prerequisites']*=2
    elif mutation=='foreign':data['request']['prerequisites'][0]['claim_id']='foreign'
    elif mutation=='target':data['request']['prerequisites'][0]['decision_target_id']='water'
    elif mutation=='affected':gov['bindings'][0]['account_refs'].remove('hall')
    elif mutation=='independent_target':data['request']['prerequisites'][1]['decision_target_id']='food'
    elif mutation=='foreign_account':p['batch']['accounts'][0]['id']='foreign'
    elif mutation=='foreign_claimant':gov['administration']['batch']['claims'][0]['claimant_id']='foreign'
    elif mutation=='foreign_holder':gov['administration']['holders'][0]['holder_id']='foreign'
    elif mutation=='missing_holder':gov['administration']['holders'].pop(0)
    elif mutation=='overlap':gov['administration']['batch']['accounts'].append(deepcopy(p['batch']['accounts'][0]))
    elif mutation=='claim_overlap':p['batch']['claims'][0]['id']='admin'
    elif mutation=='subtotal_overlap':p['batch']['subtotals'][0]['id']='east:stock-view'
    elif mutation=='ownership':p['facilities'][0]['ownership_relationship_id']='participation:access:ritual'
    elif mutation=='reach':p['demands'][0]['access_relationship_id']='participation:access:meeting'
    elif mutation=='account_period':p['batch']['accounts'][0]['period_id']='day:1'
    elif mutation=='claimant':p['batch']['claims'][0]['claimant_id']='cohort:b'
    elif mutation=='missing_obligation':p['demands'][0].update(obligation_status='conflict',obligation_refs=[])
    elif mutation=='duplicate_facility':p['facilities']*=2
    else:p['batch']['accounts'][0]['unit_id']='hours'
    with pytest.raises((AccountError,ValidationError),match=code):run(data)


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
        next(r for r in data['inputs']['relationships'] if r['id']=='participation:owner')['from_id']=authority
        relation=deepcopy(next(r for r in data['inputs']['relationships'] if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority'))
        relation.update(id='scope:jurisdiction',from_id=authority,to_id=scope);data['inputs']['relationships'].append(relation)
    assert run(data).status=='resolved'


def test_explicit_reverse_queue_shares_capacity_and_retains_prior():
    data=fixture();data['request']['participation']['claim_order'].reverse()
    result=run(data)
    assert amounts(result)=={'ritual':['1','1','1'],'meeting':['0','3','0']}
    assert balances(result)=={'hall':'0'}


@pytest.mark.parametrize('mutation',['forged_dto','policy_units','payload'])
def test_host_revalidates_nested_contracts_and_policy_units(mutation):
    from poliscope_engine.numeric import Registry,Unit
    from decimal import Decimal
    data=fixture()
    if mutation=='payload':
        data['request']['participation']['demands'][0]['payload']='private'
        with pytest.raises(ValidationError):run(data)
        return
    r,i,g,u=setup(data);m=policy_registry(units=u,reviews=reviews())
    if mutation=='forged_dto':
        r.participation.demands[0].__dict__['participation']='forced'
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u,mechanisms=m)
    else:
        changed=Registry(tuple(Unit(x.id,x.dimension,x.kind,x.scale*Decimal(2)) for x in u.units))
        with pytest.raises(AccountError,match='policy_units'):evaluate_pair(r,graph=g,units=changed,mechanisms=m)
