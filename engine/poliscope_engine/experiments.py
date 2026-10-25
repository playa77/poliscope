"""Durable experiment control over immutable validated boundary history.

All APIs are trusted-host only. Checkpoints index retained snapshots; neither
checkpoint policy nor cache eviction deletes accepted results or explanations.
"""
from pydantic import TypeAdapter
from poliscope_engine.boundaries import BoundaryError, outcome, checked, plan_digest
from poliscope_engine.contracts.boundaries import (
    BoundaryOutcome, ExperimentRecord, BoundaryCandidate, ConfirmBoundary)
from poliscope_engine.contracts.experiments import (
    StartExperiment, ForkExperiment, ExperimentManifest, ExperimentControl,
    ControlExperiment, AdvanceExperiment, ExperimentProgress, Checkpoint, ReplayExperiment)
from poliscope_engine.contracts.world import SafeCount
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.simulation import REDUCER_ID
from poliscope_engine.timeline import boundaries, stage_changes, validate_approval
from poliscope_engine.stochastic import fork_plan

MANIFEST = 'experiment-controller:v1'
CONTROLS = 'experiment-control:v1'
CHECKPOINTS = 'experiment-checkpoint:v1'
INTENTS = 'experiment-advance:v1'


class Experiments:
    def __init__(self, reducer):
        self.reducer, self.boundaries = reducer, reducer.store
        self.store = self.boundaries.store
        if self.boundaries.on_persist is not None:
            raise BoundaryError('experiment_controller_already_attached')
        self.boundaries.on_persist = self._persist
        self._pending = None

    def _binding(self, request):
        return digest(dict(experiment_operation=request.operation_id)), serialized(dict(
            controller_contract=1, kind=type(request).__name__, request_digest=digest(request)))

    def _old(self, scope, request, model):
        key, binding = self._binding(request)
        intent = self.store.read_record(scope, INTENTS, key)
        if intent is not None and intent != binding:
            raise BoundaryError('advance_operation_payload_mismatch')
        raw = self.store.operation_outcome(scope, key, binding)
        return None if raw is None else model.model_validate_json(raw)

    def _complete(self, scope, request, result):
        key, binding = self._binding(request)
        self.store.complete_operation(scope, key, binding, result.model_dump_json())

    def _manifest(self, context):
        scope, _ = self.boundaries._experiment(context)
        raw = self.store.read_record(scope, MANIFEST, 'manifest')
        if raw is None:
            raise BoundaryError('experiment_controller_unavailable')
        return scope, ExperimentManifest.model_validate_json(raw)

    def _control(self, scope):
        rows = self.store.record_page(scope, CONTROLS, limit=1, descending=True)
        if not rows:
            raise BoundaryError('experiment_controller_unavailable')
        return ExperimentControl.model_validate_json(rows[0][1])

    def _persist(self, record):
        scope = self.boundaries._scope(record.context)
        if record.sequence == 0 and self._pending is not None:
            context, manifest, request = self._pending
            if context != record.context:
                raise BoundaryError('controller_opening_context_mismatch')
            self.store.add_record(scope, MANIFEST, 'manifest', manifest.model_dump_json())
            self.store.add_record(scope, CONTROLS, '0000000000000000',
                ExperimentControl(sequence=0, state='ready').model_dump_json())
            self._complete(scope, request, outcome(record))
        else:
            raw = self.store.read_record(scope, MANIFEST, 'manifest')
            if raw is None:  # Existing boundary-store clients retain v1 behavior.
                return
            manifest = ExperimentManifest.model_validate_json(raw)
            if self._control(scope).state != 'ready':
                raise BoundaryError('experiment_not_running')
        if record.sequence % manifest.checkpoint_interval == 0:
            checkpoint = Checkpoint(boundary=outcome(record), state_digest=record.state_digest,
                evidence_digest=record.evidence_digest)
            self.store.add_record(scope, CHECKPOINTS, f'{record.sequence:016d}', checkpoint.model_dump_json())

    def create(self, request: StartExperiment, *, cancelled=None):
        self.boundaries._confirmed_only()
        request = checked(StartExperiment, request)
        scope = self.boundaries._scope(request.request.context)
        # Bind checkpoint policy as well as the underlying opening request.
        old = self._old(scope, request, BoundaryOutcome)
        if old is not None:
            return old
        if self.store.read_context(scope) is not None:
            raise BoundaryError('experiment_exists')
        manifest = ExperimentManifest(checkpoint_interval=request.checkpoint_interval,
            realization_policy='opening')
        self._pending = (request.request.context, manifest, request)
        try:
            return self.boundaries.create(request.request, cancelled=cancelled)
        finally:
            self._pending = None

    def control(self, request: ControlExperiment):
        self.boundaries._confirmed_only()
        request = checked(ControlExperiment, request)
        scope, _ = self._manifest(request.context)
        with self.store.transaction():
            old = self._old(scope, request, ExperimentControl)
            if old is not None:
                return old
            current = self._control(scope)
            if current != request.expected:
                raise BoundaryError('stale_experiment_control')
            if current.state == 'cancelled' and request.state != 'cancelled':
                raise BoundaryError('cancelled_experiment_requires_fork')
            result = ExperimentControl(sequence=current.sequence + 1, state=request.state)
            self.store.add_record(scope, CONTROLS, f'{result.sequence:016d}', result.model_dump_json())
            self._complete(scope, request, result)
        return result

    def query(self, context, sequence=None):
        self.boundaries._confirmed_only()
        scope, manifest = self._manifest(context)
        return manifest, self._control(scope), self.boundaries.read(context, sequence)

    def checkpoints(self, context, *, after=None, limit=100):
        self.boundaries._confirmed_only()
        scope, _ = self._manifest(context)
        if after is not None:
            TypeAdapter(SafeCount).validate_python(after, strict=True)
        rows = self.store.record_page(scope, CHECKPOINTS,
            after=None if after is None else f'{after:016d}', limit=limit)
        return [Checkpoint.model_validate_json(raw) for _, raw in rows]

    def _resume(self, request, *, cancelled=None, progress=None, execute=True):
        scope, _ = self._manifest(request.expected.context)
        old = self._old(scope, request, ExperimentProgress)
        if old is not None:
            return old
        _, experiment = self.boundaries._experiment(request.expected.context)
        opening = self.boundaries.read(request.expected.context, request.expected.sequence)
        if outcome(opening.record) != request.expected:
            raise BoundaryError('advance_opening_mismatch')
        if request.target_day < request.expected.day:
            raise BoundaryError('past_target_requires_fork')
        current, count = request.expected, 0
        status = 'complete'
        for due in boundaries(experiment.plan, request.target_day, after_day=current.day):
            if count == request.max_boundaries:
                status = 'quota'
                break
            operation_id = digest(dict(controller_advance=request.operation_id,
                opening_digest=current.boundary_digest, day=due.day))
            # Recover completed child outcomes before control, cancellation or runtime checks.
            try:
                saved = self.boundaries.read(current.context, current.sequence + 1)
            except BoundaryError as error:
                if str(error) != 'unknown_confirmed_boundary':
                    raise
                saved = None
            recovered = None
            if saved is not None:
                child = ConfirmBoundary(boundary_contract=1, expected=current, operation_id=operation_id,
                    candidate=BoundaryCandidate(inputs=saved.state.inputs, evidence=saved.evidence,
                        transition=saved.state.transition))
                recovered = self.boundaries.status(child)
                if recovered is None:
                    raise BoundaryError('advance_conflicts_with_confirmed_history')
            if recovered is not None:
                current = recovered
            else:
                if not execute:
                    return (None if count == 0 else
                            ExperimentProgress(head=current, completed=count, status='running'))
                control = self._control(scope)
                if control.state != 'ready':
                    status = control.state
                    break
                try:
                    current = self.reducer.advance_boundary(current, due.day,
                        operation_id=operation_id, cancelled=cancelled)
                except BoundaryError as error:
                    if str(error) != 'boundary_cancelled':
                        raise
                    status = 'cancelled'
                    break
            count += 1
            if progress is not None:
                progress(ExperimentProgress(head=current, completed=count, status='complete' if current.day == request.target_day else 'quota'))
        result = ExperimentProgress(head=current, completed=count, status=status)
        if execute:
            with self.store.transaction():
                old = self._old(scope, request, ExperimentProgress)
                if old is not None:
                    return old
                self._complete(scope, request, result)
        return result

    def advance(self, request: AdvanceExperiment, *, cancelled=None, progress=None):
        self.boundaries._confirmed_only()
        request = checked(AdvanceExperiment, request)
        scope, _ = self._manifest(request.expected.context)
        key, binding = self._binding(request)
        with self.store.transaction():
            old = self._old(scope, request, ExperimentProgress)
            if old is not None:
                return old
            intent = self.store.read_record(scope, INTENTS, key)
            if intent is not None and intent != binding:
                raise BoundaryError('advance_operation_payload_mismatch')
            if intent is None:
                self.store.add_record(scope, INTENTS, key, binding)
        return self._resume(request, cancelled=cancelled, progress=progress)

    def status(self, request):
        self.boundaries._confirmed_only()
        if isinstance(request, StartExperiment):
            request = checked(StartExperiment, request)
            return self._old(self.boundaries._scope(request.request.context), request, BoundaryOutcome)
        if isinstance(request, ForkExperiment):
            request = checked(ForkExperiment, request)
            return self._old(self.boundaries._scope(request.context), request, BoundaryOutcome)
        if isinstance(request, ControlExperiment):
            request = checked(ControlExperiment, request)
            scope, _ = self._manifest(request.context)
            return self._old(scope, request, ExperimentControl)
        request = checked(AdvanceExperiment, request)
        scope, _ = self._manifest(request.expected.context)
        key, binding = self._binding(request)
        raw = self.store.read_record(scope, INTENTS, key)
        if raw is None:
            return None
        if raw != binding:
            raise BoundaryError('advance_operation_payload_mismatch')
        return self._resume(request, execute=False)

    def replay(self, request: ReplayExperiment, *, cancelled=None):
        self.boundaries._confirmed_only()
        request = checked(ReplayExperiment, request)
        scope, _ = self._manifest(request.context)
        target = self.boundaries.read(request.context, request.sequence)
        # Nearest checkpoint at/before the requested sequence, with bounded work.
        upper = request.sequence if request.mode == 'verify' and request.sequence > 0 else request.sequence + 1
        rows = self.store.record_page(scope, CHECKPOINTS,
            after=f'{upper:016d}', limit=1, descending=True)
        if not rows:
            raise BoundaryError('checkpoint_unavailable')
        checkpoint = Checkpoint.model_validate_json(rows[0][1])
        current = self.boundaries.read(request.context, checkpoint.boundary.sequence)
        if (outcome(current.record) != checkpoint.boundary or current.record.state_digest != checkpoint.state_digest
                or current.record.evidence_digest != checkpoint.evidence_digest):
            raise BoundaryError('checkpoint_identity_mismatch')
        if request.sequence - current.record.sequence > request.max_boundaries:
            raise BoundaryError('replay_chunk_quota')
        _, experiment = self.boundaries._experiment(request.context)
        if request.mode == 'verify':
            if self.reducer.mechanisms is None or (target.record.sequence > 0 and target.record.validator_id != REDUCER_ID):
                raise BoundaryError('historical_runtime_unavailable')
            if experiment.transition_plan is not None and experiment.transition_plan.random_plan is not None:
                from poliscope_engine.stochastic import require_runtime
                require_runtime(experiment.transition_plan.random_plan.runtime)
        for sequence in range(current.record.sequence + 1, request.sequence + 1):
            if cancelled is not None and cancelled():
                raise BoundaryError('boundary_cancelled')
            saved = self.boundaries.read(request.context, sequence)
            due = next(boundaries(experiment.plan, saved.record.day, after_day=current.record.day))
            changes, facts = stage_changes(experiment.plan, saved.record.day,
                current.state.inputs.design.policies,
                {(c.scope_id, c.condition_id): c.value for c in current.state.conditions},
                read_revision=self.reducer.revisions.read)
            if (saved.record.parent_digest != current.record.boundary_digest or saved.record.due != due
                    or due.day != saved.record.day or saved.record.changes != changes
                    or digest(saved.state.inputs.design.policies) != digest(changes.policies)
                    or {(c.scope_id, c.condition_id): c.value for c in saved.state.conditions} != facts):
                raise BoundaryError('recorded_history_chain_mismatch')
            if request.mode == 'verify':
                if saved.record.validator_id != REDUCER_ID or self.reducer.mechanisms is None:
                    raise BoundaryError('historical_runtime_unavailable')
                candidate = self.reducer._reduce(current, experiment, due, cancelled=cancelled,
                    recorded_draws=[] if saved.state.transition is None else saved.state.transition.random_draws)
                if (digest(candidate.inputs) != digest(saved.state.inputs)
                        or digest(candidate.evidence) != digest(saved.evidence)
                        or digest(candidate.transition) != digest(saved.state.transition)):
                    raise BoundaryError('historical_runtime_or_result_mismatch')
            current = saved
        if outcome(current.record) != outcome(target.record):
            raise BoundaryError('replay_target_mismatch')
        return current

    def fork(self, request: ForkExperiment, *, cancelled=None):
        self.boundaries._confirmed_only()
        request = checked(ForkExperiment, request)
        scope = self.boundaries._scope(request.context)
        old = self._old(scope, request, BoundaryOutcome)
        if old is not None:
            return old
        self._manifest(request.source.context)
        source = self.boundaries.read(request.source.context, request.source.sequence)
        if outcome(source.record) != request.source:
            raise BoundaryError('fork_source_mismatch')
        if (request.context.civilization_id != request.source.context.civilization_id
                or request.context.data_store_id != request.source.context.data_store_id):
            raise BoundaryError('foreign_fork_context')
        _, parent = self.boundaries._experiment(request.source.context)
        if (request.plan.opening_revision != parent.plan.opening_revision
                or request.plan.opening_day != source.record.day or request.plan.calendar != parent.plan.calendar
                or request.plan.schedules != parent.plan.schedules):
            raise BoundaryError('fork_schedule_identity_mismatch')
        for adoption in request.plan.adoptions:
            validate_approval(adoption, self.reducer.revisions.read)
        scopes = {s.id for s in source.state.inputs.scopes}
        if any(c.scope_id not in scopes for event in request.plan.events for c in event.changes):
            raise BoundaryError('unknown_event_scope')
        transition = parent.transition_plan
        if transition is not None and transition.random_plan is not None:
            random = fork_plan(transition.random_plan, policy=request.realization_policy, seed=request.seed)
            transition = transition.model_copy(update={'random_plan': random})
            # fork_plan verifies the actual parent's complete named identities.
            # Past draws remain in that immutable model for persistent variables;
            # they must not be revalidated as newly scheduled events after the fork.
        elif request.realization_policy != 'preserve' or request.seed is not None:
            raise BoundaryError('fork_random_plan_unavailable')
        manifest = ExperimentManifest(checkpoint_interval=request.checkpoint_interval,
            origin=request.source, realization_policy=request.realization_policy)
        self._pending = (request.context, manifest, request)
        try:
            with self.store.transaction():
                old = self._old(scope, request, BoundaryOutcome)
                if old is not None:
                    return old
                if cancelled is not None and cancelled():
                    raise BoundaryError('boundary_cancelled')
                if self.store.read_context(scope) is not None:
                    raise BoundaryError('experiment_exists')
                from poliscope_engine.boundaries import _record
                plan_id = plan_digest(request.plan, transition)
                record = _record(request.context, 0, source.state, source.evidence, plan_id, None, 'retrospective-fork:v1')
                self.store.add_context(scope, ExperimentRecord(boundary_contract=1, context=request.context,
                    plan=request.plan, plan_digest=plan_id, opening_digest=record.boundary_digest,
                    transition_plan=transition, origin=request.source).model_dump_json())
                result = self.boundaries._persist(scope, request.context, 0, source.state, source.evidence,
                    plan_id, None, 'retrospective-fork:v1')
                if cancelled is not None and cancelled():
                    raise BoundaryError('boundary_cancelled')
            return result
        finally:
            self._pending = None
