"""Confirmed-only timeline projections; trusted host selects executable catalogs."""
from poliscope_engine.contracts.timeline_workspace import TimelineRequest, TimelineReply, TimelineEntry
from poliscope_engine.contracts.boundaries import ExperimentContext, CreateExperiment
from poliscope_engine.contracts.experiments import StartExperiment, AdvanceExperiment, ControlExperiment, ForkExperiment, Checkpoint
from poliscope_engine.contracts.timeline import TimelinePlan, PolicyAdoption, BindingDelta
from poliscope_engine.contracts.transitions import TransitionPlan
from poliscope_engine.comparison import retained, difference
from poliscope_engine.boundaries import outcome
from poliscope_engine.evaluation.identity import digest, serialized
from poliscope_engine.experiments import Experiments, CHECKPOINTS
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.domains import DomainRegistry


def controller(revisions):
    # The workspace registry has no activated dynamic sources. Empty catalogs do
    # not create synthetic implementations or grant code execution to content.
    return Experiments(TransitionReducer(revisions, catalog=DomainRegistry()))


def compare(left, right, indicator=None):
    ids = sorted({d.id for b in (left, right) for d in b.evidence.report.definitions})
    return [difference(i, retained(left.evidence, i), retained(right.evidence, i),
        left.state, right.state, left.evidence.evaluation, right.evidence.evaluation) for i in ([indicator] if indicator else ids[:10])]


def semantics(service, left_context, right_context):
    """Explain changed inputs separately from whether subtraction is meaningful."""
    boundaries = service.boundaries
    _, left = boundaries._experiment(left_context)
    _, right = boundaries._experiment(right_context)
    lo, ro = boundaries.read(left_context, 0), boundaries.read(right_context, 0)
    changes = []
    pairs = [('opening conditions', lo.state.conditions, ro.state.conditions),
        ('opening state and choices', lo.state.inputs.values, ro.state.inputs.values),
        ('policies', lo.state.inputs.design.policies, ro.state.inputs.design.policies),
        ('assumptions', lo.state.inputs.assumptions, ro.state.inputs.assumptions),
        ('scopes', lo.state.inputs.scopes, ro.state.inputs.scopes),
        ('schedule', left.plan, right.plan), ('transition/realization definitions', left.transition_plan, right.transition_plan),
        ('model/runtime', lo.state.inputs.versions, ro.state.inputs.versions)]
    for name, before, after in pairs:
        if digest(before) != digest(after):
            changes.append(name + ' changed: ' + serialized(before) + ' → ' + serialized(after))
    return changes


def page(revisions, data, *, service=None):
    q = TimelineRequest.model_validate(data)
    if q.context.data_store_id != revisions.data_store_id:
        raise ValueError('wrong_data_store')
    revisions.read(q.context)
    service = service or controller(revisions)
    store = revisions.store
    directory = digest(dict(timeline_directory=1, store=q.context.data_store_id, civ=q.context.civilization_id))
    context = ExperimentContext(data_store_id=q.context.data_store_id,
        civilization_id=q.context.civilization_id, experiment_id=q.experiment_id)
    with store.transaction():
        if store.read_context(directory) is None:
            store.add_context(directory, '{}')
    binding = serialized(q)
    opkey = digest(dict(timeline_command=q.operation_id))
    if q.action not in ('read', 'preview_schedule'):
        old = store.operation_outcome(directory, opkey, binding)
        if old:
            return TimelineReply.model_validate_json(old)
        with store.transaction():
            intent = store.read_record(directory, 'intent', opkey)
            if intent is not None and intent != binding:
                raise ValueError('timeline_operation_payload_mismatch')
            if intent is None:
                store.add_record(directory, 'intent', opkey, binding)
    proposed_plan = None
    if q.action == 'create':
        revision = revisions.read(q.context)
        time = revision.inputs.design.effective_time
        if time.calendar_id != 'fixed-364-v1':
            raise ValueError('unsupported_opening_calendar')
        instances = revision.inputs.design.execution.dependencies.instances
        if instances:
            raise ValueError('explicit_reviewed_transition_schedule_required')
        plan = TimelinePlan(contract_version=1, calendar={}, opening_revision=q.context,
            opening_day=time.tick, schedules=[], events=[], adoptions=[])
        transition = TransitionPlan(contract_version=1, opening=None, account_bindings=[],
            instance_order=[], carry_priority='existing_first', operation_limit=100000)
        service.create(StartExperiment(request=CreateExperiment(boundary_contract=1, context=context,
            operation_id=q.operation_id, plan=plan, conditions=[], transition_plan=transition), checkpoint_interval=10))
    elif q.action == 'advance':
        if q.expected is None or q.expected.context != context:
            raise ValueError('expected_confirmed_boundary_required')
        service.advance(AdvanceExperiment(expected=q.expected, operation_id=q.operation_id,
            target_day=q.target_day, max_boundaries=10))
    elif q.action in ('pause', 'resume', 'cancel'):
        if q.control is None:
            raise ValueError('expected_control_required')
        service.control(ControlExperiment(context=context, operation_id=q.operation_id, expected=q.control,
            state={'pause':'paused', 'resume':'ready', 'cancel':'cancelled'}[q.action]))
    elif q.action in ('fork', 'schedule', 'preview_schedule'):
        if q.other_id is None or q.other_id == q.experiment_id or q.expected is None or q.expected.context != context:
            raise ValueError('distinct_fork_and_confirmed_source_required')
        source = service.boundaries.read(context, q.sequence)
        if outcome(source.record) != q.expected:
            raise ValueError('fork_source_mismatch')
        if q.action in ('schedule', 'preview_schedule') and outcome(service.boundaries.read(context).record) != q.expected:
            raise ValueError('future_schedule_requires_current_head')
        _, parent = service.boundaries._experiment(context)
        adoptions = [a for a in parent.plan.adoptions if a.effective_day > source.record.day]
        if q.action in ('schedule', 'preview_schedule'):
            if q.source_revision_id is None or q.target_day <= source.record.day:
                raise ValueError('future_approved_revision_required')
            approved = revisions.read(q.context.model_copy(update={'revision_id':q.source_revision_id}))
            if approved.parent_id is None:
                raise ValueError('approved_policy_change_required')
            base = revisions.read(approved.context.model_copy(update={'revision_id':approved.parent_id}))
            before = {p.id:p for p in base.inputs.design.policies}
            after = {p.id:p for p in approved.inputs.design.policies}
            deltas = [BindingDelta(binding_id=i, scope_id=(after.get(i) or before[i]).scope_id,
                expected_digest=None if i not in before else digest(before[i]), replacement=after.get(i))
                for i in sorted(before.keys() | after.keys()) if before.get(i) != after.get(i)]
            adoptions.append(PolicyAdoption(id='adoption:'+digest(q.operation_id), effective_day=q.target_day,
                order=0, origin='player_approved', source_revision=approved.context, base_revision=base.context,
                deltas=deltas, preconditions=[], transition='binding_only', source_refs=[]))
        plan = TimelinePlan.model_validate(parent.plan.model_dump() | dict(opening_day=source.record.day,
            events=[e for e in parent.plan.events if e.effective_day > source.record.day], adoptions=adoptions))
        proposed_plan = plan
        if q.action != 'preview_schedule':
            context = context.model_copy(update={'experiment_id':q.other_id})
            service.fork(ForkExperiment(operation_id=q.operation_id, source=q.expected, context=context,
                plan=plan, checkpoint_interval=10, realization_policy=q.realization_policy, seed=q.seed))
    if q.action not in ('read', 'preview_schedule'):
        with store.transaction():
            old = store.read_record(directory, 'experiment', context.experiment_id)
            if old is None:
                store.add_record(directory, 'experiment', context.experiment_id, context.model_dump_json())
    experiments = [i for i, _ in store.record_page(directory, 'experiment', limit=100)]
    indexed = store.read_record(directory, 'experiment', context.experiment_id) is not None
    if indexed and context.experiment_id not in experiments:
        experiments = [*experiments[:99], context.experiment_id]
    if not indexed and q.action == 'read':
        return TimelineReply(query=q, experiments=experiments, head=None, checkpoint=None, opening=None, origin=None,
            control=None, entries=[], next_after=None, schedule=[], assumptions=[], differences=[], comparisons=[], indicators=[], distributions=[],
            notice='Select an experiment or create one from this design. Legacy calendars require an explicit supported opening.')
    manifest, control, head = service.query(context)
    opening = service.boundaries.read(context, 0)
    _, experiment = service.boundaries._experiment(context)
    first = 0 if q.after is None or q.action != 'read' else q.after + 1
    entries = []
    for seq in range(first, min(first + 10, head.record.sequence + 1)):
        saved = service.boundaries.read(context, seq)
        receipt, changes = saved.state.transition, saved.record.changes
        consequences = ([] if changes is None else [serialized(x) for x in [*changes.events, *changes.adoptions]])
        if receipt is not None:
            consequences += [serialized(s) for s in receipt.steps]
        entries.append(TimelineEntry(sequence=seq, day=saved.record.day, digest=saved.record.boundary_digest,
            coverage='opening' if receipt is None else receipt.coverage if receipt.steps else 'No selected dynamic mechanisms', consequences=consequences,
            trace_count=len(saved.evidence.report.traces),
            traces=[serialized(t) for t in saved.evidence.report.traces[q.trace_offset:q.trace_offset+100]], draws=[] if receipt is None else receipt.random_draws, values=compare(saved, saved, q.indicator_id)))
    indicators = {d.id for d in head.evidence.report.definitions}
    comparisons, differences = [], []
    if q.action == 'read' and q.other_id:
        other = context.model_copy(update={'experiment_id':q.other_id})
        _, _, right = service.query(other, q.sequence)
        left = service.boundaries.read(context, q.sequence)
        differences = semantics(service, context, other)
        comparisons = compare(left, right, q.indicator_id)
        indicators |= {d.id for d in right.evidence.report.definitions}
        if left.record.day != right.record.day:
            differences.insert(0, 'Incompatible effective time; numerical deltas unavailable.')
    displayed_plan = proposed_plan or experiment.plan
    schedule = []
    for entry in sorted([*displayed_plan.events, *displayed_plan.adoptions], key=lambda x: (x.effective_day, x.order, x.id)):
        if isinstance(entry, PolicyAdoption):
            detail = 'Approved revision ' + entry.source_revision.revision_id + '; policy bindings: ' + ', '.join(d.binding_id + ' at ' + d.scope_id + ' (requires ' + (d.expected_digest or 'absence') + ') → ' + ('remove' if d.replacement is None else serialized(d.replacement.value)) for d in entry.deltas)
        else:
            detail = 'Authored conditions: ' + ', '.join(c.condition_id + ' at ' + c.scope_id + ' = ' + serialized(c.value) for c in entry.changes)
        schedule.append(f'Day {entry.effective_day} · order {entry.order} · {entry.origin} · {entry.id}: {detail}')
    schedule += [f'Mechanism {s.instance_id}: first day {s.first_day}, every {s.interval_days} simulation days' for s in displayed_plan.schedules]
    assumptions = [serialized(a) for a in head.state.inputs.assumptions]
    if experiment.transition_plan is not None and experiment.transition_plan.random_plan is not None:
        assumptions.append('Selected stochastic model: ' + serialized(experiment.transition_plan.random_plan))
    else:
        assumptions.append('No probability distribution selected; a single trajectory is not a distribution.')
    checkpoint_rows = store.record_page(service.boundaries._scope(context), CHECKPOINTS, limit=1, descending=True)
    checkpoint = Checkpoint.model_validate_json(checkpoint_rows[0][1]).boundary if checkpoint_rows else None
    reply = TimelineReply(query=q, experiments=experiments, head=outcome(head.record), checkpoint=checkpoint, opening=outcome(opening.record),
        origin=manifest.origin, control=control, entries=entries,
        next_after=entries[-1].sequence if entries and entries[-1].sequence < head.record.sequence else None,
        schedule=schedule, assumptions=assumptions, differences=differences, comparisons=comparisons,
        indicators=sorted(indicators),
        distributions=[] if experiment.transition_plan is None or experiment.transition_plan.random_plan is None else experiment.transition_plan.random_plan.draws,
        notice=('Schedule preview; no experiment or boundary was changed. Review effective scope, binding preconditions and changes before scheduling. ' if q.action == 'preview_schedule' else '') + 'Confirmed boundaries only. Displayed range does not execute time. Dynamic effects require reviewed activated models; unchanged outcomes do not establish dynamic validity.')
    if q.action not in ('read', 'preview_schedule'):
        with store.transaction():
            store.complete_operation(directory, opkey, binding, reply.model_dump_json())
    return reply
