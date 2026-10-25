"""WP-036 workflows over the actual transition/revision/SQLite providers."""
import pytest
from poliscope_engine.boundaries import BoundaryError, BoundaryStore, outcome
from poliscope_engine.contracts.boundaries import CreateExperiment
from poliscope_engine.contracts.experiments import (
    StartExperiment, AdvanceExperiment, ControlExperiment, ForkExperiment, ReplayExperiment)
from poliscope_engine.contracts.timeline import TimelinePlan
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.experiments import Experiments
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.revisions import Revisions
from poliscope_engine.storage import Store
from transition_fixture import fixture, start


def setup(store, interval=2):
    reducer, _, original = start(store, *fixture())
    service = Experiments(reducer)
    request = CreateExperiment.model_validate(original.model_dump() | dict(
        context=original.context.model_dump() | dict(experiment_id='controlled'), operation_id='controlled-create'))
    opening = service.create(StartExperiment(request=request, checkpoint_interval=interval))
    return service, opening, request


def advance(opening, target=4, operation='advance', quota=100):
    return AdvanceExperiment(expected=opening, target_day=target, operation_id=operation, max_boundaries=quota)


def replay(context, sequence, mode='recorded', quota=1000):
    return ReplayExperiment(context=context, sequence=sequence, mode=mode, max_boundaries=quota)


def fork_request(service, source, name='fork', **updates):
    _, parent = service.boundaries._experiment(source.context)
    plan = TimelinePlan.model_validate(parent.plan.model_dump() | dict(opening_day=source.day,
        events=[e for e in parent.plan.events if e.effective_day > source.day],
        adoptions=[a for a in parent.plan.adoptions if a.effective_day > source.day]))
    return ForkExperiment.model_validate(dict(operation_id='fork-operation', source=source,
        context=source.context.model_copy(update={'experiment_id':name}), plan=plan,
        checkpoint_interval=2, realization_policy='preserve') | updates)


def test_continuous_checkpoint_resume_and_model_free_recorded_replay(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        result = service.advance(advance(opening))
        expected = service.boundaries.read(opening.context)
        assert result.head.day == 4
        assert [c.boundary.sequence for c in service.checkpoints(opening.context)] == [0,2,4]
        assert service.replay(replay(opening.context,3,'verify')).record.sequence == 3
        assert digest(service.replay(replay(opening.context,4)).state) == digest(expected.state)
        registry, catalog = service.reducer.mechanisms, service.reducer.catalog
    with Store(tmp_path) as store:
        service = Experiments(TransitionReducer(Revisions(store,registry=registry),catalog=catalog))
        resumed = service.advance(advance(result.head,6,operation='resumed'))
        final = service.boundaries.read(opening.context)
        assert resumed.head.day == 6
        reference = service.reducer._reduce(service.boundaries.read(opening.context,5),
            service.boundaries._experiment(opening.context)[1], final.record.due)
        assert digest(reference.inputs) == digest(final.state.inputs)
    with Store(tmp_path) as store:
        service = Experiments(TransitionReducer(Revisions(store,registry=None),catalog=None))
        assert service.advance(advance(opening)) == result
        assert service.status(advance(opening)) == result
        assert digest(service.replay(replay(opening.context,3)).evidence) == digest(
            service.boundaries.read(opening.context,3).evidence)
        with pytest.raises(BoundaryError,match='historical_runtime_unavailable'):
            service.replay(replay(opening.context,3,'verify'))


def test_pause_resume_cancel_and_payload_bound_retries(tmp_path):
    with Store(tmp_path) as store:
        service, opening, request = setup(store)
        _, control, _ = service.query(opening.context)
        pause = ControlExperiment(context=opening.context,operation_id='pause',expected=control,state='paused')
        paused = service.control(pause)
        assert service.control(pause) == paused
        result = service.advance(advance(opening))
        assert result.status == 'paused' and result.completed == 0
        service.control(ControlExperiment(context=opening.context,operation_id='resume',expected=paused,state='ready'))
        result = service.advance(advance(opening,operation='resume-advance'))
        assert result.head.day == 4
        with pytest.raises(Exception,match='payload|binding|different'):
            service.advance(advance(opening,target=5,operation='resume-advance'))
        with pytest.raises(Exception,match='payload|binding|different'):
            service.create(StartExperiment(request=request,checkpoint_interval=3))
        _, control, _ = service.query(opening.context)
        cancelled = service.control(ControlExperiment(context=opening.context,operation_id='cancel',expected=control,state='cancelled'))
        assert service.advance(advance(result.head,5,operation='after-cancel')).status == 'cancelled'
        with pytest.raises(BoundaryError,match='requires_fork'):
            service.control(ControlExperiment(context=opening.context,operation_id='restart',expected=cancelled,state='ready'))
        assert service.fork(fork_request(service,result.head)).day == 4


def test_retrospective_fork_preserves_stocks_pending_work_and_original_history(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        original = service.advance(advance(opening,target=5))
        source = service.boundaries.read(opening.context,1)
        request = fork_request(service,outcome(source.record))
        forked = service.fork(request)
        assert service.fork(request) == forked
        assert digest(service.boundaries.read(forked.context).state) == digest(source.state)
        fork_result = service.advance(advance(forked,5,operation='fork-advance'))
        child = service.boundaries.read(fork_result.head.context)
        parent = service.boundaries.read(original.head.context)
        assert digest(child.state.inputs) == digest(parent.state.inputs)
        assert digest(child.state.transition.allocation) == digest(parent.state.transition.allocation)
        assert outcome(parent.record) == original.head
        assert service.query(forked.context)[0].origin == outcome(source.record)
        assert len(service.checkpoints(opening.context)) == 3


def test_chunk_quota_cancel_and_reentrant_reads_never_expose_staging(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store,interval=5)
        result = service.advance(advance(opening,target=4,quota=2))
        assert result.status == 'quota' and result.completed == 2 and result.head.day == 2
        cancelled = service.advance(advance(result.head,target=4,operation='cancel-hook'),cancelled=lambda:True)
        assert cancelled.status == 'cancelled' and cancelled.head == result.head
        assert service.boundaries.read(opening.context).record.day == 2
        with pytest.raises(BoundaryError,match='replay_chunk_quota'):
            service.replay(replay(opening.context,2,quota=1))
        with store.transaction():
            with pytest.raises(BoundaryError,match='unconfirmed'):
                service.query(opening.context)
        with pytest.raises(BoundaryError,match='past_target'):
            service.advance(advance(result.head,target=1,operation='past'))


def test_checkpoint_failure_rolls_back_boundary_evidence_and_operation(tmp_path,monkeypatch):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store,interval=1)
        original = store.add_record
        def fail(scope, kind, key, payload):
            if kind == 'experiment-checkpoint:v1' and key == '0000000000000001':
                raise RuntimeError('checkpoint failure')
            return original(scope,kind,key,payload)
        monkeypatch.setattr(store,'add_record',fail)
        request = advance(opening,target=1)
        with pytest.raises(RuntimeError,match='checkpoint failure'):
            service.advance(request)
        assert outcome(service.boundaries.read(opening.context).record) == opening
        assert service.status(request) is None
        assert len(service.checkpoints(opening.context)) == 1
        monkeypatch.setattr(store,'add_record',original)
        assert service.advance(request).head.day == 1


def test_lost_acknowledgement_recovers_without_runtime_or_duplicate_advancement(tmp_path):
    class LostAck(Exception):
        pass
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        request = advance(opening,target=3)
        def lost(progress):
            if progress.head.day == 3:
                raise LostAck()
        with pytest.raises(LostAck):
            service.advance(request,progress=lost)
        assert service.status(request).head.day == 3
    with Store(tmp_path) as store:
        service = Experiments(TransitionReducer(Revisions(store,registry=None),catalog=None))
        result = service.advance(request)
        assert result.completed == 3 and result.head.sequence == 3
        assert service.advance(request) == result
        assert service.boundaries.read(opening.context).record.sequence == 3


def test_random_forks_keep_realized_past_and_explicit_future_seed_policy(tmp_path):
    from test_stochastic import setup_random, plan, spec
    with Store(tmp_path) as store:
        reducer, _, original = setup_random(store,random=plan([spec('draw-'+str(day),day=day) for day in range(1,6)]))
        service = Experiments(reducer)
        request = CreateExperiment.model_validate(original.model_dump() | dict(
            context=original.context.model_dump() | dict(experiment_id='controlled'),operation_id='random-create'))
        opening = service.create(StartExperiment(request=request,checkpoint_interval=3))
        service.advance(advance(opening,target=5))
        source = outcome(service.boundaries.read(opening.context,2).record)
        paired = service.fork(fork_request(service,source))
        changed = service.fork(fork_request(service,source,name='reseeded',realization_policy='new_realization',seed='02'*32))
        service.advance(advance(paired,target=5,operation='paired'))
        service.advance(advance(changed,target=5,operation='reseeded'))
        for day in range(3,6):
            original_draw = service.boundaries.read(opening.context,day).state.transition.random_draws
            paired_draw = service.boundaries.read(paired.context,day-2).state.transition.random_draws
            changed_draw = service.boundaries.read(changed.context,day-2).state.transition.random_draws
            assert original_draw == paired_draw
            assert original_draw[0].accepted_block != changed_draw[0].accepted_block
        assert service.boundaries.read(changed.context,0).state == service.boundaries.read(opening.context,2).state
        assert service.replay(replay(paired.context,2,'verify')).record.day == 4
        with pytest.raises(Exception,match='seed'):
            service.fork(fork_request(service,source,name='bad',realization_policy='preserve',seed='03'*32))


def test_retrospective_future_event_edit_does_not_rewrite_parent(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        service.advance(advance(opening,target=3))
        source = outcome(service.boundaries.read(opening.context,1).record)
        request = fork_request(service,source)
        raw = request.plan.model_dump()
        raw['events'] = [dict(id='future-fact',effective_day=2,order=0,origin='player_authored',source_refs=[],
            changes=[dict(condition_id='synthetic:rain',scope_id='local',expected_digest=None,
                value=dict(kind='label',value='wet'))])]
        request = ForkExperiment.model_validate(request.model_dump() | dict(plan=raw))
        forked = service.fork(request)
        service.advance(advance(forked,target=3,operation='edited-future'))
        assert service.boundaries.read(opening.context).state.conditions == []
        assert service.boundaries.read(forked.context).state.conditions[0].value.value == 'wet'
        assert service.replay(replay(forked.context,1,'verify')).record.day == 2


def test_pause_during_progress_stops_at_confirmed_boundary_and_reopens(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        def pause(progress):
            _, current, _ = service.query(opening.context)
            service.control(ControlExperiment(context=opening.context,operation_id='pause-progress',expected=current,state='paused'))
        result = service.advance(advance(opening),progress=pause)
        assert result.status == 'paused' and result.head.day == 1
    with Store(tmp_path) as store:
        service = Experiments(TransitionReducer(Revisions(store,registry=None),catalog=None))
        assert service.query(opening.context)[1].state == 'paused'
        assert service.advance(advance(opening)) == result


@pytest.mark.parametrize('after_commit',[False,True])
def test_real_process_exit_keeps_checkpoint_and_boundary_atomic(tmp_path,after_commit):
    import os
    import subprocess
    import sys
    from pathlib import Path
    with Store(tmp_path) as store:
        service, opening, _ = setup(store,interval=1)
        request = advance(opening,target=1)
        request_path = tmp_path/'request.json'
        request_path.write_text(request.model_dump_json())
    code = '''
import os,sys
from pathlib import Path
from contextlib import contextmanager
from transition_fixture import fixture
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.experiments import Experiments
from poliscope_engine.contracts.experiments import AdvanceExperiment
mechanisms,catalog,_,_=fixture()
with Store(Path(sys.argv[1])) as store:
    service=Experiments(TransitionReducer(Revisions(store,registry=mechanisms),catalog=catalog))
    original=store.transaction
    @contextmanager
    def crash():
        with original():
            yield
            # The command intent is a separate transaction; exit only at the
            # actual boundary/checkpoint transaction, immediately around COMMIT.
            scope=service.boundaries._scope(request.expected.context)
            exists=store.read_record(scope,'experiment-checkpoint:v1','0000000000000001') is not None
            if exists and sys.argv[3]=='before':os._exit(91)
        if exists:os._exit(92)
    store.transaction=crash
    request=AdvanceExperiment.model_validate_json(Path(sys.argv[2]).read_text())
    service.advance(request)
'''
    env=os.environ.copy()
    env['PYTHONPATH']=os.pathsep.join([str(Path('engine').resolve()),str(Path('tests/engine').resolve())])
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path),str(request_path),'after' if after_commit else 'before'],
        capture_output=True,text=True,env=env)
    assert result.returncode == (92 if after_commit else 91),result.stderr
    with Store(tmp_path) as store:
        mechanisms,catalog,_,_=fixture()
        service=Experiments(TransitionReducer(Revisions(store,registry=mechanisms),catalog=catalog))
        assert service.boundaries.read(opening.context).record.sequence == int(after_commit)
        assert len(service.checkpoints(opening.context)) == 1 + int(after_commit)
        assert (service.status(request) is not None) == after_commit
        assert service.advance(request).head.sequence == 1
        assert len(service.checkpoints(opening.context)) == 2


@pytest.mark.parametrize('stage',['context','manifest','control','checkpoint','outcome'])
def test_opening_and_fork_failures_leave_no_partial_experiment(tmp_path,monkeypatch,stage):
    with Store(tmp_path) as store:
        service, opening, original = setup(store)
        source=outcome(service.boundaries.read(opening.context).record)
        fork=fork_request(service,source,name='failed-fork')
        request=StartExperiment(request=original.model_copy(update={'context':original.context.model_copy(
            update={'experiment_id':'failed-opening'}),'operation_id':'failed-opening'}),checkpoint_interval=1)
        targets={'context':('add_context',None),'manifest':('add_record','experiment-controller:v1'),
            'control':('add_record','experiment-control:v1'),'checkpoint':('add_record','experiment-checkpoint:v1'),
            'outcome':('complete_operation',None)}
        name,kind=targets[stage]
        method=getattr(store,name)
        def fail(*args,**kwargs):
            if kind is None or args[1] == kind:
                raise RuntimeError('injected failure')
            return method(*args,**kwargs)
        monkeypatch.setattr(store,name,fail)
        for operation,context in [(lambda:service.create(request),request.request.context),(lambda:service.fork(fork),fork.context)]:
            with pytest.raises(RuntimeError,match='injected failure'):
                operation()
            assert store.read_context(service.boundaries._scope(context)) is None
        monkeypatch.setattr(store,name,method)
        assert service.create(request).sequence == 0
        assert service.fork(fork).sequence == 0


def test_cache_eviction_and_checkpoint_spacing_preserve_all_explanations(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store,interval=3)
        service.advance(advance(opening,target=5))
        retained=[digest(service.boundaries.read(opening.context,i).evidence) for i in range(6)]
        # Checkpoints are retained index records, never disposable cache entries.
        with store.transaction():
            store._connection.execute('DELETE FROM caches')
        assert [c.boundary.sequence for c in service.checkpoints(opening.context,limit=1)] == [0]
        assert [c.boundary.sequence for c in service.checkpoints(opening.context,after=0)] == [3]
        for i in range(6):
            assert digest(service.replay(replay(opening.context,i)).evidence) == retained[i]
        assert service.replay(replay(opening.context,3,'verify')).record.sequence == 3


def test_incomplete_chunk_status_and_operation_namespace_are_bound(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        request=advance(opening,target=4)
        def interrupt(progress):
            raise RuntimeError('lost process')
        with pytest.raises(RuntimeError,match='lost process'):
            service.advance(request,progress=interrupt)
        status=service.status(request)
        assert status.status == 'running' and status.completed == 1 and status.head.day == 1
        _,control,_=service.query(opening.context)
        with pytest.raises(BoundaryError,match='payload_mismatch'):
            service.control(ControlExperiment(context=opening.context,expected=control,
                operation_id=request.operation_id,state='paused'))
        assert service.advance(request).head.day == 4


def test_controlled_runs_cannot_bypass_checkpoint_hook(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        bare=TransitionReducer(service.reducer.revisions,catalog=service.reducer.catalog)
        with pytest.raises(BoundaryError,match='controller_required'):
            bare.advance_boundary(opening,1,operation_id='bare')
        assert service.boundaries.read(opening.context).record.sequence == 0
        assert len(service.checkpoints(opening.context)) == 1


def test_mixed_rates_event_conflict_and_checkpoint_replay_keep_intermediate_history(tmp_path):
    with Store(tmp_path) as store:
        reducer,_,original=start(store,*fixture())
        service=Experiments(reducer)
        raw=original.model_dump()
        raw['context']['experiment_id']='mixed'
        raw['operation_id']='mixed-create'
        raw['plan']['schedules'][1].update(interval_days=3,first_day=3)
        raw['plan']['events']=[dict(id=name,effective_day=2,order=order,origin='player_authored',source_refs=[],
            changes=[dict(condition_id='synthetic:rain',scope_id='local',expected_digest=None,
                value=dict(kind='label',value=value))]) for name,order,value in [('first',0,'wet'),('second',1,'dry')]]
        opening=service.create(StartExperiment(request=CreateExperiment.model_validate(raw),checkpoint_interval=3))
        result=service.advance(advance(opening,target=6))
        assert result.head.day == 6
        day2=service.boundaries.read(opening.context,2)
        assert [e.status for e in day2.record.changes.events] == ['applied','conflict']
        assert day2.state.conditions[0].value.value == 'wet'
        assert day2.record.due.mechanism_ids == ['a']
        assert service.boundaries.read(opening.context,3).record.due.mechanism_ids == ['a','b']
        for i in [2,4,6]:
            checked=service.replay(replay(opening.context,i,'verify'))
            assert checked == service.boundaries.read(opening.context,i)


def test_invalid_forks_and_runtime_verification_cannot_mutate_history(tmp_path,monkeypatch):
    with Store(tmp_path) as store:
        service,opening,request=setup(store)
        service.advance(advance(opening,target=2))
        source=outcome(service.boundaries.read(opening.context,1).record)
        fork=fork_request(service,source)
        bad=fork.model_copy(update={'source':source.model_copy(update={'boundary_digest':'sha256:'+'0'*64})})
        with pytest.raises(BoundaryError,match='fork_source_mismatch'):
            service.fork(bad)
        assert service.status(fork) is None
        assert service.status(StartExperiment(request=request,checkpoint_interval=2)) == opening
        def unavailable(*args,**kwargs):
            raise BoundaryError('historical_runtime_unavailable')
        monkeypatch.setattr(service.reducer,'_reduce',unavailable)
        assert service.replay(replay(opening.context,2)).record.sequence == 2
        with pytest.raises(BoundaryError,match='historical_runtime_unavailable'):
            service.replay(replay(opening.context,2,'verify'))
        assert service.boundaries.read(opening.context).record.sequence == 2
