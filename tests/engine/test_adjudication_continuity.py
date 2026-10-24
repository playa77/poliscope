"""Real DOM-04/12 composition with independent finite-book and continuity prerequisites."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.adjudication_continuity import AdjudicationContinuityRequest
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.law_conflict.continuity import evaluate_pair, binding
from poliscope_engine.domains.law_conflict.continuity_counterpart import (
    host_registry, policy_registry, run_bound_case, definitions, MODEL,
    CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError, Review, declaration_digest
from adjudication_continuity_fixture import fixture, setup, trusted


def reviews():
    return [Review(declaration_digest(d), *MODEL,
        'sv:WP-032-counterparts-adjudication-continuity',
        'oracle:adjudication-continuity-literal-v1') for d in definitions()]


def run(data=None):
    request, _, graph, units = setup(data)
    return evaluate_pair(request, graph=graph, units=units,
        mechanisms=policy_registry(units=units, reviews=reviews()))


def allocations(result):
    return {r.claim_id: [r.prior,r.additional,r.unmet] for r in result.continuity.results}


def balances(result):
    return {a.account_id:a.closing for a in result.continuity.allocation.accounts.accounts}


def test_complete_context_digest_changes_for_request_world_units_and_review():
    r,i,g,u=setup();m=policy_registry(units=u,reviews=reviews());original=binding(r,g,u,m)
    data=fixture();data['request']['continuity']['demands'][0]['access']='denied'
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
    assert reg.bind(('authored:ak-administration-mechanism','v1'),('authored:ak-continuity-mechanism','v1'),
        output_id=WORK,input_id=BOOK,world=g.registry,scope_id='east',
        producer_entity_id='east-authority',consumer_entity_id='east-authority').kind=='label'


@pytest.mark.parametrize('change', ['request','world','version','review'])
def test_bound_case_rejects_stale_context(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);rs=reg.reviews
    if change=='request':
        data=r.model_dump();data['continuity']['demands'][0]['access']='denied';r=AdjudicationContinuityRequest.model_validate(data)
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
    work=callbacks['authored:ak-administration'];consumer=callbacks['authored:ak-continuity']
    context=binding(r,g,u,policy_registry(units=u,reviews=reg.reviews))
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    r.continuity.demands[0] = r.continuity.demands[0].model_copy(update={'access':'denied'})
    assert work(WORK,{CONTEXT:LabelValue(kind='label',value=context)})==token
    assert consumer(CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='label'
    with pytest.raises(AccountError,match='stale_counterpart_book'):
        consumer(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_context'):
        work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})


@pytest.mark.parametrize('missing', ['administration','continuity','policy'])
def test_each_review_is_required_not_granted_by_catalog(missing):
    r,i,g,u=setup()
    omit={'administration':'authored:ak-administration-mechanism',
        'continuity':'authored:ak-continuity-mechanism','policy':'authored:ak-policy-mechanism'}[missing]
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
    r.continuity.demands[0] = r.continuity.demands[0].model_copy(update={'access':'denied'});result.candidate.continuity.postings.clear()
    assert result.request.continuity.demands[0].access=='allowed'
    assert run().candidate.continuity.postings


def test_literal_finite_books_detach_prior_holds_subtotals_and_obligations():
    data=fixture();before=deepcopy(data);result=run(data)
    assert result.status=='resolved' and result.adjudication.results[0].outcome=='upheld'
    assert balances(result)==data['expected']['continuity_closing']
    assert allocations(result)==data['expected']['continuity']
    assert {a.account_id:a.closing for a in result.adjudication.administration.evaluation.allocation.accounts.accounts}==data['expected']['administration_closing']
    assert result.candidate.administration==result.adjudication.administration.evaluation.batch
    assert result.candidate.continuity==result.continuity.allocation.batch
    assert result.candidate.continuity.reservations==result.request.continuity.batch.reservations
    assert result.candidate.continuity.subtotals==result.request.continuity.batch.subtotals
    assert result.continuity.request.demands[0].obligation_refs==['synthetic:obligation:preparedness']
    assert data==before and run(data)==result
    result.candidate.continuity.postings.clear()
    result.candidate.administration.postings.clear()
    assert result.continuity.allocation.batch.postings
    assert result.adjudication.administration.evaluation.batch.postings


@pytest.mark.parametrize('outcome',['upheld','dismissed','ineligible','capacity_blocked'])
@pytest.mark.parametrize('independent',[False,True])
def test_only_explicit_dependent_new_allocations_are_restricted(outcome,independent):
    data=fixture();legal=data['request']['adjudication'];case=legal['cases'][0]
    if outcome=='dismissed':case['disposition']='dismissed'
    elif outcome=='ineligible':case['eligibility']='ineligible'
    elif outcome=='capacity_blocked':legal['administration']['activities'][0]['access_limit']='1'
    data['request']['prerequisites'][0]['case_id']=None if independent else 'case:continuity'
    result=run(data);allowed=independent or outcome=='upheld'
    assert result.status=='resolved' and result.adjudication.results[0].outcome==outcome
    assert allocations(result)['preparedness']==(['1','2','0'] if allowed else ['1','0','2'])
    assert allocations(result)['ordinary']==(['0','2','1'] if allowed else ['0','3','0'])
    assert result.continuity.request.demands[0].access==('allowed' if allowed else 'denied')
    assert result.request.continuity.demands[0].access=='allowed'


@pytest.mark.parametrize('missing',['eligibility','disposition','rationale','rights','policy','access','terms','procedure'])
def test_unknown_case_retains_preflight_but_no_candidate(missing):
    data=fixture();legal=data['request']['adjudication'];case=legal['cases'][0]
    if missing=='eligibility':case['eligibility']='unknown'
    elif missing=='disposition':case['disposition']=None
    elif missing=='rationale':case['rationale']=None
    elif missing=='rights':case['incompatible_right_refs']=['synthetic:competing-right']
    elif missing=='policy':legal['bindings'][0]['value']=dict(kind='unknown',reason='missing')
    elif missing=='access':legal['administration']['activities'][0]['eligibility']='unknown'
    elif missing=='terms':legal['administration']['activities'][0]['terms_known']=False
    else:legal['administration']['procedure']=None
    result=run(data)
    assert result.status=='unresolved' and result.candidate is None and result.continuity is None
    assert result.preflight.status=='resolved' and result.preflight.results[0].additional=='2'
    assert result.request.continuity.batch.model_dump()['postings']==data['request']['continuity']['batch']['postings']


def test_replay_then_dismissal_never_refunds_or_double_spends():
    first=run();data=fixture()
    data['request']['adjudication']['administration']['batch']=first.candidate.administration.model_dump()
    data['request']['continuity']['batch']=first.candidate.continuity.model_dump()
    second=run(data)
    assert second.candidate==first.candidate
    assert all(m.additional=='0' for m in second.continuity.results)
    data['request']['adjudication']['cases'][0]['disposition']='dismissed'
    rejected=run(data)
    assert rejected.adjudication.results[0].outcome=='dismissed' and rejected.candidate==first.candidate
    assert allocations(rejected)['preparedness']==['3','0','0']


@pytest.mark.parametrize('selection',[None,'original','competing'])
def test_overlapping_authority_needs_explicit_selection(selection):
    data=fixture();legal=data['request']['adjudication'];competing=deepcopy(legal['bindings'][0])
    competing.update(id='competing',authority_id='region-authority',scope_id='region');legal['bindings'].append(competing)
    if selection is not None:
        legal['rules']=[dict(contract_version=1,identity=dict(id='synthetic:select',version='v1'),
            authority_id='region-authority',scope_id='region',parameter_id='ak:permission',
            entity_id='response:asset',operation='select',participant_ids=['proposal','competing'],
            selected_id='proposal' if selection=='original' else 'competing',source_refs=['authored:adjudication-continuity-v1'])]
    result=run(data)
    if selection=='original':assert result.status=='resolved'
    else:
        assert result.status=='unresolved' and result.candidate is None
        assert result.adjudication.results[0].findings==(['institutional_conflict'] if selection is None else ['adjudication_binding_not_selected'])


@pytest.mark.parametrize('field,value',[('contract_version',2),('prerequisites',[]),('prerequisites','continuity'),('payload','private')])
def test_private_contract_strict(field,value):
    data=fixture();data['request'][field]=value
    with pytest.raises(ValidationError):run(data)


def test_duplicate_dated_time_pool_rejected():
    data=fixture();work=data['request']['adjudication']['administration']
    account=deepcopy(next(a for a in work['batch']['accounts'] if a['id']=='labor'));account['id']='labor:duplicate';work['batch']['accounts'].append(account)
    work['holders'].append(dict(account_id='labor:duplicate',holder_id='shared:cohort',role='time'))
    data['inputs']['entities'].append(dict(id='labor:duplicate',entity_kind='account',label='Invalid duplicate time',provenance=dict(origin='authored',source_refs=[],assumption_refs=[])))
    with pytest.raises(AccountError,match='duplicate.*time|time.*duplicate'):run(data)


@pytest.mark.parametrize('procedure',['priority','all_or_nothing'])
def test_administration_uses_one_dated_time_book_with_competing_prior_care(procedure):
    for time in range(4,17):
        data=fixture();work=data['request']['adjudication']['administration']
        next(a for a in work['batch']['accounts'] if a['id']=='labor')['opening']=str(time)
        work['procedure']=procedure
        # These enumerate total fulfilled work, including each prior hour.
        admin=max(a for a in range(1,4) if a+2<=time and (procedure=='priority' or a in (1,3)))
        care=max(c for c in range(1,4) if admin+c<=time and (procedure=='priority' or c in (1,3)))
        result=run(data);accounts=result.adjudication.administration.evaluation.allocation.accounts
        assert {c.claim_id:c.actual for c in accounts.claims if c.claim_id in ('admin','care')}=={'admin':str(admin),'care':str(care)}
        assert Fraction(next(a.closing for a in accounts.accounts if a.account_id=='labor'))+admin+care==time
        assert result.adjudication.results[0].outcome==('upheld' if admin==3 else 'capacity_blocked')
        assert allocations(result)['preparedness'][1]==('2' if admin==3 else '0')


def test_explicit_reversed_queue_competes_in_same_finite_continuity_book():
    data=fixture();data['request']['continuity']['claim_order'].reverse()
    result=run(data)
    assert allocations(result)=={'preparedness':['1','1','1'],'ordinary':['0','3','0']}
    assert balances(result)=={'response':'0'}


def test_decimal_context_does_not_change_independent_budgets():
    from decimal import localcontext
    expected=run()
    with localcontext() as context:
        context.prec=2
        assert run()==expected


def two_cases():
    data=fixture();legal=data['request']['adjudication'];comm=data['request']['continuity']
    # Two independently declared findings for allocations competing for the same
    # continuity slots; no case/identifier order chooses a winner.
    second=deepcopy(legal['cases'][0]);second.update(id='case:second',work_claim_ids=['training'])
    legal['cases'].append(second)
    activity=next(a for a in legal['administration']['activities'] if a['claim_id']=='training')
    activity.update(kind='participation',eligibility='allowed',access_limit='3')
    comm['batch']['claims'][1]['claimant_id']='shared:cohort'
    comm['demands'][1].update(group_id='shared:cohort',access_relationship_id='continuity:access:preparedness')
    second['obligation_refs']=['synthetic:obligation:ordinary']
    data['request']['prerequisites'][1]['case_id']='case:second'
    return data


@pytest.mark.parametrize('first',['upheld','dismissed'])
@pytest.mark.parametrize('second',['upheld','dismissed'])
def test_case_specific_outcomes_do_not_gate_unrelated_allocations(first,second):
    data=two_cases();legal=data['request']['adjudication']
    legal['cases'][0]['disposition']=first;legal['cases'][1]['disposition']=second
    result=run(data)
    a=2 if first=='upheld' else 0
    b=min(3,4-a) if second=='upheld' else 0
    assert result.status=='resolved'
    assert allocations(result)=={'preparedness':['1',str(a),str(2-a)],'ordinary':['0',str(b),str(3-b)]}
    assert [r.outcome for r in result.adjudication.results]==[first,second]
    assert Fraction(balances(result)['response'])+1+a+b==5
    assert {a.account_id:a.closing for a in result.adjudication.administration.evaluation.allocation.accounts.accounts}['labor']=='3'


@pytest.mark.parametrize('field',['disposition','incompatible_right_refs'])
def test_one_unresolved_case_withholds_entire_candidate(field):
    data=two_cases();case=data['request']['adjudication']['cases'][1]
    case[field]=None if field=='disposition' else ['synthetic:conflicting-right']
    result=run(data)
    assert result.adjudication.results[0].outcome=='upheld'
    assert result.adjudication.results[1].outcome is None
    assert result.status=='unresolved' and result.candidate is None
    assert result.continuity is None and result.preflight.status=='resolved'


@pytest.mark.parametrize('mutation',['missing_obligation','wrong_binding','wrong_parameter','missing_jurisdiction','duplicate_case_work'])
def test_case_terms_and_authority_cannot_be_bypassed(mutation):
    data=two_cases();legal=data['request']['adjudication'];case=legal['cases'][0]
    if mutation=='missing_obligation':case['obligation_refs']=[]
    elif mutation=='wrong_binding':case['binding_id']='foreign'
    elif mutation=='wrong_parameter':case['parameter_id']='foreign'
    elif mutation=='missing_jurisdiction':
        data['inputs']['relationships']=[r for r in data['inputs']['relationships'] if r['relationship_kind']!='jurisdiction']
    else:legal['cases'][1]['work_claim_ids']=['admin']
    with pytest.raises(AccountError,match='affected_mapping|invalid_adjudication_binding|missing_adjudication_jurisdiction|duplicate_case_work'):
        run(data)


def test_unresolved_continuity_host_cannot_return_complete_candidate():
    data=fixture();data['request']['continuity']['demands'][0]['access']='unknown'
    request,inputs,graph,units=setup(data);registry,_=trusted(request,inputs,graph,units)
    callbacks={i.id:i.callback for i in registry.implementations}
    context=binding(request,graph,units,policy_registry(units=units,reviews=registry.reviews))
    token=callbacks['authored:ak-administration'](WORK,{CONTEXT:LabelValue(kind='label',value=context)})
    assert token['kind']=='label'
    assert callbacks['authored:ak-continuity'](CANDIDATE,{BOOK:LabelValue.model_validate(token)})['kind']=='unknown'


@pytest.mark.parametrize('procedure', ['priority', 'all_or_nothing'])
def test_independent_integer_feasible_sets_with_prior_use_and_protected_hold(procedure):
    # A needs 2 new slots, B needs 3 with a protected 2-slot hold.
    # Exhaust the feasible integer assignments independently of the allocator.
    for capacity in range(3, 10):
        data = fixture()
        continuity = data['request']['continuity']
        continuity['procedure'] = procedure
        continuity['batch']['accounts'][0]['opening'] = str(capacity)
        a = max(x for x in range(3) if 1+x+2 <= capacity
                and (procedure == 'priority' or x in (0, 2)))
        b = max(x for x in range(4) if 1+a+x <= capacity
                and (procedure == 'priority' or x in (0, 3)))
        result = run(data)
        assert allocations(result) == {'preparedness': ['1', str(a), str(2-a)],
                                       'ordinary': ['0', str(b), str(3-b)]}
        assert Fraction(balances(result)['response']) + 1+a+b == capacity


@pytest.mark.parametrize('field', ['participation', 'eligibility', 'access', 'obligation_status', 'availability', 'procedure'])
@pytest.mark.parametrize('upheld', [True, False])
def test_unknown_continuity_inputs_never_become_known_by_legal_restriction(field, upheld):
    data = fixture()
    part = data['request']['continuity']
    if not upheld:
        data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    if field == 'availability':
        part['facilities'][0][field] = 'unknown'
    elif field == 'procedure':
        part[field] = None
    else:
        part['demands'][0][field] = 'unknown'
    result = run(data)
    assert result.status == result.preflight.status == result.continuity.status == 'unresolved'
    assert result.candidate is None
    assert result.continuity.allocation.batch == result.request.continuity.batch
    assert all(r.additional is None and r.unmet is None for r in result.continuity.results)


@pytest.mark.parametrize('field,value', [('participation', 'declined'), ('eligibility', 'ineligible'),
    ('access', 'denied'), ('access_relationship_id', None), ('availability', 'offline')])
@pytest.mark.parametrize('upheld', [True, False])
def test_legal_findings_never_override_original_voluntary_choice_or_restrictions(field, value, upheld):
    data = fixture()
    part = data['request']['continuity']
    if not upheld:
        data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    target = part['facilities'][0] if field == 'availability' else part['demands'][0]
    target[field] = value
    result = run(data)
    assert result.status == 'resolved'
    assert allocations(result)['preparedness'] == ['1', '0', '2']
    assert result.continuity.request.demands[0].participation == part['demands'][0]['participation']
    assert result.continuity.request.demands[0].eligibility == part['demands'][0]['eligibility']


@pytest.mark.parametrize('upheld', [True, False])
def test_conflicting_obligations_withhold_candidate_even_after_legal_outcome(upheld):
    data = fixture()
    data['request']['continuity']['demands'][0]['obligation_status'] = 'conflict'
    if not upheld:
        data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    result = run(data)
    assert result.candidate is None and result.status == 'unresolved'
    assert 'obligation_conflict' in result.continuity.results[0].findings


@pytest.mark.parametrize('mutation,code', [
    ('period','period_mismatch'), ('scope','scope_mismatch'), ('missing','invalid_adjudication_continuity_mapping'),
    ('duplicate','invalid_adjudication_continuity_mapping'), ('foreign','invalid_adjudication_continuity_mapping'),
    ('target','affected_mapping'), ('affected','affected_mapping'), ('claimant','affected_mapping'),
    ('authority','affected_mapping'), ('obligations','affected_mapping'), ('unknown_case','affected_mapping'),
    ('foreign_account','account_identity'), ('foreign_claimant','claimant_identity'), ('foreign_holder','holder_identity'),
    ('missing_holder','time_holders'), ('overlap','overlapping_books'), ('claim_overlap','overlapping_books'),
    ('subtotal_overlap','overlapping_books'), ('ownership','invalid_continuity_authority'),
    ('reach','invalid_continuity_access_reference'), ('account_period','period_mismatch'),
])
def test_invalid_original_context_rejected_even_when_case_unresolved(mutation, code):
    data=fixture();legal=data['request']['adjudication'];part=data['request']['continuity']
    legal['cases'][0]['disposition']=None
    if mutation=='period':part['period_id']='day:1'
    elif mutation=='scope':part['scope_id']='west'
    elif mutation=='missing':data['request']['prerequisites'].pop()
    elif mutation=='duplicate':data['request']['prerequisites']*=2
    elif mutation=='foreign':data['request']['prerequisites'][0]['claim_id']='foreign'
    elif mutation=='target':legal['cases'][0]['target_id']='food'
    elif mutation=='affected':legal['bindings'][0]['account_refs'].remove('response')
    elif mutation=='claimant':legal['cases'][0]['claimant_id']='region-authority'
    elif mutation=='authority':legal['cases'][0]['authority_id']='region-authority'
    elif mutation=='obligations':part['demands'][0]['obligation_refs']=[]
    elif mutation=='unknown_case':data['request']['prerequisites'][0]['case_id']='foreign'
    elif mutation=='foreign_account':part['batch']['accounts'][0]['id']='foreign'
    elif mutation=='foreign_claimant':legal['administration']['batch']['claims'][0]['claimant_id']='foreign'
    elif mutation=='foreign_holder':legal['administration']['holders'][0]['holder_id']='foreign'
    elif mutation=='missing_holder':legal['administration']['holders'].pop(0)
    elif mutation=='overlap':legal['administration']['batch']['accounts'].append(deepcopy(part['batch']['accounts'][0]))
    elif mutation=='claim_overlap':part['batch']['claims'][0]['id']='admin'
    elif mutation=='subtotal_overlap':part['batch']['subtotals'][0]['id']='east:stock-view'
    elif mutation=='ownership':part['facilities'][0]['ownership_relationship_id']='continuity:access:preparedness'
    elif mutation=='reach':part['demands'][0]['access_relationship_id']='continuity:access:ordinary'
    else:part['batch']['accounts'][0]['period_id']='day:1'
    with pytest.raises((AccountError,ValidationError),match=code):run(data)


@pytest.mark.parametrize('mutation', ['forged_dto', 'wrong_units', 'policy_units', 'payload'])
def test_host_revalidates_dtos_units_and_private_boundary(mutation):
    from poliscope_engine.numeric import Registry, Unit
    from decimal import Decimal
    data = fixture()
    if mutation == 'payload':
        data['request']['continuity']['demands'][0]['payload'] = 'private application data'
        with pytest.raises(ValidationError):run(data)
        return
    r,i,g,u=setup(data);m=policy_registry(units=u,reviews=reviews())
    if mutation == 'forged_dto':
        r.continuity.demands[0].__dict__['participation']='mandatory'
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u,mechanisms=m)
    else:
        changed=Registry(tuple(Unit(x.id,(('time',1),) if mutation=='wrong_units' and x.id=='continuity' else x.dimension,
            x.kind,x.scale*Decimal(2) if mutation=='policy_units' else x.scale) for x in u.units))
        if mutation=='wrong_units':m=policy_registry(units=changed,reviews=reviews())
        with pytest.raises(AccountError,match='invalid_continuity_capacity|policy_units'):
            evaluate_pair(r,graph=g,units=changed,mechanisms=m)


@pytest.mark.parametrize('scope', ['east', 'west', 'region'])
def test_actual_local_and_regional_scope(scope):
    import json
    data=fixture()
    if scope!='east':
        authority='region-authority' if scope=='region' else 'west-authority'
        if scope=='west':
            entity=deepcopy(next(e for e in data['inputs']['entities'] if e['id']=='east-authority'))
            entity['id']=authority;data['inputs']['entities'].append(entity)
        data['request']=json.loads(json.dumps(data['request']).replace('"east"',f'"{scope}"').replace('"east-authority"',f'"{authority}"'))
        next(r for r in data['inputs']['relationships'] if r['id']=='continuity:owner')['from_id']=authority
        relation=deepcopy(next(r for r in data['inputs']['relationships'] if r['relationship_kind']=='jurisdiction' and r['from_id']=='east-authority'))
        relation.update(id='scope:jurisdiction',from_id=authority,to_id=scope)
        data['inputs']['relationships'].append(relation)
    assert run(data).status=='resolved'


def test_separate_facility_keeps_independent_capacity_without_duplicating_legal_work():
    data=fixture();part=data['request']['continuity'];inputs=data['inputs']
    account=deepcopy(part['batch']['accounts'][0]);account.update(id='response:other',opening='3')
    part['batch']['accounts'].append(account)
    facility=deepcopy(part['facilities'][0]);facility.update(asset_id='response:other:asset',account_id='response:other',ownership_relationship_id='owner:other')
    part['facilities'].append(facility)
    part['batch']['claims'][1]['account_id']='response:other'
    part['batch']['reservations'][0]['account_id']='response:other'
    part['demands'][1].update(facility_asset_id='response:other:asset',access_relationship_id='access:other')
    provenance=dict(origin='authored',source_refs=[],assumption_refs=[])
    inputs['entities'].extend([dict(id='response:other',entity_kind='account',label='Other slots',provenance=provenance),dict(id='response:other:asset',entity_kind='asset',label='Other facility',provenance=provenance)])
    for original,new in [('continuity:owner','owner:other'),('continuity:access:ordinary','access:other')]:
        relation=deepcopy(next(r for r in inputs['relationships'] if r['id']==original))
        relation.update(id=new,to_id='response:other:asset');inputs['relationships'].append(relation)
    result=run(data)
    assert allocations(result)=={'preparedness':['1','2','0'],'ordinary':['0','3','0']}
    assert balances(result)=={'response':'2','response:other':'0'}
    assert {a.account_id:a.closing for a in result.adjudication.administration.evaluation.allocation.accounts.accounts}['labor']=='6'


@pytest.mark.parametrize('field', ['vulnerability', 'authority', 'disclosure', 'aid_condition'])
@pytest.mark.parametrize('upheld', [True, False])
def test_continuity_unknowns_survive_legal_findings(field, upheld):
    data = fixture()
    # Conditional aid belongs to an explicitly external finite facility.
    if field == 'aid_condition':
        for facility in data['request']['continuity']['facilities']:
            facility['origin'] = 'external'
        for demand in data['request']['continuity']['demands']:
            demand['purpose'] = 'external_aid'
    data['request']['continuity']['demands'][0][field] = 'unknown'
    if not upheld:
        data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    result = run(data)
    assert result.status == result.preflight.status == result.continuity.status == 'unresolved'
    assert result.candidate is None
    assert result.continuity.request.demands[0].model_dump()[field] == 'unknown'
    assert 'unknown_' + field in result.continuity.results[0].findings
    assert result.continuity.allocation.batch == result.request.continuity.batch


@pytest.mark.parametrize('field,value,finding', [
    ('authority', 'delayed', 'authority_delayed'),
    ('authority', 'denied', 'authority_denied'),
    ('disclosure', 'withheld', 'disclosure_withheld'),
    ('aid_condition', 'unavailable', 'aid_condition_unavailable'),
])
@pytest.mark.parametrize('upheld', [True, False])
def test_legal_outcomes_preserve_distinct_continuity_restrictions(field, value, finding, upheld):
    data = fixture()
    if field == 'aid_condition':
        data['request']['continuity']['facilities'][0]['origin'] = 'external'
        for demand in data['request']['continuity']['demands']:
            demand['purpose'] = 'external_aid'
    data['request']['continuity']['demands'][0][field] = value
    if not upheld:
        data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    result = run(data)
    assert result.status == 'resolved'
    assert allocations(result)['preparedness'] == ['1', '0', '2']
    assert finding in result.preflight.results[0].findings
    assert finding in result.continuity.results[0].findings
    assert result.continuity.request.demands[0].model_dump()[field] == value


@pytest.mark.parametrize('mutation,code', [
    ('origin', 'invalid_continuity_aid_origin'),
    ('local_condition', 'invalid_continuity_local_aid_condition'),
    ('exposure', 'missing_continuity_exposure'),
])
@pytest.mark.parametrize('unknown_case', [False, True])
def test_original_risk_declarations_validate_before_any_legal_restriction(mutation, code, unknown_case):
    data = fixture()
    if unknown_case:
        data['request']['adjudication']['cases'][0]['disposition'] = None
    else:
        data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    demand = data['request']['continuity']['demands'][0]
    if mutation == 'origin': demand['purpose'] = 'external_aid'
    elif mutation == 'local_condition': demand['aid_condition'] = 'unavailable'
    else: demand['exposure_refs'] = []
    with pytest.raises(AccountError, match=code): run(data)


def test_finite_external_aid_replay_then_withdrawal_keeps_prior_capacity():
    data = fixture()
    data['request']['continuity']['facilities'][0]['origin'] = 'external'
    for demand in data['request']['continuity']['demands']:
        demand['purpose'] = 'external_aid'
    first = run(data)
    assert allocations(first) == {'preparedness': ['1', '2', '0'], 'ordinary': ['0', '2', '1']}
    assert balances(first) == {'response': '0'}
    data['request']['adjudication']['administration']['batch'] = first.candidate.administration.model_dump()
    data['request']['continuity']['batch'] = first.candidate.continuity.model_dump()
    for demand in data['request']['continuity']['demands']:
        demand['aid_condition'] = 'unavailable'
    data['request']['adjudication']['cases'][0]['disposition'] = 'dismissed'
    withdrawn = run(data)
    assert withdrawn.candidate == first.candidate
    assert allocations(withdrawn) == {'preparedness': ['3', '0', '0'], 'ordinary': ['2', '0', '1']}
    assert all('aid_condition_unavailable' in r.findings for r in withdrawn.continuity.results)
