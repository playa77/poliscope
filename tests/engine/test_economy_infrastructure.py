"""Actual facility prerequisites, independent finite slot/time/stock/rights oracles."""
from copy import deepcopy
from fractions import Fraction
import itertools
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.economy.infrastructure import evaluate_pair
from poliscope_engine.domains.economy.infrastructure_counterpart import (
    binding, host_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from economy_infrastructure_fixture import fixture, setup, trusted


def run(data=None):
    r, _, g, u = setup(data)
    return evaluate_pair(r, graph=g, units=u)


def case_for(inputs, status='partial'):
    return ConformanceCase(inputs=inputs, outcome='incomplete', observations=(
        dict(node=['output', 'economy', CANDIDATE], status=status),),
        trace_edges=((('output', 'work', WORK), ('input', 'economy', BOOK)),))


def actuals(result):
    return {c.claim_id: [c.actual, c.unmet] for c in result.economy.allocation.accounts.claims}


def test_literal_finite_books_are_pure_detached_and_repeatable():
    data = fixture(); before = deepcopy(data); result = run(data)
    assert data == before and result == run(data) and result.status == 'resolved'
    assert actuals(result) == data['expected']['claims']
    balances = {a.account_id: a.closing for a in result.economy.allocation.accounts.accounts}
    assert {k: balances[k] for k in data['expected']['closing']} == data['expected']['closing']
    assert {r.claim_id: r.additional for r in result.infrastructure.results} == {
        f'reach:{p}': '1' for p in ['make', 'deliver', 'store', 'eat']}
    assert {a.account_id: a.closing for a in result.infrastructure.allocation.accounts.accounts} == {
        a: '1' for a in ['depot:slots', 'bridge:slots', 'road:slots']}
    assert sum(p.id == 'prior:care' for p in result.batch.postings) == 1
    assert result.batch.reservations == result.request.economy.batch.reservations
    assert result.batch.subtotals == result.request.economy.batch.subtotals
    assert not {a.id for a in result.infrastructure.allocation.batch.accounts} & {a.id for a in result.batch.accounts}
    result.batch.postings.clear(); result.infrastructure.request.demands.clear()
    assert run().batch.postings and run().infrastructure.request.demands


@pytest.mark.parametrize('capacity', range(7))
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('procedure', ['priority', 'all_or_nothing'])
def test_independent_integer_slot_oracle_gates_economy(capacity, reverse, procedure):
    data = fixture(); infra = data['request']['infrastructure']
    next(a for a in infra['batch']['accounts'] if a['id'] == 'bridge:slots')['opening'] = str(capacity)
    infra['procedure'] = procedure
    if reverse: infra['claim_order'].reverse()
    # Independent lexicographic finite feasible set: all demands require one
    # facility, bridge and road slot; only bridge changes capacity in this case.
    order = infra['claim_order']
    feasible = [v for v in itertools.product(range(2), repeat=4) if sum(v) <= min(5, capacity)]
    chosen = max(feasible)
    expected = dict(zip(order, chosen))
    result = run(data)
    assert {r.claim_id: int(r.additional) for r in result.infrastructure.results} == expected
    training = 3 if expected['reach:deliver'] else 0
    employment = min(8, 12 - 3 - training) if expected['reach:store'] else 0
    goods = 5 if expected['reach:eat'] else 0
    assert actuals(result) == {'care': ['3', '0'], 'training': [str(training), str(3-training)],
        'employment': [str(employment), str(8-employment)], 'goods': [str(goods), str(8-goods)]}
    balances = {a.account_id: Fraction(a.closing) for a in result.economy.allocation.accounts.accounts}
    assert balances['labor'] + 3 + training + employment == 12
    assert balances['raw'] + goods == 20 and balances['rights'] + goods == 5
    assert {a.account_id: int(a.closing) for a in result.infrastructure.allocation.accounts.accounts} == {
        'depot:slots': 5-sum(chosen), 'bridge:slots': capacity-sum(chosen), 'road:slots': 5-sum(chosen)}


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('procedure', ['priority', 'all_or_nothing'])
@pytest.mark.parametrize('stock,rights', [(0,5),(3,5),(20,0),(20,5),(20,12)])
def test_independent_time_and_goods_feasible_sets(reverse, procedure, stock, rights):
    data = fixture(); e = data['request']['economy']
    for aid, amount in [('raw',stock),('rights',rights)]:
        next(a for a in e['batch']['accounts'] if a['id']==aid)['opening'] = str(amount)
    e['procedure'] = procedure
    if reverse: e['claim_order'].reverse()
    result = run(data)
    # Prior care 1 is fixed; the remaining held hour protects care even if
    # employment/training precede it. Model the reservation independently.
    remaining, care_hold = 11, 1
    expected = {'care':1, 'training':0, 'employment':0, 'goods':0}
    demands = {'care':2, 'training':3, 'employment':8}
    for cid in e['claim_order']:
        if cid == 'goods':
            limit = min(stock, rights, 8)
            expected[cid] = limit if procedure=='priority' or limit==8 else 0
        else:
            limit = remaining if cid=='care' else remaining-care_hold
            amount = min(demands[cid], limit)
            if procedure=='all_or_nothing' and amount < demands[cid]: amount=0
            expected[cid] += amount; remaining -= amount
            if cid=='care': care_hold=max(0,care_hold-amount)
    assert {c.claim_id: int(c.actual) for c in result.economy.allocation.accounts.claims} == expected


@pytest.mark.parametrize('unknown', ['availability','access','procedure','eligibility','terms','economy_procedure'])
def test_unknowns_withhold_complete_candidate(unknown):
    data=fixture(); r=data['request']; infra=r['infrastructure']; e=r['economy']
    if unknown=='availability': infra['links'][0]['availability']='unknown'
    if unknown=='access': infra['demands'][0]['access']='unknown'
    if unknown=='procedure': infra.update(procedure=None,claim_order=[])
    if unknown=='eligibility': e['activities'][-1]['eligibility']='unknown'
    if unknown=='terms': e['activities'][-1]['terms_known']=False
    if unknown=='economy_procedure': e.update(procedure=None,claim_order=[])
    result=run(data)
    assert result.status=='unresolved' and result.batch is None
    if unknown in ('availability','access','procedure'): assert result.economy is None
    else: assert result.infrastructure.status=='resolved'


@pytest.mark.parametrize('blocked', ['denied','planned','offline','retired','disconnected'])
def test_known_block_preserves_independent_care_and_named_cause(blocked):
    data=fixture(); infra=data['request']['infrastructure']
    if blocked=='denied':
        for d in infra['demands']: d['access']='denied'
    elif blocked=='disconnected':
        for d in infra['demands']: d.update(origin_id='island',path=[])
    else: infra['facilities'][0]['availability']=blocked
    result=run(data)
    assert result.status=='resolved'
    cause={'denied':'access_denied','disconnected':'disconnected'}.get(blocked,'nonoperating_asset')
    assert all(x.findings==[cause] for x in result.infrastructure.results)
    assert actuals(result)=={'care':['3','0'],'training':['0','3'],'employment':['0','8'],'goods':['0','8']}
    assert sum(p.id=='prior:care' for p in result.batch.postings)==1


def test_partial_reach_never_scales_economic_output_and_multiple_gates_all_required():
    data=fixture(); infra=data['request']['infrastructure']
    infra['batch']['claims'][-1]['requested']='2'; infra['demands'][-1]['access_limit']='2'
    next(a for a in infra['batch']['accounts'] if a['id']=='bridge:slots')['opening']='4'
    result=run(data)
    assert (result.infrastructure.results[-1].additional,result.infrastructure.results[-1].unmet)==('1','1')
    assert actuals(result)['goods']==['0','8']
    data=fixture(); data['request']['prerequisites'][-1]['demand_ids'].append('reach:make')
    data['request']['infrastructure']['demands'][0]['access']='denied'
    assert actuals(run(data))['goods']==['0','8']


@pytest.mark.parametrize('eligibility', ['unknown','denied'])
def test_reach_cannot_grant_goods_access_or_erase_unknown(eligibility):
    data=fixture(); data['request']['economy']['activities'][-1]['eligibility']=eligibility
    for availability in ['operating','offline']:
        data['request']['infrastructure']['facilities'][0]['availability']=availability
        result=run(data)
        if eligibility=='unknown': assert result.batch is None
        else: assert actuals(result)['goods']==['0','8']


def test_replay_retains_both_books_once_even_after_counterfactual_denial():
    data=fixture(); first=run(data)
    data['request']['economy']['batch']=first.batch.model_dump(mode='json')
    data['request']['infrastructure']['batch']=first.infrastructure.allocation.batch.model_dump(mode='json')
    result=run(data)
    assert result.batch==first.batch
    assert result.infrastructure.allocation.batch==first.infrastructure.allocation.batch
    for d in data['request']['infrastructure']['demands']: d['access']='denied'
    denied=run(data)
    assert actuals(denied)==actuals(first) and denied.batch==first.batch
    assert all(r.findings==['access_denied'] and r.prior=='1' for r in denied.infrastructure.results)


def test_slot_reservation_protects_later_demand_and_is_not_double_spent():
    data=fixture(); b=data['request']['infrastructure']['batch']
    next(a for a in b['accounts'] if a['id']=='depot:slots')['opening']='2'
    b['reservations']=[dict(id='hold:eat',account_id='depot:slots',claim_id='reach:eat',amount='1')]
    result=run(data)
    assert {r.claim_id:r.additional for r in result.infrastructure.results}=={
        'reach:make':'1','reach:deliver':'0','reach:store':'0','reach:eat':'1'}
    assert actuals(result)['goods']==['5','3'] and actuals(result)['care']==['3','0']
    assert sum(p.reservation_id=='hold:eat' for p in result.infrastructure.allocation.batch.postings)==1


@pytest.mark.parametrize('change,code', [
    ('period','infrastructure_counterpart_period_mismatch'),('pool','infrastructure_counterpart_pool_collision'),
    ('account','counterpart_account_identity'),('missing','incomplete_infrastructure_counterpart_prerequisites'),
    ('duplicate','invalid_infrastructure_counterpart_prerequisite'),('claim','invalid_infrastructure_counterpart_prerequisite'),
    ('demand','unknown_infrastructure_counterpart_demand'),('duplicate_demand','invalid_infrastructure_counterpart_prerequisite'),
    ('claimant','infrastructure_counterpart_claim_context'),('scope','infrastructure_counterpart_claim_context'),
    ('path','incomplete_infrastructure_path'),('holder','counterpart_time_holders')])
def test_invalid_bindings_reject_without_mutation(change,code):
    data=fixture(); r=data['request']; infra=r['infrastructure']; req=r['prerequisites']; e=r['economy']
    if change=='period': infra['period_id']='day:1'
    if change=='pool': infra['batch']['claims'][0]['id']='care'
    if change=='account': infra['batch']['accounts'][0]['id']='unregistered'
    if change=='missing': req.pop()
    if change=='duplicate': req.append(deepcopy(req[0]))
    if change=='claim': req[0]['claim_id']='unknown'
    if change=='demand': req[1]['demand_ids']=['unknown']
    if change=='duplicate_demand': req[1]['demand_ids']*=2
    if change=='claimant': infra['batch']['claims'][1]['claimant_id']='other:cohort'
    if change=='scope':
        for a in e['batch']['accounts']:
            if a['id'] in ('raw','product','residual','rights'): a['scope_id']='west'
    if change=='path': infra['demands'][0]['path']=[]
    if change=='holder': e['holders']=[h for h in e['holders'] if h['role']!='time']
    before=deepcopy(data)
    with pytest.raises(AccountError,match=code): run(data)
    assert data==before


def test_two_local_scopes_and_shared_cohort_preserve_canonical_time():
    data=fixture(); r=data['request']
    r['infrastructure']['scope_id']='west'
    for a in r['infrastructure']['batch']['accounts']: a['scope_id']='west'
    for a in r['economy']['batch']['accounts']:
        if a['id'] in ('raw','product','residual','labor','rights'): a['scope_id']='west'
    assert actuals(run(data))==fixture()['expected']['claims']
    # A second account for the same cohort cannot manufacture more time, even
    # in another scope. Both accounts use canonical IDs present in the world.
    e=r['economy']; duplicate=deepcopy(next(a for a in e['batch']['accounts'] if a['id']=='labor'))
    duplicate.update(id='handling',scope_id='east')
    e['batch']['accounts']=[a for a in e['batch']['accounts'] if a['id']!='handling']+[duplicate]
    e['holders'].append(dict(account_id='handling',holder_id='shared:cohort',role='time'))
    with pytest.raises(AccountError,match='duplicate_cohort_time_budget'): run(data)


def test_common_conformance_is_repeatable_and_both_callbacks_are_review_gated():
    r,i,g,u=setup(); reg,i=trusted(r,i,g,u); case=case_for(i)
    first=run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    assert first==run_bound_case(case,request=r,units=u,reviews=reg.reviews) and first.accounts is None
    unreviewed=host_registry(r,graph=g,units=u,reviews=[])
    for mid in ('authored:ei-work-mechanism','authored:ei-economy-mechanism'):
        with pytest.raises(MechanismError,match='review_required'):
            unreviewed.activate(mid,'v1',phase='static',world=g.registry,scope_id='east',entity_id='east-authority')


@pytest.mark.parametrize('unknown', ['access','terms'])
def test_common_unknown_propagates(unknown):
    data=fixture()
    if unknown=='access': data['request']['infrastructure']['demands'][0]['access']='unknown'
    else: data['request']['economy']['activities'][-1]['terms_known']=False
    r,i,g,u=setup(data); reg,i=trusted(r,i,g,u)
    assert run_bound_case(case_for(i,'missing_input'),request=r,units=u,reviews=reg.reviews).accounts is None


def test_opaque_tokens_reject_forgery_and_host_snapshots_request():
    r,i,g,u=setup(); reg,i=trusted(r,i,g,u); callbacks={x.id:x.callback for x in reg.implementations}
    work=callbacks['authored:ei-work']; economy=callbacks['authored:ei-economy']
    with pytest.raises(AccountError,match='stale_counterpart_context'): work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'): economy(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=binding(r,g,u))})
    first=economy(CANDIDATE,{BOOK:LabelValue(**token)})
    r.infrastructure.demands.clear(); r.economy.activities.clear()
    assert economy(CANDIDATE,{BOOK:LabelValue(**token)})==first


@pytest.mark.parametrize('field', ['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_runtime_identity_rejects(field):
    r,i,g,u=setup(); reg,i=trusted(r,i,g,u)
    i=i.model_copy(update={'versions':i.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):
        run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)


@pytest.mark.parametrize('change', ['request','world'])
def test_stale_context_cannot_be_reused(change):
    r,i,g,u=setup(); reg,i=trusted(r,i,g,u)
    if change=='request': r.infrastructure.demands[0]=r.infrastructure.demands[0].model_copy(update={'access':'denied'})
    else: i=i.model_copy(update={'entities':[i.entities[0].model_copy(update={'label':'Changed'}),*i.entities[1:]]})
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)


def test_forged_nested_dto_is_revalidated():
    r,_,g,u=setup(); r.prerequisites.append({'forged':True})
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError): evaluate_pair(r,graph=g,units=u)


def test_unknown_capacity_is_rejected_instead_of_zero():
    data=fixture(); data['request']['infrastructure']['batch']['accounts'][0]['opening']=None
    with pytest.raises(ValidationError): run(data)


@pytest.mark.parametrize('procedure', ['priority','all_or_nothing'])
def test_partial_slot_commitment_never_grants_full_goods_under_either_procedure(procedure):
    data=fixture(); infra=data['request']['infrastructure']
    infra['procedure']=procedure
    infra['batch']['claims'][-1]['requested']='3'; infra['demands'][-1]['access_limit']='3'
    result=run(data)
    assert result.infrastructure.results[-1].unmet in ('1','3')
    assert actuals(result)['goods']==['0','8']


def test_blocked_reach_keeps_unknown_economic_terms_and_rejects_invalid_original_terms():
    data=fixture(); r=data['request']; r['infrastructure']['facilities'][0]['availability']='offline'
    r['economy']['activities'][-1]['terms_known']=False
    assert run(data).batch is None
    # The producer being unknown cannot conceal an invalid goods account.
    r['infrastructure']['facilities'][0]['availability']='unknown'
    r['economy']['batch']['claims'][-1]['account_id']='missing'
    with pytest.raises(AccountError,match='unknown_account'): run(data)


@pytest.mark.parametrize('change,code', [('period','counterpart_period_mismatch'),
    ('dimension','invalid_infrastructure_capacity'),('scale','incompatible_infrastructure_units'),
    ('direction','invalid_infrastructure_path')])
def test_units_periods_and_directed_paths_are_not_inferred(change,code):
    data=fixture(); infra=data['request']['infrastructure']
    if change=='period': infra['batch']['accounts'][0]['period_id']='day:1'
    if change=='dimension': infra['batch']['accounts'][0]['unit_id']='hours'
    if change=='scale':
        slot=deepcopy(next(u for u in data['units'] if u['id']=='slots'))
        slot.update(id='double-slots',scale='2'); data['units'].append(slot)
        infra['batch']['accounts'][0]['unit_id']='double-slots'
    if change=='direction': infra['demands'][0]['path'].reverse()
    with pytest.raises(AccountError,match=code): run(data)


def test_opaque_token_is_bound_to_unit_registry():
    from decimal import Decimal
    from poliscope_engine.numeric import Registry, Unit
    r,i,g,u=setup(); reg,i=trusted(r,i,g,u)
    changed=Registry(tuple(Unit(x.id,x.dimension,x.kind,Decimal(7200) if x.id=='hours' else x.scale) for x in u.units))
    assert binding(r,g,u)!=binding(r,g,changed)
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):
        run_bound_case(case_for(i),request=r,units=changed,reviews=reg.reviews)
