"""Production SQLite boundary semantics; synthetic dynamics with a Fraction oracle."""
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError
from poliscope_engine.boundaries import BoundaryStore, BoundaryError, outcome
from poliscope_engine.contracts.boundaries import (
    CreateExperiment, ConfirmBoundary, BoundaryCandidate, ExperimentContext)
from poliscope_engine.contracts.revisions import RevisionInputs
from poliscope_engine.contracts.timeline import TimelinePlan
from poliscope_engine.contracts.world import EffectiveTime
from poliscope_engine.evaluation import evaluate
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.explanation import retain
from poliscope_engine.measurements import observe
from poliscope_engine.numeric import canonical, exact
from poliscope_engine.revisions import Revisions, graph
from poliscope_engine.storage import Store, StorageError
from poliscope_engine.storage.blobs import RetainedBlobs
from test_revisions import inputs, value, mechanism_registry, create_request, count

CALENDAR = 'fixed-364-v1'


def validate_stock(check):
    """Independent declared fixture: consume one stock per elapsed day, nothing else."""
    old = {v.property_id: v for v in check.opening.state.inputs.values}
    new = {v.property_id: v for v in check.closing.inputs.values}
    elapsed = check.due.day - check.opening.record.day
    assert Fraction(new['stock'].value.value) == Fraction(old['stock'].value.value) - elapsed
    assert Fraction(new['stock'].value.value) >= 0
    for key in old.keys() - {'stock'}:
        assert new[key] == old[key]


def experiment_request(revisions, context, **updates):
    return CreateExperiment.model_validate(dict(boundary_contract=1,
        context=dict(data_store_id=revisions.data_store_id, civilization_id='civ', experiment_id='run'),
        operation_id='open-run', plan=dict(contract_version=1, calendar={}, opening_revision=context,
            opening_day=0, schedules=[dict(instance_id='a', interval_days=1, first_day=1)],
            events=[], adoptions=[]), conditions=[]) | updates)


@pytest.fixture
def running(tmp_path):
    with Store(tmp_path) as store:
        revisions = Revisions(store, registry=mechanism_registry())
        initial = inputs().model_dump()
        initial['design']['effective_time'] = dict(tick=0, calendar_id=CALENDAR)
        for prop, number in [('stock', '37'), ('assets', '3'), ('cases', '1')]:
            initial['values'].append(value(number).model_copy(update={
                'id': prop, 'property_id': prop, 'partition': 'dynamic_state',
                'effective_time': EffectiveTime(tick=0, calendar_id=CALENDAR)}).model_dump())
            initial['owners'].append(dict(entity_id='supply', property_id=prop,
                partition='dynamic_state', writer_id='synthetic:stock-validator'))
        created = revisions.create(create_request(revisions, inputs=initial))
        service = BoundaryStore(revisions, validator=validate_stock, validator_id='synthetic:stock-validator:v1')
        request = experiment_request(revisions, created.context)
        opened = service.create(request)
        yield service, request, opened


def confirm_request(service, opening, *, day=None, stock=None, operation_id='advance'):
    previous = service.read(opening.context, opening.sequence)
    data = previous.state.inputs.model_dump()
    next_day = opening.day + 1 if day is None else day
    data['design']['effective_time']['tick'] = next_day
    for row in data['values']:
        if row['property_id'] == 'stock':
            amount = Fraction(row['value']['value']) - (next_day - opening.day) if stock is None else Fraction(stock)
            row['value']['value'] = canonical(exact(amount))
            row['effective_time']['tick'] = next_day
    closing = RevisionInputs.model_validate(data)
    result = evaluate(graph(closing, opening.context.civilization_id), closing.design, closing.assumptions,
        service.revisions.registry.model, registry=service.revisions.registry)
    evidence = retain(result, observe(result, closing.measurements, closing.goals), closing.references)
    return ConfirmBoundary(boundary_contract=1, expected=opening, operation_id=operation_id,
        candidate=BoundaryCandidate(inputs=closing, evidence=evidence))


def test_create_freezes_real_revision_plan_opening_and_complete_evidence(running):
    service, request, opened = running
    saved = service.read(opened.context)
    assert saved.state.inputs == service.revisions.read(request.plan.opening_revision).inputs
    assert saved.evidence == service.revisions.evidence(request.plan.opening_revision)
    assert saved.record.sequence == saved.record.day == 0
    assert service.status(request) == opened
    before = count(service.revisions)
    assert service.create(request) == opened
    assert count(service.revisions) == before
    request.plan.schedules.clear()
    saved.state.inputs.values.clear()
    assert len(service.read(opened.context).state.inputs.values) == 4
    assert service._experiment(opened.context)[1].plan.schedules


def test_atomic_confirmation_retains_state_trace_closure_and_operation(running):
    service, request, opened = running
    first_request = confirm_request(service, opened)
    first = service.confirm(first_request)
    saved = service.read(opened.context)
    assert saved.record.parent_digest == opened.boundary_digest
    assert saved.record.boundary_digest == first.boundary_digest
    assert saved.record.due.mechanism_ids == ['a']
    assert saved.record.validator_id == 'synthetic:stock-validator:v1'
    assert saved.evidence.evaluation.input_json != service.read(opened.context, 0).evidence.evaluation.input_json
    assert next(v.value.value for v in saved.state.inputs.values if v.property_id == 'stock') == '36'
    assert saved.state.inputs.design.realization == first_request.candidate.inputs.design.realization
    assert service.status(first_request) == first
    assert service.read(opened.context, 0).record.boundary_digest == opened.boundary_digest
    assert service.store.read_evidence(service._scope(opened.context), 'boundary-evidence:' + saved.evidence.closure_digest)


def test_retry_replays_original_after_head_advance_and_validator_removed(running):
    service, _, opened = running
    request = confirm_request(service, opened)
    first = service.confirm(request)
    second = service.confirm(confirm_request(service, first, operation_id='second'))
    service.validator = None
    service.revisions.registry = None
    before = count(service.revisions)
    assert service.confirm(request) == first
    assert service.status(request) == first
    assert outcome(service.read(opened.context).record) == second
    assert count(service.revisions) == before


def test_operation_ids_are_bound_to_payload_action_and_context(running):
    service, create, opened = running
    request = confirm_request(service, opened)
    service.confirm(request)
    for changed in [request.model_copy(update={'candidate': confirm_request(service, opened, stock='35').candidate}),
                    request.model_copy(update={'operation_id': create.operation_id})]:
        with pytest.raises(StorageError, match='different request'):
            service.confirm(changed)
    foreign = opened.context.model_copy(update={'experiment_id': 'foreign'})
    assert service.status(request.model_copy(update={'expected': opened.model_copy(update={'context': foreign})})) is None
    with pytest.raises(BoundaryError, match='unknown_experiment'):
        service.read(foreign)
    with pytest.raises(BoundaryError, match='wrong_data_store'):
        service.read(opened.context.model_copy(update={'data_store_id': 'foreign'}))


def test_stale_request_invalid_invariant_missing_validator_do_not_write(running):
    service, _, opened = running
    wrong = confirm_request(service, opened, stock='999')
    before = count(service.revisions)
    with pytest.raises(AssertionError):
        service.confirm(wrong)
    assert count(service.revisions) == before
    valid = confirm_request(service, opened)
    service.validator = None
    with pytest.raises(BoundaryError, match='validator_unavailable'):
        service.confirm(valid)
    service.validator = validate_stock
    service.confirm(valid)
    with pytest.raises(BoundaryError, match='stale_boundary'):
        service.confirm(confirm_request(service, opened, operation_id='stale'))


def test_skipping_required_boundary_or_mismatching_evidence_fails(running):
    service, _, opened = running
    with pytest.raises(BoundaryError, match='skipped_required_boundary'):
        service.confirm(confirm_request(service, opened, day=7))
    request = confirm_request(service, opened)
    tampered = request.candidate.inputs.model_dump()
    tampered['values'][0]['value']['value'] = '100'
    candidate = request.candidate.model_copy(update={'inputs': RevisionInputs.model_validate(tampered)})
    with pytest.raises(BoundaryError, match='evidence_state_mismatch'):
        service.confirm(request.model_copy(update={'candidate': candidate}))
    assert service.read(opened.context).record.sequence == 0


@pytest.mark.parametrize('cancel_at', [1, 2, 3, 4])
def test_cancellation_at_each_confirmation_checkpoint_rolls_back(running, cancel_at):
    service, _, opened = running
    request = confirm_request(service, opened)
    before = count(service.revisions)
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls == cancel_at
    with pytest.raises(BoundaryError, match='boundary_cancelled'):
        service.confirm(request, cancelled=cancelled)
    assert count(service.revisions) == before
    assert service.status(request) is None
    assert outcome(service.read(opened.context).record) == opened
    assert service.confirm(request).sequence == 1


def test_failure_at_every_storage_write_discards_all_effects(running, monkeypatch):
    service, _, opened = running
    request = confirm_request(service, opened)
    before = count(service.revisions)
    originals = {name: getattr(service.store, name) for name in ('add_record', 'retain_evidence', 'complete_operation')}
    # Discover actual write count via an intentionally rolled-back transaction.
    writes = []
    for name, original in originals.items():
        def track(*args, _name=name, _original=original, **kwargs):
            writes.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(service.store, name, track)
    with pytest.raises(BoundaryError):
        service.confirm(request, cancelled=lambda: len(writes) > 0)
    assert writes and count(service.revisions) == before
    total = len(writes)
    for failing in range(1, total + 1):
        seen = []
        for name, original in originals.items():
            def fail(*args, _name=name, _original=original, **kwargs):
                seen.append(_name)
                result = _original(*args, **kwargs)
                if len(seen) == failing:
                    raise RuntimeError('injected write failure')
                return result
            monkeypatch.setattr(service.store, name, fail)
        with pytest.raises(RuntimeError, match='injected write failure'):
            service.confirm(request)
        assert count(service.revisions) == before
        assert service.status(request) is None
        assert outcome(service.read(opened.context).record) == opened


@pytest.mark.parametrize('after_commit', [False, True])
def test_commit_failure_or_lost_ack_recovers_exact_confirmed_outcome(running, monkeypatch, after_commit):
    service, _, opened = running
    request = confirm_request(service, opened)
    original = service.store.transaction
    @contextmanager
    def fault():
        with original():
            yield
            if not after_commit:
                raise RuntimeError('before commit')
        if after_commit:
            raise RuntimeError('lost acknowledgment')
    monkeypatch.setattr(service.store, 'transaction', fault)
    with pytest.raises(RuntimeError):
        service.confirm(request)
    monkeypatch.setattr(service.store, 'transaction', original)
    saved = service.read(opened.context)
    assert saved.record.sequence == int(after_commit)
    assert (service.status(request) is not None) == after_commit
    assert service.confirm(request).sequence == 1


@pytest.mark.parametrize('after_commit', [False, True])
def test_actual_process_crash_before_or_after_commit_reopens_one_boundary(running, tmp_path, after_commit):
    service, _, opened = running
    request = confirm_request(service, opened)
    path = tmp_path / 'request.json'
    path.write_text(request.model_dump_json())
    code = '''
from contextlib import contextmanager
import os, sys
from pathlib import Path
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.boundaries import BoundaryStore
from poliscope_engine.contracts.boundaries import ConfirmBoundary
from test_boundaries import validate_stock
with Store(Path(sys.argv[1])) as store:
    service = BoundaryStore(Revisions(store, registry=None), validator=validate_stock, validator_id='synthetic:stock-validator:v1')
    original = store.transaction
    @contextmanager
    def crash():
        with original():
            yield
            if sys.argv[3] == 'before': os._exit(71)
        os._exit(72)
    store.transaction = crash
    service.confirm(ConfirmBoundary.model_validate_json(Path(sys.argv[2]).read_text()))
'''
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(Path('engine').resolve()), str(Path('tests/engine').resolve())])
    process = subprocess.run([sys.executable, '-c', code, str(tmp_path), str(path),
                              'after' if after_commit else 'before'], env=env, capture_output=True, text=True)
    assert process.returncode == (72 if after_commit else 71), process.stderr
    with Store(tmp_path) as reopened:
        reader = BoundaryStore(Revisions(reopened, registry=None))
        assert reader.read(opened.context).record.sequence == int(after_commit)
        assert (reader.status(request) is not None) == after_commit
        if after_commit:
            assert reader.confirm(request) == outcome(reader.read(opened.context).record)


def test_other_connection_sees_only_confirmed_head_during_each_write(running, tmp_path, monkeypatch):
    service, _, opened = running
    request = confirm_request(service, opened)
    with Store(tmp_path) as other_store:
        other = BoundaryStore(Revisions(other_store, registry=None))
        for name in ('add_record', 'retain_evidence', 'complete_operation'):
            original = getattr(service.store, name)
            def inspect(*args, _original=original, **kwargs):
                result = _original(*args, **kwargs)
                assert outcome(other.read(opened.context).record) == opened
                assert other.status(request) is None
                return result
            monkeypatch.setattr(service.store, name, inspect)
        accepted = service.confirm(request)
        assert outcome(other.read(opened.context).record) == accepted
        assert other.status(request) == accepted


def test_cache_eviction_detached_reads_and_reopen_preserve_all_evidence(running, tmp_path):
    service, _, opened = running
    request = confirm_request(service, opened)
    accepted = service.confirm(request)
    scope = service._scope(opened.context)
    with service.store.transaction():
        service.store.cache(scope, 'disposable', '{}')
        service.store.clear_caches()
    with Store(tmp_path) as store:
        reader = BoundaryStore(Revisions(store, registry=None))
        historical = reader.read(opened.context, 0)
        current = reader.read(opened.context)
        assert current.record.parent_digest == historical.record.boundary_digest
        assert reader.confirm(request) == accepted
        current.state.inputs.values.clear()
        assert len(reader.read(opened.context).state.inputs.values) == 4
        assert reader.read(opened.context).evidence.evaluation.identities == request.candidate.evidence.evaluation.identities


def test_bad_openings_roll_back_context_evidence_and_operation(running):
    service, request, _ = running
    context = request.context.model_copy(update={'experiment_id': 'bad-opening'})
    before = count(service.revisions)
    bad = request.model_copy(update={'context': context, 'plan': request.plan.model_copy(update={'opening_day': 2})})
    with pytest.raises(BoundaryError, match='opening_calendar_mismatch'):
        service.create(bad)
    assert service.status(bad) is None
    assert count(service.revisions) == before
    with pytest.raises(BoundaryError, match='unknown_experiment'):
        service.read(context)


def test_multichunk_unicode_blobs_and_corruption_fail_closed(running, monkeypatch):
    service, _, opened = running
    scope = service._scope(opened.context)
    payload = {'text': '\u2603' * 600000}
    blobs = RetainedBlobs(service.store)
    with service.store.transaction():
        blobs.put(scope, 'large-fixture', 'unicode', payload, evidence=True)
    assert json.loads(blobs.read(scope, 'large-fixture', 'unicode', evidence=True)) == payload
    before = count(service.revisions)
    with service.store.transaction():
        blobs.put(scope, 'large-fixture', 'unicode', payload, evidence=True)
    assert count(service.revisions) == before
    read = service.store.read_record
    def corrupt(context, kind, identity):
        if kind == 'chunk:large-fixture' and identity == 'unicode:0':
            return json.dumps('forged')
        return read(context, kind, identity)
    monkeypatch.setattr(service.store, 'read_record', corrupt)
    with pytest.raises(StorageError, match='digest_mismatch'):
        blobs.read(scope, 'large-fixture', 'unicode', evidence=True)


def test_callback_receives_detached_staging_and_cas_rejects_competing_advance(running, tmp_path):
    service, _, opened = running
    request = confirm_request(service, opened)
    with Store(tmp_path) as other_store:
        other = BoundaryStore(Revisions(other_store, registry=None),
            validator=validate_stock, validator_id='synthetic:stock-validator:v1')
        def compete(check):
            validate_stock(check)
            check.closing.inputs.values.clear()
            other.confirm(request.model_copy(update={'operation_id': 'competing-advance'}))
        service.validator = compete
        with pytest.raises(BoundaryError, match='stale_boundary'):
            service.confirm(request)
        assert service.status(request) is None
        assert len(service.read(opened.context).state.inputs.values) == 4
        assert service.read(opened.context).record.sequence == 1


def test_opening_cancellation_after_persistence_rolls_back_every_table(running):
    service, request, _ = running
    context = request.context.model_copy(update={'experiment_id': 'cancel-opening'})
    request = request.model_copy(update={'context': context})
    before = count(service.revisions)
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        return calls == 2
    with pytest.raises(BoundaryError, match='boundary_cancelled'):
        service.create(request, cancelled=cancel)
    assert count(service.revisions) == before
    assert service.status(request) is None
    assert service.create(request).sequence == 0


# Reuse the real accepted-policy registry fixture; all approval records still go
# through production SQLite Revisions.preview/apply, rather than a mock reader.
from test_timeline import approved


def test_actual_same_day_event_adoption_conflict_gap_survive_reopen(approved, tmp_path):
    from poliscope_engine.contracts.revisions import PreviewRequest, ApplyRequest
    from poliscope_engine.contracts.world import LabelValue
    from poliscope_engine.timeline import stage_changes
    from test_timeline import adoption
    revisions, original_base, original_source = approved
    data = original_base.inputs.model_dump()
    data['design']['effective_time'] = dict(tick=0, calendar_id=CALENDAR)
    def accept(context, data, op):
        preview = PreviewRequest.model_validate(dict(revision_contract=1, context=context,
            changes=[dict(kind='replace_inputs', inputs=data)],
            decision=dict(alternatives=[], selected_id=None, rationale_ref=None)))
        candidate = revisions.preview(preview)
        result = revisions.apply(ApplyRequest(revision_contract=1, preview=preview,
            candidate_digest=candidate.candidate_digest, operation_id=op))
        return revisions.read(result.context)
    base = accept(original_source.context, data, 'calendar-base')
    changed = deepcopy(data)
    for binding in changed['design']['policies']:
        binding['value']['value'] = '10'
    source = accept(base.context, changed, 'approved-future-policies')
    yes = LabelValue(kind='label', value='approved')
    a = adoption(base, source, 'a', effective_day=1, preconditions=[
        dict(condition_id='ready', scope_id='local', expected_digest=digest(yes))])
    conflict = adoption(base, source, 'b-conflict', effective_day=1, order=1)
    gap = adoption(base, source, 'c-gap', ('policy-b',), effective_day=1, order=2, transition='unsupported')
    plan = TimelinePlan.model_validate(dict(contract_version=1, calendar={}, opening_revision=base.context,
        opening_day=0, schedules=[dict(instance_id='a', interval_days=1, first_day=1)],
        events=[dict(id='ready', effective_day=1, order=0, origin='external', source_refs=[], changes=[
            dict(condition_id='ready', scope_id='local', expected_digest=None, value=yes)])],
        adoptions=[a, conflict, gap]))
    service = BoundaryStore(revisions, validator=validate_stock, validator_id='synthetic:stock-validator:v1')
    request = experiment_request(revisions, base.context, plan=plan)
    opened = service.create(request)
    closing = base.inputs.model_dump()
    closing['design']['effective_time']['tick'] = 1
    expected, _ = stage_changes(plan, 1, base.inputs.design.policies, {}, read_revision=revisions.read)
    closing['design']['policies'] = [p.model_dump() for p in expected.policies]
    for row in closing['values']:
        if row['property_id'] == 'stock':
            row['value']['value'] = '36'
            row['effective_time']['tick'] = 1
    closing = RevisionInputs.model_validate(closing)
    evaluation = evaluate(graph(closing, 'civ'), closing.design, closing.assumptions,
        revisions.registry.model, registry=revisions.registry)
    evidence = retain(evaluation, observe(evaluation, closing.measurements, closing.goals), closing.references)
    confirm = ConfirmBoundary(boundary_contract=1, expected=opened, operation_id='same-day',
        candidate=BoundaryCandidate(inputs=closing, evidence=evidence))
    accepted = service.confirm(confirm)
    with Store(tmp_path) as reopened:
        reader = BoundaryStore(Revisions(reopened, registry=None))
        saved = reader.read(opened.context)
        assert [a.status for a in saved.record.changes.adoptions] == ['applied', 'conflict', 'coverage_gap']
        assert saved.record.changes.events[0].status == 'applied'
        assert saved.state.conditions[0].value == yes
        assert saved.state.inputs.design.policies[1] == base.inputs.design.policies[1]
        assert reader.confirm(confirm) == accepted
        assert reader.read(opened.context, 0).state.inputs == base.inputs
        assert revisions.read(base.context) == base


def test_large_actual_evidence_confirms_with_compact_payload_binding(running, tmp_path):
    source, create, opened = running
    initial = source.read(opened.context).state.inputs.model_dump()
    for index in range(8):
        row = deepcopy(initial['values'][0])
        row.update(id=f'large-{index}', property_id=f'large-{index}', value={'kind': 'label', 'value': 'x' * 100000})
        initial['values'].append(row)
        initial['owners'].append(dict(entity_id='supply', property_id=f'large-{index}',
            partition='design', writer_id='player'))
    with Store(tmp_path / 'large') as store:
        revisions = Revisions(store, registry=mechanism_registry())
        created = revisions.create(create_request(revisions, inputs=initial))
        service = BoundaryStore(revisions, validator=validate_stock, validator_id='synthetic:stock-validator:v1')
        opened = service.create(experiment_request(revisions, created.context))
        request = confirm_request(service, opened)
        assert len(request.model_dump_json().encode()) > 1024 * 1024
        accepted = service.confirm(request)
        assert service.status(request) == accepted
        assert len(service.read(opened.context).state.inputs.values) == 12
        assert service.read(opened.context).evidence == request.candidate.evidence


def test_same_connection_reentrant_queries_never_expose_uncommitted_boundary(running):
    service, _, opened = running
    request = confirm_request(service, opened)
    calls = 0
    def inspect_and_cancel():
        nonlocal calls
        calls += 1
        if calls == 4:  # journal, evidence and outcome are staged but uncommitted
            for reader in (service, BoundaryStore(service.revisions)):
                for query in [lambda: reader.read(opened.context), lambda: reader.status(request),
                              lambda: reader.confirm(request)]:
                    with pytest.raises(BoundaryError, match='unconfirmed_write_in_progress'):
                        query()
            return True
        return False
    with pytest.raises(BoundaryError, match='boundary_cancelled'):
        service.confirm(request, cancelled=inspect_and_cancel)
    assert outcome(service.read(opened.context).record) == opened
    assert service.status(request) is None
