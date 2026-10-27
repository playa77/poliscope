"""Full WP-034 framework checks over real revisions, allocation and SQLite."""
from dataclasses import replace
from fractions import Fraction
from copy import deepcopy
import pytest

from poliscope_engine.boundaries import BoundaryStore, BoundaryError, outcome
from poliscope_engine.contracts.boundaries import BoundaryCandidate, ConfirmBoundary
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.simulation import TransitionReducer, TransitionError, TransitionAdapter, verify_receipt
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from transition_fixture import setup, adapter, fixture


def numbers(saved):
    return {v.id:v.value.value for v in saved.state.inputs.values if v.value.kind == 'quantity'}


def test_shared_material_work_actuals_exact_conservation_and_durable_trace(tmp_path):
    with Store(tmp_path) as store:
        reducer, opened, request = setup(store)
        before = reducer.store.read(opened.context)
        preview = reducer.preview(opened,1)
        assert outcome(reducer.store.read(opened.context).record) == opened
        receipt = preview.transition
        assert [a.allocated for a in receipt.allocation.actuals] != []
        assert sum(Fraction(a.allocated) for a in receipt.allocation.actuals) == 10
        accepted = reducer.advance_boundary(opened,1,operation_id='first')
        current = reducer.store.read(opened.context)
        values = numbers(current)
        assert {k:values[k] for k in ['processed-a','processed-b','balance:material','balance:labor','balance:product','balance:residual']} == {
            'processed-a':'8','processed-b':'2','balance:material':'10','balance:labor':'0','balance:product':'7','balance:residual':'2'}
        assert Fraction(values['balance:material']) + Fraction(values['balance:product']) + Fraction(values['balance:residual']) + 1 == 20
        assert digest(current.state.transition) == digest(preview.transition)
        assert current.record.parent_digest == opened.boundary_digest
        assert digest(verify_receipt(current.state.transition)) == digest(receipt)
        assert reducer.store.read(opened.context,0) == before
        second = reducer.advance_boundary(accepted,2,operation_id='second')
        assert numbers(reducer.store.read(opened.context))['balance:labor'] == '0'
        assert numbers(reducer.store.read(opened.context))['processed-a'] == '8'
        assert len(reducer.store.read(opened.context).state.transition.request.batch.claims) == 3
        assert reducer.advance_boundary(opened,1,operation_id='first') == accepted
    with Store(tmp_path) as reopened:
        reader = BoundaryStore(Revisions(reopened,registry=None))
        assert outcome(reader.read(opened.context).record) == second
        assert digest(reader.read(opened.context,1).state.transition) == digest(receipt)


def test_explicit_reverse_order_changes_only_selected_distribution(tmp_path):
    with Store(tmp_path) as store:
        reducer, opened, _ = setup(store,order=['b','a'])
        candidate = reducer.preview(opened,1)
        assert next(v.value.value for v in candidate.inputs.values if v.id=='processed-b') == '8'
        assert next(v.value.value for v in candidate.inputs.values if v.id=='processed-a') == '2'


def test_invalid_model_invariant_never_publishes_or_consumes_resources(tmp_path):
    with Store(tmp_path) as store:
        reducer, opened, _ = setup(store,adapters={'a':adapter(invalid=True)})
        with pytest.raises(AssertionError,match='model invariant'):
            reducer.advance_boundary(opened,1,operation_id='bad')
        assert outcome(reducer.store.read(opened.context).record)==opened
        assert numbers(reducer.store.read(opened.context))['balance:material']=='20'


def test_missing_model_does_not_hide_supported_counterpart(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,_ = setup(store,missing=['b'])
        accepted = reducer.advance_boundary(opened,1,operation_id='partial')
        saved = reducer.store.read(opened.context)
        assert {s.instance_id:s.status for s in saved.state.transition.steps} == {'a':'applied','b':'coverage_gap'}
        assert numbers(saved)['processed-a']=='8'
        assert numbers(saved)['processed-b']=='0'


def test_unknown_competitor_withholds_shared_effects_but_independent_effect_is_visible(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,_ = setup(store,domains=('infrastructure','knowledge_culture','health'),
            adapters={'b':adapter(access='unknown'),'c':adapter(no_demand=True)})
        reducer.advance_boundary(opened,1,operation_id='unknown')
        saved = reducer.store.read(opened.context)
        assert saved.state.transition.allocation.status=='unresolved'
        assert {s.instance_id:s.status for s in saved.state.transition.steps} == {'a':'unresolved','b':'unresolved','c':'applied'}
        assert numbers(saved)['balance:material']=='20'
        assert numbers(saved)['balance:labor']=='10'
        assert len(saved.state.transition.request.batch.claims)==2


from typing import get_args
from poliscope_engine.contracts.mechanisms import Domain
from poliscope_engine.domains.conformance import TransitionConformanceCase, run_transition_case


@pytest.mark.parametrize('domain',get_args(Domain))
def test_each_domain_uses_shared_transition_harness_and_hypothetical_counterpart(tmp_path,domain):
    counterpart = 'economy' if domain != 'economy' else 'provisioning'
    with Store(tmp_path) as store:
        reducer,opened,_ = setup(store,domains=(domain,counterpart))
        case = TransitionConformanceCase(values={'processed-a':'8','processed-b':'2'},
            statuses={'a':'applied','b':'applied'},
            accounts={'material':'10','labor':'0','product':'7','residual':'2'})
        result = run_transition_case(case,reducer=reducer,opening=opened,day=1,operation_id='conformance')
        assert result.sequence==1
        assert reducer.store.read(opened.context).state.transition.steps[0].domain == domain


def test_actual_twelve_domain_static_counterparts_keep_missing_transitions_explicit(tmp_path):
    from static_system_fixture import trusted
    from poliscope_engine.domains.static_host import conformance_catalog
    from poliscope_engine.contracts.boundaries import CreateExperiment
    from poliscope_engine.contracts.revisions import CreateRequest
    from poliscope_engine.contracts.transitions import TransitionPlan
    from poliscope_engine.contracts.world import EffectiveTime
    _,_,registry,initial = trusted()
    initial=initial.model_copy(update={'design':initial.design.model_copy(update={
        'effective_time':EffectiveTime(tick=0,calendar_id='fixed-364-v1')})})
    with Store(tmp_path) as store:
        revisions=Revisions(store,registry=registry)
        design=revisions.create(CreateRequest(revision_contract=1,data_store_id=revisions.data_store_id,
            civilization_id='civ',branch_id='main',name='Actual native counterparts',operation_id='create',inputs=initial))
        reducer=TransitionReducer(revisions,catalog=conformance_catalog())
        ids=[i.id for i in initial.design.execution.dependencies.instances]
        request=CreateExperiment.model_validate(dict(boundary_contract=1,
            context=dict(data_store_id=revisions.data_store_id,civilization_id='civ',experiment_id='native'),operation_id='experiment',
            plan=dict(contract_version=1,calendar={},opening_revision=design.context,opening_day=0,
                schedules=[dict(instance_id=i,first_day=1,interval_days=1) for i in ids],events=[],adoptions=[]),conditions=[],
            transition_plan=dict(contract_version=1,opening=None,account_bindings=[],instance_order=ids,
                carry_priority='existing_first',operation_limit=10000)))
        opened=reducer.store.create(request)
        accepted=reducer.advance_boundary(opened,1,operation_id='native-gap')
        saved=reducer.store.read(opened.context)
        assert {s.domain for s in saved.state.transition.steps} == set(get_args(Domain))
        assert {s.status for s in saved.state.transition.steps} == {'coverage_gap'}
        assert saved.state.inputs.values==reducer.store.read(opened.context,0).state.inputs.values
        assert saved.evidence.evaluation.accounts==reducer.store.read(opened.context,0).evidence.evaluation.accounts
        assert accepted.sequence==1


@pytest.mark.parametrize('stage',['proposal','resolution','invariant','closing-evaluation'])
def test_failure_at_each_private_computation_stage_preserves_confirmed_boundary(tmp_path,monkeypatch,stage):
    import poliscope_engine.simulation as runtime
    original=adapter()
    def fail(*args,**kwargs):raise RuntimeError('injected private stage')
    modified=TransitionAdapter(fail if stage=='proposal' else original.propose,
        fail if stage=='resolution' else original.resolve,fail if stage=='invariant' else original.validate)
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':modified})
        if stage=='closing-evaluation':monkeypatch.setattr(reducer.revisions,'_evaluate',fail)
        before=reducer.store.read(opened.context)
        with pytest.raises(RuntimeError,match='injected private stage'):
            reducer.advance_boundary(opened,1,operation_id='failure')
        assert reducer.store.read(opened.context)==before


def test_all_cancellation_checkpoints_in_staging_validation_and_commit_preserve_head(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        calls=0
        completed = False
        complete = store.complete_operation
        def staged(*args, **kwargs):
            nonlocal completed
            complete(*args, **kwargs)
            completed = True
        monkeypatch.setattr(store, 'complete_operation', staged)
        # Count the real checkpoints, canceling after the final staged write.
        def count():
            nonlocal calls
            calls+=1
            return completed
        with pytest.raises(BoundaryError, match='boundary_cancelled'):
            reducer.advance_boundary(opened,1,operation_id='cancel',cancelled=count)
        private_calls=calls
        monkeypatch.setattr(store, 'complete_operation', complete)
        # The checked internal producer is not rerun at confirmation. Each
        # checkpoint that actually precedes its commit must still roll back.
        for target in range(1,private_calls+1):
            seen=0
            def cancel():
                nonlocal seen
                seen+=1
                return seen==target
            with pytest.raises(BoundaryError,match='boundary_cancelled'):
                reducer.advance_boundary(opened,1,operation_id='cancel',cancelled=cancel)
            assert outcome(reducer.store.read(opened.context).record)==opened
        assert reducer.advance_boundary(opened,1,operation_id='cancel').sequence==1


def test_chunks_quota_progress_and_resume_are_confirmed_only(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        observed=[]
        def progress(event):
            assert outcome(reducer.store.read(opened.context).record).boundary_digest==event.boundary_digest
            observed.append(event.day)
        first=reducer.run_chunk(opened,4,operation_prefix='run',max_boundaries=2,progress=progress)
        assert (first.day,first.completed,first.status)==(2,2,'quota')
        current=outcome(reducer.store.read(opened.context).record)
        cancelled=reducer.run_chunk(current,4,operation_prefix='run',max_boundaries=2,cancelled=lambda:True)
        assert cancelled.status=='cancelled' and cancelled.day==2
        resumed=reducer.run_chunk(current,4,operation_prefix='run',max_boundaries=2,progress=progress)
        assert resumed.status=='complete' and observed==[1,2,3,4]
        assert reducer.store.read(opened.context,1).record.day==1


def test_operation_quota_is_not_partial_confirmation(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,operation_limit=1)
        with pytest.raises(TransitionError,match='transition_operation_quota'):
            reducer.advance_boundary(opened,1,operation_id='quota')
        assert outcome(reducer.store.read(opened.context).record)==opened


def test_wrong_or_forged_candidate_cannot_bypass_real_validator(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        candidate=reducer.preview(opened,1)
        altered=candidate.transition.model_dump()
        altered['steps'][0]['reason']='forged'
        from poliscope_engine.contracts.transitions import TransitionReceipt
        altered['receipt_digest']=digest({k:v for k,v in altered.items() if k!='receipt_digest'})
        candidate=candidate.model_copy(update={'transition':TransitionReceipt.model_validate(altered)})
        with pytest.raises(TransitionError,match='transition_candidate_mismatch'):
            reducer.store.confirm(ConfirmBoundary(boundary_contract=1,expected=opened,operation_id='forged',candidate=candidate))
        assert outcome(reducer.store.read(opened.context).record)==opened


@pytest.mark.parametrize('fault',['impure','nondeterministic','foreign-write','wrong-time','bad-precision'])
def test_callback_purity_ownership_time_and_precision_fail_closed(tmp_path,fault):
    from poliscope_engine.world import WorldError
    from poliscope_engine.mechanisms import MechanismError
    from poliscope_engine.numeric import NumericError
    original=adapter()
    serial=0
    def resolve(invocation,proposal):
        nonlocal serial
        writes=original.resolve(invocation,proposal)
        if fault=='impure':invocation.inputs.values.clear()
        if fault=='nondeterministic':
            serial+=1
            writes[0]=writes[0].model_copy(update={'value':writes[0].value.model_copy(update={'value':str(serial)})})
        if fault=='foreign-write':writes[0]=writes[0].model_copy(update={'entity_id':'service-b'})
        if fault=='wrong-time':writes[0]=writes[0].model_copy(update={'effective_time':invocation.inputs.effective_time.model_copy(update={'tick':0})})
        if fault=='bad-precision':writes[0]=writes[0].model_copy(update={'value':writes[0].value.model_copy(update={'value':'0.12345678901234567890123456789'})})
        return writes
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':TransitionAdapter(original.propose,resolve,original.validate)})
        with pytest.raises((TransitionError,MechanismError,WorldError,NumericError)):
            reducer.advance_boundary(opened,1,operation_id='invalid')
        assert outcome(reducer.store.read(opened.context).record)==opened


def test_coupled_allocation_is_retained_as_unresolved_without_single_pass_effects(tmp_path):
    original=adapter()
    def feedback(invocation):
        proposal=original.propose(invocation).model_dump()
        demand=proposal['demands'][0]
        demand['claim']['account_id']='product'
        demand['choice'].update(outputs=[],requirements=[],loss_per_unit='0')
        from poliscope_engine.contracts.transitions import TransitionProposal
        return TransitionProposal.model_validate(proposal)
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'b':TransitionAdapter(feedback,original.resolve,original.validate)})
        reducer.advance_boundary(opened,1,operation_id='feedback')
        saved=reducer.store.read(opened.context)
        assert saved.state.transition.allocation is None
        assert len(saved.state.transition.request.batch.claims)==2
        assert {s.reason for s in saved.state.transition.steps}=={'allocation_feedback_requires_solver'}
        assert numbers(saved)['balance:material']=='20'
        assert numbers(saved)['balance:product']=='0'


def test_completed_reducer_replay_requires_no_current_model_or_callback(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        first=reducer.advance_boundary(opened,1,operation_id='original')
        reducer.advance_boundary(first,2,operation_id='later')
        reader=TransitionReducer(Revisions(store,registry=None),catalog=reducer.catalog)
        assert reader.advance_boundary(opened,1,operation_id='original')==first
        with pytest.raises(TransitionError,match='operation_id_bound_to_different_boundary'):
            reader.advance_boundary(opened,2,operation_id='original')


def test_legacy_v1_state_and_operation_bindings_do_not_gain_optional_field_hashes(tmp_path):
    from test_boundaries import running, confirm_request
    from poliscope_engine.evaluation.identity import serialized
    # The legacy formula is independently pinned to the original v1 field set.
    gen=running.__wrapped__(tmp_path)
    service,create,opened=next(gen)
    try:
        state=service.read(opened.context).state
        assert service.read(opened.context).record.state_digest==digest(state.model_dump(exclude={'transition'}))
        old_create=create.model_dump(exclude={'transition_plan'})
        scope=service._scope(opened.context)
        key=digest(dict(boundary_operation=create.operation_id))
        binding=serialized(dict(boundary_contract=1,kind='create',request_digest=digest(old_create)))
        assert service.store.operation_outcome(scope,key,binding) is not None
        request=confirm_request(service,opened)
        accepted=service.confirm(request)
        legacy=request.model_dump()
        legacy['candidate'].pop('transition')
        binding=serialized(dict(boundary_contract=1,kind='confirm',request_digest=digest(legacy)))
        assert service.store.operation_outcome(scope,digest(dict(boundary_operation=request.operation_id)),binding) is not None
        assert service.confirm(request)==accepted
    finally:
        try:next(gen)
        except StopIteration:pass


@pytest.mark.parametrize('after_commit',[False,True])
def test_reducer_real_process_crash_preserves_only_confirmed_state_and_receipt(tmp_path,after_commit):
    import subprocess,sys,os
    from pathlib import Path
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        path=tmp_path/'opening.json'
        path.write_text(opened.model_dump_json())
        code='''
from pathlib import Path
from contextlib import contextmanager
import os,sys
from transition_fixture import fixture
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.contracts.boundaries import BoundaryOutcome
mechanisms,catalog,_,_=fixture()
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
        run= subprocess.run([sys.executable,'-c',code,str(tmp_path),str(path),'after' if after_commit else 'before'],
            env=env,capture_output=True,text=True)
        assert run.returncode==(82 if after_commit else 81),run.stderr
        saved=reducer.store.read(opened.context)
        assert saved.record.sequence==int(after_commit)
        assert (saved.state.transition is not None)==after_commit
        result=reducer.advance_boundary(opened,1,operation_id='crash')
        assert result.sequence==1
        assert numbers(reducer.store.read(opened.context))['balance:material']=='10'


def test_failure_after_each_transition_storage_write_rolls_back_receipt_and_resources(tmp_path,monkeypatch):
    from test_revisions import count
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        original={n:getattr(store,n) for n in ['add_record','retain_evidence','complete_operation']}
        before=count(reducer.revisions)
        writes=[]
        for name,callback in original.items():
            def track(*args,_callback=callback,_name=name,**kwargs):
                writes.append(_name)
                return _callback(*args,**kwargs)
            monkeypatch.setattr(store,name,track)
        # Reach all writes, then cancel just before commit.
        with pytest.raises(BoundaryError,match='boundary_cancelled'):
            reducer.advance_boundary(opened,1,operation_id='fault',cancelled=lambda:bool(writes))
        total=len(writes)
        assert total>=5
        for failure in range(1,total+1):
            seen=[]
            for name,callback in original.items():
                def fail(*args,_callback=callback,_name=name,**kwargs):
                    result=_callback(*args,**kwargs)
                    seen.append(_name)
                    if len(seen)==failure:raise RuntimeError('write fault')
                    return result
                monkeypatch.setattr(store,name,fail)
            with pytest.raises(RuntimeError,match='write fault'):
                reducer.advance_boundary(opened,1,operation_id='fault')
            assert count(reducer.revisions)==before
            assert outcome(reducer.store.read(opened.context).record)==opened


def test_exact_balance_oracle_rejects_corrupt_allocation_before_publication(tmp_path,monkeypatch):
    import poliscope_engine.simulation as runtime
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        original=runtime.allocate
        def forged(*args,**kwargs):
            result=original(*args,**kwargs)
            rows=list(result.accounts.accounts)
            rows[0]=rows[0].model_copy(update={'closing':'999'})
            return result.model_copy(update={'accounts':result.accounts.model_copy(update={'accounts':rows})})
        monkeypatch.setattr(runtime,'allocate',forged)
        with pytest.raises(TransitionError,match='exact_transition_balance_failure'):
            reducer.advance_boundary(opened,1,operation_id='corrupt')
        assert outcome(reducer.store.read(opened.context).record)==opened


def test_denial_and_missing_procedure_never_create_capacity_or_default_priority(tmp_path):
    with Store(tmp_path) as store:
        reducer,opened,request=setup(store,adapters={'a':adapter(access='denied')})
        reducer.advance_boundary(opened,1,operation_id='denied')
        saved=reducer.store.read(opened.context)
        assert numbers(saved)['processed-a']=='0' and numbers(saved)['processed-b']=='8'
        assert numbers(saved)['balance:labor']=='2'
        plan=request.transition_plan
        unknown=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'unknown-procedure'}),
            'transition_plan':plan.model_copy(update={'opening':plan.opening.model_copy(update={'procedure':None})})})
        other=reducer.store.create(unknown)
        reducer.advance_boundary(other,1,operation_id='unknown')
        saved=reducer.store.read(other.context)
        assert saved.state.transition.allocation.missing==['procedure']
        assert numbers(saved)['balance:labor']=='10'
        assert numbers(saved)['processed-b']=='0'


import json
from pathlib import Path
CLASS_CASES=json.loads((Path(__file__).parents[1]/'fixtures/domains/transitions-v1.json').read_text())['cases']


@pytest.mark.parametrize('case',CLASS_CASES,ids=lambda c:c['class'])
def test_selected_transition_classes_have_distinct_bounded_models_and_counterpart_oracles(tmp_path,case):
    from poliscope_engine.contracts.transitions import TransitionProposal
    from poliscope_engine.numeric import canonical,exact
    base=adapter()
    def propose(invocation):
        return base.propose(invocation).model_copy(update={'transition_class':case['class']})
    def expected(invocation):
        old=next(v for v in invocation.inputs.values if v.entity_id==invocation.instance.entity_id)
        actual={a.claim_id:Fraction(a.allocated) for a in invocation.allocation.actuals}
        change=sum((actual[c] for c in invocation.claim_ids),Fraction())*Fraction(case['coefficient'])
        number=Fraction(old.value.value)+(change if case['operation']=='add' else -change)
        return old,max(Fraction(case['lower']),min(Fraction(case['upper']),number))
    def resolve(invocation,proposal):
        old,number=expected(invocation)
        return [old.model_copy(update={'value':old.value.model_copy(update={'value':canonical(exact(number))}),
            'effective_time':invocation.inputs.effective_time})]
    def validate(invocation,proposal,writes,closing):
        old,number=expected(invocation)
        assert Fraction(writes[0].value.value)==number
        assert Fraction(case['lower'])<=number<=Fraction(case['upper'])
        assert next(v for v in closing.values if v.id==old.id)==writes[0]
    model=TransitionAdapter(propose,resolve,validate)
    counterpart='economy' if case['domain']!='economy' else 'provisioning'
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,domains=(case['domain'],counterpart),adapters={'a':model,'b':model},
            state_units={'a':case['unit'],'b':case['unit']},state_openings={'a':case['opening'],'b':case['opening']})
        oracle=TransitionConformanceCase(values={'processed-a':case['expected_a'],'processed-b':case['expected_b']},
            statuses={'a':'applied','b':'applied'},accounts={'material':'10','labor':'0','product':'7','residual':'2'})
        run_transition_case(oracle,reducer=reducer,opening=opened,day=1,operation_id='class')
        saved=reducer.store.read(opened.context)
        assert {s.transition_class for s in saved.state.transition.steps}=={case['class']}
        assert saved.state.inputs.versions==reducer.store.read(opened.context,0).state.inputs.versions


def test_due_event_conditions_reach_models_before_any_effect_and_remain_private(tmp_path):
    from poliscope_engine.contracts.timeline import DatedEvent
    original=adapter()
    service=None
    observed=[]
    def propose(invocation):
        assert reducer.store.read(opened.context).record.day==0
        assert reducer.store.read(opened.context).state.conditions==[]
        observed.append('proposal')
        result=original.propose(invocation).model_dump()
        denied=any(c.condition_id=='access' and c.value.kind=='label' and c.value.value=='denied' for c in invocation.conditions)
        result['demands'][0]['choice']['access']='denied' if denied else 'allowed'
        from poliscope_engine.contracts.transitions import TransitionProposal
        return TransitionProposal.model_validate(result)
    with Store(tmp_path) as store:
        reducer,initial,request=setup(store,adapters={'a':TransitionAdapter(propose,original.resolve,original.validate)})
        event=dict(id='dated-access',effective_day=1,order=0,origin='player_authored',source_refs=[],changes=[
            dict(scope_id='local',condition_id='access',expected_digest=None,value=dict(kind='label',value='denied'))])
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'events'}),
            'plan':request.plan.model_copy(update={'events':[DatedEvent.model_validate(event)]})})
        opened=reducer.store.create(changed)
        reducer.advance_boundary(opened,1,operation_id='event')
        saved=reducer.store.read(opened.context)
        assert numbers(saved)['processed-a']=='0' and numbers(saved)['processed-b']=='8'
        assert saved.record.changes.events[0].status=='applied'
        assert saved.state.conditions[0].value.value=='denied'
        assert observed==['proposal']*2  # detached deterministic callback repeat


def test_callbacks_use_fresh_decimal_context_and_never_leak_precision(tmp_path):
    from decimal import getcontext,localcontext
    original=adapter()
    def resolve(invocation,proposal):
        getcontext().prec=2
        return original.resolve(invocation,proposal)
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':TransitionAdapter(original.propose,resolve,original.validate)})
        with localcontext() as external:
            external.prec=5
            reducer.advance_boundary(opened,1,operation_id='precision')
            assert getcontext().prec==5
        assert numbers(reducer.store.read(opened.context))['balance:product']=='7'


def test_existing_obligation_reservation_and_selected_precedence_survive_boundaries(tmp_path):
    from test_allocations import claim,choice
    with Store(tmp_path) as store:
        reducer,_,request=setup(store)
        book=request.transition_plan.opening.model_dump()
        book['batch']['claims']=[claim('existing','4','material')|{'claimant_id':'service-a'}]
        book['batch']['reservations']=[dict(id='protected',account_id='material',claim_id='existing',amount='4')]
        book['choices']=[choice('existing',source_refs=['synthetic:source'])]
        book['claim_order']=['existing']
        from poliscope_engine.contracts.allocations import AllocationRequest
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'held'}),
            'transition_plan':request.transition_plan.model_copy(update={'opening':AllocationRequest.model_validate(book)})})
        opened=reducer.store.create(changed)
        first=reducer.advance_boundary(opened,1,operation_id='held')
        saved=reducer.store.read(opened.context)
        existing=next(a for a in saved.state.transition.allocation.actuals if a.claim_id=='existing')
        assert existing.allocated=='4'
        assert numbers(saved)['balance:material']=='6'
        assert saved.state.transition.allocation.batch.reservations[0].amount=='4'
        reducer.advance_boundary(first,2,operation_id='next')
        saved=reducer.store.read(opened.context)
        assert numbers(saved)['balance:material']=='6'
        assert all(c.claim_id!='existing' for c in saved.state.transition.allocation.accounts.claims)
        assert next(c for c in reducer.store.read(opened.context,1).state.transition.allocation.accounts.claims if c.claim_id=='existing').unmet=='0'


@pytest.mark.parametrize('bad',['alias','owner','quantity'])
def test_account_aliases_foreign_ownership_and_opening_mismatch_fail_before_experiment(tmp_path,bad):
    from pydantic import ValidationError
    with Store(tmp_path) as store:
        reducer,_,request=setup(store)
        plan=request.transition_plan.model_dump()
        if bad=='alias':plan['account_bindings'][1]['value_id']=plan['account_bindings'][0]['value_id']
        elif bad=='owner':plan['account_bindings'][0]['value_id']='amount'
        else:plan['opening']['batch']['accounts'][0]['opening']='999'
        changed=request.model_dump()
        changed['context']['experiment_id']='invalid'
        changed['transition_plan']=plan
        from poliscope_engine.contracts.boundaries import CreateExperiment
        with pytest.raises((TransitionError,ValidationError)):
            reducer.store.create(CreateExperiment.model_validate(changed))
        with pytest.raises(BoundaryError,match='unknown_experiment'):
            reducer.store.read(request.context.model_copy(update={'experiment_id':'invalid'}))


def test_multirate_chunk_retains_intermediate_gap_even_when_last_boundary_is_supported(tmp_path):
    with Store(tmp_path) as store:
        reducer,_,request=setup(store,missing=['b'])
        schedules=[s if s.instance_id=='a' else s.model_copy(update={'interval_days':7}) for s in request.plan.schedules]
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'multirate'}),
            'plan':request.plan.model_copy(update={'schedules':schedules})})
        opened=reducer.store.create(changed)
        result=reducer.run_chunk(opened,2,operation_prefix='multi',max_boundaries=2)
        assert result.status=='complete' and result.coverage=='partial'
        assert reducer.store.read(opened.context,1).state.transition.coverage=='partial'
        assert reducer.store.read(opened.context,2).state.transition.coverage=='complete'


def test_paused_pending_claim_keeps_original_terms_and_reactivates_only_with_due_owner(tmp_path):
    with Store(tmp_path) as store:
        reducer,_,request=setup(store)
        schedules=[s if s.instance_id=='a' else s.model_copy(update={'interval_days':7}) for s in request.plan.schedules]
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'pending'}),
            'plan':request.plan.model_copy(update={'schedules':schedules})})
        opened=reducer.store.create(changed)
        first=reducer.advance_boundary(opened,1,operation_id='first')
        receipt=reducer.store.read(opened.context).state.transition
        pending=next(o.claim_id for o in receipt.claim_owners if o.instance_id=='b')
        second=reducer.advance_boundary(first,2,operation_id='paused')
        receipt=reducer.store.read(opened.context).state.transition
        assert next(o.choice.access for o in receipt.claim_owners if o.claim_id==pending)=='allowed'
        assert next(c.access for c in receipt.request.choices if c.claim_id==pending)=='unknown'
        assert receipt.coverage=='unresolved'
        reducer.run_chunk(second,8,operation_prefix='resume',max_boundaries=10)
        receipt=reducer.store.read(opened.context).state.transition
        assert next(c.access for c in receipt.request.choices if c.claim_id==pending)=='allowed'
        assert pending in next(s.claim_ids for s in receipt.steps if s.instance_id=='b')


def test_duplicate_state_slot_cannot_be_aliased_by_a_second_value_id(tmp_path):
    original=adapter()
    def resolve(invocation,proposal):
        writes=original.resolve(invocation,proposal)
        return [writes[0],writes[0].model_copy(update={'id':'different-id-same-slot'})]
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':TransitionAdapter(original.propose,resolve,original.validate)})
        with pytest.raises(TransitionError,match='conflicting_or_mistimed_transition_write'):
            reducer.advance_boundary(opened,1,operation_id='alias')
        assert outcome(reducer.store.read(opened.context).record)==opened


def test_reviewed_transition_only_instance_needs_no_fake_static_execution(tmp_path):
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    from poliscope_engine.domains import DomainRegistry
    from test_mechanism_registry import registry
    from transition_fixture import start
    mechanisms,catalog,initial,plan=fixture()
    definitions=[d.model_dump() for d in mechanisms.definitions]
    definitions[0]['support']['static']=None
    modules=[m.model_dump() for m in catalog.modules]
    next(m for m in modules if m['domain']=='infrastructure')['coverage'][0]['static_available']=False
    from poliscope_engine.contracts.domains import DomainModule
    catalog=DomainRegistry([DomainModule.model_validate(m) for m in modules])
    mechanisms=registry([MechanismDefinition.model_validate(d) for d in definitions],
        implementations=mechanisms.implementations,units=mechanisms.units,times=mechanisms.times)
    instances=initial.design.execution.dependencies.instances
    a=next(i for i in instances if i.id=='a')
    dependency=initial.design.execution.dependencies.model_copy(update={'instances':[i for i in instances if i.id!='a']})
    initial=initial.model_copy(update={'design':initial.design.model_copy(update={
        'execution':initial.design.execution.model_copy(update={'dependencies':dependency})})})
    plan=plan.model_copy(update={'instances':[a]})
    with Store(tmp_path) as store:
        reducer,opened,_=start(store,mechanisms,catalog,initial,plan)
        reducer.advance_boundary(opened,1,operation_id='transition-only')
        assert numbers(reducer.store.read(opened.context))['processed-a']=='8'
        assert reducer.store.read(opened.context).state.transition.coverage=='complete'


@pytest.mark.parametrize('failure,value,expected_a,expected_b,status',[
    ('not_applicable','0','0','8','not_applicable'),('conflict','0','0','0','unresolved'),
    ('not_applicable','2','8','2','applied')])
def test_declared_preconditions_gate_effects_without_creating_a_default_winner(tmp_path,failure,value,expected_a,expected_b,status):
    from transition_fixture import start
    from test_mechanism_registry import registry
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    from poliscope_engine.contracts.domains import DomainModule
    from poliscope_engine.domains import DomainRegistry
    from poliscope_engine.contracts.revisions import RevisionInputs
    from test_dependencies import Q
    mechanisms,catalog,initial,plan=fixture()
    definitions=[d.model_dump() for d in mechanisms.definitions]
    d=definitions[0]
    d['inputs']=[dict(id='synthetic:enabled',value_type=Q,required=True,missing_behavior='propagate')]
    d['outputs'][0]['input_refs']=['synthetic:enabled']
    d['preconditions']=[dict(id='synthetic:eligible',input_refs=['synthetic:enabled'],description='Synthetic explicit gate',failure_behavior=failure)]
    modules=[m.model_dump() for m in catalog.modules]
    module=next(m for m in modules if m['domain']=='infrastructure')
    module['interfaces'].append(dict(id='infrastructure:guard',mechanism=dict(id=d['id'],version=d['version']),
        port_id='synthetic:enabled',direction='input',value_type=Q,references=[dict(entity_id='material',entity_kind='account')]))
    catalog=DomainRegistry([DomainModule.model_validate(m) for m in modules])
    mechanisms=registry([MechanismDefinition.model_validate(d) for d in definitions],implementations=mechanisms.implementations,units=mechanisms.units,times=mechanisms.times)
    raw=initial.model_dump()
    raw['design']['execution']['dependencies']['fixed_inputs']=[dict(consumer=dict(instance_id='a',port_id='synthetic:enabled'),value=dict(Q,value=value))]
    raw['design']['conditions']=[dict(identity=dict(id='synthetic:gate',version='v1'),instance_id='a',
        precondition_id='synthetic:eligible',input_id='synthetic:enabled',operation='ge',value=dict(Q,value='1'))]
    with Store(tmp_path) as store:
        reducer,opened,_=start(store,mechanisms,catalog,RevisionInputs.model_validate(raw),plan)
        reducer.advance_boundary(opened,1,operation_id='guard')
        saved=reducer.store.read(opened.context)
        assert numbers(saved)['processed-a']==expected_a and numbers(saved)['processed-b']==expected_b
        assert next(s.status for s in saved.state.transition.steps if s.instance_id=='a')==status


def test_selected_model_with_unknown_footprint_does_not_become_zero_demand(tmp_path):
    from poliscope_engine.simulation import TransitionUnresolved
    original=adapter()
    def unresolved(invocation):raise TransitionUnresolved('unknown quantity')
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':TransitionAdapter(unresolved,original.resolve,original.validate)})
        reducer.advance_boundary(opened,1,operation_id='unresolved')
        saved=reducer.store.read(opened.context)
        assert numbers(saved)['balance:material']=='20'
        assert saved.state.transition.coverage=='unresolved'
        assert next(s.status for s in saved.state.transition.steps if s.instance_id=='b')=='unresolved'


def test_real_closing_static_solver_failure_discards_all_dynamic_effects(tmp_path):
    from transition_fixture import start
    from test_mechanism_registry import registry
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    from poliscope_engine.contracts.domains import DomainModule
    from poliscope_engine.contracts.revisions import RevisionInputs
    from poliscope_engine.domains import DomainRegistry
    from poliscope_engine.mechanisms import Implementation
    from test_dependencies import Q
    mechanisms,catalog,initial,plan=fixture()
    definitions=[d.model_dump() for d in mechanisms.definitions]
    d=definitions[1]
    d['inputs']=[dict(id='synthetic:input',value_type=Q,required=True,missing_behavior='propagate')]
    d['outputs'][0]['input_refs']=['synthetic:input']
    modules=[m.model_dump() for m in catalog.modules]
    next(m for m in modules if m['domain']=='knowledge_culture')['interfaces'].append(dict(
        id='knowledge:guard',mechanism=dict(id=d['id'],version=d['version']),port_id='synthetic:input',direction='input',
        value_type=Q,references=[dict(entity_id='material',entity_kind='account')]))
    def static(port,inputs):
        if 'synthetic:input' in inputs and inputs['synthetic:input'].value!='0':raise ArithmeticError('selected fixture failure')
        return dict(Q,value='0')
    implementations=[Implementation(i.id,i.version,i.phase,static if i.phase=='static' else i.callback) for i in mechanisms.implementations]
    mechanisms=registry([MechanismDefinition.model_validate(d) for d in definitions],implementations=implementations,units=mechanisms.units,times=mechanisms.times)
    catalog=DomainRegistry([DomainModule.model_validate(m) for m in modules])
    raw=initial.model_dump()
    raw['design']['world_inputs']=[dict(consumer=dict(instance_id='b',port_id='synthetic:input'),value_id='processed-b')]
    with Store(tmp_path) as store:
        reducer,opened,_=start(store,mechanisms,catalog,RevisionInputs.model_validate(raw),plan)
        with pytest.raises(TransitionError,match='closing_solver_failure'):
            reducer.advance_boundary(opened,1,operation_id='solver-failure')
        assert outcome(reducer.store.read(opened.context).record)==opened
        assert numbers(reducer.store.read(opened.context))['balance:material']=='20'


@pytest.mark.parametrize('kind',['unknown','denied','coefficient'])
def test_pending_claim_refinement_requires_own_prior_binding_and_cannot_reauthorize_terms(tmp_path,kind):
    from poliscope_engine.contracts.transitions import TransitionProposal
    from poliscope_engine.contracts.timeline import DatedEvent
    original=adapter(access='denied' if kind=='denied' else 'unknown')
    def propose(invocation):
        result=original.propose(invocation).model_dump()
        if invocation.pending_claims:
            result['demands']=[]
            ready=any(c.condition_id=='verified' and c.value.kind=='label' and c.value.value=='yes' for c in invocation.conditions)
            if ready:
                result['refinements']=[]
                for owner in invocation.pending_claims:
                    replacement=owner.choice.model_copy(update={'access':'allowed'})
                    if kind=='coefficient':replacement=replacement.model_copy(update={'loss_per_unit':'0'})
                    result['refinements'].append(dict(claim_id=owner.claim_id,
                        expected_digest=digest(owner.choice),replacement=replacement))
        return TransitionProposal.model_validate(result)
    with Store(tmp_path) as store:
        reducer,_,request=setup(store,adapters={'a':TransitionAdapter(propose,original.resolve,original.validate)})
        event=DatedEvent.model_validate(dict(id='verified-condition',effective_day=2,order=0,origin='external',source_refs=[],
            changes=[dict(scope_id='local',condition_id='verified',expected_digest=None,value=dict(kind='label',value='yes'))]))
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'refinement'}),
            'plan':request.plan.model_copy(update={'events':[event]})})
        opened=reducer.store.create(changed)
        first=reducer.advance_boundary(opened,1,operation_id='first')
        original_receipt=reducer.store.read(opened.context).state.transition
        if kind!='unknown':
            with pytest.raises(TransitionError,match='invalid_pending_refinement'):
                reducer.advance_boundary(first,2,operation_id='refine')
            assert outcome(reducer.store.read(opened.context).record)==first
        else:
            assert original_receipt.coverage=='unresolved'
            reducer.advance_boundary(first,2,operation_id='refine')
            saved=reducer.store.read(opened.context)
            assert numbers(saved)['processed-a']=='8' and numbers(saved)['processed-b']=='2'
            assert saved.state.transition.coverage=='complete'
            assert next(s.refined_claim_ids for s in saved.state.transition.steps if s.instance_id=='a')
            assert digest(reducer.store.read(opened.context,1).state.transition)==digest(original_receipt)


def test_unordered_book_storage_does_not_change_semantic_transition_identity(tmp_path):
    from poliscope_engine.timeline import boundaries
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store)
        opening=reducer.store.read(opened.context)
        _,experiment=reducer.store._experiment(opened.context)
        due=next(boundaries(experiment.plan,1))
        first=reducer._reduce(opening,experiment,due)
        plan=experiment.transition_plan
        permuted=plan.model_copy(update={'account_bindings':list(reversed(plan.account_bindings)),
            'opening':plan.opening.model_copy(update={'batch':plan.opening.batch.model_copy(update={
                'accounts':list(reversed(plan.opening.batch.accounts))})})})
        assert digest(plan)==digest(permuted)
        other=reducer._reduce(opening,experiment.model_copy(update={'transition_plan':permuted}),due)
        assert digest(first)==digest(other)


def test_actual_year_fast_forward_keeps_intermediate_daily_unmet_work(tmp_path):
    original=adapter()
    def propose(invocation):
        result=original.propose(invocation)
        # Two finite opening cases; the original dated work book never renews
        # merely because the display target is a year. Remaining case B is retried.
        return result if invocation.day==1 else result.model_copy(update={'demands':[]})
    selected=TransitionAdapter(propose,original.resolve,original.validate)
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':selected,'b':selected})
        result=reducer.run_chunk(opened,364,operation_prefix='year',max_boundaries=364)
        assert result.status=='complete' and result.day==364 and result.completed==364
        intermediate=reducer.store.read(opened.context,3)
        assert intermediate.record.day==3
        assert sum(Fraction(a.unmet) for a in intermediate.state.transition.allocation.actuals)==6
        assert numbers(intermediate)['balance:labor']=='0'
        assert numbers(intermediate)['balance:material']=='10'
        assert numbers(reducer.store.read(opened.context))['processed-b']=='2'
        assert next(w.period_id for w in intermediate.state.transition.balances if w.account_id=='labor')=='opening-day:0'


def test_player_goals_and_notes_are_absent_from_callback_views_and_cannot_change_physics(tmp_path):
    from poliscope_engine.contracts.revisions import PreviewRequest,ApplyRequest
    original=adapter()
    def propose(invocation):
        assert not hasattr(invocation.inputs,'goals') and not hasattr(invocation.inputs,'notes')
        assert not hasattr(invocation.inputs,'measurements') and not hasattr(invocation.inputs,'design')
        assert invocation.inputs.policies is None and invocation.inputs.assumptions is None
        assert {v.partition for v in invocation.inputs.values}=={'dynamic_state'}
        return original.propose(invocation)
    def validate(invocation,proposal,writes,closing):
        assert not hasattr(closing,'goals') and not hasattr(closing,'notes')
        assert all(v.partition!='goals' for v in closing.values)
        original.validate(invocation,proposal,writes,closing)
    selected=TransitionAdapter(propose,original.resolve,validate)
    with Store(tmp_path) as store:
        reducer,opened,request=setup(store,adapters={'a':selected})
        revisions=reducer.revisions
        base=revisions.read(request.plan.opening_revision)
        inputs=base.inputs.model_dump()
        inputs['goals']=[dict(id='synthetic:goal',kind='narrative',question='Synthetic desired target; not a physical input.',
            indicator_id=None,operation=None,threshold=None)]
        preview=PreviewRequest.model_validate(dict(revision_contract=1,context=base.context,
            changes=[dict(kind='replace_inputs',inputs=inputs)],decision=dict(alternatives=[],selected_id=None,rationale_ref=None)))
        candidate=revisions.preview(preview)
        accepted=revisions.apply(ApplyRequest(revision_contract=1,operation_id='goal-edit',preview=preview,candidate_digest=candidate.candidate_digest))
        changed=request.model_copy(update={'context':request.context.model_copy(update={'experiment_id':'goal-edit'}),
            'plan':request.plan.model_copy(update={'opening_revision':accepted.context})})
        other=reducer.store.create(changed)
        a,b=reducer.preview(opened,1),reducer.preview(other,1)
        assert a.evidence.evaluation.identities==b.evidence.evaluation.identities
        assert digest(a.transition.allocation)==digest(b.transition.allocation)
        assert digest(a.transition.steps)==digest(b.transition.steps)
        assert a.evidence.report.goals!=b.evidence.report.goals


def test_fulfilled_history_does_not_create_an_active_book_horizon():
    from poliscope_engine.simulation import _carry_book
    from poliscope_engine.allocations import allocate
    from poliscope_engine.contracts.allocations import AllocationRequest
    from poliscope_engine.contracts.accounts import AccountClaim
    from poliscope_engine.contracts.transitions import TransitionClaimOwner
    from test_allocations import choice
    mechanisms,_,_,plan=fixture()
    base=plan.opening
    for i in range(1200):
        cid='completed:'+str(i)
        selected=base.model_dump()
        selected['batch']['claims']=[dict(id=cid,account_id='material',claimant_id='service-a',requested='0.01',source_refs=[])]
        terms=choice(cid,mechanism_ref='synthetic:model/infrastructure',source_refs=['synthetic:source'])
        selected.update(choices=[terms],claim_order=[cid])
        request=AllocationRequest.model_validate(selected)
        actual=allocate(request,mechanisms.units)
        owner=TransitionClaimOwner(instance_id='a',claim_id=cid,choice=request.choices[0],original_requested='0.01',fulfilled_prior='0')
        base,owners=_carry_book(request,actual.batch,{cid:owner},mechanisms.units)
        assert not base.batch.claims and not base.batch.postings and not owners
    assert next(a.opening for a in base.batch.accounts if a.id=='material')=='8'
    assert next(a.opening for a in base.batch.accounts if a.id=='labor')=='10'


def test_declared_policy_reads_receive_resolved_conflicts_not_a_binding_order_default(tmp_path):
    from transition_fixture import start
    from test_policies import definition as policy_definition,binding,edge
    from test_mechanism_registry import registry,PROVENANCE
    from poliscope_engine.contracts.mechanisms import MechanismDefinition
    from poliscope_engine.contracts.revisions import RevisionInputs
    original=adapter()
    def propose(invocation):
        assert invocation.inputs.policies.results[0].status=='conflict'
        assert invocation.inputs.policies.results[0].value is None
        return original.propose(invocation).model_copy(update={'status':'unresolved','reason':'policy_conflict'})
    mechanisms,catalog,initial,plan=fixture(adapters={'a':TransitionAdapter(propose,original.resolve,original.validate)})
    definitions=list(mechanisms.definitions)
    definitions[0]=definitions[0].model_copy(update={'read_partitions':['dynamic_state','design']})
    policy=policy_definition()
    policy_host=registry([policy],units=mechanisms.units,times=mechanisms.times)
    mechanisms=registry([*definitions,policy],implementations=[*mechanisms.implementations,*policy_host.implementations],
        units=mechanisms.units,times=mechanisms.times)
    data=initial.model_dump()
    data['entities'].append(dict(id='local-authority',entity_kind='institution',label='Synthetic authority',provenance=PROVENANCE))
    data['relationships'].append(edge('jurisdiction','local-authority','local').model_dump())
    data['design']['policies']=[binding(i,entity_ids=['service-a'],account_refs=['material'],choice_refs=[],
        value=dict(kind='quantity',value=n,unit_id='kg',time_basis_id=None,denominator_scope_id=None)).model_dump()
        for i,n in [('conflict-a','2'),('conflict-b','7')]]
    with Store(tmp_path) as store:
        reducer,opened,_=start(store,mechanisms,catalog,RevisionInputs.model_validate(data),plan)
        reducer.advance_boundary(opened,1,operation_id='policy-conflict')
        saved=reducer.store.read(opened.context)
        assert saved.state.transition.coverage=='unresolved'
        assert numbers(saved)['balance:material']=='20'
        assert {s.status for s in saved.state.transition.steps}=={'unresolved'}


@pytest.mark.parametrize('injection',['none','io','clock','random'])
def test_purity_fixture_guards_detect_injected_external_effects_inside_callbacks(tmp_path,monkeypatch,injection):
    import builtins,time,random
    original=adapter()
    def forbidden(*args,**kwargs):raise RuntimeError('forbidden callback effect')
    def guarded(callback,*args):
        with monkeypatch.context() as patch:
            patch.setattr(builtins,'open',forbidden)
            patch.setattr(time,'time',forbidden)
            patch.setattr(random,'random',forbidden)
            return callback(*args)
    def propose(invocation):
        if injection=='io':builtins.open('never-created')
        if injection=='clock':time.time()
        if injection=='random':random.random()
        return original.propose(invocation)
    selected=TransitionAdapter(lambda invocation:guarded(propose,invocation),
        lambda invocation,proposal:guarded(original.resolve,invocation,proposal),
        lambda *args:guarded(original.validate,*args))
    with Store(tmp_path) as store:
        reducer,opened,_=setup(store,adapters={'a':selected})
        if injection=='none':
            assert reducer.advance_boundary(opened,1,operation_id='pure').sequence==1
        else:
            with pytest.raises(RuntimeError,match='forbidden callback effect'):
                reducer.advance_boundary(opened,1,operation_id='impure')
            assert outcome(reducer.store.read(opened.context).record)==opened
