"""WP-035 literal model fixtures, portable vectors and actual atomic transitions."""
from dataclasses import replace
from decimal import localcontext
import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

from poliscope_engine.contracts.stochastic import DrawSpec, RandomPlan, RandomRuntime
from poliscope_engine.stochastic import (RUNTIME, RandomModelError, sample, realize,
    verify_draw, validate_plan, fork_plan, check_retained)
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.simulation import TransitionAdapter, TransitionReducer
from poliscope_engine.boundaries import BoundaryStore, BoundaryError, outcome
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.transitions import TransitionProposal, TransitionPlan
from transition_fixture import fixture, start

SEED = '01' * 32


def spec(variable='hazard-a', *, instance='a', day=1, **updates):
    raw = dict(variable_id=variable, day=day,
        key=dict(mechanism_id='synthetic:model/infrastructure',mechanism_version='v1',
            instance_id=instance,entity_id='service-'+instance,scope_id='local',
            purpose='synthetic:hazard',event_id='storm:'+str(day),draw_name='occurs',index=0),
        distribution=dict(kind='bernoulli',numerator=1,denominator=3),
        dependence='declared_independent',source_refs=['synthetic:source'],assumption_refs=['synthetic:probability'])
    raw.update(updates)
    return DrawSpec.model_validate(raw)


def plan(draws=None, **updates):
    draws = [spec()] if draws is None else draws
    raw = dict(contract_version=1,seed=SEED,runtime=RUNTIME,draws=draws,
        references=[dict(instance_id=d.key.instance_id,variable_id=d.variable_id) for d in draws])
    raw.update(updates)
    return RandomPlan.model_validate(raw)


def hazard_adapter():
    def propose(invocation):
        return TransitionProposal(transition_class='response_capacity',status='ready',reason='synthetic:hazard',
            demands=[],source_refs=['synthetic:source'])
    def resolve(invocation, proposal):
        row = next(v for v in invocation.inputs.values if v.entity_id == invocation.instance.entity_id)
        # This bounded hypothetical event changes a count only; it is no damage model.
        amount = sum(d.value == 'true' for d in invocation.random_draws)
        return [row.model_copy(update={'value':row.value.model_copy(update={'value':str(int(row.value.value)+amount)}),
            'effective_time':invocation.inputs.effective_time})]
    def validate(invocation, proposal, writes, closing):
        row = next(v for v in invocation.inputs.values if v.entity_id == invocation.instance.entity_id)
        assert int(writes[0].value.value) == int(row.value.value) + sum(d.value == 'true' for d in invocation.random_draws)
    return TransitionAdapter(propose, resolve, validate)


def setup_random(store, *, random=None, domains=('infrastructure',), shared=False):
    mechanisms,catalog,initial,transition = fixture(domains,adapters={chr(97+i):hazard_adapter() for i in range(len(domains))})
    selected = plan() if random is None else random
    transition = TransitionPlan.model_validate(transition.model_dump() | dict(random_plan=selected))
    return start(store,mechanisms,catalog,initial,transition)


def test_literal_portable_vector_and_independent_integer_oracle():
    draw = sample(SEED,RUNTIME,spec())
    # Independent fixed message, without using production canonicalizers.
    message = ('{"counter":0,"key":{"draw_name":"occurs","entity_id":"service-a",'
        '"event_id":"storm:1","index":0,"instance_id":"a","mechanism_id":"synthetic:model/infrastructure",'
        '"mechanism_version":"v1","purpose":"synthetic:hazard","scope_id":"local"},'
        '"runtime":{"key":"named-draw-json-v1","rng":"hmac-sha256-counter-v1",'
        '"sampling":"exact-discrete-rejection-v1"}}')
    expected = hmac.new(bytes.fromhex(SEED),message.encode(),hashlib.sha256).hexdigest()
    assert expected == 'bd6e1bf82d2ab5a84aa71be3a07f299e5110d9b459628e28aacb1d708cdd93f6'
    assert draw.accepted_block == expected
    assert draw.value == ('true' if int(expected,16)%3 == 0 else 'false')
    assert draw.rejected_blocks == 0
    verify_draw(draw)


@pytest.mark.parametrize('field,value', [('instance_id','b'),('entity_id','other'),('scope_id','regional'),
    ('purpose','other'),('event_id','other'),('draw_name','other'),('index',1),
    ('mechanism_id','other'),('mechanism_version','v2')])
def test_every_key_component_separates_stream(field,value):
    original=spec()
    changed=original.model_copy(update={'key':original.key.model_copy(update={field:value})})
    assert sample(SEED,RUNTIME,changed).accepted_block != sample(SEED,RUNTIME,original).accepted_block


def test_insertion_order_shared_reference_and_repeated_evaluation():
    first=spec()
    second=spec('other',instance='b')
    one=realize(plan([first]),1)[0]
    two=realize(plan([second,first]),1)
    assert next(d for d in two if d.spec.variable_id==first.variable_id)==one
    assert realize(plan([first,second]),1)==two
    shared=first.model_copy(update={'dependence':'shared_realization'})
    selected=plan([shared],references=[dict(instance_id=i,variable_id=shared.variable_id) for i in ['a','b']])
    assert len(realize(selected,1))==1
    assert realize(selected,1)[0].accepted_block==one.accepted_block


@pytest.mark.parametrize('distribution', [dict(kind='bernoulli',numerator=0,denominator=7),
    dict(kind='bernoulli',numerator=7,denominator=7),dict(kind='uniform_integer',low=9,high=9),
    dict(kind='uniform_integer',low=0,high=9007199254740991),
    dict(kind='categorical',outcomes=[dict(value='a',weight=1),dict(value='b',weight=3)])])
def test_exact_discrete_sampling(distribution):
    draw=sample(SEED,RUNTIME,spec(distribution=distribution))
    n=int(draw.accepted_block,16)
    if distribution['kind']=='bernoulli':
        assert draw.value==('true' if distribution['numerator'] else 'false')
    elif distribution['kind']=='uniform_integer':
        assert int(draw.value)==distribution['low'] + n%(distribution['high']-distribution['low']+1)
    else:
        assert draw.value==('a' if n%4==0 else 'b')


@pytest.mark.parametrize('distribution', [dict(kind='source_interval',low='1',high='2'),
    dict(kind='bernoulli',numerator=2,denominator=1),dict(kind='bernoulli',numerator=1,denominator=0),
    dict(kind='bernoulli',numerator=0.5,denominator=1),dict(kind='uniform_integer',low=2,high=1),
    dict(kind='categorical',outcomes=[dict(value='a',weight=0)]),
    dict(kind='categorical',outcomes=[dict(value='a',weight=1),dict(value='a',weight=2)])])
def test_no_implicit_source_range_probability_or_invalid_distribution(distribution):
    with pytest.raises(ValidationError): spec(distribution=distribution)


def test_no_implicit_dependence_or_duplicate_identity():
    with pytest.raises(ValidationError,match='duplicate_random_identity'): plan([spec(),spec()])
    with pytest.raises(ValidationError,match='shared_dependence_required'):
        plan(references=[dict(instance_id=i,variable_id='hazard-a') for i in ['a','b']])
    with pytest.raises(ValidationError): spec(assumption_refs=[])
    with pytest.raises(ValidationError): plan(seed='invalid')


def test_fork_paired_and_new_realization_policy_preserves_parent():
    parent=plan()
    paired=fork_plan(parent,policy='preserve')
    assert realize(parent,1)==realize(paired,1)
    assert paired.fork.parent_plan_digest==digest(parent)
    fresh=fork_plan(parent,policy='new_realization',seed='02'*32)
    assert realize(fresh,1)[0].accepted_block != realize(parent,1)[0].accepted_block
    assert parent.fork is None and parent.seed==SEED
    for policy,seed in [('preserve','02'*32),('new_realization',SEED),('new_realization',None)]:
        with pytest.raises(ValidationError): fork_plan(parent,policy=policy,seed=seed)


def test_runtime_unavailable_is_not_exact_reproduction_but_data_is_readable():
    unavailable=RandomRuntime(rng='unknown',key=RUNTIME.key,sampling=RUNTIME.sampling)
    historical=plan(runtime=unavailable)
    assert RandomPlan.model_validate_json(historical.model_dump_json())==historical
    with pytest.raises(RandomModelError,match='historical_random_runtime_unavailable'): realize(historical,1)
    draw=realize(plan(),1)[0]
    with pytest.raises(RandomModelError,match='realized_draw_mismatch'):
        verify_draw(draw.model_copy(update={'value':'forged'}))
    with pytest.raises(RandomModelError): check_retained(plan(),1,[])


def test_decimal_context_and_subprocess_do_not_change_vectors():
    expected=sample(SEED,RUNTIME,spec())
    with localcontext() as ctx:
        ctx.prec=2
        assert sample(SEED,RUNTIME,spec())==expected
    code='from poliscope_engine.contracts.stochastic import RealizedDraw; from poliscope_engine.stochastic import sample; import sys; d=RealizedDraw.model_validate_json(sys.stdin.read()); print(sample(d.seed,d.runtime,d.spec).model_dump_json())'
    result=subprocess.run([sys.executable,'-c',code],input=expected.model_dump_json(),capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)==expected.model_dump(mode='json')


def test_actual_transition_atomic_retention_shared_consumers_and_cold_retry(tmp_path,monkeypatch):
    shared=spec(dependence='shared_realization',distribution=dict(kind='bernoulli',numerator=1,denominator=1))
    selected=plan([shared],references=[dict(instance_id=i,variable_id=shared.variable_id) for i in ['a','b']])
    with Store(tmp_path) as store:
        reducer,opened,request=setup_random(store,random=selected,domains=('infrastructure','knowledge_culture'))
        preview=reducer.preview(opened,1)
        assert len(preview.transition.random_draws)==1
        assert outcome(reducer.store.read(opened.context).record)==opened
        confirmed=reducer.advance_boundary(opened,1,operation_id='first')
        saved=reducer.store.read(opened.context)
        for name in ['a','b']:
            assert next(v.value.value for v in saved.state.inputs.values if v.id=='processed-'+name)=='1'
        assert saved.state.transition.random_draws==realize(selected,1)
        assert digest(saved.state.transition)==digest(preview.transition)
    # Historical reads and completed reducer retry require no current RNG/model.
    with Store(tmp_path) as store:
        revisions=Revisions(store,registry=None)
        reader=BoundaryStore(revisions)
        import poliscope_engine.stochastic as stochastic
        monkeypatch.setattr(stochastic,'sample',lambda *a: (_ for _ in ()).throw(AssertionError('must not sample')))
        assert digest(reader.read(opened.context).state.transition)==digest(preview.transition)
        reducer=TransitionReducer(revisions,catalog=None)
        assert reducer.advance_boundary(opened,1,operation_id='first')==confirmed


def test_reopen_continuation_and_unrelated_module_insertion(tmp_path):
    draws=[spec('day:'+str(day),day=day) for day in (1,2,3)]
    selected=plan(draws)
    histories=[]
    for directory,domains,reopen in [('continuous',('infrastructure',),False),
            ('resumed',('infrastructure',),True),('extra',('infrastructure','knowledge_culture'),False)]:
        path=tmp_path/directory
        store=Store(path)
        reducer,head,request=setup_random(store,random=selected,domains=domains)
        realized=[]
        for day in (1,2,3):
            head=reducer.advance_boundary(head,day,operation_id='day:'+str(day))
            saved=reducer.store.read(head.context)
            realized.extend(saved.state.transition.random_draws)
            if reopen:
                mechanisms,catalog=reducer.mechanisms,reducer.catalog
                store.close()
                store=Store(path)
                reducer=TransitionReducer(Revisions(store,registry=mechanisms),catalog=catalog)
        histories.append((realized,next(v.value.value for v in saved.state.inputs.values if v.id=='processed-a')))
        store.close()
    assert histories[0]==histories[1]==histories[2]


@pytest.mark.parametrize('mutation', ['owner','day','runtime'])
def test_invalid_plan_cannot_create_experiment(tmp_path,mutation):
    selected=plan()
    if mutation=='owner':
        d=spec(); selected=plan([d.model_copy(update={'key':d.key.model_copy(update={'entity_id':'foreign'})})])
    elif mutation=='day': selected=plan([spec(day=0)])
    else: selected=plan(runtime=RandomRuntime(rng='unavailable'))
    with Store(tmp_path) as store:
        with pytest.raises(RandomModelError): setup_random(store,random=selected)


def test_failed_write_and_cancel_do_not_retain_random_candidate(tmp_path,monkeypatch):
    with Store(tmp_path) as store:
        reducer,opened,_=setup_random(store)
        original=store.complete_operation
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError('injected')
        monkeypatch.setattr(store,'complete_operation',fail)
        with pytest.raises(RuntimeError,match='injected'): reducer.advance_boundary(opened,1,operation_id='first')
        assert outcome(reducer.store.read(opened.context).record)==opened
        monkeypatch.setattr(store,'complete_operation',original)
        with pytest.raises(BoundaryError,match='cancelled'):
            reducer.advance_boundary(opened,1,operation_id='first',cancelled=lambda:True)
        confirmed=reducer.advance_boundary(opened,1,operation_id='first')
        assert reducer.store.read(confirmed.context).state.transition.random_draws==realize(plan(),1)


def test_original_plan_and_receipt_digest_formulas_remain_compatible():
    _,_,_,transition=fixture()
    old=transition.model_dump(exclude={'random_plan'})
    assert digest(transition)==digest(old)


def test_persistent_shared_variable_is_reused_after_reopen(tmp_path):
    selected=plan([spec(lifetime='persistent')])
    with Store(tmp_path) as store:
        reducer,head,_=setup_random(store,random=selected)
        head=reducer.advance_boundary(head,1,operation_id='first')
        first=reducer.store.read(head.context).state.transition.random_draws
        mechanisms,catalog=reducer.mechanisms,reducer.catalog
    with Store(tmp_path) as store:
        reducer=TransitionReducer(Revisions(store,registry=mechanisms),catalog=catalog)
        head=reducer.advance_boundary(head,2,operation_id='second')
        assert reducer.store.read(head.context).state.transition.random_draws==first
        check_retained(selected,2,first)


def test_rejection_is_local_unbiased_and_bounded(monkeypatch):
    import poliscope_engine.stochastic as stochastic
    original=stochastic.hmac.new
    calls=[]
    class Block:
        def __init__(self,b): self.b=b
        def digest(self): return self.b
    def injected(key,message,algorithm):
        counter=json.loads(message)['counter']
        calls.append(counter)
        return Block(b'\xff'*32 if counter==0 else b'\x00'*32)
    monkeypatch.setattr(stochastic.hmac,'new',injected)
    draw=sample(SEED,RUNTIME,spec())
    # 2**256-1 is rejected for support 3; zero is accepted at local counter 1.
    assert calls==[0,1] and draw.rejected_blocks==1 and draw.value=='true'
    monkeypatch.setattr(stochastic.hmac,'new',lambda *args: Block(b'\xff'*32))
    with pytest.raises(RandomModelError,match='random_rejection_quota'): sample(SEED,RUNTIME,spec())
    monkeypatch.setattr(stochastic.hmac,'new',original)


@pytest.mark.parametrize('after_commit',[False,True])
def test_random_evidence_real_process_crash_is_atomic(tmp_path,after_commit):
    import os
    with Store(tmp_path) as store:
        reducer,opened,_=setup_random(store)
        path=tmp_path/'opening.json'
        path.write_text(opened.model_dump_json())
        code='''
from pathlib import Path
from contextlib import contextmanager
import os,sys
from test_stochastic import fixture,hazard_adapter
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.contracts.boundaries import BoundaryOutcome
mechanisms,catalog,_,_=fixture(('infrastructure',),adapters={'a':hazard_adapter()})
with Store(Path(sys.argv[1])) as store:
    reducer=TransitionReducer(Revisions(store,registry=mechanisms),catalog=catalog)
    original=store.transaction
    @contextmanager
    def crash():
        with original():
            yield
            if sys.argv[3]=='before':os._exit(81)
        os._exit(82)
    store.transaction=crash
    reducer.advance_boundary(BoundaryOutcome.model_validate_json(Path(sys.argv[2]).read_text()),1,operation_id='crash')
'''
        env=os.environ.copy()
        env['PYTHONPATH']=os.pathsep.join([str(Path('engine').resolve()),str(Path('tests/engine').resolve())])
        result=subprocess.run([sys.executable,'-c',code,str(tmp_path),str(path),'after' if after_commit else 'before'],
            capture_output=True,text=True,env=env)
        assert result.returncode==(82 if after_commit else 81),result.stderr
        saved=reducer.store.read(opened.context)
        assert saved.record.sequence==int(after_commit)
        assert saved.state.transition is not None if after_commit else saved.state.transition is None
        confirmed=reducer.advance_boundary(opened,1,operation_id='crash')
        assert confirmed.sequence==1
        assert reducer.store.read(opened.context).state.transition.random_draws==realize(plan(),1)


def test_authored_condition_and_no_hazard_paths_are_explicit(tmp_path):
    from poliscope_engine.contracts.timeline import DatedEvent
    no_hazard=plan([spec(distribution=dict(kind='bernoulli',numerator=0,denominator=1))])
    with Store(tmp_path) as store:
        reducer,opened,request=setup_random(store,random=no_hazard)
        event=DatedEvent.model_validate(dict(id='authored',effective_day=1,order=0,origin='player_authored',source_refs=[],
            changes=[dict(scope_id='local',condition_id='warning',expected_digest=None,value=dict(kind='label',value='issued'))]))
        request=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'authored'}),
            'plan':request.plan.model_copy(update={'events':[event]})})
        opened=reducer.store.create(request)
        reducer.advance_boundary(opened,1,operation_id='authored')
        saved=reducer.store.read(opened.context)
        assert saved.state.conditions[0].value.value=='issued'
        assert saved.state.transition.random_draws[0].value=='false'
        assert next(v.value.value for v in saved.state.inputs.values if v.id=='processed-a')=='0'
        assert saved.record.due.event_ids==['authored']


def test_fork_cannot_substitute_instance_event_or_parent_identity():
    from poliscope_engine.stochastic import verify_fork
    parent=plan()
    child=fork_plan(parent,policy='preserve')
    altered=child.draws[0].model_copy(update={'key':child.draws[0].key.model_copy(update={'event_id':'other'})})
    with pytest.raises(RandomModelError,match='fork_random_identity_mismatch'):
        verify_fork(parent,child.model_copy(update={'draws':[altered]}))
    with pytest.raises(RandomModelError): verify_fork(parent,plan())


def test_random_callback_input_mutation_is_rejected(tmp_path):
    from poliscope_engine.simulation import TransitionError
    base=hazard_adapter()
    def propose(invocation):
        invocation.random_draws.clear()
        return base.propose(invocation)
    with Store(tmp_path) as store:
        mechanisms,catalog,initial,transition=fixture(('infrastructure',),
            adapters={'a':replace(base,propose=propose)})
        transition=TransitionPlan.model_validate(transition.model_dump() | dict(random_plan=plan()))
        reducer,opened,_=start(store,mechanisms,catalog,initial,transition)
        with pytest.raises(TransitionError,match='mutated_transition_inputs'):
            reducer.advance_boundary(opened,1,operation_id='mutated')
        assert outcome(reducer.store.read(opened.context).record)==opened


def test_draw_work_obeys_cancellation_and_operation_quota(tmp_path):
    from poliscope_engine.simulation import TransitionError
    with Store(tmp_path) as store:
        reducer,_,request=setup_random(store)
        limited=request.transition_plan.model_copy(update={'operation_limit':1})
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'limited'}),
            'transition_plan':limited})
        opened=reducer.store.create(changed)
        with pytest.raises(TransitionError,match='operation_quota'):
            reducer.advance_boundary(opened,1,operation_id='limited')
        assert outcome(reducer.store.read(opened.context).record)==opened
    calls=[]
    def cancel():
        calls.append(1)
        raise BoundaryError('boundary_cancelled')
    with pytest.raises(BoundaryError): realize(plan(),1,checkpoint=cancel)
    assert len(calls)==1


def test_substituted_retained_draw_cannot_confirm_even_with_rehashed_receipt(tmp_path):
    from poliscope_engine.contracts.boundaries import ConfirmBoundary
    from poliscope_engine.simulation import TransitionError
    with Store(tmp_path) as store:
        reducer,opened,_=setup_random(store)
        candidate=reducer.preview(opened,1)
        draw=candidate.transition.random_draws[0]
        forged=draw.model_copy(update={'value':'true' if draw.value=='false' else 'false'})
        receipt=candidate.transition.model_copy(update={'random_draws':[forged]})
        receipt=receipt.model_copy(update={'receipt_digest':digest(receipt.model_dump(exclude={'receipt_digest'}))})
        candidate=candidate.model_copy(update={'transition':receipt})
        with pytest.raises(TransitionError):
            reducer.store.confirm(ConfirmBoundary(boundary_contract=1,expected=opened,operation_id='forged',candidate=candidate))
        assert outcome(reducer.store.read(opened.context).record)==opened


def test_key_encoding_uses_utf8_and_unambiguous_fields():
    original=spec()
    unicode_key=original.key.model_copy(update={'event_id':'暴風:ä', 'draw_name':'a:b'})
    draw=sample(SEED,RUNTIME,original.model_copy(update={'key':unicode_key}))
    raw=json.dumps(dict(counter=0,key=unicode_key.model_dump(),runtime=RUNTIME.model_dump()),
        ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf-8')
    assert draw.accepted_block==hmac.new(bytes.fromhex(SEED),raw,hashlib.sha256).hexdigest()
    different=unicode_key.model_copy(update={'event_id':'暴風:ä:a', 'draw_name':'b'})
    assert sample(SEED,RUNTIME,original.model_copy(update={'key':different})).accepted_block!=draw.accepted_block
