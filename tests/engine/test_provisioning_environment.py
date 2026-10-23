"""Exact shared extraction and residual conservation; no duplicated pools."""
from copy import deepcopy
from fractions import Fraction
import pytest
from pydantic import ValidationError
from poliscope_engine.accounts import AccountError
from poliscope_engine.contracts.world import LabelValue
from poliscope_engine.domains import ConformanceError
from poliscope_engine.domains.conformance import ConformanceCase
from poliscope_engine.domains.provisioning.environment import evaluate_pair
from poliscope_engine.domains.provisioning.environment_counterpart import (
    binding, host_registry, run_bound_case, CONTEXT, WORK, BOOK, CANDIDATE,
)
from poliscope_engine.mechanisms import MechanismError
from provisioning_environment_fixture import fixture, setup, trusted


def run(data=None):
    r,_,g,u=setup(data)
    return evaluate_pair(r,graph=g,units=u)


def change_account(data,aid,**values):
    for b in [data['request']['provisioning'][x]['batch'] for x in ['work','chain']]:
        next(a for a in b['accounts'] if a['id']==aid).update(values)


def case_for(inputs,status='partial'):
    return ConformanceCase(inputs=inputs,outcome='incomplete',observations=(
        dict(node=['output','provision',CANDIDATE],status=status),),
        trace_edges=((('output','work',WORK),('input','provision',BOOK)),))


def test_literal_shared_book_and_detached_repeatability():
    d=fixture();before=deepcopy(d);x=run(d)
    assert d==before and x==run(d) and x.status=='resolved'
    assert {a.account_id:a.closing for a in x.provisioning.accounts.accounts}==d['expected']['accounts']
    assert {c.claim_id:[c.actual,c.unmet] for c in x.provisioning.accounts.claims}==d['expected']['claims']
    assert {b.account_id:(b.gross_debit,b.limit_status) for b in x.environment.boundaries}=={
        'raw':('10','limit_breached'),'sink':('3','limit_breached')}
    assert x.environment.allocation.batch.accounts==x.batch.accounts
    assert x.environment.allocation.batch.postings==x.batch.postings[:len(x.environment.allocation.batch.postings)]
    assert sum(p.id=='prior:care' for p in x.batch.postings)==1
    assert sum(Fraction(p.amount) for p in x.batch.postings if p.source_id=='raw')==10
    assert sum(Fraction(p.amount) for p in x.batch.postings if p.source_id=='sink')==3
    x.batch.postings.clear();x.environment.request.demands.clear()
    assert run().batch.postings and run().environment.request.demands


@pytest.mark.parametrize('raw',[0,5,10,20])
@pytest.mark.parametrize('sink',[0,1,2,3,6])
@pytest.mark.parametrize('all_or_nothing',[False,True])
def test_independent_fraction_mass_time_and_finite_sink_oracle(raw,sink,all_or_nothing):
    d=fixture();change_account(d,'raw',opening=str(raw));change_account(d,'sink',opening=str(sink))
    if all_or_nothing:d['request']['provisioning']['chain']['phases'][0]['procedure']='all_or_nothing'
    x=run(d)
    # Quantum 1 kg plus 0.7/0.2 output coefficients in whole-kg stocks
    # means 10 kg production steps. Joint sink budget is 0.3 kg per kg input.
    made=Fraction(min(raw,Fraction(sink)*10/3,12)//10*10)
    if all_or_nothing:made=0 # requested 30 kg exceeds finite inputs
    shipped=min(made*Fraction(7,10), (6-made/2)*2,10)
    stored=min(3,shipped);used=min(1,stored)
    claims={c.claim_id:Fraction(c.actual) for c in x.provisioning.accounts.claims}
    assert claims==dict(care=3,training=3,**{'make-food':made,'ship-food':shipped,'store-food':stored,'eat-food':used})
    b={a.account_id:Fraction(a.closing) for a in x.provisioning.accounts.accounts}
    assert b['sink']==sink-made*Fraction(3,10)
    assert b['labor']==6-made/2-shipped/2
    assert sum(b[a] for a in ['raw','product','residual','receiving','stored'])+made/10+used==raw


@pytest.mark.parametrize('where',['extraction','sink_capacity','sink_access','access','work','production','freight','storage','use'])
def test_unknown_competitors_withhold_candidate(where):
    d=fixture();r=d['request'];p=r['provisioning']
    if where=='extraction':r['boundaries'][0]['capacity_status']='unknown'
    if where=='sink_capacity':r['boundaries'][1]['capacity_status']='unknown'
    if where=='sink_access':r['sinks'][0]['access']='unknown'
    if where=='access':r['demands'][0]['access']='unknown'
    if where=='work':p['work']['activities'][0]['terms_known']=False
    if where in ['production','freight','storage']:
        phase=next(x for x in p['chain']['phases'] if x['kind']==where)
        phase['routes' if where=='freight' else 'choices'][0]['funding_known']=False
    if where=='use':p['use_terms'][0]['activities'][0]['eligibility']='unknown'
    x=run(d);assert x.status=='unresolved' and x.batch is None
    if where in ['extraction','sink_capacity','sink_access','access','production']:assert x.environment.status=='unresolved'
    if where in ['freight','storage','use']:assert x.environment.status=='resolved'


@pytest.mark.parametrize('where',['extraction','sink'])
def test_denial_blocks_new_extraction_without_erasing_work(where):
    d=fixture();d['request']['demands' if where=='extraction' else 'sinks'][0]['access']='denied'
    x=run(d);assert x.status=='resolved'
    b={a.account_id:a.closing for a in x.provisioning.accounts.accounts}
    assert b['raw']=='20' and b['sink']=='3' and b['labor']=='6'
    assert x.work.allocation.accounts.claims[0].actual=='3'


@pytest.mark.parametrize('where',['sink','extraction'])
def test_denial_cannot_erase_other_unknown(where):
    d=fixture();d['request']['sinks' if where=='sink' else 'demands'][0]['access']='denied'
    d['request']['provisioning']['chain']['phases'][0]['choices'][0]['access']='unknown'
    assert run(d).batch is None


@pytest.mark.parametrize('policy',['unselected','unknown','zero'])
def test_selected_limits_are_diagnostics_never_implicit_policy(policy):
    d=fixture()
    for b in d['request']['boundaries']:
        b.update(policy_ref=None if policy=='unselected' else 'policy:limit',
                 selected_limit='0' if policy=='zero' else None)
    x=run(d);assert x.batch==run().batch
    assert {b.limit_status for b in x.environment.boundaries}=={
        {'unselected':'not_selected','unknown':'unknown','zero':'limit_breached'}[policy]}


def test_prior_unclaimed_debits_imports_and_holds_survive_once():
    d=fixture()
    for b in [d['request']['provisioning'][x]['batch'] for x in ['work','chain']]:
        proto=deepcopy(b['postings'][0]);proto.update(id='prior:sink',source_id='sink',claim_id=None,reservation_id=None,amount='1')
        b['postings'].append(proto)
        b['reservations'].append(dict(id='hold:training',account_id='labor',claim_id='training',amount='1'))
    x=run(d)
    assert x.status=='resolved' and sum(p.id=='prior:sink' for p in x.batch.postings)==1
    assert next(b for b in x.environment.boundaries if b.account_id=='sink').gross_debit=='1'
    assert next(c for c in x.provisioning.accounts.claims if c.claim_id=='make-food').actual=='0'
    assert x.batch.reservations==x.request.provisioning.work.batch.reservations


def test_scaled_sink_units_conserve_exact_mass():
    d=fixture();d['units'][-1]['scale']='0.001';d['request']['sinks'][0]['per_unit']='300'
    change_account(d,'sink',opening='3000',maximum='10000')
    x=run(d);assert next(b for b in x.environment.boundaries if b.account_id=='sink').gross_debit=='3000'
    assert next(c for c in x.provisioning.accounts.claims if c.claim_id=='make-food').actual=='10'


@pytest.mark.parametrize('change,code',[
    ('rate','residual_conservation'),('resource','resource_mismatch'),('missing','invalid_environment_counterpart_mapping'),
    ('duplicate','invalid_environment_counterpart_mapping'),('sink_ref','sink_scope_reference'),
    ('extract_ref','scope_reference'),('period','counterpart_period_mismatch'),
    ('wrong_sink','invalid_environment_counterpart_accounts'),('dimension','sink_units_scope'),
    ('book','counterpart_batch_mismatch'),('replenish','extraction_replenishment'),
    ('downstream','downstream_boundary'),('two_productions','production_plan'),
    ('demand_scope','scope_reference'),('zero_residual','residual_conservation')])
def test_invalid_mapping_rejects_without_changing_input(change,code):
    d=fixture();r=d['request'];p=r['provisioning'];c=p['chain']['phases'][0]['choices'][0]
    if change=='rate':r['sinks'][0]['per_unit']='0.2'
    if change=='resource':r['boundaries'][0]['resource_id']='food'
    if change=='missing':r['demands'].clear()
    if change=='duplicate':r['sinks']*=2
    if change=='sink_ref':r['sinks'][0]['scope_relationship_id']='view-east'
    if change=='extract_ref':r['demands'][0]['scope_relationship_id']='sink:view'
    if change=='period':change_account(d,'sink',period_id='day:1')
    if change=='wrong_sink':r['sinks'][0]['account_id']='labor'
    if change=='dimension':d['units'][-1]['dimension']=[['length',1]]
    if change=='book':p['chain']['batch']['postings'][0]['amount']='2'
    if change=='replenish':c['outputs'][0]['account_id']='raw'
    if change=='downstream':p['chain']['phases'][1]['routes'][0]['destination_id']='raw'
    if change=='two_productions':
        other=deepcopy(p['chain']['phases'][0]);other['id']='make:again';p['chain']['phases'].append(other)
    if change=='demand_scope':r['demands'][0]['scope_id']='region'
    if change=='zero_residual':c['loss_per_unit']='0';c['outputs'][1]['role']='product'
    before=deepcopy(d)
    with pytest.raises((AccountError,ValidationError),match=code if change!='missing' else 'at least 1 item'):run(d)
    assert d==before


def test_common_conformance_repeatability_and_explicit_review():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);case=case_for(i)
    assert run_bound_case(case,request=r,units=u,reviews=reg.reviews)==run_bound_case(case,request=r,units=u,reviews=reg.reviews)
    with pytest.raises(MechanismError,match='review_required'):
        host_registry(r,graph=g,units=u,reviews=[]).activate('authored:environment-pair-work-mechanism','v1',phase='static',world=g.registry,scope_id='east',entity_id='east-authority')


@pytest.mark.parametrize('where',['sink','use'])
def test_common_unknown_propagation(where):
    d=fixture()
    if where=='sink':d['request']['sinks'][0]['access']='unknown'
    else:d['request']['provisioning']['use_terms'][0]['activities'][0]['terms_known']=False
    r,i,g,u=setup(d);reg,i=trusted(r,i,g,u)
    assert run_bound_case(case_for(i,'missing_input'),request=r,units=u,reviews=reg.reviews).accounts is None


def test_host_rejects_forged_tokens_and_snapshots_request():
    r,i,g,u=setup();reg,i=trusted(r,i,g,u);callbacks={x.id:x.callback for x in reg.implementations}
    work=callbacks['authored:environment-pair-work'];provision=callbacks['authored:environment-pair-provisioning']
    with pytest.raises(AccountError,match='stale_counterpart_context'):work(WORK,{CONTEXT:LabelValue(kind='label',value='forged')})
    with pytest.raises(AccountError,match='stale_counterpart_book'):provision(CANDIDATE,{BOOK:LabelValue(kind='label',value='forged')})
    token=work(WORK,{CONTEXT:LabelValue(kind='label',value=binding(r,g,u))});first=provision(CANDIDATE,{BOOK:LabelValue(**token)})
    r.sinks.clear();assert provision(CANDIDATE,{BOOK:LabelValue(**token)})==first


@pytest.mark.parametrize('field',['model_id','numeric_runtime_id','catalog_id'])
def test_foreign_runtime_rejects(field):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    i=i.model_copy(update={'versions':i.versions.model_copy(update={field:'foreign'})})
    with pytest.raises(ConformanceError,match='counterpart_version_mismatch'):run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)


@pytest.mark.parametrize('change',['request','world'])
def test_stale_context_rejects(change):
    r,i,g,u=setup();reg,i=trusted(r,i,g,u)
    if change=='request':r.sinks[0]=r.sinks[0].model_copy(update={'access':'denied'})
    else:i=i.model_copy(update={'entities':[i.entities[0].model_copy(update={'label':'changed'}),*i.entities[1:]]})
    with pytest.raises(ConformanceError,match='stale_counterpart_context'):run_bound_case(case_for(i),request=r,units=u,reviews=reg.reviews)


def test_forged_nested_dto_rejects():
    r,_,g,u=setup();r.sinks.append({'forged':True})
    with pytest.warns(UserWarning,match='Pydantic serializer warnings'):
        with pytest.raises(ValidationError):evaluate_pair(r,graph=g,units=u)


@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('hold',[False,True])
def test_actual_competitors_share_extraction_sink_and_operating_books(reverse,hold):
    d=fixture();r=d['request'];phase=r['provisioning']['chain']['phases'][0]
    phase['claims'][0]['requested']='10'
    claim=deepcopy(phase['claims'][0]);claim.update(id='make:second')
    choice=deepcopy(phase['choices'][0]);choice['claim_id']='make:second'
    phase['claims'].append(claim);phase['choices'].append(choice);phase['claim_order'].append('make:second')
    demand=deepcopy(r['demands'][0]);demand['claim_id']='make:second';r['demands'].append(demand)
    sink=deepcopy(r['sinks'][0]);sink['claim_id']='make:second';r['sinks'].append(sink)
    change_account(d,'raw',opening='10')
    if reverse:phase['claim_order'].reverse()
    if hold:phase['reservations']=[dict(id='hold:second',account_id='raw',claim_id='make:second',amount='10')]
    x=run(d);actual={c.claim_id:c.actual for c in x.provisioning.accounts.claims}
    winner='make:second' if hold or reverse else 'make-food'
    assert actual[winner]=='10' and actual['make-food' if winner=='make:second' else 'make:second']=='0'
    assert {b.account_id:b.gross_debit for b in x.environment.boundaries}=={'raw':'10','sink':'3'}
    assert sum(Fraction(p.amount) for p in x.batch.postings if p.source_id=='labor')==12
    if hold:assert sum(Fraction(p.amount) for p in x.batch.postings if p.reservation_id=='hold:second')==10


def test_imports_do_not_cancel_prior_gross_extraction_diagnostic():
    d=fixture()
    for b in [d['request']['provisioning'][x]['batch'] for x in ['work','chain']]:
        proto=deepcopy(b['postings'][0]);proto.update(id='prior:extract',source_id='raw',claim_id=None,reservation_id=None,amount='5')
        b['postings'].append(proto)
        proto=deepcopy(proto);proto.update(id='prior:import',kind='import',source_id=None,destination_id='raw')
        b['postings'].append(proto)
    x=run(d)
    assert next(b for b in x.environment.boundaries if b.account_id=='raw').gross_debit=='15'
    assert next(a for a in x.provisioning.accounts.accounts if a.account_id=='raw').closing=='10'


@pytest.mark.parametrize('where',['requirement','output'])
def test_unknown_resource_accounts_reject_cleanly(where):
    d=fixture();choice=d['request']['provisioning']['chain']['phases'][0]['choices'][0]
    choice['requirements' if where=='requirement' else 'outputs'][0]['account_id']='foreign'
    with pytest.raises(AccountError,match='unknown_account'):run(d)


@pytest.mark.parametrize('budget,made',[('0.3','1'),('1.5','5'),('2.4','8'),('3.6','12')])
def test_partial_production_is_constrained_jointly_in_material_units(budget,made):
    d=fixture()
    for aid in ['land','product','residual','receiving','stored','truck','handling']:
        change_account(d,aid,quantum='0.1')
    change_account(d,'sink',opening=budget)
    x=run(d);production=x.environment.allocation
    a=next(a for a in production.actuals if a.claim_id=='make-food')
    assert a.allocated==made
    assert list(map(Fraction,a.outputs))==[Fraction(made)*Fraction(7,10),Fraction(made)/5]
    assert Fraction(a.loss)==Fraction(made)/10
    assert next(b for b in x.environment.boundaries if b.account_id=='sink').gross_debit==budget
    assert x.status=='resolved'


def test_freight_cannot_reuse_sink_allowance_as_transport_capacity():
    d=fixture()
    d['request']['provisioning']['chain']['phases'][1]['routes'][0]['capacity_id']='sink'
    with pytest.raises(AccountError,match='downstream_boundary'):run(d)


def test_preflight_does_not_allocate_before_work_reduces_operating_inputs():
    d=fixture();change_account(d,'sink',opening='6');change_account(d,'product',maximum='10')
    x=run(d)
    assert x.status=='resolved'
    assert next(c for c in x.provisioning.accounts.claims if c.claim_id=='make-food').actual=='10'
