"""Checked internal publication agrees with independent external confirmation."""
import sqlite3
import pytest

from poliscope_engine.boundaries import BoundaryError
from poliscope_engine.contracts.boundaries import ConfirmBoundary
from poliscope_engine.evaluation.identity import serialized
from poliscope_engine.revisions import Revisions
from poliscope_engine.simulation import TransitionReducer
from poliscope_engine.storage import Store, StorageError
from transition_fixture import setup


def test_internal_advance_and_independent_confirm_retain_identical_history(tmp_path):
    fast_path, slow_path = tmp_path / 'fast', tmp_path / 'independent'
    with Store(fast_path) as fast_store:
        fast, opening, _ = setup(fast_store)
        slow_path.mkdir()
        with sqlite3.connect(slow_path / 'poliscope.sqlite3') as target:
            fast_store._connection.backup(target)
        with Store(slow_path) as slow_store:
            slow = TransitionReducer(Revisions(slow_store, registry=fast.mechanisms), catalog=fast.catalog)
            a = b = opening
            for day in range(1, 4):
                a = fast.advance_boundary(a, day, operation_id=f'day:{day}')
                candidate = slow.preview(b, day)
                b = slow.store.confirm(ConfirmBoundary(boundary_contract=1,
                    expected=b, candidate=candidate, operation_id=f'day:{day}'))
                assert a == b
                assert serialized(fast.store.read(a.context)) == serialized(slow.store.read(b.context))
            # A detached reader needs neither the reducer nor its disposable frame.
            fast.store._frames.clear()
            fast.revisions.clear_caches()
            assert serialized(fast.store.read(a.context)) == serialized(slow.store.read(b.context))


def test_prepared_candidate_mutation_and_foreign_capability_cannot_publish(tmp_path):
    with Store(tmp_path) as store:
        reducer, opening, _ = setup(store)
        candidate, prepared = reducer._preview(opening, 1)
        request = ConfirmBoundary(boundary_contract=1, expected=opening,
            candidate=candidate, operation_id='mutated')
        candidate.inputs.values[0].provenance.source_refs.append('forged')
        with pytest.raises(BoundaryError, match='transition_candidate_mismatch'):
            reducer.store._confirm_prepared(request, prepared)
        assert reducer.store.read(opening.context).record.day == 0
        candidate, prepared = reducer._preview(opening, 1)
        other = TransitionReducer(reducer.revisions, catalog=reducer.catalog)
        request = request.model_copy(update={'candidate': candidate})
        with pytest.raises(BoundaryError, match='transition_candidate_mismatch'):
            other.store._confirm_prepared(request, prepared)


def test_public_views_cannot_mutate_private_frame_and_missing_chunks_fail_closed(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        reducer, opening, _ = setup(store)
        current = reducer.advance_boundary(opening, 1, operation_id='first')
        snapshot = serialized(reducer.store.read(current.context))
        public = reducer.preview(current, 2)
        public.inputs.entities.clear()
        reducer.store.read(current.context).state.inputs.entities.clear()
        assert serialized(reducer.store.read(current.context)) == snapshot
        original = store.read_record
        def missing(context, kind, identity):
            return None if kind == 'chunk-content:v1' else original(context, kind, identity)
        monkeypatch.setattr(store, 'read_record', missing)
        with pytest.raises(StorageError, match='missing_boundary_chunk'):
            reducer.advance_boundary(current, 2, operation_id='second')
        monkeypatch.setattr(store, 'read_record', original)
        assert reducer.store.read(current.context).record.day == 1


def test_running_progress_reads_only_committed_bounded_projection(tmp_path, monkeypatch):
    with Store(tmp_path) as store:
        reducer, opening, _ = setup(store)
        current = reducer.advance_boundary(opening, 1, operation_id='first')
        def no_world(*args, **kwargs):
            raise AssertionError('progress loaded the whole world')
        monkeypatch.setattr(reducer.store, 'read', no_world)
        assert reducer.store.progress_coverage(current) == 'complete'
        real = store.read_record
        def damaged(context, kind, identity):
            if kind == 'boundary-progress:v1':
                return '{"boundary_digest":"wrong","coverage":"complete","projection_digest":"wrong"}'
            return real(context, kind, identity)
        monkeypatch.setattr(store, 'read_record', damaged)
        with pytest.raises(BoundaryError, match='boundary_progress_identity_mismatch'):
            reducer.store.progress_coverage(current)


def test_replacing_validator_invalidates_prepared_publication(tmp_path):
    with Store(tmp_path) as store:
        reducer, opening, _ = setup(store)
        candidate, prepared = reducer._preview(opening, 1)
        request = ConfirmBoundary(boundary_contract=1, expected=opening, candidate=candidate, operation_id='changed')
        reducer.store.validator = lambda _: None
        with pytest.raises(BoundaryError, match='transition_candidate_mismatch'):
            reducer.store._confirm_prepared(request, prepared)
        assert reducer.store.read(opening.context).record.day == 0
