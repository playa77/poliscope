"""WP-037 uses actual retained revisions and controller, never a renderer simulation."""
from poliscope_engine.boundaries import outcome
import pytest
from poliscope_engine.storage import Store
from poliscope_engine.workspace import dispatch, registry
from poliscope_engine.revisions import Revisions
from poliscope_engine.timeline_workspace import page, compare, semantics
from poliscope_engine.contracts.timeline_workspace import TimelineRequest
from poliscope_engine.evaluation.identity import digest
from test_experiments import setup, advance, fork_request


def world(store):
    revisions = Revisions(store, registry=registry())
    state = dispatch(revisions, 'create', dict(name='Timeline', setup='blank', scope_name='Home', population=None, land_area=None), 'timeline-test')
    return revisions, state


def request(state, action='read', **updates):
    return TimelineRequest.model_validate(dict(context=state.context, action=action,
        experiment_id='run', operation_id='op-'+action) | updates).model_dump()


def test_public_create_advance_pause_cancel_fork_and_reopen(tmp_path):
    with Store(tmp_path) as store:
        rev, state = world(store)
        assert page(rev, request(state)).head is None
        created = page(rev, request(state, 'create'))
        assert created.head.day == 0 and created.opening == created.head
        req = request(state, 'advance', expected=created.head, target_day=40)
        advanced = page(rev, req)
        assert advanced.head.day == 40
        assert [e.day for e in advanced.entries] == [0,40]  # display is not a daily execution schedule
        paused = page(rev, request(state, 'pause', control=advanced.control))
        blocked = page(rev, request(state, 'advance', operation_id='paused-advance', expected=paused.head, target_day=41))
        assert blocked.head == advanced.head
        resumed = page(rev, request(state, 'resume', control=paused.control))
        cancelled = page(rev, request(state, 'cancel', control=resumed.control))
        assert cancelled.control.state == 'cancelled'
        fork = page(rev, request(state, 'fork', expected=created.head, other_id='past', sequence=0))
        assert fork.head.day == 0 and fork.origin == created.head
        assert page(rev, req) == advanced  # exact retry before stale/current/control checks
        assert page(rev, request(state)).head == advanced.head
    with Store(tmp_path) as store:
        rev = Revisions(store, registry=registry())
        assert page(rev, request(state, experiment_id='past')).origin == created.head
        assert page(rev, request(state)).control.state == 'cancelled'


def test_unconfirmed_invalid_foreign_or_rebound_command_never_changes_saved_head(tmp_path):
    with Store(tmp_path) as store:
        rev, state = world(store)
        opened = page(rev, request(state, 'create'))
        with pytest.raises(ValueError):
            page(rev, request(state, 'advance', target_day=1))
        with pytest.raises(ValueError):
            page(rev, request(state, 'create', experiment_id='other'))
        bad = opened.head.model_copy(update={'boundary_digest':'sha256:'+'0'*64})
        with pytest.raises(ValueError):
            page(rev, request(state, 'advance', expected=bad, target_day=2, operation_id='invalid-head'))
        assert page(rev, request(state)).head == opened.head
        foreign = state.context.model_copy(update={'civilization_id':'foreign'})
        with pytest.raises(ValueError):
            page(rev, request(state, context=foreign))


def test_display_pagination_stops_at_confirmed_head(tmp_path):
    with Store(tmp_path) as store:
        service, opening, original = setup(store)
        result = service.advance(advance(opening, target=14))
        # Index a controlled fixture through a real command, then read its retained pages.
        q = dict(context=original.plan.opening_revision, action='pause', experiment_id='controlled',
            operation_id='index', control=service.query(opening.context)[1])
        first = page(service.reducer.revisions, q, service=service)
        assert len(first.entries) == 10 and first.next_after == 9
        second = page(service.reducer.revisions, q | dict(action='read', after=9), service=service)
        assert [e.sequence for e in second.entries] == [10,11,12,13,14]
        assert second.next_after is None and second.head == result.head
        assert first.entries[1].consequences
        assert all(e.digest != opening.boundary_digest for e in second.entries)


def test_retained_comparison_never_invents_missing_measurements_or_zero(tmp_path):
    with Store(tmp_path) as store:
        service, opening, _ = setup(store)
        service.advance(advance(opening, target=2))
        left = service.boundaries.read(opening.context, 1)
        right = service.boundaries.read(opening.context, 2)
        rows = compare(left, right)
        assert all(r.delta is None and 'Incompatible effective time' in r.reasons for r in rows)
        # Input differences include clock/schedule and preserve the original run.
        before = digest(right)
        fork = service.fork(fork_request(service, opening))
        assert any('schedule changed' in d for d in semantics(service, opening.context, fork.context)) is False
        assert digest(service.boundaries.read(opening.context)) == before


def test_future_schedule_requires_actual_approved_policy_and_current_head(tmp_path):
    with Store(tmp_path) as store:
        rev, state = world(store)
        opened = page(rev, request(state, 'create'))
        with pytest.raises(ValueError, match='approved_policy_change_required'):
            page(rev, request(state, 'schedule', expected=opened.head, source_revision_id=state.context.revision_id,
                other_id='future', target_day=3))
        assert page(rev, request(state, experiment_id='future')).head is None
        assert page(rev, request(state)).head == opened.head


def test_future_policy_and_retrospective_fork_have_distinct_actual_histories(tmp_path):
    from transition_fixture import fixture, start
    from test_policies import definition as policy_definition, binding, edge
    from test_mechanism_registry import registry as host_registry, PROVENANCE
    from poliscope_engine.contracts.revisions import RevisionInputs, PreviewRequest, ApplyRequest
    from poliscope_engine.contracts.boundaries import CreateExperiment
    from poliscope_engine.contracts.experiments import StartExperiment
    from poliscope_engine.experiments import Experiments
    mechanisms, catalog, initial, transition = fixture()
    policy = policy_definition()
    policy_host = host_registry([policy], units=mechanisms.units, times=mechanisms.times)
    mechanisms = host_registry([*mechanisms.definitions,policy],
        implementations=[*mechanisms.implementations,*policy_host.implementations],
        units=mechanisms.units, times=mechanisms.times)
    data = initial.model_dump()
    data['entities'].append(dict(id='local-authority',entity_kind='institution',label='Synthetic authority',provenance=PROVENANCE))
    data['relationships'].append(edge('jurisdiction','local-authority','local').model_dump())
    data['design']['policies'] = [binding('policy',entity_ids=['service-a'],account_refs=['material'],choice_refs=[],
        value=dict(kind='quantity',value='2',unit_id='kg',time_basis_id=None,denominator_scope_id=None)).model_dump()]
    with Store(tmp_path) as store:
        reducer, _, original = start(store, mechanisms, catalog, RevisionInputs.model_validate(data), transition)
        service = Experiments(reducer)
        opening_request = CreateExperiment.model_validate(original.model_dump() | dict(
            context=original.context.model_dump() | dict(experiment_id='controlled'), operation_id='controlled-create'))
        opened = service.create(StartExperiment(request=opening_request,checkpoint_interval=2))
        revisions = reducer.revisions
        base = revisions.read(original.plan.opening_revision)
        changed = base.inputs.model_dump()
        changed['design']['policies'][0]['value']['value'] = '9'
        preview = PreviewRequest.model_validate(dict(revision_contract=1, context=base.context,
            changes=[dict(kind='replace_inputs',inputs=changed)],decision=dict(alternatives=[],selected_id=None,rationale_ref=None)))
        candidate = revisions.preview(preview)
        approved = revisions.apply(ApplyRequest(revision_contract=1, preview=preview,
            candidate_digest=candidate.candidate_digest,operation_id='approve'))
        q = dict(context=base.context,experiment_id='controlled',action='schedule',operation_id='schedule',
            sequence=0,expected=opened,other_id='future',source_revision_id=approved.context.revision_id,target_day=3)
        before_preview = digest(service.boundaries.read(opened.context))
        previewed = page(revisions,q | dict(action='preview_schedule',operation_id='preview'),service=service)
        assert previewed.head == opened and 'Schedule preview' in previewed.notice
        assert previewed.schedule and digest(service.boundaries.read(opened.context)) == before_preview
        assert store.read_context(service.boundaries._scope(opened.context.model_copy(update={'experiment_id':'future'}))) is None
        future = page(revisions,q,service=service)
        assert future.head.day == 0 and 'player_approved' in future.schedule[0]
        service.advance(advance(future.head,target=3,operation='future-advance'))
        future_saved = service.boundaries.read(future.head.context)
        assert future_saved.state.inputs.design.policies[0].value.value == '9'
        assert future_saved.record.changes.adoptions[0].status == 'applied'
        assert service.boundaries.read(opened.context).state.inputs.design.policies[0].value.value == '2'
        past = page(revisions,q | dict(action='fork',operation_id='past',other_id='past',expected=outcome(future_saved.record),
            sequence=future_saved.record.sequence,experiment_id='future'),service=service)
        assert past.head.day == 3 and past.origin.day == 3
        assert digest(service.boundaries.read(future.head.context)) == digest(future_saved)
        retry = page(revisions,q,service=service)
        assert retry == future


@pytest.mark.parametrize('changed', ['time','clock','model','scope','missing'])
def test_experiment_comparison_explains_incompatible_semantics_with_actual_retained_values(tmp_path, changed):
    from types import SimpleNamespace
    from overview_fixture import seed, registry as measured_registry
    with Store(tmp_path) as store:
        rev = Revisions(store,registry=measured_registry())
        context = seed(rev).context
        record, evidence = rev.read(context), rev.evidence(context)
        left = SimpleNamespace(state=SimpleNamespace(inputs=record.inputs),evidence=evidence)
        right = SimpleNamespace(state=SimpleNamespace(inputs=record.inputs.model_copy(deep=True)),evidence=evidence.model_copy(deep=True))
        report = right.evidence.report
        if changed in ('time','clock'):
            observations = [o.model_copy(update={'effective_time':o.effective_time.model_copy(update={
                'tick': 1 if changed == 'time' else 0, 'calendar_id':'other' if changed == 'clock' else o.effective_time.calendar_id})}) for o in report.measurements]
            right.evidence = right.evidence.model_copy(update={'report':report.model_copy(update={'measurements':observations})})
        elif changed == 'model':
            right.state.inputs = right.state.inputs.model_copy(update={'versions':right.state.inputs.versions.model_copy(update={'model_id':'other'})})
        elif changed == 'scope':
            definitions = [d.model_copy(update={'scope_id':'other'}) for d in report.definitions]
            right.evidence = right.evidence.model_copy(update={'report':report.model_copy(update={'definitions':definitions})})
        else:
            right.evidence = right.evidence.model_copy(update={'report':report.model_copy(update={'measurements':[]})})
        row, = compare(left,right,'regional-reserve')
        assert row.left.observation.value.value == '200'
        assert row.delta is None and row.reasons
        if changed == 'missing':
            assert row.right.observation is None
        else:
            assert row.right.observation.value.value == '200'
