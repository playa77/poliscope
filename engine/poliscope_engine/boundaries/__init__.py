"""Atomic confirmed-boundary repository, consumed by the trusted transition host.

No in-memory head is published. Reads select one immutable confirmed journal row;
state, evidence and operation replay become visible together after SQLite COMMIT.
This service verifies storage/context/evidence/scheduling structure. A configured
host validator must independently validate dynamic transitions before confirmation.
"""
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import json
from pydantic import TypeAdapter

from poliscope_engine.contracts.base import Identifier
from poliscope_engine.contracts.measurements import AcceptedEvidence
from poliscope_engine.contracts.boundaries import (
    ExperimentContext, CreateExperiment, ConfirmBoundary, BoundaryState,
    BoundaryRecord, BoundaryOutcome, ConfirmedBoundary, ExperimentRecord,
    BoundaryCondition, BoundaryValidation)
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.explanation import read_retained
from poliscope_engine.revisions import graph
from poliscope_engine.storage.blobs import RetainedBlobs
from poliscope_engine.timeline import boundaries, stage_changes, schedule_digest, validate_approval

JOURNAL = 'confirmed-boundary:v1'


@dataclass(frozen=True)
class _Prepared:
    authority: object
    validator: object
    validator_id: str
    expected: object
    candidate_signature: bytes
    closing: object
    experiment: object
    due: object
    changes: object


def _signature(candidate):
    return sha256(candidate.model_dump_json().encode()).digest()


class BoundaryError(ValueError):
    pass


def checked(model, value):
    return model.model_validate_json(value.model_dump_json())


def outcome(record):
    return BoundaryOutcome(**record.model_dump(include={
        'boundary_contract', 'context', 'sequence', 'day', 'boundary_digest'}))


def _cancel(cancelled):
    if cancelled is not None and cancelled():
        raise BoundaryError('boundary_cancelled')


def _record(context, sequence, state, evidence, plan_digest, parent_digest, validator_id,
            due=None, changes=None):
    fields = dict(boundary_contract=1, context=context, sequence=sequence,
        day=state.inputs.design.effective_time.tick, parent_digest=parent_digest,
        plan_digest=plan_digest, state_digest=state_digest(state), evidence_digest=evidence.closure_digest,
        validator_id=validator_id, due=due, changes=changes)
    return BoundaryRecord(**fields, boundary_digest=digest(fields))


def state_digest(state):
    # Optional consumer extensions must not change existing v1 history identities.
    return (digest(dict(inputs=state.inputs, conditions=state.conditions)) if state.transition is None
            else digest(state))


def plan_digest(plan, transition_plan):
    return (schedule_digest(plan) if transition_plan is None else
            digest(dict(timeline=schedule_digest(plan), transition=transition_plan)))


class BoundaryStore:
    """Main-authorized local store plus optional, host-selected WP-034 validator.

    Callers must authorize access to the local civilization/experiment. Content
    cannot supply a validator, choose executable code or bypass this prerequisite.
    Without a validator, historical reads and completed operation replay work;
    new advances fail closed. Opening an experiment copies accepted revision data.
    """
    def __init__(self, revisions, *, validator: Callable[[BoundaryValidation], None] | None = None,
                 validator_id: str | None = None):
        if (validator is None) != (validator_id is None):
            raise BoundaryError('validator_identity_required')
        if validator_id is not None:
            TypeAdapter(Identifier).validate_python(validator_id, strict=True)
        self.revisions, self.store = revisions, revisions.store
        self.validator, self.validator_id = validator, validator_id
        self.blobs = RetainedBlobs(self.store)
        # Trusted controller hook runs inside the same transaction as confirmation.
        self.on_persist = None
        self._verified_payloads = {}
        self._request_digests = {}
        self._preparation_authority = object()
        self._frames = {}

    def _advance_opening(self, context):
        """Private committed frame; storage integrity is checked on every use."""
        self._confirmed_only()
        record = self._head(context)
        cached = self._frames.get(record.boundary_digest)
        if cached is not None:
            scope = self._scope(context)
            # A warm frame cannot conceal a deleted or damaged retained chunk.
            state = self.blobs.read(scope, 'boundary-state', record.state_digest)
            evidence = self.blobs.read(scope, 'boundary-evidence', record.evidence_digest, evidence=True)
            marker = sha256((state + '\0' + evidence).encode()).digest()
            if marker == cached[1] and cached[0].record == record:
                return cached[0]
        return self._read(context)

    def _remember_frame(self, frame):
        state, evidence = serialized(frame.state), serialized(frame.evidence)
        size = len(state.encode()) + len(evidence.encode())
        if size > 32 * 1024 * 1024:
            return
        if len(self._frames) >= 2:
            del self._frames[next(iter(self._frames))]
        self._frames[frame.record.boundary_digest] = (frame,
            sha256((state + '\0' + evidence).encode()).digest())

    def _prepare_publication(self, opening, experiment, due, changes, facts, candidate):
        """Private host capability, never accepted from a serialized request.

        The reducer has already checked callbacks, finite balances and closing
        evaluation. Bind those checks to the exact detached candidate bytes.
        External confirm requests always take the independent reduction path.
        """
        if not self.revisions._matches_assembly(candidate.inputs, candidate.evidence,
                                               experiment.context.civilization_id):
            return None
        # The assembly witness binds all world/design/measurement/reference
        # bytes to the actual producer. Check the independent transition witness
        # here; do not rebuild that same complete closing evidence again.
        from poliscope_engine.simulation import verify_receipt
        from poliscope_engine.stochastic import check_retained
        verify_receipt(candidate.transition)
        check_retained(experiment.transition_plan.random_plan, due.day, candidate.transition.random_draws)
        if (candidate.inputs.design.effective_time.tick != due.day or
                candidate.inputs.design.effective_time.calendar_id != experiment.plan.calendar.id or
                candidate.inputs.versions != opening.state.inputs.versions or
                candidate.transition.opening_digest != opening.record.boundary_digest or
                candidate.transition.plan_digest != digest(experiment.transition_plan)):
            raise BoundaryError('incompatible_boundary_candidate')
        evidence = candidate.evidence
        if evidence.evaluation.identities.model_digest != opening.evidence.evaluation.identities.model_digest:
            raise BoundaryError('experiment_model_runtime_changed')
        closing = BoundaryState(inputs=candidate.inputs, conditions=[BoundaryCondition(
            scope_id=s, condition_id=c, value=v) for (s, c), v in sorted(facts.items())], transition=candidate.transition)
        return _Prepared(self._preparation_authority, self.validator, self.validator_id, outcome(opening.record),
            _signature(candidate), closing, experiment, due, changes)

    def _confirm_prepared(self, request, prepared, *, cancelled=None):
        self._confirmed_only()
        def check():
            if (prepared.authority is not self._preparation_authority or request.expected != prepared.expected
                    or self.validator != prepared.validator or self.validator_id != prepared.validator_id
                    or _signature(request.candidate) != prepared.candidate_signature
                    or prepared.closing.inputs is not request.candidate.inputs
                    or prepared.closing.transition is not request.candidate.transition):
                raise BoundaryError('transition_candidate_mismatch')
        check()
        scope, experiment = self._experiment(request.expected.context)
        key, binding, old = self._operation(scope, request)
        if old is not None:
            return old
        _cancel(cancelled)
        if experiment != prepared.experiment or self.validator is None:
            raise BoundaryError('transition_validator_unavailable')
        with self.store.transaction():
            key, binding, old = self._operation(scope, request)
            if old is not None:
                return old
            _cancel(cancelled)
            check()
            if outcome(self._head(request.expected.context)) != request.expected:
                raise BoundaryError('stale_boundary')
            result = self._persist(scope, request.expected.context, request.expected.sequence + 1,
                prepared.closing, request.candidate.evidence, experiment.plan_digest,
                request.expected.boundary_digest, self.validator_id, prepared.due, prepared.changes)
            self.store.complete_operation(scope, key, binding, result.model_dump_json())
            _cancel(cancelled)
            check()
            record = BoundaryRecord.model_validate_json(self.store.read_record(
                scope, JOURNAL, f'{result.sequence:016d}'))
        # This private frame is published only after COMMIT. Public reads still
        # construct detached objects from their retained bytes.
        self._remember_frame(ConfirmedBoundary(record=record, state=prepared.closing,
            evidence=request.candidate.evidence))
        return result

    def _scope(self, context):
        context = checked(ExperimentContext, context)
        if context.data_store_id != self.revisions.data_store_id:
            raise BoundaryError('wrong_data_store')
        return digest(dict(boundary_contract=1, context=context))

    def _experiment(self, context):
        scope = self._scope(context)
        raw = self.store.read_context(scope)
        if raw is None:
            raise BoundaryError('unknown_experiment')
        experiment = ExperimentRecord.model_validate_json(raw)
        if (experiment.context != context or experiment.plan_digest != plan_digest(experiment.plan, experiment.transition_plan)
                or experiment.plan.opening_revision.data_store_id != context.data_store_id
                or experiment.plan.opening_revision.civilization_id != context.civilization_id):
            raise BoundaryError('experiment_identity_mismatch')
        return scope, experiment

    def _operation(self, scope, request):
        kind = 'create' if isinstance(request, CreateExperiment) else 'confirm'
        # Same ID cannot be reused for another action within the experiment.
        key = digest(dict(boundary_operation=request.operation_id))
        # Full accepted evidence can exceed the store's 1 MiB row bound. Bind
        # its canonical digest; the complete state/closure is retained in chunks.
        signature = sha256(request.model_dump_json().encode()).digest()
        request_digest = self._request_digests.get(signature)
        payload = {name: getattr(request, name) for name in type(request).model_fields}
        if kind == 'create' and request.transition_plan is None:
            payload.pop('transition_plan', None)
        if kind == 'confirm' and request.candidate.transition is None:
            payload['candidate'] = {name: getattr(request.candidate, name)
                for name in type(request.candidate).model_fields if name != 'transition'}
        if request_digest is None:
            request_digest = digest(payload)
            if len(self._request_digests) == 8:
                del self._request_digests[next(iter(self._request_digests))]
            self._request_digests[signature] = request_digest
        binding = serialized(dict(boundary_contract=1, kind=kind, request_digest=request_digest))
        raw = self.store.operation_outcome(scope, key, binding)
        return key, binding, BoundaryOutcome.model_validate_json(raw) if raw else None

    def status(self, request):
        """Exact payload-bound status, with no stale-head or model availability check."""
        self._confirmed_only()
        if isinstance(request, CreateExperiment):
            request = checked(CreateExperiment, request)
            context = request.context
        else:
            request = checked(ConfirmBoundary, request)
            context = request.expected.context
        scope = self._scope(context)
        # Unknown exact create status is valid before its context exists.
        if self.store.read_context(scope) is not None:
            self._experiment(context)
        return self._operation(scope, request)[2]

    @staticmethod
    def _check_state_evidence(context, state, evidence):
        """Bind the retained result to precisely this canonical closing state."""
        evidence = read_retained(evidence.model_dump_json())
        if evidence.state != 'complete':
            raise BoundaryError('complete_boundary_evidence_required')
        inputs = state.inputs
        world = graph(inputs, context.civilization_id)
        snapshot = dict(civilization_id=world.registry.civilization_id,
            entities=world.registry._canonical_entities, scopes=world.registry._canonical_scopes,
            values=world.registry.values, owners=world.registry._canonical_owners,
            populations=world.registry._canonical_populations, relationships=world._canonical_relationships)
        expected = dict(world=snapshot, design={name: getattr(inputs.design, name)
            for name in type(inputs.design).model_fields if name != 'realization'},
                        assumptions=sorted(inputs.assumptions, key=lambda a: a.id))
        evaluation, report = evidence.evaluation, evidence.report
        model = json.loads(evaluation.model_json)
        if (evaluation.identities.input_digest != digest(expected)
                or evaluation.identities.realization_digest != digest(inputs.design.realization)
                or evaluation.effective_time != inputs.design.effective_time
                or model['identity'][0] != inputs.versions.model_id
                or model['numeric'] != inputs.versions.numeric_runtime_id
                or digest(sorted(report.definitions, key=lambda r: r.id)) != digest(sorted(inputs.measurements, key=lambda r: r.id))
                or digest(sorted(report.goal_definitions, key=lambda r: r.id)) != digest(sorted(inputs.goals, key=lambda r: r.id))):
            raise BoundaryError('boundary_evidence_state_mismatch')
        scopes = {s.id for s in inputs.scopes}
        if any(c.scope_id not in scopes for c in state.conditions):
            raise BoundaryError('unknown_condition_scope')
        # Canonical identity also validates authoritative decimal precision.
        digest(state)
        if state.transition is not None:
            from poliscope_engine.simulation import verify_receipt
            verify_receipt(state.transition)
            if state.transition.day != inputs.design.effective_time.tick:
                raise BoundaryError('transition_evidence_time_mismatch')
        return evidence

    def _persist(self, scope, context, sequence, state, evidence, plan_digest,
                 parent_digest, validator_id, due=None, changes=None):
        if self.on_persist is None and self.store.read_record(scope, 'experiment-controller:v1', 'manifest') is not None:
            raise BoundaryError('experiment_controller_required')
        record = _record(context, sequence, state, evidence, plan_digest, parent_digest, validator_id, due, changes)
        self.blobs.put(scope, 'boundary-state', record.state_digest, state)
        self.blobs.put(scope, 'boundary-evidence', evidence.closure_digest, evidence, evidence=True)
        self.store.add_record(scope, JOURNAL, f'{sequence:016d}', record.model_dump_json())
        projection = dict(boundary_digest=record.boundary_digest,
            coverage='not_assessed' if state.transition is None else state.transition.coverage)
        self.store.add_record(scope, 'boundary-progress:v1', f'{sequence:016d}',
            serialized(dict(projection, projection_digest=digest(projection))))
        if self.on_persist is not None:
            self.on_persist(record)
        return outcome(record)

    def progress_coverage(self, expected):
        """Bounded committed projection; legacy history retains a read fallback."""
        self._confirmed_only()
        scope = self._scope(expected.context)
        raw = self.store.read_record(scope, JOURNAL, f'{expected.sequence:016d}')
        if raw is None:
            raise BoundaryError('unknown_confirmed_boundary')
        record = BoundaryRecord.model_validate_json(raw)
        if (outcome(record) != expected or record.boundary_digest !=
                digest(record.model_dump(exclude={'boundary_digest'}))):
            raise BoundaryError('boundary_record_identity_mismatch')
        raw = self.store.read_record(scope, 'boundary-progress:v1', f'{expected.sequence:016d}')
        if raw is None:
            transition = self.read(expected.context, expected.sequence).state.transition
            return 'not_assessed' if transition is None else transition.coverage
        projection = json.loads(raw)
        checksum = projection.pop('projection_digest', None)
        if (set(projection) != {'boundary_digest', 'coverage'} or digest(projection) != checksum
                or projection['boundary_digest'] != expected.boundary_digest or
                projection['coverage'] not in ('not_assessed', 'complete', 'partial', 'unresolved')):
            raise BoundaryError('boundary_progress_identity_mismatch')
        return projection['coverage']

    def create(self, request: CreateExperiment, *, cancelled=None):
        request = checked(CreateExperiment, request)
        scope = self._scope(request.context)
        with self.store.transaction():
            key, binding, old = self._operation(scope, request)
            if old is not None:
                return old
            _cancel(cancelled)
            if self.store.read_context(scope) is not None:
                raise BoundaryError('experiment_exists')
            plan, context = request.plan, request.context
            if (plan.opening_revision.data_store_id, plan.opening_revision.civilization_id) != (
                    context.data_store_id, context.civilization_id):
                raise BoundaryError('foreign_opening_revision')
            revision = self.revisions.read(plan.opening_revision)
            if request.transition_plan is not None:
                from poliscope_engine.stochastic import validate_plan
                validate_plan(request.transition_plan.random_plan,
                    [*revision.inputs.design.execution.dependencies.instances, *request.transition_plan.instances], plan)
            state = BoundaryState(inputs=revision.inputs, conditions=request.conditions)
            evidence = self._check_state_evidence(context, state, self.revisions.evidence(plan.opening_revision))
            if (state.inputs.design.effective_time.tick != plan.opening_day
                    or state.inputs.design.effective_time.calendar_id != plan.calendar.id):
                raise BoundaryError('opening_calendar_mismatch')
            for adoption in plan.adoptions:
                validate_approval(adoption, self.revisions.read)
            instance_ids = {i.id for i in state.inputs.design.execution.dependencies.instances}
            if request.transition_plan is not None:
                extra_ids = {i.id for i in request.transition_plan.instances}
                if extra_ids & instance_ids:
                    raise BoundaryError('duplicate_transition_instance')
                instance_ids |= extra_ids
            if any(s.instance_id not in instance_ids for s in plan.schedules):
                raise BoundaryError('unknown_scheduled_instance')
            scopes = {s.id for s in state.inputs.scopes}
            if any(c.scope_id not in scopes for e in plan.events for c in e.changes):
                raise BoundaryError('unknown_event_scope')
            if request.transition_plan is not None:
                from poliscope_engine.simulation import validate_opening_book
                validate_opening_book(request.transition_plan, state.inputs, self.revisions.registry)
                if set(request.transition_plan.instance_order) != {s.instance_id for s in plan.schedules}:
                    raise BoundaryError('transition_schedule_mismatch')
            plan_id = plan_digest(plan, request.transition_plan)
            initial = _record(context, 0, state, evidence, plan_id, None, 'accepted-design-revision:v1')
            self.store.add_context(scope, ExperimentRecord(boundary_contract=1, context=context, plan=plan,
                plan_digest=plan_id, opening_digest=initial.boundary_digest,
                transition_plan=request.transition_plan).model_dump_json())
            result = self._persist(scope, context, 0, state, evidence, plan_id, None, 'accepted-design-revision:v1')
            self.store.complete_operation(scope, key, binding, result.model_dump_json())
            _cancel(cancelled)
        return result

    def read(self, context: ExperimentContext, sequence: int | None = None) -> ConfirmedBoundary:
        self._confirmed_only()
        return self._read(context, sequence)

    def _confirmed_only(self):
        # A cancellation hook or other reentrant host call must not use this
        # connection's read-your-own-writes to expose an uncommitted journal row.
        if self.store.in_write_transaction:
            raise BoundaryError('unconfirmed_write_in_progress')

    def _read(self, context, sequence=None):
        context = checked(ExperimentContext, context)
        scope, experiment = self._experiment(context)
        if sequence is None:
            rows = self.store.record_page(scope, JOURNAL, limit=1, descending=True)
            raw = rows[0][1] if rows else None
        else:
            from poliscope_engine.contracts.world import SafeCount
            sequence = TypeAdapter(SafeCount).validate_python(sequence, strict=True)
            raw = self.store.read_record(scope, JOURNAL, f'{sequence:016d}')
        if raw is None:
            raise BoundaryError('unknown_confirmed_boundary')
        record = BoundaryRecord.model_validate_json(raw)
        if (record.context != context or record.plan_digest != experiment.plan_digest
                or record.boundary_digest != digest(record.model_dump(exclude={'boundary_digest'}))
                or (sequence is not None and record.sequence != sequence)):
            raise BoundaryError('boundary_record_identity_mismatch')
        state_text = self.blobs.read(scope, 'boundary-state', record.state_digest)
        evidence_text = self.blobs.read(scope, 'boundary-evidence', record.evidence_digest, evidence=True)
        marker = sha256((raw + '\0' + experiment.plan_digest + '\0' + state_text + '\0' + evidence_text).encode()).digest()
        state = BoundaryState.model_validate_json(state_text)
        evidence = AcceptedEvidence.model_validate_json(evidence_text)
        verified = marker in self._verified_payloads
        if not verified:
            evidence = self._check_state_evidence(context, state, evidence)
        if (not verified and state_digest(state) != record.state_digest or evidence.closure_digest != record.evidence_digest
                or state.inputs.design.effective_time.tick != record.day
                or state.inputs.design.effective_time.calendar_id != experiment.plan.calendar.id):
            raise BoundaryError('boundary_payload_identity_mismatch')
        if record.sequence == 0 and (record.boundary_digest != experiment.opening_digest
                or record.parent_digest is not None or record.day != experiment.plan.opening_day):
            raise BoundaryError('opening_boundary_identity_mismatch')
        fork_opening = record.sequence == 0 and experiment.origin is not None
        if fork_opening:
            origin = experiment.origin
            if (origin.context.data_store_id != context.data_store_id
                    or origin.context.civilization_id != context.civilization_id):
                raise BoundaryError('foreign_experiment_origin')
            parent_scope = self._scope(origin.context)
            raw_parent = self.store.read_record(parent_scope, JOURNAL, f'{origin.sequence:016d}')
            if raw_parent is None:
                raise BoundaryError('missing_experiment_origin')
            parent = BoundaryRecord.model_validate_json(raw_parent)
            if (outcome(parent) != origin or parent.boundary_digest != digest(parent.model_dump(exclude={'boundary_digest'}))
                    or parent.state_digest != record.state_digest or parent.evidence_digest != record.evidence_digest):
                raise BoundaryError('experiment_origin_mismatch')
        if state.transition is not None and not fork_opening and (
                state.transition.opening_digest != record.parent_digest
                or state.transition.plan_digest != digest(experiment.transition_plan)):
            raise BoundaryError('transition_evidence_context_mismatch')
        if state.transition is not None and not fork_opening:
            from poliscope_engine.stochastic import check_retained
            check_retained(experiment.transition_plan.random_plan, record.day, state.transition.random_draws)
        if not verified:
            if len(self._verified_payloads) == 8:
                del self._verified_payloads[next(iter(self._verified_payloads))]
            self._verified_payloads[marker] = True
        return ConfirmedBoundary(record=record, state=state, evidence=evidence)

    def _head(self, context):
        """The write-lock stale check needs the journal identity, not its payload."""
        scope, experiment = self._experiment(context)
        rows = self.store.record_page(scope, JOURNAL, limit=1, descending=True)
        if not rows:
            raise BoundaryError('unknown_confirmed_boundary')
        record = BoundaryRecord.model_validate_json(rows[0][1])
        if (record.context != context or record.plan_digest != experiment.plan_digest or
                record.boundary_digest != digest(record.model_dump(exclude={'boundary_digest'}))):
            raise BoundaryError('boundary_record_identity_mismatch')
        return record

    def confirm(self, request: ConfirmBoundary, *, cancelled=None):
        self._confirmed_only()
        request = checked(ConfirmBoundary, request)
        context = request.expected.context
        scope, experiment = self._experiment(context)
        # Completed replay is deliberately before model/validator/head checks.
        key, binding, old = self._operation(scope, request)
        if old is not None:
            return old
        _cancel(cancelled)
        if self.validator is None:
            raise BoundaryError('transition_validator_unavailable')
        opening = self.read(context)
        if outcome(opening.record) != request.expected:
            raise BoundaryError('stale_boundary')
        inputs = request.candidate.inputs
        day = inputs.design.effective_time.tick
        if (day <= opening.record.day or inputs.design.effective_time.calendar_id != experiment.plan.calendar.id
                or inputs.versions != opening.state.inputs.versions):
            raise BoundaryError('incompatible_boundary_candidate')
        due = next(boundaries(experiment.plan, day, after_day=opening.record.day))
        if due.day != day:
            raise BoundaryError('skipped_required_boundary')
        changes, conditions = stage_changes(experiment.plan, day, opening.state.inputs.design.policies,
            {(c.scope_id, c.condition_id): c.value for c in opening.state.conditions},
            read_revision=self.revisions.read)
        if digest(inputs.design.policies) != digest(changes.policies):
            raise BoundaryError('unscheduled_policy_change')
        if (experiment.transition_plan is None) != (request.candidate.transition is None):
            raise BoundaryError('transition_receipt_required')
        if request.candidate.transition is not None and (
                request.candidate.transition.opening_digest != request.expected.boundary_digest
                or request.candidate.transition.plan_digest != digest(experiment.transition_plan)):
            raise BoundaryError('transition_evidence_context_mismatch')
        closing = BoundaryState(inputs=inputs, conditions=[BoundaryCondition(scope_id=s, condition_id=c, value=v)
            for (s, c), v in sorted(conditions.items())], transition=request.candidate.transition)
        evidence = self._check_state_evidence(context, closing, request.candidate.evidence)
        if evidence.evaluation.identities.model_digest != opening.evidence.evaluation.identities.model_digest:
            raise BoundaryError('experiment_model_runtime_changed')
        validation = BoundaryValidation(opening=opening, due=due, changes=changes, closing=closing, evidence=evidence)
        self.validator(checked(BoundaryValidation, validation))
        _cancel(cancelled)
        # Recheck under the write lock after all pure, private validation.
        with self.store.transaction():
            key, binding, old = self._operation(scope, request)
            if old is not None:
                return old
            _cancel(cancelled)
            if outcome(self._head(context)) != request.expected:
                raise BoundaryError('stale_boundary')
            result = self._persist(scope, context, opening.record.sequence + 1, closing, evidence,
                experiment.plan_digest, opening.record.boundary_digest, self.validator_id, due, changes)
            self.store.complete_operation(scope, key, binding, result.model_dump_json())
            _cancel(cancelled)
        # No cancellation or mutable-state publication can intervene after commit.
        return result
