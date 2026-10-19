"""Synthetic real-SQLite history invariants with independently derived outcomes."""
from dataclasses import asdict
from copy import deepcopy
import json
import os
import subprocess
import sys
import sqlite3
import pytest
from poliscope_engine.contracts.revisions import (
    RevisionInputs, CreateRequest, PreviewRequest, ApplyRequest, BranchRequest, HistoryQuery)
from poliscope_engine.contracts.world import WorldInspectParams, PartitionValueDTO
from poliscope_engine.evaluation.identity import digest
from poliscope_engine.numeric import RUNTIME_ID
from poliscope_engine.storage import Store, StorageError
from poliscope_engine.revisions import Revisions, RevisionError
from poliscope_engine.world import StateOwner
from test_evaluation import design
from test_mechanism_registry import world, PROVENANCE
from test_dependencies import plain, request as dependency
from test_solvers import host, quantity


def mechanism_registry():
    definition = plain(('synthetic:in',)).model_copy(update={'read_partitions': ['design']})
    return host(definition, lambda p, i: quantity(str(int(i['synthetic:in'].value) * 3)))


def value(number='2'):
    return PartitionValueDTO(id='amount', entity_id='supply', scope_id='local', partition='design',
        property_id='mass', value=quantity(number), effective_time=dict(tick=0, calendar_id='calendar'),
        provenance=PROVENANCE)


def inputs():
    w = world(owners=[StateOwner('supply', 'mass', 'design', 'player')])
    d = design(dependency(('a',), plain(('synthetic:in',))),
        world_inputs=[dict(consumer=dict(instance_id='a', port_id='synthetic:in'), value_id='amount')])
    return RevisionInputs.model_validate(dict(versions=dict(world_schema=1, catalog_id='synthetic:catalog',
        model_id='synthetic:model', numeric_runtime_id=RUNTIME_ID), entities=list(w.entities), scopes=list(w.scopes),
        values=[value()], owners=[asdict(o) for o in w.owners], populations=[], relationships=[],
        design=d, assumptions=[], measurements=[], goals=[], references=[]))


def create_request(service, **updates):
    return CreateRequest.model_validate(dict(revision_contract=1, data_store_id=service.data_store_id,
        civilization_id='civ', branch_id='main', name='Synthetic', operation_id='create', inputs=inputs()) | updates)


@pytest.fixture
def repo(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        created = service.create(create_request(service))
        yield service, created


def preview_request(context, number='5', **updates):
    return PreviewRequest.model_validate(dict(revision_contract=1, context=context,
        changes=[dict(kind='set_values', writer_id='player', partition='design', values=[value(number)])],
        decision=dict(alternatives=[], selected_id=None, rationale_ref=None)) | updates)


def apply_request(service, context, number='5', op='apply', **updates):
    preview = preview_request(context, number)
    candidate = service.preview(preview)
    return ApplyRequest.model_validate(dict(revision_contract=1, preview=preview,
        candidate_digest=candidate.candidate_digest, operation_id=op) | updates)


def move(service, outcome, action, **updates):
    data = dict(revision_contract=1, context=outcome.context, expected_sequence=outcome.branch_sequence,
        operation_id=action + str(outcome.branch_sequence), action=action, new_branch_id=None, name=None)
    return service.change_branch(BranchRequest.model_validate(data | updates))


def count(service):
    return {table: service.store._connection.execute('SELECT count(*) FROM ' + table).fetchone()[0]
            for table in ('contexts', 'records', 'evidence', 'operations', 'caches')}


def output(evidence):
    return next(o.value.value for o in evidence.evaluation.observations if o.node[0] == 'output')


def test_create_query_evaluate_and_preview_are_independent_of_ui(repo):
    service, created = repo
    context = created.context
    assert output(service.evidence(context)) == '6'  # input 2 * declared multiplier 3
    query = WorldInspectParams(world_schema=1, context=context, collection='values', cursor=None, limit=10)
    assert service.inspect(query).page.items[0].value.value == '2'
    before = count(service)
    candidate = service.preview(preview_request(context))
    assert count(service) == before
    assert service.branch(context).context == context
    assert candidate.affected_scope_ids == ['local']
    assert candidate.changed_value_ids == ['amount']
    assert candidate.report.physical_output_digest != service.evidence(context).evaluation.identities.output_digest
    assert output(service.evidence(context)) == '6'


def test_apply_reconstructs_and_commits_one_revision_with_evidence(repo):
    service, created = repo
    request = apply_request(service, created.context)
    accepted = service.apply(request)
    assert output(service.evidence(accepted.context)) == '15'
    assert output(service.evidence(created.context)) == '6'
    assert service.read(accepted.context).parent_id == created.context.revision_id
    assert service.branch(created.context).context == accepted.context
    before = count(service)
    assert service.apply(request) == accepted
    assert count(service) == before


def test_replay_after_head_advances_and_current_model_removed(repo):
    service, created = repo
    request = apply_request(service, created.context)
    first = service.apply(request)
    second = service.apply(apply_request(service, first.context, '8', op='second'))
    service.registry = None  # no evaluation/model lookup may run on completed replay
    assert service.apply(request) == first
    assert service.status('apply', request) == first
    assert service.branch(first.context).context == second.context
    assert output(service.evidence(first.context)) == '15'


@pytest.mark.parametrize('field', ['payload', 'digest', 'branch', 'base'])
def test_changed_request_operation_key_conflicts_before_head_check(repo, field):
    service, created = repo
    request = apply_request(service, created.context)
    accepted = service.apply(request)
    data = request.model_dump()
    if field == 'payload':
        data['preview']['changes'][0]['values'][0]['value']['value'] = '9'
    elif field == 'digest':
        data['candidate_digest'] = 'sha256:' + '0' * 64
    elif field == 'branch':
        fork = move(service, accepted, 'fork', new_branch_id='other', name='Other')
        data['preview']['context']['branch_id'] = fork.context.branch_id
    else:
        data['preview']['context']['revision_id'] = accepted.context.revision_id
    before = count(service)
    with pytest.raises(StorageError, match='different request'):
        service.apply(ApplyRequest.model_validate(data))
    assert count(service) == before


@pytest.mark.parametrize('case', ['stale', 'digest', 'payload', 'wrong_store', 'wrong_civilization', 'wrong_branch'])
def test_invalid_apply_cannot_mutate_history(repo, case):
    service, created = repo
    request = apply_request(service, created.context)
    data = request.model_dump()
    if case == 'stale':
        service.apply(apply_request(service, created.context, '7', op='advancer'))
    elif case == 'digest':
        data['candidate_digest'] = 'sha256:' + '0' * 64
    elif case == 'payload':
        data['preview']['changes'][0]['values'][0]['value']['value'] = '9'
    else:
        key = {'wrong_store': 'data_store_id', 'wrong_civilization': 'civilization_id', 'wrong_branch': 'branch_id'}[case]
        data['preview']['context'][key] = 'missing'
    before = count(service)
    with pytest.raises(RevisionError):
        service.apply(ApplyRequest.model_validate(data))
    assert count(service) == before


def test_unknown_status_exact_binding_and_cross_context_isolation(repo):
    service, created = repo
    request = apply_request(service, created.context)
    assert service.status('apply', request) is None
    accepted = service.apply(request)
    assert service.status('apply', request) == accepted
    other = request.model_dump()
    other['preview']['context']['civilization_id'] = 'not-authorized'
    with pytest.raises(RevisionError, match='unknown_civilization'):
        service.status('apply', ApplyRequest.model_validate(other))
    other['preview']['context']['civilization_id'] = 'civ'
    other['preview']['context']['data_store_id'] = 'another-store'
    with pytest.raises(RevisionError, match='wrong_data_store'):
        service.status('apply', ApplyRequest.model_validate(other))


def test_reopen_and_cache_eviction_never_recompute_evidence(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        request = create_request(service)
        created = service.create(request)
        apply = apply_request(service, created.context)
        accepted = service.apply(apply)
        with store.transaction():
            store.clear_caches()
    with Store(tmp_path) as store:
        service = Revisions(store, registry=None)
        assert service.create(request) == created
        assert service.apply(apply) == accepted
        assert output(service.evidence(accepted.context)) == '15'
        assert output(service.evidence(created.context)) == '6'


def test_undo_redo_and_edit_preserve_both_futures_and_alternatives(repo):
    service, created = repo
    preview = preview_request(created.context)
    alternative = dict(id='chosen', changes=[c.model_dump() for c in preview.changes])
    rejected = dict(id='other', changes=[c.model_dump() for c in preview_request(created.context, '9').changes])
    decision = dict(alternatives=[alternative, rejected], selected_id='chosen',
                    rationale_ref=dict(id='private-note', visibility='private', status='available'))
    preview = PreviewRequest.model_validate(preview.model_dump() | dict(decision=decision))
    request = ApplyRequest(revision_contract=1, operation_id='decision', preview=preview,
                           candidate_digest=service.preview(preview).candidate_digest)
    future = service.apply(request)
    undone = move(service, future, 'undo')
    assert undone.context.revision_id == created.context.revision_id
    redone = move(service, undone, 'redo')
    assert redone.context == future.context
    undone = move(service, redone, 'undo')
    edited = service.apply(apply_request(service, undone.context, '7', op='new-future'))
    assert output(service.evidence(edited.context)) == '21'
    assert output(service.evidence(future.context)) == '15'
    assert service.read(future.context).decision.model_dump() == decision
    with pytest.raises(RevisionError, match='no_redo'):
        move(service, edited, 'redo')
    page = service.history(HistoryQuery(context=edited.context, cursor=None, limit=100))
    assert {row.context.revision_id for row in page.items} == {
        created.context.revision_id, future.context.revision_id, edited.context.revision_id}


def test_fork_rename_and_replay_preserve_lineage(repo):
    service, created = repo
    forked = move(service, created, 'fork', new_branch_id='fork', name='Experiment')
    fork_request = BranchRequest(revision_contract=1, context=created.context, expected_sequence=0,
        operation_id='fork0', action='fork', new_branch_id='fork', name='Experiment')
    assert service.change_branch(fork_request) == forked
    renamed = move(service, forked, 'rename', name='Named')
    assert service.branch(renamed.context).name == 'Named'
    assert service.branch(renamed.context).forked_from == created.context
    updated = service.apply(apply_request(service, forked.context, '11'))
    assert output(service.evidence(updated.context)) == '33'
    assert service.branch(created.context).context == created.context


def test_branch_sequence_prevents_aba_after_undo_redo(repo):
    service, created = repo
    future = service.apply(apply_request(service, created.context))
    undone = move(service, future, 'undo')
    redone = move(service, undone, 'redo')
    with pytest.raises(RevisionError, match='stale_branch'):
        move(service, future, 'rename', name='stale')
    assert service.branch(redone.context).sequence == 3


@pytest.mark.parametrize('method', ['_persist', '_save_branch', 'complete_operation'])
def test_failure_at_each_publication_stage_rolls_back_everything(repo, monkeypatch, method):
    service, created = repo
    request = apply_request(service, created.context)
    before = count(service)
    target = service.store if method == 'complete_operation' else service
    original = getattr(target, method)
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise sqlite3.OperationalError('synthetic disk failure')
    with monkeypatch.context() as m:
        m.setattr(target, method, fail)
        with pytest.raises(sqlite3.OperationalError):
            service.apply(request)
    assert count(service) == before
    assert service.status('apply', request) is None
    assert service.branch(created.context).context == created.context
    assert output(service.evidence(service.apply(request).context)) == '15'


def test_history_pagination_binds_context_and_preserves_all_revisions(repo):
    service, created = repo
    current = created
    for i in range(3):
        current = service.apply(apply_request(service, current.context, str(i + 3), op=str(i)))
    cursor, ids = None, []
    while True:
        page = service.history(HistoryQuery(context=current.context, cursor=cursor, limit=1))
        ids.extend(r.context.revision_id for r in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert len(ids) == len(set(ids)) == 4
    cursor = service.history(HistoryQuery(context=current.context, cursor=None, limit=1)).next_cursor
    with pytest.raises(RevisionError, match='invalid_history_cursor'):
        service.history(HistoryQuery(context=created.context, cursor=cursor, limit=1))


def test_world_cursor_binds_collection_and_revision(repo):
    service, created = repo
    query = WorldInspectParams(world_schema=1, context=created.context, collection='entities', cursor=None, limit=1)
    page = service.inspect(query)
    assert page.page.next_cursor is not None
    second = service.inspect(query.model_copy(update={'cursor': page.page.next_cursor}))
    assert second.page.items[0].id != page.page.items[0].id
    with pytest.raises(RevisionError, match='invalid_world_cursor'):
        service.inspect(query.model_copy(update={'collection': 'values', 'cursor': page.page.next_cursor}))


@pytest.mark.parametrize('case', ['owner', 'selected', 'duplicate', 'model', 'dangling'])
def test_invalid_candidate_structures_fail_without_writes(repo, case):
    service, created = repo
    data = preview_request(created.context).model_dump()
    if case == 'owner':
        data['changes'][0]['writer_id'] = 'other'
    elif case == 'selected':
        data['decision']['selected_id'] = 'not-offered'
    elif case == 'duplicate':
        data['changes'][0]['values'] *= 2
    else:
        snapshot = inputs().model_dump()
        if case == 'model':
            snapshot['versions']['model_id'] = 'changed'
        else:
            snapshot['values'][0]['entity_id'] = 'missing'
        data['changes'] = [dict(kind='replace_inputs', inputs=snapshot)]
    before = count(service)
    with pytest.raises(ValueError):
        service.preview(PreviewRequest.model_validate(data))
    assert count(service) == before


def test_two_connections_recheck_current_head_under_sqlite_lock(tmp_path):
    with Store(tmp_path) as a, Store(tmp_path) as b:
        first, second = Revisions(a, registry=mechanism_registry()), Revisions(b, registry=mechanism_registry())
        assert first.data_store_id == second.data_store_id
        created = first.create(create_request(first))
        request_a = apply_request(first, created.context, '5', op='a')
        request_b = apply_request(second, created.context, '7', op='b')
        accepted = first.apply(request_a)
        with pytest.raises(RevisionError, match='stale_revision'):
            second.apply(request_b)
        assert second.branch(created.context).context == accepted.context


def test_process_exit_after_commit_before_reply_recovers_original(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        created = service.create(create_request(service))
        request = apply_request(service, created.context)
    script = '''
import os,sys
from pathlib import Path
from test_revisions import mechanism_registry
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import ApplyRequest
with Store(Path(sys.argv[1])) as store:
    repo = Revisions(store, registry=mechanism_registry())
    repo.apply(ApplyRequest.model_validate_json(sys.argv[2]))
    os._exit(47)
'''
    env = dict(os.environ, PYTHONPATH=str(__import__('pathlib').Path(__file__).parent))
    process = subprocess.run([sys.executable, '-c', script, str(tmp_path), request.model_dump_json()], env=env)
    assert process.returncode == 47
    with Store(tmp_path) as store:
        service = Revisions(store, registry=None)
        accepted = service.status('apply', request)
        assert accepted is not None
        assert service.apply(request) == accepted
        assert output(service.evidence(accepted.context)) == '15'
        assert len(service.history(HistoryQuery(context=accepted.context, cursor=None, limit=100)).items) == 2


def test_open_uses_confirmed_head_and_preserves_immutable_event_payload(repo):
    service, created = repo
    request = apply_request(service, created.context)
    candidate = service.preview(request.preview)
    diff = next(d for d in candidate.differences if d.node[0] == 'output')
    assert diff.before.value.value == '6'
    assert diff.after.value.value == '15'
    accepted = service.apply(request)
    opened = service.open(data_store_id=service.data_store_id, civilization_id='civ', branch_id='main')
    assert opened.context == accepted.context
    assert service.read(accepted.context).applied_preview == request.preview


def test_same_operation_id_is_scoped_by_civilization_and_kind(repo):
    service, created = repo
    other_inputs = inputs().model_dump()
    other_inputs['entities'][0]['id'] = 'second-civ'
    second = service.create(create_request(service, civilization_id='second-civ', inputs=RevisionInputs.model_validate(other_inputs)))
    first_op = service.apply(apply_request(service, created.context, '5', op='shared'))
    second_op = service.apply(apply_request(service, second.context, '7', op='shared'))
    assert output(service.evidence(first_op.context)) == '15'
    assert output(service.evidence(second_op.context)) == '21'
    renamed = move(service, first_op, 'rename', name='named', operation_id='shared')
    assert renamed.context == first_op.context


def test_valid_unknown_and_incomplete_design_is_accepted_with_findings(repo):
    service, created = repo
    snapshot = inputs().model_dump()
    snapshot['values'][0]['value'] = dict(kind='unknown', reason='Synthetic unavailable input')
    from test_measurements import indicator
    snapshot['measurements'] = [indicator().model_dump()]
    preview = preview_request(created.context).model_dump()
    preview['changes'] = [dict(kind='replace_inputs', inputs=snapshot)]
    preview = PreviewRequest.model_validate(preview)
    candidate = service.preview(preview)
    accepted = service.apply(ApplyRequest(revision_contract=1, operation_id='unknown', preview=preview,
                                         candidate_digest=candidate.candidate_digest))
    evidence = service.evidence(accepted.context)
    assert evidence.evaluation.outcome == 'incomplete'
    assert any(o.status == 'missing_input' for o in evidence.evaluation.observations)
    assert evidence.report.findings


def test_model_callback_change_under_same_version_cannot_accept_old_preview(repo):
    service, created = repo
    request = apply_request(service, created.context)
    definition = plain(('synthetic:in',)).model_copy(update={'read_partitions': ['design']})
    service.registry = host(definition, lambda p, i: quantity('999'))
    before = count(service)
    with pytest.raises(RevisionError, match='candidate_digest_mismatch'):
        service.apply(request)
    assert count(service) == before
    assert output(service.evidence(created.context)) == '6'


@pytest.mark.parametrize('stage', ['_blob', '_save_branch', 'complete_operation'])
def test_create_failure_rolls_back_context_and_all_closure_chunks(tmp_path, monkeypatch, stage):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        before = count(service)
        request = create_request(service)
        target = store if stage == 'complete_operation' else service
        original = getattr(target, stage)
        def fail(*a, **k):
            original(*a, **k)
            raise sqlite3.OperationalError('synthetic failure')
        with monkeypatch.context() as m:
            m.setattr(target, stage, fail)
            with pytest.raises(sqlite3.OperationalError):
                service.create(request)
        assert count(service) == before
        assert service.status('create', request) is None
        assert service.create(request)


def test_chunked_accepted_closure_roundtrips_beyond_single_record(repo):
    service, created = repo
    scope = service._context(created.context)
    # Independently formed 1.2 MiB JSON object exercises UTF-8 and escaped chunks.
    payload = {'data': ('é"\\' * 200000)}
    with service.store.transaction():
        service._blob(scope, 'synthetic', 'large', payload)
    assert json.loads(service._read_blob(scope, 'synthetic', 'large')) == payload
    chunks = service.store.record_page(scope, 'chunk:synthetic', limit=100)
    assert len(chunks) > 1
    assert all(len(raw.encode()) <= 1024 * 1024 for _, raw in chunks)


def test_missing_accepted_closure_chunk_is_unavailable_not_recomputed(repo, monkeypatch):
    service, created = repo
    original = service.store.read_record
    def missing(scope, kind, identity):
        if kind == 'chunk:accepted':
            return None
        return original(scope, kind, identity)
    monkeypatch.setattr(service.store, 'read_record', missing)
    service.registry = None
    with pytest.raises(RevisionError, match='unavailable_snapshot_chunk'):
        service.evidence(created.context)


def test_oversized_closure_failure_rolls_back_before_head_publication(repo, monkeypatch):
    import poliscope_engine.revisions as module
    service, created = repo
    request = apply_request(service, created.context)
    before = count(service)
    monkeypatch.setattr(module, 'MAX_BLOB_BYTES', 1000)
    with pytest.raises(RevisionError, match='retained_snapshot_too_large'):
        service.apply(request)
    assert count(service) == before
    assert service.branch(created.context).context == created.context


def test_disk_lock_failure_does_not_accept_or_forget_request(tmp_path):
    with Store(tmp_path) as a, Store(tmp_path) as b:
        first, second = Revisions(a, registry=mechanism_registry()), Revisions(b, registry=mechanism_registry())
        created = first.create(create_request(first))
        request = apply_request(second, created.context)
        with a.transaction():
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                second.apply(request)
        assert second.status('apply', request) is None
        assert output(second.evidence(second.apply(request).context)) == '15'


def test_process_exit_during_transaction_preserves_last_confirmed_head(tmp_path):
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        created = service.create(create_request(service))
        request = apply_request(service, created.context)
        before = count(service)
    script = '''
import os,sys
from pathlib import Path
from test_revisions import mechanism_registry
from poliscope_engine.storage import Store
from poliscope_engine.revisions import Revisions
from poliscope_engine.contracts.revisions import ApplyRequest
with Store(Path(sys.argv[1])) as store:
    repo = Revisions(store, registry=mechanism_registry())
    original = repo._save_branch
    def crash(*args):
        original(*args)
        os._exit(48)
    repo._save_branch = crash
    repo.apply(ApplyRequest.model_validate_json(sys.argv[2]))
'''
    env = dict(os.environ, PYTHONPATH=str(__import__('pathlib').Path(__file__).parent))
    process = subprocess.run([sys.executable, '-c', script, str(tmp_path), request.model_dump_json()], env=env)
    assert process.returncode == 48
    with Store(tmp_path) as store:
        service = Revisions(store, registry=mechanism_registry())
        assert count(service) == before
        assert service.branch(created.context).context == created.context
        assert service.status('apply', request) is None
        assert output(service.evidence(service.apply(request).context)) == '15'


@pytest.mark.parametrize('case', ['undo-root', 'redo-empty', 'duplicate-fork', 'wrong-sequence', 'bad-rename'])
def test_invalid_branch_moves_leave_original_journal(repo, case):
    service, created = repo
    action, updates = 'undo', {}
    if case == 'redo-empty':
        action = 'redo'
    elif case == 'duplicate-fork':
        action, updates = 'fork', dict(new_branch_id='main', name='Duplicate')
    elif case == 'wrong-sequence':
        action, updates = 'rename', dict(name='No', expected_sequence=7)
    elif case == 'bad-rename':
        action = 'rename'
    before = count(service)
    with pytest.raises(RevisionError):
        move(service, created, action, **updates)
    assert count(service) == before


def test_branch_failure_after_journal_write_rolls_back_operation(repo, monkeypatch):
    service, created = repo
    before = count(service)
    original = service.store.complete_operation
    def fail(*a):
        original(*a)
        raise sqlite3.OperationalError('synthetic branch failure')
    with monkeypatch.context() as m:
        m.setattr(service.store, 'complete_operation', fail)
        with pytest.raises(sqlite3.OperationalError):
            move(service, created, 'rename', name='not-published')
    assert count(service) == before
    assert service.branch(created.context).name == 'Synthetic'


def test_snapshot_inputs_and_returned_data_are_detached(repo):
    service, created = repo
    request = apply_request(service, created.context)
    first = service.preview(request.preview)
    first.report.traces.clear()
    first.changed_value_ids.clear()
    assert service.preview(request.preview).changed_value_ids == ['amount']
    saved = service.read(created.context)
    saved.inputs.entities.clear()
    assert len(service.read(created.context).inputs.entities) == 3


@pytest.mark.parametrize('kind', ['entity', 'value', 'scope'])
def test_complete_snapshot_cannot_rebind_canonical_identity(repo, kind):
    service, created = repo
    snapshot = inputs().model_dump()
    if kind == 'entity':
        snapshot['entities'][1]['entity_kind'] = 'asset'
    elif kind == 'scope':
        snapshot['scopes'][0]['scope_kind'] = 'region'
    else:
        snapshot['values'][0]['property_id'] = 'different'
        snapshot['owners'][0]['property_id'] = 'different'
    data = preview_request(created.context).model_dump()
    data['changes'] = [dict(kind='replace_inputs', inputs=snapshot)]
    with pytest.raises(RevisionError, match='canonical_identity_rebound'):
        service.preview(PreviewRequest.model_validate(data))


def test_missing_executable_model_blocks_new_preview_but_keeps_history(repo):
    service, created = repo
    service.registry = None
    with pytest.raises(RevisionError, match='unavailable_model_or_numeric_runtime'):
        service.preview(preview_request(created.context))
    assert output(service.evidence(created.context)) == '6'


def test_accepted_account_results_and_trace_closure_survive_reopen(tmp_path):
    from test_solvers import contention
    req, registry = contention()
    snapshot = inputs().model_dump()
    execution_data = req.model_dump()
    for claim in execution_data['batch']['claims']:
        claim['claimant_id'] = 'supply'
    snapshot['design'] = design(execution=execution_data).model_dump()
    snapshot['values'] = []
    snapshot['owners'] = []
    with Store(tmp_path) as store:
        service = Revisions(store, registry=registry)
        created = service.create(create_request(service, inputs=RevisionInputs.model_validate(snapshot)))
        evidence = service.evidence(created.context)
        # Stock 100, two ordered claims of 100: only the first can consume stock.
        assert sorted((c.claim_id, c.actual, c.unmet) for c in evidence.evaluation.accounts.claims) == [
            ('a', '100', '0'), ('b', '0', '100')]
        assert evidence.evaluation.accounts.accounts[0].closing == '0'
        assert evidence.evaluation.outcome == 'insufficient'
        before = evidence.model_dump_json()
    with Store(tmp_path) as store:
        service = Revisions(store, registry=None)
        saved = service.evidence(created.context)
        assert saved.model_dump_json() == before
        assert any(t.members[0].node[0] == 'claim_result' for t in saved.report.traces)


def test_goal_only_edit_preserves_accepted_physics(repo):
    from test_measurements import indicator, goal
    service, created = repo
    snapshot = inputs().model_dump()
    snapshot['measurements'] = [indicator().model_dump()]
    snapshot['goals'] = [goal().model_dump()]
    data = preview_request(created.context).model_dump()
    data['changes'] = [dict(kind='replace_inputs', inputs=snapshot)]
    preview = PreviewRequest.model_validate(data)
    candidate = service.preview(preview)
    accepted = service.apply(ApplyRequest(revision_contract=1, operation_id='goal', preview=preview,
        candidate_digest=candidate.candidate_digest))
    assert service.evidence(accepted.context).evaluation == service.evidence(created.context).evaluation
    assert service.evidence(accepted.context).report.goals[0].matched is True
    assert candidate.differences == []
